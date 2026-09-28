# DESPACHO-ENG-025 — Retomada: a PR do Atestado + a nona row + a caneta em lote

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro |
| **Data** | 24/09/2026 (tarde) — martelos do Fabiano NA RETOMADA, verbatim: **"Vamos lá prosseguir com 1, 2 e 3. Mensagem à engenharia, por favor."** |
| **Classe** | §A zero-código (abertura de PR) · §B/§C `curadoria` (dados + guardas, zero app) |
| **Base** | §A: branch EXISTENTE `eng024-atestado-vivo` (`570c8e9`, já na origin) · §B/§C: `origin/main` |
| **Entrega** | 3 PRs, NESTA ordem: **A → B → C** (B e C colidem nos CSVs — nunca paralelos) |
| **Autorizações citáveis** | 23/09: *"manda a caneta da nona row com o PCDT 2021"* · 24/09: *"Vamos lá prosseguir com 1, 2 e 3"* |

---

## §A — A PR do Atestado Vivo (o trabalho já está pronto e revisado)

O branch perdeu a PR na queda do volume de 24/09. O rito do arquiteto já
correu contra o branch (24/09, seção "Retomada pós-volume" do manual do
intensivo): conteúdo **aprovado com prova própria** — guardas re-rodadas
19/19 + 18/18 + 18/18 + 21/21, selo conferido como fato em `atestados.py:440/
540/548`, núcleo byte-idêntico ao #274, zero backend. O veredito era
AGUARDANDO **só** porque a PR não existia e o CI nunca correu.

1. `gh pr create` do branch existente — **SEM nenhum commit novo**. Se o diff
   do branch já não for exatamente `570c8e9`, PARAR e reportar.
2. Corpo da PR: o sumário já escrito no commit + referência ao
   `DESPACHO-ENG-024-ATESTADO-VIVO.md` (committed no próprio branch) + a
   citação do martelo de 24/09.
3. CI `gates`+`smokes` verde → avisar o arquiteto para o RATIFICADO formal →
   **merge é clique do Fabiano** (o martelo dele já está dado; o rito fecha
   com o veredito escrito).
4. Pós-merge (fora da tua sessão): ff da main + conferência visual ao vivo
   com evidência em `conceitos-atestado/capturas-producao/` — régua:
   `conceitos-atestado/documento-referencia.pdf`.

**Intocáveis: TUDO.** Nenhuma linha de código muda nesta PR.

## §B — Nona row J44 (a caneta que faltava)

GO do Fabiano, 23/09: *"manda a caneta da nona row com o PCDT 2021"*.

1. **Estagiar o PCDT DPOC 2021** como adendo em
   `data/fontes-oficiais/pcdt/adendos-pos-batch/` (padrão do #272): download
   da fonte oficial, sha256 + entrada no MANIFEST. **O PDF é o juiz da
   data**: o texto do PCDT 2025 revoga "nº 19, de **16/11/2021**"; a fala da
   casa dizia 22/11 — registra no MANIFEST o que o documento estagiado diz
   na capa/rodapé, sem adjudicar de ouvido.
2. **Dose COM PÁGINA e citação verbatim** do 2021 para a associação
   LABA+ICS (fumarato de formoterol + budesonida). O elenco segue do
   **PCDT DPOC 2025** (Portaria Conjunta SAES/SCTIE nº 29, de 27/11/2025,
   68 págs., p. 19 — já no corpus, `pcdt-da-doenca-pulmonar-obstrutiva-
   cronica.pdf`). Procedência DUPLA nas citações da row.
3. **A row**: `posologia_sugerida.csv`, chave composta
   `(fumarato de formoterol + budesonida, J44)` — a nona row que o #269
   deixou de fora honestamente (sem dose na fonte, não se escreve row).
4. Guarda: estender `test_semaforo_flip_j44_i50` (ou família nova no padrão)
   — a dose de ASMA não vaza para a DPOC, a row nova não colide no índice
   `(ativo, CID)`.
5. **Se o 2021 também não trouxer dose**: PARAR e reportar — a pendência
   original continua de pé, e é registrado como fato, não contornado.

Zero backend/app: dados + testes.

## §C — Caneta em lote: a pilha inteira

Autorização: 24/09, *"Vamos lá prosseguir com 1, 2 e 3"*, citada verbatim no
corpo da PR. **P-9 está resolvido por construção** (chave `(ativo, CID)` LIVE
desde o #269) — a pilha flui INTEIRA, sem partições de gating.

1. **A pilha, enumerada no corpo da PR** — todo rascunho no disco ainda não
   flipado. Hoje são **14**: `A30 · D50 · D57 · E28 · E78 · F17 · G20 · G30 ·
   G40 · IST · L20 · L40 · M81 · R52`. (O registro projetava 16: os 2 da
   conta são **K21 + E03**, que a R4/R5 ainda não lavraram — **FORA deste
   despacho**, lote seguinte. Não flipa o que não tem rascunho.)
2. **Pontos de decisão: seguir a recomendação registrada no próprio
   rascunho** (precedente #261 §4), cada decisão CITADA no corpo da PR com a
   página do rascunho. Rascunho sem recomendação num ponto → **pendência
   escrita de volta ao Fabiano**, nunca adjudicada pela engenharia. Pontos
   conhecidos: **D57** (5 antimicrobianos de intercorrência → rec. NÃO-rows;
   CID triplo D57.0/.1/.2 → guarda-chave D57 umbrella), **D50** (formato
   velho sem seção CID → chave proposta no rascunho; ácido fólico como
   observação), **IST** (26 rows em 11 CIDs — keying por CID), **E28** (CID
   dupla E28.2+L68.0), **G20** (flip livre de colisão).
3. Cada condição vira **exaustiva** no `decisao_semaforo.csv` com página nas
   fontes (padrão E11/J45); posologias citáveis entram no
   `posologia_sugerida.csv` pela chave composta; versão nomeada por condição
   (`semaforo_<cid>_exaustiva_v1_2026-09`, salvo recomendação diversa no
   próprio rascunho).
4. Guardas: família `test_semaforo_flip_*` por cluster + o literal de CIDs
   do `test_semaforo_flip_i10_v2::test_nenhuma_outra_condicao_touch`
   atualizado como **ATO DECLARADO** (a casa faz isso a cada caneta).
   Vermelho-antes-do-verde nas guardas novas.
5. Self-check: citações dos pontos de decisão reabertas contra os PDFs
   (mínimo 3 por rascunho, padrão do intensivo — a lição da adjudicação da
   insulina: o PDF é o juiz, inclusive da direção da divergência).
6. **Um PR para o lote.** Se o diff explodir em revisão, declarar no corpo e
   dividir em sub-lotes SERIAIS (os CSVs colidem entre si — nunca paralelos).

Zero backend/app: dados + guardas.

---

## Rito comum

- Merge é do Fabiano, um clique por PR, **depois de RATIFICADO por escrito**
  em cada uma (arquiteto). O martelo geral já está lavrado acima; o rito não
  abre exceção.
- Commit deste despacho na primeira PR que pousar (precedente: o despacho do
  ENG-024 viajou no próprio branch).
- GitHub via `gh` para abrir/ver PRs; nenhum deploy, nenhum Render, nenhum
  toque em automações.

*Lavrado em 24/09/2026. A queda do volume comeu dois gestos — a PR e a nona
row; a caneta em lote estava madura desde o #269. Os três cabem numa sessão
de engenharia, na ordem A → B → C.*
