"""
test_tokens_apresentacao.py
===========================
Testes unitários e de integração — Token de Apresentação (Ticket 24).

COBERTURA
---------
  1. Helpers: geração de código Crockford, lógica de expiração
  2. POST /tokens/apresentacao       — paciente gera
  3. GET  /tokens/apresentacao       — paciente lista
  4. DELETE /tokens/apresentacao/... — paciente revoga (inclui isolamento)
  5. GET  /tokens/apresentacao/.../qr — QR Code PNG
  6. POST /tokens/apresentacao/resolver
     a. token válido → retorna protocolo + itens
     b. token não encontrado
     c. token revogado
     d. token multiuso (mesmo código resolvível N vezes)
     e. isolamento de role (paciente não resolve)

Banco em memória via tmp_path (conftest.py).
CPF do paciente = "12345678901" (bate com PAYLOAD_PADRAO.cpf_paciente).
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.routers.tokens import _esta_expirado, _gerar_codigo_curto, _CROCKFORD, _CODIGO_LEN
from tests.conftest import PAYLOAD_PADRAO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def proto(prescritor):
    """Cria prescrição digital e retorna o protocolo."""
    r = prescritor.post("/prescricoes", json=PAYLOAD_PADRAO)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ---------------------------------------------------------------------------
# 1. Helpers unitários
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_codigo_tamanho(self, db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        codigo = _gerar_codigo_curto(conn)
        conn.close()
        assert len(codigo) == _CODIGO_LEN

    def test_codigo_alphabet_crockford(self, db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for _ in range(20):
            codigo = _gerar_codigo_curto(conn)
            assert all(c in _CROCKFORD for c in codigo)
        conn.close()

    def test_sem_chars_ambiguos(self, db_path):
        """I, L, O, U não devem aparecer no alfabeto Crockford."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for _ in range(30):
            codigo = _gerar_codigo_curto(conn)
            for c in ("I", "L", "O", "U"):
                assert c not in codigo
        conn.close()

    def test_esta_expirado_passado(self):
        passado = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert _esta_expirado(passado) is True

    def test_esta_expirado_futuro(self):
        futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert _esta_expirado(futuro) is False

    def test_esta_expirado_invalido(self):
        assert _esta_expirado("nao-e-data") is True

    def test_esta_expirado_none(self):
        assert _esta_expirado(None) is True


# ---------------------------------------------------------------------------
# 2. POST /tokens/apresentacao — geração
# ---------------------------------------------------------------------------

class TestGerar:

    def test_sucesso(self, paciente, proto):
        r = paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        assert r.status_code == 201
        data = r.json()
        assert len(data["codigo_curto"]) == _CODIGO_LEN
        assert data["escopo"] == "apresentacao"
        assert data["status"] == "ativo"
        assert "expira_em" in data
        assert "aviso" in data

    def test_protocolo_inexistente(self, paciente):
        r = paciente.post("/tokens/apresentacao", json={"protocolo": "nao-existe"})
        assert r.status_code == 404

    def test_validade_acima_do_limite(self, paciente, proto):
        r = paciente.post(
            "/tokens/apresentacao",
            json={"protocolo": proto, "validade_minutos": 999},
        )
        assert r.status_code == 422

    def test_validade_zero(self, paciente, proto):
        r = paciente.post(
            "/tokens/apresentacao",
            json={"protocolo": proto, "validade_minutos": 0},
        )
        assert r.status_code == 422

    def test_validade_customizada(self, paciente, proto):
        r = paciente.post(
            "/tokens/apresentacao",
            json={"protocolo": proto, "validade_minutos": 30},
        )
        assert r.status_code == 201

    def test_outro_paciente_nao_gera(self, outro_paciente, proto):
        r = outro_paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        assert r.status_code == 403

    def test_multiplos_tokens_mesmo_proto(self, paciente, proto):
        """Mesma prescrição aceita múltiplos tokens simultâneos."""
        r1 = paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        r2 = paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["codigo_curto"] != r2.json()["codigo_curto"]


# ---------------------------------------------------------------------------
# 3. GET /tokens/apresentacao — listagem
# ---------------------------------------------------------------------------

class TestListar:

    def test_lista_vazia_inicial(self, paciente):
        r = paciente.get("/tokens/apresentacao")
        assert r.status_code == 200
        assert isinstance(r.json()["tokens"], list)

    def test_lista_apos_criacao(self, paciente, proto):
        paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        r = paciente.get("/tokens/apresentacao")
        tokens = r.json()["tokens"]
        assert any(t["protocolo"] == proto for t in tokens)

    def test_nao_lista_tokens_de_outro_paciente(self, paciente, outro_paciente, proto):
        paciente.post("/tokens/apresentacao", json={"protocolo": proto})
        r = outro_paciente.get("/tokens/apresentacao")
        tokens = r.json()["tokens"]
        # outro_paciente não deve ver tokens do paciente principal
        assert not any(t["protocolo"] == proto for t in tokens)


# ---------------------------------------------------------------------------
# 4. DELETE /tokens/apresentacao/{codigo} — revogação
# ---------------------------------------------------------------------------

class TestRevogar:

    def test_revogar_sucesso(self, paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = paciente.delete(f"/tokens/apresentacao/{codigo}")
        assert r.status_code == 200
        assert "revogado" in r.json()["detail"].lower()

    def test_revogar_idempotente(self, paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        paciente.delete(f"/tokens/apresentacao/{codigo}")
        r2 = paciente.delete(f"/tokens/apresentacao/{codigo}")
        assert r2.status_code == 200

    def test_outro_paciente_nao_revoga(self, paciente, outro_paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = outro_paciente.delete(f"/tokens/apresentacao/{codigo}")
        assert r.status_code == 403

    def test_revogar_inexistente(self, paciente):
        r = paciente.delete("/tokens/apresentacao/XXXXXXXX")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 5. GET /tokens/apresentacao/{codigo}/qr — QR Code
# ---------------------------------------------------------------------------

class TestQr:

    def test_retorna_png(self, paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = paciente.get(f"/tokens/apresentacao/{codigo}/qr")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 100

    def test_inexistente_404(self, paciente):
        r = paciente.get("/tokens/apresentacao/XXXXXXXX/qr")
        assert r.status_code == 404

    def test_outro_paciente_403(self, paciente, outro_paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = outro_paciente.get(f"/tokens/apresentacao/{codigo}/qr")
        assert r.status_code == 403

    def test_revogado_410(self, paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        paciente.delete(f"/tokens/apresentacao/{codigo}")
        r = paciente.get(f"/tokens/apresentacao/{codigo}/qr")
        assert r.status_code == 410


# ---------------------------------------------------------------------------
# 6. POST /tokens/apresentacao/resolver — dispensador
# ---------------------------------------------------------------------------

class TestResolver:

    def test_resolver_sucesso(self, paciente, dispensador, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["protocolo"] == proto
        assert "status_prescricao" in data
        assert "itens_pendentes" in data
        assert isinstance(data["itens_pendentes"], list)
        assert "aviso" in data

    def test_resolver_case_insensitive(self, paciente, dispensador, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo.lower()},
        )
        assert r.status_code == 200

    def test_resolver_nao_encontrado(self, dispensador):
        r = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": "XXXXXXXX"},
        )
        assert r.status_code == 404

    def test_resolver_revogado(self, paciente, dispensador, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        paciente.delete(f"/tokens/apresentacao/{codigo}")
        r = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo},
        )
        assert r.status_code == 410

    def test_resolver_multiuso(self, paciente, dispensador, proto):
        """Token pode ser resolvido múltiplas vezes enquanto válido."""
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r1 = dispensador.post(
            "/tokens/apresentacao/resolver", json={"codigo_curto": codigo}
        )
        r2 = dispensador.post(
            "/tokens/apresentacao/resolver", json={"codigo_curto": codigo}
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_paciente_nao_resolve(self, paciente, proto):
        codigo = paciente.post(
            "/tokens/apresentacao", json={"protocolo": proto}
        ).json()["codigo_curto"]
        r = paciente.post(
            "/tokens/apresentacao/resolver", json={"codigo_curto": codigo}
        )
        assert r.status_code == 403
