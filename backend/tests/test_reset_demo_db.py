"""
TICKET-DEMO-RESET-PG — testes que NÃO exigem PostgreSQL.

Cobrem:
  - `_confirmacao_ok` (§3.3) — a decisão pura de autorização do alvo (AC8/AC9),
    testável sem banco: matriz flag × terminal × resposta.
  - Regressão SQLite (AC7) — rodar o script contra um SQLite demo efêmero e
    provar que o schema volta ao `alembic head`, com os 16 triggers de
    imutabilidade (o de saldo é PG-only) e as personas semeadas. Prova também
    o §3.2: recriação via migração (não `create_all`).

Os testes de PostgreSQL (AC4/5/6/9/10 — DROP SCHEMA, anti-contaminação,
idempotência, alvo protegido) vivem em `tests/integration/test_reset_demo_db_pg.py`,
que pula sem `DATABASE_URL` de Postgres.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.ledger_imutabilidade import TABELAS_LEDGER, nome_trigger
from scripts.reset_demo_db import _confirmacao_ok

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_RESET_SCRIPT = _BACKEND_ROOT / "scripts" / "reset_demo_db.py"

# 8 tabelas × (UPDATE, DELETE) = 16 triggers de imutabilidade no SQLite.
_TRIGGERS_IMUTABILIDADE = {
    nome_trigger(acao, tabela)
    for tabela in TABELAS_LEDGER
    for acao in ("UPDATE", "DELETE")
}

# Personas canônicas do seed_demo (§ seed_demo.py).
_CNS_PRESCRITOR_DEMO = "980001112223334"
_CNPJ_DISPENSADOR_DEMO = "99999999000191"


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(cfg).get_current_head()


# ---------------------------------------------------------------------------
# §3.3 — decisão pura de autorização do alvo (AC8/AC9)
# ---------------------------------------------------------------------------

class TestConfirmacaoAlvo:
    DBNAME = "picsaude"

    def test_flag_assentimento_autoriza_sempre(self):
        # --sim-eu-quero autoriza inclusive job cego (sem terminal, sem resposta).
        assert _confirmacao_ok(True, is_tty=False, resposta=None, dbname=self.DBNAME)
        assert _confirmacao_ok(True, is_tty=True, resposta=None, dbname=self.DBNAME)

    def test_terminal_com_nome_correto_autoriza(self):
        assert _confirmacao_ok(False, True, self.DBNAME, self.DBNAME)
        # tolera espaços em volta (input do operador).
        assert _confirmacao_ok(False, True, f"  {self.DBNAME}  ", self.DBNAME)

    def test_terminal_com_nome_errado_nega(self):
        assert not _confirmacao_ok(False, True, "outro_banco", self.DBNAME)
        assert not _confirmacao_ok(False, True, "", self.DBNAME)

    def test_nao_interativo_sem_flag_nega(self):
        # AC9 — job não-interativo sem a flag NÃO é autorizado (nenhum DROP).
        assert not _confirmacao_ok(False, is_tty=False, resposta=None, dbname=self.DBNAME)
        # mesmo que "chegue" uma resposta, sem terminal não se confia nela.
        assert not _confirmacao_ok(False, is_tty=False, resposta=self.DBNAME, dbname=self.DBNAME)


# ---------------------------------------------------------------------------
# AC7 — regressão SQLite (dev): rebuild real via subprocess
# ---------------------------------------------------------------------------

def _rodar_reset_sqlite(demo_db: Path, *extra_args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PICSAUDE_DEMO_MODE": "true",
        "PICSAUDE_ENV": "stg",  # != prod
        "PIX_SAUDE_DEMO_DB": str(demo_db),
    }
    env.pop("DATABASE_URL", None)  # garante ramo SQLite
    return subprocess.run(
        [sys.executable, str(_RESET_SCRIPT), *extra_args],
        cwd=str(_BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestRebuildSqlite:
    def test_rebuild_recria_schema_triggers_e_personas(self, tmp_path):
        demo_db = tmp_path / "pix_saude_demo.db"
        proc = _rodar_reset_sqlite(demo_db)
        assert proc.returncode == 0, f"reset falhou:\n{proc.stdout}\n{proc.stderr}"
        assert demo_db.exists(), "arquivo do banco demo não foi criado"

        conn = sqlite3.connect(str(demo_db))
        try:
            # §3.2 — schema veio da migração (alembic head), não de create_all.
            versao = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            assert versao is not None and versao[0] == _alembic_head()

            # 16 triggers de imutabilidade; o de saldo é PG-only (ausente aqui).
            triggers = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
            assert _TRIGGERS_IMUTABILIDADE <= triggers, (
                f"faltam triggers de imutabilidade: "
                f"{_TRIGGERS_IMUTABILIDADE - triggers}"
            )
            assert "trg_check_saldo_efetivo" not in triggers  # PG-only

            # Personas canônicas semeadas.
            n_presc = conn.execute(
                "SELECT COUNT(*) FROM prescritores WHERE cns = ?",
                (_CNS_PRESCRITOR_DEMO,),
            ).fetchone()[0]
            assert n_presc == 1, "prescritor demo não foi semeado"
            n_disp = conn.execute(
                "SELECT COUNT(*) FROM prestadores WHERE cnpj = ?",
                (_CNPJ_DISPENSADOR_DEMO,),
            ).fetchone()[0]
            assert n_disp == 1, "dispensador demo não foi semeado"
        finally:
            conn.close()

    def test_rebuild_idempotente(self, tmp_path):
        # AC6 (dialeto SQLite) — rodar duas vezes não falha nem acumula personas.
        demo_db = tmp_path / "pix_saude_demo.db"
        assert _rodar_reset_sqlite(demo_db).returncode == 0
        proc2 = _rodar_reset_sqlite(demo_db)
        assert proc2.returncode == 0, f"2ª execução falhou:\n{proc2.stdout}\n{proc2.stderr}"

        conn = sqlite3.connect(str(demo_db))
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM prescritores WHERE cns = ?",
                (_CNS_PRESCRITOR_DEMO,),
            ).fetchone()[0]
            assert n == 1, "seed não é idempotente (prescritor duplicado)"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# AC3 — guardas §5 preservadas (defense-in-depth): abortam ANTES de qualquer
# import de banco. Não exigem dialeto — o abort acontece cedo.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# §4/§6.2 (DESPACHO-OPS-002) — sentinela pós-seed: sem verificador humano no
# cron, a checagem vira código. Sabota um sentinela após um reset SQLite real
# e prova que `_verificar_sentinelas()` aborta nomeando exatamente o que falta.
#
# `_resolve_sqlite_db_path()` (app/database.py) faz `from app.config import
# PICSAUDE_DEMO_MODE, PIX_SAUDE_DEMO_DB` DENTRO da função — cada chamada relê
# os atributos atuais do módulo `app.config`. Por isso `monkeypatch.setattr`
# no módulo (não `monkeypatch.setenv`) é o jeito confiável de redirecionar
# `get_conn()` para o SQLite efêmero do teste: os atributos de `app.config`
# já foram resolvidos (e cacheados) no import do módulo, cedo na sessão do
# pytest — mudar a env var agora não teria efeito nenhum.
# ---------------------------------------------------------------------------

class TestVerificarSentinelas:
    def _apontar_get_conn_para(self, monkeypatch, demo_db: Path) -> None:
        monkeypatch.setattr("app.config.PICSAUDE_DEMO_MODE", True)
        monkeypatch.setattr("app.config.PIX_SAUDE_DEMO_DB", str(demo_db))

    def test_sentinela_ausente_aborta_nomeando_a_ausente(
        self, tmp_path, monkeypatch, capsys
    ):
        demo_db = tmp_path / "pix_saude_demo.db"
        proc = _rodar_reset_sqlite(demo_db)
        assert proc.returncode == 0, f"setup do reset falhou:\n{proc.stdout}\n{proc.stderr}"

        # Sabota a sentinela do atestado por DELETE direto — simula um
        # `_garantir_atestado_demo` que engoliu erro (best-effort, OPS-001 §1).
        # `atestados` não é ledger (§2): só `*_eventos` tem trigger de
        # imutabilidade, a tabela primária aceita DELETE.
        conn = sqlite3.connect(str(demo_db))
        try:
            conn.execute(
                "DELETE FROM atestados WHERE protocolo = ?", ("DEMO-ATESTADO-0001",)
            )
            conn.commit()
        finally:
            conn.close()

        self._apontar_get_conn_para(monkeypatch, demo_db)

        from scripts.reset_demo_db import _verificar_sentinelas

        with pytest.raises(SystemExit) as exc_info:
            _verificar_sentinelas()
        assert exc_info.value.code == 1
        assert "atestados.DEMO-ATESTADO-0001" in capsys.readouterr().out

    def test_todas_sentinelas_presentes_nao_aborta(self, tmp_path, monkeypatch):
        demo_db = tmp_path / "pix_saude_demo.db"
        proc = _rodar_reset_sqlite(demo_db)
        assert proc.returncode == 0, f"setup do reset falhou:\n{proc.stdout}\n{proc.stderr}"

        self._apontar_get_conn_para(monkeypatch, demo_db)

        from scripts.reset_demo_db import _verificar_sentinelas
        _verificar_sentinelas()  # não deve lançar


class TestGuardas:
    def _rodar_com_env(self, tmp_path, env_over: dict) -> subprocess.CompletedProcess:
        env = {**os.environ, "PIX_SAUDE_DEMO_DB": str(tmp_path / "x.db"), **env_over}
        env.pop("DATABASE_URL", None)
        return subprocess.run(
            [sys.executable, str(_RESET_SCRIPT), "--sim-eu-quero"],
            cwd=str(_BACKEND_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_aborta_em_env_prod(self, tmp_path):
        proc = self._rodar_com_env(
            tmp_path, {"PICSAUDE_ENV": "prod", "PICSAUDE_DEMO_MODE": "true"}
        )
        assert proc.returncode == 1
        assert "PICSAUDE_ENV=prod" in proc.stdout

    def test_aborta_sem_demo_mode(self, tmp_path):
        proc = self._rodar_com_env(
            tmp_path, {"PICSAUDE_ENV": "stg", "PICSAUDE_DEMO_MODE": ""}
        )
        assert proc.returncode == 1
        assert "PICSAUDE_DEMO_MODE" in proc.stdout
