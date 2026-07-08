"""
test_estorno.py — T2: estorno de dispensação como objeto derivado imutável.
Harness SQLite (fixtures prescritor/dispensador/db_path do conftest).

Cobre: estorno completo + ledger duplo; estorno parcial que repõe saldo Σ e
permite redispensação (T7c); ownership por CNPJ (403); saldo estornável (422/409);
regras de `motivo`; imutabilidade do ledger do estorno.
"""
from __future__ import annotations

import sqlite3

import pytest

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


def _seed_custodia(db_path, proto, cnpj=_CNPJ):
    """Custódia ativa do dispensador + item em_custodia. Retorna (presc_id, item_id)."""
    with _conn(db_path) as c:
        presc_id = c.execute("SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)).fetchone()["id"]
        item_id = c.execute(
            "SELECT id FROM prescricao_itens WHERE prescricao_id = ? LIMIT 1", (presc_id,)
        ).fetchone()["id"]
        now = "2026-07-08T00:00:00"
        c.execute(
            """INSERT INTO prescricao_custodia
                 (prescricao_id, item_id, detentor_tipo, detentor_id,
                  transferida_em, encerrada_em, motivo, created_at)
               VALUES (?, ?, 'dispensador', ?, ?, NULL, 'seed-t2', ?)""",
            (presc_id, item_id, cnpj, now, now),
        )
        c.execute("UPDATE prescricao_itens SET status_item='em_custodia' WHERE id=?", (item_id,))
        c.commit()
    return presc_id, item_id


def _dispensar(dispensador, proto, item_id, qtd, cnpj=_CNPJ):
    r = dispensador.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": cnpj, "quantidade_dispensada": qtd},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cli_dispensador(shared, cnpj):
    """RoleClient dispensador com sub arbitrário (para testar ownership entre CNPJs)."""
    from tests.conftest import RoleClient

    class _D(RoleClient):
        def _activate(self):
            from app.main import app
            from app.auth.dependencies import get_current_user
            app.dependency_overrides[get_current_user] = lambda: {"role": "dispensador", "sub": cnpj}

    return _D(shared, "dispensador")


def test_dispensar_expoe_dispensacao_id(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _, item_id = _seed_custodia(db_path, proto)
    disp = _dispensar(dispensador, proto, item_id, 5)
    assert disp["dispensacao_id"], "dispensar_item deve expor o dispensacao_id (pré-requisito do estorno)"


def test_estorno_completo_e_ledger_duplo(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    presc_id, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 5)["dispensacao_id"]

    r = dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 5, "motivo": "desistencia"},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["quantidade_estornada"] == 5
    assert d["saldo_estornavel_restante"] == 0
    assert d["protocolo_estorno"] and d["documento_hash"]

    with _conn(db_path) as c:
        # dispensacoes INTOCADA
        assert c.execute("SELECT quantidade_dispensada FROM dispensacoes WHERE id=?",
                         (disp_id,)).fetchone()["quantidade_dispensada"] == 5
        # item PERMANECE dispensado ou em_custodia — nunca 'estornado'
        st = c.execute(
            "SELECT status_item FROM prescricao_itens WHERE id=?", (item_id,)
        ).fetchone()["status_item"]
        assert st != "estornado"
        # objeto derivado
        est = c.execute("SELECT * FROM estornos WHERE origem_dispensacao_id=?", (disp_id,)).fetchone()
        assert est["quantidade_estornada"] == 5 and est["motivo"] == "desistencia"
        # ledger DUPLO
        ev_est = [x["tipo_evento"] for x in c.execute(
            "SELECT tipo_evento FROM estorno_eventos WHERE estorno_id=?", (est["id"],)).fetchall()]
        assert "estorno_registrado" in ev_est
        ev_presc = [x["tipo_evento"] for x in c.execute(
            "SELECT tipo_evento FROM prescricao_eventos WHERE prescricao_id=?", (presc_id,)).fetchall()]
        assert "dispensacao_estornada" in ev_presc


def test_estorno_parcial_repoe_saldo_e_redispensa(prescritor, dispensador, db_path):
    """T7c — estorno parcial repõe saldo Σ efetivo e o item volta a ser dispensável."""
    proto = _emitir(prescritor)
    _, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 5)["dispensacao_id"]  # 5/10, em_custodia

    r = dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 3, "motivo": "falha_pagamento"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["saldo_estornavel_restante"] == 2

    # saldo efetivo = 10 − (5 − 3) = 8 → nova dispensação de 8 fecha o item
    disp2 = _dispensar(dispensador, proto, item_id, 8)
    assert disp2["saldo_restante"] == 0
    assert disp2["status_item"] == "dispensado"


def test_estorno_de_outro_cnpj_403(prescritor, dispensador, _shared_client, db_path):
    proto = _emitir(prescritor)
    _, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 5)["dispensacao_id"]

    outro = _cli_dispensador(_shared_client, _CNPJ_OUTRO)
    r = outro.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "desistencia"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_da_dispensacao"


def test_estorno_supera_saldo_422_e_ja_estornada_409(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 5)["dispensacao_id"]

    r = dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 6, "motivo": "desistencia"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "quantidade_supera_saldo_estornavel"

    assert dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 5, "motivo": "desistencia"},
    ).status_code == 201

    r2 = dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "desistencia"},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["codigo"] == "dispensacao_ja_estornada"


def test_estorno_motivo_invalido_e_outro_sem_detalhe(prescritor, dispensador, db_path):
    proto = _emitir(prescritor)
    _, item_id = _seed_custodia(db_path, proto)
    disp_id = _dispensar(dispensador, proto, item_id, 5)["dispensacao_id"]

    # fora do enum → 422 (Pydantic)
    assert dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "qualquer"},
    ).status_code == 422

    # 'outro' sem detalhe → 422 (regra de negócio)
    r = dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "outro"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "motivo_detalhe_obrigatorio"

    # 'outro' com detalhe → 201
    assert dispensador.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "outro", "motivo_detalhe": "erro de digitação"},
    ).status_code == 201


def test_estorno_dispensacao_inexistente_404(dispensador, db_path):
    r = dispensador.post(
        "/dispensacoes/999999/estornar",
        json={"quantidade_estornada": 1, "motivo": "desistencia"},
    )
    assert r.status_code == 404, r.text


def test_estorno_eventos_imutavel(db_path):
    """Ledger do estorno é INSERT-only — UPDATE/DELETE bloqueados por trigger."""
    c = sqlite3.connect(db_path)
    try:
        c.execute(
            "INSERT INTO estorno_eventos (estorno_id, tipo_evento, ator_tipo, created_at) "
            "VALUES (1, 'estorno_registrado', 'dispensador', '2026-07-08')"
        )
        c.commit()
        for stmt in (
            "UPDATE estorno_eventos SET tipo_evento='x' WHERE estorno_id=1",
            "DELETE FROM estorno_eventos WHERE estorno_id=1",
        ):
            with pytest.raises(sqlite3.Error):
                c.execute(stmt)
            c.rollback()
    finally:
        c.close()
