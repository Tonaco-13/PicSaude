# Handoff de continuidade — Arquiteto (Z) — PicSaúde

> Retome lendo isto primeiro. Atualizado em 2026-08-16 (tarde). Situação: Fabiano DEU
> "tudo autorizado" e VIAJOU; o engenheiro roda a fila em modo autônomo sob o protocolo
> do Adendo §10 do ENG-012. Sua primeira tarefa ao retomar: auditar o que a rodada
> autônoma produziu.

## Quem é quem

* Z (você): arquiteto do PicSaúde. Não escreve código de produção — verifica no código o
  que o engenheiro entrega, dá parecer, segura invariantes, classifica mudanças
  (core/module/docs/ops, AGENTS.md §10). O martelo final em core é do Fabiano.
* Engenheiro: Claude Code no Terminal do Mac. Executa tickets/despachos, roda gates, não
  commita sem ordem (exceto o que o ENG-012 §10 autoriza), registra relatório em
  `docs/tickets/`. Discordou de ponto técnico → PARA e devolve ao arquiteto (ENG-010 §3).
* Fabiano Tonaco: líder/arquiteto-líder. Martelo em core. Dono do repo (privado, AGPL-3.0).
  **Viajando desde 16/08 à tarde** — os pontos que exigem ele estão listados abaixo.
* Caminho do repo: `/Users/fabianotonaco/Developer/PicSaude_Dev` (Terminal do engenheiro).
  O ambiente do arquiteto vê o mesmo repo em `/Volumes/fabianotonaco/Developer/PicSaude_Dev`
  (sandbox bind-mount) — mesmos arquivos, só path diferente.

## Estado no momento do handoff (16/08, tarde)

Main em `097534a` (#162). Três PRs abertos, CI verde (gates + smokes), MERGEABLE,
todos com parecer favorável do arquiteto:

* #163 `ops` — CNES durável no boot (commit único `75b949f`; arquivos disjuntos do J.7).
* #164 `module` — abas J.8/J.9 + desambiguaute 403 (commit único `a7ddb58`).
* #165 `core` — J.7 (commit único `851dfe0` EM CIMA do #164; revisado e aprovado no
  parecer J7-PRS §1).

**Autorizações do Fabiano (16/08, "tudo autorizado", registradas no Adendo §10 do
ENG-012 e no bloco de 16/08 do `Fabiano.md`):**

1. Engenheiro mergeia #163 e #164 (squash + delete branch).
2. Martelo ANTECIPADO no #165, condicionado ao protocolo mecânico do §10b: rebase =
   replay de 1 commit com mensagem preservada + igualdade byte-a-byte entre
   `git diff a7ddb58 851dfe0` (patch revisado) e `git diff origin/main..HEAD` pós-rebase
   + CI verde. Tudo segurando → merge; QUALQUER divergência → NÃO mergeia e reporta.
   (Fundamentação verificada: os 3 PRs são 1 commit cada; interseção de arquivos
   J.7 × #163 é vazia; squash de #164 single-commit = árvore idêntica.)
3. Abertura da migração `core` da custódia LIBERADA — mas o MERGE dela pede martelo
   próprio do Fabiano no PR (ponto de parada da rodada).
4. J.11 (`module`) mergeia sob ordem geral — com revisão RETROATIVA sua.
5. PR `docs` (não versionados) autorizado.

## Primeiras ações ao retomar (17/08)

1. **Auditar a rodada autônoma:** `gh pr list` + `git log --oneline -10 origin/main` +
   ler o relatório `SESSAO-2026-08-16-TICKET-ENG-012-*.md` do engenheiro. Conferir que o
   #165 (se mergeado) cumpriu as 3 condições do §10b COM evidências no relatório
   (patches comparados, SHAs, CI). Merge de core sem evidência = incidente, levantar.
2. **Revisão retroativa do J.11** (module, mergeado sob ordem geral): selo de agendamento
   no cartão do exame + lente compartilhada; ACs dos Adendos §10/§11b do ENG-011.
   Achado = ticket de correção (fix-forward), como acordado.
3. **Revisar em detalhe o PR `core` da migração** ("custódia de exame ganha posse atual":
   `encerrada_em` + índice único parcial nos 2 dialetos + data-fix + choke-point
   `transferir_posse_exame` + 3 sítios de leitura "última linha" → `DESENHO-J10` §
   caminho (b)). Seu parecer sai ANTES do martelo do Fabiano. Verificar coerência com os
   helpers do J.7 (`detentor_atual_pedido`/`posse_do_cidadao`) — a migração deve
   absorvê-los, não duplicá-los.
4. Se o engenheiro não terminou (rodada em andamento): NÃO interferir no meio da dança;
   responder aos stop-points que ele reportar (§3 do ENG-012: discordância/surpresa).

## Pendências do Fabiano (na volta da viagem)

1. **Martelo + merge do PR `core` da migração da custódia** → destrava J.10 (module:
   `itens:[...]` opcional, `/devolver` por item, fila por custódia com anti-vazamento
   AC (vi)) + micro-ticket `core` do RBAC assimétrico no combo (martelo próprio).
2. **Reset da vitrine no Render** (runbook entregue; após #163 mergeado no mínimo;
   conferir `[cnes-demo] snapshot CNES garantido` no boot; nunca re-rodar snippet CNES).
3. Depois: J.10 + J.11 resolvidos → plano go-public (`planejamento/GO-PUBLIC-PLANO.md`,
   trilha GP-1..GP-4, gatilho = "vamos ao deploy").

## Itens rastreados (não bloqueiam)

* 401 "Signature verification failed" na vitrine (14/08, não reproduzido) — vigilância.
* `test_concorrencia.py` não coleta (importa `DATABASE_URL_TEST` inexistente) — dívida
  da main.
* Atomização V2 + individualização de exames: NA GAVETA, pós-go-public, UM programa
  (checklist de 6 itens no parecer de 15/08 / Fabiano.md).

## Referências rápidas

* Despacho vigente: `docs/tickets/DESPACHO-ENG-012-MERGES-E-REBASE-DO-J7.md` + **Adendo
  §10** (protocolo da rodada autônoma — fonte de verdade desta janela).
* Pareceres 15/08: `SESSAO-2026-08-15-PARECER-ARQUITETO-J7-PRS.md` (J.7 aprovado,
  J.11 despachado no §2, J.10 caminho (b)) e `SESSAO-2026-08-15-PARECER-ARQUITETO-
  ENG-011-REVISAO.md`.
* Desenho J.10: `docs/tickets/DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`.
* Decisões: `Fabiano.md` (blocos 14, 15 e **16/08** — autorizações da viagem).
* Princípios: `AGENTS.md` (§5a governança de estados, §10 taxonomia),
  `docs/NUCLEO_SANITARIO.md`.

## Princípios que não podem esquecer

Objetos sanitários imutáveis após emissão · ledger INSERT-only · custódia ≠ agenda (J.7) ·
posse lê-se da custódia, não do status · encerrado_fisico ≠ cancelado · CPF sentinela
'00000000000' · invariante afirmado sem constraint de banco não é invariante (COER-2) ·
adapter/transmissão externa só com G4A · diagnosticar antes de agir (cruzar fontes;
observar efeito ≠ observar causa) · core não se auto-mergeia — martelo do Fabiano,
registrado em documento.

*Handoff atualizado pelo arquiteto (Z) em 2026-08-16, antes do início da rodada autônoma
do engenheiro.*