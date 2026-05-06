# Arquitetura Dual de Bancos — PicSaúde

> Documento de referência para a camada dual PostgreSQL + SQLite/CNES.
> Gerado no Ticket 8 (Fase 3 — Documentação e Isolamento).

---

## 1. Descrição Geral

O PicSaúde opera com **dois bancos de dados distintos e com responsabilidades separadas**:

| Banco | Tecnologia | Responsabilidade | Acesso |
|---|---|---|---|
| **Aplicação** | PostgreSQL (prod) / SQLite (dev) | Dados transacionais clínicos e operacionais | Leitura e escrita via `get_conn()` |
| **CNES** | SQLite fixo (`data/pix_saude_pe.db`) | Snapshot mensal do DataSUS — referência externa | Somente leitura via `_get_cnes_conn()` |

Essa dualidade é **intencional e documentada**. O CNES é uma base externa fornecida
pelo Ministério da Saúde (DataSUS), atualizada mensalmente, e não pertence ao
domínio transacional da aplicação.

---

## 2. Diagrama de Dependência

```
[FastAPI routers / domain modules]
  │
  ├── get_conn()
  │     └── PostgreSQL (prod): dados transacionais
  │         SQLite (dev): mesmo papel, banco diferente
  │         Tabelas: prescricoes, pacientes, prescritores, prescricao_itens,
  │                  prescricao_eventos, prescricao_custodia, dispensacoes,
  │                  pedidos_exame, laudos, agendamentos, tokens_apresentacao,
  │                  dispensacoes_hospitalares, usuarios, prestadores, api_keys,
  │                  estabelecimentos_proprios, eventos_publicacao, ...
  │
  └── _get_cnes_conn()
        └── SQLite fixo: data/pix_saude_pe.db (snapshot DataSUS)
            Tabelas: profissionais_cnes, relacao_prof_estab, estabelecimentos_cnes
            Acesso: READ-ONLY, nunca modificado pela aplicação
```

---

## 3. Inventário de Tabelas

### 3a. Tabelas transacionais — PostgreSQL / SQLite aplicação (via `get_conn()`)

Tabelas gerenciadas pelo Alembic e `init_tables.py`:

| Tabela | Módulo | Descrição |
|---|---|---|
| `prescricoes` | Prescrição | Prescrições digitais e físicas |
| `prescricao_itens` | Prescrição | Itens individuais de cada prescrição |
| `prescricao_eventos` | Prescrição | Ledger imutável de eventos |
| `prescricao_custodia` | Prescrição | Cadeia de custódia por prescrição/item |
| `prescricao_assinatura` | Prescrição | Metadados de assinatura digital (stub MVP) |
| `pacientes` | Identidade | Dados do paciente (cadastro mínimo) |
| `prescritores` | Identidade | Dados do prescritor (cadastro mínimo) |
| `usuarios` | Auth | Credenciais e papéis |
| `codigos_login` | Auth | Códigos OTP de autenticação |
| `prestadores` | Institucional | Entidades prestadoras (org_id) |
| `unidades` | Institucional | Unidades operacionais dentro do prestador |
| `dispensacoes` | Dispensação | Registros de dispensação ambulatorial |
| `dispensacoes_hospitalares` | Dispensação | Extensão hospitalar (Ticket 27) |
| `tokens_apresentacao` | Tokens | Tokens de acesso emitidos pelo paciente |
| `tokens_apresentacao_usos` | Tokens | Log de uso dos tokens |
| `pedidos_exame` | Exames | Pedidos de exame (cabeçalho) |
| `pedido_exame_itens` | Exames | Itens dos pedidos de exame |
| `pedido_exame_eventos` | Exames | Ledger imutável de eventos de exame |
| `pedido_exame_custodia` | Exames | Cadeia de custódia de exames |
| `laudos` | Laudo | Laudos (cabeçalho) |
| `laudo_itens` | Laudo | Itens dos laudos |
| `laudo_eventos` | Laudo | Ledger imutável de eventos de laudo |
| `laudo_custodia` | Laudo | Cadeia de custódia de laudos |
| `agendamentos` | Agendamento | Agendamentos (Ticket 29) |
| `agendamento_eventos` | Agendamento | Ledger imutável de eventos de agendamento |
| `circulacoes_diagnosticas` | Diagnóstico | Circulação diagnóstica (Ticket 52) |
| `circulacao_diagnostica_itens` | Diagnóstico | Itens da circulação diagnóstica |
| `circulacao_diagnostica_eventos` | Diagnóstico | Ledger imutável de eventos |
| `eventos_publicacao` | G4A | Outbox de eventos externos (G4A) |
| `meta_instalacao` | Ops | Metadados da instalação |
| `solicitacoes_renovacao` | Prescrição | Solicitações de renovação pelo paciente |

### 3b. Tabelas CNES — SQLite fixo (via `_get_cnes_conn()`)

| Tabela | Origem | Acesso | Descrição |
|---|---|---|---|
| `profissionais_cnes` | DataSUS | READ-ONLY | Profissionais de saúde com CNS e CBO |
| `relacao_prof_estab` | DataSUS | READ-ONLY | Vínculos entre profissional e estabelecimento |
| `estabelecimentos_cnes` | DataSUS | READ-ONLY | Estabelecimentos de saúde (CNPJ, municipio, tipo) |

Snapshot de referência: `CNES_SNAPSHOT_REF=cnes_br_2025_12` (`cnes_br_YYYY_MM`).
Atualizado mensalmente. A aplicação **nunca grava** nessas tabelas.

### 3c. Gaps — tabelas com model ORM mas fora do Alembic baseline

| Tabela | Arquivo ORM | Status Alembic | Risco |
|---|---|---|---|
| `api_keys` | `backend/app/models/api_key.py` | **Ausente do baseline** | Criada via `init_tables.py`; não versionada no Alembic |
| `estabelecimentos_proprios` | `backend/app/models/estabelecimento.py` | **Ausente do baseline** | Criada via `init_tables.py`; não versionada no Alembic |

Ação necessária (fora do escopo deste ticket): criar migration Alembic para
formalizar essas tabelas no histórico de schema.

---

## 4. Mapa Completo de Pontos de Acesso CNES

Todos os pontos onde `_get_cnes_conn()` é chamada. Marcados com o comentário
padronizado `# CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md`.

| Arquivo | Função | Tabelas CNES acessadas |
|---|---|---|
| `backend/app/domain/cnes_prescritor.py` | `_verificar_vinculo_prestador()` | `estabelecimentos_cnes` |
| `backend/app/domain/cnes_prescritor.py` | `validar_cns_prescritor()` | `profissionais_cnes`, `relacao_prof_estab` |
| `backend/app/domain/identidade_prescritor.py` | `BancoCnesConselhoProvider.buscar()` | `relacao_prof_estab` |
| `backend/app/domain/identidade_prescritor.py` | `resolver_multiplos_vinculos()` | `profissionais_cnes`, `relacao_prof_estab`, `estabelecimentos_cnes` |
| `backend/app/domain/validacao_documental.py` | `_check_cnes()` | `profissionais_cnes`, `relacao_prof_estab` |
| `backend/app/routers/dispensadores.py` | `busca()` | `estabelecimentos_cnes` |
| `backend/app/routers/prescritores.py` | `busca()` | `profissionais_cnes`, `relacao_prof_estab`, `estabelecimentos_cnes` |
| `backend/app/routers/prescritores.py` | `profissional()` | `profissionais_cnes`, `relacao_prof_estab`, `estabelecimentos_cnes` |

**Total: 8 pontos de acesso CNES, todos via `_get_cnes_conn()`.**

---

## 5. Verificação de Isolamento Técnico

Verificado no Ticket 8:

- [x] Todas as queries CNES usam exclusivamente `_get_cnes_conn()`
- [x] Nenhuma query CNES usa `get_conn()` (PostgreSQL/SQLite app)
- [x] Tabelas transacionais NÃO usam a conexão CNES
- [x] `dispensadores.py` importa `get_conn` mas não o usa — usa apenas `_get_cnes_conn()`
- [x] `prescritores.py` importa `get_conn` mas não o usa nas funções de busca CNES
- [x] `cnes_prescritor.py::validar_cns_prescritor()` usa ambas as conexões corretamente:
  - `conn` (PostgreSQL) → tabela `prestadores`
  - `_get_cnes_conn()` → tabelas CNES

**Nenhuma violação de isolamento encontrada.**

---

## 6. Riscos Documentados

### R1 — Dualidade de fontes de dados
**Descrição:** Dois bancos distintos com tecnologias diferentes (PostgreSQL + SQLite).
**Impacto:** Complexidade operacional; backups, monitoramento e troubleshooting envolvem dois sistemas.
**Salvaguarda atual:** `_get_cnes_conn()` isolado; documentação explícita neste arquivo.

### R2 — Complexidade operacional (2 conexões ativas)
**Descrição:** Em produção, o sistema mantém pool de conexões PostgreSQL + abre/fecha conexões SQLite por request CNES.
**Impacto:** Potencial de connection leak se `_get_cnes_conn()` não fechar corretamente.
**Salvaguarda atual:** Todos os pontos de acesso CNES usam `try/finally: conn.close()`.

### R3 — Risco de uso do banco errado
**Descrição:** Um desenvolvedor pode inadvertidamente usar `get_conn()` para query CNES ou vice-versa.
**Impacto:** Erro de tabela inexistente ou dado incorreto.
**Salvaguarda atual:** Comentário padronizado `# CNES: ...` em todos os 8 pontos de acesso; funções com nomes distintos.

### R4 — Dependência de arquivo físico SQLite
**Descrição:** `_get_cnes_conn()` depende de `data/pix_saude_pe.db` estar presente no filesystem.
**Impacto:** Se o arquivo não existir, `FileNotFoundError` em qualquer endpoint que consulte CNES.
**Salvaguarda atual:** `_get_cnes_conn()` lança `FileNotFoundError` com mensagem clara.

### R5 — Snapshot CNES desatualizado
**Descrição:** O snapshot é mensal. Profissionais recém-cadastrados no DataSUS podem não aparecer.
**Impacto:** Validação CNES retorna `nao_encontrado` para profissional legítimo.
**Salvaguarda atual:** A emissão nunca é bloqueada por resultado CNES (`nivel_validacao_cnes` é informativo).

### R6 — Gaps fora do Alembic (`api_keys`, `estabelecimentos_proprios`)
**Descrição:** Duas tabelas existem como models ORM e são criadas por `init_tables.py`, mas não estão no baseline Alembic.
**Impacto:** Em ambientes que sobem via `alembic upgrade head` sem rodar `init_tables.py`, essas tabelas ficam ausentes.
**Salvaguarda atual:** Nenhuma (risco ativo). Ação pendente: criar migration Alembic.

---

## 7. Plano de Evolução Futura

Este ticket **não define** qual caminho seguir. Os três caminhos possíveis são:

### Caminho A — Migrar CNES para PostgreSQL

Importar as tabelas CNES (`profissionais_cnes`, `relacao_prof_estab`, `estabelecimentos_cnes`)
para o PostgreSQL da aplicação via ETL mensal.

**Prós:**
- Elimina SQLite da infraestrutura de produção
- Permite JOINs entre tabelas CNES e transacionais sem mudança de conexão
- Backup unificado

**Contras:**
- Volume de dados (~milhões de registros no DataSUS nacional)
- Necessidade de pipeline ETL mensal
- Custo de armazenamento em PostgreSQL

**Pré-requisito:** Pipeline de importação mensal + validação de integridade do snapshot.

---

### Caminho B — Externalizar CNES como microserviço

Criar um serviço dedicado (`cnes-service`) que serve os dados CNES via API REST/gRPC.
O PicSaúde passa a consumir esse serviço em vez de acessar SQLite diretamente.

**Prós:**
- Separação de responsabilidades total
- CNES pode ser atualizado independentemente
- Reutilizável por outros sistemas do ecossistema

**Contras:**
- Latência adicional por request (network hop)
- Novo ponto de falha externo
- Overhead operacional de manter outro serviço

**Pré-requisito:** Plataforma de serviços, service discovery, circuit breaker.

---

### Caminho C — Manter SQLite isolado (status quo documentado)

Continuar com a arquitetura atual: SQLite para CNES, PostgreSQL para aplicação.

**Prós:**
- Zero custo de migração
- Arquitetura já validada e funcionando
- Snapshot local elimina dependência de rede para consultas CNES

**Contras:**
- Dualidade técnica permanece
- Risco R1–R4 persistem
- Operação mais complexa (dois bancos para monitorar)

**Adequado para:** MVP e estágios iniciais de produção.

---

## 8. Referências

- `backend/app/domain/cnes_prescritor.py` — definição de `_get_cnes_conn()`
- `backend/app/database.py` — definição de `get_conn()`
- `backend/app/config.py` — `DB_PATH`, `CNES_SNAPSHOT_REF`, `DATABASE_URL`
- `backend/alembic/versions/037d38d98806_baseline_schema_manual.py` — baseline Alembic
- `backend/app/models/api_key.py` — gap: `api_keys`
- `backend/app/models/estabelecimento.py` — gap: `estabelecimentos_proprios`
- `docs/NUCLEO_SANITARIO.md` — contrato arquitetural de objetos sanitários
- `CLAUDE.md` seção 8 — estrutura de arquivos do projeto
