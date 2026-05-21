"""
test_outbox_hardening.py
========================
Guarda estática da assinatura de `registrar_outbox` (TICKET 4E.2 §3.1.4).

`instance_id` virou keyword-only obrigatório — sem default. Caller deve
passar via `get_instance_id_conn(conn)`, garantindo coerência forense
entre ledger e outbox no mesmo `with get_tx()`.

Este teste falha cedo se alguém remover o `*` ou o tornar opcional outra
vez, evitando regressão silenciosa para o estado pré-4E.2.
"""
from __future__ import annotations

import inspect

from app.domain.outbox import registrar_outbox


def test_registrar_outbox_exige_instance_id():
    """Não permitir regressão silenciosa: chamada sem instance_id deve falhar."""
    sig = inspect.signature(registrar_outbox)
    param = sig.parameters.get("instance_id")
    assert param is not None, "registrar_outbox perdeu o parâmetro instance_id"
    assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"instance_id deve ser KEYWORD_ONLY (4E.2 §3.1.4) — atual: {param.kind}"
    )
    assert param.default is inspect.Parameter.empty, (
        "instance_id não pode ter default — caller deve passar explicitamente"
    )
