"""TICKET-5C-BIS-F — ownership de `devolver_item` (custodia.py).

Espelha o V6 do transferir: dispensador → detém custódia ativa; prescritor → é o
autor. admin bypass. Anti-leak 404 → 403 → 409. Reusa o seed da suíte focal de
devolução (custódia já montada para `_DISPENSADOR_CNPJ`).

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import SEED_PRESCRITOR_CNS
from tests.integration.test_custodia_devolucao import (
    _seed_prescricao_com_itens_em_custodia,
    _DISPENSADOR_CNPJ,
)

_OUTRO_CNPJ = "99999999000191"   # dispensador que NÃO detém custódia
_OUTRO_CNS = "999999999999999"   # prescritor que NÃO é autor


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _devolver(client, proto: str, item_id: int, token: str, para: str = "paciente"):
    return client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": para, "motivo": "teste ownership"},
        headers=_h(token),
    )


def test_dispensador_sem_custodia_403(client, outer_conn):
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    # custódia é do _DISPENSADOR_CNPJ; um dispensador diferente não detém
    r = _devolver(client, proto, item_id, _tok(_OUTRO_CNPJ, "dispensador"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_detem_custodia"


def test_dispensador_com_custodia_200(client, outer_conn):
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    r = _devolver(client, proto, item_id, _tok(_DISPENSADOR_CNPJ, "dispensador"))
    assert r.status_code == 200, r.text


def test_prescritor_nao_autor_403(client, outer_conn):
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    r = _devolver(client, proto, item_id, _tok(_OUTRO_CNS, "prescritor"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_autor_da_prescricao"


def test_prescritor_autor_200(client, outer_conn):
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    r = _devolver(client, proto, item_id, _tok(SEED_PRESCRITOR_CNS, "prescritor"))
    assert r.status_code == 200, r.text


def test_admin_bypass_200(client, outer_conn):
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    r = _devolver(client, proto, item_id, _tok("admin", "admin"))
    assert r.status_code == 200, r.text


def test_antileak_403_precede_409(client, outer_conn):
    """Item terminal (dispensado) normalmente daria 409; o não-dono recebe 403 antes."""
    _, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    with outer_conn.cursor() as cur:
        cur.execute("UPDATE prescricao_itens SET status_item='dispensado' WHERE id=%s", (item_id,))
    r = _devolver(client, proto, item_id, _tok(_OUTRO_CNPJ, "dispensador"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_detem_custodia"
