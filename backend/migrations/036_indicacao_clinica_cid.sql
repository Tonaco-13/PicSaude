-- =============================================================================
-- Ticket 36 — Prescrição com Contexto Clínico (indicacao_clinica + codigo_cid)
-- =============================================================================
--
-- Objetivo: adicionar campos opcionais de contexto clínico à tabela prescricoes.
--
-- Regras:
--   - Ambas as colunas são nullable (sem NOT NULL, sem DEFAULT).
--   - Registros existentes ficam com NULL — sem migração de dados antigos.
--   - A validação semântica do CID é responsabilidade da IA CID, não do banco.
--   - Esta migration é idempotente (se rodar duas vezes, falha silenciosamente
--     no segundo ALTER se a coluna já existir — comportamento normal do SQLite).
--
-- Rollback:
--   SQLite não suporta DROP COLUMN em versões antigas.
--   Para reverter, recriar a tabela sem os campos (não necessário em SQLite >= 3.35).
--
-- Data: 2026-03-24
-- Autor: Ticket 36 / PicSaúde
-- =============================================================================

ALTER TABLE prescricoes ADD COLUMN indicacao_clinica TEXT;
ALTER TABLE prescricoes ADD COLUMN codigo_cid TEXT;
