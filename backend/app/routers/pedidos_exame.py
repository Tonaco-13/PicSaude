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

from fastapi import APIRouter, Body, Depends, HTTPException
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
from app.domain.states_laudo import ESTADOS_TERMINAIS_LAUDO
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
            # J.10-CORE: pelo choke-point. Aqui não há posse anterior a fechar
            # (o pedido acaba de nascer), mas passar por fora seria abrir a
            # exceção pela qual a próxima escrita passa também.
            transferir_posse_exame(
                conn, pedido_id, None,
                "prescritor", cns,
                DETENTOR_PACIENTE, cpf,
                DETENTOR_PACIENTE,          # coluna `para`: o PAPEL, para o cidadão
                "entrega_carteira_digital", agora,
                instance_id=instance_id,
                extra_payload={"via": "emissao_direta"},
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


# Valor que `pedido_exame_custodia.para` guarda quando quem detém é o cidadão.
# A coluna guarda o PAPEL para o paciente ('paciente') e o CNPJ para o
# prestador — o CPF fica só em `dados_json.para_id`. Comparar o detentor com o
# CPF do JWT nunca casaria; é a lição de custo baixo que o gate de navegador
# cobrou antes do merge.
DETENTOR_PACIENTE = "paciente"


def posse_do_cidadao(detentor: Optional[str]) -> bool:
    """O pedido está com o cidadão? Fonte única do predicado (TICKET-J.7).

    `None` = nenhuma linha de custódia de nível-pedido: o pedido nunca saiu de
    onde nasceu (emissão sem `enviar_ao_paciente` não grava a linha).
    """
    return detentor in (None, DETENTOR_PACIENTE)


def detentor_atual_pedido(conn, pedido_id: int) -> Optional[str]:
    """Quem detém a posse do pedido AGORA — `None` se nunca saiu do cidadão.

    TICKET-J.7 (`core`): a custódia passa a ser a fonte da verdade da posse, no
    lugar do status. Antes, "quem está com o pedido" era lido do
    `pedidos_exame.status` (`emitido` = cidadão, `agendado` = laboratório) — um
    proxy que só funcionava porque transferir mudava o estado. Com o martelo do
    §11a, transferir não mexe em estado nenhum: um pedido `emitido` tanto pode
    estar na mão do cidadão quanto na bancada do laboratório, e a única coisa
    que sabe a diferença é esta cadeia.

    J.10-CORE: devolve o `para` da custódia ATIVA de nível-pedido
    (`item_id IS NULL AND encerrada_em IS NULL`). Era "a última linha"
    (`ORDER BY id DESC LIMIT 1`) — leitura derivada que o formato de ledger
    obrigava e que nenhum índice podia garantir. Agora a posse é um fato
    explícito no banco, e o índice único parcial prova que só existe uma.

    O `ORDER BY id DESC LIMIT 1` fica como cinto e suspensório: com o índice
    instalado a linha é única por construção, mas a função não depende disso
    para responder — se um banco anterior à migração for lido por engano, ela
    devolve a mais recente em vez de uma qualquer.

    Para o cidadão, esse valor é o PAPEL (`'paciente'`), não o CPF; use
    `posse_do_cidadao()` para interpretá-lo.
    """
    row = conn.execute(
        "SELECT para FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id IS NULL AND encerrada_em IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (pedido_id,),
    ).fetchone()
    return row["para"] if row else None


def dispensador_detem_pedido(conn, pedido_id: int, ident_cnpj: str) -> bool:
    """Este CNPJ detém a posse do pedido inteiro AGORA?

    Fonte ÚNICA do predicado (J.10-CORE). Antes existiam duas cópias — aqui e
    em `laudos.py::_dispensador_detem_pedido` —, cada uma com a sua leitura de
    "última linha". Duas cópias de um predicado de posse é o mesmo risco que a
    dupla posse: divergem em silêncio e cada tela passa a acreditar numa
    verdade diferente. `laudos.py` importa esta.

    NÃO é "qualquer custódia histórica" (correção do P1(b) da CODEX rodada 1):
    quem já foi custodiante e perdeu a posse não continua operando.

    Guard de 14 dígitos, defensivo: ident não-CNPJ nunca casa por acidente — e
    a custódia do cidadão guarda o PAPEL (`'paciente'`), não o CPF.
    Comparação direta (opção A, §8.4): a escrita já normaliza o CNPJ.
    """
    if len(ident_cnpj) != 14:
        return False
    return detentor_atual_pedido(conn, pedido_id) == ident_cnpj


def _assert_dispensador_dono_pedido(conn, pedido_id: int, ident_cnpj: str) -> None:
    _assert_or_403(
        dispensador_detem_pedido(conn, pedido_id, ident_cnpj),
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Pedido de exame sob responsabilidade de outro prestador.",
    )


# ---------------------------------------------------------------------------
# Posse por ITEM (J.10) — transferência parcial e devolução granular
# ---------------------------------------------------------------------------

def detentor_atual_item(conn, pedido_id: int, item_id: int) -> Optional[str]:
    """Quem detém a posse DESTE item agora (J.10, nível-item).

    Linha de item ATIVA (`item_id = X AND encerrada_em IS NULL`) vence; sem
    linha de item, o item é coberto pela posse de NÍVEL-PEDIDO
    (`detentor_atual_pedido`) — o formato de antes da primeira transferência
    parcial, em que a custódia do pedido inteiro responde por todos os itens.

    A linha de item vence DE PROPÓSITO mesmo que exista linha de pedido ativa:
    posse cross-granularidade viva não deve existir (§3.3 do DESENHO-J10 — a
    explosão fecha a nível-pedido antes de abrir as de item), mas se um dia
    existir, a resposta mais específica é a menos errada.
    """
    row = conn.execute(
        "SELECT para FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id = ? AND encerrada_em IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (pedido_id, item_id),
    ).fetchone()
    if row:
        return row["para"]
    return detentor_atual_pedido(conn, pedido_id)


def dispensador_detem_item(conn, pedido_id: int, item_id: int, ident_cnpj: str) -> bool:
    """Este CNPJ detém a posse DESTE item agora? (J.10)

    Espelho nível-item de `dispensador_detem_pedido`: vale pela linha de item
    ativa OU pela posse de pedido inteiro que cobre o item. É a guarda dos
    gestos operacionais por item (coletar/bancada/resultado/devolver) — depois
    de uma transferência parcial, a unidade só opera o que efetivamente detém.
    """
    if len(ident_cnpj) != 14:
        return False
    return detentor_atual_item(conn, pedido_id, item_id) == ident_cnpj


def _assert_dispensador_dono_item(conn, pedido_id: int, item_id: int, ident_cnpj: str) -> None:
    _assert_or_403(
        dispensador_detem_item(conn, pedido_id, item_id, ident_cnpj),
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Item de exame sob responsabilidade de outra unidade.",
    )


def dispensador_tem_algo_no_pedido(conn, pedido_id: int, ident_cnpj: str) -> bool:
    """Este CNPJ detém ALGUMA COISA deste pedido — o inteiro ou um item? (J.10)

    Guarda GROSSA, para a ordem anti-leak (#52). Ela separa **parte** de
    **estranho**, que é uma distinção real e não uma repetição da guarda fina:

      · estranho (não detém nada do pedido) → 403 aqui, e não aprende NADA:
        nem que o pedido está terminal, nem se aquele id de item existe;
      · parte (detém o pedido ou algum item) → passa, e daí em diante recebe
        respostas honestas — inclusive o 404 de um id de item que não existe,
        que para ela é informação legítima: ela já enxerga os próprios itens.

    A guarda FINA (`_assert_dispensador_dono_item`) continua depois, e é ela
    que barra a parte que tenta operar o item de outra unidade.

    Convenção da casa, em todos os módulos: **403 de posse precede 422 de
    estado**. Quem não tem vínculo não recebe informação de estado por via
    nenhuma — nem pela mensagem, nem pelo código.
    """
    if len(ident_cnpj) != 14:
        return False
    if detentor_atual_pedido(conn, pedido_id) == ident_cnpj:
        return True
    return conn.execute(
        "SELECT 1 FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id IS NOT NULL "
        "  AND encerrada_em IS NULL AND para = ? LIMIT 1",
        (pedido_id, ident_cnpj),
    ).fetchone() is not None


def _assert_dispensador_algo_no_pedido(conn, pedido_id: int, ident_cnpj: str) -> None:
    _assert_or_403(
        dispensador_tem_algo_no_pedido(conn, pedido_id, ident_cnpj),
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Pedido de exame sob responsabilidade de outro prestador.",
    )


def pedido_em_modo_item(conn, pedido_id: int) -> bool:
    """O pedido já opera com custódia por item? (J.10 §3.3)

    True depois da primeira explosão de granularidade (transferência parcial
    ou devolução de item sob posse nível-pedido). Uma vez explodido, o pedido
    NÃO volta a nível-pedido: a posse viva passa a ser uma linha por item, e é
    a constraint por `(pedido_id, item_id)` que responde sozinha por ele.
    """
    return conn.execute(
        "SELECT 1 FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id IS NOT NULL AND encerrada_em IS NULL "
        "LIMIT 1",
        (pedido_id,),
    ).fetchone() is not None


def _dissolver_posse_de_pedido_em_itens(conn, pedido_id: int, agora: str) -> None:
    """Fecha a custódia ATIVA de nível-pedido — a posse passa a viver por item.

    J.10 §3.3: transferência parcial nunca deixa as duas granularidades vivas.
    Fechar a nível-pedido e abrir uma linha de item para cada item ativo é o
    que impede a dupla posse CROSS-granularidade — a que o índice único não
    pega, porque as chaves diferem (`item_id` NULL vs id). Quem abre as linhas
    de item é o caminho, logo em seguida, pelo choke-point (com evento); este
    fechamento é a metade que não tem o que abrir — o mesmo papel do bloco de
    reconciliação de `custodia.py::devolver_item` na receita.
    """
    _fechar_custodia_exame_ativa(conn, pedido_id, None, agora)


# ---------------------------------------------------------------------------
# Choke-point de posse do exame (J.10-CORE) — espelho do COER-2 na receita
# ---------------------------------------------------------------------------

# Rótulo CANÔNICO por caminho. Texto livre do usuário vai em `extra_payload` e
# nunca sobrescreve o motivo — mesma disciplina do `custodia.py` (§3 do CLAUDE.md).
MOTIVOS_CUSTODIA_EXAME = frozenset({
    "entrega_carteira_digital",   # emissão com `enviar_ao_paciente`
    "agendamento_prestador",      # POST /pedidos-exame/{p}/agendar
    "transferencia_laboratorio",  # ato do cidadão (J.7) — pedido inteiro, nível-pedido
    "transferencia_parcial",      # J.10 — cidadão entrega SÓ alguns itens ao CNPJ
    "devolucao_nao_realizavel",   # J.10 — laboratório devolve item que não performa
})


def _fechar_custodia_exame_ativa(conn, pedido_id: int, item_id: Optional[int],
                                 agora: str) -> None:
    """Fecha a posse ativa desta granularidade, se houver. Idempotente."""
    if item_id is None:
        conn.execute(
            "UPDATE pedido_exame_custodia SET encerrada_em = ? "
            "WHERE pedido_id = ? AND item_id IS NULL AND encerrada_em IS NULL",
            (agora, pedido_id),
        )
    else:
        conn.execute(
            "UPDATE pedido_exame_custodia SET encerrada_em = ? "
            "WHERE pedido_id = ? AND item_id = ? AND encerrada_em IS NULL",
            (agora, pedido_id, item_id),
        )


def transferir_posse_exame(
    conn, pedido_id: int, item_id: Optional[int],
    de: str, de_id: Optional[str],
    para: str, para_id: Optional[str],
    detentor: str,
    motivo: str, agora: str,
    *, instance_id: str,
    extra_payload: Optional[dict] = None,
) -> None:
    """Choke-point de transição de posse do PEDIDO DE EXAME (J.10-CORE).

    Ponto de passagem ÚNICO e obrigatório para toda mudança de detentor em
    `pedido_exame_custodia`. Faz, na MESMA transação e nesta ordem:

      1. Fecha a posse ativa anterior desta granularidade (qualquer detentor);
      2. Abre a nova no nome de `para`;
      3. Emite `custodia_transferida` no ledger.

    Por que existe: antes, cada caminho de produto dava o seu `INSERT` e a posse
    era "a última linha". Enquanto ninguém fechava nada, não havia como um
    índice único provar que a posse é exclusiva — o R2 na camada de custódia
    ficava por conta da convenção. Roteando tudo por aqui, "fechou a anterior"
    deixa de ser fé e vira invariante, e a constraint
    `uq_custodia_exame_ativa_*` prova que cada caminho fechou.

    POR QUE `detentor` É PARÂMETRO SEPARADO DE `para`/`para_id`
    -----------------------------------------------------------
    A coluna `pedido_exame_custodia.para` é assimétrica por herança: guarda o
    **papel** quando quem detém é o cidadão (`'paciente'`) e o **CNPJ** quando é
    o prestador. Já o ledger quer o par semântico (`para='prestador_exame'` +
    `para_id=<cnpj>`). Um único argumento não serve aos dois — e conflatá-los é
    exatamente o bug que o gate de navegador pegou no J.7 (o guard comparava o
    detentor com o CPF do JWT e recusava o dono legítimo com 409).

    Então: `detentor` é o valor da COLUNA — a chave por onde
    `detentor_atual_pedido` responde "quem detém agora" —, e `para`/`para_id`
    são o par do ledger. Explícito de propósito: a assimetria é real e caro
    esquecê-la; escondê-la atrás de uma regra implícita ("papel se cidadão,
    senão id") só adiaria a próxima vez.

    Granularidade: opera SÓ no nível de `item_id` recebido. A reconciliação
    CROSS-granularidade (nível-pedido obsoleto × nível-item ativo) é
    responsabilidade do caminho que a criar — hoje nenhum cria, porque só
    existe transferência de pedido inteiro; o J.10 (`module`) a introduz.
    """
    if motivo not in MOTIVOS_CUSTODIA_EXAME:
        raise ValueError(
            f"motivo de custódia '{motivo}' não é canônico. "
            f"Conhecidos: {sorted(MOTIVOS_CUSTODIA_EXAME)}"
        )

    _fechar_custodia_exame_ativa(conn, pedido_id, item_id, agora)

    dados: dict = {
        "de": de, "de_id": de_id,
        "para": para, "para_id": para_id,
        "nivel": "item" if item_id is not None else "pedido",
        "motivo": motivo,
    }
    if item_id is not None:
        # J.10: sem o id no payload, eventos de item são indistinguíveis no
        # ledger (o espelho da receita, `custodia.py::transferir_posse`, o
        # carrega). Aditivo — payloads de nível-pedido seguem iguais.
        dados["item_id"] = item_id
    if extra_payload:
        # `motivo` canônico por último: detalhe livre nunca o sobrescreve.
        dados = {**extra_payload, **dados}

    conn.execute(
        """
        INSERT INTO pedido_exame_custodia
          (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
        VALUES (?, ?, ?, ?, ?, NULL, ?)
        """,
        (pedido_id, item_id, de, detentor, agora,
         json.dumps(dados, ensure_ascii=False)),
    )

    registrar_evento_ledger(
        conn,
        objeto_tipo="pedido_exame",
        objeto_id=pedido_id,
        tipo_evento="custodia_transferida",
        instance_id=instance_id,
        payload=dados,
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
        itens  = _get_itens(conn, pedido["id"])
        if papel == "dispensador":
            # J.10 — anti-vazamento entre prestadores (AC vi, §3.5 do desenho):
            # quem detém o pedido inteiro vê tudo (retrocompat); quem detém só
            # parte vê APENAS os itens sob a sua custódia; quem não detém nada
            # segue levando 403, como sempre.
            if not dispensador_detem_pedido(conn, pedido["id"], ident):
                itens = [
                    i for i in itens
                    if dispensador_detem_item(conn, pedido["id"], i["id"], ident)
                ]
                _assert_or_403(
                    bool(itens),
                    codigo="nao_e_dono_do_pedido_exame",
                    mensagem="Pedido de exame sob responsabilidade de outro prestador.",
                )
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, dados_json, criado_em FROM pedido_exame_eventos "
                "WHERE pedido_id = ? ORDER BY id ASC",
                (pedido["id"],),
            ).fetchall()
        ]

        # TICKET-I.1 — o pedido guarda `paciente_id`, não a identidade. A tela do
        # laboratório sempre esperou os campos resolvidos (`renderizarPedido` já
        # os procurava desde antes), e sem eles mostrava "Paciente: —" e não
        # tinha como preencher o laudo. Sem escopo novo: quem chega aqui já
        # passou pelo ownership acima e já enxerga itens e eventos.
        pac = conn.execute(
            "SELECT nome, cpf FROM pacientes WHERE id = ?", (pedido["paciente_id"],)
        ).fetchone() if pedido.get("paciente_id") else None

        # Laudo VIGENTE do pedido (não-terminal), se houver. É o que permite à
        # tela travar "Produzir laudo" mesmo depois de um reload — antes o
        # vínculo só vivia na sessão JS, e recarregar a página abria caminho
        # para um segundo laudo do mesmo pedido.
        _terminais = tuple(sorted(ESTADOS_TERMINAIS_LAUDO))
        laudo = conn.execute(
            "SELECT protocolo, status FROM laudos "
            f"WHERE pedido_id = ? AND status NOT IN ({','.join('?' * len(_terminais))}) "
            "ORDER BY id DESC LIMIT 1",
            (pedido["id"], *_terminais),
        ).fetchone()

        # ENG-019 (PR 1) — cobertura por item: este item JÁ está num laudo?
        #
        # `laudo_protocolo`, acima, reporta o laudo VIGENTE (não-terminal) do
        # pedido. Não serve para saber se um ITEM pode ainda ser laudado: quando
        # o laudo chega a `encerrado` — as duas ciências —, aquele campo volta a
        # NULL, e o item pode continuar em `resultado_disponivel`, porque a
        # ciência do PEDIDO é outro gesto. A tela precisa da cobertura, não da
        # vigência.
        #
        # Antes isto não fazia falta: o gatilho "Produzir laudo" media itens em
        # `em_analise`, e laudar TIRA o item de lá — o botão sumia por efeito
        # colateral. Ao passar a aceitar `resultado_disponivel` (percurso E2, que
        # nunca REPOUSA na bancada), o efeito colateral acaba e o motivo tem de
        # ser dito: é este campo.
        #
        # Só leitura, derivado do elo `laudo_itens.pedido_item_id` — nenhum
        # estado, evento ou custódia é tocado. Laudo `cancelado` não cobre nada
        # (nenhum endpoint o produz hoje; a exclusão é para não travar o item se
        # um dia produzir).
        laudados = {
            r["pedido_item_id"] for r in conn.execute(
                "SELECT li.pedido_item_id FROM laudo_itens li "
                " JOIN laudos l ON l.id = li.laudo_id "
                " WHERE l.pedido_id = ? AND li.pedido_item_id IS NOT NULL "
                "   AND l.status != 'cancelado'",
                (pedido["id"],),
            ).fetchall()
        }
        itens = [{**i, "laudado": i["id"] in laudados} for i in itens]

        return {
            **pedido,
            "paciente_nome":   pac["nome"] if pac else None,
            "paciente_cpf":    pac["cpf"] if pac else None,
            "laudo_protocolo": laudo["protocolo"] if laudo else None,
            "laudo_status":    laudo["status"] if laudo else None,
            "itens":           itens,
            "eventos":         eventos,
        }


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

        instance_id = get_instance_id_conn(conn)
        # J.10-CORE: pelo choke-point — fecha a posse do cidadão e abre a do
        # prestador. Antes o `INSERT` cru deixava as duas linhas vivas, e a
        # posse era "a última"; agora só uma fica ativa, e o índice prova.
        transferir_posse_exame(
            conn, pedido["id"], None,
            DETENTOR_PACIENTE, None,
            "prestador_exame", cnpj_prestador_norm,
            cnpj_prestador_norm,        # coluna `para`: o CNPJ, para o prestador
            "agendamento_prestador", agora,
            instance_id=instance_id,
            extra_payload={
                "nome_prestador":   payload.nome_prestador,
                "data_agendamento": payload.data_agendamento,
            },
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

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
# POST /pedidos-exame/{protocolo}/transferir-laboratorio — ato do CIDADÃO
# ---------------------------------------------------------------------------
# Espelho exato de POST /paciente/prescricoes/{proto}/transferir-farmacia
# (auth.py:202): o mesmo gesto da receita — o cidadão escolhe o estabelecimento,
# entrega a posse, e o objeto cai na fila daquele CNPJ
# (GET /dispensadores/fila-exames). Antes, o cidadão não tinha como transferir
# custódia de exame: só `agendar` (papel prescritor/admin) e a chave de
# circulação (que o operador do laboratório precisava digitar).
#
# TICKET-J.7 (`core`, martelo do Fabiano em 15/08 — DESPACHO-ENG-011 §4 + §11a)
# ----------------------------------------------------------------------------
# ANTES este endpoint fazia DUAS coisas: entregava a posse E movia os itens
# `pendente → agendado`, emitindo `pedido_agendado` — **sem criar agendamento
# nenhum**. O comentário original assumia a confluência ("`agendado` É 'sob
# custódia do prestador'"), e era exatamente aí que estava o defeito: a fila do
# laboratório não distinguia "chegou, esperando marcar" de "já marcado para
# quinta às 8h". O mesmo princípio que o endpoint invocava para emitir DOIS
# eventos — posse e estado são fatos distintos — é o que ele violava ao fundi-los.
#
# AGORA é ato de custódia e nada mais:
#   · custódia de nível-pedido (item_id IS NULL): paciente → <cnpj>
#   · UM evento: `custodia_transferida`
#   · itens NÃO são tocados: continuam `pendente`
#   · o pedido permanece `emitido`
#
# Quem promove a `agendado` é o laboratório, criando agendamento com
# data/hora/unidade (`POST /agendamentos`) — ou coletando direto
# (`pendente → coletado`, aresta acrescentada em states_exame.py).
#
# "Onde está o pedido?" passa a ser pergunta para a CUSTÓDIA, não para o status
# (ver `detentor_atual_pedido`). A fila do laboratório já lia custódia; a
# carteira do cidadão passou a ler também.

class TransferirLaboratorioIn(BaseModel):
    cnpj_laboratorio: str
    nome_laboratorio: Optional[str] = None
    # J.10 — ids de `pedido_exame_itens` que seguem ao CNPJ. AUSENTE = tudo o
    # que o cidadão detém (pedido inteiro, se nunca houve parcial — o gesto do
    # J.7 preservado; ou todos os seus itens, se o pedido já opera por item).
    itens: Optional[List[int]] = None


@router.post("/{protocolo}/transferir-laboratorio", status_code=201)
def transferir_laboratorio(
    protocolo: str,
    payload: TransferirLaboratorioIn,
    usuario=Depends(require_role("paciente")),
):
    """
    Cidadão entrega a posse do pedido de exame ao laboratório que escolheu.

    TICKET-J.7 — ato de POSSE, só isso:

    - Cidadão deve deter a custódia (não basta o status ser 'emitido')
    - Itens NÃO mudam de estado: continuam 'pendente'
    - Custódia: paciente → prestador_exame (nível pedido)
    - Ledger: `custodia_transferida` — e mais nada

    TICKET-J.10 — `itens: [id, …]` OPCIONAL no payload: presente, só os itens
    marcados seguem ao CNPJ (§3.3 do desenho: explosão em nível-item); ausente,
    o gesto do J.7 — tudo o que o cidadão detém. Em nenhum caminho os itens
    mudam de estado.
    """
    agora = datetime.utcnow().isoformat()

    # §8.4 (opção A): normalizar o CNPJ na ESCRITA, na raiz — a custódia guarda
    # o valor canônico contra o qual `_assert_dispensador_dono_pedido` compara.
    cnpj = normalize_cnpj(payload.cnpj_laboratorio)
    if len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="cnpj_laboratorio inválido")

    _papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        # TICKET-5C-BIS-A §7.2 — ownership ANTES das checagens de estado
        # (anti-leak #52): quem não é dono não descobre o status alheio.
        _assert_paciente_dono_pedido(conn, protocolo, ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal ({pedido['status']}).",
            )
        # Os itens NÃO são tocados em estado nenhum caminho daqui (martelo §11a:
        # "itens continuam pendente"). Quem os promove a `agendado` é o
        # laboratório, criando agendamento — ou coletando direto.
        todos_itens = _get_itens(conn, pedido["id"])
        itens_ativos = [
            i for i in todos_itens
            if not eh_terminal_item_exame(i["status_item"])
        ]
        if not itens_ativos:
            raise HTTPException(
                status_code=422,
                detail="Nenhum item ativo disponível para transferir.",
            )

        instance_id = get_instance_id_conn(conn)

        em_modo_item = pedido_em_modo_item(conn, pedido["id"])

        if payload.itens is None and not em_modo_item:
            # ── Caminho J.7, intacto (retrocompat): pedido inteiro ──────────
            #
            # TICKET-J.7 — o guard passou de STATUS para CUSTÓDIA.
            #
            # Antes bastava `status == 'emitido'`, porque transferir movia o
            # pedido para `agendado` e o próprio estado impedia a segunda
            # transferência. Agora o pedido permanece `emitido` na mão do
            # laboratório: o status deixou de saber a resposta. Sem esta troca,
            # o cidadão poderia entregar o MESMO pedido a um segundo CNPJ
            # enquanto o primeiro ainda o detém — dupla posse ativa, o R2 na
            # camada de custódia (§3 do CLAUDE.md).
            detentor = detentor_atual_pedido(conn, pedido["id"])
            if not posse_do_cidadao(detentor):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Pedido não está sob sua custódia — a posse está com "
                        f"'{detentor}'."
                    ),
                )

            # TICKET-J.7 — UM evento, porque houve UM fato: a posse mudou de mão.
            #
            # O `pedido_agendado` que saía daqui nomeava uma transição de estado
            # que não deveria ter acontecido — e pior, anunciava um agendamento
            # que não existia em `agendamentos` (`data_agendamento: None` era a
            # confissão). O ledger não fica com mudança de estado sem evento
            # porque não há mais mudança de estado: o pedido segue `emitido`,
            # os itens seguem `pendente`.
            #
            # J.10-CORE — o INSERT cru e este evento viraram uma chamada só: o
            # choke-point fecha a posse do cidadão, abre a do laboratório e
            # emite, atômico. É o que torna a posse exclusiva provável por índice.
            transferir_posse_exame(
                conn, pedido["id"], None,
                DETENTOR_PACIENTE, ident,
                "prestador_exame", cnpj,
                cnpj,                    # coluna `para`: o CNPJ, para o prestador
                "transferencia_laboratorio", agora,
                instance_id=instance_id,
                extra_payload={
                    "nome_laboratorio": payload.nome_laboratorio,
                    "origem":           "cidadao_app",
                    # Quantos itens ativos foram junto com a posse. NÃO é
                    # transição de estado — é o tamanho do que mudou de mão.
                    "itens":            len(itens_ativos),
                },
            )

            novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

            return {
                "ok":                 True,
                "protocolo":          protocolo,
                "status":             novo_status,
                "parcial":            False,
                "itens_transferidos": len(itens_ativos),
                "cnpj_laboratorio":   cnpj,
            }

        # ── Caminho J.10: transferência PARCIAL (DESENHO-J10 §3.3) ───────────
        #
        # O cidadão entrega SÓ alguns itens ao CNPJ. Para a posse nunca viver
        # nas duas granularidades ao mesmo tempo, a primeira parcial EXPLODE o
        # nível-pedido em nível-item: fecha a linha de pedido e abre uma linha
        # por item ativo — os escolhidos ao CNPJ, os demais ao cidadão. Depois
        # disso o pedido opera só em nível-item (`pedido_em_modo_item`), e é a
        # constraint por (pedido_id, item_id) que responde por ele sozinha.
        posse_por_item = {
            i["id"]: detentor_atual_item(conn, pedido["id"], i["id"])
            for i in itens_ativos
        }

        if payload.itens is None:
            # "Nenhum marcado = todos" (§3.6): pedido já explodido, gesto do
            # J.7 reinterpretado no nível que o pedido opera — tudo o que está
            # com o cidadão segue ao CNPJ.
            escolhidos = [
                i["id"] for i in itens_ativos
                if posse_do_cidadao(posse_por_item[i["id"]])
            ]
            if not escolhidos:
                com_outro = next(
                    (p for p in posse_por_item.values() if p), DETENTOR_PACIENTE
                )
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Nenhum item ativo está sob sua custódia — a posse está "
                        f"com '{com_outro}'."
                    ),
                )
        else:
            if not payload.itens:
                raise HTTPException(
                    status_code=422,
                    detail="'itens' não pode ser vazio — omita o campo para transferir tudo.",
                )
            if len(set(payload.itens)) != len(payload.itens):
                raise HTTPException(status_code=422, detail="'itens' contém ids duplicados.")

            item_por_id = {i["id"]: i for i in todos_itens}
            for item_id in payload.itens:
                item_alvo = item_por_id.get(item_id)
                if item_alvo is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Item {item_id} não encontrado no pedido '{protocolo}'.",
                    )
                if eh_terminal_item_exame(item_alvo["status_item"]):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Item {item_id} está em estado terminal "
                            f"({item_alvo['status_item']}) — não circula mais."
                        ),
                    )
                detentor_item = posse_por_item[item_id]
                if not posse_do_cidadao(detentor_item):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Item {item_id} não está sob sua custódia — a posse "
                            f"está com '{detentor_item}'."
                        ),
                    )
            escolhidos = list(payload.itens)

        escolhidos_set = set(escolhidos)
        if not em_modo_item:
            # Primeira parcial: dissolve a nível-pedido e abre linha por item
            # para TODOS os ativos — os demais ficam registrados com o cidadão.
            _dissolver_posse_de_pedido_em_itens(conn, pedido["id"], agora)
            alvos = itens_ativos
        else:
            # Já explodido: só os escolhidos mudam de mão; os demais têm a sua
            # linha ativa (com outro CNPJ ou com o cidadão) e não são tocados.
            alvos = [i for i in itens_ativos if i["id"] in escolhidos_set]

        for item in alvos:
            if item["id"] in escolhidos_set:
                transferir_posse_exame(
                    conn, pedido["id"], item["id"],
                    DETENTOR_PACIENTE, ident,
                    "prestador_exame", cnpj,
                    cnpj,                # coluna `para`: o CNPJ, para o prestador
                    "transferencia_parcial", agora,
                    instance_id=instance_id,
                    extra_payload={
                        "nome_laboratorio": payload.nome_laboratorio,
                        "origem":           "cidadao_app",
                        "nome_exame":       item["nome_exame"],
                    },
                )
            else:
                # Re-expressão de granularidade: o item JÁ estava com o cidadão
                # (coberto pela linha de pedido); ganha a sua própria linha com
                # `de == para`. O payload marca a intenção — sem a flag, um
                # auditor leria "transferiu para si mesmo" onde o que houve foi
                # "a posse passou a viver por item".
                transferir_posse_exame(
                    conn, pedido["id"], item["id"],
                    DETENTOR_PACIENTE, ident,
                    DETENTOR_PACIENTE, ident,
                    DETENTOR_PACIENTE,     # coluna `para`: o PAPEL, para o cidadão
                    "transferencia_parcial", agora,
                    instance_id=instance_id,
                    extra_payload={
                        "reexpressao_nivel_item": True,
                        "nome_exame":             item["nome_exame"],
                    },
                )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        return {
            "ok":                 True,
            "protocolo":          protocolo,
            "status":             novo_status,
            "parcial":            True,
            "itens_transferidos": len(escolhidos),
            "itens":              sorted(escolhidos),
            "cnpj_laboratorio":   cnpj,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/itens/{item_id}/devolver — J.10 (§3.4)
# O laboratório devolve ao cidadão o item que não realiza.
# ----------------------------------------------------------------------------

class DevolverItemExameIn(BaseModel):
    # Texto livre do operador ("não temos o reagente"). Vai no extra_payload
    # como `motivo_declarado` — o motivo CANÔNICO da custódia é
    # `devolucao_nao_realizavel` e detalhe livre nunca o sobrescreve (§3 do
    # CLAUDE.md, mesma disciplina do choke-point).
    motivo: str = Field(..., min_length=3, max_length=240)


@router.post("/{protocolo}/itens/{item_id}/devolver", status_code=200)
def devolver_item_exame(
    protocolo: str,
    item_id: int,
    payload: DevolverItemExameIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Laboratório devolve ao cidadão um item que não realiza (J.10 §0.2).

    - Custódia: prestador_exame → paciente, no nível do item
    - Item PERMANECE 'pendente' — devolução é posse, não clínica (a mesma
      separação do J.7). O estado `nao_realizado` (reservado v2) NÃO é usado:
      "esta unidade não performa" vive no motivo da custódia, não num estado
      terminal que impediria o item de circular a outro CNPJ.
    - Exige item 'pendente': `agendado` tem objeto agendamento — cancelá-lo
      (`POST /agendamentos/{id}/cancelar`, caminho existente) é o que devolve
      o item a 'pendente'; a máquina de estados não tem aresta de volta, e
      criá-la seria mudança `core` fora deste ticket.
    - Se a posse era de NÍVEL-PEDIDO, o pedido explode em nível-item (§3.3):
      este item volta ao cidadão; os demais ativos ficam com a unidade, cada
      um com a sua linha.
    """
    agora = datetime.utcnow().isoformat()

    # 404 do PEDIDO → 403 GROSSO → 404 do ITEM → 403 FINO → 422 (anti-leak #52).
    #
    # O 403 grosso vem antes do 404 do item de propósito: sem ele, quem não
    # detém nada deste pedido distingue, pelo código de status, um id de item
    # que existe de um que não existe — e enumera os itens de um pedido alheio
    # de fora. Quem É parte passa e recebe o 404 honesto.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel == "dispensador":
            _assert_dispensador_algo_no_pedido(conn, pedido["id"], ident)

        item = conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE id = ? AND pedido_id = ?",
            (item_id, pedido["id"]),
        ).fetchone()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item_id} não encontrado no pedido '{protocolo}'.",
            )

        if papel != "admin":
            _assert_dispensador_dono_item(conn, pedido["id"], item_id, ident)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal ({pedido['status']}).",
            )

        if item["status_item"] != "pendente":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Devolução requer item em 'pendente' (está em "
                    f"'{item['status_item']}'). Item agendado: cancele o "
                    "agendamento antes — o cancelamento devolve o item a "
                    "'pendente'."
                ),
            )

        # Para o ledger da devolução: o cidadão que recebe de volta.
        pac_cpf = conn.execute(
            "SELECT pa.cpf FROM pacientes pa WHERE pa.id = ?",
            (pedido["paciente_id"],),
        ).fetchone()["cpf"]

        itens_ativos = [
            i for i in _get_itens(conn, pedido["id"])
            if not eh_terminal_item_exame(i["status_item"])
        ]
        instance_id = get_instance_id_conn(conn)
        em_modo_item = pedido_em_modo_item(conn, pedido["id"])

        if not em_modo_item:
            # Posse era de nível-pedido (desta unidade): explosão §3.3 — este
            # item volta ao cidadão, os demais ativos são re-expressos em
            # nível-item no nome da própria unidade.
            _dissolver_posse_de_pedido_em_itens(conn, pedido["id"], agora)
            alvos = itens_ativos
        else:
            alvos = [it for it in itens_ativos if it["id"] == item_id]

        for it in alvos:
            if it["id"] == item_id:
                transferir_posse_exame(
                    conn, pedido["id"], it["id"],
                    "prestador_exame", ident,
                    DETENTOR_PACIENTE, pac_cpf,
                    DETENTOR_PACIENTE,     # coluna `para`: o PAPEL, para o cidadão
                    "devolucao_nao_realizavel", agora,
                    instance_id=instance_id,
                    extra_payload={
                        "motivo_declarado": payload.motivo,
                        "nome_exame":       it["nome_exame"],
                    },
                )
            else:
                # Re-expressão de granularidade (ver nota no transferir): o
                # item continua com a unidade; só o nível em que a posse vive
                # mudou de pedido para item.
                transferir_posse_exame(
                    conn, pedido["id"], it["id"],
                    "prestador_exame", ident,
                    "prestador_exame", ident,
                    ident,                 # coluna `para`: o CNPJ, para o prestador
                    "devolucao_nao_realizavel", agora,
                    instance_id=instance_id,
                    extra_payload={
                        "reexpressao_nivel_item": True,
                        "nome_exame":             it["nome_exame"],
                    },
                )

        # Sem transição de estado e sem evento de estado: o fato é o da
        # custódia (`custodia_transferida`, motivo `devolucao_nao_realizavel`).
        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "pendente",
            "status_pedido": novo_status,
            "detentor":      DETENTOR_PACIENTE,
            "motivo":        "devolucao_nao_realizavel",
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
                # Guarda GROSSA antes do estado (anti-leak #52): quem não detém
                # nada deste pedido não aprende que ele está terminal. O guard
                # FINO, por item, continua depois do 404 do item.
                _assert_dispensador_algo_no_pedido(conn, pedido["id"], ident)

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

        # J.10 — guarda do ITEM, não do pedido: coleta é gesto por item, e quem
        # detém só parte de um pedido (transferência parcial) coleta o que
        # detém. Vale pela linha de item ativa OU pela posse de pedido inteiro
        # que o cobre (`_assert_dispensador_dono_item`).
        if papel == "dispensador":
            _assert_dispensador_dono_item(conn, pedido["id"], item_id, ident)

        # TICKET-J.7 — `pendente` também coleta: é a "coleta direta" do martelo
        # (§11a, verbatim: "criando agendamento com data/hora/unidade — ou
        # realizando direto"). O laboratório que já está com o material na mão
        # não precisa inventar um agendamento retroativo para registrar o fato.
        # Continua valendo o contrato: só estes dois estados coletam.
        if item["status_item"] not in ("pendente", "agendado"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Coleta requer item em 'pendente' ou 'agendado'. "
                    f"Status atual: '{item['status_item']}'."
                ),
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
# POST /pedidos-exame/{protocolo}/itens/{item_id}/em-analise — "enviar à bancada"
# Transição do item: coletado → em_analise
#
# TICKET-B (demo laboratório, decisão #4). Até aqui `em_analise` era estado
# FANTASMA: declarado em states_exame.py, na lista branca de transições e no
# vocabulário de eventos — mas nenhum endpoint o persistia. O /resultado emitia
# `pedido_em_analise` como marco intermediário e escrevia `resultado_disponivel`
# direto; o item nunca REPOUSAVA na bancada. Este endpoint materializa a
# transição que o contrato já previa, para que a clínica possa dizer "mandei
# para a bancada" e o laudo ser produzido a partir daí.
#
# FRONTEIRA LIMS: `setor` é texto livre para visibilidade operacional ("bancada
# de bioquímica"). Roteamento interno — analisador, técnico, fila de
# equipamento, lote — é o LIMS do laboratório, NÃO o PicSaúde. O dia em que
# `setor` virar fila de máquina, virou outro produto.
# ---------------------------------------------------------------------------

class EmAnaliseIn(BaseModel):
    # max_length é higiene, não regra de negócio: texto livre que entra em
    # ledger imutável (§2) não tem como ser corrigido depois.
    setor: Optional[str] = Field(default=None, max_length=120)


@router.post("/{protocolo}/itens/{item_id}/em-analise", status_code=200)
def enviar_item_a_bancada(
    protocolo: str,
    item_id: int,
    # Corpo opcional (precedente: circulacao_diagnostica.py:664) — enviar à
    # bancada sem declarar setor é o caso comum.
    payload: EmAnaliseIn = Body(default=EmAnaliseIn()),
    # Quem envia à bancada é a UNIDADE que detém o pedido; o prescritor não
    # participa deste gesto (não é dele a bancada).
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Envia um item coletado à bancada do laboratório.

    Item: coletado → em_analise
    Status do pedido recalculado automaticamente via derivar_status_pedido().
    """
    agora = datetime.utcnow().isoformat()

    # TICKET-5C-BIS-A §7.2 — dispensador valida ownership; admin bypassa.
    # 404 → 403 → 422 de estado (anti-leak #52).
    papel, ident = _normalizar_identidade_jwt(usuario)

    # String vazia não é setor declarado — o ledger não deve guardar "" como se
    # fosse um dado que alguém informou.
    setor = (payload.setor or "").strip() or None

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel == "dispensador":
            # Guarda GROSSA antes do estado (anti-leak #52) — ver coletar_item_exame.
            _assert_dispensador_algo_no_pedido(conn, pedido["id"], ident)

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

        # J.10 — guarda do ITEM (ver nota em coletar_item_exame): a bancada é
        # da unidade que detém o item, ainda que o pedido circule por parcial.
        if papel == "dispensador":
            _assert_dispensador_dono_item(conn, pedido["id"], item_id, ident)

        if item["status_item"] != "coletado":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Envio à bancada requer item em 'coletado'. "
                    f"Status atual: '{item['status_item']}'."
                ),
            )

        conn.execute(
            "UPDATE pedido_exame_itens SET status_item = 'em_analise' WHERE id = ?",
            (item_id,),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        ev_bancada = {
            "item_id":    item_id,
            "nome_exame": item["nome_exame"],
            "setor":      setor,
        }
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="pedido_exame",
            objeto_id=pedido["id"],
            tipo_evento="pedido_em_analise",
            instance_id=instance_id,
            payload=ev_bancada,
        )
        registrar_outbox(
            conn, "pedido_em_analise", "pedido_exame", protocolo, ev_bancada,
            instance_id=instance_id,
        )

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "em_analise",
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

    @field_validator("resultado_resumo")
    @classmethod
    def _resumo_precisa_ter_conteudo(cls, v: Optional[str]) -> Optional[str]:
        """ENG-019 PR 6 — `""` não é dado; `None` é ausência declarada.

        A tela capturava o resumo num `prompt()` que só barrava o cancelar, e
        string vazia avançava o item com um resultado clínico SEM CONTEÚDO. O
        ledger é imutável por trigger (§2): o que entra em branco hoje não se
        corrige nunca, só se supera. Por isso a guarda é do backend, e não só
        da tela — validação de tela não protege registro permanente.

        Nulo segue aceito de propósito: o caminho do LAUDO manda nulo quando o
        RT preenche conclusão e valor de referência e deixa o resumo livre em
        branco (`_coletarItensDoEditor` faz `.trim() || null`). Ali o artefato é
        o laudo; o resumo do item é ponteiro. Exigir texto quebraria o Ticket G
        sem defender nada.

        Espaço nas bordas é digitação, não dado — some antes de gravar.
        """
        if v is None:
            return None
        limpo = v.strip()
        if not limpo:
            raise ValueError(
                "resultado_resumo não pode ser vazio: informe o resultado ou "
                "omita o campo."
            )
        return limpo


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
    # A guarda de posse segue a de coletar_item_exame — dono = prestador na
    # custódia ATUAL, no nível do ITEM desde o J.10. Nada de guarda nova.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel == "dispensador":
            # Guarda GROSSA antes do estado (anti-leak #52) — ver coletar_item_exame.
            _assert_dispensador_algo_no_pedido(conn, pedido["id"], ident)

        if papel != "admin":
            if papel == "prescritor":
                _assert_prescritor_dono_pedido(conn, protocolo, ident)

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

        # J.10 — guarda do ITEM (ver nota em coletar_item_exame): o resultado é
        # do item que a unidade detém, ainda que o pedido circule por parcial.
        if papel == "dispensador":
            _assert_dispensador_dono_item(conn, pedido["id"], item_id, ident)

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
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
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

        # §7.3 — owner check só para 'prescritor'; admin passa.
        #
        # > **Superseded em 24/08 para o PACIENTE (ENG-017 PR B, `core`, martelo
        # > do Fabiano).** A regra anterior dizia "não há paciente/dispensador
        # > no require_role do pdf — não adicionar (§4.4)". A comissão de
        # > diagnóstico da Regra Zero (#189, S5) mostrou a contradição: o
        # > cidadão DETÉM A CUSTÓDIA do pedido — está na carteira dele, ancorado
        # > ao CPF dele — e levava 403 ao pedir o PDF do que carrega. O martelo
        # > abriu para o `paciente`, com ownership por CPF.
        # >
        # > **`dispensador` continua FORA, e isso não foi esquecimento:** o
        # > pedido é artefato de QUEM EMITIU, e abri-lo ao laboratório daria à
        # > clínica o documento do prescritor. O que a clínica precisa é de
        # > comprovante do que ELA executou, sob escopo de posse — é o S5-bis,
        # > delimitado pelo arquiteto e fora deste PR.
        if papel == "paciente":
            # O cidadão só baixa o PRÓPRIO pedido. Papel sem dono deixaria
            # qualquer paciente autenticado baixar o pedido de qualquer outro.
            #
            # Ownership por CPF do DOCUMENTO, não por custódia: o pedido pode
            # estar no laboratório no momento do download e continua sendo o
            # documento dele. Custódia responde "onde está"; ownership responde
            # "de quem é".
            _assert_or_403(
                normalize_cpf(ident) == normalize_cpf(row["cpf_paciente"] or ""),
                codigo="nao_e_dono_do_pedido_exame",
                mensagem="Este pedido de exame pertence a outro paciente.",
            )

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
