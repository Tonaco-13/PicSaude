"""
test_relatorio_sngpc_endpoint.py — TICKET-F5, Fatia A (endpoint, harness SQLite).

Exercita GET /dispensadores/relatorio.{csv,pdf} de ponta a ponta contra SQLite:
  §5.1 isolamento por CNPJ · §5.2 dispensação+estorno = 2 linhas + saldo reposto
  §5.3 comprador declarado × paciente · §5.4 sentinela excluída · §5.5 sem endereço
  §5.8 PDF 2xx · role dispensador obrigatória · read-only (nada muda no banco)

O caminho 2xx contra PostgreSQL (tipos datetime) está em
tests/integration/test_relatorio_sngpc.py (gate com docker postgres:15).
"""
from __future__ import annotations

import csv
import io
import sqlite3

_CNPJ = "12345678000195"           # = sub do RoleClient dispensador
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


def _seed_custodia(db_path, proto, cnpj=_CNPJ):
    pid, iid = _ids(db_path, proto)
    with _conn(db_path) as c:
        now = "2026-07-08T00:00:00"
        c.execute(
            """INSERT INTO prescricao_custodia
                 (prescricao_id, item_id, detentor_tipo, detentor_id,
                  transferida_em, encerrada_em, motivo, created_at)
               VALUES (?, NULL, 'dispensador', ?, ?, NULL, 'seed-f5', ?)""",
            (pid, cnpj, now, now),
        )
        c.execute("UPDATE prescricao_itens SET status_item='em_custodia' WHERE id=?", (iid,))
        c.commit()
    return pid, iid


def _dispensar(dispensador, proto, item_id, qtd, comprador=None, doc=None):
    payload = {"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": qtd}
    if comprador:
        payload["comprador_nome"] = comprador
    if doc:
        payload["comprador_documento"] = doc
    r = dispensador.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["dispensacao_id"]


def _csv_rows(dispensador, **params):
    r = dispensador.get("/dispensadores/relatorio.csv", params=params)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    return list(csv.DictReader(io.StringIO(r.text)))


def _contagens(db_path):
    with _conn(db_path) as c:
        d = c.execute("SELECT COUNT(*) AS n FROM dispensacoes").fetchone()["n"]
        e = c.execute("SELECT COUNT(*) AS n FROM estornos").fetchone()["n"]
    return d, e


# --------------------------------------------------------------------------- 2xx + cabeçalho

def test_csv_2xx_e_cabecalho(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 3)

    rows = _csv_rows(dispensador)
    linha = next(r for r in rows if r["protocolo_prescricao"] == proto)
    assert linha["tipo_movimento"] == "dispensacao"
    assert linha["medicamento"] == "AMOXICILINA"
    assert linha["quantidade"] == "3"
    assert linha["saldo_efetivo_item"] == "3"
    assert linha["data_movimento"]              # datetime normalizada, não vazia


# --------------------------------------------------------------------------- §5.1

def test_csv_isolado_por_cnpj(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto, _CNPJ)
    _dispensar(dispensador, proto, item_id, 2)

    # Farmácia B (outro CNPJ via JWT forjado) não vê o movimento de A.
    from app.main import app
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"role": "dispensador", "sub": _CNPJ_OUTRO}
    try:
        r = dispensador._inner.get("/dispensadores/relatorio.csv")
        assert r.status_code == 200, r.text
        rows = list(csv.DictReader(io.StringIO(r.text)))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert all(row["protocolo_prescricao"] != proto for row in rows)


# --------------------------------------------------------------------------- §5.2

def test_csv_dispensacao_e_estorno_duas_linhas_saldo_reposto(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 3)

    r = dispensador.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"})
    assert r.status_code == 201, r.text

    rows = [x for x in _csv_rows(dispensador) if x["protocolo_prescricao"] == proto]
    por_tipo = {x["tipo_movimento"]: x for x in rows}
    assert set(por_tipo) == {"dispensacao", "estorno"}          # 2 linhas
    assert por_tipo["dispensacao"]["saldo_efetivo_item"] == "3"
    assert por_tipo["estorno"]["saldo_efetivo_item"] == "0"     # reposto
    assert por_tipo["estorno"]["estorno_protocolo"]            # protocolo presente
    assert por_tipo["estorno"]["motivo_estorno"] == "outro"


def test_relatorio_e_read_only(prescritor, dispensador, db_path):
    """Gerar o relatório (CSV e PDF) não altera dispensacoes/estornos."""
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 3)
    antes = _contagens(db_path)

    _csv_rows(dispensador)
    r = dispensador.get("/dispensadores/relatorio.pdf")
    assert r.status_code == 200, r.text

    assert _contagens(db_path) == antes                         # nada inserido/alterado


# --------------------------------------------------------------------------- §5.3

def test_csv_comprador_declarado_vs_paciente(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 2, comprador="MARIA PORTADORA", doc="22233344455")

    linha = next(x for x in _csv_rows(dispensador) if x["protocolo_prescricao"] == proto)
    assert linha["comprador_nome"] == "MARIA PORTADORA"
    assert linha["comprador_documento"] == "22233344455"
    assert linha["comprador_eh_paciente"] == "nao"


def test_csv_sem_comprador_eh_paciente(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 2)

    linha = next(x for x in _csv_rows(dispensador) if x["protocolo_prescricao"] == proto)
    assert linha["comprador_eh_paciente"] == "sim"
    assert linha["comprador_nome"] == linha["paciente_nome"]


# --------------------------------------------------------------------------- §5.4

def test_csv_exclui_cpf_sentinela(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 3)

    # Marca o paciente com o CPF sentinela — a linha deve sumir do relatório.
    with _conn(db_path) as c:
        c.execute("UPDATE pacientes SET cpf='00000000000' WHERE cpf='12345678901'")
        c.commit()

    rows = _csv_rows(dispensador)
    assert all(row["paciente_cpf"] != "00000000000" for row in rows)
    assert all(row["protocolo_prescricao"] != proto for row in rows)


# --------------------------------------------------------------------------- §5.5

def test_csv_nao_expoe_endereco(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 1)

    r = dispensador.get("/dispensadores/relatorio.csv")
    header = r.text.splitlines()[0].lower()
    assert "endereco" not in header and "end_" not in header


# --------------------------------------------------------------------------- §5.8 (PDF)

def test_pdf_2xx(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _pid, item_id = _seed_custodia(db_path, proto)
    _dispensar(dispensador, proto, item_id, 3)

    r = dispensador.get("/dispensadores/relatorio.pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


# --------------------------------------------------------------------------- role/auth

def test_relatorio_exige_role_dispensador(paciente, db_path):
    r = paciente.get("/dispensadores/relatorio.csv")
    assert r.status_code == 403, r.text


def test_data_invalida_422(dispensador, db_path):
    r = dispensador.get("/dispensadores/relatorio.csv", params={"data_inicio": "10-07-2026"})
    assert r.status_code == 422, r.text
