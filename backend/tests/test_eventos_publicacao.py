"""
test_eventos_publicacao.py
==========================
Testes do G4A — Event Publishing Layer.

Cobertura:
  1. Outbox: evento criado via ação clínica aparece em /eventos
  2. Filtro por org_id
  3. Paginação (limite)
  4. ACK funciona
  5. ACK idempotente (ack duplo não gera erro)
  6. Evento não reaparece após ack (via incluir_consumidos=false)
  7. Eventos antigos continuam disponíveis (via incluir_consumidos=true)
  8. Filtro por objeto_tipo
  9. Filtro por desde (cursor)
  10. outbox.registrar_outbox direto — inserção correta
  11. outbox.registrar_outbox — falha silenciosa (princípio G4A)
  12. Endpoint requer role admin
  13. Retorno de total e proximo_cursor
  14. ACK em evento inexistente → 404
  15. Prescricao emitida → gera evento no outbox
  16. Agendamento criado → gera evento no outbox
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.domain.outbox import registrar_outbox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_schema(db_path: str) -> None:
    from app.database import Base
    import app.models  # noqa
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    eng.dispose()


def _make_get_conn(db_path: str):
    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return _get_conn


def _conn(db_path: str):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path_g4a(tmp_path):
    path = str(tmp_path / "g4a_test.db")
    _init_schema(path)
    return path


@pytest.fixture()
def admin_client(db_path_g4a):
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.main import app
    from app.auth.dependencies import get_current_user

    from app.auth.dependencies import get_current_user_or_api_key

    gc = _make_get_conn(db_path_g4a)
    stack = ExitStack()
    # database_tx.get_conn cobre eventos/agendamentos/pedidos_exame (usam get_tx).
    stack.enter_context(patch("app.database_tx.get_conn", gc))
    # prescricoes importa get_conn diretamente — patch específico necessário.
    stack.enter_context(patch("app.routers.prescricoes.get_conn", gc))

    _admin = {"role": "admin", "sub": "test"}
    app.dependency_overrides[get_current_user] = lambda: _admin
    # G4B: /eventos agora usa get_current_user_or_api_key
    app.dependency_overrides[get_current_user_or_api_key] = lambda: _admin

    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()
    yield client, db_path_g4a
    client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def paciente_client(db_path_g4a):
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.main import app
    from app.auth.dependencies import get_current_user

    from app.auth.dependencies import get_current_user_or_api_key

    gc = _make_get_conn(db_path_g4a)
    stack = ExitStack()
    # database_tx.get_conn cobre eventos (usa get_tx).
    stack.enter_context(patch("app.database_tx.get_conn", gc))

    _paciente = {"role": "paciente", "sub": "test"}
    app.dependency_overrides[get_current_user] = lambda: _paciente
    app.dependency_overrides[get_current_user_or_api_key] = lambda: _paciente

    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()
    yield client
    client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Testes de registrar_outbox (domínio)
# ---------------------------------------------------------------------------

class TestRegistrarOutbox:

    def test_insere_evento_corretamente(self, db_path_g4a):
        """outbox.registrar_outbox insere na tabela com campos corretos."""
        conn = _conn(db_path_g4a)
        payload = {"tipo": "teste", "valor": 42}
        evt_id = registrar_outbox(
            conn, "evento_teste", "prescricao", "proto-123", payload,
            org_id="ORG-X", unidade_id="UNIDADE-1",
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM eventos_publicacao WHERE id = ?", (evt_id,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["tipo_evento"]  == "evento_teste"
        assert row["objeto_tipo"]  == "prescricao"
        assert row["objeto_id"]    == "proto-123"
        assert row["org_id"]       == "ORG-X"
        assert row["unidade_id"]   == "UNIDADE-1"
        assert row["publicado"]    == 0
        assert row["tentativas"]   == 0
        assert row["publicado_em"] is None
        assert json.loads(row["payload"]) == payload

    def test_retorna_id_com_prefixo_evt(self, db_path_g4a):
        conn = _conn(db_path_g4a)
        evt_id = registrar_outbox(conn, "ev", "laudo", "uuid-abc", {})
        conn.commit()
        conn.close()
        assert evt_id.startswith("evt_")

    def test_falha_silenciosa_sem_tabela(self):
        """Falha no outbox não levanta exceção — princípio G4A §2.4."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Banco vazio sem tabela eventos_publicacao
        result = registrar_outbox(conn, "ev", "obj", "id", {})
        conn.close()
        assert result is None   # falhou silenciosamente

    def test_org_id_nulo_permitido(self, db_path_g4a):
        """Eventos de objetos sem escopo institucional têm org_id = NULL."""
        conn = _conn(db_path_g4a)
        evt_id = registrar_outbox(conn, "prescricao_emitida", "prescricao", "p1", {})
        conn.commit()
        row = conn.execute("SELECT org_id FROM eventos_publicacao WHERE id=?", (evt_id,)).fetchone()
        conn.close()
        assert row["org_id"] is None


# ---------------------------------------------------------------------------
# Testes de GET /eventos
# ---------------------------------------------------------------------------

class TestListarEventos:

    def _inserir_eventos(self, db_path, n=3, org="ORG-A"):
        conn = _conn(db_path)
        for i in range(n):
            registrar_outbox(conn, f"evento_{i}", "agendamento", f"proto-{i}", {"i": i}, org_id=org)
        conn.commit()
        conn.close()

    def test_retorna_lista_vazia_sem_eventos(self, admin_client):
        client, _ = admin_client
        r = client.get("/eventos")
        assert r.status_code == 200
        data = r.json()
        assert data["eventos"] == []
        assert data["total"] == 0
        assert data["proximo_cursor"] is None

    def test_retorna_eventos_inseridos(self, admin_client):
        client, db_path = admin_client
        self._inserir_eventos(db_path, n=3)
        r = client.get("/eventos")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_formato_canonico_do_evento(self, admin_client):
        client, db_path = admin_client
        conn = _conn(db_path)
        registrar_outbox(conn, "agendamento_realizado", "agendamento", "uuid-xyz",
                         {"k": "v"}, org_id="LAB", unidade_id="U1")
        conn.commit()
        conn.close()

        r = client.get("/eventos")
        ev = r.json()["eventos"][0]
        assert ev["tipo_evento"]        == "agendamento_realizado"
        assert ev["objeto"]["tipo"]     == "agendamento"
        assert ev["objeto"]["id"]       == "uuid-xyz"
        assert ev["org_id"]             == "LAB"
        assert ev["unidade_id"]         == "U1"
        assert ev["payload"]            == {"k": "v"}
        assert ev["publicado"]          is False
        assert "timestamp"              in ev
        assert ev["id"].startswith("evt_")

    def test_filtro_por_org_id(self, admin_client):
        client, db_path = admin_client
        conn = _conn(db_path)
        registrar_outbox(conn, "ev1", "agendamento", "p1", {}, org_id="ORG-A")
        registrar_outbox(conn, "ev2", "agendamento", "p2", {}, org_id="ORG-B")
        conn.commit()
        conn.close()

        r = client.get("/eventos?org_id=ORG-A")
        evs = r.json()["eventos"]
        assert len(evs) == 1
        assert evs[0]["org_id"] == "ORG-A"

    def test_filtro_por_objeto_tipo(self, admin_client):
        client, db_path = admin_client
        conn = _conn(db_path)
        registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        registrar_outbox(conn, "ev2", "prescricao", "p2", {})
        conn.commit()
        conn.close()

        r = client.get("/eventos?objeto_tipo=prescricao")
        evs = r.json()["eventos"]
        assert len(evs) == 1
        assert evs[0]["objeto"]["tipo"] == "prescricao"

    def test_limite_respeitado(self, admin_client):
        client, db_path = admin_client
        self._inserir_eventos(db_path, n=10)
        r = client.get("/eventos?limite=3")
        assert r.json()["total"] == 3

    def test_proximo_cursor_presente_quando_ha_eventos(self, admin_client):
        client, db_path = admin_client
        self._inserir_eventos(db_path, n=2)
        r = client.get("/eventos")
        assert r.json()["proximo_cursor"] is not None

    def test_filtro_desde_cursor(self, admin_client):
        """Eventos após o cursor são retornados; anteriores são ignorados."""
        import time
        client, db_path = admin_client

        # Insere evento antigo com timestamp controlado
        conn = _conn(db_path)
        registrar_outbox(conn, "ev_antigo", "prescricao", "p1", {})
        conn.commit()
        conn.close()

        # Garante que o próximo evento terá timestamp maior
        time.sleep(0.02)

        # Anota o momento de corte APÓS garantir diferença de tempo
        from datetime import datetime, timezone
        cursor = datetime.now(timezone.utc).isoformat()

        time.sleep(0.01)

        # Insere evento posterior ao cursor
        conn = _conn(db_path)
        registrar_outbox(conn, "ev_novo", "laudo", "p2", {})
        conn.commit()
        conn.close()

        r2 = client.get(f"/eventos?desde={cursor}")
        evs = r2.json()["eventos"]
        assert len(evs) == 1
        assert evs[0]["tipo_evento"] == "ev_novo"

    def test_pendentes_por_padrao(self, admin_client):
        """Sem incluir_consumidos, apenas publicado=0 é retornado."""
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        # Ack manual
        conn.execute("UPDATE eventos_publicacao SET publicado=1 WHERE id=?", (evt_id,))
        conn.commit()
        conn.close()

        r = client.get("/eventos")
        assert r.json()["total"] == 0

    def test_incluir_consumidos(self, admin_client):
        """Com incluir_consumidos=true, eventos acked também aparecem."""
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        conn.execute("UPDATE eventos_publicacao SET publicado=1 WHERE id=?", (evt_id,))
        conn.commit()
        conn.close()

        r = client.get("/eventos?incluir_consumidos=true")
        assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# Testes de POST /eventos/{id}/ack
# ---------------------------------------------------------------------------

class TestAckEvento:

    def test_ack_marca_publicado(self, admin_client):
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        conn.close()

        r = client.post(f"/eventos/{evt_id}/ack")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["publicado_em"] is not None

        # Verificar no banco
        conn = _conn(db_path)
        row = conn.execute("SELECT publicado, publicado_em FROM eventos_publicacao WHERE id=?", (evt_id,)).fetchone()
        conn.close()
        assert row["publicado"] == 1
        assert row["publicado_em"] is not None

    def test_ack_idempotente(self, admin_client):
        """Ack duplo não gera erro — retorna 200."""
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        conn.close()

        r1 = client.post(f"/eventos/{evt_id}/ack")
        r2 = client.post(f"/eventos/{evt_id}/ack")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_ack_evento_inexistente_retorna_404(self, admin_client):
        client, _ = admin_client
        r = client.post("/eventos/evt_nao_existe/ack")
        assert r.status_code == 404

    def test_evento_nao_reaparece_apos_ack(self, admin_client):
        """Após ack, evento não aparece no polling padrão (publicado=0)."""
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        conn.close()

        client.post(f"/eventos/{evt_id}/ack")

        r = client.get("/eventos")
        assert r.json()["total"] == 0

    def test_evento_permanece_disponivel_apos_ack(self, admin_client):
        """Evento acked permanece disponível com incluir_consumidos=true (sem DELETE)."""
        client, db_path = admin_client
        conn = _conn(db_path)
        evt_id = registrar_outbox(conn, "ev1", "agendamento", "p1", {})
        conn.commit()
        conn.close()

        client.post(f"/eventos/{evt_id}/ack")

        r = client.get("/eventos?incluir_consumidos=true")
        assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# Testes de segurança
# ---------------------------------------------------------------------------

class TestSegurancaEventos:

    def test_paciente_nao_acessa_eventos(self, paciente_client):
        """Role 'paciente' não pode acessar /eventos — requer admin."""
        r = paciente_client.get("/eventos")
        assert r.status_code == 403

    def test_paciente_nao_acessa_ack(self, paciente_client):
        r = paciente_client.post("/eventos/evt_qualquer/ack")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Fixture de integração (role prescritor para criar, admin para ler eventos)
# ---------------------------------------------------------------------------

@pytest.fixture()
def integracao_client(db_path_g4a):
    """
    Retorna dois clientes para testes de integração:
    - prescritor_c: pode criar prescrições, pedidos e agendamentos
    - admin_c:      pode ler /eventos
    Ambos apontam para o mesmo banco de teste.
    """
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.main import app
    from app.auth.dependencies import get_current_user, get_current_user_or_api_key

    gc = _make_get_conn(db_path_g4a)
    stack = ExitStack()
    # database_tx.get_conn cobre eventos/agendamentos/pedidos_exame.
    # prescricoes importa get_conn diretamente — patch específico.
    for target in [
        "app.database_tx.get_conn",
        "app.routers.prescricoes.get_conn",
    ]:
        stack.enter_context(patch(target, gc))

    raw_client = TestClient(app, raise_server_exceptions=True)
    raw_client.__enter__()

    class _RoleClient:
        def __init__(self, role):
            self._role = role
        def _activate(self):
            u = {"role": self._role, "sub": "test"}
            app.dependency_overrides[get_current_user] = lambda: u
            # G4B: /eventos usa get_current_user_or_api_key
            app.dependency_overrides[get_current_user_or_api_key] = lambda: u
        def post(self, *a, **kw):
            self._activate(); return raw_client.post(*a, **kw)
        def get(self, *a, **kw):
            self._activate(); return raw_client.get(*a, **kw)

    yield _RoleClient("prescritor"), _RoleClient("admin")

    raw_client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Testes de integração: ação clínica → outbox
# ---------------------------------------------------------------------------

class TestIntegracaoOutbox:

    def test_prescricao_emitida_gera_evento_outbox(self, integracao_client):
        """POST /prescricoes deve criar entrada no outbox para prescricao_emitida."""
        prescritor_c, admin_c = integracao_client
        r = prescritor_c.post("/prescricoes", json={
            "cns_prescritor":  "123456789012345",
            "nome_prescritor": "Dr. Teste",
            "cpf_paciente":    "12345678901",
            "nome_paciente":   "Paciente Teste",
            "tipo_emissao":    "nova",
            "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
                        "quantidade": 10, "posologia": "1 cap 3x ao dia"}],
        })
        assert r.status_code == 201

        r2 = admin_c.get("/eventos?objeto_tipo=prescricao")
        evs = r2.json()["eventos"]
        assert len(evs) >= 1
        tipos = [e["tipo_evento"] for e in evs]
        assert "prescricao_emitida" in tipos

    def test_agendamento_criado_gera_evento_outbox(self, integracao_client):
        """POST /agendamentos deve criar entrada no outbox para agendamento_criado."""
        prescritor_c, admin_c = integracao_client

        # Criar pedido de exame primeiro
        r_pedido = prescritor_c.post("/pedidos-exame", json={
            "cns_prescritor":  "123456789012345",
            "nome_prescritor": "Dr. Teste",
            "cpf_paciente":    "12345678901",
            "nome_paciente":   "Paciente Teste",
            "tipo_emissao":    "novo",
            "itens": [{"nome_exame": "Hemograma", "quantidade": 1}],
        })
        assert r_pedido.status_code == 201
        proto_pedido = r_pedido.json()["protocolo"]

        # Criar agendamento (paciente pode agendar)
        r_ag = prescritor_c.post("/agendamentos", json={
            "pedido_protocolo": proto_pedido,
            "data_hora":        "2026-06-01T09:00:00",
            "org_id":           "LAB-TESTE",
            "unidade_id":       "UNIDADE-001",
            "tipo_agendamento": "exame",
        })
        assert r_ag.status_code == 201

        r_ev = admin_c.get("/eventos?objeto_tipo=agendamento")
        evs = r_ev.json()["eventos"]
        assert len(evs) >= 1
        tipos = [e["tipo_evento"] for e in evs]
        assert "agendamento_criado" in tipos

        # Verificar org_id propagado corretamente
        ev_criado = next(e for e in evs if e["tipo_evento"] == "agendamento_criado")
        assert ev_criado["org_id"]     == "LAB-TESTE"
        assert ev_criado["unidade_id"] == "UNIDADE-001"
