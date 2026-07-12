"""TICKET-CORE-R2 §3.3 (fix M1) — token com `expira_em` malformado é rejeitado.

Antes, `custodia.py` capturava o erro de parse do `expira_em` e seguia sem
rejeitar (`pass`) — uma janela em que um token cuja validade não se pode
verificar ainda dispensava. Passa a devolver 422 `token_expira_em_malformado`.

Harness SQLite (fixtures prescritor/dispensador/db_path). Custódia semeada à mão
porque fora do DEMO_MODE não há auto-retenção.
"""
from __future__ import annotations

import sqlite3

_CNPJ = "12345678000195"          # = sub do RoleClient dispensador
_CPF = "12345678901"

_PRESC = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": _CPF,
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


def _seed_custodia_item(db_path, pid, iid, cnpj=_CNPJ):
    with _conn(db_path) as c:
        now = "2026-07-11T00:00:00"
        c.execute(
            """INSERT INTO prescricao_custodia
                 (prescricao_id, item_id, detentor_tipo, detentor_id,
                  transferida_em, encerrada_em, motivo, created_at)
               VALUES (?, ?, 'dispensador', ?, ?, NULL, 'seed-r2', ?)""",
            (pid, iid, cnpj, now, now),
        )
        c.commit()


def _seed_token(db_path, proto, iid, expira_em):
    with _conn(db_path) as c:
        c.execute(
            """INSERT INTO tokens_apresentacao
                 (codigo_curto, protocolo, paciente_cpf, escopo, status,
                  expira_em, criado_em, item_id)
               VALUES ('TOKMAL', ?, ?, 'item', 'ativo', ?, ?, ?)""",
            (proto, _CPF, expira_em, "2026-07-11T00:00:00", iid),
        )
        c.commit()


def test_token_expira_em_malformado_rejeita(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    pid, iid = _ids(db_path, proto)
    _seed_custodia_item(db_path, pid, iid)
    _seed_token(db_path, proto, iid, expira_em="nao-e-uma-data")

    r = dispensador.post(
        f"/prescricoes/{proto}/itens/{iid}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 1,
              "codigo_curto_token": "TOKMAL"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "token_expira_em_malformado"

    # Read-only sobre o furo: nenhuma dispensação gravada apesar do token.
    with _conn(db_path) as c:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM dispensacoes WHERE prescricao_item_id = ?", (iid,)
        ).fetchone()["n"]
    assert n == 0, "token malformado não pode gerar movimento"


def test_token_expira_em_valido_nao_regride(prescritor, dispensador, db_path):
    """Contra-prova: token bem-formado e vigente dispensa normalmente (não
    quebramos o caminho feliz ao endurecer o malformado)."""
    proto = _emitir(prescritor)
    pid, iid = _ids(db_path, proto)
    _seed_custodia_item(db_path, pid, iid)
    _seed_token(db_path, proto, iid, expira_em="2099-01-01T00:00:00")

    r = dispensador.post(
        f"/prescricoes/{proto}/itens/{iid}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 1,
              "codigo_curto_token": "TOKMAL"},
    )
    assert r.status_code == 201, r.text
