"""
routers/laudos.py
=================
Módulo de laudos — artefato clínico produzido pelo prestador.

tipo_agregacao_status = "direto"
O status do laudo é transitado explicitamente pelos endpoints — não derivado dos itens.

ROTAS IMPLEMENTADAS (Ticket 20)
---------------------------------
POST /laudos                              ← emissão digital (prestador cria o laudo)
POST /laudos/fisica                       ← emissão física (fire-and-forget)
GET  /laudos/{proto}                      ← consulta completa (itens + eventos)
GET  /laudos/{proto}/custodia             ← histórico de custódia
POST /laudos/{proto}/assinar              ← responsável técnico declara assinatura
POST /laudos/{proto}/liberar              ← laudo disponibilizado ao paciente/prescritor
POST /laudos/{proto}/ciencia-paciente     ← paciente registra ciência
POST /laudos/{proto}/ciencia-prescritor   ← prescritor registra ciência clínica
POST /laudos/{proto}/cancelar             ← cancelar laudo não liberado
POST /laudos/{proto}/encerrar             ← encerramento formal do ciclo

ROTAS IMPLEMENTADAS (Ticket 21)
---------------------------------
GET  /laudos/{proto}/pdf                  ← PDF institucional do laudo
GET  /laudos/{proto}/qr                   ← QR Code PNG → /public/laudos/{proto}

RBAC — TICKET-C (core, aprovado pelo arquiteto)
-----------------------------------------------
O laudo exige Responsável Técnico com CNS, mas quem opera a tela do laboratório
entra como `dispensador` (CNPJ da unidade). O dispensador PRODUZ EM NOME DO RT:
declara `cns_autor`, e o RT continua sendo o `autor_id` — o CNPJ nunca vira autor.
O direito de operar vem da POSSE do pedido de exame vinculado (custódia atual em
`pedido_exame_custodia`), não de identidade nominal. Sem coluna nova, sem migração.

  criar · assinar · liberar · encerrar · cancelar · GET · pdf · qr → + dispensador
  ciencia-paciente (paciente) e ciencia-prescritor (solicitante) → INALTERADOS:
  ciência é ato clínico de quem recebe o laudo, nunca de quem o produziu.
  Laudo standalone (sem pedido vinculado) → segue restrito a prescritor/admin.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator, model_validator

from app.auth.dependencies import require_role
from app.config import BASE_URL
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.outbox import registrar_outbox
from app.domain.pdf_laudo import gerar_pdf_laudo
from app.instance import get_instance_id_conn
from app.routers.pedidos_exame import (  # J.10-CORE — fonte única do predicado de posse
    dispensador_detem_pedido,
)
from app.domain.states_laudo import (
    ESTADOS_TERMINAIS_LAUDO,
    ESTADOS_TERMINAIS_ITEM_LAUDO,
    transicao_valida_laudo,
    transicao_valida_item_laudo,
    eh_terminal_laudo,
    eh_terminal_item_laudo,
)
from app.utils.helpers import (
    normalize_cns,
    normalize_cpf,
    normalize_nome,
    _assert_or_403,
    _normalizar_identidade_jwt,
)

router = APIRouter(prefix="/laudos", tags=["laudos"])

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO  = "00000000000"
_TIPOS_EMISSAO_VALIDOS = {"novo", "correcao"}
_CONCLUSOES_VALIDAS    = {"normal", "alterado", "indeterminado", "inconclusivo"}
_VALIDADE_PADRAO_DIAS  = 90


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class ItemLaudoIn(BaseModel):
    nome_exame:       str
    codigo_tuss:      Optional[str] = None
    resultado_resumo: Optional[str] = None
    conclusao:        Optional[str] = None
    valor_referencia: Optional[str] = None
    resultado_url:    Optional[str] = None

    @field_validator("nome_exame")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_exame não pode ser vazio")
        return v.strip().upper()

    @field_validator("conclusao")
    @classmethod
    def conclusao_valida(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _CONCLUSOES_VALIDAS:
            raise ValueError(
                f"conclusao inválida: '{v}'. Valores aceitos: {sorted(_CONCLUSOES_VALIDAS)}"
            )
        return v


class LaudoIn(BaseModel):
    cns_autor:        str             # CNS do responsável técnico (patologista, bioquímico, etc.)
    nome_autor:       Optional[str] = None
    cpf_paciente:     str
    nome_paciente:    str
    pedido_protocolo: Optional[str] = None   # protocolo do pedido de exame vinculado
    data_validade:    Optional[str] = None
    tipo_emissao:     str = "novo"
    origem_laudo_id:  Optional[int] = None
    itens:            List[ItemLaudoIn] = []

    @field_validator("tipo_emissao")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_EMISSAO_VALIDOS:
            raise ValueError(
                f"tipo_emissao inválido: '{v}'. Valores aceitos: {sorted(_TIPOS_EMISSAO_VALIDOS)}"
            )
        return v

    @model_validator(mode="after")
    def origem_obrigatoria(self) -> "LaudoIn":
        if self.tipo_emissao == "correcao" and self.origem_laudo_id is None:
            raise ValueError("origem_laudo_id é obrigatório quando tipo_emissao='correcao'")
        return self


class FisicaLaudoIn(BaseModel):
    cns_autor:    str
    nome_autor:   Optional[str] = None
    cpf_paciente: Optional[str] = None
    nome_paciente: str
    itens:        List[ItemLaudoIn] = []


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _calcular_hash(protocolo: str, cns_autor: str, cpf: str,
                   data_emissao: str, itens: list) -> str:
    doc = {
        "protocolo":      protocolo,
        "autor_cns":      cns_autor,
        "paciente_cpf":   cpf,
        "data_emissao":   data_emissao,
        "itens": [
            {
                "nome_exame":      item.nome_exame,
                "codigo_tuss":     item.codigo_tuss,
                "resultado_resumo": item.resultado_resumo,
                "conclusao":       item.conclusao,
            }
            for item in itens
        ],
        "versao_esquema": "1",
    }
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _localizar_ou_criar_autor(conn, cns: str, nome_hint: Optional[str], agora: str) -> int:
    row = conn.execute("SELECT id FROM prescritores WHERE cns = ?", (cns,)).fetchone()
    if row:
        return row["id"]
    nome = normalize_nome(nome_hint or "")
    if not nome:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Responsável técnico com CNS '{cns}' não encontrado. "
                "Envie 'nome_autor' para registrá-lo automaticamente."
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


def _get_laudo_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute("SELECT * FROM laudos WHERE protocolo = ?", (protocolo,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Laudo '{protocolo}' não encontrado.")
    return dict(row)


# ---------------------------------------------------------------------------
# TICKET-5C-BIS-B §7.0 — ownership local (3 resolvers de chave + 4 asserts).
# Reusa o Helper 1 global `_assert_or_403`. O papel `prescritor` cobre DOIS atores:
# o autor/responsável técnico (autor_id) e o prescritor solicitante (via pedido
# vinculado). São distintos — nunca um é fallback do outro (§4.5/§8.1).
# ---------------------------------------------------------------------------

def _cns_autor(conn, protocolo: str) -> str | None:
    row = conn.execute(
        "SELECT pr.cns FROM laudos l JOIN prescritores pr ON pr.id = l.autor_id "
        "WHERE l.protocolo = ?", (protocolo,),
    ).fetchone()
    return row["cns"] if row else None


def _cns_solicitante(conn, protocolo: str) -> str | None:
    row = conn.execute(
        "SELECT pr.cns FROM laudos l "
        "JOIN pedidos_exame pe ON pe.id = l.pedido_id "
        "JOIN prescritores pr ON pr.id = pe.prescritor_id "
        "WHERE l.protocolo = ?", (protocolo,),
    ).fetchone()
    return row["cns"] if row else None


def _cpf_paciente_laudo(conn, protocolo: str) -> str | None:
    row = conn.execute(
        "SELECT pa.cpf FROM laudos l JOIN pacientes pa ON pa.id = l.paciente_id "
        "WHERE l.protocolo = ?", (protocolo,),
    ).fetchone()
    return row["cpf"] if row else None


def _assert_autor_dono(conn, protocolo: str, ident: str) -> None:
    _assert_or_403(
        _cns_autor(conn, protocolo) == ident,
        codigo="nao_e_dono_do_laudo",
        mensagem="Este laudo foi emitido por outro responsável técnico.",
    )


def _assert_solicitante(conn, protocolo: str, ident: str) -> None:
    # ciencia-prescritor: só o prescritor solicitante (via pedido vinculado).
    # Sem pedido vinculado → cns is None → 403 (§8.1, sem fallback de autor).
    cns = _cns_solicitante(conn, protocolo)
    _assert_or_403(
        cns is not None and cns == ident,
        codigo="nao_e_dono_do_laudo",
        mensagem="Apenas o prescritor solicitante pode dar ciência clínica deste laudo.",
    )


def _assert_leitura_prescritor(conn, protocolo: str, ident: str) -> None:
    # Leitura (GET/pdf/qr/custodia): autor OU solicitante.
    donos = {_cns_autor(conn, protocolo), _cns_solicitante(conn, protocolo)} - {None}
    _assert_or_403(
        ident in donos,
        codigo="nao_e_dono_do_laudo",
        mensagem="Este laudo pertence a outro prescritor ou serviço.",
    )


def _assert_paciente_dono(conn, protocolo: str, ident: str) -> None:
    cpf = _cpf_paciente_laudo(conn, protocolo)
    # P2 (CODEX rodada 1): CPF sentinela '00000000000' nunca representa cidadão
    # real — nega mesmo que ident seja a própria sentinela (laudo físico/sem id).
    _assert_or_403(
        cpf != _CPF_NAO_IDENTIFICADO and cpf == ident,
        codigo="nao_e_dono_do_laudo",
        mensagem="Este laudo pertence a outro paciente.",
    )


# ---------------------------------------------------------------------------
# TICKET-C (core, aprovado pelo arquiteto) — ownership do DISPENSADOR.
#
# O laudo exige um Responsável Técnico com CNS (patologista, bioquímico). Mas
# quem opera a tela do laboratório entra como `dispensador`, identificado pelo
# CNPJ da unidade. A decisão: o dispensador PRODUZ EM NOME DO RT — declara o CNS
# e o RT continua sendo o `autor_id`. O CNPJ nunca vira autor.
#
# De onde vem o direito de operar, então? Da POSSE do pedido de exame: a unidade
# só mexe em laudo vinculado a um pedido sob sua custódia ATUAL. É dado que já
# existe (`pedido_exame_custodia`) — sem coluna nova, sem migração.
#
# A query é a mesma semântica de `pedidos_exame.py::_assert_dispensador_dono_pedido`
# (custódia nível-pedido, `item_id IS NULL`, a mais recente). Fica escrita aqui,
# e não importada, por decisão de arquitetura: ADR-002 opção C mantém as queries
# de ownership locais ao subdomínio (mesma razão pela qual os 3 resolvers acima
# são locais). Não é fonte única e não se pretende fonte única.
# ---------------------------------------------------------------------------

# J.10-CORE — a cópia local deste predicado morreu aqui. Ela lia "última linha"
# por conta própria; a posse agora se lê por `encerrada_em IS NULL`, e duas
# leituras do mesmo predicado em dois arquivos divergiriam em silêncio — o mesmo
# risco da dupla posse, um andar acima. Fonte única em `pedidos_exame.py`.
_dispensador_detem_pedido = dispensador_detem_pedido


def _assert_dispensador_dono_pedido(conn, pedido_id: int, ident_cnpj: str) -> None:
    """Usado na CRIAÇÃO: o laudo nasce vinculado a um pedido que é nosso."""
    _assert_or_403(
        _dispensador_detem_pedido(conn, pedido_id, ident_cnpj),
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Pedido de exame sob responsabilidade de outra unidade.",
    )


def _assert_dispensador_dono_laudo_via_pedido(conn, laudo: dict, ident_cnpj: str) -> None:
    """Usado nos demais endpoints: o direito é derivado do pedido vinculado.

    Laudo standalone (`pedido_id IS NULL`) → 403. Não é lacuna: laudo sem pedido
    não tem custódia de onde derivar posse, então segue restrito a
    prescritor/admin. Negar é a resposta correta, não um efeito colateral.
    """
    if not laudo.get("pedido_id"):
        _assert_or_403(
            False,
            codigo="laudo_sem_pedido_vinculado",
            mensagem="Laudo sem pedido vinculado: operação restrita ao prescritor/admin.",
        )
    _assert_or_403(
        _dispensador_detem_pedido(conn, laudo["pedido_id"], ident_cnpj),
        codigo="nao_e_dono_do_laudo",
        mensagem="Este laudo pertence a um pedido sob custódia de outra unidade.",
    )


def _get_itens_laudo(conn, laudo_id: int) -> list[dict]:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM laudo_itens WHERE laudo_id = ?", (laudo_id,)
        ).fetchall()
    ]


def _evento(conn, laudo_id: int, tipo: str, dados: dict, agora: str,
            protocolo: str | None = None,
            *, instance_id: str) -> None:
    """Insere evento no ledger de laudos. Nunca recebe UPDATE/DELETE.

    Ticket 4D.2: delega para ``registrar_evento_ledger`` e propaga
    ``instance_id`` para o outbox quando ``protocolo`` for fornecido —
    preserva correspondência forense entre ledger e outbox.

    ``instance_id`` é parâmetro keyword-only obrigatório — caller obtém
    via ``get_instance_id_conn(conn)`` uma vez por transação clínica.
    """
    registrar_evento_ledger(
        conn,
        objeto_tipo="laudo",
        objeto_id=laudo_id,
        tipo_evento=tipo,
        instance_id=instance_id,
        payload=dados,
    )
    if protocolo:
        registrar_outbox(
            conn, tipo, "laudo", protocolo, dados,
            instance_id=instance_id,
        )


# ---------------------------------------------------------------------------
# POST /laudos — emissão digital
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def criar_laudo(
    payload: LaudoIn,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Cria um laudo no estado 'em_producao'.

    Fluxo completo:
        em_producao → assinar → liberar → ciência → encerrar

    O autor é o responsável técnico (cns_autor) — inclusive quando quem opera é
    a unidade (dispensador), que produz EM NOME do RT declarado.
    Suporte a vinculação com pedido_exame via pedido_protocolo.
    """
    # TICKET-5C-BIS-B §7.1 (Padrão A) — CNS do autor declarado == JWT; admin
    # bypassa essa comparação nominal, mas NÃO as invariantes de domínio (§8.3).
    papel, ident = _normalizar_identidade_jwt(usuario)

    if not payload.itens:
        raise HTTPException(status_code=422, detail="O laudo deve conter ao menos um item.")

    cns      = normalize_cns(payload.cns_autor)
    if papel == "prescritor":
        _assert_or_403(
            ident == cns,
            codigo="autor_mismatch",
            mensagem="CNS do autor não coincide com o responsável técnico autenticado.",
        )
    elif papel == "dispensador":
        # TICKET-C — a unidade não tem CNS para comparar; declara o do RT. O que
        # a autoriza não é identidade nominal, é POSSE: o laudo tem que nascer
        # preso a um pedido sob sua custódia. Sem o vínculo não há de onde
        # derivar direito nenhum — por isso 422, e não um laudo órfão.
        if not payload.pedido_protocolo:
            raise HTTPException(
                status_code=422,
                detail=(
                    "A unidade deve vincular o laudo a um pedido de exame sob sua "
                    "custódia (pedido_protocolo)."
                ),
            )
    # admin: bypass (como hoje)
    cpf      = normalize_cpf(payload.cpf_paciente)
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora    = datetime.utcnow().isoformat()
    data_emissao  = date.today().isoformat()
    data_validade = (
        payload.data_validade
        or (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()
    )

    with get_tx() as conn:
        autor_id    = _localizar_ou_criar_autor(conn, cns, payload.nome_autor, agora)
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        pedido_id = None
        if payload.pedido_protocolo:
            # §8.4 (P1 CODEX) — vínculo não é só existência: o paciente do pedido
            # deve ser o do laudo. É o pedido que define o solicitante autorizado;
            # vínculo errado concederia leitura/ciência ao prescritor errado.
            row = conn.execute(
                "SELECT pe.id, pa.cpf FROM pedidos_exame pe "
                "JOIN pacientes pa ON pa.id = pe.paciente_id "
                "WHERE pe.protocolo = ?", (payload.pedido_protocolo,),
            ).fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pedido de exame '{payload.pedido_protocolo}' não encontrado.",
                )
            # TICKET-C — a POSSE é conferida antes do vínculo clínico. Ordem
            # deliberada (doutrina anti-leak #52): uma unidade alheia recebe 403
            # sem aprender de quem é o pedido. Prescritor/admin não passam por aqui.
            if papel == "dispensador":
                _assert_dispensador_dono_pedido(conn, row["id"], ident)

            _assert_or_403(
                row["cpf"] == cpf,
                codigo="vinculo_pedido_invalido",
                mensagem="O pedido de exame vinculado pertence a outro paciente.",
            )
            pedido_id = row["id"]

        if payload.origem_laudo_id is not None:
            # §8.3 — origem de correção deve pertencer ao MESMO autor do payload
            # (inclusive quando admin cria em nome de alguém).
            origem = conn.execute(
                "SELECT pr.cns FROM laudos l JOIN prescritores pr ON pr.id = l.autor_id "
                "WHERE l.id = ?", (payload.origem_laudo_id,),
            ).fetchone()
            if origem is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Laudo de origem id={payload.origem_laudo_id} não encontrado.",
                )
            _assert_or_403(
                origem["cns"] == cns,
                codigo="nao_e_dono_do_laudo",
                mensagem="O laudo de origem foi emitido por outro responsável técnico.",
            )

        cursor = conn.execute(
            """
            INSERT INTO laudos
              (protocolo, autor_id, paciente_id, pedido_id, status, tipo_emissao,
               origem_laudo_id, data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, ?, 'em_producao', ?, ?, ?, ?, ?)
            """,
            (protocolo, autor_id, paciente_id, pedido_id,
             payload.tipo_emissao, payload.origem_laudo_id,
             data_emissao, data_validade, agora),
        )
        laudo_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO laudo_itens
                  (laudo_id, nome_exame, codigo_tuss, resultado_resumo,
                   conclusao, valor_referencia, resultado_url, status_item, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'em_producao', ?)
                """,
                (laudo_id, item.nome_exame, item.codigo_tuss, item.resultado_resumo,
                 item.conclusao, item.valor_referencia, item.resultado_url, agora),
            )

        doc_hash = _calcular_hash(protocolo, cns, cpf, data_emissao, payload.itens)
        conn.execute(
            "UPDATE laudos SET assinatura_hash = ? WHERE id = ?",
            (doc_hash, laudo_id),
        )

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo_id, "laudo_criado", {
            "tipo_emissao":    payload.tipo_emissao,
            "origem_laudo_id": payload.origem_laudo_id,
            "pedido_id":       pedido_id,
            "itens_count":     len(payload.itens),
            # TICKET-C — o autor é o RT; QUEM operou é outra pergunta, e o ledger
            # responde as duas. Sem isto, um laudo produzido pela unidade seria
            # indistinguível de um digitado pelo próprio RT.
            "produzido_por":      papel,
            "produzido_por_cnpj": ident if papel == "dispensador" else None,
        }, agora, protocolo=protocolo, instance_id=instance_id)

        return {
            "id":            laudo_id,
            "protocolo":     protocolo,
            "status":        "em_producao",
            "tipo_emissao":  payload.tipo_emissao,
            "data_emissao":  data_emissao,
            "data_validade": data_validade,
            "itens_count":   len(payload.itens),
            "documento_hash": doc_hash,
        }


# ---------------------------------------------------------------------------
# POST /laudos/fisica — emissão exclusivamente física
# ---------------------------------------------------------------------------

@router.post("/fisica", status_code=201)
def criar_laudo_fisico(
    payload: FisicaLaudoIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """
    Registra laudo emitido exclusivamente em papel.

    Status: encerrado_fisico (objeto + todos os itens)
    Sem cadeia de custódia digital.
    Dois eventos no ledger: laudo_impresso + encerrado_localmente
    """
    # TICKET-5C-BIS-B §7.1 — mesma checagem de autor da emissão digital.
    papel, ident = _normalizar_identidade_jwt(usuario)

    if not payload.itens:
        raise HTTPException(status_code=422, detail="O laudo deve conter ao menos um item.")

    cns      = normalize_cns(payload.cns_autor)
    if papel != "admin":
        _assert_or_403(
            ident == cns,
            codigo="autor_mismatch",
            mensagem="CNS do autor não coincide com o responsável técnico autenticado.",
        )
    cpf      = normalize_cpf(payload.cpf_paciente) if payload.cpf_paciente else _CPF_NAO_IDENTIFICADO
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora    = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()

    with get_tx() as conn:
        autor_id    = _localizar_ou_criar_autor(conn, cns, payload.nome_autor, agora)
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO laudos
              (protocolo, autor_id, paciente_id, status, tipo_emissao,
               data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'encerrado_fisico', 'fisico', ?, NULL, ?)
            """,
            (protocolo, autor_id, paciente_id, data_emissao, agora),
        )
        laudo_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO laudo_itens
                  (laudo_id, nome_exame, codigo_tuss, resultado_resumo,
                   conclusao, valor_referencia, resultado_url, status_item, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'encerrado_fisico', ?)
                """,
                (laudo_id, item.nome_exame, item.codigo_tuss, item.resultado_resumo,
                 item.conclusao, item.valor_referencia, item.resultado_url, agora),
            )

        # Ticket 4D.2: 2 eventos do fluxo físico compartilham instance_id.
        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo_id, "laudo_impresso", {
            "tipo_emissao":      "fisico",
            "itens_count":       len(payload.itens),
            "cpf_identificado":  payload.cpf_paciente is not None,
        }, agora, instance_id=instance_id)
        _evento(conn, laudo_id, "encerrado_localmente", {
            "status_novo":          "encerrado_fisico",
            "motivo":               "emissao_exclusivamente_fisica",
            "sem_custodia_digital": True,
        }, agora, instance_id=instance_id)

        return {
            "protocolo":    protocolo,
            "status":       "encerrado_fisico",
            "tipo_emissao": "fisico",
            "data_emissao": data_emissao,
            "itens_count":  len(payload.itens),
        }


# ---------------------------------------------------------------------------
# GET /laudos/{protocolo} — consulta completa
# ---------------------------------------------------------------------------

@router.get("/{protocolo}")
def get_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    # §7.2 — leitura: prescritor (autor∨solicitante) · dispensador (via pedido
    # sob custódia, TICKET-C — é como a unidade acompanha a ciência do cidadão);
    # admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo  = _get_laudo_ou_404(conn, protocolo)
        if papel == "prescritor":
            _assert_leitura_prescritor(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)
        itens  = _get_itens_laudo(conn, laudo["id"])
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, dados_json, criado_em FROM laudo_eventos "
                "WHERE laudo_id = ? ORDER BY id ASC",
                (laudo["id"],),
            ).fetchall()
        ]
        return {**laudo, "itens": itens, "eventos": eventos}


# ---------------------------------------------------------------------------
# GET /laudos/{protocolo}/custodia — histórico de custódia
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/custodia")
def get_custodia_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    # §7.2 — matriz: prescritor (autor∨solicitante) · paciente; admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_leitura_prescritor(conn, protocolo, ident)
            elif papel == "paciente":
                _assert_paciente_dono(conn, protocolo, ident)
        registros = conn.execute(
            "SELECT de, para, transferido_em, dados_json FROM laudo_custodia "
            "WHERE laudo_id = ? ORDER BY id ASC",
            (laudo["id"],),
        ).fetchall()
        return {"protocolo": protocolo, "custodia": [dict(r) for r in registros]}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/assinar
# Transição: em_producao → assinado
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/assinar", status_code=200)
def assinar_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Responsável técnico declara assinatura do laudo.
    Transição: em_producao → assinado

    A assinatura continua sendo do RT (`autor_id` não muda). O dispensador
    registra o ato em nome dele, pela mesma posse que o autorizou a produzir.
    """
    agora = datetime.utcnow().isoformat()
    # §7.2 — autor (ou a unidade que detém o pedido, TICKET-C); admin bypassa.
    # 404 → 403 → 422.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel == "prescritor":
            _assert_autor_dono(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)

        if eh_terminal_laudo(laudo["status"]):
            raise HTTPException(status_code=422, detail=f"Laudo '{protocolo}' está em estado terminal.")

        if laudo["status"] != "em_producao":
            raise HTTPException(
                status_code=422,
                detail=f"Assinatura requer status 'em_producao'. Status atual: '{laudo['status']}'.",
            )

        # Transicionar itens em_producao → concluido
        itens = _get_itens_laudo(conn, laudo["id"])
        for item in itens:
            if item["status_item"] == "em_producao":
                conn.execute(
                    "UPDATE laudo_itens SET status_item = 'concluido' WHERE id = ?",
                    (item["id"],),
                )

        conn.execute(
            "UPDATE laudos SET status = 'assinado' WHERE id = ?",
            (laudo["id"],),
        )

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "laudo_assinado", {
            "status_anterior": "em_producao",
        }, agora, protocolo=laudo["protocolo"], instance_id=instance_id)

        return {"protocolo": protocolo, "status": "assinado"}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/liberar
# Transição: assinado → liberado
# Cria custódia: prestador → paciente
# ---------------------------------------------------------------------------

class LiberarIn(BaseModel):
    # TICKET-C — opcional porque o dispensador NÃO declara o próprio CNPJ: ele
    # vem do JWT (ver abaixo). Continua obrigatório para prescritor/admin, agora
    # com 422 nomeado em vez do erro genérico do Pydantic.
    cnpj_prestador: Optional[str] = None
    cpf_paciente:   Optional[str] = None   # para registrar custódia direcionada


@router.post("/{protocolo}/liberar", status_code=200)
def liberar_laudo(
    protocolo: str,
    payload: LiberarIn,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Libera o laudo para acesso do paciente e/ou prescritor solicitante.
    Transição: assinado → liberado
    Cria custódia: prestador → paciente
    """
    agora = datetime.utcnow().isoformat()
    # §7.2 — autor (ou a unidade que detém o pedido, TICKET-C); admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel == "prescritor":
            _assert_autor_dono(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)

        # TICKET-C — a custódia tem que registrar a unidade AUTENTICADA, não uma
        # que o corpo da requisição afirme ser. Para o dispensador o CNPJ vem do
        # JWT e o payload é ignorado: é a diferença entre posse provada e posse
        # declarada, e a cadeia de custódia (§3) não aceita a segunda.
        cnpj_prestador = ident if papel == "dispensador" else payload.cnpj_prestador
        if not cnpj_prestador:
            raise HTTPException(
                status_code=422,
                detail="cnpj_prestador é obrigatório para registrar a custódia do laudo.",
            )

        if laudo["status"] != "assinado":
            raise HTTPException(
                status_code=422,
                detail=f"Liberação requer status 'assinado'. Status atual: '{laudo['status']}'.",
            )

        conn.execute(
            "UPDATE laudos SET status = 'liberado' WHERE id = ?",
            (laudo["id"],),
        )

        conn.execute(
            """
            INSERT INTO laudo_custodia (laudo_id, item_id, de, para, transferido_em, dados_json)
            VALUES (?, NULL, ?, 'paciente', ?, ?)
            """,
            (
                laudo["id"],
                cnpj_prestador,
                agora,
                json.dumps({"cnpj_prestador": cnpj_prestador}, ensure_ascii=False),
            ),
        )

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "laudo_liberado", {
            "cnpj_prestador": cnpj_prestador,
            "liberado_por":   papel,
        }, agora, protocolo=laudo["protocolo"], instance_id=instance_id)

        return {"protocolo": protocolo, "status": "liberado"}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/ciencia-paciente
# Transição: liberado | ciencia_prescritor → ciencia_paciente | encerrado
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/ciencia-paciente", status_code=200)
def ciencia_paciente(
    protocolo: str,
    usuario=Depends(require_role("paciente", "admin")),
):
    """
    Paciente registra ciência do laudo.

    - liberado → ciencia_paciente (prescritor ainda não deu ciência)
    - ciencia_prescritor → encerrado (ambas as ciências registradas)
    """
    agora = datetime.utcnow().isoformat()
    # §7.3 — fecha o BUG ATIVO: valida que o paciente é o dono do laudo. admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel != "admin":
            _assert_paciente_dono(conn, protocolo, ident)

        if laudo["status"] not in ("liberado", "ciencia_prescritor"):
            raise HTTPException(
                status_code=422,
                detail=f"Ciência do paciente requer status 'liberado' ou 'ciencia_prescritor'. "
                       f"Status atual: '{laudo['status']}'.",
            )

        novo_status = "encerrado" if laudo["status"] == "ciencia_prescritor" else "ciencia_paciente"

        conn.execute(
            "UPDATE laudos SET status = ? WHERE id = ?",
            (novo_status, laudo["id"]),
        )

        # Ticket 4D.2: ciencia_paciente + laudo_encerrado (condicional)
        # compartilham instance_id na mesma transação clínica.
        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "ciencia_paciente", {
            "status_anterior": laudo["status"],
            "status_novo":     novo_status,
        }, agora, protocolo=protocolo, instance_id=instance_id)

        if novo_status == "encerrado":
            _evento(conn, laudo["id"], "laudo_encerrado", {
                "motivo": "ciencia_completa",
            }, agora, protocolo=protocolo, instance_id=instance_id)

        return {"protocolo": protocolo, "status": novo_status}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/abrir — ENG-014 (PR C), §3 do desenho
# A abertura pelo cidadão é ATO: escreve ledger e DERIVA a ciência.
# ---------------------------------------------------------------------------

def _iso(valor) -> str | None:
    """Normaliza o carimbo para ISO-8601 com `T`, venha de onde vier.

    O PostgreSQL devolve `datetime` e o SQLite devolve `str`; e o valor recém
    escrito é a string ISO que acabamos de gerar. Sem normalizar, a PRIMEIRA
    abertura respondia `...T17:52:13` e a segunda `... 17:52:13` — mesmo
    instante, formatos diferentes. Um cliente que comparasse os dois (para
    decidir se já abriu) concluiria que mudou. Foi o teste de idempotência que
    pegou.
    """
    if valor is None:
        return None
    return str(valor).replace(" ", "T")


@router.post("/{protocolo}/abrir", status_code=200)
def abrir_laudo(
    protocolo: str,
    usuario=Depends(require_role("paciente", "admin")),
):
    """O cidadão abriu o laudo — e abrir é dar ciência (martelo (a), 20/08).

    O EVENTO NOMEIA A ABERTURA, que é o fato que realmente aconteceu; a ciência
    é consequência DERIVADA, declarada como regra. O ledger fica honesto:
    "abriu em X → ciência derivada da abertura" — nunca uma "ciência"
    anunciando fato que não ocorreu (a lição do `pedido_agendado` fantasma).

    NUNCA em `GET`: ato escreve ledger por `POST` explícito. A tela chama uma
    vez, ao abrir o cartão.

    IDEMPOTENTE: a segunda abertura responde 200 e **não emite nada** — um
    fato, um evento (espírito R2). O carimbo `laudos.aberto_em` é a marca da
    primeira.

    MÁQUINA DE ESTADOS: mudança nenhuma. `liberado → ciencia_paciente` já é
    aresta válida e o endpoint de ciência já compõe as duas ciências — isto
    aqui é um CAMINHO NOVO para uma transição existente, no mesmo formato do
    martelo do J.7.

    Estados sem o que abrir (`em_producao`, `assinado`, `cancelado`,
    `encerrado_fisico`) → 422. Laudo standalone abre igual: a abertura é do
    cidadão sobre o documento, não depende do pedido.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        # 404 → 403 → 422 (anti-leak #52).
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel != "admin":
            _assert_paciente_dono(conn, protocolo, ident)

        _ABRIVEIS = ("liberado", "ciencia_prescritor", "ciencia_paciente", "encerrado")
        if laudo["status"] not in _ABRIVEIS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Laudo em '{laudo['status']}' não está disponível para leitura. "
                    "A abertura vale a partir da liberação."
                ),
            )

        # Já aberto: devolve o carimbo e não escreve. A tela pode chamar sem
        # medo — mas o ledger não ganha um evento por reabertura de cartão.
        if laudo.get("aberto_em"):
            return {
                "protocolo":        protocolo,
                "status":           laudo["status"],
                "aberto_em":        _iso(laudo["aberto_em"]),
                "primeira_abertura": False,
                "ciencia_derivada": False,
            }

        conn.execute("UPDATE laudos SET aberto_em = ? WHERE id = ?", (agora, laudo["id"]))

        # A ciência só nasce se há ciência a dar. Em `ciencia_paciente` ou
        # `encerrado` o cidadão já a deu — a abertura é só o fato da leitura.
        deriva = laudo["status"] in ("liberado", "ciencia_prescritor")
        novo_status = laudo["status"]

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "laudo_aberto_paciente", {
            "aberto_em":         agora,
            "status_na_abertura": laudo["status"],
            "derivada_ciencia":  deriva,
        }, agora, protocolo=protocolo, instance_id=instance_id)

        if deriva:
            # MESMA lógica do `POST /ciencia-paciente` — composição, não
            # duplicação: `ciencia_prescritor` + esta ciência fecham o laudo.
            novo_status = "encerrado" if laudo["status"] == "ciencia_prescritor" else "ciencia_paciente"
            conn.execute("UPDATE laudos SET status = ? WHERE id = ?", (novo_status, laudo["id"]))
            _evento(conn, laudo["id"], "ciencia_paciente", {
                "status_anterior": laudo["status"],
                "status_novo":     novo_status,
                "origem":          "abertura",   # a ciência foi DERIVADA, e o ledger diz de onde
            }, agora, protocolo=protocolo, instance_id=instance_id)
            if novo_status == "encerrado":
                _evento(conn, laudo["id"], "laudo_encerrado", {
                    "motivo": "ciencia_completa",
                }, agora, protocolo=protocolo, instance_id=instance_id)

        return {
            "protocolo":         protocolo,
            "status":            novo_status,
            "aberto_em":         _iso(agora),
            "primeira_abertura": True,
            "ciencia_derivada":  deriva,
        }


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/ciencia-prescritor
# Transição: liberado | ciencia_paciente → ciencia_prescritor | encerrado
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/ciencia-prescritor", status_code=200)
def ciencia_prescritor(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """
    Prescritor solicitante registra ciência clínica do laudo.

    - liberado → ciencia_prescritor (paciente ainda não deu ciência)
    - ciencia_paciente → encerrado (ambas as ciências registradas)
    """
    agora = datetime.utcnow().isoformat()
    # §7.2 — só o prescritor SOLICITANTE (via pedido vinculado); sem pedido → 403
    # (§8.1, sem fallback de autor). admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel != "admin":
            _assert_solicitante(conn, protocolo, ident)

        if laudo["status"] not in ("liberado", "ciencia_paciente"):
            raise HTTPException(
                status_code=422,
                detail=f"Ciência do prescritor requer status 'liberado' ou 'ciencia_paciente'. "
                       f"Status atual: '{laudo['status']}'.",
            )

        novo_status = "encerrado" if laudo["status"] == "ciencia_paciente" else "ciencia_prescritor"

        conn.execute(
            "UPDATE laudos SET status = ? WHERE id = ?",
            (novo_status, laudo["id"]),
        )

        # Ticket 4D.2: ciencia_prescritor + laudo_encerrado (condicional)
        # compartilham instance_id na mesma transação clínica.
        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "ciencia_prescritor", {
            "status_anterior": laudo["status"],
            "status_novo":     novo_status,
        }, agora, protocolo=protocolo, instance_id=instance_id)

        if novo_status == "encerrado":
            _evento(conn, laudo["id"], "laudo_encerrado", {
                "motivo": "ciencia_completa",
            }, agora, protocolo=protocolo, instance_id=instance_id)

        return {"protocolo": protocolo, "status": novo_status}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/encerrar
# Encerramento direto (ex: apenas uma ciência é necessária — configurável)
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/encerrar", status_code=200)
def encerrar_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Encerramento formal do laudo a partir de 'liberado', 'ciencia_paciente' ou 'ciencia_prescritor'.
    Usado quando apenas uma ciência é suficiente (configuração institucional).
    """
    agora = datetime.utcnow().isoformat()
    # §8.2 — encerramento é fechamento operacional do PRODUTOR: o autor ou a
    # unidade que produziu em nome dele (TICKET-C); admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel == "prescritor":
            _assert_autor_dono(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)

        if laudo["status"] not in ("liberado", "ciencia_paciente", "ciencia_prescritor"):
            raise HTTPException(
                status_code=422,
                detail=f"Encerramento requer status 'liberado', 'ciencia_paciente' ou "
                       f"'ciencia_prescritor'. Status atual: '{laudo['status']}'.",
            )

        conn.execute(
            "UPDATE laudos SET status = 'encerrado' WHERE id = ?",
            (laudo["id"],),
        )

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "laudo_encerrado", {
            "status_anterior": laudo["status"],
            "motivo":          "encerramento_direto",
        }, agora, protocolo=protocolo, instance_id=instance_id)

        return {"protocolo": protocolo, "status": "encerrado"}


# ---------------------------------------------------------------------------
# POST /laudos/{protocolo}/cancelar
# ---------------------------------------------------------------------------

class CancelarLaudoIn(BaseModel):
    motivo: Optional[str] = None


@router.post("/{protocolo}/cancelar", status_code=200)
def cancelar_laudo(
    protocolo: str,
    payload: CancelarLaudoIn,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Cancela um laudo que ainda não foi liberado (em_producao ou assinado).
    """
    agora = datetime.utcnow().isoformat()
    # §7.2 — autor (ou a unidade que detém o pedido, TICKET-C); admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)

        if papel == "prescritor":
            _assert_autor_dono(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)

        if eh_terminal_laudo(laudo["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Laudo '{protocolo}' já está em estado terminal ({laudo['status']}).",
            )

        if laudo["status"] == "liberado":
            raise HTTPException(
                status_code=422,
                detail="Laudo já liberado não pode ser cancelado. Use /correcao para emitir laudo corrigido.",
            )

        itens = _get_itens_laudo(conn, laudo["id"])
        for item in itens:
            if not eh_terminal_item_laudo(item["status_item"]):
                conn.execute(
                    "UPDATE laudo_itens SET status_item = 'cancelado' WHERE id = ?",
                    (item["id"],),
                )

        conn.execute(
            "UPDATE laudos SET status = 'cancelado' WHERE id = ?",
            (laudo["id"],),
        )

        instance_id = get_instance_id_conn(conn)
        _evento(conn, laudo["id"], "laudo_cancelado", {
            "status_anterior": laudo["status"],
            "motivo":          payload.motivo,
        }, agora, protocolo=protocolo, instance_id=instance_id)

        return {"protocolo": protocolo, "status": "cancelado"}


# ---------------------------------------------------------------------------
# GET /laudos/{protocolo}/pdf — PDF institucional do laudo (Ticket 21)
# ---------------------------------------------------------------------------

@router.get(
    "/{protocolo}/pdf",
    summary="PDF institucional do laudo clínico",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF do laudo"},
        404: {"description": "Protocolo não encontrado"},
    },
)
def pdf_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente", "dispensador")),
):
    """
    Gera e retorna o PDF institucional do laudo, com todos os resultados,
    conclusões, identificação do documento e área de assinatura.

    O PDF inclui:
    - Responsável técnico (autor), paciente, pedido vinculado (se houver)
    - Itens: nome do exame, conclusão (com cor por severidade), resultado resumido,
      valor de referência
    - Hash SHA-256 do documento canônico
    - Área de assinatura física do responsável técnico
    """
    # §7.2 — matriz: prescritor (autor∨solicitante) · paciente · dispensador
    # (via pedido sob custódia, TICKET-C — a unidade pré-visualiza o que
    # produziu); admin bypassa.
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_leitura_prescritor(conn, protocolo, ident)
            elif papel == "paciente":
                _assert_paciente_dono(conn, protocolo, ident)
            elif papel == "dispensador":
                _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)
        itens = _get_itens_laudo(conn, laudo["id"])

        # Autor
        autor_row = conn.execute(
            "SELECT nome, cns FROM prescritores WHERE id = ?", (laudo["autor_id"],)
        ).fetchone()
        nome_autor = autor_row["nome"] if autor_row else "—"
        cns_autor  = autor_row["cns"]  if autor_row else "—"

        # Paciente
        pac_row = conn.execute(
            "SELECT nome, cpf FROM pacientes WHERE id = ?", (laudo["paciente_id"],)
        ).fetchone()
        nome_paciente = pac_row["nome"] if pac_row else "—"
        cpf_paciente  = pac_row["cpf"]  if pac_row else "00000000000"

        # Pedido vinculado (se houver)
        pedido_protocolo = None
        if laudo.get("pedido_id"):
            ped_row = conn.execute(
                "SELECT protocolo FROM pedidos_exame WHERE id = ?", (laudo["pedido_id"],)
            ).fetchone()
            if ped_row:
                pedido_protocolo = ped_row["protocolo"]

    pdf_bytes = gerar_pdf_laudo(
        protocolo        = protocolo,
        status           = laudo["status"],
        tipo_emissao     = laudo["tipo_emissao"],
        assinatura_hash  = laudo.get("assinatura_hash"),
        data_emissao     = laudo["data_emissao"],
        data_validade    = laudo.get("data_validade"),
        nome_autor       = nome_autor,
        cns_autor        = cns_autor,
        nome_paciente    = nome_paciente,
        cpf_paciente     = cpf_paciente,
        pedido_protocolo = pedido_protocolo,
        itens            = [dict(i) for i in itens],
    )

    return Response(
        content      = pdf_bytes,
        media_type   = "application/pdf",
        headers      = {
            "Content-Disposition": f'inline; filename="laudo-{protocolo[:8]}.pdf"'
        },
    )


# ---------------------------------------------------------------------------
# GET /laudos/{protocolo}/qr — QR Code PNG (Ticket 21)
# ---------------------------------------------------------------------------

@router.get(
    "/{protocolo}/qr",
    summary="QR Code do protocolo de laudo",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "Imagem PNG do QR Code"},
        404: {"description": "Protocolo não encontrado"},
    },
)
def qr_laudo(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente", "dispensador")),
):
    """
    Gera e retorna um QR Code PNG para o protocolo do laudo.

    O QR Code codifica a URL pública do laudo:
    `{BASE_URL}/public/laudos/{protocolo}`

    - Imagem gerada inteiramente em memória (sem arquivo em disco).
    - 404 se o protocolo não existir no banco.
    """
    # §7.2/§5.1 — QR precisa de query (Padrão B): 404 → 403 (leitura prescritor∨
    # paciente dono ∨ unidade que detém o pedido; admin bypassa).
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        laudo = _get_laudo_ou_404(conn, protocolo)
        if papel != "admin":
            if papel == "prescritor":
                _assert_leitura_prescritor(conn, protocolo, ident)
            elif papel == "paciente":
                _assert_paciente_dono(conn, protocolo, ident)
            elif papel == "dispensador":
                _assert_dispensador_dono_laudo_via_pedido(conn, laudo, ident)

    url = f"{BASE_URL}/public/laudos/{protocolo}"
    qr  = qrcode.QRCode(
        version          = 1,
        error_correction = qrcode.constants.ERROR_CORRECT_M,
        box_size         = 10,
        border           = 4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.read(), media_type="image/png")
