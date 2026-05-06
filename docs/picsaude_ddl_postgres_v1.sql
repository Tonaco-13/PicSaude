-- =============================================================================
-- PicSaúde v1.0 — Modelo Físico PostgreSQL
-- Anexo A do Whitepaper Técnico
-- Derivado dos modelos SQLAlchemy em backend/app/models/
-- =============================================================================
-- Compatível com: PostgreSQL 14+
-- Encoding:       UTF-8
-- Timezone:       UTC (todos os timestamps são TIMESTAMPTZ)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- EXTENSÕES
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "unaccent";   -- normalização de nomes em buscas


-- ---------------------------------------------------------------------------
-- DOMÍNIOS — tipos restritos com validação integrada
-- ---------------------------------------------------------------------------

-- CPF: 11 dígitos, sem máscara
CREATE DOMAIN cpf_t AS VARCHAR(11)
    CHECK (VALUE ~ '^\d{11}$');

-- CNS (Cartão Nacional de Saúde): 15 dígitos
CREATE DOMAIN cns_t AS VARCHAR(15)
    CHECK (VALUE ~ '^\d{15}$');

-- CNPJ: 14 dígitos, sem máscara
CREATE DOMAIN cnpj_t AS VARCHAR(14)
    CHECK (VALUE ~ '^\d{14}$');


-- ---------------------------------------------------------------------------
-- TIPOS ENUMERADOS
-- ---------------------------------------------------------------------------

-- Ciclo de vida da prescrição
CREATE TYPE prescricao_status AS ENUM (
    'pendente',               -- emitida, aguardando transferência
    'transferida_paciente',   -- enviada à custódia do paciente
    'em_custodia',            -- retida em estabelecimento (ex: controlados)
    'parcialmente_dispensada',-- ao menos um item dispensado
    'dispensada',             -- todos os itens dispensados
    'cancelada',              -- cancelada pelo prescritor ou sistema
    'expirada'                -- data_validade ultrapassada
);

-- Modos de assinatura digital — valores reais usados no frontend
CREATE TYPE assinatura_modo_t AS ENUM (
    'icp_brasil_local',   -- certificado A1/A3 local (ICP-Brasil)
    'gov_br_nuvem'        -- assinatura em nuvem via Gov.br
);

-- Origem da emissão: nova receita, correção ou renovação
CREATE TYPE tipo_emissao_t AS ENUM (
    'nova',       -- prescrição original
    'correcao',   -- corrição de prescrição existente (exige origem_prescricao_id)
    'renovacao'   -- renovação periódica (exige origem_prescricao_id)
);

-- Ciclo de vida de cada item individualmente
CREATE TYPE status_item_t AS ENUM (
    'pendente',
    'em_custodia',
    'dispensado',
    'cancelado'
);

-- Quem gerou o evento no ledger
CREATE TYPE ator_tipo_t AS ENUM (
    'prescritor',
    'paciente',
    'dispensador',
    'sistema'
);


-- =============================================================================
-- TABELAS
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. PACIENTES
--    Fonte: backend/app/models/paciente.py
-- ---------------------------------------------------------------------------
CREATE TABLE pacientes (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cpf         cpf_t       NOT NULL,
    nome        TEXT        NOT NULL,
    telefone    VARCHAR(20),
    ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_pacientes_cpf UNIQUE (cpf)
);

CREATE INDEX idx_pacientes_cpf ON pacientes (cpf);

COMMENT ON TABLE  pacientes         IS 'Beneficiários identificados por CPF. Registro criado no primeiro envio de OTP.';
COMMENT ON COLUMN pacientes.cpf     IS 'CPF normalizado: somente dígitos, 11 caracteres. Domínio cpf_t valida o formato.';
COMMENT ON COLUMN pacientes.ativo   IS 'FALSE até o paciente validar o código OTP de cadastro (endpoint /paciente/validar-codigo).';


-- ---------------------------------------------------------------------------
-- 2. PRESCRITORES
--    Fonte: backend/app/models/prescritor.py
-- ---------------------------------------------------------------------------
CREATE TABLE prescritores (
    id                  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cns                 cns_t       NOT NULL,
    nome                TEXT        NOT NULL,
    telefone_vinculado  VARCHAR(20),
    email               VARCHAR(254),
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_prescritores_cns UNIQUE (cns)
);

CREATE INDEX idx_prescritores_cns ON prescritores (cns);

COMMENT ON TABLE  prescritores                   IS 'Profissionais habilitados a emitir prescrições (CBO 2251/2252/2232 — CNES).';
COMMENT ON COLUMN prescritores.cns               IS 'CNS normalizado: 15 dígitos. Identificador principal do prescritor no sistema.';
COMMENT ON COLUMN prescritores.telefone_vinculado IS 'Número de celular para autenticação OTP futura do prescritor.';


-- ---------------------------------------------------------------------------
-- 3. ESTABELECIMENTOS PRÓPRIOS (farmácias dispensadoras)
--    Fonte: backend/app/models/estabelecimento.py
-- ---------------------------------------------------------------------------
CREATE TABLE estabelecimentos_proprios (
    id                  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cnpj                cnpj_t      NOT NULL,
    nome_fantasia       TEXT        NOT NULL,
    razao_social        TEXT,
    telefone_vinculado  VARCHAR(20),
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_estab_cnpj UNIQUE (cnpj)
);

CREATE INDEX idx_estab_cnpj ON estabelecimentos_proprios (cnpj);

COMMENT ON TABLE estabelecimentos_proprios IS 'Farmácias e estabelecimentos de saúde habilitados a dispensar prescrições.';


-- ---------------------------------------------------------------------------
-- 4. PRESCRIÇÕES
--    Fonte: backend/app/models/prescricao.py  +  routers/prescricoes.py
--
--    NOTA DE MIGRAÇÃO:
--    tipo_emissao e origem_prescricao_id existem no router (PrescricaoIn)
--    mas ainda não estão na tabela SQLite nem no modelo ORM.
--    Este DDL os inclui como parte do modelo físico oficial.
-- ---------------------------------------------------------------------------
CREATE TABLE prescricoes (
    id                      BIGINT              GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    protocolo               UUID                NOT NULL DEFAULT gen_random_uuid(),
    prescritor_id           BIGINT              NOT NULL REFERENCES prescritores(id),
    paciente_id             BIGINT              NOT NULL REFERENCES pacientes(id),
    status                  prescricao_status   NOT NULL DEFAULT 'pendente',
    assinatura_modo         assinatura_modo_t,
    tipo_emissao            tipo_emissao_t      NOT NULL DEFAULT 'nova',
    origem_prescricao_id    BIGINT              REFERENCES prescricoes(id),
    data_emissao            TIMESTAMPTZ         NOT NULL DEFAULT now(),
    data_validade           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT now(),

    CONSTRAINT uq_prescricoes_protocolo UNIQUE (protocolo),

    -- Correção e renovação obrigatoriamente referenciam a prescrição de origem
    CONSTRAINT chk_origem_obrigatoria
        CHECK (tipo_emissao = 'nova' OR origem_prescricao_id IS NOT NULL)
);

CREATE INDEX idx_prescricoes_protocolo  ON prescricoes (protocolo);
CREATE INDEX idx_prescricoes_prescritor ON prescricoes (prescritor_id);
CREATE INDEX idx_prescricoes_paciente   ON prescricoes (paciente_id);
CREATE INDEX idx_prescricoes_status     ON prescricoes (status);
CREATE INDEX idx_prescricoes_origem     ON prescricoes (origem_prescricao_id)
    WHERE origem_prescricao_id IS NOT NULL;

COMMENT ON TABLE  prescricoes                       IS 'Prescrições médicas digitais. O protocolo (UUID) é o identificador público (QR Code).';
COMMENT ON COLUMN prescricoes.protocolo             IS 'UUID público impresso no QR Code. Gerado pelo banco, não pela aplicação.';
COMMENT ON COLUMN prescricoes.tipo_emissao          IS 'nova: prescrição original. correcao/renovacao: exigem origem_prescricao_id.';
COMMENT ON COLUMN prescricoes.origem_prescricao_id  IS 'Cadeia de renovações: aponta para a prescrição que originou esta.';
COMMENT ON COLUMN prescricoes.data_validade         IS 'NULL = sem prazo. Medicamentos controlados devem ter prazo legal definido.';


-- ---------------------------------------------------------------------------
-- 5. ITENS DA PRESCRIÇÃO
--    Fonte: backend/app/models/prescricao_item.py
-- ---------------------------------------------------------------------------
CREATE TABLE prescricao_itens (
    id                  BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prescricao_id       BIGINT          NOT NULL REFERENCES prescricoes(id) ON DELETE CASCADE,
    nome_medicamento    TEXT            NOT NULL,
    concentracao        VARCHAR(50),
    quantidade          INTEGER         CHECK (quantidade IS NULL OR quantidade > 0),
    posologia           TEXT,
    status_item         status_item_t   NOT NULL DEFAULT 'pendente',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_itens_prescricao ON prescricao_itens (prescricao_id);
CREATE INDEX idx_itens_status     ON prescricao_itens (status_item);

COMMENT ON TABLE  prescricao_itens              IS 'Medicamentos individuais. Cada item tem seu próprio ciclo de vida e pode ser dispensado separadamente.';
COMMENT ON COLUMN prescricao_itens.quantidade   IS 'Unidades prescritas. Deve ser positivo quando informado.';
COMMENT ON COLUMN prescricao_itens.status_item  IS 'Ciclo individual: pendente → em_custodia → dispensado | cancelado.';


-- ---------------------------------------------------------------------------
-- 6. LEDGER DE EVENTOS (append-only — imutável por design)
--    Fonte: backend/app/models/prescricao_evento.py
--
--    DIFERENÇAS em relação ao modelo atual:
--    - payload_json: TEXT → JSONB  (consulta por conteúdo + índice GIN)
--    - ator_tipo: String → ator_tipo_t  (enum controlado)
--    - Sem updated_at (ledger não deve ser alterado)
--    - RULE de proteção contra UPDATE e DELETE
-- ---------------------------------------------------------------------------
CREATE TABLE prescricao_eventos (
    id              BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prescricao_id   BIGINT          NOT NULL REFERENCES prescricoes(id),
    tipo_evento     TEXT            NOT NULL,
    ator_tipo       ator_tipo_t     NOT NULL,
    ator_id         TEXT,
    payload_json    JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()

    -- Sem updated_at: o ledger não deve ser modificado após inserção
);

CREATE INDEX idx_eventos_prescricao ON prescricao_eventos (prescricao_id);
CREATE INDEX idx_eventos_tipo       ON prescricao_eventos (tipo_evento);
CREATE INDEX idx_eventos_ator       ON prescricao_eventos (ator_tipo, ator_id);
CREATE INDEX idx_eventos_payload    ON prescricao_eventos USING GIN (payload_json);
CREATE INDEX idx_eventos_created_at ON prescricao_eventos (created_at);

COMMENT ON TABLE  prescricao_eventos             IS 'Ledger imutável de todos os eventos do ciclo de vida das prescrições.';
COMMENT ON COLUMN prescricao_eventos.tipo_evento IS 'Vocabulário de eventos: prescricao_emitida, custodia_transferida, item_dispensado, prescricao_cancelada, prescricao_expirada.';
COMMENT ON COLUMN prescricao_eventos.ator_id     IS 'Identificador natural do ator: CNS (prescritor), CPF (paciente), CNPJ (estabelecimento) ou "sistema".';
COMMENT ON COLUMN prescricao_eventos.payload_json IS 'Dados adicionais em JSONB. Ex: {"tipo_emissao":"nova","origem_prescricao_id":null}. Indexado por GIN.';

-- Imutabilidade do ledger: proibir UPDATE e DELETE via RULE
CREATE RULE prescricao_eventos_no_update
    AS ON UPDATE TO prescricao_eventos DO INSTEAD NOTHING;

CREATE RULE prescricao_eventos_no_delete
    AS ON DELETE TO prescricao_eventos DO INSTEAD NOTHING;


-- ---------------------------------------------------------------------------
-- 7. CUSTÓDIA SANITÁRIA
--    Conceito de negócio: quem detém a prescrição a cada momento.
--    Não existe ainda no backend atual — tabela nova para o whitepaper.
-- ---------------------------------------------------------------------------
CREATE TABLE prescricao_custodia (
    id              BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prescricao_id   BIGINT      NOT NULL REFERENCES prescricoes(id),
    detentor_tipo   TEXT        NOT NULL
                    CHECK (detentor_tipo IN ('paciente', 'estabelecimento', 'prescritor')),
    detentor_id     TEXT        NOT NULL,   -- CPF, CNPJ ou CNS (normalizado, só dígitos)
    transferida_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    encerrada_em    TIMESTAMPTZ,            -- NULL = custódia ativa no momento
    motivo          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_custodia_prescricao ON prescricao_custodia (prescricao_id);
CREATE INDEX idx_custodia_detentor   ON prescricao_custodia (detentor_tipo, detentor_id);
-- Índice parcial: localiza rapidamente a custódia ativa de qualquer prescrição
CREATE INDEX idx_custodia_ativa      ON prescricao_custodia (prescricao_id)
    WHERE encerrada_em IS NULL;

COMMENT ON TABLE  prescricao_custodia              IS 'Cadeia de custódia sanitária: rastreia quem detém a prescrição a cada instante.';
COMMENT ON COLUMN prescricao_custodia.detentor_id  IS 'CPF, CNPJ ou CNS normalizado (somente dígitos). Tipo definido por detentor_tipo.';
COMMENT ON COLUMN prescricao_custodia.encerrada_em IS 'NULL indica custódia ativa. Preenchido automaticamente quando há nova transferência.';
COMMENT ON COLUMN prescricao_custodia.motivo       IS 'Ex: "dispensacao_parcial", "rejeicao_farmacia", "devolucao_paciente".';


-- ---------------------------------------------------------------------------
-- 8. DISPENSAÇÕES
--    Conceito de negócio: registro de entrega de cada item ao paciente.
--    Não existe ainda no backend atual — tabela nova para o whitepaper.
-- ---------------------------------------------------------------------------
CREATE TABLE dispensacoes (
    id                      BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prescricao_item_id      BIGINT      NOT NULL REFERENCES prescricao_itens(id),
    estabelecimento_id      BIGINT      NOT NULL REFERENCES estabelecimentos_proprios(id),
    quantidade_dispensada   INTEGER     NOT NULL CHECK (quantidade_dispensada > 0),
    dispensado_por          TEXT,        -- nome/CRF do farmacêutico responsável
    dispensado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    lote                    VARCHAR(50),
    fabricante              TEXT,
    observacao              TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dispensacoes_item          ON dispensacoes (prescricao_item_id);
CREATE INDEX idx_dispensacoes_estab         ON dispensacoes (estabelecimento_id);
CREATE INDEX idx_dispensacoes_dispensado_em ON dispensacoes (dispensado_em);

COMMENT ON TABLE  dispensacoes                       IS 'Registro de dispensação de cada item por estabelecimento habilitado.';
COMMENT ON COLUMN dispensacoes.prescricao_item_id    IS 'Item específico dispensado. Vínculo granular: um item pode ter múltiplas dispensações parciais.';
COMMENT ON COLUMN dispensacoes.quantidade_dispensada IS 'Pode ser menor que prescricao_itens.quantidade (dispensação fracionada).';
COMMENT ON COLUMN dispensacoes.lote                  IS 'Lote do medicamento — rastreabilidade ANVISA/RDC 204/2017.';


-- =============================================================================
-- FUNÇÃO E TRIGGERS — atualização automática de updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_set_updated_at() IS 'Atualiza automaticamente updated_at antes de qualquer UPDATE.';

CREATE TRIGGER trg_pacientes_updated_at
    BEFORE UPDATE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_prescritores_updated_at
    BEFORE UPDATE ON prescritores
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_estab_updated_at
    BEFORE UPDATE ON estabelecimentos_proprios
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_prescricoes_updated_at
    BEFORE UPDATE ON prescricoes
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_itens_updated_at
    BEFORE UPDATE ON prescricao_itens
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- prescricao_eventos não recebe trigger: ledger imutável


-- =============================================================================
-- FIM DO DDL
-- =============================================================================
