"""
test_fila_dispensador.py — T4: fila do dispensador.

GET /dispensadores/fila lista as prescrições sob custódia ATIVA do CNPJ do JWT.
É o que faz o balcão ver as receitas chegarem (em vez de resolver token na mão).
Cobre: fila populada + itens/saldo; fila vazia; isolamento por CNPJ; saldo que
desconta o já dispensado. Harness SQLite (fixtures prescritor/dispensador/db_path).
"""
from __future__ import annotations

import sqlite3

_CNPJ = "12345678000195"          # = sub do RoleClient dispensador
_CNPJ_OUTRO = "98765432000110"

_PRESC = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Teste",
    "tipo_emissao": "nova",
    "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
               "quantidade": 10, "posologia": "1x"}],
}


def _conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _emitir(prescritor):
    r = prescritor.post("/prescricoes", json=_PRESC)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ids(db_path, proto):
    with _conn(db_path) as c:
        pid = c.execute("SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)).fetchone()["id"]
        iid = c.execute("SELECT id FROM prescricao_itens WHERE prescricao_id = ? LIMIT 1", (pid,)).fetchone()["id"]
    return pid, iid


def _seed_custodia(db_path, proto, cnpj=_CNPJ, item_id=None, marca_item_em_custodia=False):
    """Abre custódia ativa do dispensador. item_id=None → prescrição inteira."""
    pid, iid = _ids(db_path, proto)
    with _conn(db_path) as c:
        now = "2026-07-08T00:00:00"
        c.execute(
            """INSERT INTO prescricao_custodia
                 (prescricao_id, item_id, detentor_tipo, detentor_id,
                  transferida_em, encerrada_em, motivo, created_at)
               VALUES (?, ?, 'dispensador', ?, ?, NULL, 'seed-t4', ?)""",
            (pid, item_id, cnpj, now, now),
        )
        if marca_item_em_custodia:
            c.execute("UPDATE prescricao_itens SET status_item='em_custodia' WHERE id=?", (iid,))
        c.commit()
    return pid, iid


def test_fila_mostra_prescricao_sob_custodia(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _seed_custodia(db_path, proto, _CNPJ)              # custódia da prescrição inteira

    r = dispensador.get("/dispensadores/fila")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 1
    p = d["fila"][0]
    assert p["protocolo"] == proto
    assert p["paciente"]["nome"] == "PACIENTE TESTE"   # backend normaliza p/ maiúsculas
    assert len(p["itens"]) == 1
    it = p["itens"][0]
    assert it["nome_medicamento"] == "AMOXICILINA"
    assert it["quantidade"] == 10
    assert it["saldo"] == 10


def test_fila_vazia_sem_custodia(dispensador, db_path):
    r = dispensador.get("/dispensadores/fila")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


def test_fila_isolada_por_cnpj(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _seed_custodia(db_path, proto, _CNPJ_OUTRO)        # custódia de OUTRA farmácia

    r = dispensador.get("/dispensadores/fila")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0                      # não vaza pra este CNPJ


def test_fila_saldo_desconta_dispensado(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto, _CNPJ, item_id=None, marca_item_em_custodia=True)

    rd = dispensador.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 4},
    )
    assert rd.status_code == 201, rd.text

    r = dispensador.get("/dispensadores/fila")
    it = r.json()["fila"][0]["itens"][0]
    assert it["quantidade_dispensada"] == 4
    assert it["saldo"] == 6
