"""
routers/pedidos_exame.py
========================
Emissão digital e física de pedidos de exame.

Ticket 15 — Model + emissão (digital e física)
Ticket 16 — Custódia + fluxo (agendar/coletar)    [futuro]
Ticket 17 — Resultado + PDF + validação pública    [futuro]

ROTAS IMPLEMENTADAS (Ticket 15)
---------------------------------
POST /pedidos-exame           ← emissão digital
POST /pedidos-exame/fisica    ← emissão física (fire-and-forget)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.dependencies import require_role
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.cofre_pfx import decifrar_pfx
from app.domain.ledger import registrar_evento_ledger
from app.domain.outbox import registrar_outbox
from app.domain.pdf_assinatura import (
    MetadataAssinatura,
    SenhaPfxInvalida,
    assinar_pdf_icp,
)
from app.instance import get_instance_id_conn
from app.domain.states_exame import (
    ESTADOS_TERMINAIS_PEDIDO_EXAME,
    derivar_status_pedido,
    transicao_valida_pedido,
    transicao_valida_item_exame,
    eh_terminal_pedido,
    eh_terminal_item_exame,
)
from app.utils.helpers import (
    normalize_cns,
    normalize_cpf,
    normalize_nome,
    normalize_cnpj,
    _assert_or_403,
    _normalizar_identidade_jwt,
)

router = APIRouter(prefix="/pedidos-exame", tags=["pedidos_exame"])

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO = "00000000000"   # Convenção: mesmo valor da prescrição
_TIPOS_EMISSAO_VALIDOS = {"novo", "correcao", "renovacao"}
_PRIORIDADES_VALIDAS   = {"rotina", "urgente", "urgentissimo"}
_VALIDADE_PADRAO_DIAS  = 30


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class ItemExameIn(BaseModel):
    nome_exame:    str
    codigo_tuss:   Optional[str] = None
    codigo_sigtap: Optional[str] = None
    quantidade:    int = 1

    @field_validator("nome_exame")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_exame não pode ser vazio")
        return v.strip().upper()

    @field_validator("quantidade")
    @classmethod
    def quantidade_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantidade deve ser maior que zero")
        return v


class PedidoExameIn(BaseModel):
    cns_prescritor:   str
    nome_prescritor:  Optional[str] = None
    cpf_paciente:     str
    nome_paciente:    str
    prioridade:       str = "rotina"
    indicacao_clinica: Optional[str] = None
    data_validade:    Optional[str] = None    # ISO 8601; padrão: 30 dias
    tipo_emissao:     str = "novo"
    origem_pedido_id: Optional[int] = None
    # Ticket 63 — Escolha de modo de entrega na emissão.
    # True  = criar custódia prescritor→paciente imediatamente (carteira digital).
    # False = pedido fica em 'emitido', paciente acessa via link (comportamento original).
    enviar_ao_paciente: bool = False
    itens:            List[ItemExameIn] = []

    @field_validator("tipo_emissao")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_EMISSAO_VALIDOS:
            raise ValueError(
                f"tipo_emissao inválido: '{v}'. Valores aceitos: {sorted(_TIPOS_EMISSAO_VALIDOS)}"
            )
        return v

    @field_validator("prioridade")
    @classmethod
    def prioridade_valida(cls, v: str) -> str:
        if v not in _PRIORIDADES_VALIDAS:
            raise ValueError(
                f"prioridade inválida: '{v}'. Valores aceitos: {sorted(_PRIORIDADES_VALIDAS)}"
            )
        return v

    @model_validator(mode="after")
    def origem_obrigatoria_para_nao_novo(self) -> "PedidoExameIn":
        if self.tipo_emissao != "novo" and self.origem_pedido_id is None:
            raise ValueError(
                f"origem_pedido_id é obrigatório quando tipo_emissao='{self.tipo_emissao}'"
            )
        return self


class FisicaExameIn(BaseModel):
    cns_prescritor:    str
    nome_prescritor:   Optional[str] = None
    cpf_paciente:      Optional[str] = None
    nome_paciente:     str
    prioridade:        str = "rotina"
    indicacao_clinica: Optional[str] = None
    itens:             List[ItemExameIn] = []

    @field_validator("prioridade")
    @classmethod
    def prioridade_valida(cls, v: str) -> str:
        if v not in _PRIORIDADES_VALIDAS:
            raise ValueError(
                f"prioridade inválida: '{v}'. Valores aceitos: {sorted(_PRIORIDADES_VALIDAS)}"
            )
        return v


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _calcular_hash(protocolo: str, cns: str, cpf: str,
                   data_emissao: str, data_validade: str,
                   prioridade: str, indicacao: Optional[str],
                   itens: list) -> str:
    """
    Hash SHA-256 do documento canônico do pedido de exame.
    Versão simplificada para Ticket 15 — módulo completo vem no Ticket 17.
    """
    doc = {
        "protocolo":        protocolo,
        "prescritor_cns":   cns,
        "paciente_cpf":     cpf,
        "data_emissao":     data_emissao,
        "data_validade":    data_validade,
        "prioridade":       prioridade,
        "indicacao_clinica": indicacao,
        "itens": [
            {
                "nome_exame":  item.nome_exame,
                "codigo_tuss": item.codigo_tuss,
                "quantidade":  item.quantidade,
            }
            for item in itens
        ],
        "versao_esquema": "1",
    }
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
            detail=(
                f"Prescritor com CNS '{cns}' não encontrado. "
                "Envie 'nome_prescritor' para registrá-lo automaticamente."
            ),
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


# ---------------------------------------------------------------------------
# POST /pedidos-exame — emissão digital
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def criar_pedido_exame(
    payload: PedidoExameIn,
    usuario=Depends(require_role("prescritor")),
):
    """
    Emite um pedido de exame digitalmente.

    Fluxo:
    1. Localiza ou registra prescritor por CNS
    2. Valida pedido de origem (correcao/renovacao)
    3. Localiza ou registra paciente por CPF
    4. Insere pedido com status 'emitido'
    5. Insere itens com status 'pendente'
    6. Gera hash do documento canônico
    7. Grava evento 'pedido_emitido' no ledger
    """
    # TICKET-5C-BIS-A §7.1 (Padrão A) — ownership por identidade nominal: o CNS
    # declarado no payload deve coincidir com o do JWT. Primeiro efeito do
    # handler, antes de qualquer escrita (prova de rollback, §9).
    papel, ident = _normalizar_identidade_jwt(usuario)

    if not payload.itens:
        raise HTTPException(status_code=422, detail="O pedido deve conter ao menos um item.")

    cns       = normalize_cns(payload.cns_prescritor)
    _assert_or_403(
        ident == cns,
        codigo="prescritor_mismatch",
        mensagem="CNS do payload não coincide com prescritor autenticado.",
    )
    cpf       = normalize_cpf(payload.cpf_paciente)
    nome_pac  = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora     = datetime.utcnow().isoformat()

    data_emissao  = date.today().isoformat()
    data_validade = (
        payload.data_validade
        or (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()
    )

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)

        if payload.origem_pedido_id is not None:
            # P1 (CODEX rodada 2) — derivação (correcao/renovacao) só pode apontar
            # para pedido do PRÓPRIO prescritor: 404 se não existe, 403 se pertence a
            # outro CNS. Sem o JOIN, A derivaria objeto ligado à cadeia clínica de B.
            origem = conn.execute(
                "SELECT pr.cns FROM pedidos_exame pe "
                "JOIN prescritores pr ON pr.id = pe.prescritor_id "
                "WHERE pe.id = ?",
                (payload.origem_pedido_id,),
            ).fetchone()
            if not origem:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pedido de origem id={payload.origem_pedido_id} não encontrado.",
                )
            _assert_or_403(
                origem["cns"] == ident,
                codigo="nao_e_dono_do_pedido_exame",
                mensagem="O pedido de exame de origem foi emitido por outro prescritor.",
            )

        # Ticket 63: verificar se paciente já existe antes de criar
        _pac_row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
        paciente_existia = _pac_row is not None

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

        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO pedidos_exame
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               origem_pedido_id, prioridade, indicacao_clinica,
               data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'emitido', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id,
                payload.tipo_emissao, payload.origem_pedido_id,
                payload.prioridade, payload.indicacao_clinica,
                data_emissao, data_validade, agora,
            ),
        )
        pedido_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO pedido_exame_itens
                  (pedido_id, nome_exame, codigo_tuss, codigo_sigtap,
                   status_item, quantidade, criado_em)
                VALUES (?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (pedido_id, item.nome_exame, item.codigo_tuss,
                 item.codigo_sigtap, item.quantidade, agora),
            )

        doc_hash = _calcular_hash(
            protocolo, cns, cpf, data_emissao, data_validade,
            payload.prioridade, payload.indicacao_clinica, payload.itens,
        )
        conn.execute(
            "UPDATE pedidos_exame SET assinatura_hash = ? WHERE id = ?",
            (doc_hash, pedido_id),
        )

        # Ticket 4D.2: instance_id uma vez por transação clínica.
        instance_id = get_instance_id_conn(conn)

        ev_emitido = {
            "tipo_emissao":     payload.tipo_emissao,
            "origem_pedido_id": payload.origem_pedido_id,
            "prioridade":       payload.prioridade,
            "itens_count":      len(payload.itens),
        }
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido_id,
            tipo_evento="pedido_emitido",
            instance_id=instance_id,
            payload=ev_emitido,
        )
        registrar_outbox(
            conn, "pedido_emitido", "pedido_exame", protocolo, ev_emitido,
            instance_id=instance_id,
        )

        # ------------------------------------------------------------------
        # Ticket 63 — Entrega à carteira digital
        # Se enviar_ao_paciente=True e paciente já existia (tem carteira),
        # cria custódia prescritor→paciente em pedido_exame_custodia.
        # O status do pedido permanece 'emitido' (não há estado
        # 'transferida_paciente' no módulo de exames — exceção documentada).
        # ------------------------------------------------------------------
        entregue_carteira = False

        if payload.enviar_ao_paciente and paciente_existia:
            conn.execute(
                """
                INSERT INTO pedido_exame_custodia
                  (pedido_id, item_id, de, para, transferido_em, dados_json)
                VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)
                """,
                (
                    pedido_id,
                    agora,
                    json.dumps(
                        {
                            "de": "prescritor", "de_id": cns,
                            "para": "paciente", "para_id": cpf,
                            "motivo": "entrega_carteira_digital",
                            "via": "emissao_direta",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            registrar_evento_ledger(
                conn,
                objeto_tipo="pedido_exame",
                objeto_id=pedido_id,
                tipo_evento="custodia_transferida",
                instance_id=instance_id,
                payload={
                    "de": "prescritor", "de_id": cns,
                    "para": "paciente", "para_id": cpf,
                    "via": "emissao_direta",
                },
            )
            entregue_carteira = True

        return {
            "id":               pedido_id,
            "protocolo":        protocolo,
            "status":           "emitido",
            "tipo_emissao":     payload.tipo_emissao,
            "prioridade":       payload.prioridade,
            "data_emissao":     data_emissao,
            "data_validade":    data_validade,
            "itens_count":      len(payload.itens),
            "documento_hash":   doc_hash,
            # Ticket 63 — resultado da entrega à carteira digital
            # True  = custódia criada imediatamente em pedido_exame_custodia
            # False = pedido em 'emitido'; frontend exibe link de acesso
            "entregue_carteira": entregue_carteira,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/fisica — emissão exclusivamente física (fire-and-forget)
# ---------------------------------------------------------------------------

@router.post("/fisica", status_code=201)
def criar_pedido_exame_fisico(
    payload: FisicaExameIn,
    usuario=Depends(require_role("prescritor")),
):
    """
    Registra um pedido de exame emitido exclusivamente em papel.

    Diferenças em relação à emissão digital:
    - Status final do pedido: encerrado_fisico
    - Status de cada item: encerrado_fisico
    - Sem cadeia de custódia (nenhum registro em pedido_exame_custodia)
    - Dois eventos no ledger: pedido_impresso + encerrado_localmente
    - cpf_paciente é opcional (sentinela '00000000000' se ausente)

    Fire-and-forget: o frontend imprime sem aguardar resposta.
    """
    # TICKET-5C-BIS-A §7.1 (Padrão A) — mesma checagem da emissão digital:
    # CNS do payload == CNS do JWT, antes de qualquer escrita.
    papel, ident = _normalizar_identidade_jwt(usuario)

    if not payload.itens:
        raise HTTPException(status_code=422, detail="O pedido deve conter ao menos um item.")

    cns      = normalize_cns(payload.cns_prescritor)
    _assert_or_403(
        ident == cns,
        codigo="prescritor_mismatch",
        mensagem="CNS do payload não coincide com prescritor autenticado.",
    )
    cpf      = normalize_cpf(payload.cpf_paciente) if payload.cpf_paciente else _CPF_NAO_IDENTIFICADO
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora    = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()
    # Ticket 4D.2 (rodada 4): fix incidental — data_validade era
    # NULL mas schema é NOT NULL. Mesma classe do fix da 4D.1 §4.7
    # P1.2 (auth.py prescricao_custodia). Usa mesma fórmula/constante
    # do endpoint digital (linhas 237-240).
    data_validade = (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)
        paciente_id   = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO pedidos_exame
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               prioridade, indicacao_clinica, data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'encerrado_fisico', 'fisico', ?, ?, ?, ?, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id,
                payload.prioridade, payload.indicacao_clinica,
                data_emissao, data_validade, agora,
            ),
        )
        pedido_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO pedido_exame_itens
                  (pedido_id, nome_exame, codigo_tuss, codigo_sigtap,
                   status_item, quantidade, criado_em)
                VALUES (?, ?, ?, ?, 'encerrado_fisico', ?, ?)
                """,
                (pedido_id, item.nome_exame, item.codigo_tuss,
                 item.codigo_sigtap, item.quantidade, agora),
            )

        # Ticket 4D.2: dois eventos no ledger (mesmo padrão do fluxo físico
        # da prescrição). Mesmo instance_id em ambos — invariante forense.
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido_id,
            tipo_evento="pedido_impresso",
            instance_id=instance_id,
            payload={
                "tipo_emissao":      "fisico",
                "itens_count":       len(payload.itens),
                "cpf_identificado":  payload.cpf_paciente is not None,
            },
        )
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido_id,
            tipo_evento="encerrado_localmente",
            instance_id=instance_id,
            payload={
                "status_novo":           "encerrado_fisico",
                "motivo":                "emissao_exclusivamente_fisica",
                "sem_custodia_digital":  True,
            },
        )

        return {
            "protocolo":     protocolo,
            "status":        "encerrado_fisico",
            "tipo_emissao":  "fisico",
            "prioridade":    payload.prioridade,
            "data_emissao":  data_emissao,
            "itens_count":   len(payload.itens),
        }


# ---------------------------------------------------------------------------
# Helpers internos compartilhados pelos endpoints de fluxo
# ---------------------------------------------------------------------------

def _get_pedido_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")
    return dict(row)


# ---------------------------------------------------------------------------
# TICKET-5C-BIS-A §7.0 — Helpers locais privados de ownership (DRY no módulo).
# As queries de ownership ficam locais ao subdomínio (ADR-002 opção C), mas sem
# reescrever o mesmo JOIN em 5 endpoints. NÃO são abstração global (P2 do
# Conselheiro). Usam o Helper 1 global `_assert_or_403`.
# ---------------------------------------------------------------------------

def _assert_prescritor_dono_pedido(conn, protocolo: str, ident_cns: str) -> None:
    dono = conn.execute(
        "SELECT pr.cns FROM pedidos_exame pe "
        "JOIN prescritores pr ON pr.id = pe.prescritor_id "
        "WHERE pe.protocolo = ?", (protocolo,),
    ).fetchone()
    _assert_or_403(
        dono is not None and ident_cns == dono["cns"],
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame foi emitido por outro prescritor.",
    )


def _assert_paciente_dono_pedido(conn, protocolo: str, ident_cpf: str) -> None:
    dono = conn.execute(
        "SELECT pa.cpf FROM pedidos_exame pe "
        "JOIN pacientes pa ON pa.id = pe.paciente_id "
        "WHERE pe.protocolo = ?", (protocolo,),
    ).fetchone()
    _assert_or_403(
        dono is not None and ident_cpf == dono["cpf"],
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame pertence a outro paciente.",
    )


def _assert_dispensador_dono_pedido(conn, pedido_id: int, ident_cnpj: str) -> None:
    # Dono = prestador na CUSTÓDIA ATUAL do pedido inteiro (item_id IS NULL),
    #   pós-'agendar'. NÃO "qualquer custódia histórica" (correção do P1(b) da
    #   CODEX rodada 1): um prestador que já foi custodiante e perdeu a custódia
    #   não pode continuar passando. Por isso ORDER BY id DESC LIMIT 1.
    # Comparação direta (opção A, §8.4): o 'agendar' agora grava o CNPJ já
    #   normalizado, então não normalizamos o lado lido. Guard len==14 é
    #   defensivo: ident não-CNPJ (ex.: admin já fez bypass; mas paranoia)
    #   nunca casa, e a custódia 'paciente' (carteira) também não casa.
    if len(ident_cnpj) != 14:
        _assert_or_403(False, codigo="nao_e_dono_do_pedido_exame",
                       mensagem="Pedido de exame sob responsabilidade de outro prestador.")
    atual = conn.execute(
        "SELECT para FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (pedido_id,),
    ).fetchone()
    _assert_or_403(
        atual is not None and atual["para"] == ident_cnpj,
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Pedido de exame sob responsabilidade de outro prestador.",
    )


def _get_itens(conn, pedido_id: int) -> list:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE pedido_id = ?", (pedido_id,)
        ).fetchall()
    ]


def _recalcular_e_atualizar_status_pedido(conn, pedido_id: int, agora: str) -> str:
    itens = conn.execute(
        "SELECT status_item FROM pedido_exame_itens WHERE pedido_id = ?", (pedido_id,)
    ).fetchall()
    novo_status = derivar_status_pedido([i["status_item"] for i in itens])
    conn.execute(
        "UPDATE pedidos_exame SET status = ? WHERE id = ?",
        (novo_status, pedido_id),
    )
    return novo_status


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo} — consulta individual
# ---------------------------------------------------------------------------

@router.get("/{protocolo}")
def get_pedido_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (MVP, futuro: prestador)
):
    # TICKET-5C-BIS-A §7.2 — bypass de admin; demais papéis validam ownership
    # logo após o 404 e ANTES de devolver conteúdo (anti-leak #52).
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)
            elif papel == "dispensador":
                _assert_dispensador_dono_pedido(conn, pedido["id"], ident)
        itens  = _get_itens(conn, pedido["id"])
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, dados_json, criado_em FROM pedido_exame_eventos "
                "WHERE pedido_id = ? ORDER BY id ASC",
                (pedido["id"],),
            ).fetchall()
        ]
        return {**pedido, "itens": itens, "eventos": eventos}


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/custodia — histórico de custódia
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/custodia")
def get_custodia_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    # TICKET-5C-BIS-A §7.2 — matriz prescritor/paciente; admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)
            elif papel == "paciente":
                _assert_paciente_dono_pedido(conn, protocolo, ident)
        registros = conn.execute(
            "SELECT de, para, transferido_em, dados_json FROM pedido_exame_custodia "
            "WHERE pedido_id = ? ORDER BY id ASC",
            (pedido["id"],),
        ).fetchall()
        return {"protocolo": protocolo, "custodia": [dict(r) for r in registros]}


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/agendar — nível do pedido
# Transição: emitido → agendado
# Todos os itens pendentes → agendado
# Cria registro de custódia: paciente → prestador_exame
# ---------------------------------------------------------------------------

class AgendarIn(BaseModel):
    cnpj_prestador: str
    nome_prestador: Optional[str] = None
    data_agendamento: Optional[str] = None


@router.post("/{protocolo}/agendar", status_code=201)
def agendar_pedido_exame(
    protocolo: str,
    payload: AgendarIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """
    Registra o agendamento de um pedido com um prestador de exames.

    - Pedido deve estar em 'emitido' ou 'agendado' (re-agendamento parcial)
    - Itens 'pendente' → 'agendado'
    - Custódia: paciente → prestador_exame (nível pedido)
    - Status do pedido recalculado via derivar_status_pedido()
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — ownership (prescritor; admin bypassa) ANTES das
    # checagens de estado 422 (anti-leak #52).
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal ({pedido['status']}).",
            )
        if pedido["status"] not in ("emitido", "agendado"):
            raise HTTPException(
                status_code=422,
                detail=f"Agendamento requer status 'emitido' ou 'agendado'. Status atual: '{pedido['status']}'.",
            )

        itens = _get_itens(conn, pedido["id"])
        itens_agendar = [i for i in itens if i["status_item"] == "pendente"]

        if not itens_agendar:
            raise HTTPException(status_code=422, detail="Nenhum item 'pendente' disponível para agendar.")

        for item in itens_agendar:
            conn.execute(
                "UPDATE pedido_exame_itens SET status_item = 'agendado' WHERE id = ?",
                (item["id"],),
            )

        # TICKET-5C-BIS-A §8.4 (opção A) — normalizar o CNPJ na ESCRITA, na raiz.
        # A custódia (e ledger/retorno) guardam o CNPJ homogêneo (sem máscara,
        # sem sufixo .0), para que o ownership do dispensador (§7.0) compare
        # contra um valor já canônico. AgendarIn permanece sem validator.
        cnpj_prestador_norm = normalize_cnpj(payload.cnpj_prestador)

        conn.execute(
            """
            INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json)
            VALUES (?, NULL, 'paciente', ?, ?, ?)
            """,
            (
                pedido["id"],
                cnpj_prestador_norm,
                agora,
                json.dumps({
                    "nome_prestador":   payload.nome_prestador,
                    "data_agendamento": payload.data_agendamento,
                }, ensure_ascii=False),
            ),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="pedido_agendado",
            instance_id=instance_id,
            payload={
                "cnpj_prestador":   cnpj_prestador_norm,
                "nome_prestador":   payload.nome_prestador,
                "data_agendamento": payload.data_agendamento,
                "itens_agendados":  len(itens_agendar),
            },
        )

        return {
            "protocolo":       protocolo,
            "status":          novo_status,
            "itens_agendados": len(itens_agendar),
            "cnpj_prestador":  cnpj_prestador_norm,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/itens/{item_id}/coletar — nível do item
# Transição do item: agendado → coletado
# O item é a unidade operacional de coleta.
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/itens/{item_id}/coletar", status_code=201)
def coletar_item_exame(
    protocolo: str,
    item_id: int,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (MVP, futuro: prestador)
):
    """
    Registra a coleta de um item específico.

    Item: agendado → coletado
    Status do pedido recalculado automaticamente via derivar_status_pedido().
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — prescritor/dispensador validam ownership; admin
    # bypassa. 404 → 403 → 422 de estado (anti-leak #52).
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)
            elif papel == "dispensador":
                _assert_dispensador_dono_pedido(conn, pedido["id"], ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(status_code=422, detail=f"Pedido '{protocolo}' está em estado terminal.")

        item = conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE id = ? AND pedido_id = ?",
            (item_id, pedido["id"]),
        ).fetchone()

        if not item:
            raise HTTPException(
                status_code=404, detail=f"Item {item_id} não encontrado no pedido '{protocolo}'."
            )

        if item["status_item"] != "agendado":
            raise HTTPException(
                status_code=422,
                detail=f"Coleta requer item em 'agendado'. Status atual: '{item['status_item']}'.",
            )

        conn.execute(
            "UPDATE pedido_exame_itens SET status_item = 'coletado' WHERE id = ?",
            (item_id,),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        ev_coletado = {"item_id": item_id, "nome_exame": item["nome_exame"]}
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="pedido_coletado",
            instance_id=instance_id,
            payload=ev_coletado,
        )
        registrar_outbox(
            conn, "pedido_coletado", "pedido_exame", protocolo, ev_coletado,
            instance_id=instance_id,
        )

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "coletado",
            "status_pedido": novo_status,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/cancelar
# ---------------------------------------------------------------------------

class CancelarIn(BaseModel):
    motivo: Optional[str] = None


@router.post("/{protocolo}/cancelar", status_code=200)
def cancelar_pedido_exame(
    protocolo: str,
    payload: CancelarIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """
    Cancela o pedido e todos os itens não terminais.
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — só o prescritor dono cancela; admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' já está em estado terminal ({pedido['status']}).",
            )

        itens = _get_itens(conn, pedido["id"])
        cancelados = 0
        for item in itens:
            if not eh_terminal_item_exame(item["status_item"]):
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'cancelado' WHERE id = ?",
                    (item["id"],),
                )
                cancelados += 1

        conn.execute(
            "UPDATE pedidos_exame SET status = 'cancelado' WHERE id = ?",
            (pedido["id"],),
        )

        ev_cancelado = {
            "status_anterior":  pedido["status"],
            "motivo":           payload.motivo,
            "itens_cancelados": cancelados,
        }
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="pedido_cancelado",
            instance_id=instance_id,
            payload=ev_cancelado,
        )
        registrar_outbox(
            conn, "pedido_cancelado", "pedido_exame", protocolo, ev_cancelado,
            instance_id=instance_id,
        )

        return {
            "protocolo":        protocolo,
            "status":           "cancelado",
            "itens_cancelados": cancelados,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/itens/{item_id}/resultado
# Transição: coletado → em_analise → resultado_disponivel (colapsado para MVP)
# Dois eventos no ledger: pedido_em_analise + resultado_registrado
# ---------------------------------------------------------------------------

class ResultadoIn(BaseModel):
    resultado_resumo: Optional[str] = None
    resultado_url:    Optional[str] = None


@router.post("/{protocolo}/itens/{item_id}/resultado", status_code=201)
def registrar_resultado_item(
    protocolo: str,
    item_id: int,
    payload: ResultadoIn,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (R1 V2)
):
    """
    Registra o resultado de um item de exame.

    Fluxo MVP colapsado (dois eventos no ledger):
        coletado → em_analise   (pedido_em_analise)
        em_analise → resultado_disponivel  (resultado_registrado)

    Status do pedido recalculado automaticamente.
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — prescritor/dispensador validam ownership; admin
    # bypassa. 404 → 403 → 422 de estado (anti-leak #52).
    # R1 do arco V2 (DESPACHO-ENG-007): `dispensador` (clínica/lab) passou a
    # registrar resultado. Antes, a clínica coletava e realizava mas dependia de
    # um prescritor para "bater o resultado" — fricção sem justificativa clínica.
    # A guarda de posse é a MESMA de coletar_item_exame: dono = prestador na
    # custódia ATUAL do pedido inteiro. Nada de guarda nova.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)
            elif papel == "dispensador":
                _assert_dispensador_dono_pedido(conn, pedido["id"], ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal.",
            )

        item = conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE id = ? AND pedido_id = ?",
            (item_id, pedido["id"]),
        ).fetchone()

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item_id} não encontrado no pedido '{protocolo}'.",
            )

        if item["status_item"] not in ("coletado", "em_analise"):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Registro de resultado requer item em 'coletado' ou 'em_analise'. "
                    f"Status atual: '{item['status_item']}'."
                ),
            )

        # Ticket 4D.2: dois eventos compartilham instance_id (invariante
        # forense da transação de registro de resultado).
        instance_id = get_instance_id_conn(conn)

        # Evento intermediário: em_analise (semântica preservada no ledger)
        if item["status_item"] == "coletado":
            registrar_evento_ledger(
                conn,
                objeto_tipo="pedido_exame",
                objeto_id=pedido["id"],
                tipo_evento="pedido_em_analise",
                instance_id=instance_id,
                payload={"item_id": item_id, "nome_exame": item["nome_exame"]},
            )

        # Atualizar item com resultado e transicionar para resultado_disponivel
        conn.execute(
            """
            UPDATE pedido_exame_itens
            SET status_item = 'resultado_disponivel',
                resultado_resumo = ?,
                resultado_url = ?,
                resultado_em = ?
            WHERE id = ?
            """,
            (payload.resultado_resumo, payload.resultado_url, agora, item_id),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        ev_resultado = {
            "item_id":    item_id,
            "nome_exame": item["nome_exame"],
            "tem_resumo": payload.resultado_resumo is not None,
            "tem_url":    payload.resultado_url is not None,
        }
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="resultado_registrado",
            instance_id=instance_id,
            payload=ev_resultado,
        )
        registrar_outbox(
            conn, "resultado_registrado", "pedido_exame", protocolo, ev_resultado,
            instance_id=instance_id,
        )

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "resultado_disponivel",
            "status_pedido": novo_status,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/encerrar
# Ciência formal do resultado pelo prescritor/paciente.
# Transição: itens resultado_disponivel → encerrado
# Pedido: resultado_disponivel → encerrado
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/encerrar", status_code=200)
def encerrar_pedido_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    """
    Registra a ciência formal do resultado.

    "resultado_disponivel" e "encerrado" NÃO são o mesmo estado:
    - resultado_disponivel: laudo pronto, aguarda ciência
    - encerrado: ciência registrada, ciclo completo

    Todos os itens em 'resultado_disponivel' → 'encerrado'.
    Pedido → 'encerrado'.
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — matriz prescritor/paciente; admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)
            elif papel == "paciente":
                _assert_paciente_dono_pedido(conn, protocolo, ident)

        if pedido["status"] != "resultado_disponivel":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Encerramento requer pedido em 'resultado_disponivel'. "
                    f"Status atual: '{pedido['status']}'."
                ),
            )

        itens = _get_itens(conn, pedido["id"])
        encerrados = 0
        for item in itens:
            if item["status_item"] == "resultado_disponivel":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'encerrado' WHERE id = ?",
                    (item["id"],),
                )
                encerrados += 1

        conn.execute(
            "UPDATE pedidos_exame SET status = 'encerrado' WHERE id = ?",
            (pedido["id"],),
        )

        ev_encerrado = {
            "itens_encerrados": encerrados,
            "motivo": "ciencia_registrada",
        }
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="pedido_encerrado",
            instance_id=instance_id,
            payload=ev_encerrado,
        )
        registrar_outbox(
            conn, "pedido_encerrado", "pedido_exame", protocolo, ev_encerrado,
            instance_id=instance_id,
        )

        return {
            "protocolo":       protocolo,
            "status":          "encerrado",
            "itens_encerrados": encerrados,
        }


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/pdf — PDF do pedido de exame
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/pdf")
def get_pdf_pedido_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    from fastapi.responses import StreamingResponse
    from app.domain.pdf_pedido_exame import gerar_pdf_pedido_exame
    import io as _io

    # TICKET-5C-BIS-A §7.3 (Padrão C) — reusa o row (a query já faz JOIN pr.cns).
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT
                pe.protocolo, pe.status, pe.tipo_emissao, pe.prioridade,
                pe.indicacao_clinica, pe.assinatura_hash,
                pe.data_emissao, pe.data_validade,
                pr.nome AS nome_prescritor, pr.cns AS cns_prescritor,
                pa.nome AS nome_paciente, pa.cpf AS cpf_paciente
            FROM pedidos_exame pe
            JOIN prescritores pr ON pr.id = pe.prescritor_id
            JOIN pacientes    pa ON pa.id = pe.paciente_id
            WHERE pe.protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")

        # §7.3 — owner check só para 'prescritor'; admin passa. Não há
        # paciente/dispensador no require_role do pdf — não adicionar (§4.4).
        if papel == "prescritor":
            _assert_or_403(
                ident == row["cns_prescritor"],
                codigo="nao_e_dono_do_pedido_exame",
                mensagem="Este pedido de exame foi emitido por outro prescritor.",
            )

        itens = conn.execute(
            """
            SELECT nome_exame, codigo_tuss, codigo_sigtap, quantidade, status_item
            FROM pedido_exame_itens WHERE pedido_id = (
                SELECT id FROM pedidos_exame WHERE protocolo = ?
            )
            ORDER BY id
            """,
            (protocolo,),
        ).fetchall()

    pdf_bytes = gerar_pdf_pedido_exame(
        protocolo        = row["protocolo"],
        status           = row["status"],
        tipo_emissao     = row["tipo_emissao"],
        prioridade       = row["prioridade"] or "rotina",
        indicacao_clinica = row["indicacao_clinica"],
        assinatura_hash  = row["assinatura_hash"],
        data_emissao     = row["data_emissao"],
        data_validade    = row["data_validade"],
        nome_prescritor  = row["nome_prescritor"],
        cns_prescritor   = row["cns_prescritor"],
        nome_paciente    = row["nome_paciente"],
        cpf_paciente     = row["cpf_paciente"],
        itens            = [dict(i) for i in itens],
    )

    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="pedido-exame-{protocolo[:8]}.pdf"'
            ),
        },
    )


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/pdf-assinado — PDF + assinatura ICP (PAdES)
# Reusa o cofre + assinar_pdf_icp (idêntico à prescrição/atestado).
# ---------------------------------------------------------------------------

class PdfAssinadoExameRequest(BaseModel):
    senha_pfx: str = Field(..., min_length=1, max_length=200)


def _carregar_certificado_ativo_exame(conn, prescritor_id: int):
    row = conn.execute(
        """
        SELECT pfx_cifrado, pfx_iv, pfx_tag, hash_cert_der, serial,
               nome_no_certificado, cpf_no_certificado
          FROM prescritor_certificados
         WHERE prescritor_id = ? AND ativo = TRUE
        """,
        (prescritor_id,),
    ).fetchone()
    return dict(row) if row else None


@router.post("/{protocolo}/pdf-assinado", response_class=StreamingResponse)
def get_pdf_assinado_pedido_exame(
    protocolo: str,
    body: PdfAssinadoExameRequest,
    usuario=Depends(require_role("prescritor")),
):
    """Gera o PDF do pedido de exame e embute assinatura ICP-Brasil (PAdES-B)
    com o certificado A1 do prescritor no cofre.

    Segurança: senha usada uma vez (não persistida); .pfx decifrado só em memória
    e descartado. Bloqueado em DEMO_MODE. Registra `pdf_assinado_pades` no ledger.
    """
    from app.domain.pdf_pedido_exame import gerar_pdf_pedido_exame
    import io as _io

    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={"codigo": "demo_mode_ativo",
                    "mensagem": "Assinatura com certificado desabilitada em modo demo."},
        )

    _papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT pe.id, pe.prescritor_id, pe.protocolo, pe.status, pe.tipo_emissao,
                   pe.prioridade, pe.indicacao_clinica, pe.assinatura_hash,
                   pe.data_emissao, pe.data_validade,
                   pr.nome AS nome_prescritor, pr.cns AS cns_prescritor,
                   pa.nome AS nome_paciente, pa.cpf AS cpf_paciente
              FROM pedidos_exame pe
              JOIN prescritores pr ON pr.id = pe.prescritor_id
              JOIN pacientes    pa ON pa.id = pe.paciente_id
             WHERE pe.protocolo = ?
            """,
            (protocolo,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")
        _assert_or_403(
            ident == row["cns_prescritor"],
            codigo="nao_e_dono_do_pedido_exame",
            mensagem="Somente o prescritor que emitiu o pedido pode assiná-lo.",
        )

        cert = _carregar_certificado_ativo_exame(conn, row["prescritor_id"])
        if not cert:
            raise HTTPException(
                status_code=422,
                detail="Nenhum certificado ICP-Brasil ativo. Faça upload via POST /prescritor/certificado.",
            )

        itens = conn.execute(
            """
            SELECT nome_exame, codigo_tuss, codigo_sigtap, quantidade, status_item
              FROM pedido_exame_itens WHERE pedido_id = ? ORDER BY id
            """,
            (row["id"],),
        ).fetchall()

        pfx_bytes = decifrar_pfx(
            bytes(cert["pfx_cifrado"]), bytes(cert["pfx_iv"]), bytes(cert["pfx_tag"]),
        )
        pdf_base = gerar_pdf_pedido_exame(
            protocolo=row["protocolo"], status=row["status"], tipo_emissao=row["tipo_emissao"],
            prioridade=row["prioridade"] or "rotina", indicacao_clinica=row["indicacao_clinica"],
            assinatura_hash=row["assinatura_hash"], data_emissao=row["data_emissao"],
            data_validade=row["data_validade"], nome_prescritor=row["nome_prescritor"],
            cns_prescritor=row["cns_prescritor"], nome_paciente=row["nome_paciente"],
            cpf_paciente=row["cpf_paciente"], itens=[dict(i) for i in itens],
        )
        meta = MetadataAssinatura(
            nome_prescritor=cert["nome_no_certificado"] or row["nome_prescritor"] or "",
            cpf_prescritor=cert["cpf_no_certificado"],
            razao="Pedido de exame digital PicSaúde",
        )
        try:
            pdf_assinado = assinar_pdf_icp(
                pdf_bytes=pdf_base, pfx_bytes=pfx_bytes,
                senha=body.senha_pfx, metadata=meta,
            )
        except SenhaPfxInvalida:
            raise HTTPException(status_code=401, detail="Senha do certificado inválida.")
        finally:
            del pfx_bytes

        import hashlib as _hashlib
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn, objeto_tipo="pedido_exame", objeto_id=row["id"],
            tipo_evento="pdf_assinado_pades", instance_id=instance_id,
            payload={"hash_pdf": _hashlib.sha256(pdf_assinado).hexdigest(),
                     "serial_cert": cert["serial"], "hash_cert_der": cert["hash_cert_der"],
                     "nivel_pades": "B"},
        )

    return StreamingResponse(
        _io.BytesIO(pdf_assinado),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="pedido-exame-{protocolo[:8]}-assinado.pdf"'},
    )


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/qr — QR Code (aponta para validação pública)
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/qr")
def qr_code_pedido_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    import io as _io
    import qrcode
    from fastapi.responses import Response as _Response
    from app.config import BASE_URL

    # TICKET-5C-BIS-A §7.2/§5.1(3) — QR precisa de query nova (Padrão B): a
    # versão anterior só fazia SELECT 1. 404 → 403 (prescritor dono; admin bypassa).
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        _get_pedido_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)

    url = f"{BASE_URL}/public/exames/{protocolo}"
    qr  = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return _Response(content=buf.read(), media_type="image/png")
