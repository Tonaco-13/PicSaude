# TICKET-70 — IA Farmacêutica: base DEF expandida + UX Inserir/Editar

> Spec consolidada após 3 ciclos de revisão (Engenheiro-Chefe ↔ Z AI).
> Esta é a versão definitiva. Implementação deve seguir esta spec.

---

## 0. Metadados de governança

| Campo | Valor |
|---|---|
| Classe (CLAUDE.md §10) | `module` |
| Revisão exigida | Checklist NUCLEO_SANITARIO + revisão do Engenheiro-Chefe |
| Eventos novos no ledger | `sugestao_ia_gerada`, `sugestao_ia_aceita`, `sugestao_ia_editada`, `sugestao_ia_rejeitada` |
| Tabelas novas | `sugestoes_ia` (transitória, com TTL) |
| Dependências | `instance_id` integrado (Etapa 4 do plano principal — pré-requisito) |
| Sub-tickets | 70A (good-first-issue), 70B (module), 70C (good-first-issue) |
| Vocabulário CLAUDE.md §2 | Atualizar lista de eventos antes do merge |

---

## 1. Motivação

### Regulatória
- **RDC 1.000/2025**: rastreabilidade da prescrição inclui rastrear *como* os dados foram inseridos. A diferença entre dado sugerido pela IA, dado ajustado pelo prescritor, e dado digitado manualmente tem peso em auditoria de erro de medicação.
- **LGPD Art. 6º, III** (minimização): persistência de sugestões com dado sensível (CNS prescritor + CPF paciente + medicamento) deve ser pelo tempo mínimo necessário.

### Operacional
- Base DEF atual tem 42 itens — insuficiente para cobrir prescrição rotineira no SUS. O prescritor sai do fluxo assistido e digita manualmente, perdendo o benefício de validação automática.
- Bulário Anvisa tem ~50k itens registrados. Importar é ganho imediato de cobertura.

### Sanitária
- Cada clique desperdiçado é tempo clínico perdido. Autocompletar bem desenhado reduz fricção; mal desenhado, aumenta. Esta spec opta por *desenho cuidadoso*, não por simplificação genérica.

---

## 2. Escopo

### Dentro
- Importação programática do Bulário Eletrônico da Anvisa para base local DEF
- Validação de schema na importação + health check
- Autocompletar contextual no formulário de prescrição
- Metadado `origem_dados` derivado pelo backend (jamais enviado pelo frontend)
- Eventos imutáveis no ledger registrando interação prescritor ↔ IA
- Microcopy clara em PT-BR para prescritor e farmacêutico

### Fora
- Validação de interações medicamentosas (outro sistema)
- Cálculo de dose por peso/idade (fora de escopo deste ticket)
- Sugestão proativa não solicitada (sistema é reativo ao input do prescritor)
- Histórico personalizado de sugestões por prescritor (privacy-by-design)

---

## 3. Princípios arquiteturais aplicáveis

Esta spec respeita os princípios fundadores do PicSaúde:

1. **Backend é fonte de verdade.** O frontend nunca envia `origem_dados`; o backend deriva por comparação determinística com a sugestão armazenada.
2. **Auditoria é arquitetura.** Cada interação relevante (geração, aceitação, edição, rejeição) gera evento append-only no ledger com `instance_id`, hash, ator e timestamp.
3. **Proteção de dados é estrutural.** TTL curto + criptografia em repouso + degradação graciosa. Default seguro com hard cap arquitetural; operador não pode minar LGPD via configuração.
4. **Default seguro.** Em qualquer ambiguidade ou falha (sugestão expirada, schema inválido, base indisponível), o sistema degrada para o caminho manual sem bloquear o prescritor.

---

## 4. Divisão em sub-tickets

### TICKET-70A — Importação da base DEF
**Classe:** `module` (extensão operacional)
**Elegível como `good-first-issue`:** Sim — não toca contrato público nem ledger.

**Escopo:**
- Script `backend/scripts/import_def_anvisa.py` que consome arquivo de Bulário (CSV/JSON da Anvisa)
- Validação de schema **antes** da importação:
  - Cabeçalhos esperados presentes
  - Número de registros dentro de faixa (30k–80k)
  - Sem colunas vazias em massa (>20% vazio em coluna obrigatória)
  - Sem duplicatas no campo de chave primária (registro Anvisa)
- Importação atômica: se validação falha, dados antigos preservados
- Endpoint `GET /api/ai/def/status` retornando JSON:
  ```json
  {
    "total_registros": 50123,
    "ultima_importacao": "2026-05-04T03:00:00Z",
    "schema_valido": true,
    "fonte": "Bulário Anvisa v2026.04",
    "instance_id": "uuid-da-instancia"
  }
  ```
- Testes unitários cobrindo:
  - Schema válido → importação sucede
  - Schema inválido → importação aborta, dados antigos preservados
  - Duplicata em chave primária → importação aborta
  - Tamanho fora de faixa → importação aborta

**Critérios de aceitação 70A:**
- [ ] Importação de 50k registros do Bulário em ambiente de teste sucede
- [ ] Schema modificado artificialmente (cabeçalho renomeado) → importação aborta com mensagem clara
- [ ] Endpoint `/api/ai/def/status` responde em <100ms
- [ ] Endpoint expõe `instance_id` (rastreabilidade da instância)
- [ ] Testes passam (cobertura >80% no script de importação)

---

### TICKET-70B — UX de autocompletar + contrato API
**Classe:** `module` (toca contrato público de prescrição)
**Elegível como `good-first-issue`:** **Não.** Toca rastreabilidade regulatória e adiciona vocabulário ao ledger. Exige revisão do Engenheiro-Chefe e checklist NUCLEO_SANITARIO.

**Escopo backend:**
- Endpoint `POST /api/ai/sugestoes` — gera sugestão para termo:
  - Input: `{ "termo": "losart", "contexto": { "tipo_receita": "comum_branca" } }`
  - Output: `{ "sugestao_id": "uuid", "expires_at": "...", "candidatos": [...] }`
  - Limite de 10 candidatos por resposta; ordenação por relevância (match exato > prefixo > alias > fuzzy)
  - Se >10 candidatos, retorna campo `total_disponivel` para frontend exibir "continue digitando"
  - Emite evento `sugestao_ia_gerada` no ledger com `instance_id`
- Persistência da sugestão na tabela `sugestoes_ia` (schema na §6)
- Endpoint `POST /prescricoes` aceita campo opcional `sugestao_ia_id` em cada item:
  - Se presente, backend busca sugestão original e compara com dados finais do item
  - Deriva `origem_dados`: `ia_def` (coincide), `ia_def_editado` (difere em ≥1 campo), `manual` (sugestao_ia_id nulo ou expirada)
  - Emite evento correspondente: `sugestao_ia_aceita`, `sugestao_ia_editada` (com diff dos campos), `sugestao_ia_rejeitada`
- **Importante:** se `sugestao_ia_id` é enviado mas a sugestão expirou ou não existe → backend defaulta para `origem_dados=manual` **sem erro**. Degradação graciosa.

**Escopo frontend:**
- Fluxo único, **sem botões "Inserir" / "Editar"**:
  1. Prescritor digita no campo "medicamento" do item
  2. Após **3 caracteres** (sem exceções, sem trigger adaptativo, sem contexto de edição), frontend chama `POST /api/ai/sugestoes`
  3. Dropdown exibe até 10 candidatos com botão "Aceitar" discreto
  4. Se prescritor seleciona um candidato:
     - **Se a tupla `(princípio_ativo, concentração, forma_farmacêutica, via)` retorna N=1 na base DEF**: autofill dos campos secundários (laboratório, registro Anvisa, apresentação comercial)
     - **Se N>1**: dropdown adicional para o prescritor escolher a apresentação; sem autofill automático
     - **Em qualquer caso**: dose e posologia são *hint* (ghost text), nunca autofill — decisão clínica é do prescritor
  5. Frontend armazena `sugestao_ia_id` localmente e envia junto com o item ao salvar a prescrição
  6. Se prescritor digita >3 chars sem aceitar nenhuma sugestão e finaliza → `sugestao_ia_id` é nulo
- Indicador visual sutil quando campo foi preenchido por sugestão (ícone discreto, sem distração)
- Quando prescritor edita campo preenchido por sugestão, indicador muda (ex: ícone de lápis), refletindo `ia_def_editado` que será calculado pelo backend

**Critérios de aceitação 70B (incluindo E2E obrigatório):**
- [ ] **Backend unitário:** `POST /api/ai/sugestoes` retorna ≤10 candidatos com ranking correto
- [ ] **Backend unitário:** sugestão expirada → `origem_dados=manual` sem erro
- [ ] **Backend unitário:** evento `sugestao_ia_editada` carrega diff JSON com campos alterados
- [ ] **Backend unitário:** todo evento novo carrega `instance_id` da instância
- [ ] **Frontend unitário:** trigger dispara em 3 chars, não antes
- [ ] **Frontend unitário:** dose nunca recebe autofill (apenas hint)
- [ ] **Frontend unitário:** autofill só ocorre quando tupla retorna N=1
- [ ] **E2E #1:** prescritor aceita sugestão sem editar → item criado com `origem_dados=ia_def`, evento `sugestao_ia_aceita` no ledger
- [ ] **E2E #2:** prescritor aceita sugestão e edita dose → item criado com `origem_dados=ia_def_editado`, evento `sugestao_ia_editada` com diff `{"dose": {"sugerido": "50mg", "final": "25mg"}}`
- [ ] **E2E #3:** prescritor digita tudo manualmente, ignorando sugestões → item criado com `origem_dados=manual`, evento `sugestao_ia_rejeitada` (se houve sugestão gerada e ignorada) ou nenhum evento de sugestão (se nunca disparou)
- [ ] **E2E #4:** sugestão expirou entre geração e submissão → item criado com `origem_dados=manual`, sem erro 422
- [ ] **E2E #5:** importar base, fazer 100 sugestões, verificar P95 < 200ms para `POST /api/ai/sugestoes`

---

### TICKET-70C — Exibição de `origem_dados`
**Classe:** `module` (extensão de UI)
**Elegível como `good-first-issue`:** Sim — frontend puro, sem alteração de contrato público.

**Escopo:**
- Frontend de prescrição: ícone + tooltip ao lado de cada item, refletindo `origem_dados`:
  - `ia_def` → 🤖 "Sugestão automática"
  - `ia_def_editado` → ✏️ "Sugestão ajustada pelo prescritor"
  - `manual` → ✍️ "Digitado manualmente"
- PDF da prescrição: rodapé do item com texto sanitário (sem jargão dev):
  - `ia_def` → "Dados preenchidos automaticamente pelo sistema"
  - `ia_def_editado` → "Dados ajustados pelo prescritor"
  - `manual` → "Dados informados manualmente"
- Relatórios analíticos (dashboard do prescritor): contadores agregados (ex: "73% das prescrições neste mês usaram sugestão IA").

**Critérios de aceitação 70C:**
- [ ] Frontend exibe ícone correto para cada estado de `origem_dados`
- [ ] PDF gerado contém texto sanitário no rodapé do item
- [ ] Auditor regulatório (não-dev) entende o significado sem consultar documentação técnica
- [ ] Relatório agregado existe e responde em <500ms

---

## 5. Vocabulário de eventos no ledger

Adicionar a `prescricao_eventos` (CLAUDE.md §2 — atualizar a tabela de vocabulário antes do merge):

| Evento | Quando ocorre | Payload mínimo |
|---|---|---|
| `sugestao_ia_gerada` | Backend gerou sugestão para termo | `{ termo, sugestao_id, total_candidatos, instance_id }` |
| `sugestao_ia_aceita` | Item criado com `origem_dados=ia_def` | `{ sugestao_id, item_id, instance_id }` |
| `sugestao_ia_editada` | Item criado com `origem_dados=ia_def_editado` | `{ sugestao_id, item_id, diff: { campo: { sugerido, final } }, instance_id }` |
| `sugestao_ia_rejeitada` | Sugestão foi gerada mas prescritor digitou tudo manualmente | `{ sugestao_id, motivo: "ignorada" \| "expirada", instance_id }` |

Todos os eventos são append-only. **Nunca** `UPDATE` ou `DELETE`. Todos carregam `instance_id` desde o primeiro commit (não retrofit).

---

## 6. Schema da tabela `sugestoes_ia`

Tabela transitória para permitir que o backend compare dados finais com sugestão original. Não é log nem auditoria — auditoria está no ledger. Esta tabela apenas viabiliza a derivação de `origem_dados`.

```sql
CREATE TABLE sugestoes_ia (
    id              UUID         PRIMARY KEY,
    prescritor_cns  TEXT         NOT NULL,
    paciente_cpf    TEXT         NULL,         -- NULL para prescrição sem paciente vinculado ainda
    termo_busca     TEXT         NOT NULL,
    payload         JSONB        NOT NULL,     -- conteúdo da sugestão (criptografado em repouso na fase de produção)
    instance_id     UUID         NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP    NOT NULL
);

CREATE INDEX idx_sugestoes_ia_expires ON sugestoes_ia(expires_at);
CREATE INDEX idx_sugestoes_ia_prescritor ON sugestoes_ia(prescritor_cns);
```

### TTL configurável com hard cap

- Variável de ambiente `SUGESTION_TTL_HOURS`
- **Default: 1 hora** (cobre fluxo normal de prescrição em consulta)
- **Hard cap no código: 6 horas.** Valor configurado >6h → backend recusa boot com erro de configuração.
- Justificativa: pesquisa científica não acessa sugestões transitórias (acessa eventos do ledger, que são permanentes). Não há caso de uso legítimo para retenção >6h.
- Job de expurgo automático (cron horário): `DELETE FROM sugestoes_ia WHERE expires_at < NOW()`
- Endpoint `GET /admin/config/ttl` expõe valor configurado, para auditoria

### Criptografia em repouso

- Fase MVP (demo): plain text, com nota explícita em `DATA-PROTECTION.md` que produção exigirá criptografia
- Fase produção: AES-256-GCM no campo `payload`, alinhado com cofre PFX existente (mesmo padrão de chave)

---

## 7. Contrato de API

### `POST /api/ai/sugestoes`

**Request:**
```json
{
  "termo": "losart",
  "contexto": {
    "tipo_receita": "comum_branca",
    "paciente_cpf": "12345678909"
  }
}
```

**Response 200:**
```json
{
  "sugestao_id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-05-05T15:30:00Z",
  "total_candidatos": 47,
  "candidatos": [
    {
      "principio_ativo": "Losartana Potássica",
      "concentracao": "50mg",
      "forma_farmacutica": "comprimido revestido",
      "via": "oral",
      "registro_anvisa": "1.0123.0456.001-2",
      "laboratorio": "EMS",
      "apresentacao_comercial": "30 comprimidos",
      "match_score": 0.95,
      "match_tipo": "prefixo"
    }
  ]
}
```

### `POST /prescricoes` (extensão)

Cada item agora aceita `sugestao_ia_id` opcional:
```json
{
  "itens": [
    {
      "medicamento": "Losartana Potássica 50mg comprimido revestido",
      "dose": "50mg",
      "posologia": "1 cp 1x ao dia",
      "quantidade": 30,
      "sugestao_ia_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

Backend deriva `origem_dados` e salva no item. **Frontend nunca envia `origem_dados`.**

### `GET /api/ai/def/status`

Health check da base DEF (definido em 70A).

### `GET /admin/config/ttl`

Auditoria do TTL configurado:
```json
{
  "sugestion_ttl_hours": 1,
  "default": 1,
  "hard_cap": 6,
  "instance_id": "..."
}
```

---

## 8. Microcopy

### Frontend (interface do prescritor)

| Estado | Ícone | Tooltip |
|---|---|---|
| `ia_def` | 🤖 | "Sugestão automática" |
| `ia_def_editado` | ✏️ | "Sugestão ajustada pelo prescritor" |
| `manual` | ✍️ | "Digitado manualmente" |

> Se a UI do PicSaúde não usar emoji, substituir por ícones SVG equivalentes. Mantém-se o significado.

### PDF da prescrição (auditoria sanitária)

Rodapé de cada item, em PT-BR sanitário:

| `origem_dados` | Texto no PDF |
|---|---|
| `ia_def` | "Dados preenchidos automaticamente pelo sistema, com base no registro Anvisa" |
| `ia_def_editado` | "Dados ajustados pelo prescritor após sugestão automática" |
| `manual` | "Dados informados manualmente pelo prescritor" |

### Erros do backend (frontend exibe)

| Cenário | Mensagem ao prescritor |
|---|---|
| Base DEF indisponível | "Sistema de sugestões temporariamente indisponível. Você pode digitar normalmente." |
| Sugestão expirou | (silencioso — backend defaulta para `manual`) |
| Termo retorna 0 candidatos | "Nenhuma sugestão encontrada. Você pode digitar manualmente." |

---

## 9. Checklist NUCLEO_SANITARIO

Conforme `docs/NUCLEO_SANITARIO.md`. Esta spec adiciona vocabulário ao ledger — exige checklist completo antes do merge.

- [ ] **Imutabilidade:** `sugestoes_ia` recebe INSERT e DELETE (expurgo). Eventos no ledger são append-only.
- [ ] **Identidade:** sugestões têm UUID próprio (`sugestao_id`). Eventos referenciam por ID.
- [ ] **Custódia:** N/A — sugestões não são objeto sanitário (não têm cadeia de custódia). São artefato técnico transitório.
- [ ] **Estados:** N/A — sugestões não têm máquina de estados. Existem ou não existem (TTL).
- [ ] **Ledger:** 4 eventos novos catalogados (§5). `instance_id` em todos.
- [ ] **Documento canônico:** `origem_dados` integra-se ao documento canônico da prescrição (cada item passa a carregar este campo). Hash do documento muda — atualizar testes do `domain/documento_canonico.py`.
- [ ] **Assinatura:** N/A — sugestões não são assinadas. Item assinado é o item *final* da prescrição, com `origem_dados` já derivado.
- [ ] **Escopo institucional (§6b):** sugestões herdam contexto via prescrição final; `sugestoes_ia` não recebe `org_id` direto (rollout incremental). Documentar exceção.
- [ ] **Classificação (§10):** `module`. Não toca core, mas adiciona vocabulário ao ledger — revisão central obrigatória.

---

## 10. Sequência de implementação e relação com o plano principal

70A é uma das `good-first-issue` da Etapa 9 do plano principal. Implementar 70A antes das Etapas 4–6 é **adiantamento justificável apenas se** Fabiano aprovar explicitamente. Em qualquer caso:

1. 70A **não pode** criar helper `instance_id` paralelo — usa TODO explícito se o endpoint precisar do campo
2. 70A **não pode** tocar `documento_canonico.py` — bump de versão é escopo exclusivo de 70B
3. 70B só inicia após Etapa 4 (instance_id canônico) + 70A mergeado
4. 70C só inicia após 70B mergeado

Etapas bloqueadoras do deploy público (B1, seletor de papéis) têm prioridade sobre 70A.

Cada sub-ticket gera PR independente, com revisão própria. PR de 70B exige aprovação do Engenheiro-Chefe (mudança em contrato público).

---

## 11. Riscos e mitigações

| Risco | Severidade | Mitigação |
|---|---|---|
| Schema do Bulário Anvisa muda silenciosamente | Alta | Validação de schema na importação + health check (70A) |
| Estudante perde tempo descobrindo onde baixar e como o Bulário está formatado | Média | **Pré-Etapa 9:** Engenheiro-Chefe ou Fabiano baixa Bulário manualmente, anota formato atual nos cabeçalhos da issue 70A (ex: *"Bulário em 2026-05 tem colunas: X, Y, Z. Script deve aceitar este formato."*). Elimina primeira barreira do estudante. |
| Performance degrada com 50k registros | Média | Critério P95 <200ms + índice em memória |
| Frontend ignora `sugestao_ia_id` (regressão) | Alta | E2E #1, #2, #3 obrigatórios em CI |
| Operador configura TTL muito longo | Média | Hard cap 6h no código, recusa boot acima disso |
| Sugestão vaza dado sensível em log | Alta | Logs do `POST /api/ai/sugestoes` redatam `paciente_cpf` e `payload` |
| Auditor não entende `origem_dados` | Baixa | Microcopy sanitária no PDF (§8) |

---

## 12. Pós-implementação (opcional, fora deste ticket)

Itens identificados na revisão mas explicitamente fora de escopo:

- Indicador agregado por prescritor: "73% de uso de sugestão IA neste mês"
- Alerta quando prescritor edita >50% das sugestões (sinal de que base DEF está desatualizada)
- Exportação anonimizada de eventos `sugestao_ia_*` para análise epidemiológica de erros de medicação (sob aprovação CEP/CONEP)

Estes itens viram tickets futuros se valor regulatório/operacional justificar.

---

## 13. Histórico de revisão

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 1.0 | 2026-05-05 | Z AI | Proposta inicial |
| 1.1 | 2026-05-05 | Z AI | Revisão com 8 pontos (críticos + altos + médios) |
| 1.2 | 2026-05-05 | Engenheiro-Chefe | Revisão da revisão: 4 omissões adicionadas (ledger, classe, instance_id, LGPD), 2 discordâncias parciais (autofill, trigger) |
| 1.3 | 2026-05-05 | Z AI | Contrarresvisão: aceitação dos 4 omissões, refinamento do autofill (match único), manutenção do trigger 3 chars |
| 1.4 | 2026-05-05 | Engenheiro-Chefe | Versão consolidada definitiva. Convergência atingida em 3 ciclos. |
| 1.5 | 2026-05-05 | Engenheiro-Chefe + Z AI | §10 reescrita: faseamento explícito + relação com plano principal + bloqueadores. §11 adiciona risco "estudante perde tempo descobrindo formato Bulário" com mitigação pré-Etapa 9. |

---

*"O SUS é o maior sistema universal de saúde do mundo. Merece software à altura."*
