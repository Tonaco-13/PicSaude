from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator

from app.auth.dependencies import require_role
from app.config import PICSAUDE_DECISAO_CLINICA
from app.database import get_conn
from app.database_tx import get_tx
from app.domain.auditoria_decisao import TIPO_EVENTO_DECISAO, montar_trilha_decisao
from app.domain.documento_canonico import montar_documento, montar_documento_de_conn
from app.domain.ledger import registrar_evento_ledger
from app.domain.outbox import registrar_outbox
from app.instance import get_instance_id_conn
from app.domain.pdf_prescricao import gerar_pdf_prescricao
from app.domain.assinatura import (
    MODOS_DIGITAIS_VALIDOS,
    MODOS_COM_VALIDADE_CFM,
    calcular_nivel_formal,
    campos_cfm_ausentes_no_item,
)
from app.domain.medicamento import (
    normalizar_unidade,
    unidade_valida,
    prescricao_atomizavel,
    ESTADOS_ITEM_CIRCULAVEIS,
)
from app.domain.cnes_prescritor import validar_cns_prescritor
from app.domain.confianca_cuidado import calcular_score_confianca_prescricao
from app.domain.string_validacao import gerar_string_validacao_identidade, hash_cert_der
from app.domain.icp_identity import parsear_certificado_icp
from app.domain.identidade_prescritor import resolver_identidade_prescritor
from app.domain.assinatura_icp import verificar_assinatura_icp, serializar_payload
from app.utils.helpers import normalize_cns, normalize_cpf, normalize_nome

router = APIRouter(prefix="/prescricoes", tags=["prescricoes"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_TIPOS_EMISSAO_VALIDOS = {"nova", "correcao", "renovacao"}

# CPF sentinela para prescrições físicas sem identificação digital do paciente.
# CONVENÇÃO TÉCNICA: '00000000000' nunca é um CPF real (dígitos verificadores inválidos).
# Queries analíticas devem excluir este valor: WHERE cpf != '00000000000'.
# Nunca expor este valor em relatórios de auditoria como se fosse identificação real.
_CPF_NAO_IDENTIFICADO = "00000000000"


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class ItemIn(BaseModel):
    nome_medicamento: str
    concentracao: Optional[str] = None
    quantidade: Optional[int] = None
    unidade_quantidade: Optional[str] = None   # vocabulário controlado (domain/medicamento.py)
    forma_farmaceutica: Optional[str] = None   # apresentação livre ("1 cx c/ 30 cáps.")
    posologia: Optional[str] = None
    # Ticket 44 — classe regulatória; None = medicamento comum (elegível para atomização)
    # Valores que bloqueiam: A1, A2, A3, B1, B2, C5, D1, D2
    classe_controle: Optional[str] = None
    # Ticket 18 — Retenção por RDC 471/2021 (independente da Portaria 344).
    # NULL = não sujeito; 'antimicrobiano' (RDC 471/IN 83) ou 'glp1_agonista' (IN 360/2025).
    tipo_retencao: Optional[str] = None

    @field_validator("tipo_retencao")
    @classmethod
    def tipo_retencao_valido_vocab(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        from app.domain.retencao import TIPOS_RETENCAO_VALIDOS
        v_norm = v.strip().lower()
        if v_norm not in TIPOS_RETENCAO_VALIDOS:
            raise ValueError(
                f"tipo_retencao '{v}' não pertence ao vocabulário controlado. "
                f"Valores aceitos: {sorted(TIPOS_RETENCAO_VALIDOS)}"
            )
        return v_norm

    @field_validator("quantidade")
    @classmethod
    def quantidade_positiva(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("quantidade deve ser maior que zero")
        return v

    @field_validator("unidade_quantidade")
    @classmethod
    def unidade_valida_vocab(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalizado = normalizar_unidade(v)
        if normalizado is None:
            from app.domain.medicamento import UNIDADES_LISTA
            raise ValueError(
                f"unidade_quantidade '{v}' não pertence ao vocabulário controlado. "
                f"Valores aceitos: {UNIDADES_LISTA}"
            )
        return normalizado

    @field_validator("nome_medicamento")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_medicamento não pode ser vazio")
        return v.strip().upper()


class PrescricaoIn(BaseModel):
    cns_prescritor: str
    nome_prescritor: Optional[str] = None   # usado para auto-registro na primeira emissão
    cpf_paciente: str
    nome_paciente: str
    assinatura_modo: Optional[str] = None
    tipo_emissao: str = "nova"
    origem_prescricao_id: Optional[int] = None
    # Ticket 36 — Contexto clínico estruturado (ambos opcionais, sem default)
    # A validação semântica do CID é responsabilidade da IA CID, não do backend.
    indicacao_clinica: Optional[str] = None   # texto clínico livre (hipótese diagnóstica)
    codigo_cid: Optional[str] = None          # código CID-10 escolhido explicitamente (ex: "I10")
    # Ticket 63 — Escolha de modo de entrega na emissão.
    # True  = criar custódia prescritor→paciente imediatamente (carteira digital).
    # False = prescrição fica 'pendente', paciente acessa via link (comportamento original).
    enviar_ao_paciente: bool = False
    # Ticket 67 — Certificado ICP-Brasil (PEM) para binding criptográfico.
    # Opcional: quando presente, o backend extrai CPF/conselho e gera string_validacao_prescritor.
    # Quando ausente: string_validacao_prescritor = NULL (emissão sem binding ICP).
    cert_pem: Optional[str] = None
    # Ticket 68 — Assinatura ICP RSA PKCS1v15 SHA-256 sobre o digest do payload.
    # Gerada pelo WebCrypto/WebPKI no frontend sobre o digest SHA-256 do payload canônico.
    # Requer cert_pem. Quando ambos ausentes → emissão no modo físico (sem verificação).
    # Quando cert_pem presente mas assinatura_b64 ausente → binding ICP sem verificação de assinatura.
    assinatura_b64: Optional[str] = None
    itens: List[ItemIn] = []

    @field_validator("tipo_emissao")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_EMISSAO_VALIDOS:
            raise ValueError(
                f"tipo_emissao inválido: '{v}'. Valores aceitos: {sorted(_TIPOS_EMISSAO_VALIDOS)}"
            )
        return v

    @field_validator("assinatura_modo")
    @classmethod
    def assinatura_valida(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODOS_DIGITAIS_VALIDOS:
            raise ValueError(
                f"assinatura_modo inválido: '{v}'. "
                f"Valores aceitos: {sorted(MODOS_DIGITAIS_VALIDOS)}"
            )
        return v

    @model_validator(mode="after")
    def origem_obrigatoria_para_nao_nova(self) -> "PrescricaoIn":
        if self.tipo_emissao != "nova" and self.origem_prescricao_id is None:
            raise ValueError(
                f"origem_prescricao_id é obrigatório quando tipo_emissao='{self.tipo_emissao}'"
            )
        return self

    @model_validator(mode="after")
    def campos_cfm_obrigatorios(self) -> "PrescricaoIn":
        """
        Prescrições que declaram modo de assinatura com pretensão de validade
        CFM (icp_brasil_local, gov_br_nuvem) devem carregar:
          - CPF real do paciente (não sentinela '00000000000')
          - posologia e quantidade em todos os itens
        """
        if self.assinatura_modo not in MODOS_COM_VALIDADE_CFM:
            return self

        # CPF real obrigatório — sentinela '00000000000' é reservado para físico
        cpf_normalizado = normalize_cpf(self.cpf_paciente) if self.cpf_paciente else ""
        if not cpf_normalizado or cpf_normalizado == _CPF_NAO_IDENTIFICADO:
            raise ValueError(
                "Para prescrições com assinatura digital (CFM), "
                "cpf_paciente deve ser um CPF real. "
                "O sentinela '00000000000' é reservado para emissões físicas."
            )

        # Campos obrigatórios por item
        itens_invalidos = []
        for idx, item in enumerate(self.itens, start=1):
            ausentes = campos_cfm_ausentes_no_item(item)
            if ausentes:
                itens_invalidos.append(f"item {idx}: {ausentes}")

        if itens_invalidos:
            raise ValueError(
                f"Campos obrigatórios ausentes para prescrição com validade CFM "
                f"(assinatura_modo='{self.assinatura_modo}'): {'; '.join(itens_invalidos)}. "
                f"Campos exigidos por item: nome_medicamento, quantidade, unidade_quantidade, posologia."
            )

        return self


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def criar_prescricao(payload: PrescricaoIn, usuario=Depends(require_role("prescritor"))):
    if not payload.itens:
        raise HTTPException(status_code=422, detail="A prescrição deve conter ao menos um item.")

    # ------------------------------------------------------------------
    # Ticket 68A — Guardrail: cert_pem e assinatura_b64 são par inseparável.
    # Cenário B (apenas um dos dois) é inválido — rejeitar antes de qualquer
    # persistência. Fluxo físico (nenhum) e digital (ambos) continuam normais.
    # ------------------------------------------------------------------
    _tem_cert = bool(payload.cert_pem)
    _tem_assinatura = bool(payload.assinatura_b64)
    if _tem_cert != _tem_assinatura:
        raise HTTPException(
            status_code=422,
            detail="Assinatura criptográfica ausente ou inconsistente para o certificado informado.",
        )

    cns = normalize_cns(payload.cns_prescritor)
    # V1 (TICKET-5C §4.1) — CNS declarado deve coincidir com o JWT.
    if normalize_cns(usuario["sub"]) != cns:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "prescritor_mismatch",
                "mensagem": "CNS do payload não coincide com prescritor autenticado.",
            },
        )
    cpf = normalize_cpf(payload.cpf_paciente)
    nome = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    conn = get_conn()
    try:
        # Ticket 4D.1 (snippet §4.1): instance_id obtido UMA VEZ, dentro do
        # try, antes de qualquer evento. Se get_conn() falhou, o try não é
        # alcançado; se get_instance_id_conn falhar aqui, o except limpa.
        instance_id = get_instance_id_conn(conn)

        # ------------------------------------------------------------------
        # 1. Localizar ou criar prescritor por CNS
        # ------------------------------------------------------------------
        prescritor = conn.execute(
            "SELECT id, nome FROM prescritores WHERE cns = ?", (cns,)
        ).fetchone()
        if prescritor:
            prescritor_id = prescritor["id"]
            nome_prescritor_final = prescritor["nome"]
        else:
            nome_pres = normalize_nome(payload.nome_prescritor or "")
            if not nome_pres:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Prescritor com CNS '{cns}' não encontrado. "
                        "Envie 'nome_prescritor' para registrá-lo automaticamente."
                    ),
                )
            cursor = conn.execute(
                """
                INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
                VALUES (?, ?, true, ?, ?)
                """,
                (cns, nome_pres, agora, agora),
            )
            prescritor_id = cursor.lastrowid
            nome_prescritor_final = nome_pres

        # ------------------------------------------------------------------
        # 2. Validar prescrição de origem (quando correcao / renovacao)
        # ------------------------------------------------------------------
        if payload.origem_prescricao_id is not None:
            origem = conn.execute(
                "SELECT id FROM prescricoes WHERE id = ?", (payload.origem_prescricao_id,)
            ).fetchone()
            if not origem:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prescrição de origem id={payload.origem_prescricao_id} não encontrada.",
                )

        # ------------------------------------------------------------------
        # 3. Localizar ou criar paciente por CPF
        # Concorrência: INSERT OR IGNORE garante atomicidade — se outra thread
        # inserir o mesmo CPF entre o check e o insert, ON CONFLICT é silencioso
        # e o SELECT subsequente sempre encontra a linha vencedora.
        # ------------------------------------------------------------------
        paciente_antes = conn.execute(
            "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
        ).fetchone()
        paciente_existia = paciente_antes is not None

        # 5A — entrega digital solicitada sem carteira disponível
        # (ver TICKET-5A-CARTEIRA-DIGITAL-422.md §3.1 — "paciente_existia=False"
        # é a inferência atual para "sem carteira digital"; modelo pode evoluir.)
        if payload.enviar_ao_paciente and not paciente_existia:
            raise HTTPException(
                status_code=422,
                detail={
                    "codigo": "patient_no_digital_wallet",
                    "mensagem": (
                        "Paciente sem carteira digital disponível. "
                        "Emissão rejeitada porque a entrega digital solicitada não é possível. "
                        "Reemita com enviar_ao_paciente=false ou cadastre o paciente antes."
                    ),
                },
            )

        conn.execute(
            """
            INSERT OR IGNORE INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (?, ?, true, ?, ?)
            """,
            (cpf, nome, agora, agora),
        )
        paciente_id = conn.execute(
            "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
        ).fetchone()["id"]
        # Ticket 63: paciente_existia determina se há carteira digital prévia

        # ------------------------------------------------------------------
        # 4. Inserir prescrição (com tipo_emissao, origem_prescricao_id e
        #    contexto clínico opcional — Ticket 36)
        # ------------------------------------------------------------------
        cursor = conn.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, origem_prescricao_id,
               indicacao_clinica, codigo_cid,
               data_emissao, data_validade, created_at, updated_at)
            VALUES (?, ?, ?, 'pendente', ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                protocolo,
                prescritor_id,
                paciente_id,
                payload.assinatura_modo,
                payload.tipo_emissao,
                payload.origem_prescricao_id,
                payload.indicacao_clinica or None,
                payload.codigo_cid or None,
                agora,
                agora,
                agora,
            ),
        )
        prescricao_id = cursor.lastrowid

        # ------------------------------------------------------------------
        # 5. Inserir itens
        # ------------------------------------------------------------------
        itens_emitidos: list[tuple[int, str]] = []   # (item_id, nome) p/ camada 3
        for item in payload.itens:
            cur_item = conn.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   unidade_quantidade, forma_farmaceutica,
                   posologia, status_item, classe_controle, tipo_retencao,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?, ?)
                """,
                (
                    prescricao_id,
                    item.nome_medicamento,
                    item.concentracao,
                    item.quantidade,
                    item.unidade_quantidade,
                    item.forma_farmaceutica,
                    item.posologia,
                    item.classe_controle or None,
                    item.tipo_retencao or None,
                    agora,
                    agora,
                ),
            )
            itens_emitidos.append((cur_item.lastrowid, item.nome_medicamento))

        # ------------------------------------------------------------------
        # 6. Gerar documento canônico e armazenar hash de integridade
        # ------------------------------------------------------------------
        doc_result = montar_documento(
            protocolo       = protocolo,
            data_emissao    = agora,
            tipo_emissao    = payload.tipo_emissao,
            assinatura_modo = payload.assinatura_modo,
            cns_prescritor  = cns,
            nome_prescritor = nome_prescritor_final,
            cpf_paciente    = cpf,
            nome_paciente   = nome,
            itens           = payload.itens,
        )
        conn.execute(
            "UPDATE prescricoes SET assinatura_hash = ? WHERE id = ?",
            (doc_result.hash_sha256, prescricao_id),
        )

        # ------------------------------------------------------------------
        # 7. Gravar evento de emissão no ledger
        #    Ticket 36: enriquece payload com contexto clínico (quando presente).
        #    Ticket 47: enriquece payload com bloco cnes_validacao (sem bloquear emissão).
        #    Não cria novo tipo de evento — apenas adiciona campos ao payload
        #    já existente de 'prescricao_emitida'. Campos ausentes ficam omitidos.
        # ------------------------------------------------------------------
        ev_payload: dict = {
            "tipo_emissao": payload.tipo_emissao,
            "origem_prescricao_id": payload.origem_prescricao_id,
            "assinatura_modo": payload.assinatura_modo,
        }
        if payload.indicacao_clinica:
            ev_payload["indicacao_clinica"] = payload.indicacao_clinica
        if payload.codigo_cid:
            ev_payload["codigo_cid"] = payload.codigo_cid

        # Ticket 47/48 — Camada 6: Validação CNES do Prescritor
        # Não bloqueia emissão. Resultado gravado no evento para auditoria.
        # org_id=None: PrescricaoIn não carrega org_id ainda (rollout incremental).
        cnes_validacao = validar_cns_prescritor(conn, cns, nome_prescritor_final, org_id=None)
        ev_payload["cnes_validacao"] = cnes_validacao

        # Ticket 50 — Score Composto de Confiança do Cuidado
        score_confianca = calcular_score_confianca_prescricao(cnes_validacao)
        ev_payload["score_confianca"] = score_confianca

        # ------------------------------------------------------------------
        # Ticket 68 — Verificação criptográfica da assinatura ICP
        # Executada ANTES de gerar string_validacao (T67).
        # Cenário A: cert_pem + assinatura_b64 → verificação matemática obrigatória.
        #   - Assinatura inválida → HTTPException 422 (não persiste prescrição).
        #   - Certificado expirado → HTTPException 422.
        # Cenário B: somente cert_pem → binding ICP sem verificação de assinatura.
        # Cenário C: nenhum → fluxo físico (sem ICP, sem verificação).
        # ------------------------------------------------------------------
        resultado_assinatura = None
        assinatura_valida_flag = False
        certificado_valido_flag = False

        if payload.cert_pem and payload.assinatura_b64:
            # Payload canônico: estrutura determinística para verificação
            dados_canonicos = {
                "cns_prescritor":        cns,
                "cpf_paciente":          cpf,
                "tipo_emissao":          payload.tipo_emissao,
                "itens": [
                    {
                        "nome_medicamento":   it.nome_medicamento,
                        "concentracao":       it.concentracao,
                        "quantidade":         it.quantidade,
                        "unidade_quantidade": it.unidade_quantidade,
                        "posologia":          it.posologia,
                    }
                    for it in payload.itens
                ],
            }
            resultado_assinatura = verificar_assinatura_icp(
                cert_pem=payload.cert_pem,
                assinatura_b64=payload.assinatura_b64,
                dados_payload=dados_canonicos,
            )

            if not resultado_assinatura.valida:
                # Falha criptográfica → rejeitar a emissão
                raise HTTPException(
                    status_code=422,
                    detail={
                        "erro": resultado_assinatura.erro,
                        "assinatura_valida": resultado_assinatura.assinatura_valida,
                        "certificado_valido": resultado_assinatura.certificado_valido,
                    },
                )
            assinatura_valida_flag = True
            certificado_valido_flag = True

        # Registrar resultado de verificação no ledger (auditável)
        if resultado_assinatura:
            ev_payload["verificacao_assinatura_icp"] = {
                "assinatura_valida":  resultado_assinatura.assinatura_valida,
                "certificado_valido": resultado_assinatura.certificado_valido,
                "digest_hex":         resultado_assinatura.digest_hex,
            }
        elif payload.cert_pem and not payload.assinatura_b64:
            # Binding ICP sem verificação de assinatura (ex: A3 sem plugin instalado)
            ev_payload["verificacao_assinatura_icp"] = {
                "assinatura_valida":  None,
                "certificado_valido": None,
                "modo": "binding_sem_assinatura",
            }
        else:
            # Fluxo físico
            ev_payload["validacao_prescritor"] = "NAO_REALIZADA"
            ev_payload["modo"] = "FISICO"

        # ------------------------------------------------------------------
        # Ticket 67 — String de Validação Auditável
        # Gerada no momento da emissão quando cert_pem é fornecido.
        # Condição adicional (T68): quando assinatura_b64 fornecida, só gerar
        # se a assinatura for válida (já verificado acima — exceção impede chegar aqui).
        # Não bloqueia emissão: ausência de cert_pem → string_validacao = NULL.
        # ------------------------------------------------------------------
        string_validacao_prescritor: str | None = None
        sv_payload: dict | None = None

        if payload.cert_pem:
            icp = parsear_certificado_icp(payload.cert_pem)
            if icp.parseable and not icp.precisa_conselho_manual():
                # Pipeline de identidade para obter CNS e status_nome
                identidade = resolver_identidade_prescritor(
                    conn=conn,
                    cpf_certificado=icp.cpf_certificado or "",
                    nome_certificado=icp.nome_certificado or "",
                    conselho_numero=icp.conselho_numero,
                    conselho_uf=icp.conselho_uf,
                )
                cns_resolvido = identidade.get("cns") or ""
                nome_val = identidade.get("nome_validacao") or {}
                status_nome_raw = nome_val.get("status") or "NAO_VALIDADO"

                try:
                    sv = gerar_string_validacao_identidade(
                        cpf=icp.cpf_certificado or "",
                        conselho_tipo=icp.conselho_tipo or "",
                        conselho_uf=icp.conselho_uf or "",
                        conselho_numero=icp.conselho_numero or "",
                        cns=cns_resolvido,
                        status_nome=status_nome_raw,
                        cert_pem=payload.cert_pem,
                    )
                    string_validacao_prescritor = sv["string_validacao"]
                    sv_payload = sv
                except ValueError:
                    pass  # campos insuficientes — string não gerada

        # Persistir string_validacao_prescritor na prescrição
        if string_validacao_prescritor:
            conn.execute(
                "UPDATE prescricoes SET string_validacao_prescritor = ? WHERE id = ?",
                (string_validacao_prescritor, prescricao_id),
            )

        # Incluir string_validacao no payload do evento inicial do ledger
        if sv_payload:
            ev_payload["string_validacao"] = {
                "string_validacao": sv_payload["string_validacao"],
                "hash_cert":        sv_payload["hash_cert"],
                "componentes":      sv_payload["componentes"],
            }

        # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao_id,
            tipo_evento="prescricao_emitida",
            instance_id=instance_id,
            payload=ev_payload,
            ator_tipo="prescritor",
            ator_id=cns,
        )
        registrar_outbox(conn, "prescricao_emitida", "prescricao", protocolo,
                         ev_payload, instance_id=instance_id)

        # ------------------------------------------------------------------
        # Camada 3 — trilha de auditoria da decisão clínica (append-only).
        # Registra qual sinal do semáforo cada item recebeu na EMISSÃO e sob
        # qual VERSÃO de regra (complemento persistente da ficha — camada 2).
        # Só registra quando o semáforo está ATIVO (algo foi apresentado ao
        # prescritor) e há CID (houve indicação a validar).
        # NÃO-BLOQUEANTE: a trilha NUNCA pode quebrar a emissão.
        # ------------------------------------------------------------------
        if PICSAUDE_DECISAO_CLINICA and payload.codigo_cid and itens_emitidos:
            try:
                registrar_evento_ledger(
                    conn,
                    objeto_tipo="prescricao",
                    objeto_id=prescricao_id,
                    tipo_evento=TIPO_EVENTO_DECISAO,
                    instance_id=instance_id,
                    payload=montar_trilha_decisao(payload.codigo_cid, itens_emitidos),
                    ator_tipo="prescritor",
                    ator_id=cns,
                )
            except Exception:   # pragma: no cover — defesa; trilha é secundária
                logger.exception(
                    "Falha ao registrar trilha de decisão clínica "
                    "(prescricao_id=%s) — emissão segue normalmente.",
                    prescricao_id,
                )

        # ------------------------------------------------------------------
        # Ticket 63 — Entrega à carteira digital
        # Se enviar_ao_paciente=True e paciente já existia (tem carteira),
        # cria custódia prescritor→paciente e avança status para
        # 'transferida_paciente' dentro da mesma transação de emissão.
        # ------------------------------------------------------------------
        entregue_carteira = False
        status_final = "pendente"

        if payload.enviar_ao_paciente and paciente_existia:
            # Abrir custódia do paciente
            conn.execute(
                """
                INSERT INTO prescricao_custodia
                  (prescricao_id, item_id, detentor_tipo, detentor_id,
                   transferida_em, encerrada_em, motivo, created_at)
                VALUES (?, NULL, 'paciente', ?, ?, NULL, 'entrega_carteira_digital', ?)
                """,
                (prescricao_id, cpf, agora, agora),
            )
            # Avançar status da prescrição
            conn.execute(
                "UPDATE prescricoes SET status = 'transferida_paciente', updated_at = ? WHERE id = ?",
                (agora, prescricao_id),
            )
            # Registrar evento de custódia no ledger (imutável)
            # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
            # Reutiliza o mesmo instance_id da transação (invariante §6.3).
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=prescricao_id,
                tipo_evento="custodia_transferida",
                instance_id=instance_id,
                payload={
                    "de": "prescritor", "de_id": cns,
                    "para": "paciente", "para_id": cpf,
                    "motivo": "entrega_carteira_digital",
                    "via": "emissao_direta",
                },
                ator_tipo="prescritor",
                ator_id=cns,
            )
            entregue_carteira = True
            status_final = "transferida_paciente"

        conn.commit()

        return {
            "id": prescricao_id,
            "protocolo": protocolo,
            "status": status_final,
            "tipo_emissao": payload.tipo_emissao,
            "origem_prescricao_id": payload.origem_prescricao_id,
            "assinatura_modo": payload.assinatura_modo,
            "nivel_formal": calcular_nivel_formal(payload.assinatura_modo, payload.tipo_emissao),
            "data_emissao": agora,
            "itens_count": len(payload.itens),
            "documento_hash": doc_result.hash_sha256,
            # Ticket 36 — contexto clínico (None quando não informado)
            "indicacao_clinica": payload.indicacao_clinica or None,
            "codigo_cid": payload.codigo_cid or None,
            # Ticket 47 — resultado da validação CNES do prescritor
            "cnes_validacao": cnes_validacao,
            # Ticket 50 — score composto de confiança do cuidado
            "score_confianca": score_confianca,
            # Ticket 63 — resultado da entrega à carteira digital
            # True  = custódia criada imediatamente (transferida_paciente)
            # False = prescrição em 'pendente'; frontend exibe link de acesso
            "entregue_carteira": entregue_carteira,
            # Ticket 67 — string de validação auditável (None quando cert_pem não fornecido)
            "string_validacao_prescritor": string_validacao_prescritor,
            # Ticket 68 — resultado da verificação criptográfica ICP
            "assinatura_valida":  assinatura_valida_flag or None,
            "certificado_valido": certificado_valido_flag or None,
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        # Captura erros de conectividade com o banco (PostgreSQL ou SQLite)
        # e retorna 503 estruturado para o cliente sem vazar traceback.
        msg = str(exc).lower()
        if any(kw in msg for kw in ("database is locked", "could not connect", "connection", "pool")):
            raise HTTPException(
                status_code=503,
                detail={
                    "erro": "banco_indisponivel",
                    "mensagem": "Serviço temporariamente indisponível. Tente novamente em instantes.",
                    "codigo": "DB_UNAVAILABLE",
                },
            )
        raise

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema de emissão física
# ---------------------------------------------------------------------------

class FisicaIn(BaseModel):
    cns_prescritor:  str
    nome_prescritor: Optional[str] = None
    cpf_paciente:    Optional[str] = None   # opcional: paciente pode não ter CPF no sistema
    nome_paciente:   str
    itens:           List[ItemIn] = []


# ---------------------------------------------------------------------------
# Endpoint de emissão exclusivamente física
# ---------------------------------------------------------------------------

@router.post("/fisica", status_code=201)
def criar_prescricao_fisica(payload: FisicaIn, usuario=Depends(require_role("prescritor"))):
    """
    Registra uma prescrição emitida exclusivamente em papel.

    Diferenças em relação à emissão digital:
    - Sem assinatura_modo
    - Status final: encerrada_localmente
    - Sem cadeia de custódia (nenhum registro em prescricao_custodia)
    - Sem transferência ao cidadão ou farmácia
    - Evento gravado no ledger: prescricao_impressa
    - cpf_paciente é opcional (sentinela '00000000000' se ausente)
    """
    if not payload.itens:
        raise HTTPException(status_code=422, detail="A prescrição deve conter ao menos um item.")

    cns      = normalize_cns(payload.cns_prescritor)
    # V2 (TICKET-5C §4.2) — CNS declarado deve coincidir com o JWT.
    if normalize_cns(usuario["sub"]) != cns:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "prescritor_mismatch",
                "mensagem": "CNS do payload não coincide com prescritor autenticado.",
            },
        )
    cpf      = normalize_cpf(payload.cpf_paciente) if payload.cpf_paciente else _CPF_NAO_IDENTIFICADO
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora    = datetime.utcnow().isoformat()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        instance_id = get_instance_id_conn(conn)

        # 1. Localizar ou criar prescritor
        prescritor = conn.execute(
            "SELECT id FROM prescritores WHERE cns = ?", (cns,)
        ).fetchone()
        if prescritor:
            prescritor_id = prescritor["id"]
        else:
            nome_pres = normalize_nome(payload.nome_prescritor or "")
            if not nome_pres:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Prescritor com CNS '{cns}' não encontrado. "
                        "Envie 'nome_prescritor' para registrá-lo automaticamente."
                    ),
                )
            cursor = conn.execute(
                "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
                (cns, nome_pres, agora, agora),
            )
            prescritor_id = cursor.lastrowid

        # 2. Localizar ou criar paciente (pode ser sentinela se CPF não informado)
        # Concorrência: INSERT OR IGNORE + SELECT é atômico para CPF duplicado concorrente.
        conn.execute(
            "INSERT OR IGNORE INTO pacientes (cpf, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
            (cpf, nome_pac, agora, agora),
        )
        paciente_id = conn.execute(
            "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
        ).fetchone()["id"]

        # 3. Inserir prescrição com status terminal encerrada_localmente
        #    tipo_emissao = 'fisica' — valor semântico distinto de 'nova'/'correcao'/'renovacao'.
        #    Permite que calcular_nivel_formal() e o endpoint /pdf retornem 'fisica' corretamente.
        cursor = conn.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, origem_prescricao_id,
               data_emissao, data_validade, created_at, updated_at)
            VALUES (?, ?, ?, 'encerrada_localmente', NULL, 'fisica', NULL, ?, NULL, ?, ?)
            """,
            (protocolo, prescritor_id, paciente_id, agora, agora, agora),
        )
        prescricao_id = cursor.lastrowid

        # 4. Inserir itens com status 'encerrado_fisico':
        #    significa "registrado para auditoria, fora do ciclo digital de dispensação".
        #    Diferente de 'cancelado' (revogação clínica) e de 'dispensado' (entrega confirmada).
        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   unidade_quantidade, forma_farmaceutica,
                   posologia, status_item, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'encerrado_fisico', ?, ?)
                """,
                (prescricao_id, item.nome_medicamento, item.concentracao,
                 item.quantidade, item.unidade_quantidade, item.forma_farmaceutica,
                 item.posologia, agora, agora),
            )

        # 5. Gravar dois eventos distintos no ledger:
        #
        #    prescricao_impressa    — ação: o prescritor imprimiu para assinar e carimbar.
        #                             Registra o ato físico de impressão.
        #    encerrada_localmente   — estado: a prescrição encerrou-se sem entrar no ciclo
        #                             digital. Separação explícita de evento de ação vs.
        #                             evento de transição de estado.
        # Ticket 4D.1: substituídos os 2 INSERTs por registrar_evento_ledger.
        # Os dois eventos (prescricao_impressa + encerrada_localmente) e os
        # 2 outboxes compartilham o mesmo instance_id da transação.
        ev_impressa = {
            "tipo_emissao":     "fisica",
            "itens_count":      len(payload.itens),
            "cpf_identificado": payload.cpf_paciente is not None,
        }
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao_id,
            tipo_evento="prescricao_impressa",
            instance_id=instance_id,
            payload=ev_impressa,
            ator_tipo="prescritor",
            ator_id=cns,
        )
        registrar_outbox(conn, "prescricao_impressa", "prescricao", protocolo,
                         ev_impressa, instance_id=instance_id)

        ev_encerrada = {
            "status_anterior": None,          # prescrição nasce já encerrada
            "status_novo":     "encerrada_localmente",
            "motivo":          "emissao_exclusivamente_fisica",
            "sem_custodia_digital": True,
        }
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao_id,
            tipo_evento="encerrada_localmente",
            instance_id=instance_id,
            payload=ev_encerrada,
            ator_tipo="prescritor",
            ator_id=cns,
        )
        registrar_outbox(conn, "encerrada_localmente", "prescricao", protocolo,
                         ev_encerrada, instance_id=instance_id)

        return {
            "protocolo": protocolo,
            "status": "encerrada_localmente",
            "tipo_emissao": "fisica",
            "nivel_formal": calcular_nivel_formal(None, "fisica"),
            "data_emissao": agora,
            "itens_count": len(payload.itens),
        }


# ---------------------------------------------------------------------------
# GET /{protocolo}/documento — inspecionar / verificar integridade
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/documento")
def get_documento(protocolo: str, usuario=Depends(require_role("prescritor", "admin"))):
    """
    Retorna o documento canônico de uma prescrição e verifica integridade.

    Campos retornados:
    - documento: dict com os campos canônicos
    - serializado: string JSON compacta que foi (ou será) assinada
    - hash_recomputado: SHA-256 do serializado recalculado agora
    - hash_armazenado: valor salvo em prescricoes.assinatura_hash no momento da emissão
    - integro: true se os dois hashes coincidem
    """
    with get_tx() as conn:
        # Verificação rápida antes de montar o documento canônico:
        # prescrições físicas não possuem hash nem documento assinável.
        meta = conn.execute(
            "SELECT tipo_emissao FROM prescricoes WHERE protocolo = ?",
            (protocolo,),
        ).fetchone()

        if meta is None:
            raise HTTPException(status_code=404, detail=f"Prescrição '{protocolo}' não encontrada.")

        # V3 (TICKET-5C §4.3) — owner check; admin sempre passa.
        if usuario["role"] != "admin":
            owner = conn.execute(
                """
                SELECT 1
                  FROM prescricoes p
                  JOIN prescritores pr ON pr.id = p.prescritor_id
                 WHERE p.protocolo = ? AND pr.cns = ?
                """,
                (protocolo, normalize_cns(usuario["sub"])),
            ).fetchone()
            if not owner:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "codigo": "nao_e_dono_da_prescricao",
                        "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                    },
                )

        if meta["tipo_emissao"] == "fisica":
            raise HTTPException(
                status_code=400,
                detail={
                    "erro": "documento_nao_aplicavel",
                    "mensagem": (
                        "Prescrições físicas (tipo_emissao='fisica') não possuem "
                        "documento canônico nem hash de integridade. "
                        "Elas são registradas no ledger com os eventos "
                        "'prescricao_impressa' e 'encerrada_localmente', "
                        "mas ficam fora do ciclo de assinatura digital."
                    ),
                    "nivel_formal": "fisica",
                    "protocolo": protocolo,
                },
            )

        resultado = montar_documento_de_conn(conn, protocolo)
        if resultado is None:
            raise HTTPException(status_code=404, detail=f"Prescrição '{protocolo}' não encontrada.")

        doc_result, hash_armazenado = resultado

        return {
            "protocolo": protocolo,
            "documento": doc_result.documento,
            "serializado": doc_result.serializado,
            "hash_recomputado": doc_result.hash_sha256,
            "hash_armazenado": hash_armazenado,
            "integro": doc_result.hash_sha256 == hash_armazenado,
        }


# ---------------------------------------------------------------------------
# GET /{protocolo}/pdf — receita médica em PDF institucional
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/pdf")
def get_pdf_prescricao(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """
    Gera e retorna o PDF da receita médica no formato institucional PicSaúde.

    Inclui:
    - Identificação do prescritor (nome, CNS, modo de assinatura)
    - Dados do paciente (nome, CPF mascarado)
    - Medicamentos prescritos com posologia
    - Protocolo UUID e hash SHA-256 do documento canônico
    - Badge indicando o tipo: Digital ICP-Brasil / gov.br / Operacional / Física
    - Área de assinatura

    Roles autorizados: prescritor, dispensador, admin.
    """
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT
                p.protocolo,
                p.status,
                p.tipo_emissao,
                p.assinatura_modo,
                p.assinatura_hash,
                p.data_emissao,
                pr.cns  AS cns_prescritor,
                pr.nome AS nome_prescritor,
                pa.cpf  AS cpf_paciente,
                pa.nome AS nome_paciente
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Prescrição '{protocolo}' não encontrada.")

        # V4 (TICKET-5C §4.4) — owner check apenas para role 'prescritor'.
        # Dispensador e admin passam direto (fluxo de balcão / fiscalização).
        if usuario["role"] == "prescritor":
            if normalize_cns(usuario["sub"]) != row["cns_prescritor"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "codigo": "nao_e_dono_da_prescricao",
                        "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                    },
                )

        itens_rows = conn.execute(
            """
            SELECT nome_medicamento, concentracao, quantidade, posologia
              FROM prescricao_itens
             WHERE prescricao_id = (SELECT id FROM prescricoes WHERE protocolo = ?)
             ORDER BY id
            """,
            (protocolo,),
        ).fetchall()
        itens = [dict(r) for r in itens_rows]

    # Calcular nivel_formal (não armazenado no banco)
    from app.domain.assinatura import calcular_nivel_formal as _calc
    nivel = _calc(row["assinatura_modo"], row["tipo_emissao"])

    # TICKET-6: marca d'água "DEMO" runtime via PICSAUDE_DEMO_MODE.
    from app.config import PICSAUDE_DEMO_MODE as _DEMO

    pdf_bytes = gerar_pdf_prescricao(
        protocolo       = row["protocolo"],
        status          = row["status"],
        tipo_emissao    = row["tipo_emissao"],
        assinatura_modo = row["assinatura_modo"],
        assinatura_hash = row["assinatura_hash"],
        nivel_formal    = nivel,
        data_emissao    = row["data_emissao"],
        nome_prescritor = row["nome_prescritor"],
        cns_prescritor  = row["cns_prescritor"],
        nome_paciente   = row["nome_paciente"],
        cpf_paciente    = row["cpf_paciente"],
        itens           = itens,
        is_demo         = _DEMO,
    )

    filename = f"receita_{protocolo[:8]}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Circulação atomizada (Ticket 44)
# ---------------------------------------------------------------------------

# Alfabeto Crockford — sem I, L, O, U (evita confusão visual 0/O, 1/I, 5/S…)
_CROCKFORD_A = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_VALIDADE_ATOM_PADRAO = 60    # minutos
_VALIDADE_ATOM_MAX    = 120   # minutos

_ESTADOS_TERMINAIS_PRESCRICAO_A = {
    "dispensada", "cancelada", "expirada", "encerrada_localmente",
}


def _gerar_codigo_atomizacao(conn) -> str:
    """Gera código Crockford único de 8 chars para token atomizado."""
    for _ in range(8):
        codigo = "".join(secrets.choice(_CROCKFORD_A) for _ in range(8))
        existe = conn.execute(
            "SELECT 1 FROM tokens_apresentacao WHERE codigo_curto = ?", (codigo,)
        ).fetchone()
        if not existe:
            return codigo
    raise RuntimeError("Falha ao gerar código único para token atomizado.")


def _expira_atomizacao(minutos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutos)).isoformat()


class AtomizarIn(BaseModel):
    validade_minutos: int = _VALIDADE_ATOM_PADRAO

    @field_validator("validade_minutos")
    @classmethod
    def validade_no_limite(cls, v: int) -> int:
        if not (1 <= v <= _VALIDADE_ATOM_MAX):
            raise ValueError(
                f"validade_minutos deve estar entre 1 e {_VALIDADE_ATOM_MAX}."
            )
        return v


@router.post(
    "/{protocolo}/tokens/atomizar",
    status_code=201,
    summary="Paciente atomiza circulação — gera um token por item ativo",
)
def atomizar_circulacao(
    protocolo: str,
    payload: AtomizarIn,
    usuario=Depends(require_role("paciente")),
):
    """
    Gera um token de circulação independente para cada item ativo da prescrição.

    **Pré-requisitos:**
    - Prescrição pertence ao paciente autenticado (CPF do JWT).
    - Prescrição não está em estado terminal.
    - Nenhum item possui classe de controle especial (A1–D2).
    - Há ao menos um item em estado circulável (pendente / devolvido_paciente).

    **Invariante arquitetural:**
      Um item inelegível bloqueia a atomização da prescrição inteira.
      Não existe atomização seletiva ou parcial.

    **Retorno:** lista de tokens, um por item circulável.
    O paciente pode apresentar cada token em farmácias distintas.
    O farmacêutico que resolve o token verá APENAS o item correspondente
    — os demais itens da prescrição não são expostos (privacidade mínima).

    **Ledger:** emite `circulacao_atomizada_ativada` + N eventos `token_item_emitido`.
    """
    cpf_paciente = usuario["sub"]
    proto = protocolo.strip()
    agora = datetime.now(timezone.utc).isoformat()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        # Reutilizado pelo evento principal e pelos N tokens (invariante §6.3).
        instance_id = get_instance_id_conn(conn)

        # 1. Carregar prescrição e verificar titularidade
        prescricao = conn.execute(
            """
            SELECT p.id, p.status
            FROM prescricoes p
            JOIN pacientes pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ?
              AND pa.cpf = ?
            """,
            (proto, cpf_paciente),
        ).fetchone()

        if not prescricao:
            raise HTTPException(
                status_code=404,
                detail="Prescrição não encontrada ou não pertence ao paciente autenticado.",
            )

        if prescricao["status"] in _ESTADOS_TERMINAIS_PRESCRICAO_A:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Prescrição com status '{prescricao['status']}' "
                    "não aceita circulação atomizada."
                ),
            )

        prescricao_id = prescricao["id"]

        # 2. Carregar todos os itens para verificar elegibilidade regulatória
        todos_itens = conn.execute(
            """
            SELECT id, nome_medicamento, concentracao, quantidade,
                   unidade_quantidade, forma_farmaceutica, posologia,
                   status_item, classe_controle
            FROM prescricao_itens
            WHERE prescricao_id = ?
            """,
            (prescricao_id,),
        ).fetchall()

        if not todos_itens:
            raise HTTPException(status_code=422, detail="Prescrição sem itens.")

        # 3. Verificar elegibilidade regulatória (todos os itens ou nenhum)
        elegivel, motivo = prescricao_atomizavel([dict(i) for i in todos_itens])
        if not elegivel:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Prescrição inelegível para circulação atomizada: {motivo} "
                    "Emita uma prescrição separada para o medicamento de controle especial."
                ),
            )

        # 4. Filtrar itens circuláveis (excluir terminais e em custódia ativa)
        itens_circulaveis = [
            i for i in todos_itens
            if i["status_item"] in ESTADOS_ITEM_CIRCULAVEIS
        ]

        if not itens_circulaveis:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Nenhum item em estado circulável (pendente / devolvido_paciente). "
                    "Itens já dispensados, cancelados ou em custódia ativa não recebem novo token."
                ),
            )

        expira_em = _expira_atomizacao(payload.validade_minutos)
        tokens_gerados = []

        # 5. Gerar um token por item circulável
        for item in itens_circulaveis:
            codigo = _gerar_codigo_atomizacao(conn)
            conn.execute(
                """
                INSERT INTO tokens_apresentacao
                    (codigo_curto, protocolo, paciente_cpf, escopo,
                     status, expira_em, criado_em, item_id)
                VALUES (?, ?, ?, 'apresentacao_item', 'ativo', ?, ?, ?)
                """,
                (codigo, proto, cpf_paciente, expira_em, agora, item["id"]),
            )
            tokens_gerados.append({
                "item_id":         item["id"],
                "nome_medicamento": item["nome_medicamento"],
                "concentracao":    item["concentracao"],
                "quantidade":      item["quantidade"],
                "unidade_quantidade": item["unidade_quantidade"],
                "status_item":     item["status_item"],
                "codigo_curto":    codigo,
                "expira_em":       expira_em,
            })

        # 6. Registrar eventos no ledger
        # Ticket 4D.1: substituídos pelo helper. Todos os 1+N eventos
        # compartilham o mesmo instance_id (invariante §6.3).
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao_id,
            tipo_evento="circulacao_atomizada_ativada",
            instance_id=instance_id,
            payload={
                "total_tokens":     len(tokens_gerados),
                "validade_minutos": payload.validade_minutos,
            },
            ator_tipo="paciente",
            ator_id=cpf_paciente,
        )

        for t in tokens_gerados:
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=prescricao_id,
                tipo_evento="token_item_emitido",
                instance_id=instance_id,
                payload={
                    "item_id":          t["item_id"],
                    "nome_medicamento": t["nome_medicamento"],
                    "codigo_curto":     t["codigo_curto"],
                    "expira_em":        t["expira_em"],
                },
                ator_tipo="paciente",
                ator_id=cpf_paciente,
            )

        return {
            "protocolo":          proto,
            "circulacao_atomizada": True,
            "total_tokens":       len(tokens_gerados),
            "expira_em":          expira_em,
            "tokens":             tokens_gerados,
            "aviso": (
                "Cada token é independente. Apresente cada um em uma farmácia diferente "
                "se desejar. O farmacêutico verá apenas o medicamento correspondente ao "
                "token apresentado."
            ),
        }
