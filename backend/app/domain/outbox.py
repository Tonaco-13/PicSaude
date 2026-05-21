"""
outbox.py
=========
Helper central para inserção no outbox de publicação de eventos (G4A).

Uso:
    Quando houver evento publicável previsto, o router deve chamar
    `registrar_outbox()` com o mesmo `instance_id` do ledger, dentro da
    mesma transação clínica. Nem todo INSERT em `*_eventos` tem outbox
    adjacente — apenas os eventos com semântica de publicação externa.

Princípio de isolamento:
    A função nunca levanta exceção que impacte o fluxo clínico.
    Se o INSERT no outbox falhar (ex: tabela não existe), o erro é silenciado
    com log de warning — o ledger clínico já foi gravado e é a fonte de verdade.

Classificação de mudança: module (G4A)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


def registrar_outbox(
    conn,
    tipo_evento:  str,
    objeto_tipo:  str,
    objeto_id:    str,
    payload:      dict[str, Any],
    org_id:       str | None = None,
    unidade_id:   str | None = None,
    *,
    instance_id:  str,
) -> str | None:
    """
    Insere um registro no outbox `eventos_publicacao`.

    Parâmetros
    ----------
    conn        : conexão SQLite ativa (mesma transação do ledger)
    tipo_evento : string do evento (ex: "agendamento_realizado")
    objeto_tipo : tipo do objeto sanitário (ex: "agendamento", "prescricao")
    objeto_id   : protocolo UUID do objeto
    payload     : dict com contexto do evento (será serializado em JSON)
    org_id      : escopo institucional (None = sem escopo obrigatório)
    unidade_id  : escopo de unidade (None = sem escopo obrigatório)
    instance_id : UUID v4 da instância. **Keyword-only obrigatório desde 4E.2.**
                  Caller obtém via get_instance_id_conn(conn) e passa para
                  ledger e outbox no mesmo `with get_tx()` para garantir
                  coerência forense.

    Retorna
    -------
    id do evento criado (ex: "evt_<uuid>") ou None se falhou silenciosamente.
    """
    evt_id = "evt_" + str(uuid.uuid4())
    agora  = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute(
            """
            INSERT INTO eventos_publicacao
                (id, tipo_evento, objeto_tipo, objeto_id, payload,
                 org_id, unidade_id, instance_id,
                 publicado, tentativas, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (
                evt_id,
                tipo_evento,
                objeto_tipo,
                objeto_id,
                json.dumps(payload, ensure_ascii=False),
                org_id,
                unidade_id,
                instance_id,
                agora,
            ),
        )
        return evt_id
    except Exception:  # noqa: BLE001
        # Falha de outbox nunca impacta o fluxo clínico (princípio G4A §2.4)
        import logging
        logging.getLogger(__name__).warning(
            "outbox: falha ao registrar evento '%s' para objeto '%s/%s'",
            tipo_evento,
            objeto_tipo,
            objeto_id,
        )
        return None
