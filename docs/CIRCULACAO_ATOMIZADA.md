# PicSaúde — Circulação Atomizada: token e QR por item de prescrição

> **Classificação:** `module` — extensão do núcleo de tokens e circulação
> **Ticket de implementação:** Ticket 44
> **Dependências:**
> - Núcleo de custódia (Fase 1–3) estável
> - `TOKEN_APRESENTACAO_ECOMMERCE.md` — a atomização complementa, não substitui, o modelo de token de prescrição
> - `CIRCULACAO_E_OCORRENCIAS.md` — contexto de circulação digital
> **Pré-requisito soft:** Fase 4 (QR Code + consulta pelo cidadão) — pode ser desenvolvido em paralelo, pois o modelo de token é o mesmo
> **Status:** Proposta arquitetural — pré-implementação

---

## Por que este documento existe

O PicSaúde suporta dispensação parcial e devolução por item. O objeto sanitário
(prescrição) já reconhece granularidade no nível de item. Mas a **unidade de
circulação** — o que o paciente apresenta no balcão — ainda é a prescrição inteira.

Isso cria uma contradição prática:

> O sistema já sabe dispensar item por item. Mas o paciente ainda precisa apresentar
> a prescrição completa para obter qualquer item.

A consequência é uma restrição operacional que não tem fundamento clínico: o
paciente precisa ir à mesma farmácia (ou dar a mesma "chave") para todos os
medicamentos prescritos simultaneamente.

**A circulação atomizada** resolve esse ponto. O ato médico continua uno — um
protocolo, um documento, uma assinatura. O que muda é que cada item recebe sua
própria **unidade de circulação digital**: um token e um QR Code independentes.
O paciente recebe N cartões digitais (um por medicamento) e pode apresentá-los
em N farmácias diferentes, em N momentos diferentes.

Este documento define o conceito, o modelo de dados, os fluxos, as restrições
regulatórias e a relação com o núcleo sanitário existente.

---

## Mapa rápido

| Seção | Conteúdo |
|---|---|
| 1 | Conceito — o que é circulação atomizada |
| 2 | Invariantes — o que não muda |
| 3 | Modo de circulação — flag e semântica |
| 4 | Modelo de dados — delta |
| 5 | Fluxo de emissão atomizada |
| 6 | Fluxo de apresentação por item |
| 7 | Fluxo de dispensação por item |
| 8 | Restrições regulatórias — classes de medicamento |
| 9 | Benefício de privacidade |
| 10 | Impacto no ledger |
| 11 | Impacto na custódia |
| 12 | Impacto no PDF e QR Code |
| 13 | Endpoints novos e alterados |
| 14 | Relação com Token de Apresentação (e-commerce) |
| 15 | Decisões de design documentadas |
| 16 | Fora do escopo deste ticket |
| 17 | Sequência de implementação |

---

## 1. Conceito — o que é circulação atomizada

**Definição:**

> Circulação atomizada é o modo de emissão no qual cada item de uma prescrição
> recebe uma unidade de circulação digital independente (token + QR Code), sem
> que a integridade jurídica da prescrição original seja alterada.

O que permanece **uno**:

- O protocolo da prescrição (UUID imutável)
- O documento canônico e sua assinatura
- A relação entre itens (todos pertencem à mesma prescrição)
- A rastreabilidade clínica completa

O que se **atomiza**:

- O token de apresentação — um por item, não um por prescrição
- O QR Code — um por item (impresso ou digital)
- A cadeia de custódia — registrada no nível do item

**Analogia postal:** a prescrição é o remetente. Os itens são as encomendas.
Hoje todas saem no mesmo pacote. Com circulação atomizada, cada encomenda tem
sua própria etiqueta de rastreamento e pode seguir rotas diferentes.

---

## 2. Invariantes — o que não muda

Estas regras são invioláveis mesmo no modo atomizado.

```
1. A prescrição original nunca é editada após emissão.
   (imutabilidade — CLAUDE.md seção 1)

2. O ledger (prescricao_eventos) nunca recebe UPDATE nem DELETE.
   (ledger imutável — CLAUDE.md seção 2)

3. A soma de quantidade_dispensada por item nunca supera prescricao_itens.quantidade.
   (constraint de quantidade — CLAUDE.md seção 4)

4. Itens com classe de controle especial (A, B, C5) não podem ser atomizados.
   (restrição regulatória — seção 8 deste documento)

5. O protocolo da prescrição mãe é sempre preservado em cada token de item.
   (rastreabilidade clínica obrigatória)

6. A atomização é declarada no momento da emissão e não pode ser alterada.
   (imutabilidade do modo de circulação)
```

---

## 3. Modo de circulação — flag e semântica

Nova coluna na tabela `prescricoes`:

```sql
circulacao_atomizada  BOOLEAN  NOT NULL  DEFAULT FALSE
```

| Valor | Semântica |
|---|---|
| `FALSE` (padrão) | Token único por prescrição — comportamento atual |
| `TRUE` | Um token por item ativo — circulação atomizada |

Regras:

- Definido pelo prescritor no momento da emissão (`POST /prescricoes`)
- Não pode ser alterado após emissão (objeto imutável)
- Automaticamente `FALSE` para prescrições físicas (`circulacao_atomizada` não se aplica)
- Automaticamente `FALSE` se qualquer item for de classe de controle especial
  (o sistema deve rejeitar `circulacao_atomizada: true` nesses casos)

**Valor padrão `FALSE`:** preserva 100% da compatibilidade retroativa. Todas as
prescrições existentes e novos fluxos que não definirem explicitamente o campo
continuam com o comportamento atual.

---

## 4. Modelo de dados — delta

### 4.1 Alteração em `prescricoes`

```sql
ALTER TABLE prescricoes
  ADD COLUMN circulacao_atomizada BOOLEAN NOT NULL DEFAULT FALSE;
```

### 4.2 Alteração em `tokens_apresentacao`

Nova coluna opcional `item_id`:

```sql
ALTER TABLE tokens_apresentacao
  ADD COLUMN item_id INTEGER REFERENCES prescricao_itens(id);
```

Semântica:

| `item_id` | Significado |
|---|---|
| `NULL` | Token cobre a prescrição inteira (modo atual) |
| `X` | Token cobre apenas o item X |

**Constraint de coerência:**

```
SE prescricoes.circulacao_atomizada = TRUE
ENTÃO todos os tokens dessa prescrição devem ter item_id IS NOT NULL

SE prescricoes.circulacao_atomizada = FALSE
ENTÃO todos os tokens dessa prescrição devem ter item_id IS NULL
```

### 4.3 Sem novas tabelas

A circulação atomizada não requer tabelas novas. Reutiliza:

- `tokens_apresentacao` — com `item_id`
- `tokens_apresentacao_usos` — sem alteração
- `prescricao_custodia` — `item_id` já existe e é nullable
- `prescricao_eventos` — novos eventos (seção 10)

---

## 5. Fluxo de emissão atomizada

```
Prescritor
  │
  ├── POST /prescricoes
  │     { ...campos normais..., "circulacao_atomizada": true }
  │
  │   Backend:
  │   1. Valida: nenhum item tem classe de controle especial
  │   2. INSERT prescricoes (circulacao_atomizada = TRUE)
  │   3. INSERT prescricao_itens (N itens)
  │   4. INSERT prescricao_eventos: "prescricao_emitida"
  │   5. Para cada item ativo:
  │       INSERT tokens_apresentacao (item_id = X, token = UUID)
  │       INSERT prescricao_eventos: "token_item_emitido" (item_id = X)
  │
  └── Resposta inclui:
        protocolo
        tokens_por_item: [
          { item_id: 1, medicamento: "Losartana 50mg", token: "AAA-BBB-CCC", qr_url: "..." },
          { item_id: 2, medicamento: "AAS 100mg",      token: "DDD-EEE-FFF", qr_url: "..." },
          { item_id: 3, medicamento: "Metformina 500mg", token: "GGG-HHH-III", qr_url: "..." }
        ]
```

O paciente recebe N tokens independentes. O prescritor digitou os dados do
paciente uma única vez.

---

## 6. Fluxo de apresentação por item

```
Paciente
  │
  ├── Possui token "DDD-EEE-FFF" (AAS 100mg)
  │
  ├── Apresenta na Farmácia B (qualquer — token é aberto)
  │
  └── Farmácia B:
        GET /prescricoes/validacao?token=DDD-EEE-FFF

        Resposta restrita ao item:
        {
          "protocolo": "REC-001-...",   ← rastreabilidade preservada
          "modo": "item",
          "item": {
            "id": 2,
            "medicamento": "AAS 100mg",
            "quantidade": 2,
            "quantidade_dispensada": 0,
            "status": "pendente"
          }
          ← OUTROS ITENS NÃO SÃO EXIBIDOS  ← privacidade do paciente
        }
```

**Princípio de mínima exposição:** a farmácia B vê apenas o medicamento que
está sendo apresentado. Não tem acesso à lista completa de medicamentos do paciente.
Isso é um avanço significativo em relação ao modelo atual (seção 9).

---

## 7. Fluxo de dispensação por item

```
Farmácia B (dispensador)
  │
  ├── Confirma apresentação do token "DDD-EEE-FFF"
  │     POST /prescricoes/{proto}/custodia
  │           { item_id: 2, para: "dispensador" }
  │
  ├── Dispensa:
  │     POST /prescricoes/{proto}/itens/2/dispensar
  │           { quantidade: 2, token: "DDD-EEE-FFF" }
  │
  └── Item 2 → status: "dispensado"
      Prescrição → status: "parcialmente_dispensada" (itens 1 e 3 pendentes)
      Itens 1 e 3 → inalterados, tokens próprios ainda válidos
```

A constraint `Σ dispensado ≤ prescrito` aplica-se da mesma forma. Não há
alteração na lógica de dispensação — apenas a autorização (token) é item-nível.

---

## 8. Restrições regulatórias — classes de medicamento

A legislação brasileira define regimes de controle que impedem ou limitam a
circulação atomizada.

### 8.1 Tabela de restrições

| Classe | Descrição | Circulação atomizada |
|---|---|---|
| Medicamentos comuns | Lista C1, C2 genéricos, MIPs | ✅ Permitida |
| Antimicrobianos | Lista C5 / Portaria 2.814/98 | ⚠️ Exige 2 vias + retenção — aguardar regulação digital |
| Psicotrópicos | Lista B1 (ansiolíticos, hipnóticos) | ❌ Receita de controle especial — documento retido |
| Entorpecentes | Lista A1, A2, A3 | ❌ Receituário especial — 3 vias, retido |
| Retinoides / talidomida | Listas D1, D2 | ❌ Controle especial obrigatório |

### 8.2 Lógica de validação no backend

```python
# No momento do POST /prescricoes com circulacao_atomizada=True:
for item in itens:
    if item.classe_controle in CLASSES_CONTROLE_ESPECIAL:
        raise HTTPException(
            422,
            "Circulação atomizada não permitida para medicamentos de controle especial."
            f" Item: {item.nome} — Classe: {item.classe_controle}"
        )
```

Onde `CLASSES_CONTROLE_ESPECIAL = {"A1", "A2", "A3", "B1", "B2", "C5", "D1", "D2"}`.

### 8.3 Prescrições mistas

Se uma prescrição contém medicamentos comuns e controlados, o prescritor tem duas opções:

1. Emitir **duas prescrições separadas**: uma atomizada (comuns) + uma convencional (controlados)
2. Emitir uma prescrição convencional cobrindo todos

O sistema **não** atomiza seletivamente dentro de uma mesma prescrição.
A razão: a atomização seletiva criaria dois regimes de circulação para o
mesmo documento, o que viola a integridade jurídica da prescrição.

---

## 9. Benefício de privacidade

Este é um efeito arquitetural relevante que merece documentação explícita.

### Modelo atual (token de prescrição inteira)

```
Farmácia A recebe token → vê TODOS os medicamentos do paciente:
  - Losartana 50mg   (hipertensão)
  - Sertralina 50mg  (depressão)
  - Metformina 500mg (diabetes)
  → Farmácia infere perfil clínico completo do paciente
```

### Modelo atomizado (token por item)

```
Farmácia A recebe token do item 1 → vê APENAS:
  - Losartana 50mg
  → Farmácia infere apenas hipertensão

Farmácia B recebe token do item 2 → vê APENAS:
  - Sertralina 50mg
  → Farmácia infere apenas tratamento psiquiátrico

Farmácia C recebe token do item 3 → vê APENAS:
  - Metformina 500mg
  → Farmácia infere apenas diabetes
```

**Nenhuma farmácia vê o quadro clínico completo do paciente.**

Isso é um avanço real em relação ao modelo atual e é consistente com princípios
de privacidade por design (LGPD, art. 46 — medidas técnicas de proteção).

O protocolo da prescrição é preservado em cada token para fins de auditoria pelo
próprio paciente e pelo prescritor — mas não é acessível ao dispensador via token
de item, apenas o item em si.

---

## 10. Impacto no ledger

Novos eventos em `prescricao_eventos`:

| Evento | Quando ocorre |
|---|---|
| `token_item_emitido` | Geração de token para item específico (N eventos, um por item) |
| `circulacao_atomizada_ativada` | Prescrição emitida com modo atomizado (1 evento por prescrição) |

### Estrutura do evento `token_item_emitido`

```json
{
  "evento": "token_item_emitido",
  "prescricao_id": 123,
  "item_id": 2,
  "token_id": 456,
  "medicamento": "AAS 100mg",
  "criado_por": "prescritor"
}
```

O evento `circulacao_atomizada_ativada` é registrado **antes** dos
`token_item_emitido` — ordem garantida pela sequência de INSERT no backend.

---

## 11. Impacto na custódia

O modelo de custódia existente suporta item-level nativamente (`item_id` em
`prescricao_custodia`). A atomização apenas torna esse caminho o **padrão**
para prescrições atomizadas.

Diferença de comportamento:

| Evento | Modo convencional | Modo atomizado |
|---|---|---|
| Transferência inicial | `prescritor → paciente` (prescrição inteira) | `prescritor → paciente` (por item, N registros) |
| Apresentação na farmácia | Um registro de custódia, `item_id = NULL` | Um registro por item apresentado, `item_id = X` |
| Devolução | Por item ou prescrição | Por item (única forma possível) |

**A constraint de transições permitidas não muda.** As transições
`prescritor→paciente`, `paciente→dispensador`, etc. continuam as mesmas —
apenas ganham `item_id` obrigatório no modo atomizado.

---

## 12. Impacto no PDF e QR Code

### 12.1 Opção A — PDF único com N QR Codes (recomendada para MVP)

O prescritor imprime um único documento. Cada item tem seu próprio bloco visual
com QR Code independente:

```
┌─────────────────────────────────────────────────────────┐
│  RECEITA MÉDICA — CIRCULAÇÃO ATOMIZADA                  │
│  Dr. João Silva | CRM-PE 12345 | 2026-03-27             │
│  Paciente: Maria Santos | CPF: XXX.XXX.XXX-XX           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [QR] ITEM 1 — Losartana 50mg 1cp/dia — 60 cps         │
│       Token: AAA-BBB-CCC                                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [QR] ITEM 2 — AAS 100mg 1cp/dia — 30 cps              │
│       Token: DDD-EEE-FFF                                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [QR] ITEM 3 — Metformina 500mg 2cp/dia — 60 cps       │
│       Token: GGG-HHH-III                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

O paciente recorta (literalmente) ou divide digitalmente em N imagens — uma
por item.

### 12.2 Opção B — N PDFs individuais (para fase digital)

Na fase do app do cidadão (Fase 4), cada item gera um "card digital" individual
com seu QR. O PDF consolidado ainda existe como comprovante para o prescritor.

### 12.3 Recomendação para implementação

MVP: Opção A. O PDF é gerado por `domain/pdf_prescricao.py` com layout adaptado
para prescrições atomizadas. A lógica de geração de QR por item está no mesmo
módulo.

---

## 13. Endpoints novos e alterados

### 13.1 Novos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/prescricoes/{proto}/tokens` | Lista tokens emitidos para a prescrição (por item ou por prescrição) |

### 13.2 Alterados

| Método | Rota | O que muda |
|---|---|---|
| `POST` | `/prescricoes` | Aceita campo opcional `circulacao_atomizada: bool`; valida classes controladas; emite tokens por item quando `true` |
| `GET` | `/prescricoes/{proto}/validacao` | Quando `?token=` aponta para item-token, retorna apenas o item correspondente |
| `GET` | `/prescricoes/{proto}/pdf` | Gera layout com N QR Codes quando `circulacao_atomizada = true` |

### 13.3 Não alterados

- `POST /prescricoes/{proto}/itens/{id}/dispensar` — inalterado
- `POST /prescricoes/{proto}/custodia` — inalterado (já suporta `item_id`)
- `POST /prescricoes/fisica` — inalterado (emissão física não usa tokens)

---

## 14. Relação com Token de Apresentação (e-commerce)

O documento `TOKEN_APRESENTACAO_ECOMMERCE.md` define tokens de prescrição
para uso em canais digitais (e-commerce farmacêutico).

A circulação atomizada e o token de e-commerce são **ortogonais** e se compõem:

```
Prescrição atomizada (Ticket 44)
  └─ Item 1 → token AAA-BBB-CCC
       └─ Paciente cria token de e-commerce sobre AAA-BBB-CCC
            └─ E-commerce Farmácia A compra item 1
  └─ Item 2 → token DDD-EEE-FFF
       └─ Paciente apresenta presencialmente na Farmácia B
  └─ Item 3 → token GGG-HHH-III
       └─ Paciente apresenta presencialmente na Farmácia C
```

A granularidade introduzida pela atomização amplia a utilidade do token de
e-commerce: o paciente pode comprar online apenas o medicamento que quer,
sem expor os demais.

**Dependência de implementação:** o token de e-commerce (Fase 4) deve ser
adaptado para aceitar `item_id` no momento em que a atomização estiver ativa.
Isso é uma extensão natural — não uma refatoração.

---

## 15. Decisões de design documentadas

### 15.1 Por que a atomização é por prescrição inteira (flag), não por item selecionado

**Decisão:** O flag `circulacao_atomizada` é da prescrição. Todos os itens são
atomizados ou nenhum é.

**Razão:** Atomização seletiva (alguns itens atomizados, outros não) criaria dois
regimes de circulação convivendo no mesmo documento. Isso complica a validação
("esse token é de prescrição inteira ou de item?"), o PDF (onde estão os QR Codes
e onde não estão?) e a auditoria regulatória. A simplicidade arquitetural justifica
a restrição.

**Consequência aceita:** Prescrições mistas (itens comuns + controlados) exigem
duas prescrições separadas. Isso é uma restrição clínica informada pelo próprio
sistema — não uma limitação técnica.

### 15.2 Por que o token de item ainda carrega o protocolo da prescrição mãe

**Decisão:** Cada `tokens_apresentacao` com `item_id` armazena também a referência
à prescrição mãe (via FK em `prescricao_itens`).

**Razão:** Rastreabilidade. O auditor (ANVISA, CRM, auditoria hospitalar) precisa
poder percorrer de um token de item até a prescrição original, o CRM do prescritor
e o diagnóstico associado. A atomização não pode romper essa cadeia.

### 15.3 Por que a privacidade do paciente é um efeito arquitetural, não uma promessa explícita

**Decisão:** O documento descreve a privacidade como consequência do modelo, não
como garantia contratual.

**Razão:** A garantia completa de privacidade exigiria também criptografia
end-to-end dos dados do token, auditoria de acesso e conformidade formal com
LGPD — que são itens de Fase 5+. O benefício de privacidade descrito aqui
(farmácia vê apenas o item apresentado) é real e imediato, mas incompleto.

### 15.4 Por que `circulacao_atomizada` é booleano e não um enum de modos

**Decisão:** `BOOLEAN`, não `TEXT` com valores como `"por_item"`, `"por_prescricao"`.

**Razão:** No horizonte atual do produto, há apenas dois modos. Introduzir um
enum agora seria over-engineering. Se surgir um terceiro modo (ex: atomização
parcial por grupo terapêutico), o campo pode ser migrado para enum sem quebrar
as queries existentes (FALSE/TRUE mapeiam para 0/1 em SQLite, e 0/1 são valores
válidos de enum).

---

## 16. Fora do escopo deste ticket

```
❌  App do cidadão (cards digitais por item no celular)
         → pertence à Fase 4

❌  Token de e-commerce sobre item atomizado
         → depende de TOKEN_APRESENTACAO_ECOMMERCE.md estar implementado

❌  Separação automática de prescrição mista em duas prescrições
         → decisão clínica do prescritor; não automatizar

❌  Notificações push por item ("seu AAS foi retirado")
         → infraestrutura de notificações não existe

❌  Controle de validade diferenciada por item
         → prescrição tem uma data de validade que vale para todos os itens

❌  Integração com SNGPC (Sistema Nacional de Gerenciamento de Produtos Controlados)
         → requer adapter externo após G4A

❌  Atomização retroativa de prescrições já emitidas
         → viola imutabilidade (CLAUDE.md seção 1)
```

---

## 17. Sequência de implementação

### Fase 1 — Modelo de dados e emissão (back-end)

1. Migração: `ALTER TABLE prescricoes ADD COLUMN circulacao_atomizada`
2. Migração: `ALTER TABLE tokens_apresentacao ADD COLUMN item_id`
3. Constante: `CLASSES_CONTROLE_ESPECIAL` em `domain/medicamento.py` ou `domain/states.py`
4. Atualizar `POST /prescricoes`:
   - Aceitar `circulacao_atomizada`
   - Validar classes controladas
   - Emitir tokens por item quando `true`
   - Registrar eventos `circulacao_atomizada_ativada` e `token_item_emitido`
5. Novo endpoint: `GET /prescricoes/{proto}/tokens`

### Fase 2 — Validação e dispensação

6. Atualizar `GET /prescricoes/{proto}/validacao`:
   - Detectar se token é item-nível
   - Retornar apenas o item quando `item_id IS NOT NULL`
7. Verificar `POST /prescricoes/{proto}/itens/{id}/dispensar`:
   - Confirmar que token (se fornecido) corresponde ao item sendo dispensado

### Fase 3 — PDF e frontend

8. Atualizar `domain/pdf_prescricao.py`:
   - Detectar `circulacao_atomizada`
   - Gerar layout com N blocos de QR Code (um por item)
9. Atualizar `prescritor.html`:
   - Checkbox "Emitir com circulação atomizada" no formulário de receita
   - Exibir aviso para prescrições mistas
10. Testes de integração cobrindo os novos fluxos

### Critério de conclusão

- `POST /prescricoes` com `circulacao_atomizada: true` gera N tokens (um por item)
- `GET /prescricoes/{proto}/validacao?token=<item-token>` retorna apenas o item correspondente
- PDF gerado tem N QR Codes independentes
- Prescrição com item de classe controlada rejeita `circulacao_atomizada: true`
- 100% dos testes existentes continuam passando (compatibilidade retroativa)
