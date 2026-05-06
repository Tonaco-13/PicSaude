-- =============================================================================
-- Ticket 52 — Circulação Diagnóstica: modelo de dados
-- =============================================================================
--
-- Objetivo: criar as três tabelas do módulo de Circulação Diagnóstica.
--
--   circulacoes_diagnosticas        — objeto principal (chave + negociação)
--   circulacao_diagnostica_itens    — vínculo com itens do pedido de exame
--   circulacao_diagnostica_eventos  — ledger imutável
--
-- Referência arquitetural: docs/ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md
-- Estados: backend/app/domain/states_circulacao_diagnostica.py
--
-- Regras:
--   - circulacao_diagnostica_eventos nunca recebe UPDATE nem DELETE.
--   - Um item de pedido não pode pertencer a duas circulações ativas
--     simultaneamente (constraint verificada no router, não no banco SQLite).
--   - Esta migration é idempotente (CREATE TABLE IF NOT EXISTS).
--
-- Rollback:
--   DROP TABLE IF EXISTS circulacao_diagnostica_eventos;
--   DROP TABLE IF EXISTS circulacao_diagnostica_itens;
--   DROP TABLE IF EXISTS circulacoes_diagnosticas;
--
-- Data: 2026-03-31
-- Autor: Ticket 52 / PicSaúde
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Tabela principal
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS circulacoes_diagnosticas (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo            TEXT    NOT NULL UNIQUE,   -- UUID
    chave_circulacao     TEXT    NOT NULL UNIQUE,   -- chave apresentada ao laboratório

    pedido_id            INTEGER NOT NULL REFERENCES pedidos_exame(id),
    paciente_id          INTEGER NOT NULL REFERENCES pacientes(id),

    -- Laboratório destinatário — contexto institucional obrigatório
    org_id               TEXT    NOT NULL,
    unidade_id           TEXT    NOT NULL,

    -- Proposta do laboratório (preenchidos em proposta_recebida)
    data_hora_proposta   TEXT,   -- ISO 8601 datetime
    local_texto          TEXT,
    instrucoes_preparo   TEXT,

    observacao           TEXT,

    status               TEXT    NOT NULL DEFAULT 'selecionado',
    tipo_emissao         TEXT    NOT NULL DEFAULT 'novo',   -- novo | remarcacao
    origem_circulacao_id INTEGER REFERENCES circulacoes_diagnosticas(id),

    validade             TEXT    NOT NULL,   -- ISO 8601 datetime — expiração da chave

    criado_por           TEXT    NOT NULL,   -- CPF do paciente
    criado_em            TEXT    NOT NULL    -- ISO 8601 datetime
);

CREATE INDEX IF NOT EXISTS idx_circulacoes_diagnosticas_pedido_id
    ON circulacoes_diagnosticas(pedido_id);

CREATE INDEX IF NOT EXISTS idx_circulacoes_diagnosticas_paciente_id
    ON circulacoes_diagnosticas(paciente_id);

CREATE INDEX IF NOT EXISTS idx_circulacoes_diagnosticas_org_id
    ON circulacoes_diagnosticas(org_id);

CREATE INDEX IF NOT EXISTS idx_circulacoes_diagnosticas_unidade_id
    ON circulacoes_diagnosticas(unidade_id);

-- ---------------------------------------------------------------------------
-- 2. Itens da circulação
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS circulacao_diagnostica_itens (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    circulacao_id        INTEGER NOT NULL REFERENCES circulacoes_diagnosticas(id),
    pedido_exame_item_id INTEGER NOT NULL REFERENCES pedido_exame_itens(id),
    nome_exame           TEXT    NOT NULL,   -- denormalizado para leitura
    criado_em            TEXT    NOT NULL    -- ISO 8601 datetime
);

CREATE INDEX IF NOT EXISTS idx_circulacao_diagnostica_itens_circulacao_id
    ON circulacao_diagnostica_itens(circulacao_id);

CREATE INDEX IF NOT EXISTS idx_circulacao_diagnostica_itens_pedido_exame_item_id
    ON circulacao_diagnostica_itens(pedido_exame_item_id);

-- ---------------------------------------------------------------------------
-- 3. Ledger de eventos (imutável)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS circulacao_diagnostica_eventos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    circulacao_id  INTEGER NOT NULL REFERENCES circulacoes_diagnosticas(id),
    tipo_evento    TEXT    NOT NULL,
    dados_json     TEXT,           -- JSON livre por evento
    criado_em      TEXT    NOT NULL -- ISO 8601 datetime
);

CREATE INDEX IF NOT EXISTS idx_circulacao_diagnostica_eventos_circulacao_id
    ON circulacao_diagnostica_eventos(circulacao_id);
