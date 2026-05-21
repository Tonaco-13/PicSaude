"""
tests/test_ledger_helper.py
===========================

Testes da sub-tarefa 4C — helper centralizado de inserção no ledger
(``app/domain/ledger.py``) + ``get_instance_id_conn`` em
``app/instance.py`` + parâmetro ``instance_id`` opcional em
``app/domain/outbox.py``.

Cobertura (15 testes — alinhado com TICKET-4C §4.5):

  Cobertura por subdomínio (5 — happy path):
    1. test_registrar_evento_prescricao_preenche_instance_id
    2. test_registrar_evento_pedido_exame_preenche_instance_id
    3. test_registrar_evento_laudo_preenche_instance_id
    4. test_registrar_evento_agendamento_preenche_instance_id  (outlier "evento")
    5. test_registrar_evento_circulacao_diagnostica_preenche_instance_id

  Validação de entrada (3 — negative path):
    6. test_objeto_tipo_invalido_raise_value_error
    7. test_prescricao_sem_ator_raise_value_error
    8. test_outros_subdominios_com_ator_raise_value_error

  Outbox e retrocompatibilidade (2):
    9. test_outbox_aceita_instance_id_opcional
   10. test_outbox_sem_instance_id_continua_funcionando_silencioso

  Invariantes transacionais (4 — adicionados na rodada CODEX):
   11. test_rollback_da_transacao_remove_ledger_e_outbox
   12. test_ledger_e_outbox_recebem_o_mesmo_instance_id
   13. test_payload_none_inserido_como_dict_vazio
   14. test_first_boot_nao_antecipa_commit_de_dados_clinicos

  Compatibilidade DB (1):
   15. test_get_instance_id_conn_funciona_com_pgconnection_wrapper

Setup (CODEX P2-3): NÃO usar ``Base.metadata.create_all()``. A coluna
``instance_id`` vem só por Alembic (4B). Cada teste sobe SQLite
temporário e roda ``alembic upgrade head`` (mesmo padrão de
``test_migration_4b_instance_id.py``).

FK enforcement: desligado via ``PRAGMA foreign_keys = OFF`` para
permitir inserir eventos com FKs sintéticas (testamos o helper, não a
integridade referencial — esta é coberta em 4D pelos endpoints reais).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config


# ---------------------------------------------------------------------------
# Fixture: SQLite + Alembic upgrade head
# ---------------------------------------------------------------------------


@pytest.fixture
def alembic_db(tmp_path, monkeypatch):
    """
    Banco SQLite temporário com TODA a cadeia Alembic aplicada
    (incluindo 4B — ``instance_id`` em 10 tabelas).
    """
    db_path = tmp_path / "test_ledger_helper.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    monkeypatch.chdir(backend_root)

    command.upgrade(cfg, "head")
    return db_path


@pytest.fixture
def conn(alembic_db):
    """
    Conexão SQLite raw com ``row_factory = sqlite3.Row`` (mesmo perfil de
    ``app.database.get_conn()`` em modo dev). FK enforcement OFF para
    permitir inserções com FKs sintéticas — testamos o helper, não a
    integridade referencial.
    """
    c = sqlite3.connect(str(alembic_db), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = OFF")
    yield c
    c.close()


def _instance_id_fake() -> str:
    """UUID v4 fixo para testes — sem depender de get_instance_id_conn
    nos cenários onde queremos isolar o helper de ledger."""
    return "11111111-1111-4111-8111-111111111111"


# ===========================================================================
# 1–5. Cobertura por subdomínio (happy path)
# ===========================================================================


def test_registrar_evento_prescricao_preenche_instance_id(conn):
    """``prescricao`` é o único subdomínio com colunas de ator."""
    from app.domain.ledger import registrar_evento_ledger

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="prescricao",
        objeto_id=42,
        tipo_evento="prescricao_emitida",
        instance_id=iid,
        payload={"protocolo": "abc-123"},
        ator_tipo="prescritor",
        ator_id="987654321098765",
    )
    conn.commit()

    row = conn.execute(
        "SELECT instance_id, tipo_evento, ator_tipo, ator_id, payload_json "
        "FROM prescricao_eventos WHERE prescricao_id = ?",
        (42,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid
    assert row["tipo_evento"] == "prescricao_emitida"
    assert row["ator_tipo"] == "prescritor"
    assert row["ator_id"] == "987654321098765"
    assert json.loads(row["payload_json"]) == {"protocolo": "abc-123"}


def test_registrar_evento_pedido_exame_preenche_instance_id(conn):
    from app.domain.ledger import registrar_evento_ledger

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="pedido_exame",
        objeto_id=7,
        tipo_evento="pedido_emitido",
        instance_id=iid,
        payload={"qtd_itens": 3},
    )
    conn.commit()

    row = conn.execute(
        "SELECT instance_id, tipo_evento, dados_json "
        "FROM pedido_exame_eventos WHERE pedido_id = ?",
        (7,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid
    assert row["tipo_evento"] == "pedido_emitido"
    assert json.loads(row["dados_json"]) == {"qtd_itens": 3}


def test_registrar_evento_laudo_preenche_instance_id(conn):
    from app.domain.ledger import registrar_evento_ledger

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="laudo",
        objeto_id=11,
        tipo_evento="laudo_assinado",
        instance_id=iid,
        payload={"hash": "abc"},
    )
    conn.commit()

    row = conn.execute(
        "SELECT instance_id, tipo_evento, dados_json "
        "FROM laudo_eventos WHERE laudo_id = ?",
        (11,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid
    assert row["tipo_evento"] == "laudo_assinado"


def test_registrar_evento_agendamento_preenche_instance_id(conn):
    """Outlier: tabela usa coluna ``evento`` (não ``tipo_evento``) e
    ``payload`` (não ``dados_json``)."""
    from app.domain.ledger import registrar_evento_ledger

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="agendamento",
        objeto_id=99,
        tipo_evento="agendamento_realizado",
        instance_id=iid,
        payload={"sala": "B2"},
    )
    conn.commit()

    # Coluna ``evento`` (outlier confirmado pelo schema do model)
    row = conn.execute(
        "SELECT instance_id, evento, payload "
        "FROM agendamento_eventos WHERE agendamento_id = ?",
        (99,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid
    assert row["evento"] == "agendamento_realizado"
    assert json.loads(row["payload"]) == {"sala": "B2"}


def test_registrar_evento_circulacao_diagnostica_preenche_instance_id(conn):
    from app.domain.ledger import registrar_evento_ledger

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="circulacao_diagnostica",
        objeto_id=5,
        tipo_evento="circulacao_iniciada",
        instance_id=iid,
        payload={"motivo": "transferencia"},
    )
    conn.commit()

    row = conn.execute(
        "SELECT instance_id, tipo_evento, dados_json "
        "FROM circulacao_diagnostica_eventos WHERE circulacao_id = ?",
        (5,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid
    assert row["tipo_evento"] == "circulacao_iniciada"


# ===========================================================================
# 6–8. Validação de entrada (negative path)
# ===========================================================================


def test_objeto_tipo_invalido_raise_value_error(conn):
    """``Literal[...]`` não protege chamadas dinâmicas — runtime check."""
    from app.domain.ledger import registrar_evento_ledger

    with pytest.raises(ValueError, match="objeto_tipo"):
        registrar_evento_ledger(
            conn,
            objeto_tipo="objeto_inexistente",  # type: ignore[arg-type]
            objeto_id=1,
            tipo_evento="x",
            instance_id=_instance_id_fake(),
        )


def test_prescricao_sem_ator_raise_value_error(conn):
    """``prescricao`` exige ``ator_tipo``. Sem ele → ValueError."""
    from app.domain.ledger import registrar_evento_ledger

    with pytest.raises(ValueError, match="ator_tipo"):
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=1,
            tipo_evento="prescricao_emitida",
            instance_id=_instance_id_fake(),
            payload={},
            # ator_tipo ausente
        )


def test_outros_subdominios_com_ator_raise_value_error(conn):
    """Apenas ``prescricao`` tem coluna de ator. Outros subdomínios →
    erro se receberem ``ator_tipo`` ou ``ator_id``."""
    from app.domain.ledger import registrar_evento_ledger

    with pytest.raises(ValueError, match="não suporta ator"):
        registrar_evento_ledger(
            conn,
            objeto_tipo="laudo",
            objeto_id=1,
            tipo_evento="laudo_assinado",
            instance_id=_instance_id_fake(),
            ator_tipo="prestador",   # incompatível com schema do laudo
        )


# ===========================================================================
# 9–10. Outbox e retrocompatibilidade
# ===========================================================================


def test_outbox_aceita_instance_id_opcional(conn):
    """Quando 4D passar ``instance_id`` para o outbox, a coluna deve
    receber o valor."""
    from app.domain.outbox import registrar_outbox

    iid = _instance_id_fake()
    evt_id = registrar_outbox(
        conn,
        "prescricao_emitida",
        "prescricao",
        "abc-123",
        {"protocolo": "abc-123"},
        instance_id=iid,
    )
    conn.commit()
    assert evt_id is not None and evt_id.startswith("evt_")

    row = conn.execute(
        "SELECT instance_id FROM eventos_publicacao WHERE id = ?",
        (evt_id,),
    ).fetchone()
    assert row is not None
    assert row["instance_id"] == iid


def test_outbox_sem_instance_id_recusa_chamada(conn):
    """4E.2 §3.1.4: ``instance_id`` é keyword-only obrigatório — chamadas
    sem o parâmetro devem falhar cedo com TypeError, não silenciosamente
    gravar NULL como acontecia no contrato pré-4E.2."""
    from app.domain.outbox import registrar_outbox

    with pytest.raises(TypeError, match="instance_id"):
        registrar_outbox(
            conn,
            "agendamento_realizado",
            "agendamento",
            "proto-xyz",
            {"sala": "B2"},
        )


# ===========================================================================
# 11–14. Invariantes transacionais (CODEX rodada 1, item 7)
# ===========================================================================


def test_rollback_da_transacao_remove_ledger_e_outbox(conn):
    """
    Cenário real: pagamento falha após emissão clínica → exceção no router
    → ``with get_tx()`` faz rollback. Ledger + outbox devem desaparecer
    juntos (estavam na mesma transação).
    """
    from app.domain.ledger import registrar_evento_ledger
    from app.domain.outbox import registrar_outbox

    iid = _instance_id_fake()
    # Simula transação clínica usando a conn raw em modo manual.
    try:
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=999,
            tipo_evento="prescricao_emitida",
            instance_id=iid,
            payload={"x": 1},
            ator_tipo="prescritor",
            ator_id="cns",
        )
        registrar_outbox(
            conn, "prescricao_emitida", "prescricao", "proto",
            {"x": 1}, instance_id=iid,
        )
        raise RuntimeError("simulando falha de pagamento")
    except RuntimeError:
        conn.rollback()

    # Após rollback: nada persistiu.
    row_ledger = conn.execute(
        "SELECT 1 FROM prescricao_eventos WHERE prescricao_id = ?",
        (999,),
    ).fetchone()
    row_outbox = conn.execute(
        "SELECT 1 FROM eventos_publicacao WHERE objeto_id = ?",
        ("proto",),
    ).fetchone()
    assert row_ledger is None
    assert row_outbox is None


def test_ledger_e_outbox_recebem_o_mesmo_instance_id(conn):
    """
    Invariante crítica: ambas as tabelas devem ter o mesmo UUID em uma
    única transação clínica — caso contrário a marca d'água perde a
    correspondência forense.
    """
    from app.domain.ledger import registrar_evento_ledger
    from app.domain.outbox import registrar_outbox

    iid = _instance_id_fake()
    registrar_evento_ledger(
        conn,
        objeto_tipo="prescricao",
        objeto_id=77,
        tipo_evento="prescricao_emitida",
        instance_id=iid,
        payload={"protocolo": "p77"},
        ator_tipo="prescritor",
        ator_id="cns",
    )
    registrar_outbox(
        conn, "prescricao_emitida", "prescricao", "p77",
        {"protocolo": "p77"}, instance_id=iid,
    )
    conn.commit()

    iid_ledger = conn.execute(
        "SELECT instance_id FROM prescricao_eventos WHERE prescricao_id = ?",
        (77,),
    ).fetchone()["instance_id"]
    iid_outbox = conn.execute(
        "SELECT instance_id FROM eventos_publicacao WHERE objeto_id = ?",
        ("p77",),
    ).fetchone()["instance_id"]

    assert iid_ledger == iid_outbox == iid


def test_payload_none_inserido_como_dict_vazio(conn):
    """
    Semântica de ``payload=None``: helper insere ``"{}"`` no banco
    (não NULL). Evita ambiguidade entre "sem payload" e "payload ausente".
    """
    from app.domain.ledger import registrar_evento_ledger

    registrar_evento_ledger(
        conn,
        objeto_tipo="laudo",
        objeto_id=88,
        tipo_evento="laudo_arquivado",
        instance_id=_instance_id_fake(),
        # payload omitido → default None → deve persistir como "{}"
    )
    conn.commit()

    row = conn.execute(
        "SELECT dados_json FROM laudo_eventos WHERE laudo_id = ?",
        (88,),
    ).fetchone()
    assert row is not None
    assert row["dados_json"] == "{}"
    assert json.loads(row["dados_json"]) == {}


def test_first_boot_nao_antecipa_commit_de_dados_clinicos(conn):
    """
    Teste de regressão para o bug que motivou a §4.1-bis (CODEX P1-1):
    ``get_instance_id(session)`` chamava ``session.commit()`` no first
    boot, antecipando commits dentro da transação clínica. A versão
    ``get_instance_id_conn`` NÃO comita — caller controla a transação.

    Cenário (refinado por CODEX 2026-05-08):
      1. Transação aberta na conn raw
      2. INSERT em ``prescricoes`` (dado clínico) — pendente, não comitado
      3. ``get_instance_id_conn`` (first boot — INSERT em meta_instalacao)
      4. Registra evento no ledger
      5. Exceção → rollback

    Assertivas (em ordem de criticidade):
      - prescricoes está VAZIA (rollback funcionou no clínico)
      - prescricao_eventos está VAZIA (rollback funcionou no ledger)
      - meta_instalacao pode estar com instance_id ou vazia (design choice
        — o ponto é não ter ANTECIPADO commit do clínico)
    """
    from app.domain.ledger import registrar_evento_ledger
    from app.instance import get_instance_id_conn

    # Sanity: meta_instalacao começa vazia (first boot)
    pre = conn.execute(
        "SELECT COUNT(*) AS n FROM meta_instalacao WHERE chave = 'instance_id'"
    ).fetchone()["n"]
    assert pre == 0

    try:
        # 1. Inicia transação inserindo dado clínico (não comita ainda)
        conn.execute(
            "INSERT INTO prescricoes "
            "  (protocolo, prescritor_id, paciente_id, status, "
            "   tipo_emissao, data_emissao, created_at, updated_at) "
            "VALUES "
            "  ('PROTO-FIRSTBOOT', 1, 1, 'pendente', "
            "   'nova', '2026-05-08T00:00:00', "
            "   '2026-05-08T00:00:00', '2026-05-08T00:00:00')"
        )
        # 2. First boot do instance_id — chama dentro da transação clínica
        iid = get_instance_id_conn(conn)
        assert uuid.UUID(iid).version == 4

        # 3. Grava evento no ledger
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=1,
            tipo_evento="prescricao_emitida",
            instance_id=iid,
            ator_tipo="prescritor",
            ator_id="cns",
        )

        # 4. Falha simulada
        raise RuntimeError("simulando falha pós-first-boot")
    except RuntimeError:
        conn.rollback()

    # Invariante crítica: dado clínico SUMIU.
    row = conn.execute(
        "SELECT 1 FROM prescricoes WHERE protocolo = 'PROTO-FIRSTBOOT'"
    ).fetchone()
    assert row is None, (
        "Dado clínico foi comitado antecipadamente — o helper "
        "get_instance_id_conn quebrou a transação clínica."
    )
    # Ledger também sumiu.
    row = conn.execute(
        "SELECT 1 FROM prescricao_eventos WHERE prescricao_id = 1"
    ).fetchone()
    assert row is None
    # meta_instalacao: design choice — pode estar vazia (rolled back junto)
    # ou pode estar com o valor (caso some optimization commitasse). O
    # essencial é que o clínico desapareceu.


# ===========================================================================
# 15. Compatibilidade com wrapper _PgConnection (PostgreSQL em prod)
# ===========================================================================


class _FakePgConnection:
    """
    Mock minimalista do ``_PgConnection`` para verificar que o SQL emitido
    por ``get_instance_id_conn`` na variante PG **já contém RETURNING**,
    impedindo a auto-adição de ``RETURNING id`` (linha 173 de
    ``database.py``) que quebraria em ``meta_instalacao`` (PK é ``chave``,
    não ``id``).

    Captura cada SQL enviado, simula a checagem de regex idêntica ao
    wrapper real e confirma o caminho correto.
    """

    _RETURNING_RE = __import__("re").compile(r"\bRETURNING\b", __import__("re").IGNORECASE)
    _INSERT_RE = __import__("re").compile(r"^\s*INSERT\b", __import__("re").IGNORECASE)

    def __init__(self) -> None:
        self.sqls_capturados: list[str] = []
        self.tomou_caminho_returning_explicito: list[bool] = []
        # estado interno: já temos um instance_id "persistido"?
        self._instance_id_persistido: str | None = None

    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.sqls_capturados.append(sql)
        is_insert = bool(self._INSERT_RE.match(sql))
        has_returning = bool(self._RETURNING_RE.search(sql))

        if is_insert:
            self.tomou_caminho_returning_explicito.append(has_returning)
            assert has_returning, (
                "INSERT em meta_instalacao precisa carregar RETURNING "
                "explícito — sem ele, o wrapper _PgConnection adicionaria "
                "RETURNING id automaticamente, quebrando porque a tabela "
                "tem PK 'chave'."
            )
            # Simula o INSERT idempotente (ON CONFLICT DO NOTHING):
            # se ainda não persistido, persiste; se já, no-op.
            if self._instance_id_persistido is None and len(params) >= 2:
                self._instance_id_persistido = params[1]

        # Mock cursor — SELECT retorna a linha corrente, INSERT vazio.
        cursor = MagicMock()
        if "SELECT" in sql.upper():
            if self._instance_id_persistido:
                cursor.fetchone.return_value = {"valor": self._instance_id_persistido}
            else:
                cursor.fetchone.return_value = None
        else:
            cursor.fetchone.return_value = None
        return cursor


def test_get_instance_id_conn_funciona_com_pgconnection_wrapper(monkeypatch):
    """
    Com mock do wrapper PG, confirma que ``get_instance_id_conn`` envia o
    INSERT com ``RETURNING chave`` explícito — caminho que evita a
    interceptação automática do ``_PgConnection`` (linha 173 de
    database.py).
    """
    from app.instance import get_instance_id_conn

    fake = _FakePgConnection()
    # Força o caminho não-SQLite no helper (in-memory mock não é
    # ``sqlite3.Connection``, mas garantimos via monkeypatch).
    monkeypatch.setattr("app.instance._is_sqlite_conn", lambda _conn: False)

    iid = get_instance_id_conn(fake)
    assert uuid.UUID(iid).version == 4

    # SQL enviado deve conter o INSERT com RETURNING explícito.
    insert_sqls = [s for s in fake.sqls_capturados if s.strip().upper().startswith("INSERT")]
    assert len(insert_sqls) == 1
    assert "RETURNING chave" in insert_sqls[0]
    # Também valida que o insert tomou o caminho ON CONFLICT (PG path).
    assert "ON CONFLICT" in insert_sqls[0].upper()
    # Confirma que o helper percorreu o caminho com RETURNING.
    assert fake.tomou_caminho_returning_explicito == [True]


# ===========================================================================
# 16–18. CODEX rodada 3 — P1: validação de instance_id em runtime
# ===========================================================================
#
# O regime keyword-only sem default só pega ausência (TypeError).
# CODEX P1 (rodada 3) apontou que valores inválidos passados explicitamente
# (None, "", string lixo, UUID v1) precisam ser rejeitados também — defesa
# em camadas. ``_validar_uuid_v4`` é chamada no início de
# ``registrar_evento_ledger`` e levanta ``RuntimeError`` para esses casos
# (semântica idêntica à de ``get_instance_id``).


def test_registrar_evento_recusa_instance_id_none(conn):
    """instance_id=None deve falhar (defesa em camadas — keyword-only só
    pega ausência)."""
    from app.domain.ledger import registrar_evento_ledger
    with pytest.raises((ValueError, RuntimeError)):
        registrar_evento_ledger(
            conn,
            objeto_tipo="laudo",
            objeto_id=1,
            tipo_evento="laudo_arquivado",
            instance_id=None,  # type: ignore[arg-type]
        )


def test_registrar_evento_recusa_instance_id_vazio(conn):
    """instance_id='' deve falhar."""
    from app.domain.ledger import registrar_evento_ledger
    with pytest.raises((ValueError, RuntimeError)):
        registrar_evento_ledger(
            conn,
            objeto_tipo="laudo",
            objeto_id=1,
            tipo_evento="laudo_arquivado",
            instance_id="",
        )


def test_registrar_evento_recusa_instance_id_nao_uuid(conn):
    """String não-UUID deve falhar."""
    from app.domain.ledger import registrar_evento_ledger
    with pytest.raises((ValueError, RuntimeError)):
        registrar_evento_ledger(
            conn,
            objeto_tipo="laudo",
            objeto_id=1,
            tipo_evento="laudo_arquivado",
            instance_id="not-a-uuid",
        )


# ===========================================================================
# 19–20. CODEX rodada 3 — P2-A: env override em get_instance_id_conn
# ===========================================================================


def test_get_instance_id_conn_respeita_env_override_em_dev(
    conn, monkeypatch,
):
    """
    Em dev/test, ``PICSAUDE_INSTANCE_ID`` curto-circuita — não toca DB.
    Coerência com ``get_instance_id(session)``, evitando que o ``_conn``
    persista valor diferente do override (que geraria divergência forense
    detectada no próximo boot).
    """
    from app.instance import get_instance_id_conn
    uuid_fixo = "11111111-1111-4111-8111-111111111111"
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", uuid_fixo)
    monkeypatch.setenv("PICSAUDE_ENV", "dev")

    iid = get_instance_id_conn(conn)
    assert iid == uuid_fixo

    # DB NÃO foi tocado — short-circuit antes do SELECT/INSERT.
    row = conn.execute(
        "SELECT valor FROM meta_instalacao WHERE chave = ?",
        ("instance_id",),
    ).fetchone()
    assert row is None


def test_get_instance_id_conn_recusa_env_override_em_prod(
    conn, monkeypatch,
):
    """Em prod, ``PICSAUDE_INSTANCE_ID`` setada deve raise — bloqueia
    spoof de marca d'água em produção."""
    from app.instance import get_instance_id_conn
    monkeypatch.setenv(
        "PICSAUDE_INSTANCE_ID",
        "11111111-1111-4111-8111-111111111111",
    )
    monkeypatch.setenv("PICSAUDE_ENV", "prod")

    with pytest.raises(RuntimeError):
        get_instance_id_conn(conn)
