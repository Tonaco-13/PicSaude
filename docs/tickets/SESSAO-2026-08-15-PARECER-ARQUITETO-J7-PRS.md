# Parecer do arquiteto (Z) — J.7 (PR #165) + PRs #163/#164 + desenho J.10

| Campo | Valor |
|---|---|
| **Data** | 2026-08-15 (fecho do dia) |
| **Objeto** | PRs #163/#164/#165 (CI verde) · `SESSAO-2026-08-15-TICKET-ENG-011-PRS-E-J7.md` · `DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md` |
| **Veredito** | J.7 **APROVADO** (ver §1) · desenho J.10 **APROVADO com recomendação (b)** (§3) · escopo §10/§11b sai como **J.11** (§2) |

---

## §1 J.7 (PR #165, `core`) — revisão completa: APROVADO

Verificado no diff (`core/j7-transferir-e-posse` sobre `module/abas-j8-j9`):

1. **`states_exame.py`:** fiel ao martelo — duas arestas novas (`emitido → coletado` no
   pedido, `pendente → coletado` no item = "ou realizando direto"), **nenhum estado novo**,
   `agendado` volta a significar "existe agendamento com data/hora/unidade". A declaração
   explícita da aresta evita máquina declarada ≠ máquina real (o comentário registra o porquê).
   Governança acompanhou: `CLAUDE.md` + `ARQUITETURA_EXAMES.md` no mesmo PR; AGENTS §7 lista
   estados (inalterados), não arestas — sem edição necessária.
2. **`transferir-laboratorio`:** ato de posse e nada mais — custódia nível-pedido, **um**
   evento (`custodia_transferida`), itens intocados, pedido permanece `emitido`. O
   `pedido_agendado` fantasma (com `data_agendamento: None` — a confissão no payload antigo)
   morreu.
3. **Guard de status → custódia:** sem isso, cidadão poderia entregar o MESMO pedido a dois
   CNPJs (dupla posse ativa). Migração correta e necessária.
4. **Helpers de fonte única** (`detentor_atual_pedido` / `posse_do_cidadao`): a semântica
   `None` = nunca saiu do cidadão vs `'paciente'` = papel (não CPF) é o bug que o gate de
   navegador pegou — e a integração não pegaria (testes de lá emitem sem
   `enviar_ao_paciente`). Correção principled, não remendo; buraco de cobertura tapeado.
5. **Fila (`dispensadores.py`):** `pendente` entrou em `_ESTADOS_ITEM_ACIONAVEL_LAB` — sem
   isso o pedido recém-entregue sumiria da tela do laboratório ("o exame sumiu" da demo).
   Carteira (`auth.py`): `sob_minha_custodia` + `detentor` acrescentados **sem quebrar os
   baldes por status** — consumidores antigos intactos.
6. **Testes:** 306 linhas de browser novo + integração estendida + unit de estados; CI verde
   (gates + smokes).

ACs do §4.5 do despacho: **todos atendidos** (i) só `custodia_transferida`; (ii) fila
funciona por custódia; (iii) `agendado` só via `POST /agendamentos` (aresta + testes);
(iv) regressão cobre cidadão → fila → agendamento → realização; (v) guia/demos coerentes
(`cidadao.html`/`clinica.html` ajustados no PR).

**Merge: aguarda martelo do Fabiano no PR (padrão `core`).**

## §2 Escopo §10/§11b fora do #164 — aceite; vira J.11 (`module`)

Correto não incluir por conta própria (a ordem nomeou o conteúdo antes dos Adendos). E a
razão do engenheiro é a melhor possível: **com o J.7, o selo de agendamento (§10) só aparece
quando existe agendamento de verdade** — que é exatamente o que ele deve mostrar.

**DESPACHO J.11 (executar após merge do #165):** PR `module` próprio com (a) selo de
agendamento no cartão do exame (aba Exames; leitura papel `paciente`; agendamento ATIVO;
remarcação = derivado, mostra o corrente) e (b) lente compartilhada (componente extraído;
index intocado; "ver rastreabilidade" por cartão via `/public/*`). ACs dos Adendos §10/§11b
aplicam integralmente.

## §3 Desenho J.10 — análise CONFIRMA o bloqueio; recomendação (b)

**A alegação é verdadeira** — verifiquei: `pedido_exame_custodia` é ledger `de/para` sem
coluna de posse atual (`models/pedido_exame_custodia.py`), enquanto `prescricao_custodia`
tem `detentor_*` + `encerrada_em` com índice único parcial (COER-2). Num ledger append-only
não há "linha ativa" a restringir: **o AC (iii) é inalcançável sem migração**, e migrar cadeia
de custódia é `core` pela taxonomia §10. O §11c errou ao classificar como `module` puro —
meu erro de despacho; o desenho corrige.

**Recomendação do arquiteto: caminho (b)** — migração em PR `core` próprio
("custódia de exame ganha posse atual": `encerrada_em` + índice único parcial nos dois
dialetos + data-fix na migração + choke-point `transferir_posse_exame` + migração dos 3
sítios de leitura "última linha"), e o J.10 (`module` de verdade: endpoints `itens:[...]` +
`/devolver`, fila por custódia com o AC (vi) anti-vazamento, telas) empilha sobre ele.
O caminho (c) (desistir do AC iii) está vetado — é o defeito que o COER-2 existe para impedir.

**Martelo pendente do Fabiano:** aprovar o PR `core` da migração (formulado no fecho do
`Fabiano.md`). Sem ele, o J.10 não inicia (correto, §3).

**Nota §6 do desenho (RBAC assimétrico):** resolver a assimetria junto ao J.10 é a janela
certa, mas **é mudança de RBAC = `core`** — sai como micro-ticket `core` próprio no mesmo
combo, com martelo.

## §4 Ordem de merge e fila

1. **#163** (`ops`) — após ordem do Fabiano; independente.
2. **#164** (`module`) — após ordem; independente.
3. **#165** (`core`, base no #164) — após o merge do #164: rebase para a main + reapontar
   base (mesma dança do #162) + **martelo do Fabiano no PR**.
4. **J.11** (`module`) — após #165 (§2 acima).
5. **J.10** — após martelo da migração `core` (§3) + merge do #165.
6. Render (reset da vitrine): após os merges de #163/#164 (no mínimo o #163) — passo a passo
   já entregue ao Fabiano.

---

*Parecer do arquiteto (Z), fecho de 2026-08-15. Martelos pendentes: #165 (merge) e migração
`core` do J.10 (início).*
