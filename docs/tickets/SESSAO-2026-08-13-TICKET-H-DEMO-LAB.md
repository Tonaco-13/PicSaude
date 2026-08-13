# Sessão 2026-08-13 — Engenheiro: Ticket H (demo end-to-end + verificação)

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator deste registro |
| **Arquiteto** | Z AI — autor do ticket |
| **Escopo** | Ticket H (`ops`/test) — depende de A–G ✅ |
| **Branch** | `docs/sessoes-11-12-agosto` — **sem commit**, trabalho na árvore |
| **Estado** | Entregue, **com um bloqueio registrado** (§6) e **um bug de vitrine corrigido** (§4) |

---

## §1 Resumo em uma frase

O roteiro da demo virou **teste executável** que atravessa três telas e dois perfis — e, ao rodá-lo
pela primeira vez, ele encontrou um **500 na vitrine** que nenhum gate via.

---

## §2 O que entrou

### `docs/ROTEIRO_DEMO_LABORATORIO.md`

O roteiro 1→5 para apresentar, com o que **falar** em cada passo — inclusive as três frases que não
podem faltar: a fronteira LIMS, o RT como autor, e "faturamento é contagem interna, **não** é guia
TISS". Traz também uma tabela de "se algo falhar na apresentação".

### `backend/tests/browser/test_demo_lab_e2e.py`

O mesmo roteiro, sem ninguém clicando:

```
1. prescritor emite (TUSS + SIGTAP)                       [API]
2. cidadão transfere a custódia                           [tela do cidadão]
3. fila → coleta → bancada → laudo assinado e liberado    [tela da clínica]
4. cidadão recebe e dá ciência                            [tela do cidadão]
5. a ciência reflui à clínica · faturamento TUSS ≠ SIGTAP [tela + API]
```

**Por que ele existe, se já há smokes de F e G:** aqueles provam cada gesto isolado; este prova que
os gestos **se encadeiam** — que a saída de um é a entrada do outro. E é a única prova de que a
**ciência do cidadão volta à tela da clínica**: um recorte por ticket nunca cruzaria essa fronteira.

Um detalhe que o teste ensinou: no passo 1 a clínica **ainda leva 403** ao ler o pedido — a posse só
chega no passo 2. O teste lê o item com o token do prescritor, que é o dono naquele instante. O 403
ali é o Ticket C funcionando, não um obstáculo.

### Complemento do G4 (poll da ciência)

O Ticket G previa "opcional: um poll leve de ~30s". Deixou de ser opcional: **sem ele o AC do H não
fecha**. Depois de liberar o laudo não há mais mutação no pedido — logo não há mais
`recarregarPedido()`, e a clínica **nunca** saberia da ciência. Poll de 30s (mesmo ritmo da fila),
que se **desliga sozinho** quando o laudo encerra.

---

## §3 Faturamento no roteiro — o que descobri sobre TUSS/SIGTAP

O ticket manda o passo 1 emitir com os dois códigos. Fui carimbar por escrita direta no banco (como
faz a suíte de faturamento) e descobri que **não é preciso**: `ItemExameIn` já aceita `codigo_tuss`
e `codigo_sigtap`, e o router os persiste. O comentário em
`test_faturamento_exames_clinica.py:79` — *"o payload de criação do MVP não expõe o campo"* — está
**desatualizado**. O E2E emite com os dois códigos pela API, sem tocar no banco.

> **Achado paralelo:** o `seed_demo.py` preenche `codigo_tuss` mas **nunca `codigo_sigtap`**. Na
> vitrine, portanto, `?agrupar_por=sigtap` joga tudo em "(não classificado)" — tecnicamente uma
> agregação distinta, mas não a narrativa "particular/TUSS/SUS" que a decisão #3 quer contar. **Não
> mexi no seed** (muda a vitrine, é decisão sua). Duas linhas resolvem, se quiser.

---

## §4 O bug que o E2E encontrou — 500 no faturamento da vitrine ⚠️

Ao rodar o roteiro pela primeira vez, `/clinicas/faturamento.csv` devolveu **500**.

### Diagnóstico

```
TypeError: can't compare offset-naive and offset-aware datetimes
  clinicas.py: if dt_inicio and dt < dt_inicio
```

O banco guarda `resultado_em` em **dois formatos**, conforme quem escreveu:

| Quem escreve | Como | Resultado |
|---|---|---|
| `seed_demo.py::_agora()` | `datetime.now(timezone.utc).isoformat()` | **com** fuso |
| routers (`pedidos_exame.py` etc.) | `datetime.utcnow().isoformat()` | **sem** fuso |

A janela do período é naive. Uma linha do seed encontra a janela → `TypeError` → 500.

### Provei que é pré-existente

`git stash` das minhas mudanças de Ticket D e reprodução contra um banco de demo reconstruído do
zero: **500 idêntico**. Não é regressão desta sessão.

### Por que nenhum gate viu

Os testes de integração rodam contra **PostgreSQL** e criam tudo **pela API** — nunca encontram uma
linha escrita pelo seed. O defeito só existe onde o seed existe: **no banco de demo, isto é, na
vitrine**. Os botões **"Relatório de exames"** e **"Faturamento"** do `clinica.html` estavam
quebrados lá, e nenhum gate acusava. É a mesma doutrina do `test_4d2`, um grau pior: não é verde
não-gateado, é **vermelho invisível em produção**.

### Correção

Normalização para naive-UTC no **funil único** `_como_datetime` — as duas rotas passam por ele
(`_filtrar_periodo` do relatório e `_linhas_faturamento` do faturamento), então a correção é uma só.
O fuso é **convertido** para UTC antes de descartado: descartá-lo cru deslocaria o instante e um
exame das 23h cairia no dia seguinte.

Guarda nova: `backend/tests/unit/test_clinicas_periodo_fuso.py` (5 casos) — cobre o normalizador, a
conversão correta de fuso, e as duas rotas com formatos misturados, incluindo o caso "a tolerância
não pode ter virado *aceita tudo*".

> **Sinalizo como escopo que adicionei:** é correção de código fora dos tickets F/G/H. Fiz porque o
> Ticket H é justamente "validar a demo", e entregar um relatório dizendo "a demo funciona" com o
> botão de Faturamento quebrado seria o pior desfecho possível. Mesma natureza da correção de
> `acionavel` no Ticket B, que o senhor endossou.

---

## §5 Gates

| Gate | Resultado |
|---|---|
| E2E do roteiro (Ticket H) | **1 passed** |
| `tests/browser` (completo) | **61 passed** (54 → 57 → 60 → 61 ao longo de F/G/H) |
| `tests/unit` | **419 passed** (412 no início do dia) |
| Integração (seleção `-k` da CI) | **326 passed** — sem regressão |

---

## §6 BLOQUEIO — `web-gui-tester` não existe neste ambiente

O ticket manda: *"Usar a skill `web-gui-tester` para um passe preto de caixa"*, e o AC final exige
que ela **aprove o fluxo crítico do clínica**.

**Essa skill não existe** — nem no repositório (`.claude/` só tem `settings.local.json` e
`worktrees/`), nem entre as skills disponíveis para mim neste ambiente. Não há o que invocar.

**Não substituí por improviso.** O que entreguei no lugar, e que é verificável:
`test_demo_lab_e2e.py` percorre o fluxo crítico do `clinica.html` em navegador real (Chromium via
Playwright), com asserções de estado no backend a cada etapa. É cobertura automatizada do mesmo
caminho — mas **não é** o passe preto de caixa pedido, e não me cabe declarar aprovado um AC cuja
ferramenta eu não tenho.

**Decisão do arquiteto:** (a) considerar o AC atendido pelo E2E de navegador; (b) apontar onde a
skill vive, para eu rodá-la; ou (c) removê-la do ticket.

---

## §7 Itens do ticket deliberadamente não executados

- **"Branch `feat/demo-lab-laudo-cidadao` com commits por ticket"** — a instrução desta sessão é
  explícita: **não commitar, não empurrar**. Todo o trabalho está na árvore.
- **"Atualizar o diário de sessões (`docs/sessoes-*`)"** — a convenção real do repo é
  `docs/tickets/SESSAO-*.md` (foi assim no commit `666b61b`). Os cinco relatórios desta sessão já
  são o diário.

---

## §8 Fila de decisões acumulada (dia 2)

| # | Assunto | Onde |
|---|---|---|
| 1 | `web-gui-tester` inexistente — AC do H em aberto | §6 |
| 2 | `GET /pedidos-exame/{proto}` não devolve paciente; painel mostra "Paciente: —" | Relatório do G, §3 |
| 3 | Sem seletor de `agrupar_por` na tela — SIGTAP só pela URL | Roteiro, passo 5 |
| 4 | `seed_demo.py` não preenche `codigo_sigtap` | §3 |
| 5 | `registrarColeta`/`registrarResultado` tratam 403 como sessão expirada | Relatório do F, §6 |
| 6 | `test_regras_receituario` vermelho por data fixa (2026-05-26) | Relatório do pacote §6, sessão anterior |

Nenhum bloqueia a demo. Todos são pequenos e nomeados.

---

*Registro emitido pelo Engenheiro em 2026-08-13. Classe `ops`/test, com uma correção `module` em
`clinicas.py` sinalizada no §4. O §6 é bloqueio real e aguarda decisão.*
