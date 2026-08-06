# TICKET-GAP-1-UI-LAUDO-CLINICA — UI de emissão de laudo na clínica (fase C) + bloco RBAC

| Campo | Valor |
|---|---|
| **ID** | TICKET-GAP-1-UI-LAUDO-CLINICA |
| **Estado** | 🟢 **DECIDIDO** — martelo Opção A (Fabiano, 2026-08-03) + ownership por CNPJ |
| **Classe** | `core` (RBAC — estender gates) + `module` (UI clínica) |
| **Origem** | Despachos KIMI3-001 §10.C · parecer Fable 5 §3 (apontamento de sequenciamento) |
| **Para** | Arquiteto (spec) → Engenheiro (backend RBAC) → Kimi 3 (UI) → Revisor → Fabiano |
| **Pré-requisito** | Demo de exames (Q2-M) de pé (#131 mergeado). |

---

## §3-bis Decisão do Fabiano (martelo 2026-08-03)

**Opção A ratificada:** estender os 4 gates pra aceitar `dispensador`, com **ownership por CNPJ** (a esteira completa valida que o `dispensador` que chama é o detentor da custódia do pedido/laudo).

**Implicações:**
- Os gates de resultado/laudo passam a aceitar `dispensador` + validam ownership (CNPJ do JWT = custodiante atual).
- `prestador_exame` (`TICKET-CORE-ROLE-PRESTADOR-EXAME`) permanece **agendado** — entra no gatilho de piloto real. Quando entrar, `dispensador` sai desses 4 gates.
- A observação de segurança do Fable 5 (token clínica aceito em dispensador.html) **permanece vigente** até `prestador_exame` entrar — registrada no ticket da role.

---

## §1 Contexto

Na estratégia Q2-M (mínimo viável), o laudo entra **mockado no seed** (`DEMO-LAUDO-0001`, status `liberado`) e a UI de emissão de laudo fica pra **fase seguinte** — este ticket. A clínica hoje mostra "Aguardando laudo" (estático), agora sinalizado como "próxima fase" (PR #132 — KIMI3-004).

**O que falta:** a clínica poder **emitir laudo** pela UI — registrar resultado nos itens, criar laudo, assinar, liberar ao paciente. Os endpoints existem no backend; falta a UI.

## §2 O problema arquitetural (descoberto pelo Fable 5, ratificado)

Verifiquei os gates. A cobertura da role `dispensador` (que a clínica usa, Q1=(a)) no lado do laboratório é **parcial**:

| Ação do laboratório | Gate atual | `dispensador` passa? |
|---|---|---|
| Buscar pedido por protocolo | `pedidos_exame.py:646` | ✅ |
| Coleta | `pedidos_exame.py:815` | ✅ |
| Agendamentos | `agendamentos.py:292,398` | ✅ |
| Circulação diagnóstica | `circulacao_diagnostica.py:556,728` | ✅ |
| **Registrar resultado** | `pedidos_exame.py:979` — só `prescritor`,`admin` | ❌ |
| **Criar laudo** | `laudos.py:320` — só `prescritor`,`admin` | ❌ |
| **Assinar laudo** | `laudos.py:595` — só `prescritor`,`admin` | ❌ |
| **Liberar laudo** | `laudos.py:655` — só `prescritor`,`admin` | ❌ |

**Consequência:** mesmo que o Kimi 3 construa a UI de emissão de laudo, a clínica logada como `dispensador` **toma 403** em todos os endpoints do ciclo do laudo. A UI vai parecer quebrada.

**Com Q2-M nada quebra agora** (laudo mockado no seed, ninguém chama esses endpoints). Mas o Gap 1 **vai bater nesta parede** no primeiro dia.

## §3 Spec de implementação — Opção A (estender gates + ownership por CNPJ)

### 3.1 Backend — 4 gates a estender (Engenheiro)

Adicionar `"dispensador"` aos gates e validar ownership por CNPJ (a esteira completa):

```python
# pedidos_exame.py:979 — registrar resultado
def registrar_resultado_item(
    protocolo, item_id, payload,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    # se role == 'dispensador': validar que o CNPJ do JWT é o custodiante
    # atual do pedido (último registro de pedido_exame_custodia com
    # item_id IS NULL e para=<cnpj>). Padrão: _assert_dispensador_dono_pedido
    # (pedidos_exame.py:594-616). Admin bypassa.
```

Os outros 3 gates seguem o mesmo padrão:
- `laudos.py:320` — `criar_laudo` (mas o laudo é `autor_id = prescritor` — ver §3.2 abaixo).
- `laudos.py:595` — `assinar_laudo`.
- `laudos.py:655` — `liberar_laudo`.

### 3.2 Tensão semântica a resolver (arquiteto — especifiquei antes da implementação)

O `laudos.autor_id` é FK pra `prescritores`. Mas a clínica (que emite o laudo) é `dispensador`, não `prescritor`. **Como fica a autoria do laudo?**

**3 opções (Engenheiro implementa uma; arquiteto ratifica antes):**

- **(i)** O `autor_id` do laudo continua sendo o **prescritor que emitiu o pedido origem** (o laboratório executa o laudo em nome do prescritor solicitante). O `dispensador` aparece no ledger como ator, mas não como autor do laudo.
- **(ii)** `autor_id` fica nullable e o laboratório é registrado só no ledger (`ator_tipo='dispensador'`, `ator_id=<cnpj>`).
- **(iii)** Introduz `autor_tipo` no laudo (prescritor | dispensador) — mais flexível, mais trabalho.

**Recomendação do arquiteto: (i)** — alinha com o desenho MVP (o laudo é técnico, mas a solicitação é do prescritor; o laboratório executa). Minimiza mudança de schema. **Confirmar com o Engenheiro antes de implementar.**

### 3.3 Frontend — UI de laudo na clínica (Kimi 3)

Especificado em §4 (inalterado). Substitui o `TICKET-UI-MOCK-SINALIZADO-CLINICA` quando implementado.

## §4 Spec da UI (Kimi 3 — após decisão do §3)

Independente da decisão de RBAC, a UI é a mesma. Em `clinica.html`, função `renderizarItens`:

1. **Quando item está `coletado`:** substituir o aviso "próxima fase" por um **formulário de resultado** (resultado_resumo, conclusão, valor_referencia) chamando `POST /pedidos-exame/{proto}/itens/{id}/resultado`.
2. **Quando todos os itens têm resultado:** habilitar ação **"Emitir laudo"** que:
   - Cria laudo (`POST /laudos`) vinculado ao pedido.
   - Assina (`POST /laudos/{proto}/assinar`).
   - Libera ao paciente (`POST /laudos/{proto}/liberar`).
3. **Após liberação:** feedback "Laudo liberado ao paciente" + link para visualizar.

Substitui o `TICKET-UI-MOCK-SINALIZADO-CLINICA` (que vira obsoleto quando este ticket implementar).

## §5 Critérios de aceite (parcial — detalhar após decisão RBAC)

1. Clínica logada consegue registrar resultado num item `coletado` (sem 403).
2. Clínica consegue criar/assinar/liberar laudo vinculado ao pedido (sem 403).
3. Após liberação, o laudo aparece na carteira do cidadão (`DEMO-LAUDO-*` em `GET /paciente/laudos`).
4. Aviso "próxima fase" removido (substituído pela UI real).
5. Browser-E2E: clínica coleta → registra resultado → emite laudo → cidadão vê.
6. Sem regressão nos 21+16 testes de autorização (pedidos/laudos).

## §6 Coordenadas

| Artefato | Caminho |
|---|---|
| Parecer Fable 5 (origem do apontamento) | PR #131/#132, §3 |
| Ticket da role agendada | `TICKET-CORE-ROLE-PRESTADOR-EXAME` |
| Mock sinalizado (substituído por este) | `TICKET-UI-MOCK-SINALIZADO-CLINICA` |
| Gates a estender/migrar | `pedidos_exame.py:979` · `laudos.py:320,595,655` |

---

*Ticket aberto pelo arquiteto de backend (GLM-5.2) em 2026-08-03. **Bloqueado pela decisão §3** (Opção A × B) — precisa martelo do Fabiano.*
