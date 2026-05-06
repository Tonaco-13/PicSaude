"""
tests/test_instance_id.py
=========================
Testes do helper ``app.instance.get_instance_id`` (Etapa 4A do plano de
produção).

Cobertura:
  T1. First boot gera UUID v4 válido.
  T2. Boots subsequentes retornam o mesmo UUID.
  T3. Env var override funciona em dev/test.
  T4. Env var override REJEITADO em PICSAUDE_ENV=prod.
  T5. Valor inválido (não UUID v4) raise.
  T6. DB existe + arquivo ausente → recria arquivo.
  T7. Arquivo existe + DB vazio → INSERT no DB (recovery).
  T8. Divergência arquivo vs DB → RuntimeError.
  T9. Modo degraded (session=None) com arquivo presente.
  T10. Modo degraded sem arquivo → raise.

Notas:
  - Race condition (multi-processo) é teste de integração, fica em 4D.
  - Testes que cruzam ledger (eventos com instance_id) ficam em 4C/4D.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.instance import get_instance_id, _CHAVE_DB
from app.models.meta_instalacao import MetaInstalacao


# ---------------------------------------------------------------------------
# Fixture: ambiente isolado por teste
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_session(tmp_path, monkeypatch):
    """
    SQLite isolado em arquivo temporário + arquivo .instance_id em tmp_path.

    Isola completamente o estado entre testes:
      - DB próprio (arquivo SQLite em tmp_path)
      - Arquivo .instance_id próprio (path override via env)
      - Variáveis de ambiente PICSAUDE_INSTANCE_ID e PICSAUDE_ENV limpas
    """
    db_path = tmp_path / "test.db"
    instance_file = tmp_path / ".instance_id"

    # Override path do arquivo .instance_id
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID_PATH", str(instance_file))

    # Limpa env vars potencialmente contaminantes
    monkeypatch.delenv("PICSAUDE_INSTANCE_ID", raising=False)
    monkeypatch.delenv("PICSAUDE_ENV", raising=False)

    # Cria engine + tabela meta_instalacao isolados
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[MetaInstalacao.__table__])

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session, instance_file

    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# T1 — First boot gera UUID v4
# ---------------------------------------------------------------------------


def test_first_boot_gera_uuid_v4(temp_session):
    session, instance_file = temp_session

    instance_id = get_instance_id(session)

    # Valida UUID v4
    parsed = uuid.UUID(instance_id)
    assert parsed.version == 4, f"Esperado UUID v4, recebido v{parsed.version}"

    # Valida persistência dual
    assert instance_file.exists(), "Arquivo .instance_id deveria ter sido criado"
    assert instance_file.read_text().strip() == instance_id

    row = session.query(MetaInstalacao).filter_by(chave=_CHAVE_DB).first()
    assert row is not None, "DB deveria ter linha para instance_id"
    assert row.valor == instance_id


# ---------------------------------------------------------------------------
# T2 — Boots subsequentes retornam o mesmo UUID
# ---------------------------------------------------------------------------


def test_second_boot_retorna_mesmo_id(temp_session):
    session, _ = temp_session

    primeiro = get_instance_id(session)
    segundo = get_instance_id(session)
    terceiro = get_instance_id(session)

    assert primeiro == segundo == terceiro


# ---------------------------------------------------------------------------
# T3 — Env var override funciona em dev/test
# ---------------------------------------------------------------------------


def test_env_override_funciona_em_dev(temp_session, monkeypatch):
    session, _ = temp_session
    custom = "12345678-1234-4abc-9def-123456789abc"  # UUID v4 válido
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", custom)
    monkeypatch.setenv("PICSAUDE_ENV", "dev")

    assert get_instance_id(session) == custom


def test_env_override_funciona_em_test(temp_session, monkeypatch):
    session, _ = temp_session
    custom = "12345678-1234-4abc-9def-123456789abc"
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", custom)
    monkeypatch.setenv("PICSAUDE_ENV", "test")

    assert get_instance_id(session) == custom


# ---------------------------------------------------------------------------
# T4 — Env var override REJEITADO em PICSAUDE_ENV=prod
# ---------------------------------------------------------------------------


def test_env_override_rejeitado_em_prod(temp_session, monkeypatch):
    session, _ = temp_session
    custom = "12345678-1234-4abc-9def-123456789abc"
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", custom)
    monkeypatch.setenv("PICSAUDE_ENV", "prod")

    with pytest.raises(RuntimeError, match="PICSAUDE_ENV=prod"):
        get_instance_id(session)


# ---------------------------------------------------------------------------
# T5 — Valor inválido não-UUID raise
# ---------------------------------------------------------------------------


def test_valor_invalido_nao_uuid_raise(temp_session, monkeypatch):
    session, _ = temp_session
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", "nao-eh-uuid")
    monkeypatch.setenv("PICSAUDE_ENV", "dev")

    with pytest.raises(RuntimeError, match="instance_id inválido"):
        get_instance_id(session)


def test_valor_uuid_v1_rejeitado(temp_session, monkeypatch):
    """UUID válido mas de outra versão (não v4) deve raise."""
    session, _ = temp_session
    # UUID v1 (timestamp + MAC)
    uuid_v1 = str(uuid.uuid1())
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", uuid_v1)
    monkeypatch.setenv("PICSAUDE_ENV", "dev")

    with pytest.raises(RuntimeError, match="UUID v4"):
        get_instance_id(session)


# ---------------------------------------------------------------------------
# T6 — DB tem valor + arquivo ausente → recria arquivo
# ---------------------------------------------------------------------------


def test_db_tem_arquivo_ausente_recria(temp_session):
    """Simula reinício do container Docker onde filesystem foi limpo."""
    session, instance_file = temp_session

    # First boot popula ambos
    primeiro = get_instance_id(session)
    assert instance_file.exists()

    # Apaga arquivo (filesystem efêmero do container)
    instance_file.unlink()
    assert not instance_file.exists()

    # Próximo boot deve recriar arquivo a partir do DB
    segundo = get_instance_id(session)
    assert segundo == primeiro
    assert instance_file.exists()
    assert instance_file.read_text().strip() == primeiro


# ---------------------------------------------------------------------------
# T7 — Arquivo tem valor + DB vazio → INSERT no DB (recovery)
# ---------------------------------------------------------------------------


def test_arquivo_tem_db_vazio_insere(temp_session):
    """
    Simula DB resetado mas filesystem persiste (raro, mas possível em
    desastre operacional). Recovery: arquivo é fonte temporária até
    repopular o DB.
    """
    session, instance_file = temp_session

    # Popula apenas o arquivo (sem tocar DB)
    valor_arquivo = "abcdef12-3456-4789-abcd-ef0123456789"
    instance_file.write_text(valor_arquivo)

    # Confirma DB vazio
    assert (
        session.query(MetaInstalacao).filter_by(chave=_CHAVE_DB).first()
        is None
    )

    # Boot deve inserir no DB
    resultado = get_instance_id(session)
    assert resultado == valor_arquivo

    row = session.query(MetaInstalacao).filter_by(chave=_CHAVE_DB).first()
    assert row is not None
    assert row.valor == valor_arquivo


# ---------------------------------------------------------------------------
# T8 — Divergência arquivo vs DB → RuntimeError
# ---------------------------------------------------------------------------


def test_divergencia_arquivo_vs_db_raise(temp_session):
    """
    Cenário: clone do banco para máquina nova, mas filesystem original
    foi copiado também. Arquivo aponta para instância antiga, DB para
    nova. Divergência indica anomalia operacional grave.
    """
    session, instance_file = temp_session

    # Popula DB
    valor_db = str(uuid.uuid4())
    session.add(
        MetaInstalacao(
            chave=_CHAVE_DB,
            valor=valor_db,
            criado_em="2026-05-06T15:00:00+00:00",
        )
    )
    session.commit()

    # Popula arquivo com valor diferente (simula clone)
    valor_arquivo = str(uuid.uuid4())
    instance_file.write_text(valor_arquivo)

    with pytest.raises(RuntimeError, match="DIVERGÊNCIA detectada"):
        get_instance_id(session)


# ---------------------------------------------------------------------------
# T9 — Modo degraded (session=None) com arquivo presente
# ---------------------------------------------------------------------------


def test_modo_degraded_com_arquivo(temp_session):
    """
    Sem session: usado em scripts/utilitários sem contexto de banco.
    Lê apenas do arquivo. Útil para CLIs.
    """
    session, instance_file = temp_session

    # First boot popula arquivo (via session normal)
    valor = get_instance_id(session)
    assert instance_file.exists()

    # Chamada sem session deve retornar o mesmo
    valor_degraded = get_instance_id(session=None)
    assert valor_degraded == valor


# ---------------------------------------------------------------------------
# T10 — Modo degraded sem arquivo → raise
# ---------------------------------------------------------------------------


def test_modo_degraded_sem_arquivo_raise(tmp_path, monkeypatch):
    """
    Sem session E sem arquivo: não há de onde ler. Deve raise com
    mensagem clara orientando o operador.
    """
    instance_file = tmp_path / ".instance_id"
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID_PATH", str(instance_file))
    monkeypatch.delenv("PICSAUDE_INSTANCE_ID", raising=False)
    monkeypatch.delenv("PICSAUDE_ENV", raising=False)

    with pytest.raises(RuntimeError, match="instance_id não disponível"):
        get_instance_id(session=None)
