# TICKET-SMOKES-WAIT-PRIMITIVE — Trocar `networkidle` por espera explícita, PAREADO com fortalecer as asserções tautológicas

| Campo | Valor |
|---|---|
| **Classe** | `ops` / test-infra (não toca produto, não toca núcleo) |
| **Para** | Engenheiro (Claude/Code) → Conselheiro (parecer leve) → martelo Fabiano |
| **Origem** | AÇÃO 4 do despacho do Conselheiro, 2026-07-25, ao fechar o TICKET-GATE-SMOKES-NETWORKIDLE (PR #127) |
| **Pré-requisito** | PR #127 na `main` (`1fb175d`) — a causa raiz do gate vermelho já está corrigida |
| **Urgência** | **Baixa.** Entra na fila. O gate está verde e é portão outra vez; isto é dívida de qualidade, não incêndio |
| **Ponto de partida** | Branch `wip/smokes-wait-primitive` (commit `23c03d0`) — o commit descartado do #127, preservado no remoto |

---

## §1 Contexto (não reabrir)

O gate `smokes` ficou vermelho na `main` de 23/07 a 25/07. A investigação do
TICKET-GATE-SMOKES-NETWORKIDLE achou a causa raiz — **deadlock de pipe** no
`conftest.py`, que congelava o servidor da fixture no meio da sessão — e o PR #127
a corrigiu. Os timeouts de `networkidle` eram **sintoma**: o `goto` não completava
porque o servidor estava morto, não porque a rede não silenciava.

O #127 subiu com **um commit só**, o da causa raiz. O commit que trocava a
primitiva de espera foi **descartado por decisão do Conselheiro** — PR mínimo,
superfície de revisão proporcional ao risco. Este ticket é a versão completa e
honesta daquele descarte.

### Por que ainda vale fazer

Duas dívidas independentes, que só valem a pena se resolvidas **juntas**:

**(1) `networkidle` é a primitiva errada.** Ela só resolve após 500 ms sem
tráfego de rede — uma condição sobre o **ambiente**, não sobre o produto. Com o
deadlock corrigido ela para de derrubar o gate, mas continua sendo uma espera cujo
fim depende de o runner ficar quieto. Medido no laptop: `domcontentloaded` chega em
0,03–0,12 s contra ~0,6 s do `networkidle`, com **zero** requisição pendurada.

**(2) Duas asserções são tautológicas.** Em `test_smokes.py`, hoje na `main`:

```python
# linhas ~98-99 — test_cada_card_entra_no_modulo
expect(page.locator("body")).not_to_be_empty(timeout=_TIMEOUT_MS)

# linha ~542 — test_tela_sem_erro_de_console
expect(page.locator("body")).not_to_be_empty(timeout=_TIMEOUT_MS)
```

Um `<body>` com erro de JS e nada renderizado **também é "não vazio"**. Quem
sustentava esses dois testes era o `networkidle` do `goto` — e ele auditava a
**rede**, não a tela.

### A regra que amarra os dois

> **A troca de primitiva vem COM dente, não tirando dente.**

Trocar `networkidle` por `domcontentloaded` **sem** fortalecer as asserções
converteria fragilidade em tautologia: `domcontentloaded` + `body` não-vazio passa
em qualquer HTML, até quebrado. Seria o anti-padrão do AC9 — asserção que passa
trivialmente não testa nada. É exatamente por isso que este ticket **pareia** as
duas mudanças: uma sem a outra é regressão disfarçada de limpeza.

---

## §2 Invariantes (não-negociáveis)

- **Não toca produto.** Nenhum `.html` de feature é alterado. Só `tests/browser/`
- **Não toca núcleo.** Nem ledger, nem estados, nem custódia, nem RBAC
- **Nenhuma asserção enfraquece.** Toda troca de espera entrega poder de detecção
  igual ou maior. Este é o critério de aceite central
- **Vermelho antes de verde:** a prova de que a asserção nova tem dente é o teste
  de mutação do §5 — guarda que não falha quando deveria é decoração

---

## §3 Escopo

### 3.1 `backend/tests/browser/test_smokes.py` — 14 `goto`

Trocar `wait_until="networkidle"` por `wait_until="domcontentloaded"` **mais**
espera explícita pelo elemento que o teste de fato precisa.

A maioria dos 14 já tem a espera explícita logo abaixo (`expect(#fila-lista)`,
`expect(#atestado-conselho)`, `expect(#lista-atestados)`…) — nesses, só a primitiva
muda. Os dois problemáticos são os do §1(2).

### 3.2 `test_coer2_e2e.py` (4) e `test_coer2_fix.py` (1) — 5 `goto`

Mesma migração. Passam hoje, mas carregam a mesma primitiva frágil. **Atenção:**
são fluxos E2E que dependem de dados carregados; a espera explícita tem de ser o
efeito real (lista populada, card presente), nunca só o container visível.

### 3.3 Fortalecer as duas tautológicas — **obrigatório, pareado**

Trocar `body not_to_be_empty` por asserção de conteúdo real por tela. Duas
abordagens possíveis; o engenheiro escolhe e justifica no PR:

**(A) Marca de montagem por tela** — o que o commit descartado fazia. Cada tela
declara o seletor que prova que montou:

| Tela | Marca | Observação |
|---|---|---|
| `index.html` | `a.card` | a grade de cards do portal |
| `prescritor.html` | `#tela-acesso` | sem auto-login |
| `dispensador.html` | `#tela-dashboard` | **ver armadilha abaixo** |
| `cidadao.html` | `#tela-acesso` | sem auto-login |
| `clinica.html` | `#tela-login` | auto-login só sob `DEV_PRESET_CONTEXT` (falso na demo) |
| `validar.html` | `#card-busca` | sem sessão |

**(B) Heading/texto conhecido** por tela (sugestão original do despacho). Mais
legível, porém acoplado a texto de interface — envelhece pior.

> ⚠️ **Armadilha já paga, não redescobrir.** A marca tem de ser o estado
> **ESTÁVEL** em DEMO_MODE, nunca um transitório. O `#tela-login` do
> `dispensador.html` nasce visível e o auto-login demo (Fase 4,
> `dispensador.html:2598`) o esconde ao entrar no dashboard. Usá-lo como marca é
> **corrida** — na primeira versão do commit descartado, passou num teste e falhou
> no outro pela ordem de chegada. Por isso a marca dele é o **destino**
> (`#tela-dashboard`), não a origem.

### 3.4 Preservar a janela assíncrona do teste de console

`test_tela_sem_erro_de_console` é o único smoke que **precisa** de tempo de
assentamento: o erro que ele caça pode nascer de um bootstrap assíncrono (um
`fetch` que rejeita depois do `DOMContentLoaded`), não só da execução síncrona.
Era isso que o `networkidle` dava de graça.

Repor **sem** devolver a fragilidade: `networkidle` vira espera de **melhor
esforço** — timeout curto, falha tolerada.

```python
try:
    page.wait_for_load_state("networkidle", timeout=3_000)
except PlaywrightTimeoutError:
    pass  # rede não assentou; não é o que este teste audita.
```

A diferença é de **papel**: `networkidle` deixa de ser portão e vira cortesia.
Nunca mais reprova por causa do ambiente.

---

## §4 Fora de escopo

- Mexer no `conftest.py` — o deadlock já foi corrigido no #127
- Adicionar novos smokes ou novas telas ao gate
- Tocar `.html` de produto
- Mudar o `gates-browser.yml`

---

## §5 Critérios de aceite

1. Zero `wait_until="networkidle"` em `tests/browser/` (o melhor-esforço do §3.4
   é `wait_for_load_state`, não `goto` — e é o único uso remanescente permitido)
2. Zero `expect(page.locator("body")).not_to_be_empty()` em `test_smokes.py`
3. **Teste de mutação executado e relatado no PR.** Quebrar deliberadamente uma
   tela (ex.: renomear o container de entrada, ou introduzir um `ReferenceError`
   no bootstrap) e provar que o teste correspondente **FICA VERMELHO**. Sem isso
   não há prova de que a asserção nova tem dente — e o ticket inteiro existe por
   causa disso
4. Suíte completa (`pytest tests/browser`) verde **3× local** e **2× no runner**
   — a régua que o #127 estabeleceu
5. Sem regressão de tempo: a suíte não pode ficar mais lenta que a `main`
   (referência do #127: ~35 s com `networkidle`, ~23 s sem)

---

## §6 Fluxo de aprovação

1. Engenheiro implementa + teste de mutação (§5.3) + as rodadas do §5.4
2. Conselheiro — parecer leve: confirma que nenhuma asserção enfraqueceu
3. Martelo do Fabiano + merge

---

## §7 Coordenadas

| Trabalho | Relação |
|---|---|
| **TICKET-GATE-SMOKES-NETWORKIDLE** (PR #127, `1fb175d`) | Origem. Causa raiz já fechada — este ticket é a higiene que sobrou |
| **PR #126** (rodapé) | Seu teste novo `test_index_tem_contato_institucional` usa `networkidle`. Com o deadlock corrigido, passa. Alinhar aqui **se o #126 já tiver mergeado**; senão, coordenar para não conflitar |
| **Etapa C de UX (F5-C1/C2/C3)** | Em pausa. Toca `test_smokes.py` (linha ~317, `.atestado-card`) e `conftest.py`. **Conflito provável** — coordenar a ordem antes de começar |
