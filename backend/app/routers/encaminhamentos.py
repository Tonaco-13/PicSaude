"""
routers/encaminhamentos.py
==========================
Objeto sanitário Encaminhamento — referência clínica (E1).
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator, model_validator, model_validator

from app.auth.dependencies import require_role
from app.config import BASE_URL
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.pdf_encaminhamento import gerar_pdf_encaminhamento
from app.domain.states_encaminhamento import (
    eh_terminal_encaminhamento,
    eh_terminal_item_encaminhamento,
    transicao_valida_encaminhamento,
)
from app.instance import get_instance_id_conn
from app.utils.helpers import (
    normalize_cns,
    normalize_cpf,
    normalize_nome,
    _assert_or_403,
    _normalizar_identidade_jwt,
)


router = APIRouter(prefix="/encaminhamentos", tags=["encaminhamentos"])

_CPF_NAO_IDENTIFICADO = "00000000000"
_TIPOS_EMISSAO_DIGITAL = {"novo", "correcao"}
_VALIDADE_PADRAO_DIAS = 90


# ENG-016 §5 — FINALIDADE ESTRUTURADA (martelo 2 do Fabiano, 23/08).
#
# "Para que estou mandando este paciente" é dado OPERACIONAL: é por ele que a
# regulação futura filtra fila. Enterrado na prosa da justificativa, vira coisa
# que só um humano lê.
#
# A lista vive AQUI e não como CHECK no banco: o vocabulário ainda vai crescer,
# e mudar CHECK é migração enquanto mudar esta tupla é uma linha. `outra` é o
# escape honesto — exige texto, porque "outra" sem dizer qual não informa nada.
FINALIDADES_ENCAMINHAMENTO: tuple[str, ...] = (
    "avaliacao",
    "conduta",
    "exame_complementar",
    "segunda_opiniao",
    "seguimento",
    "outra",
)


class ItemEncaminhamentoIn(BaseModel):
    especialidade: str
    procedimento: Optional[str] = None
    motivo: Optional[str] = None

    @field_validator("especialidade")
    @classmethod
    def especialidade_nao_vazia(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("especialidade não pode ser vazia")
        return v.strip()


class EncaminhamentoIn(BaseModel):
    cns_prescritor: str
    nome_prescritor: Optional[str] = None
    cpf_paciente: str
    nome_paciente: str
    cns_destino: str
    especialidade_destino: str
    cid: Optional[str] = None
    justificativa_clinica: str
    # Opcional no SCHEMA, sempre enviado pela TELA. Encaminhamento emitido antes
    # desta coluna não tem finalidade e não pode ganhá-la (§1: objeto emitido é
    # imutável); `None` significa "emitido antes de a finalidade existir", que é
    # a verdade — e não um valor plausível inventado por backfill.
    finalidade: Optional[str] = None
    finalidade_texto: Optional[str] = None
    # ENG-016 §5 — AUDITORIA DA SUGESTÃO (martelo 3 do Fabiano, 23/08).
    #
    # Os CNS que a tela APRESENTOU como sugestão, na ordem em que apareceram.
    # Se o sistema influencia a escolha do destino, a influência é auditável —
    # é a mitigação declarada do efeito primeiro-da-lista e da captura de
    # demanda. Sem isto, "a rede se conhece" seria uma caixa-preta que ninguém
    # consegue questionar depois.
    #
    # A tela manda o que MOSTROU, não o que o backend calcularia agora: a
    # ordenação pode mudar entre a consulta e a emissão, e o que importa para a
    # auditoria é o que esteve diante dos olhos de quem decidiu.
    sugestoes_apresentadas: Optional[List[str]] = None
    data_validade: Optional[str] = None
    tipo_emissao: str = "novo"
    origem_encaminhamento_id: Optional[int] = None
    itens: List[ItemEncaminhamentoIn] = []

    @field_validator("tipo_emissao")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_EMISSAO_DIGITAL:
            raise ValueError(
                f"tipo_emissao inválido: '{v}'. Valores aceitos: {sorted(_TIPOS_EMISSAO_DIGITAL)}"
            )
        return v

    @field_validator("finalidade")
    @classmethod
    def finalidade_conhecida(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v not in FINALIDADES_ENCAMINHAMENTO:
            raise ValueError(
                f"finalidade inválida: '{v}'. Valores aceitos: "
                f"{sorted(FINALIDADES_ENCAMINHAMENTO)}"
            )
        return v

    @model_validator(mode="after")
    def outra_exige_texto(self):
        # "outra" sem dizer qual não informa nada — seria o campo estruturado
        # devolvendo o problema que ele existe para resolver.
        if self.finalidade == "outra" and not (self.finalidade_texto or "").strip():
            raise ValueError("finalidade 'outra' exige `finalidade_texto`.")
        return self

    @field_validator("especialidade_destino", "justificativa_clinica")
    @classmethod
    def texto_obrigatorio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("campo obrigatório não pode ser vazio")
        return v.strip()

    @model_validator(mode="after")
    def origem_obrigatoria_para_correcao(self) -> "EncaminhamentoIn":
        if self.tipo_emissao != "novo" and self.origem_encaminhamento_id is None:
            raise ValueError("origem_encaminhamento_id é obrigatório para correção.")
        return self


class EncaminhamentoFisicoIn(BaseModel):
    cns_prescritor: str
    nome_prescritor: Optional[str] = None
    cpf_paciente: Optional[str] = None
    nome_paciente: str
    cns_destino: str
    especialidade_destino: str
    cid: Optional[str] = None
    justificativa_clinica: str
    itens: List[ItemEncaminhamentoIn] = []

    @field_validator("especialidade_destino", "justificativa_clinica", "nome_paciente")
    @classmethod
    def texto_obrigatorio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("campo obrigatório não pode ser vazio")
        return v.strip()


class AgendarEncaminhamentoIn(BaseModel):
    data_agendamento: Optional[str] = None
    local_texto: Optional[str] = None


class MotivoIn(BaseModel):
    motivo: Optional[str] = None


# ── DOCUMENTO CANÔNICO DO ENCAMINHAMENTO — versionado ─────────────────────
#
# A versão ATUAL. Emissão nova sempre usa esta; verificação usa a que estiver
# GRAVADA no documento.
VERSAO_DOC_ENCAMINHAMENTO = "2"

# As versões que este código sabe reproduzir, congeladas por valor. Não é
# decoração: é a lista que um verificador consulta antes de dizer "não confere".
# Documento com versão fora daqui não é documento adulterado — é documento que
# ESTE código não sabe verificar, e a diferença importa.
VERSOES_DOC_ENCAMINHAMENTO: tuple[str, ...] = ("1", "2")


def _documento_canonico_encaminhamento(
    versao: str,
    *,
    protocolo: str,
    cns_origem: str,
    cns_destino: str,
    cpf_paciente: str,
    especialidade_destino: str,
    cid: Optional[str],
    justificativa_clinica: str,
    itens: list[ItemEncaminhamentoIn],
    finalidade: Optional[str] = None,
    finalidade_texto: Optional[str] = None,
) -> dict:
    """O documento, montado sob a regra da VERSÃO pedida.

    ⚠️ ENG-016 §5 — a v2 acrescenta a FINALIDADE. Não é capricho de
    versionamento: o §5 manda a confirmação mostrar o documento montado e o hash
    congelar o que se vê. Finalidade visível no cabeçalho que o médico confirma
    e ausente do hash faria o hash deixar de congelar o que foi visto — que é a
    única coisa que ele faz. Hash que não congela o que foi visto é hash que
    mente.

    A REGRA v1 CONTINUA AQUI, INTACTA, e é isso que torna a compatibilidade
    versionada uma afirmação verificável em vez de uma promessa. Documento
    emitido antes é v1 e verifica sob a v1: objeto sanitário emitido é imutável
    (§1), e recalcular o passado com a regra de hoje é o R1 invertido.

    Quem um dia escrever o verificador chama esta função com a versão GRAVADA no
    documento — nunca com a versão atual. Ler a versão do código em vez do
    documento é o defeito que este desenho existe para impedir.
    """
    if versao not in VERSOES_DOC_ENCAMINHAMENTO:
        raise ValueError(
            f"versão de documento desconhecida: '{versao}'. "
            f"Conhecidas: {list(VERSOES_DOC_ENCAMINHAMENTO)}"
        )

    doc = {
        "protocolo": protocolo,
        "cns_origem": cns_origem,
        "cns_destino": cns_destino,
        "paciente_cpf": cpf_paciente,
        "especialidade_destino": especialidade_destino,
        "cid": cid,
        "justificativa_clinica": justificativa_clinica,
        "itens": [
            {
                "especialidade": item.especialidade,
                "procedimento": item.procedimento,
                "motivo": item.motivo,
            }
            for item in itens
        ],
        "versao_esquema": versao,
    }
    if versao == "2":
        doc["finalidade"] = finalidade
        doc["finalidade_texto"] = finalidade_texto
    return doc


def _calcular_hash(
    *,
    protocolo: str,
    cns_origem: str,
    cns_destino: str,
    cpf_paciente: str,
    especialidade_destino: str,
    cid: Optional[str],
    justificativa_clinica: str,
    itens: list[ItemEncaminhamentoIn],
    finalidade: Optional[str] = None,
    finalidade_texto: Optional[str] = None,
    versao: str = VERSAO_DOC_ENCAMINHAMENTO,
) -> str:
    """SHA-256 do documento canônico, sob a regra da versão pedida.

    O default é a versão ATUAL porque quem chama daqui é a EMISSÃO. Verificação
    passa a versão explicitamente — e não existe hoje nenhum caminho de
    verificação (há guarda estática afirmando isso em
    `tests/unit/test_documento_canonico_encaminhamento.py`).
    """
    doc = _documento_canonico_encaminhamento(
        versao,
        protocolo=protocolo,
        cns_origem=cns_origem,
        cns_destino=cns_destino,
        cpf_paciente=cpf_paciente,
        especialidade_destino=especialidade_destino,
        cid=cid,
        justificativa_clinica=justificativa_clinica,
        itens=itens,
        finalidade=finalidade,
        finalidade_texto=finalidade_texto,
    )
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _localizar_ou_criar_prescritor(conn, cns: str, nome_hint: Optional[str], agora: str) -> int:
    row = conn.execute("SELECT id FROM prescritores WHERE cns = ?", (cns,)).fetchone()
    if row:
        return row["id"]
    nome = normalize_nome(nome_hint or "")
    if not nome:
        raise HTTPException(
            status_code=422,
            detail=f"Prescritor com CNS '{cns}' não encontrado. Envie 'nome_prescritor'.",
        )
    cursor = conn.execute(
        "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
        (cns, nome, agora, agora),
    )
    return cursor.lastrowid


def _localizar_ou_criar_paciente(conn, cpf: str, nome: str, agora: str) -> int:
    row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
        (cpf, nome, agora, agora),
    )
    return cursor.lastrowid


def _get_encaminhamento_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM encaminhamentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Encaminhamento '{protocolo}' não encontrado.")
    return dict(row)


def _cns_origem(conn, enc: dict) -> str | None:
    row = conn.execute(
        "SELECT cns FROM prescritores WHERE id = ?", (enc["prescritor_id"],)
    ).fetchone()
    return row["cns"] if row else None


def _cpf_paciente(conn, enc: dict) -> str | None:
    row = conn.execute(
        "SELECT cpf FROM pacientes WHERE id = ?", (enc["paciente_id"],)
    ).fetchone()
    return row["cpf"] if row else None


def _assert_origem(conn, enc: dict, ident_cns: str) -> None:
    _assert_or_403(
        _cns_origem(conn, enc) == ident_cns,
        codigo="nao_e_dono_do_encaminhamento",
        mensagem="Este encaminhamento foi emitido por outro prescritor.",
    )


def _assert_destino(enc: dict, ident_cns: str) -> None:
    _assert_or_403(
        enc["cns_destino"] == ident_cns,
        codigo="nao_e_dono_do_encaminhamento",
        mensagem="Este encaminhamento é destinado a outro prescritor.",
    )


def _assert_paciente(conn, enc: dict, ident_cpf: str) -> None:
    cpf = _cpf_paciente(conn, enc)
    _assert_or_403(
        cpf is not None and cpf != _CPF_NAO_IDENTIFICADO and cpf == ident_cpf,
        codigo="nao_e_dono_do_encaminhamento",
        mensagem="Este encaminhamento pertence a outro paciente.",
    )


def _assert_leitura(conn, enc: dict, papel: str, ident: str) -> None:
    if papel == "prescritor":
        donos = {_cns_origem(conn, enc), enc["cns_destino"]} - {None}
        _assert_or_403(
            ident in donos,
            codigo="nao_e_dono_do_encaminhamento",
            mensagem="Este encaminhamento pertence a outro prescritor ou paciente.",
        )
        return
    if papel == "paciente":
        _assert_paciente(conn, enc, ident)
        return
    _assert_or_403(
        False,
        codigo="papel_sem_acesso_ao_encaminhamento",
        mensagem="Este perfil não pode acessar o encaminhamento.",
    )


def _assert_origem_ou_destino(conn, enc: dict, ident_cns: str) -> None:
    donos = {_cns_origem(conn, enc), enc["cns_destino"]} - {None}
    _assert_or_403(
        ident_cns in donos,
        codigo="nao_e_dono_do_encaminhamento",
        mensagem="Este encaminhamento pertence a outro prescritor.",
    )


def _get_itens(conn, encaminhamento_id: int) -> list[dict]:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM encaminhamento_itens WHERE encaminhamento_id = ? ORDER BY id",
            (encaminhamento_id,),
        ).fetchall()
    ]


def _fechar_custodia_ativa(conn, encaminhamento_id: int, agora: str) -> None:
    conn.execute(
        """
        UPDATE encaminhamento_custodia
           SET encerrada_em = ?
         WHERE encaminhamento_id = ? AND item_id IS NULL AND encerrada_em IS NULL
        """,
        (agora, encaminhamento_id),
    )


def _custodia_ativa(conn, encaminhamento_id: int) -> Optional[dict]:
    """A posse ATUAL — `None` quando não há (ex.: emissão física).

    Fonte única de "onde está o encaminhamento": `encerrada_em IS NULL`, nunca
    "a última linha" e nunca o status (§1a). O índice único do #185 garante que
    esta consulta devolve no máximo uma.
    """
    row = conn.execute(
        """
        SELECT * FROM encaminhamento_custodia
         WHERE encaminhamento_id = ? AND item_id IS NULL AND encerrada_em IS NULL
         ORDER BY id DESC LIMIT 1
        """,
        (encaminhamento_id,),
    ).fetchone()
    return dict(row) if row else None


def _abrir_custodia(conn, encaminhamento_id: int, detentor_tipo: str,
                    detentor_id: str, motivo: str, agora: str) -> None:
    conn.execute(
        """
        INSERT INTO encaminhamento_custodia
          (encaminhamento_id, item_id, detentor_tipo, detentor_id,
           transferida_em, encerrada_em, motivo, created_at)
        VALUES (?, NULL, ?, ?, ?, NULL, ?, ?)
        """,
        (encaminhamento_id, detentor_tipo, detentor_id, agora, motivo, agora),
    )


def _evento(conn, enc_id: int, tipo: str, payload: dict, papel: str, ident: str,
            *, instance_id: str) -> None:
    registrar_evento_ledger(
        conn,
        objeto_tipo="encaminhamento",
        objeto_id=enc_id,
        tipo_evento=tipo,
        instance_id=instance_id,
        payload=payload,
        ator_tipo=papel,
        ator_id=ident,
    )


def _validar_transicao(enc: dict, novo_status: str) -> None:
    if not transicao_valida_encaminhamento(enc["status"], novo_status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Transição inválida: '{enc['status']}' → '{novo_status}'."
            ),
        )


@router.post("", status_code=201)
def criar_encaminhamento(
    payload: EncaminhamentoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    if not payload.itens:
        raise HTTPException(status_code=422, detail="O encaminhamento deve conter ao menos um item.")

    cns_origem = normalize_cns(payload.cns_prescritor)
    cns_destino = normalize_cns(payload.cns_destino)
    if papel != "admin":
        _assert_or_403(
            ident == cns_origem,
            codigo="prescritor_mismatch",
            mensagem="CNS do payload não coincide com prescritor autenticado.",
        )

    cpf = normalize_cpf(payload.cpf_paciente)
    nome_paciente = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()
    data_validade = payload.data_validade or (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns_origem, payload.nome_prescritor, agora)
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_paciente, agora)

        if payload.origem_encaminhamento_id is not None:
            origem = conn.execute(
                "SELECT pr.cns FROM encaminhamentos e "
                "JOIN prescritores pr ON pr.id = e.prescritor_id "
                "WHERE e.id = ?",
                (payload.origem_encaminhamento_id,),
            ).fetchone()
            if not origem:
                raise HTTPException(
                    status_code=404,
                    detail=f"Encaminhamento de origem id={payload.origem_encaminhamento_id} não encontrado.",
                )
            _assert_or_403(
                origem["cns"] == cns_origem,
                codigo="nao_e_dono_do_encaminhamento",
                mensagem="O encaminhamento de origem foi emitido por outro prescritor.",
            )

        cursor = conn.execute(
            """
            INSERT INTO encaminhamentos
              (protocolo, prescritor_id, paciente_id, cns_destino,
               especialidade_destino, finalidade, finalidade_texto,
               cid, justificativa_clinica, status,
               tipo_emissao, origem_encaminhamento_id, data_emissao,
               data_validade, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'emitido', ?, ?, ?, ?, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id, cns_destino,
                payload.especialidade_destino, payload.finalidade, payload.finalidade_texto,
                payload.cid, payload.justificativa_clinica,
                payload.tipo_emissao, payload.origem_encaminhamento_id,
                data_emissao, data_validade, agora,
            ),
        )
        enc_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO encaminhamento_itens
                  (encaminhamento_id, especialidade, procedimento, motivo, status_item, criado_em)
                VALUES (?, ?, ?, ?, 'pendente', ?)
                """,
                (enc_id, item.especialidade, item.procedimento, item.motivo, agora),
            )

        doc_hash = _calcular_hash(
            protocolo=protocolo,
            cns_origem=cns_origem,
            cns_destino=cns_destino,
            cpf_paciente=cpf,
            especialidade_destino=payload.especialidade_destino,
            cid=payload.cid,
            justificativa_clinica=payload.justificativa_clinica,
            itens=payload.itens,
            finalidade=payload.finalidade,
            finalidade_texto=payload.finalidade_texto,
        )
        conn.execute("UPDATE encaminhamentos SET assinatura_hash = ? WHERE id = ?", (doc_hash, enc_id))

        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc_id, "encaminhamento_emitido", {
            "tipo_emissao": payload.tipo_emissao,
            "origem_encaminhamento_id": payload.origem_encaminhamento_id,
            "cns_destino": cns_destino,
            "finalidade": payload.finalidade,
            "itens_count": len(payload.itens),
            # §5 — a influência do sistema fica no ledger, ao lado da escolha.
            # `escolheu_sugerido` é derivado aqui e não na tela: quem responde
            # "a sugestão pegou?" é o registro, não o cliente que a exibiu.
            "sugestoes_apresentadas": payload.sugestoes_apresentadas,
            "escolheu_sugerido": (
                cns_destino in (payload.sugestoes_apresentadas or [])
                if payload.sugestoes_apresentadas else None
            ),
        }, papel, ident or cns_origem, instance_id=instance_id)

        _abrir_custodia(conn, enc_id, "paciente", cpf, "emissao_digital", agora)
        _evento(conn, enc_id, "custodia_transferida", {
            "de": "prescritor",
            "de_id": cns_origem,
            "para": "paciente",
            "para_id": cpf,
            "via": "emissao_digital",
        }, papel, ident or cns_origem, instance_id=instance_id)

        return {
            "id": enc_id,
            "protocolo": protocolo,
            "status": "emitido",
            "tipo_emissao": payload.tipo_emissao,
            "data_emissao": data_emissao,
            "data_validade": data_validade,
            "itens_count": len(payload.itens),
            "documento_hash": doc_hash,
        }


@router.get("/meus", status_code=200)
def meus_encaminhamentos(
    usuario=Depends(require_role("prescritor", "admin")),
):
    """Os encaminhamentos do prescritor, separados por CHAPÉU.

    ENG-016 §3 — o mesmo profissional é ORIGEM de uns e DESTINO de outros, e as
    perguntas são diferentes: "o que eu mandei, e voltou?" contra "o que chegou
    para mim, e o que eu devo?". Uma lista só obrigaria o operador a separar na
    cabeça o que o sistema já sabe separar.

    LISTA POR DEVER, SELO POR POSSE — a lei nº 1 do §2, e a razão de haver dois
    campos por linha:

      · `dever` responde "o que ESTE profissional tem de fazer agora";
      · `posse` responde "onde o documento ESTÁ fisicamente".

    Os dois divergem de propósito no caso que dá nome à regra: `atendido` é
    DEVER do destino (ele precisa contrarreferir) com a POSSE no cidadão — o
    `atender` devolveu o documento. Listar por custódia faria o item sumir da
    tela exatamente quando vira obrigação.

    Sem paginação: a demanda desta onda é a vitrine, e inventar paginação sem
    volume real seria complexidade adivinhada. Quando o volume aparecer, entra —
    com o número que o caso pedir.
    """
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        linhas = conn.execute(
            """
            SELECT e.*, pr.cns AS cns_origem, pa.cpf AS cpf_paciente,
                   pa.nome AS nome_paciente
              FROM encaminhamentos e
              LEFT JOIN prescritores pr ON pr.id = e.prescritor_id
              LEFT JOIN pacientes    pa ON pa.id = e.paciente_id
             ORDER BY e.id DESC
            """
        ).fetchall()

        origem, destino = [], []
        for row in linhas:
            enc = dict(row)
            eh_origem  = enc.get("cns_origem") == ident
            eh_destino = enc.get("cns_destino") == ident
            if not (eh_origem or eh_destino or papel == "admin"):
                continue

            atual = _custodia_ativa(conn, enc["id"])
            item = {
                "protocolo":             enc["protocolo"],
                "status":                enc["status"],
                "especialidade_destino": enc["especialidade_destino"],
                "finalidade":            enc.get("finalidade"),
                "finalidade_texto":      enc.get("finalidade_texto"),
                "cid":                   enc.get("cid"),
                "cns_destino":           enc["cns_destino"],
                "cns_origem":            enc.get("cns_origem"),
                "cpf_paciente":          enc.get("cpf_paciente"),
                "nome_paciente":         enc.get("nome_paciente"),
                "data_emissao":          enc["data_emissao"],
                # POSSE — fonte única: custódia ativa, nunca o status (§1a).
                "posse_tipo":            atual["detentor_tipo"] if atual else None,
                "posse_id":              atual["detentor_id"] if atual else None,
            }
            if eh_origem:
                origem.append(item)
            if eh_destino:
                destino.append({**item, "dever": _dever_do_destino(enc["status"])})

    return {"encaminhados": origem, "recebidos": destino}


def _dever_do_destino(status: str) -> str:
    """O que o DESTINO deve fazer agora — as três gavetas do §3.

    `chegou` (decidir: agendar ou recusar) · `devo_retorno` (atendeu e deve a
    contrarreferência — o caso em que dever e posse divergem) · `devolvi`
    (contrarreferiu; acompanha até a origem encerrar) · `sem_dever` (terminal).
    """
    if status in ("emitido", "em_regulacao", "agendado"):
        return "chegou"
    if status == "atendido":
        return "devo_retorno"
    if status == "contrarreferido":
        return "devolvi"
    return "sem_dever"


@router.get("/sugestoes-destino", status_code=200)
def sugestoes_destino(
    cpf_paciente: str,
    especialidade: Optional[str] = None,
    limite: int = 5,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """Quem já atendeu este paciente — a rede se conhece porque os objetos circularam.

    ENG-016 §5 (martelo 3 do Fabiano). O dado já existe: cada encaminhamento
    ATENDIDO é a prova de que aquele profissional recebeu aquele paciente e o
    atendeu. Nada de cadastro novo, nada de índice de reputação — só o ledger
    lido de trás para frente.

    TRÊS REGRAS QUE FAZEM ESTA SUGESTÃO SER HONESTA (§5):

    1. **Razão declarada.** Cada item traz `razao` e `atendimentos` — a tela
       mostra POR QUE aquele nome está ali. Sugestão sem razão é palpite com
       cara de recomendação.
    2. **Nunca pré-selecionada.** Este endpoint só devolve lista; a escolha do
       destino é do prescritor, e o formulário não marca nenhuma por padrão.
    3. **Auditável.** O que a tela apresentar volta em `sugestoes_apresentadas`
       no `POST /encaminhamentos` e entra no payload de
       `encaminhamento_emitido`. Se o sistema influencia, a influência fica
       registrada ao lado da escolha.

    ORDEM: mais atendimentos primeiro, desempate pelo mais recente. Não é
    ranking de qualidade e o texto da tela não pode sugerir que seja —
    é "já cuidou deste paciente", nada mais.

    ESCOPO: só o paciente informado. Não existe aqui "os mais usados da rede" —
    isso seria captura de demanda, e o §5 a nomeia como o risco a mitigar.
    """
    cpf = normalize_cpf(cpf_paciente)
    limite = max(1, min(limite, 20))

    with get_tx() as conn:
        linhas = conn.execute(
            """
            SELECT e.cns_destino,
                   e.especialidade_destino,
                   COUNT(*)          AS atendimentos,
                   MAX(e.data_emissao) AS ultimo
              FROM encaminhamentos e
              JOIN pacientes p ON p.id = e.paciente_id
             WHERE p.cpf = ?
               AND e.status IN ('atendido', 'contrarreferido', 'encerrado')
             GROUP BY e.cns_destino, e.especialidade_destino
             ORDER BY COUNT(*) DESC, MAX(e.data_emissao) DESC
            """,
            (cpf,),
        ).fetchall()

    itens = []
    for r in linhas:
        if especialidade and r["especialidade_destino"] != especialidade:
            continue
        # O nome do profissional NÃO vem daqui: o encaminhamento guarda o CNS do
        # destino, e resolver nome exigiria uma leitura que este endpoint não
        # precisa fazer. A tela resolve o que souber e mostra o CNS quando não
        # souber — melhor um CNS honesto que um nome adivinhado.
        itens.append({
            "cns_destino":   r["cns_destino"],
            "especialidade": r["especialidade_destino"],
            "atendimentos":  r["atendimentos"],
            "ultimo":        r["ultimo"],
            "razao":         "já atendeu este paciente",
        })
        if len(itens) >= limite:
            break

    return {"cpf_paciente": cpf, "sugestoes": itens}


@router.post("/fisica", status_code=201)
def criar_encaminhamento_fisico(
    payload: EncaminhamentoFisicoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    if not payload.itens:
        raise HTTPException(status_code=422, detail="O encaminhamento deve conter ao menos um item.")

    cns_origem = normalize_cns(payload.cns_prescritor)
    cns_destino = normalize_cns(payload.cns_destino)
    if papel != "admin":
        _assert_or_403(
            ident == cns_origem,
            codigo="prescritor_mismatch",
            mensagem="CNS do payload não coincide com prescritor autenticado.",
        )

    cpf = normalize_cpf(payload.cpf_paciente) if payload.cpf_paciente else _CPF_NAO_IDENTIFICADO
    nome_paciente = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()
    data_validade = (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns_origem, payload.nome_prescritor, agora)
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_paciente, agora)

        cursor = conn.execute(
            """
            INSERT INTO encaminhamentos
              (protocolo, prescritor_id, paciente_id, cns_destino,
               especialidade_destino, cid, justificativa_clinica, status,
               tipo_emissao, data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'encerrado_fisico', 'fisico', ?, ?, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id, cns_destino,
                payload.especialidade_destino, payload.cid, payload.justificativa_clinica,
                data_emissao, data_validade, agora,
            ),
        )
        enc_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO encaminhamento_itens
                  (encaminhamento_id, especialidade, procedimento, motivo, status_item, criado_em)
                VALUES (?, ?, ?, ?, 'encerrado_fisico', ?)
                """,
                (enc_id, item.especialidade, item.procedimento, item.motivo, agora),
            )

        doc_hash = _calcular_hash(
            protocolo=protocolo,
            cns_origem=cns_origem,
            cns_destino=cns_destino,
            cpf_paciente=cpf,
            especialidade_destino=payload.especialidade_destino,
            cid=payload.cid,
            justificativa_clinica=payload.justificativa_clinica,
            itens=payload.itens,
        )
        conn.execute("UPDATE encaminhamentos SET assinatura_hash = ? WHERE id = ?", (doc_hash, enc_id))

        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc_id, "encaminhamento_impresso", {
            "tipo_emissao": "fisico",
            "itens_count": len(payload.itens),
            "cpf_identificado": payload.cpf_paciente is not None,
        }, papel, ident or cns_origem, instance_id=instance_id)

        return {
            "protocolo": protocolo,
            "status": "encerrado_fisico",
            "tipo_emissao": "fisico",
            "data_emissao": data_emissao,
            "itens_count": len(payload.itens),
            "documento_hash": doc_hash,
        }


@router.get("/{protocolo}")
def get_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura(conn, enc, papel, ident)
        itens = _get_itens(conn, enc["id"])
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, ator_tipo, ator_id, payload, created_at "
                "FROM encaminhamento_eventos WHERE encaminhamento_id = ? ORDER BY id ASC",
                (enc["id"],),
            ).fetchall()
        ]
        return {**enc, "itens": itens, "eventos": eventos}


@router.get("/{protocolo}/custodia")
def get_custodia_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura(conn, enc, papel, ident)
        rows = conn.execute(
            """
            SELECT item_id, detentor_tipo, detentor_id, transferida_em,
                   encerrada_em, motivo, created_at
              FROM encaminhamento_custodia
             WHERE encaminhamento_id = ?
             ORDER BY id ASC
            """,
            (enc["id"],),
        ).fetchall()
        return {"protocolo": protocolo, "custodia": [dict(r) for r in rows]}


@router.post("/{protocolo}/agendar", status_code=200)
def agendar_encaminhamento(
    protocolo: str,
    payload: AgendarEncaminhamentoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_destino(enc, ident)
        _validar_transicao(enc, "agendado")

        conn.execute("UPDATE encaminhamentos SET status = 'agendado' WHERE id = ?", (enc["id"],))
        conn.execute(
            "UPDATE encaminhamento_itens SET status_item = 'em_andamento' "
            "WHERE encaminhamento_id = ? AND status_item = 'pendente'",
            (enc["id"],),
        )
        # ENG-016 §1a — AGENDAR NÃO ESCREVE CUSTÓDIA.
        #
        # Marcar hora é compromisso; entregar o documento é posse. Antes, este
        # gesto movia a posse ao destino de carona com a marcação — o padrão
        # pré-J.7, e pelo mesmo motivo: era o único gesto disponível, então
        # carregava dois fatos. Quem move a posse agora é o CIDADÃO, em
        # `POST /encaminhamentos/{p}/entregar` (espelho do transferir-farmácia
        # e do transferir-laboratório).
        #
        # Consequência que é o ponto, não efeito colateral: um encaminhamento
        # `agendado` pode estar com o cidadão (marcou e ainda não foi) ou com o
        # destino (já entregou). Quem responde "onde está" é
        # `encaminhamento_custodia`, nunca o status — ler posse do status é o
        # defeito que o martelo do J.7 matou no exame.
        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "encaminhamento_agendado", {
            "status_anterior": enc["status"],
            "data_agendamento": payload.data_agendamento,
            "local_texto": payload.local_texto,
        }, papel, ident, instance_id=instance_id)
        return {"protocolo": protocolo, "status": "agendado"}


@router.post("/{protocolo}/entregar", status_code=200)
def entregar_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("paciente", "admin")),
):
    """O CIDADÃO entrega o encaminhamento ao prescritor de destino (ENG-016 §1a).

    Espelho exato do `transferir-farmacia` da receita e do
    `transferir-laboratorio` do exame: é o cidadão que leva o documento, e é o
    gesto dele que move a posse. Antes deste endpoint, a posse ia ao destino de
    carona com o `agendar` DELE — o cidadão não tinha gesto nenhum, e o
    protagonista do percurso era o único sem ato.

    POSSE MUDA, ESTADO NÃO. O encaminhamento continua `emitido` (ou `agendado`,
    se já houver hora marcada): entregar não é etapa clínica. UM fato, UM evento
    (`custodia_transferida`) — nada de mover estado de carona, que é o que o
    J.7 desfez no exame.

    Não há corpo: o destino já está NOMEADO no documento (`cns_destino`,
    congelado no hash). Aceitar um destino no payload deixaria o cidadão
    entregar a quem o documento não endereça.

    Ordem dos guards, anti-leak (#52): 404 do objeto → 403 de dono → 422 de
    posse/estado. Quem não é o paciente do encaminhamento não distingue, pelo
    status, um protocolo que existe de um que não existe.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)          # 404
        if papel != "admin":
            _assert_paciente(conn, enc, ident)                      # 403

        if eh_terminal_encaminhamento(enc["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Encaminhamento em estado terminal ({enc['status']}) não circula.",
            )

        atual = _custodia_ativa(conn, enc["id"])
        if atual is None:
            raise HTTPException(
                status_code=422,
                detail="Este encaminhamento não tem custódia ativa (emissão física não circula).",
            )
        if atual["detentor_tipo"] != "paciente":
            # Mensagem que ENSINA: dizer só "não é seu" mandaria o cidadão
            # procurar um erro que não é dele.
            raise HTTPException(
                status_code=422,
                detail=(
                    "Este encaminhamento já está com o profissional de destino — "
                    "a entrega já foi feita."
                ),
            )

        _fechar_custodia_ativa(conn, enc["id"], agora)
        _abrir_custodia(conn, enc["id"], "prescritor", enc["cns_destino"],
                        "apresentacao_cidadao", agora)

        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "custodia_transferida", {
            "de": "paciente",
            "de_id": atual["detentor_id"],
            "para": "prescritor_destino",
            "para_id": enc["cns_destino"],
            "motivo": "apresentacao_cidadao",
        }, papel, ident, instance_id=instance_id)
        return {
            "protocolo": protocolo,
            "status": enc["status"],          # inalterado: posse ≠ estado
            "detentor": "prescritor_destino",
            "cns_destino": enc["cns_destino"],
        }


@router.post("/{protocolo}/atender", status_code=200)
def atender_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_destino(enc, ident)
        _validar_transicao(enc, "atendido")

        conn.execute("UPDATE encaminhamentos SET status = 'atendido' WHERE id = ?", (enc["id"],))
        conn.execute(
            "UPDATE encaminhamento_itens SET status_item = 'concluido' "
            "WHERE encaminhamento_id = ? AND status_item NOT IN ('concluido','cancelado','encerrado_fisico')",
            (enc["id"],),
        )
        cpf = _cpf_paciente(conn, enc) or _CPF_NAO_IDENTIFICADO
        _fechar_custodia_ativa(conn, enc["id"], agora)
        _abrir_custodia(conn, enc["id"], "paciente", cpf, "atendimento_realizado", agora)

        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "encaminhamento_atendido", {
            "status_anterior": enc["status"],
        }, papel, ident, instance_id=instance_id)
        _evento(conn, enc["id"], "custodia_transferida", {
            "de": "prescritor_destino",
            "de_id": enc["cns_destino"],
            "para": "paciente",
            "para_id": cpf,
        }, papel, ident, instance_id=instance_id)
        return {"protocolo": protocolo, "status": "atendido"}


@router.post("/{protocolo}/encerrar", status_code=200)
def encerrar_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_origem(conn, enc, ident)
        _validar_transicao(enc, "encerrado")

        conn.execute("UPDATE encaminhamentos SET status = 'encerrado' WHERE id = ?", (enc["id"],))
        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "encaminhamento_encerrado", {
            "status_anterior": enc["status"],
            "motivo": "ciencia_origem",
        }, papel, ident, instance_id=instance_id)
        return {"protocolo": protocolo, "status": "encerrado"}


@router.post("/{protocolo}/cancelar", status_code=200)
def cancelar_encaminhamento(
    protocolo: str,
    payload: MotivoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_origem(conn, enc, ident)
        _validar_transicao(enc, "cancelado")

        conn.execute("UPDATE encaminhamentos SET status = 'cancelado' WHERE id = ?", (enc["id"],))
        itens = _get_itens(conn, enc["id"])
        cancelados = 0
        for item in itens:
            if not eh_terminal_item_encaminhamento(item["status_item"]):
                conn.execute(
                    "UPDATE encaminhamento_itens SET status_item = 'cancelado' WHERE id = ?",
                    (item["id"],),
                )
                cancelados += 1
        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "encaminhamento_cancelado", {
            "status_anterior": enc["status"],
            "motivo": payload.motivo,
            "itens_cancelados": cancelados,
        }, papel, ident, instance_id=instance_id)
        return {"protocolo": protocolo, "status": "cancelado", "itens_cancelados": cancelados}


@router.post("/{protocolo}/negar", status_code=200)
def negar_encaminhamento(
    protocolo: str,
    payload: MotivoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_origem_ou_destino(conn, enc, ident)
        _validar_transicao(enc, "negado")

        conn.execute("UPDATE encaminhamentos SET status = 'negado' WHERE id = ?", (enc["id"],))
        conn.execute(
            "UPDATE encaminhamento_itens SET status_item = 'cancelado' "
            "WHERE encaminhamento_id = ? AND status_item NOT IN ('concluido','cancelado','encerrado_fisico')",
            (enc["id"],),
        )
        instance_id = get_instance_id_conn(conn)
        _evento(conn, enc["id"], "encaminhamento_negado", {
            "status_anterior": enc["status"],
            "motivo": payload.motivo,
        }, papel, ident, instance_id=instance_id)
        return {"protocolo": protocolo, "status": "negado"}


@router.get("/{protocolo}/pdf", response_class=Response)
def pdf_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura(conn, enc, papel, ident)
        itens = _get_itens(conn, enc["id"])
        origem = conn.execute(
            "SELECT nome, cns FROM prescritores WHERE id = ?", (enc["prescritor_id"],)
        ).fetchone()
        paciente = conn.execute(
            "SELECT nome, cpf FROM pacientes WHERE id = ?", (enc["paciente_id"],)
        ).fetchone()

    pdf_bytes = gerar_pdf_encaminhamento(
        protocolo=protocolo,
        status=enc["status"],
        tipo_emissao=enc["tipo_emissao"],
        assinatura_hash=enc.get("assinatura_hash"),
        data_emissao=enc["data_emissao"],
        data_validade=enc["data_validade"],
        nome_origem=origem["nome"] if origem else "-",
        cns_origem=origem["cns"] if origem else "-",
        cns_destino=enc["cns_destino"],
        especialidade_destino=enc["especialidade_destino"],
        cid=enc.get("cid"),
        justificativa_clinica=enc["justificativa_clinica"],
        nome_paciente=paciente["nome"] if paciente else "-",
        cpf_paciente=paciente["cpf"] if paciente else _CPF_NAO_IDENTIFICADO,
        itens=itens,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="encaminhamento-{protocolo[:8]}.pdf"'},
    )


@router.get("/{protocolo}/qr", response_class=Response)
def qr_encaminhamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura(conn, enc, papel, ident)

    url = f"{BASE_URL}/public/encaminhamentos/{protocolo}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")
