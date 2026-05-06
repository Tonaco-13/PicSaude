"""
app/instance.py
===============
Identificador único da instância PicSaúde (instance_id).

UUID v4 inalterável, gerado no primeiro boot, usado como marca d'água de
rastreabilidade conforme DATA-PROTECTION.md §4.2 e DATA-PROTECTION.md §2
(Mecanismos técnicos de proteção).

Persistência (defesa em profundidade):
  - Tabela ``meta_instalacao`` com chave ``instance_id`` — FONTE DE VERDADE
  - Arquivo ``.instance_id`` na raiz do projeto — ESPELHO/CACHE

Validações no boot:
  - Divergência entre DB e arquivo → ``RuntimeError`` (clone/restore detectado)
  - DB tem valor, arquivo ausente → recria arquivo a partir do DB
  - DB vazio, arquivo tem valor → INSERT no DB (recovery após reset de banco)
  - Valor não-UUID v4 → ``RuntimeError``

Race condition (first boot com múltiplos processos):
  - Estratégia: INSERT OR IGNORE (SQLite) / ON CONFLICT DO NOTHING (PostgreSQL)
    seguido de SELECT para garantir que ambos os processos retornem o mesmo
    UUID — o vencedor da inserção.

Override em dev/test:
  - ``PICSAUDE_INSTANCE_ID`` env var é respeitada apenas se
    ``PICSAUDE_ENV != "prod"``. Em produção, raise.

Path do arquivo (Docker / volumes):
  - Padrão: raiz do projeto.
  - Override via ``PICSAUDE_INSTANCE_ID_PATH`` para apontar para volume
    persistente (ex: ``/data/.instance_id``).

Referências:
  - docs/PLANO-PRODUCAO-V2.md (Etapa 4)
  - DATA-PROTECTION.md §4 (mecanismos de proteção)
  - app/models/meta_instalacao.py (modelo da tabela KV)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.meta_instalacao import MetaInstalacao

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_CHAVE_DB = "instance_id"

# Caminho default do arquivo .instance_id (raiz do projeto).
# Em produção (Docker), recomenda-se override via PICSAUDE_INSTANCE_ID_PATH
# para apontar para um volume persistente (ex: /data/.instance_id).
_DEFAULT_INSTANCE_FILE = (
    Path(__file__).resolve().parent.parent.parent / ".instance_id"
)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _get_instance_file() -> Path:
    """Retorna o caminho do arquivo .instance_id, respeitando override de env."""
    override = os.environ.get("PICSAUDE_INSTANCE_ID_PATH")
    if override:
        return Path(override)
    return _DEFAULT_INSTANCE_FILE


def _validar_uuid_v4(valor: str) -> str:
    """
    Valida que o valor é UUID v4 e retorna a forma canônica.

    Raises:
      RuntimeError: se o valor não for UUID válido ou não for v4.
    """
    try:
        u = uuid.UUID(valor)
    except (ValueError, TypeError) as e:
        raise RuntimeError(
            f"instance_id inválido (não é UUID parseável): {valor!r}"
        ) from e
    if u.version != 4:
        raise RuntimeError(
            f"instance_id deve ser UUID v4 (recebido v{u.version}): {valor}"
        )
    return str(u)


def _ler_arquivo() -> Optional[str]:
    """
    Lê e valida o arquivo .instance_id.

    Returns:
      str validado se o arquivo existe e tem conteúdo válido; ``None`` se
      ausente ou vazio.

    Raises:
      RuntimeError: se o arquivo existe mas o conteúdo não é UUID v4.
    """
    f = _get_instance_file()
    if not f.exists():
        return None
    raw = f.read_text().strip()
    if not raw:
        return None
    return _validar_uuid_v4(raw)


def _gravar_arquivo(instance_id: str) -> None:
    """
    Grava o instance_id no arquivo de forma atômica (tempfile + rename).

    O rename é atômico em sistemas POSIX, evitando arquivo parcial em caso
    de crash durante a escrita.
    """
    f = _get_instance_file()
    # Garante diretório pai existe (relevante para path customizado tipo /data/)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(instance_id)
    tmp.replace(f)


def _ler_db(session: Session) -> Optional[str]:
    """
    Lê o instance_id do DB (tabela meta_instalacao).

    Returns:
      str validado se a chave existe; ``None`` se ausente.

    Raises:
      RuntimeError: se a chave existe mas o valor armazenado não é UUID v4.
    """
    row = (
        session.query(MetaInstalacao)
        .filter_by(chave=_CHAVE_DB)
        .first()
    )
    if row is None:
        return None
    return _validar_uuid_v4(row.valor)


def _gravar_db(session: Session, instance_id: str) -> None:
    """
    Grava o instance_id no DB usando INSERT race-safe.

    Estratégia:
      - SQLite: ``INSERT OR IGNORE``
      - PostgreSQL: ``ON CONFLICT (chave) DO NOTHING``

    Em ambos os casos, dois processos competindo no first boot resultam em
    apenas uma linha — o vencedor da inserção. O chamador deve fazer SELECT
    após esta função para obter o valor efetivamente persistido.
    """
    agora = datetime.now(timezone.utc).isoformat()

    bind = session.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        sql = text(
            "INSERT OR IGNORE INTO meta_instalacao (chave, valor, criado_em) "
            "VALUES (:chave, :valor, :criado_em)"
        )
    else:  # postgresql, mysql etc.
        sql = text(
            "INSERT INTO meta_instalacao (chave, valor, criado_em) "
            "VALUES (:chave, :valor, :criado_em) "
            "ON CONFLICT (chave) DO NOTHING"
        )

    session.execute(
        sql,
        {
            "chave": _CHAVE_DB,
            "valor": instance_id,
            "criado_em": agora,
        },
    )
    session.commit()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def get_instance_id(session: Optional[Session] = None) -> str:
    """
    Retorna o instance_id da instância PicSaúde, gerando se primeiro boot.

    Ordem de precedência:
      1. Env var ``PICSAUDE_INSTANCE_ID`` (apenas se ``PICSAUDE_ENV != "prod"``)
      2. DB (``meta_instalacao.instance_id``) — FONTE DE VERDADE
      3. Arquivo ``.instance_id`` — ESPELHO/CACHE
      4. Gerar novo UUID v4 (first boot), persistir em DB e arquivo

    Args:
      session: SQLAlchemy ``Session`` ativa. Se ``None``, lê apenas do
        arquivo (modo degraded, útil para scripts/utilitários sem contexto
        de banco). Em produção, sempre passar ``session``.

    Returns:
      str: UUID v4 da instância no formato canônico
        ``"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"``.

    Raises:
      RuntimeError:
        - Divergência entre arquivo e DB (clone/restore detectado).
        - Valor armazenado não é UUID v4.
        - Env override usado em ``PICSAUDE_ENV=prod``.
        - Modo degraded sem arquivo disponível.
    """
    # ───────────────────────────────────────────────────────────────────
    # 1. Env override (apenas dev/test)
    # ───────────────────────────────────────────────────────────────────
    env_id = os.environ.get("PICSAUDE_INSTANCE_ID")
    if env_id:
        env_modo = os.environ.get("PICSAUDE_ENV", "dev")
        if env_modo == "prod":
            raise RuntimeError(
                "PICSAUDE_INSTANCE_ID env var não pode ser usada em "
                "PICSAUDE_ENV=prod. Em produção, instance_id é gerado "
                "automaticamente no primeiro boot e persistido."
            )
        return _validar_uuid_v4(env_id)

    # ───────────────────────────────────────────────────────────────────
    # Modo degraded: sem session, lê apenas do arquivo
    # ───────────────────────────────────────────────────────────────────
    if session is None:
        valor_arquivo = _ler_arquivo()
        if valor_arquivo:
            return valor_arquivo
        raise RuntimeError(
            "instance_id não disponível: arquivo .instance_id ausente e "
            "session de DB não fornecida. Forneça session ou rode primeiro "
            "boot com session ativa."
        )

    # ───────────────────────────────────────────────────────────────────
    # Modo normal: DB é fonte de verdade
    # ───────────────────────────────────────────────────────────────────
    valor_db = _ler_db(session)
    valor_arquivo = _ler_arquivo()

    # Caso 1: ambos têm valor
    if valor_db and valor_arquivo:
        if valor_db != valor_arquivo:
            raise RuntimeError(
                f"DIVERGÊNCIA detectada no instance_id: "
                f"DB={valor_db[:8]}... vs arquivo={valor_arquivo[:8]}.... "
                f"Indica clone, restore parcial ou corrupção. "
                f"Investigue antes de prosseguir — não é seguro continuar."
            )
        return valor_db

    # Caso 2: DB tem valor, arquivo ausente → recriar arquivo
    if valor_db and not valor_arquivo:
        _gravar_arquivo(valor_db)
        return valor_db

    # Caso 3: DB vazio, arquivo tem valor → recovery (insere no DB)
    if valor_arquivo and not valor_db:
        _gravar_db(session, valor_arquivo)
        # Re-ler para obter valor efetivamente persistido (race-safe)
        final = _ler_db(session)
        return final or valor_arquivo

    # Caso 4: ambos vazios → first boot, gerar novo
    novo = str(uuid.uuid4())
    _gravar_db(session, novo)
    # Re-ler do DB: se outro processo venceu a race, retorna o valor dele
    final = _ler_db(session)
    if final is None:
        # Não deveria acontecer: INSERT OR IGNORE garante presença
        raise RuntimeError(
            "Falha ao persistir instance_id no DB durante first boot. "
            "Verifique conexão e existência da tabela meta_instalacao."
        )
    _gravar_arquivo(final)
    return final
