"""conftest.py — Fixtures para testes de integração (Camada 2)."""
from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

# Nota: sys.path é configurado pelo conftest.py raiz em backend/
# (carregado pelo pytest antes deste arquivo)


def _init_schema(db_path: str) -> None:
    from app.database import Base
    import app.models  # noqa
    from init_tables import aplicar_triggers_ledger
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    eng.dispose()
    aplicar_triggers_ledger(db_path)


def _make_get_conn(db_path: str):
    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return _get_conn


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "picsaude_test.db")
    _init_schema(path)
    return path


class RoleClient:
    """
    Wrapper sobre TestClient que redefine o role antes de cada request HTTP.

    Necessário porque múltiplos fixtures compartilham o mesmo app e
    dependency_overrides é global — o último a escrever ganha.
    Ao chamar .post() / .get(), este wrapper garante que o override
    correto está ativo para este cliente antes de despachar a request.
    """

    def __init__(self, inner: TestClient, role: str):
        self._inner = inner
        self._role = role

    def _activate(self):
        from app.main import app
        from app.auth.dependencies import get_current_user
        role = self._role
        app.dependency_overrides[get_current_user] = lambda: {"role": role, "sub": "test"}

    def post(self, *args, **kwargs):
        self._activate()
        return self._inner.post(*args, **kwargs)

    def get(self, *args, **kwargs):
        self._activate()
        return self._inner.get(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._activate()
        return self._inner.delete(*args, **kwargs)

    def put(self, *args, **kwargs):
        self._activate()
        return self._inner.put(*args, **kwargs)

    def patch(self, *args, **kwargs):
        self._activate()
        return self._inner.patch(*args, **kwargs)


def _build_shared_client(db_path: str) -> TestClient:
    """Cria um único TestClient com get_conn patchado para o banco de teste."""
    from app.main import app
    gc = _make_get_conn(db_path)
    stack = ExitStack()
    for target in [
        "app.routers.prescricoes.get_conn",
        "app.routers.custodia.get_conn",
        "app.routers.dispensacoes.get_conn",
        "app.routers.tokens.get_conn",
        "app.routers.hospitalares.get_conn",   # Ticket 27
        "app.routers.agendamentos.get_conn",   # Ticket 29
        "app.routers.pedidos_exame.get_conn",  # Ticket 29 (integração)
        "app.routers.auth.get_conn",           # Ticket 29 (carteira exames)
        "app.routers.eventos.get_conn",                     # G4A — event publishing layer
        "app.routers.circulacao_diagnostica.get_conn",      # Ticket 53
    ]:
        stack.enter_context(patch(target, gc))
    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()
    client._test_stack = stack
    return client


def _teardown(client: TestClient) -> None:
    from app.main import app
    client.__exit__(None, None, None)
    client._test_stack.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def _shared_client(db_path):
    """TestClient compartilhado entre roles no mesmo teste."""
    c = _build_shared_client(db_path)
    yield c
    _teardown(c)


@pytest.fixture()
def prescritor(_shared_client):
    return RoleClient(_shared_client, "prescritor")


@pytest.fixture()
def dispensador(_shared_client):
    return RoleClient(_shared_client, "dispensador")


@pytest.fixture()
def paciente(_shared_client):
    """Paciente com CPF = 12345678901 (bate com cpf_paciente do PAYLOAD_PADRAO)."""

    class _PacienteClient(RoleClient):
        def _activate(self):
            from app.main import app
            from app.auth.dependencies import get_current_user
            app.dependency_overrides[get_current_user] = lambda: {
                "role": "paciente",
                "sub": "12345678901",
            }

    return _PacienteClient(_shared_client, "paciente")


@pytest.fixture()
def outro_paciente(_shared_client):
    """Paciente diferente — CPF = 99999999999 (não tem prescrições)."""

    class _OtherPatient(RoleClient):
        def _activate(self):
            from app.main import app
            from app.auth.dependencies import get_current_user
            app.dependency_overrides[get_current_user] = lambda: {
                "role": "paciente",
                "sub": "99999999999",
            }

    return _OtherPatient(_shared_client, "paciente")


# ---------------------------------------------------------------------------
# Payloads reutilizáveis
# ---------------------------------------------------------------------------

PAYLOAD_PADRAO = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Teste",
    "tipo_emissao": "nova",
    "itens": [
        {
            "nome_medicamento": "AMOXICILINA",
            "concentracao": "500mg",
            "quantidade": 10,
            "posologia": "1 capsula 3x ao dia",
        }
    ],
}

PAYLOAD_DOIS_ITENS = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Teste",
    "tipo_emissao": "nova",
    "itens": [
        {
            "nome_medicamento": "AMOXICILINA",
            "concentracao": "500mg",
            "quantidade": 10,
            "posologia": "1 capsula 3x ao dia",
        },
        {
            "nome_medicamento": "IBUPROFENO",
            "concentracao": "400mg",
            "quantidade": 6,
            "posologia": "1 comprimido 2x ao dia",
        },
    ],
}

PAYLOAD_FISICA = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "nome_paciente": "Paciente Fisico",
    "itens": [
        {
            "nome_medicamento": "DIPIRONA",
            "concentracao": "500mg",
            "quantidade": 4,
        }
    ],
}

PAYLOAD_DISPENSA = {
    "cnpj_estabelecimento": "12345678000195",
    "quantidade_dispensada": 5,
    "dispensado_por": "Farmaceutico Teste",
}

PAYLOAD_PEDIDO = {
    "cns_prescritor":  "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente":    "12345678901",
    "nome_paciente":   "Paciente Teste",
    "tipo_emissao":    "novo",
    "itens": [
        {
            "nome_exame":  "Hemograma Completo",
            "quantidade":  1,
        }
    ],
}

PAYLOAD_AGENDAR = {
    "data_hora":        "2026-05-15T09:00:00",
    "org_id":           "LAB-TESTE",
    "unidade_id":       "UNIDADE-001",
    "tipo_agendamento": "exame",
}
