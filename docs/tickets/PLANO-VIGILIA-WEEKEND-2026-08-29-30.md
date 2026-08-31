# PLANO — Vigília de fim de semana (29–30/08/2026)

| Campo | Valor |
|---|---|
| **Janela** | 29/08/2026 **00:01** → 30/08/2026 **18:00** BRT (autorização do Fabiano, 28/08) |
| **Quem** | Z (arquiteto), em rodadas automáticas neste workspace |
| **Por quê** | Engenheiro executando a fila (M-C → painel typeahead → base CBO); Fabiano ausente no fim de semana |
| **Veículo** | **UMA automação de múltiplos disparos** (`automation-5fba8e8e…`): cron `1 0,9,15,18 29,30 8 *` + `maxRuns=8`. A plataforma limita cada sessão a criar uma única automação e proíbe que uma rodada agende outra (anti-cadeia, por design) — por isso o cron único com prompt adaptativo que identifica a rodada pelo horário do disparo |
| **Fecho às 18:01** | Limitação estrutural: cron de 5 campos não mistura minuto/hora por dia. O disparo de abertura honra 00:01 exato; o fecho dispara 18:01 de domingo (60 s após o fechamento nominal da janela — declarado aqui) |
| **Política de merge** | **O arquiteto NÃO mergeia.** Veredito RATIFICADO + "APROVADO PARA MERGE" registrado; o gesto permanece do Fabiano (padrão da casa: #212 e #213 foram gestos dele) |
| **Log das rodadas** | `docs/tickets/SESSAO-2026-08-29-30-VIGILIA-WEEKEND.md` (criado na R1) |

## Rodadas (8 disparos)

| # | Quando (BRT) | Foco |
|---|---|---|
| 1 | sáb 00:01 | **Abertura**: cria o log, baseline (`origin/main` sha, PRs), fila esperada |
| 2 | sáb 09:01 | Revisão + sanidade pós-reset 04:00 (`/health`) |
| 3 | sáb 15:01 | Revisão de PRs contra ACs dos despachos |
| 4 | sáb 18:01 | Revisão + pendências acumuladas |
| 5 | dom 00:01 | Revisão |
| 6 | dom 09:01 | Revisão + sanidade pós-reset 04:00 |
| 7 | dom 15:01 | Revisão + preparo do fecho (consolida vereditos) |
| 8 | dom 18:01 | **Fecho**: relatório final, lista "aprovados p/ merge", handoff para segunda |

## Rotina de cada rodada (fixa)

1. `gh pr list` (abertos + mergeados) — **verificar merge claims de forma independente**
   (`gh pr view N --json state,mergedAt,mergeCommit`); nesta casa já houve duas
   afirmações de merge que o GitHub não confirmava.
2. PR novo/alterado → `gh pr diff` + confronto com os **ACs numerados** do despacho
   correspondente (`DESENHO-VITRINE-HIGIENE-VISITANTE.md` §7 para o M-C;
   `DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md` §3/§4/§6 para painel e base) + checks
   verdes. Veredito: RATIFICADO · BLOQUEADO (âncoras arquivo:linha) · AGUARDANDO.
3. Registrar no log da vigília + atualizar `FILA-VIVA.md` (reler do disco antes — o
   engenheiro pode tê-lo editado).
4. `WebFetch https://picsaude.com.br/health` — esperado `{ok:true}`; falha vira
   🚨 ALARME no topo do log (o reset diário roda 04:00 BRT).

## Limites invioláveis de toda rodada

Arquiteto, não engenheiro: não implementa, não edita código do app, **não mergeia**,
não toca no Render/dashboard, não cria/altera/deleta automações, não pergunta ao
usuário — dúvida vira pendência escrita. Git/GitHub somente leitura (via `gh`), exceto
os arquivos de registro citados.

## Cancelamento

Qualquer momento: `CronDelete` da `automation-5fba8e8e-f7fc-4768-b465-ce979566f071`
(remove a vigília inteira — as 8 rodadas). A rodada 8 encerra a janela por esgotamento
do `maxRuns`; nada fica ativo depois de domingo.

---

*Plano do arquiteto, 28/08/2026. Restrição de automação única por sessão registrada
como fato de plataforma; rodadas adicionais, se um dia necessárias, pedem sessão nova
(anti-cadeia é desenho da plataforma, não defeito).*
