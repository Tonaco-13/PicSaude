"""
test_auth_paciente.py
=====================
Testes para o fluxo de autenticação OTP do cidadão.

Cobre:
  - POST /auth/paciente/solicitar-codigo  (login.py)
  - POST /auth/paciente/validar-codigo    (login.py)
  - GET  /pacientes/me                    (pacientes.py)
  - GET  /pacientes                       (pacientes.py — bloqueado)

Estratégia:
  - Os endpoints OTP não usam dependency_overrides — testados no fluxo real.
  - get_conn é patchado via monkeypatch para apontar ao banco de teste.
  - O OTP é lido diretamente do banco após solicitar, sem expô-lo na resposta.
"""
from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.main import app
from app.auth.dependencies import get_current_user, get_current_user_or_api_key
from app.database import get_conn

_PACIENTE_CPF = "12345678901"
_OUTRO_CPF    = "98765432100"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_schema(db_path: str) -> None:
    from app.database import Base
    import app.models  # noqa
    eng = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    eng.dispose()


def _make_get_conn(db_path: str):
    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return _get_conn


def _get_otp(cpf: str, db_path: str) -> str | None:
    """Lê o OTP mais recente não-utilizado do banco de teste."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT codigo FROM codigos_login WHERE cpf=? AND usado=0 ORDER BY id DESC LIMIT 1",
            (cpf,),
        ).fetchone()
        return row["codigo"] if row else None
    finally:
        conn.close()


_LOGIN_TARGETS = [
    "app.routers.login.get_conn",
    "app.routers.pacientes.get_conn",
    "app.routers.auth.get_conn",
    "app.routers.prescricoes.get_conn",
    "app.routers.custodia.get_conn",
    "app.routers.dispensacoes.get_conn",
    "app.routers.tokens.get_conn",
    "app.routers.hospitalares.get_conn",
    "app.routers.agendamentos.get_conn",
    "app.routers.pedidos_exame.get_conn",
    "app.routers.eventos.get_conn",
]


@pytest.fixture()
def auth_db_path(tmp_path):
    path = str(tmp_path / "auth_test.db")
    _init_schema(path)
    return path


@pytest.fixture()
def auth_client(auth_db_path):
    gc = _make_get_conn(auth_db_path)
    stack = ExitStack()
    for target in _LOGIN_TARGETS:
        stack.enter_context(patch(target, gc))
    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()
    yield client, auth_db_path
    client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Classe 1: POST /auth/paciente/solicitar-codigo
# ---------------------------------------------------------------------------

class TestSolicitarCodigo:

    def test_solicitar_cpf_valido_retorna_200(self, auth_client):
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        assert resp.status_code == 200

    def test_solicitar_retorna_ok_true(self, auth_client):
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        assert resp.json()["ok"] is True

    def test_solicitar_nao_expoe_dev_codigo(self, auth_client):
        """dev_codigo NÃO deve aparecer na resposta — segurança."""
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        data = resp.json()
        assert "dev_codigo" not in data

    def test_solicitar_nao_expoe_codigo_teste(self, auth_client):
        """codigo_teste NÃO deve aparecer na resposta."""
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        data = resp.json()
        assert "codigo_teste" not in data
        assert "codigo" not in data

    def test_solicitar_nao_expoe_codigo_na_mensagem(self, auth_client):
        """Mensagem de retorno não deve conter dígitos do OTP."""
        client, db_path = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        otp = _get_otp(_PACIENTE_CPF, db_path)
        assert otp is not None
        # OTP não deve aparecer no corpo da resposta
        assert otp not in resp.text

    def test_solicitar_cpf_vazio_retorna_400(self, auth_client):
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": ""})
        assert resp.status_code == 400

    def test_solicitar_cpf_invalido_retorna_400(self, auth_client):
        client, _ = auth_client
        resp = client.post("/auth/paciente/solicitar-codigo", json={"cpf": "abc"})
        assert resp.status_code == 400

    def test_solicitar_cria_paciente_se_nao_existir(self, auth_client):
        """Deve criar registro em pacientes para CPF novo."""
        client, db_path = auth_client
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT cpf FROM pacientes WHERE cpf = ?", (_PACIENTE_CPF,)
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_solicitar_grava_otp_no_banco(self, auth_client):
        """OTP deve ser persistido em codigos_login."""
        client, db_path = auth_client
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        otp = _get_otp(_PACIENTE_CPF, db_path)
        assert otp is not None
        assert len(otp) == 6
        assert otp.isdigit()

    def test_solicitar_multiplas_vezes_ultimo_codigo_funciona(self, auth_client):
        """Múltiplas solicitações — o código mais recente deve ser válido."""
        client, db_path = auth_client
        # Solicita duas vezes
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        # O OTP mais recente deve existir
        otp = _get_otp(_PACIENTE_CPF, db_path)
        assert otp is not None
        # Validar com o OTP mais recente deve funcionar
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Classe 2: POST /auth/paciente/validar-codigo
# ---------------------------------------------------------------------------

class TestValidarCodigo:

    def _solicitar_e_obter_otp(self, client, db_path, cpf=_PACIENTE_CPF):
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": cpf})
        return _get_otp(cpf, db_path)

    def test_validar_codigo_correto_retorna_200(self, auth_client):
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        assert resp.status_code == 200

    def test_validar_retorna_access_token(self, auth_client):
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        data = resp.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_validar_retorna_token_type_bearer(self, auth_client):
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        assert resp.json()["token_type"] == "bearer"

    def test_validar_retorna_cpf_e_nome(self, auth_client):
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        data = resp.json()
        assert data["cpf"] == _PACIENTE_CPF
        assert "nome" in data
        assert isinstance(data["nome"], str)

    def test_validar_token_tem_role_paciente(self, auth_client):
        """Token emitido deve ter role=paciente no payload."""
        import base64, json as _json
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        token = resp.json()["access_token"]
        # Decodificar payload JWT (sem verificar assinatura)
        payload_b64 = token.split(".")[1]
        # Corrigir padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = _json.loads(base64.b64decode(payload_b64))
        assert payload.get("role") == "paciente"

    def test_validar_codigo_errado_retorna_401(self, auth_client):
        client, db_path = auth_client
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": "000000"},
        )
        assert resp.status_code == 401

    def test_validar_codigo_cpf_errado_retorna_401(self, auth_client):
        """Código válido mas CPF errado deve falhar."""
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _OUTRO_CPF, "codigo": otp},
        )
        assert resp.status_code == 401

    def test_validar_codigo_reutilizado_retorna_401(self, auth_client):
        """Código já utilizado não pode ser reutilizado."""
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        # Primeira validação
        resp1 = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        assert resp1.status_code == 200
        # Segunda validação com mesmo código
        resp2 = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        assert resp2.status_code == 401

    def test_validar_invalida_otp_apos_uso(self, auth_client):
        """OTP deve ser marcado como usado no banco após validação."""
        client, db_path = auth_client
        otp = self._solicitar_e_obter_otp(client, db_path)
        client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        # Não deve haver OTP não-usado para esse CPF
        otp_restante = _get_otp(_PACIENTE_CPF, db_path)
        assert otp_restante is None

    def test_validar_codigo_expirado_retorna_401(self, auth_client):
        """Código expirado deve ser rejeitado com 401."""
        client, db_path = auth_client
        # Inserir código já expirado diretamente no banco
        codigo_expirado = "555111"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Garantir que o paciente existe
            conn.execute(
                "INSERT OR IGNORE INTO pacientes (cpf, nome, created_at, updated_at, ativo) "
                "VALUES (?, 'PACIENTE', datetime('now'), datetime('now'), 0)",
                (_PACIENTE_CPF,),
            )
            # Inserir OTP com expiração no passado
            conn.execute(
                "INSERT INTO codigos_login (cpf, codigo, expiracao, usado, created_at) "
                "VALUES (?, ?, datetime('now', '-10 minutes'), 0, datetime('now'))",
                (_PACIENTE_CPF, codigo_expirado),
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": codigo_expirado},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Classe 3: POST /paciente/enviar-codigo (endpoint legado em auth.py)
# ---------------------------------------------------------------------------

class TestEnviarCodigoLegado:

    def test_enviar_codigo_nao_expoe_dev_codigo(self, auth_client):
        """Endpoint legado também NÃO deve retornar dev_codigo."""
        client, _ = auth_client
        resp = client.post(
            "/paciente/enviar-codigo",
            json={"cpf": _PACIENTE_CPF},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dev_codigo" not in data

    def test_enviar_codigo_nao_expoe_codigo_na_resposta(self, auth_client):
        client, db_path = auth_client
        resp = client.post(
            "/paciente/enviar-codigo",
            json={"cpf": _PACIENTE_CPF},
        )
        assert resp.status_code == 200
        otp = _get_otp(_PACIENTE_CPF, db_path)
        assert otp is not None
        assert otp not in resp.text

    def test_enviar_codigo_retorna_ok(self, auth_client):
        client, _ = auth_client
        resp = client.post(
            "/paciente/enviar-codigo",
            json={"cpf": _PACIENTE_CPF},
        )
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Classe 4: GET /pacientes/me
# ---------------------------------------------------------------------------

class TestPacientesMe:

    def _obter_token_paciente(self, client, db_path, cpf=_PACIENTE_CPF):
        """Helper: solicita OTP, valida e retorna o access_token."""
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": cpf})
        otp = _get_otp(cpf, db_path)
        resp = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": cpf, "codigo": otp},
        )
        return resp.json()["access_token"]

    def test_me_sem_token_retorna_401(self, auth_client):
        client, _ = auth_client
        resp = client.get("/pacientes/me")
        assert resp.status_code == 401

    def test_me_com_token_prescritor_retorna_403(self, auth_client):
        """Token com role=prescritor não pode acessar /pacientes/me."""
        client, db_path = auth_client
        # Override para simular prescritor
        from app.auth.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "test_prescritor"}
        try:
            resp = client.get("/pacientes/me")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_me_com_token_paciente_retorna_200(self, auth_client):
        client, db_path = auth_client
        token = self._obter_token_paciente(client, db_path)
        resp = client.get(
            "/pacientes/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_me_retorna_cpf_do_proprio_paciente(self, auth_client):
        client, db_path = auth_client
        token = self._obter_token_paciente(client, db_path)
        resp = client.get(
            "/pacientes/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["cpf"] == _PACIENTE_CPF

    def test_me_nao_retorna_dados_de_outro_cpf(self, auth_client):
        """Paciente A não pode ver dados do Paciente B via /me."""
        client, db_path = auth_client
        # Registrar paciente B
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _OUTRO_CPF})
        _get_otp(_OUTRO_CPF, db_path)  # garantir que existe no banco

        # Obter token do paciente A
        token_a = self._obter_token_paciente(client, db_path, cpf=_PACIENTE_CPF)
        resp = client.get(
            "/pacientes/me",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        data = resp.json()
        # Deve retornar apenas dados do paciente A
        assert data["cpf"] == _PACIENTE_CPF
        assert data["cpf"] != _OUTRO_CPF


# ---------------------------------------------------------------------------
# Classe 5: GET /pacientes (listagem bloqueada)
# ---------------------------------------------------------------------------

class TestListagemPacientesBloqueada:

    def test_listar_sem_auth_retorna_403(self, auth_client):
        client, _ = auth_client
        resp = client.get("/pacientes")
        assert resp.status_code == 403

    def test_listar_com_auth_paciente_ainda_retorna_403(self, auth_client):
        """Nem com token de paciente a listagem deve ser acessível."""
        client, db_path = auth_client
        # Solicitar OTP e validar
        client.post("/auth/paciente/solicitar-codigo", json={"cpf": _PACIENTE_CPF})
        otp = _get_otp(_PACIENTE_CPF, db_path)
        resp_val = client.post(
            "/auth/paciente/validar-codigo",
            json={"cpf": _PACIENTE_CPF, "codigo": otp},
        )
        token = resp_val.json()["access_token"]
        resp = client.get(
            "/pacientes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
