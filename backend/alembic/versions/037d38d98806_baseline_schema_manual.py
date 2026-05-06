"""baseline_schema_manual

Migration MANUAL — não gerada por autogenerate.

Esta migration representa o snapshot do schema PicSaúde no momento da
introdução do Alembic. É a âncora histórica de todas as migrations futuras.

Por que manual:
  - autogenerate compararia models Python com banco de dev (SQLite),
    potencialmente gerando operações incorretas ou incompletas.
  - A baseline manual garante um ponto de partida auditável e independente
    do estado do banco de desenvolvimento.

O que está incluído:
  - 27 tabelas do núcleo PicSaúde
  - PKs, UNIQUEs, FKs, índices essenciais
  - Tipos compatíveis com PostgreSQL (alvo principal de produção)
  - classe_controle em prescricao_itens (Ticket 44) — campo que ficou fora
    do banco por limitação do create_all() (não faz ALTER TABLE)

Instruções de uso:
  # Banco PostgreSQL limpo (primeira instalação):
  alembic upgrade head

  # Banco existente (SQLite de dev já populado):
  alembic stamp 037d38d98806   ← registra sem rodar as DDLs
  alembic upgrade head          ← aplica apenas migrations APÓS esta

Revision ID: 037d38d98806
Revises:
Create Date: 2026-04-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '037d38d98806'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helper — idempotência: não falha se tabela já existir
# ---------------------------------------------------------------------------

def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


# ---------------------------------------------------------------------------
# UPGRADE — cria schema completo em banco limpo
# ---------------------------------------------------------------------------

def upgrade() -> None:
    """
    Cria todas as tabelas do núcleo PicSaúde.

    Cada create_table é envolvido em guarda _table_exists() para ser
    idempotente: se o banco já tiver a tabela (ex: SQLite de dev),
    a operação é ignorada silenciosamente.

    Ordem de criação respeita dependências de FK:
      1. entidades independentes (pacientes, prescritores, prestadores…)
      2. entidades dependentes (prescricoes, pedidos_exame, laudos…)
      3. tabelas de relacionamento (custódia, eventos, dispensações…)
    """

    # ------------------------------------------------------------------
    # 1. ENTIDADES RAIZ
    # ------------------------------------------------------------------

    if not _table_exists("pacientes"):
        op.create_table(
            "pacientes",
            sa.Column("id",         sa.Integer(),  nullable=False),
            sa.Column("cpf",        sa.String(),   nullable=False),
            sa.Column("nome",       sa.String(),   nullable=False),
            sa.Column("telefone",   sa.String(),   nullable=True),
            sa.Column("ativo",      sa.Boolean(),  nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pacientes_id",  "pacientes", ["id"],  unique=False)
        op.create_index("ix_pacientes_cpf", "pacientes", ["cpf"], unique=True)

    if not _table_exists("prescritores"):
        op.create_table(
            "prescritores",
            sa.Column("id",                 sa.Integer(), nullable=False),
            sa.Column("cns",                sa.String(),  nullable=False),
            sa.Column("nome",               sa.String(),  nullable=False),
            sa.Column("telefone_vinculado", sa.String(),  nullable=True),
            sa.Column("email",              sa.String(),  nullable=True),
            sa.Column("ativo",              sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at",         sa.DateTime(), nullable=False),
            sa.Column("updated_at",         sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescritores_id",  "prescritores", ["id"],  unique=False)
        op.create_index("ix_prescritores_cns", "prescritores", ["cns"], unique=True)

    if not _table_exists("prestadores"):
        op.create_table(
            "prestadores",
            sa.Column("id",         sa.Integer(), nullable=False),
            sa.Column("cnpj",       sa.String(),  nullable=False),
            sa.Column("nome",       sa.String(),  nullable=False),
            sa.Column("tipo",       sa.String(),  nullable=True),
            sa.Column("ativo",      sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prestadores_id",   "prestadores", ["id"],   unique=False)
        op.create_index("ix_prestadores_cnpj", "prestadores", ["cnpj"], unique=True)

    if not _table_exists("usuarios"):
        op.create_table(
            "usuarios",
            sa.Column("id",            sa.Integer(), nullable=False),
            sa.Column("role",          sa.String(),  nullable=False),
            sa.Column("identificador", sa.String(),  nullable=False),
            sa.Column("nome",          sa.String(),  nullable=False),
            sa.Column("senha_hash",    sa.String(),  nullable=False),
            sa.Column("ativo",         sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at",    sa.DateTime(), nullable=False),
            sa.Column("updated_at",    sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_usuarios_id",            "usuarios", ["id"],            unique=False)
        op.create_index("ix_usuarios_identificador", "usuarios", ["identificador"], unique=True)

    if not _table_exists("codigos_login"):
        op.create_table(
            "codigos_login",
            sa.Column("id",         sa.Integer(),  nullable=False),
            sa.Column("cpf",        sa.String(),   nullable=False),
            sa.Column("codigo",     sa.String(),   nullable=False),
            sa.Column("expiracao",  sa.DateTime(), nullable=False),
            sa.Column("usado",      sa.Integer(),  nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_codigos_login_id",  "codigos_login", ["id"],  unique=False)
        op.create_index("ix_codigos_login_cpf", "codigos_login", ["cpf"], unique=False)

    if not _table_exists("meta_instalacao"):
        op.create_table(
            "meta_instalacao",
            sa.Column("chave",     sa.Text(), nullable=False),
            sa.Column("valor",     sa.Text(), nullable=False),
            sa.Column("criado_em", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("chave"),
        )

    # ------------------------------------------------------------------
    # 2. PRESCRIÇÕES (depende de prescritores + pacientes)
    # ------------------------------------------------------------------

    if not _table_exists("prescricoes"):
        op.create_table(
            "prescricoes",
            sa.Column("id",                          sa.Integer(),     nullable=False),
            sa.Column("protocolo",                   sa.String(),      nullable=False),
            sa.Column("prescritor_id",               sa.Integer(),     nullable=False),
            sa.Column("paciente_id",                 sa.Integer(),     nullable=False),
            sa.Column("status",                      sa.String(),      nullable=False),
            sa.Column("assinatura_modo",             sa.String(),      nullable=True),
            sa.Column("assinatura_hash",             sa.String(),      nullable=True),
            sa.Column("tipo_emissao",                sa.String(),      nullable=False, server_default=sa.text("'nova'")),
            sa.Column("origem_prescricao_id",        sa.Integer(),     nullable=True),
            sa.Column("indicacao_clinica",           sa.Text(),        nullable=True),
            sa.Column("codigo_cid",                  sa.String(),      nullable=True),
            sa.Column("string_validacao_prescritor", sa.String(512),   nullable=True),
            sa.Column("data_emissao",                sa.DateTime(),    nullable=False),
            sa.Column("data_validade",               sa.DateTime(),    nullable=True),
            sa.Column("created_at",                  sa.DateTime(),    nullable=False),
            sa.Column("updated_at",                  sa.DateTime(),    nullable=False),
            sa.ForeignKeyConstraint(["prescritor_id"],        ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"],          ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_prescricao_id"], ["prescricoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescricoes_id",        "prescricoes", ["id"],        unique=False)
        op.create_index("ix_prescricoes_protocolo", "prescricoes", ["protocolo"], unique=True)

    if not _table_exists("prescricao_itens"):
        op.create_table(
            "prescricao_itens",
            sa.Column("id",                sa.Integer(),   nullable=False),
            sa.Column("prescricao_id",     sa.Integer(),   nullable=False),
            sa.Column("nome_medicamento",  sa.String(),    nullable=False),
            sa.Column("concentracao",      sa.String(),    nullable=True),
            sa.Column("quantidade",        sa.Integer(),   nullable=True),
            sa.Column("unidade_quantidade",sa.String(),    nullable=True),
            sa.Column("forma_farmaceutica",sa.String(),    nullable=True),
            sa.Column("posologia",         sa.Text(),      nullable=True),
            sa.Column("status_item",       sa.String(),    nullable=False, server_default=sa.text("'pendente'")),
            # Ticket 44 — classe regulatória (NULL = medicamento comum)
            sa.Column("classe_controle",   sa.String(10),  nullable=True),
            sa.Column("created_at",        sa.DateTime(),  nullable=False),
            sa.Column("updated_at",        sa.DateTime(),  nullable=False),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescricao_itens_id", "prescricao_itens", ["id"], unique=False)

    if not _table_exists("prescricao_eventos"):
        op.create_table(
            "prescricao_eventos",
            sa.Column("id",            sa.Integer(), nullable=False),
            sa.Column("prescricao_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento",   sa.String(),  nullable=False),
            sa.Column("ator_tipo",     sa.String(),  nullable=False),
            sa.Column("ator_id",       sa.String(),  nullable=True),
            sa.Column("payload_json",  sa.Text(),    nullable=True),
            sa.Column("created_at",    sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescricao_eventos_id", "prescricao_eventos", ["id"], unique=False)

    if not _table_exists("prescricao_custodia"):
        op.create_table(
            "prescricao_custodia",
            sa.Column("id",                   sa.Integer(),  nullable=False),
            sa.Column("prescricao_id",        sa.Integer(),  nullable=False),
            sa.Column("item_id",              sa.Integer(),  nullable=True),
            sa.Column("detentor_tipo",        sa.String(),   nullable=False),
            sa.Column("detentor_id",          sa.String(),   nullable=False),
            sa.Column("transferida_em",       sa.DateTime(), nullable=False),
            sa.Column("encerrada_em",         sa.DateTime(), nullable=True),
            sa.Column("motivo",               sa.String(),   nullable=True),
            sa.Column("contexto_operacional", sa.String(),   nullable=True),
            sa.Column("unidade_id",           sa.String(),   nullable=True),
            sa.Column("created_at",           sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.ForeignKeyConstraint(["item_id"],       ["prescricao_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescricao_custodia_id",           "prescricao_custodia", ["id"],           unique=False)
        op.create_index("ix_prescricao_custodia_prescricao_id","prescricao_custodia", ["prescricao_id"],unique=False)
        op.create_index("ix_prescricao_custodia_item_id",      "prescricao_custodia", ["item_id"],      unique=False)

    if not _table_exists("prescricao_assinatura"):
        op.create_table(
            "prescricao_assinatura",
            sa.Column("id",                   sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("prescricao_id",        sa.Integer(), nullable=False),
            sa.Column("tipo_certificado",     sa.String(),  nullable=True),
            sa.Column("emissor",              sa.String(),  nullable=True),
            sa.Column("serial_certificado",   sa.String(),  nullable=True),
            sa.Column("timestamp_assinatura", sa.String(),  nullable=True),
            sa.Column("hash_documento",       sa.String(),  nullable=True),
            sa.Column("dados_assinatura_b64", sa.Text(),    nullable=True),
            sa.Column("status_validacao",     sa.String(),  nullable=False, server_default=sa.text("'assinatura_pendente'")),
            sa.Column("detalhe_validacao",    sa.Text(),    nullable=True),
            sa.Column("created_at",           sa.String(),  nullable=False),
            sa.Column("updated_at",           sa.String(),  nullable=False),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("prescricao_id", name="uq_prescricao_assinatura_prescricao"),
        )
        op.create_index("ix_prescricao_assinatura_prescricao_id", "prescricao_assinatura", ["prescricao_id"], unique=False)

    if not _table_exists("solicitacoes_renovacao"):
        op.create_table(
            "solicitacoes_renovacao",
            sa.Column("id",                        sa.Integer(),  nullable=False, autoincrement=True),
            sa.Column("protocolo_prescricao",      sa.String(50), nullable=False),
            sa.Column("prescricao_id",             sa.Integer(),  nullable=True),
            sa.Column("cpf_paciente",              sa.String(11), nullable=False),
            sa.Column("cns_prescritor",            sa.String(15), nullable=False),
            sa.Column("status",                    sa.String(20), nullable=False, server_default=sa.text("'pendente'")),
            sa.Column("motivo",                    sa.Text(),     nullable=True),
            sa.Column("criado_em",                 sa.DateTime(), nullable=False),
            sa.Column("respondido_em",             sa.DateTime(), nullable=True),
            sa.Column("respondido_por",            sa.String(15), nullable=True),
            sa.Column("observacao_resposta",       sa.Text(),     nullable=True),
            sa.Column("nova_prescricao_protocolo", sa.String(50), nullable=True),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_solicitacoes_renovacao_protocolo_prescricao", "solicitacoes_renovacao", ["protocolo_prescricao"], unique=False)
        op.create_index("ix_solicitacoes_renovacao_cpf_paciente",          "solicitacoes_renovacao", ["cpf_paciente"],          unique=False)
        op.create_index("ix_solicitacoes_renovacao_cns_prescritor",        "solicitacoes_renovacao", ["cns_prescritor"],        unique=False)

    # ------------------------------------------------------------------
    # 3. DISPENSAÇÕES (depende de prescricao_itens)
    # ------------------------------------------------------------------

    if not _table_exists("dispensacoes"):
        op.create_table(
            "dispensacoes",
            sa.Column("id",                    sa.Integer(),   nullable=False),
            sa.Column("prescricao_item_id",    sa.Integer(),   nullable=False),
            sa.Column("cnpj_estabelecimento",  sa.String(),    nullable=False),
            sa.Column("quantidade_dispensada", sa.Integer(),   nullable=False),
            sa.Column("dispensado_por",        sa.String(),    nullable=True),
            sa.Column("dispensado_em",         sa.DateTime(),  nullable=False),
            sa.Column("lote",                  sa.String(50),  nullable=True),
            sa.Column("fabricante",            sa.String(),    nullable=True),
            sa.Column("observacao",            sa.Text(),      nullable=True),
            sa.Column("origem_contexto",       sa.String(30),  nullable=True),
            sa.Column("created_at",            sa.DateTime(),  nullable=False),
            sa.ForeignKeyConstraint(["prescricao_item_id"], ["prescricao_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_dispensacoes_id",                   "dispensacoes", ["id"],                   unique=False)
        op.create_index("ix_dispensacoes_prescricao_item_id",   "dispensacoes", ["prescricao_item_id"],   unique=False)
        op.create_index("ix_dispensacoes_cnpj_estabelecimento", "dispensacoes", ["cnpj_estabelecimento"], unique=False)

    if not _table_exists("dispensacoes_hospitalares"):
        op.create_table(
            "dispensacoes_hospitalares",
            sa.Column("id",                 sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("dispensacao_id",     sa.Integer(), nullable=False),
            sa.Column("prescricao_item_id", sa.Integer(), nullable=False),
            sa.Column("protocolo",          sa.Text(),    nullable=False),
            sa.Column("org_id",             sa.Text(),    nullable=False),
            sa.Column("unidade_id",         sa.Text(),    nullable=False),
            sa.Column("setor",              sa.Text(),    nullable=True),
            sa.Column("leito",              sa.Text(),    nullable=True),
            sa.Column("modalidade",         sa.Text(),    nullable=False, server_default=sa.text("'internacao'")),
            sa.Column("dose_unitaria",      sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("quantidade_doses",   sa.Integer(), nullable=True),
            sa.Column("dispensado_por",     sa.Text(),    nullable=False),
            sa.Column("dispensado_em",      sa.Text(),    nullable=False),
            sa.Column("criado_em",          sa.Text(),    nullable=False),
            sa.ForeignKeyConstraint(["dispensacao_id"],     ["dispensacoes.id"]),
            sa.ForeignKeyConstraint(["prescricao_item_id"], ["prescricao_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_dispensacoes_hospitalares_dispensacao_id",     "dispensacoes_hospitalares", ["dispensacao_id"],     unique=False)
        op.create_index("ix_dispensacoes_hospitalares_prescricao_item_id", "dispensacoes_hospitalares", ["prescricao_item_id"], unique=False)
        op.create_index("ix_dispensacoes_hospitalares_org_id",             "dispensacoes_hospitalares", ["org_id"],             unique=False)
        op.create_index("ix_dispensacoes_hospitalares_unidade_id",         "dispensacoes_hospitalares", ["unidade_id"],         unique=False)
        op.create_index("ix_dispensacoes_hospitalares_protocolo",          "dispensacoes_hospitalares", ["protocolo"],          unique=False)

    # ------------------------------------------------------------------
    # 4. TOKENS DE APRESENTAÇÃO (depende de prescricao_itens)
    # ------------------------------------------------------------------

    if not _table_exists("tokens_apresentacao"):
        op.create_table(
            "tokens_apresentacao",
            sa.Column("id",           sa.Integer(),   nullable=False),
            sa.Column("codigo_curto", sa.String(8),   nullable=False),
            sa.Column("protocolo",    sa.Text(),       nullable=False),
            sa.Column("paciente_cpf", sa.String(11),  nullable=False),
            sa.Column("escopo",       sa.String(30),  nullable=False, server_default=sa.text("'apresentacao'")),
            sa.Column("status",       sa.String(20),  nullable=False, server_default=sa.text("'ativo'")),
            sa.Column("expira_em",    sa.Text(),       nullable=False),
            sa.Column("criado_em",    sa.Text(),       nullable=False),
            sa.Column("item_id",      sa.Integer(),   nullable=True),
            sa.Column("revogado_em",  sa.Text(),       nullable=True),
            sa.Column("revogado_por", sa.Text(),       nullable=True),
            sa.ForeignKeyConstraint(["item_id"], ["prescricao_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tokens_apresentacao_codigo_curto", "tokens_apresentacao", ["codigo_curto"], unique=True)
        op.create_index("ix_tokens_apresentacao_protocolo",    "tokens_apresentacao", ["protocolo"],    unique=False)
        op.create_index("ix_tokens_apresentacao_paciente_cpf", "tokens_apresentacao", ["paciente_cpf"], unique=False)

    if not _table_exists("tokens_apresentacao_usos"):
        op.create_table(
            "tokens_apresentacao_usos",
            sa.Column("id",                   sa.Integer(),   nullable=False),
            sa.Column("token_id",             sa.Integer(),   nullable=True),
            sa.Column("codigo_curto",         sa.String(8),   nullable=False),
            sa.Column("dispensador_cns",      sa.String(15),  nullable=True),
            sa.Column("cnpj_estabelecimento", sa.String(14),  nullable=True),
            sa.Column("resultado",            sa.String(30),  nullable=False),
            sa.Column("protocolo_resolvido",  sa.Text(),       nullable=True),
            sa.Column("criado_em",            sa.Text(),       nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tokens_apresentacao_usos_codigo_curto", "tokens_apresentacao_usos", ["codigo_curto"], unique=False)

    # ------------------------------------------------------------------
    # 5. PEDIDOS DE EXAME (depende de prescritores + pacientes)
    # ------------------------------------------------------------------

    if not _table_exists("pedidos_exame"):
        op.create_table(
            "pedidos_exame",
            sa.Column("id",                sa.Integer(),   nullable=False, autoincrement=True),
            sa.Column("protocolo",         sa.String(50),  nullable=False),
            sa.Column("prescritor_id",     sa.Integer(),   nullable=True),
            sa.Column("paciente_id",       sa.Integer(),   nullable=True),
            sa.Column("status",            sa.String(30),  nullable=False, server_default=sa.text("'emitido'")),
            sa.Column("tipo_emissao",      sa.String(20),  nullable=False, server_default=sa.text("'novo'")),
            sa.Column("origem_pedido_id",  sa.Integer(),   nullable=True),
            sa.Column("prioridade",        sa.String(20),  nullable=False, server_default=sa.text("'rotina'")),
            sa.Column("indicacao_clinica", sa.Text(),       nullable=True),
            sa.Column("data_emissao",      sa.String(10),  nullable=False),
            sa.Column("data_validade",     sa.String(10),  nullable=False),
            sa.Column("assinatura_hash",   sa.String(64),  nullable=True),
            sa.Column("criado_em",         sa.DateTime(),  nullable=False),
            sa.ForeignKeyConstraint(["prescritor_id"],    ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"],      ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_pedido_id"], ["pedidos_exame.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pedidos_exame_protocolo", "pedidos_exame", ["protocolo"], unique=True)

    if not _table_exists("pedido_exame_itens"):
        op.create_table(
            "pedido_exame_itens",
            sa.Column("id",               sa.Integer(),    nullable=False, autoincrement=True),
            sa.Column("pedido_id",        sa.Integer(),    nullable=False),
            sa.Column("nome_exame",       sa.String(200),  nullable=False),
            sa.Column("codigo_tuss",      sa.String(20),   nullable=True),
            sa.Column("codigo_sigtap",    sa.String(20),   nullable=True),
            sa.Column("status_item",      sa.String(30),   nullable=False, server_default=sa.text("'pendente'")),
            sa.Column("quantidade",       sa.Integer(),    nullable=False, server_default=sa.text("1")),
            sa.Column("resultado_resumo", sa.Text(),       nullable=True),
            sa.Column("resultado_url",    sa.Text(),       nullable=True),
            sa.Column("resultado_em",     sa.DateTime(),   nullable=True),
            sa.Column("criado_em",        sa.DateTime(),   nullable=False),
            sa.ForeignKeyConstraint(["pedido_id"], ["pedidos_exame.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pedido_exame_itens_pedido_id", "pedido_exame_itens", ["pedido_id"], unique=False)

    if not _table_exists("pedido_exame_eventos"):
        op.create_table(
            "pedido_exame_eventos",
            sa.Column("id",          sa.Integer(),  nullable=False, autoincrement=True),
            sa.Column("pedido_id",   sa.Integer(),  nullable=False),
            sa.Column("tipo_evento", sa.String(60), nullable=False),
            sa.Column("dados_json",  sa.Text(),     nullable=True),
            sa.Column("criado_em",   sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["pedido_id"], ["pedidos_exame.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pedido_exame_eventos_pedido_id", "pedido_exame_eventos", ["pedido_id"], unique=False)

    if not _table_exists("pedido_exame_custodia"):
        op.create_table(
            "pedido_exame_custodia",
            sa.Column("id",             sa.Integer(),  nullable=False, autoincrement=True),
            sa.Column("pedido_id",      sa.Integer(),  nullable=False),
            sa.Column("item_id",        sa.Integer(),  nullable=True),
            sa.Column("de",             sa.String(100), nullable=False),
            sa.Column("para",           sa.String(100), nullable=False),
            sa.Column("transferido_em", sa.DateTime(), nullable=False),
            sa.Column("dados_json",     sa.Text(),     nullable=True),
            sa.ForeignKeyConstraint(["pedido_id"], ["pedidos_exame.id"]),
            sa.ForeignKeyConstraint(["item_id"],   ["pedido_exame_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pedido_exame_custodia_pedido_id", "pedido_exame_custodia", ["pedido_id"], unique=False)

    # ------------------------------------------------------------------
    # 6. LAUDOS (depende de prescritores + pacientes + pedidos_exame)
    # ------------------------------------------------------------------

    if not _table_exists("laudos"):
        op.create_table(
            "laudos",
            sa.Column("id",               sa.Integer(),  nullable=False, autoincrement=True),
            sa.Column("protocolo",        sa.String(50), nullable=False),
            sa.Column("autor_id",         sa.Integer(),  nullable=True),
            sa.Column("paciente_id",      sa.Integer(),  nullable=True),
            sa.Column("pedido_id",        sa.Integer(),  nullable=True),
            sa.Column("status",           sa.String(30), nullable=False, server_default=sa.text("'em_producao'")),
            sa.Column("tipo_emissao",     sa.String(20), nullable=False, server_default=sa.text("'novo'")),
            sa.Column("origem_laudo_id",  sa.Integer(),  nullable=True),
            sa.Column("data_emissao",     sa.String(10), nullable=False),
            sa.Column("data_validade",    sa.String(10), nullable=True),
            sa.Column("assinatura_hash",  sa.String(64), nullable=True),
            sa.Column("criado_em",        sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["autor_id"],        ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"],     ["pacientes.id"]),
            sa.ForeignKeyConstraint(["pedido_id"],       ["pedidos_exame.id"]),
            sa.ForeignKeyConstraint(["origem_laudo_id"], ["laudos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_laudos_protocolo", "laudos", ["protocolo"], unique=True)

    if not _table_exists("laudo_itens"):
        op.create_table(
            "laudo_itens",
            sa.Column("id",               sa.Integer(),    nullable=False, autoincrement=True),
            sa.Column("laudo_id",         sa.Integer(),    nullable=False),
            sa.Column("nome_exame",       sa.String(200),  nullable=False),
            sa.Column("codigo_tuss",      sa.String(20),   nullable=True),
            sa.Column("resultado_resumo", sa.Text(),       nullable=True),
            sa.Column("conclusao",        sa.String(30),   nullable=True),
            sa.Column("valor_referencia", sa.Text(),       nullable=True),
            sa.Column("resultado_url",    sa.Text(),       nullable=True),
            sa.Column("status_item",      sa.String(30),   nullable=False, server_default=sa.text("'em_producao'")),
            sa.Column("criado_em",        sa.DateTime(),   nullable=False),
            sa.ForeignKeyConstraint(["laudo_id"], ["laudos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_laudo_itens_laudo_id", "laudo_itens", ["laudo_id"], unique=False)

    if not _table_exists("laudo_eventos"):
        op.create_table(
            "laudo_eventos",
            sa.Column("id",          sa.Integer(),  nullable=False, autoincrement=True),
            sa.Column("laudo_id",    sa.Integer(),  nullable=False),
            sa.Column("tipo_evento", sa.String(60), nullable=False),
            sa.Column("dados_json",  sa.Text(),     nullable=True),
            sa.Column("criado_em",   sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["laudo_id"], ["laudos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_laudo_eventos_laudo_id", "laudo_eventos", ["laudo_id"], unique=False)

    if not _table_exists("laudo_custodia"):
        op.create_table(
            "laudo_custodia",
            sa.Column("id",             sa.Integer(),    nullable=False, autoincrement=True),
            sa.Column("laudo_id",       sa.Integer(),    nullable=False),
            sa.Column("item_id",        sa.Integer(),    nullable=True),
            sa.Column("de",             sa.String(100),  nullable=False),
            sa.Column("para",           sa.String(100),  nullable=False),
            sa.Column("transferido_em", sa.DateTime(),   nullable=False),
            sa.Column("dados_json",     sa.Text(),       nullable=True),
            sa.ForeignKeyConstraint(["laudo_id"], ["laudos.id"]),
            sa.ForeignKeyConstraint(["item_id"],  ["laudo_itens.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_laudo_custodia_laudo_id", "laudo_custodia", ["laudo_id"], unique=False)

    # ------------------------------------------------------------------
    # 7. AGENDAMENTOS (depende de pedidos_exame + pacientes)
    # ------------------------------------------------------------------

    if not _table_exists("agendamentos"):
        op.create_table(
            "agendamentos",
            sa.Column("id",                    sa.Integer(),   nullable=False),
            sa.Column("protocolo",             sa.String(),    nullable=False),
            sa.Column("pedido_id",             sa.Integer(),   nullable=False),
            sa.Column("paciente_id",           sa.Integer(),   nullable=False),
            sa.Column("org_id",                sa.Text(),      nullable=False),
            sa.Column("unidade_id",            sa.Text(),      nullable=False),
            sa.Column("tipo_agendamento",      sa.String(30),  nullable=False, server_default=sa.text("'exame'")),
            sa.Column("data_hora",             sa.Text(),      nullable=False),
            sa.Column("local_texto",           sa.Text(),      nullable=True),
            sa.Column("observacao",            sa.Text(),      nullable=True),
            sa.Column("status",                sa.String(30),  nullable=False, server_default=sa.text("'criado'")),
            sa.Column("tipo_emissao",          sa.String(20),  nullable=False, server_default=sa.text("'novo'")),
            sa.Column("origem_agendamento_id", sa.Integer(),   nullable=True),
            sa.Column("criado_por",            sa.Text(),      nullable=False),
            sa.Column("criado_em",             sa.Text(),      nullable=False),
            sa.ForeignKeyConstraint(["pedido_id"],             ["pedidos_exame.id"]),
            sa.ForeignKeyConstraint(["paciente_id"],           ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_agendamento_id"], ["agendamentos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agendamentos_id",        "agendamentos", ["id"],        unique=False)
        op.create_index("ix_agendamentos_protocolo", "agendamentos", ["protocolo"], unique=True)
        op.create_index("ix_agendamentos_pedido_id", "agendamentos", ["pedido_id"], unique=False)
        op.create_index("ix_agendamentos_org_id",    "agendamentos", ["org_id"],    unique=False)
        op.create_index("ix_agendamentos_unidade_id","agendamentos", ["unidade_id"],unique=False)

    if not _table_exists("agendamento_eventos"):
        op.create_table(
            "agendamento_eventos",
            sa.Column("id",             sa.Integer(), nullable=False),
            sa.Column("agendamento_id", sa.Integer(), nullable=False),
            sa.Column("evento",         sa.Text(),    nullable=False),
            sa.Column("payload",        sa.Text(),    nullable=True),
            sa.Column("criado_em",      sa.Text(),    nullable=False),
            sa.ForeignKeyConstraint(["agendamento_id"], ["agendamentos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agendamento_eventos_id",             "agendamento_eventos", ["id"],             unique=False)
        op.create_index("ix_agendamento_eventos_agendamento_id", "agendamento_eventos", ["agendamento_id"], unique=False)

    # ------------------------------------------------------------------
    # 8. OUTBOX DE EVENTOS (G4A — sem FK, tabela autônoma)
    # ------------------------------------------------------------------

    if not _table_exists("eventos_publicacao"):
        op.create_table(
            "eventos_publicacao",
            sa.Column("id",           sa.Text(),    nullable=False),
            sa.Column("tipo_evento",  sa.Text(),    nullable=False),
            sa.Column("objeto_tipo",  sa.Text(),    nullable=False),
            sa.Column("objeto_id",    sa.Text(),    nullable=False),
            sa.Column("payload",      sa.Text(),    nullable=False),
            sa.Column("org_id",       sa.Text(),    nullable=True),
            sa.Column("unidade_id",   sa.Text(),    nullable=True),
            sa.Column("publicado",    sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("tentativas",   sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("criado_em",    sa.Text(),    nullable=False),
            sa.Column("publicado_em", sa.Text(),    nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


# ---------------------------------------------------------------------------
# DOWNGRADE — remove tabelas na ordem inversa (FKs)
# ---------------------------------------------------------------------------

def downgrade() -> None:
    """
    Remove todas as tabelas criadas pelo upgrade.

    ATENÇÃO: operação destrutiva. Em produção, execute somente após
    confirmação explícita e com backup do banco.
    """
    tables_in_reverse = [
        "eventos_publicacao",
        "agendamento_eventos",
        "agendamentos",
        "laudo_custodia",
        "laudo_eventos",
        "laudo_itens",
        "laudos",
        "pedido_exame_custodia",
        "pedido_exame_eventos",
        "pedido_exame_itens",
        "pedidos_exame",
        "tokens_apresentacao_usos",
        "tokens_apresentacao",
        "dispensacoes_hospitalares",
        "dispensacoes",
        "solicitacoes_renovacao",
        "prescricao_assinatura",
        "prescricao_custodia",
        "prescricao_eventos",
        "prescricao_itens",
        "prescricoes",
        "codigos_login",
        "meta_instalacao",
        "usuarios",
        "prestadores",
        "prescritores",
        "pacientes",
    ]
    for table in tables_in_reverse:
        if _table_exists(table):
            op.drop_table(table)
