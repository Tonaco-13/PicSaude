"""
app/domain/ledger.py
====================
Helper centralizado de inserção no ledger imutável (Sub-tarefa 4C).

Propósito (DATA-PROTECTION.md §4.2)
-----------------------------------
Cada evento do ledger interno deve carregar o ``instance_id`` da instância
PicSaúde. A 4B adicionou a coluna física em 6 tabelas; este módulo entrega
o **fluxo centralizado** que recusa inserções sem ``instance_id``.

Por que helper único e não 5 helpers por subdomínio
---------------------------------------------------
Encapsula o **drift de schema** pré-existente entre as tabelas de
eventos clínicos (ex.: ``agendamento_eventos.evento`` é outlier — usa
``evento`` em vez de ``tipo_evento``) num único mapping privado. Routers
ficam com API uniforme. Padronização do drift vira ticket separado.

Contrato com os routers (aplicado pelos routers desde 4D — Etapa 4 fechada em 2026-05-21)
-----------------------------------------------------------------------------------------
1. Router abre transação clínica via ``get_tx()``.
2. Router chama ``get_instance_id_conn(conn)`` UMA VEZ por transação.
3. Router passa ``instance_id`` para ``registrar_evento_ledger`` E para
   ``registrar_outbox`` — garante coerência entre ledger e outbox.
4. Helper recusa chamadas sem ``instance_id`` (parâmetro keyword-only
   obrigatório, sem default → ``TypeError`` em chamadas mal formadas).

Diferença em relação ao outbox
------------------------------
Falha em INSERT no ledger **levanta exceção** — ledger é fonte de verdade
do subdomínio. Outbox segue best-effort (silencia exceção): ele apenas
espelha para publicação externa.

Classificação (CLAUDE.md §10): ``core`` — toca o ledger imutável.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from app.instance import _validar_uuid_v4


# ---------------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------------

ObjetoSanitario = Literal[
    "prescricao",
    "pedido_exame",
    "laudo",
    "agendamento",
    "circulacao_diagnostica",
    "encaminhamento",
    "contrarreferencia",
]


# ---------------------------------------------------------------------------
# Mapping privado das diferenças de schema (drift pré-existente)
# ---------------------------------------------------------------------------
# Padronização das colunas (renomear ``evento`` → ``tipo_evento`` em
# ``agendamento_eventos`` etc.) vira ticket separado — escapar do escopo da
# 4C evita PR gigante. Aqui apenas convivemos com o drift.

_LEDGER_SCHEMA: dict[str, dict[str, Any]] = {
    "prescricao": {
        "tabela":          "prescricao_eventos",
        "coluna_fk":       "prescricao_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "payload_json",
        "coluna_data":     "created_at",
        "tem_ator":        True,
    },
    "pedido_exame": {
        "tabela":          "pedido_exame_eventos",
        "coluna_fk":       "pedido_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "dados_json",
        "coluna_data":     "criado_em",
        "tem_ator":        False,
    },
    "laudo": {
        "tabela":          "laudo_eventos",
        "coluna_fk":       "laudo_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "dados_json",
        "coluna_data":     "criado_em",
        "tem_ator":        False,
    },
    "agendamento": {
        # OUTLIER: usa ``evento`` em vez de ``tipo_evento``.
        "tabela":          "agendamento_eventos",
        "coluna_fk":       "agendamento_id",
        "coluna_tipo":     "evento",
        "coluna_payload":  "payload",
        "coluna_data":     "criado_em",
        "tem_ator":        False,
    },
    "circulacao_diagnostica": {
        "tabela":          "circulacao_diagnostica_eventos",
        "coluna_fk":       "circulacao_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "dados_json",
        "coluna_data":     "criado_em",
        "tem_ator":        False,
    },
    "encaminhamento": {
        "tabela":          "encaminhamento_eventos",
        "coluna_fk":       "encaminhamento_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "payload",
        "coluna_data":     "created_at",
        "tem_ator":        True,
    },
    "contrarreferencia": {
        "tabela":          "contrarreferencia_eventos",
        "coluna_fk":       "contrarreferencia_id",
        "coluna_tipo":     "tipo_evento",
        "coluna_payload":  "payload",
        "coluna_data":     "created_at",
        "tem_ator":        True,
    },
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def registrar_evento_ledger(
    conn,
    *,
    objeto_tipo: ObjetoSanitario,
    objeto_id: int,
    tipo_evento: str,
    instance_id: str,
    payload: dict[str, Any] | None = None,
    ator_tipo: str | None = None,
    ator_id: str | None = None,
) -> None:
    """
    Insere um evento no ledger interno do subdomínio.

    Encapsula o drift de schema entre as tabelas de eventos clínicos
    (nome de coluna de tipo, nome do payload, presença de coluna de ator).

    Parâmetros
    ----------
    conn : conexão raw (``sqlite3.Connection`` em dev / ``_PgConnection``
        em prod). Mesma transação clínica do router caller.
    objeto_tipo : ``"prescricao" | "pedido_exame" | "laudo" |
        "agendamento" | "circulacao_diagnostica" | "encaminhamento"``.
        Validado em runtime (defesa em camadas além do ``Literal`` para
        o type-checker).
    objeto_id : ID inteiro do objeto sanitário (FK para a tabela do
        subdomínio).
    tipo_evento : nome do evento (string livre — vocabulário em
        ``CLAUDE.md §2``).
    instance_id : UUID v4 da instância. **Obrigatório** — caller obtém via
        ``app.instance.get_instance_id_conn(conn)`` UMA VEZ por transação
        e passa para ledger E outbox. Sem default: chamadas sem o
        argumento levantam ``TypeError``.
    payload : dict opcional. ``None`` é normalizado para ``{}`` no banco
        (semântica explícita: payload vazio, não NULL).
    ator_tipo, ator_id : aceitos apenas nos subdomínios cujo schema possui
        colunas de ator. Para esses subdomínios, ``ator_tipo`` é obrigatório
        (ator_id pode ser ``None`` por design das tabelas).

    Levanta
    -------
    TypeError
        Quando ``instance_id`` não é fornecido (regime keyword-only
        sem default).
    ValueError
        - ``objeto_tipo`` não está em ``_LEDGER_SCHEMA``.
        - ``ator_tipo``/``ator_id`` em subdomínio que não suporta ator.
        - subdomínio com colunas de ator chamado sem ``ator_tipo``.
    Exception
        Qualquer falha do ``conn.execute`` (SQLite ``OperationalError``,
        ``IntegrityError`` etc.). **Não é silenciada** — ledger é fonte
        de verdade do subdomínio.
    """
    # 0. Validação de instance_id em runtime (CODEX rodada 3 — P1).
    #    O regime keyword-only sem default só pega ausência (TypeError);
    #    aqui pegamos invalidez (None explícito, "", lixo, UUID v1).
    #    Defesa em camadas: caller pode ter `instance_id: str | None = None`
    #    no escopo local e passar inadvertidamente.
    _validar_uuid_v4(instance_id)

    # 1. Validação de objeto_tipo (defesa em camadas — Literal só vale para type-checker).
    schema = _LEDGER_SCHEMA.get(objeto_tipo)
    if schema is None:
        raise ValueError(
            f"objeto_tipo {objeto_tipo!r} inválido. "
            f"Permitidos: {sorted(_LEDGER_SCHEMA.keys())}"
        )

    # 2. Validação de ator (consistência com schema do subdomínio).
    if not schema["tem_ator"] and (ator_tipo is not None or ator_id is not None):
        raise ValueError(
            f"objeto_tipo {objeto_tipo!r} não suporta ator_tipo/ator_id. "
            "Apenas subdomínios com colunas de ator aceitam esses campos."
        )
    if schema["tem_ator"] and not ator_tipo:
        raise ValueError(
            f"objeto_tipo {objeto_tipo!r} exige ator_tipo "
            "(ex.: 'prescritor', 'paciente', 'sistema')."
        )

    # 3. Preparação dos valores.
    agora = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    # 4. INSERT dinâmico respeitando schema do subdomínio.
    #    Usa placeholders ``?`` (SQLite nativo + traduzido para ``%s`` pelo
    #    wrapper ``_PgConnection`` em prod).
    if schema["tem_ator"]:
        sql = (
            f"INSERT INTO {schema['tabela']} "
            f"({schema['coluna_fk']}, {schema['coluna_tipo']}, "
            f"ator_tipo, ator_id, "
            f"{schema['coluna_payload']}, {schema['coluna_data']}, instance_id) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            objeto_id,
            tipo_evento,
            ator_tipo,
            ator_id,
            payload_json,
            agora,
            instance_id,
        )
    else:
        sql = (
            f"INSERT INTO {schema['tabela']} "
            f"({schema['coluna_fk']}, {schema['coluna_tipo']}, "
            f"{schema['coluna_payload']}, {schema['coluna_data']}, instance_id) "
            f"VALUES (?, ?, ?, ?, ?)"
        )
        params = (
            objeto_id,
            tipo_evento,
            payload_json,
            agora,
            instance_id,
        )

    # 5. Execução. Falha levanta — ledger é fonte de verdade.
    conn.execute(sql, params)
