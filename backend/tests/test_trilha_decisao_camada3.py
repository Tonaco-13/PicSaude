"""
test_trilha_decisao_camada3.py — trilha de auditoria da decisão clínica.
=========================================================================
Camada 3 da explicabilidade do semáforo: na EMISSÃO de uma prescrição, grava o
evento `decisao_clinica_avaliada` no ledger imutável (`prescricao_eventos`) com
o sinal do semáforo + a versão da regra, por item.

Invariantes cobertas:
  - grava o evento com sinal/causa/versao por item (🟢/🟡);
  - cada avaliação aponta para o item_id real;
  - NÃO grava com a flag desligada (nada foi apresentado);
  - NÃO grava sem codigo_cid (não havia indicação a validar);
  - NÃO-BLOQUEANTE: se a montagem da trilha falhar, a emissão segue (201).

Reaproveita as fixtures `prescritor` e `db_path` do conftest (TestClient+SQLite).
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import app.routers.prescricoes as pr
from app.domain.auditoria_decisao import TIPO_EVENTO_DECISAO, montar_trilha_decisao
from app.domain.semaforo_decisao import SINAL_AMARELO, SINAL_NEUTRO, SINAL_VERDE

# captopril ∈ lista exaustiva de I10 → 🟢 ; amoxicilina fora → 🟡
_ITEM_VERDE = {"nome_medicamento": "captopril", "concentracao": "25mg",
               "quantidade": 30, "posologia": "1x ao dia"}
_ITEM_AMARELO = {"nome_medicamento": "amoxicilina", "concentracao": "500mg",
                 "quantidade": 10, "posologia": "3x ao dia"}

_BASE = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Trilha",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Trilha",
    "tipo_emissao": "nova",
}


def _payload(**overrides) -> dict:
    p = {**_BASE, "itens": [_ITEM_VERDE, _ITEM_AMARELO]}
    p.update(overrides)
    return p


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _evento_decisao(db_path: str, protocolo: str):
    with _conn(db_path) as c:
        row = c.execute(
            """
            SELECT pe.payload_json
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = ? AND pe.tipo_evento = ?
            """,
            (protocolo, TIPO_EVENTO_DECISAO),
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None


@pytest.fixture
def flag_on(monkeypatch):
    """Liga o semáforo no router e força o recarregamento das regras curadas
    (CSV padrão — I10 exaustiva)."""
    import app.domain.semaforo_decisao as sd
    monkeypatch.setattr(pr, "PICSAUDE_DECISAO_CLINICA", True)
    monkeypatch.setattr(sd, "_REGRAS_CACHE", None)
    yield


# ---------------------------------------------------------------------------
# Helper puro — montar_trilha_decisao (sem banco)
# ---------------------------------------------------------------------------

class TestHelperTrilha:

    def test_monta_avaliacoes_com_versao_por_item(self, flag_on):
        p = montar_trilha_decisao("I10", [(10, "captopril"), (20, "amoxicilina")])
        assert p["codigo_cid"] == "I10"
        por_canon = {a["principio_ativo_canonico"]: a for a in p["avaliacoes"]}
        assert por_canon["captopril"]["sinal"] == SINAL_VERDE
        assert por_canon["captopril"]["item_id"] == 10
        assert por_canon["captopril"]["versao_regra"]          # versão registrada
        assert por_canon["amoxicilina"]["sinal"] == SINAL_AMARELO

    def test_neutro_quando_sem_cid(self, flag_on):
        p = montar_trilha_decisao(None, [(1, "captopril")])
        assert p["avaliacoes"][0]["sinal"] == SINAL_NEUTRO
        assert p["avaliacoes"][0]["versao_regra"] is None


# ---------------------------------------------------------------------------
# Integração — hook na emissão
# ---------------------------------------------------------------------------

class TestTrilhaNaEmissao:

    def test_grava_evento_com_sinais_e_versao(self, prescritor, db_path, flag_on):
        r = prescritor.post("/prescricoes", json=_payload(codigo_cid="I10"))
        assert r.status_code == 201
        ev = _evento_decisao(db_path, r.json()["protocolo"])
        assert ev is not None, "evento decisao_clinica_avaliada não foi gravado"
        assert ev["codigo_cid"] == "I10"
        por_canon = {a["principio_ativo_canonico"]: a for a in ev["avaliacoes"]}
        assert por_canon["captopril"]["sinal"] == SINAL_VERDE
        assert por_canon["amoxicilina"]["sinal"] == SINAL_AMARELO
        assert por_canon["captopril"]["versao_regra"]            # auditável no tempo
        assert all(isinstance(a["item_id"], int) for a in ev["avaliacoes"])

    def test_flag_off_nao_grava(self, prescritor, db_path, monkeypatch):
        monkeypatch.setattr(pr, "PICSAUDE_DECISAO_CLINICA", False)
        r = prescritor.post("/prescricoes", json=_payload(codigo_cid="I10"))
        assert r.status_code == 201
        assert _evento_decisao(db_path, r.json()["protocolo"]) is None

    def test_sem_cid_nao_grava(self, prescritor, db_path, flag_on):
        r = prescritor.post("/prescricoes", json=_payload())   # sem codigo_cid
        assert r.status_code == 201
        assert _evento_decisao(db_path, r.json()["protocolo"]) is None

    def test_nao_bloqueante_emissao_segue_se_trilha_falha(
        self, prescritor, db_path, flag_on, monkeypatch
    ):
        """Garantia central: a trilha NUNCA quebra a emissão. Se a montagem
        explode, a prescrição ainda é emitida (201) e nenhum evento é gravado."""
        def _boom(*a, **k):
            raise RuntimeError("falha simulada na trilha")
        monkeypatch.setattr(pr, "montar_trilha_decisao", _boom)
        r = prescritor.post("/prescricoes", json=_payload(codigo_cid="I10"))
        assert r.status_code == 201
        assert _evento_decisao(db_path, r.json()["protocolo"]) is None
