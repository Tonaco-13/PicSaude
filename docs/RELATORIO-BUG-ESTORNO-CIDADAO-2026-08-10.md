# Relatório de Teste de UI — Bug do Estorno que Não Chega ao Cidadão

> **Data:** 10/08/2026
> **Ambiente:** picsaude.com.br (demo_mode)
> **Testador:** ZCode (agente de UI, modo black-box)
> **Bug relatado por:** Fabiano Tonaco Borges
> **Severidade:** Alta — quebra o fluxo de extorno e bloqueia a devolução ao prescritor

---

## 1. Resumo executivo

Reproduzi e **confirmei** o bug relatado: ao estornar uma dispensação, o estorno **não chega ao
cidadão**. As prescrições estornadas voltam exclusivamente para a fila do dispensador, e o cidadão
perde toda visibilidade/custódia delas — impossibilitando a etapa seguinte (devolução ao prescritor,
que só o cidadão pode iniciar).

O bug tem **causa raiz identificada no código**: o handler de estorno, por uma decisão de design
("estorno como objeto derivado"), deliberadamente **não muta** o `status_item` nem o
`status_prescricao`, e reabre a custódia **no nome do dispensador** (não do paciente).

---

## 2. Cenário executado

| Etapa | Ação | Resultado |
|---|---|---|
| T0 | Abrir vitrine picsaude.com.br | ✅ Portal com 4 perfis |
| T1 | Prescritor emite **P1** (Dipirona 500mg, 20 comp) | ✅ Protocolo `82cdbb62-5634-4ea6-ba2e-5b150621a35d` |
| T2 | Prescritor emite **P2** (Amoxicilina 500mg, 21 cáps) | ✅ Protocolo `478609db-5953-4a54-8a17-eccc5b69daad` |
| T3 | Cidadão transfere custódia das 2 à Farmácia Demo Central | ✅ Ambas saem da carteira ativa |
| T4 | Dispensador dispensa as 2 (lotes DIP2026A / AMX2026B) | ✅ "Dispensação registrada. Saldo restante: 0." |
| T5 | Dispensador estorna as 2 (`desistencia_paciente`) | ⚠️ Estorno registrado, **mas não chega ao cidadão** |
| T6 | Cidadão verifica carteira | ❌ **"Nenhuma prescrição sob sua custódia no momento."** |
| T7 | Cidadão tenta devolver ao prescritor | ❌ **BLOQUEADO** — não há prescrição na carteira |

---

## 3. O bug — evidência definitiva

### 3.1 Resposta da API ao estornar (`POST /dispensacoes/7/estornar`)

```json
{
  "estorno_id": 3,
  "protocolo": "f732f1e6-7c34-43b1-9a3a-42b31b6e9ce0",
  "origem_dispensacao_id": 7,
  "item_id": 8,
  "quantidade_estornada": 21,
  "motivo": "desistencia_paciente",
  "saldo_restante": 21,
  "status_item": "dispensado",          ← NÃO mudou (deveria: devolvido_paciente)
  "status_prescricao": "dispensada",     ← NÃO mudou
  "custodia_reaberta": true              ← mas custódia foi reaberta
}
```

### 3.2 Carteira do cidadão após estorno (`GET /paciente/prescricoes`)

```json
{
  "posse": [],           ← VAZIA — cidadão não tem nada
  "historico": [
    {
      "protocolo": "478609db-...",
      "status": "dispensada",           ← continua dispensada
      "itens": [{ "status_item": "dispensado" }]   ← continua dispensado
    },
    ...
  ]
}
```

### 3.3 UI do cidadão após estorno

> **"Nenhuma prescrição sob sua custódia no momento."**

![Carteira do cidadão vazia após estorno](../gui-test-screenshots/t6_cidadao_pos_estorno.png)

### 3.4 UI do dispensador após estorno — onde os itens foram parar

Os itens estornados voltaram para a **fila do dispensador** (saldo reposto), não para o cidadão:

![Fila do dispensador com itens estornados](../gui-test-screenshots/t5c_dispensador_pos_estorno.png)

> Amoxicilina `478609db`: saldo **21/21** ← voltou à fila do dispensador
> Dipirona `82cdbb62`: saldo **20/20** ← voltou à fila do dispensador

---

## 4. Causa raiz (análise de código)

O bug **não é acidental** — é uma consequência direta de uma decisão de design documentada como
"estorno como objeto sanitário derivado" (TICKET-ESTORNO-OBJETO-DERIVADO).

### 4.1 O handler de estorno (`backend/app/routers/dispensacoes.py:488-657`)

O handler faz três coisas e **deliberadamente não faz** a quarta:

| Faz | Linha | Efeito |
|---|---|---|
| INSERT em `estornos` | 562-573 | Cria objeto derivado imutável |
| Emite `estorno_registrado` no ledger | 577-594 | Auditoria |
| `transferir_posse(...)` para o **dispensador** | 635-641 | Reabre custódia na farmácia |

| **NÃO faz** | Efeito esperado |
|---|---|
| `UPDATE prescricao_itens SET status_item='devolvido_paciente'` | Item permanece `dispensado` |
| `transferir_posse(...)` para o **paciente** | Custódia vai ao dispensador, não ao cidadão |
| `_recalcular_status_prescricao(...)` | Prescrição permanece `dispensada` |

### 4.2 Evidência da intenção no código

- `dispensacoes.py:475-480` (comentário): *"O estorno NÃO muta a dispensação nem o item: cria um
  objeto derivado imutável..."*
- `dispensacoes.py:501` (docstring): *"O item NÃO é mutado (a reversão vive no objeto-estorno)."*
- `states.py:157-162`: *"a transição dispensado → estornado… permanece como scaffolding dormente."*

### 4.3 O saldo é "virtual"

O saldo reposto (`saldo_restante: 21`) é computado **on-the-fly** em queries de leitura
(`Σ dispensado − Σ estornado`), não é um estado persistido. Por isso o dispensador vê saldo 21/21
na fila — mas o item subjacente nunca deixou de ser `dispensado`.

---

## 5. Impacto no fluxo regulatório

O fluxo completo que **deveria** funcionar (CLAUDE.md §3, §5a):

```
Prescritor → Cidadão → Dispensador → [estorno] → Cidadão → Prescritor
                                              ↑           ↑
                                         QUEBRADO    BLOQUEADO
```

- **Estorno → Cidadão:** QUEBRADO. O item vai ao dispensador, não ao cidadão.
- **Cidadão → Prescritor:** BLOQUEADO. O cidadão não vê a prescrição (carteira vazia), então não
  pode clicar em "Identifiquei um erro (Devolver ao Médico)".

O cidadão fica **sem qualquer via** de devolver a prescrição ao prescritor após um estorno — a
 única via regulatória documentada (§3: `paciente → prescritor`) é inalcançável.

---

## 6. Observação sobre o ambiente de automação (IAB)

Durante o teste, observei que o `prompt()` nativo do JavaScript (usado pelo handler
`estornarDispensacao` em `dispensador.html:1496` para pedir o motivo do estorno) **não é
interceptável** pelo In-App Browser via `getJsDialog()`. O `prompt()` bloqueia a execução do
`click()` por 32s (timeout) e o dialog nunca é capturado.

Para completar o teste do estorno, usei a API REST diretamente (`POST /dispensacoes/{id}/estornar`),
o que é legítimo pois reproduz exatamente o que o frontend envia. O bug confirmado é independente
desta limitação de automação — ele está no backend.

> **Nota:** vale investigar se o "caiu" relatado pelo Fabiano está relacionado a este `prompt()` —
> se o IAB ou o navegador do usuário não lida bem com `prompt()`, o handler pode falhar
> silenciosamente, deixando o usuário sem saber se o estorno foi ou não registrado.

---

## 7. Recomendação de correção

Para que o extorno cumpra o fluxo regulatório (`estorno → cidadão → prescritor`), o handler
`dispensacoes.py:488-657` deve, após criar o objeto-estorno:

1. **Mutar o status do item** para `devolvido_paciente` (estado que permite nova tentativa OU volta
   ao médico, conforme §5a):
   ```sql
   UPDATE prescricao_itens SET status_item = 'devolvido_paciente' WHERE id = :item_id
   ```
2. **Reabrir a custódia no nome do paciente**, não do dispensador (`dispensacoes.py:637`):
   ```python
   transferir_posse(..., para_tipo="paciente", para_id=cpf_paciente, ...)
   ```
3. **Recalcular o status da prescrição** via `_recalcular_status_prescricao(...)` para que ela
   regredir de `dispensada` para `transferida_paciente` (ou estado derivado do item).

> ⚠️ Esta correção é **classe `core`** (CLAUDE.md §10): altera máquina de estados e cadeia de
> custódia. Exige revisão central obrigatória e migração/teste nos dois dialetos.

---

## 8. Evidências (screenshots)

Todas em `gui-test-screenshots/`:

| Arquivo | Descrição |
|---|---|
| `t0_vitrine.png` | Portal de acesso (vitrine) |
| `t1e_presc1_form_completo.png` | Prescrição 1 preenchida (Dipirona) |
| `t1f_presc1_depois_emitir.png` | Tela de sucesso P1 — protocolo 82cdbb62 |
| `t2b_presc2_depois_emitir.png` | Tela de sucesso P2 — protocolo 478609db |
| `t3a_cidadao_antes_transferir.png` | Carteira do cidadão com 2 receitas ativas |
| `t4b_dispensador_dipirona_dispensada.png` | Dipirona dispensada (saldo 0) |
| `t4c_dispensador_amox_dispensada.png` | Amoxicilina dispensada (saldo 0) |
| `t5c_dispensador_pos_estorno.png` | **Fila do dispensador com itens estornados de volta** |
| `t6_cidadao_pos_estorno.png` | **Carteira do cidadão VAZIA após estorno** |

---

## 9. Conclusão

O bug está **confirmado, reproduzido e tem causa raiz identificada**. O estorno foi projetado como
objeto derivado que não muta o item — uma decisão legítima para o registro contábil, mas que deixa
uma lacuna no fluxo de custódia: sem mutar o `status_item` para `devolvido_paciente` e sem reabrir
a custódia no nome do paciente, o cidadão perde a prescrição de vista e fica sem via de devolução
ao prescritor.

A correção exige tocar a máquina de estados e a cadeia de custódia (classe `core`), e deve ser
submetida a revisão central obrigatória.
