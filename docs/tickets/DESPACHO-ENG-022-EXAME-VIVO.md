# DESPACHO-ENG-022 — Pedido de Exame Vivo: a primeira remontagem da família (e o nascimento do núcleo)

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 22/09/2026 — martelo do Fabiano: *"vamos, exames primeiro"* (ordem das ondas: Exame → Encaminhamento → Atestado) |
| **Classe** | `module` — frontend puro |
| **Lei do ticket** | `docs/tickets/DESENHO-PEDIDO-EXAME-VIVO.md` (Kimi, **COM VISTO do arquiteto**) + `PARECER-ARQ-ENXAME-DEMAIS-OBJETOS-2026-09-22.md` (adjudicações 1–5 — **commit ambos na PR**) |
| **Régua visual** | `conceitos-exame/` (moc navegável + capturas) · **`conceitos-exame/documento-referencia.pdf` = o papel canônico** · `pdf-vitrine-atual-6658c65c.pdf` = o Y real de hoje |
| **Base** | `origin/main` atualizado (pós-#269/#270 — **as PRs #271/#272 do ENG-021 são independentes e não colidem**) |
| **Entrega** | **1 PR com 2 commits** (extração + remontagem — ver §2) |

---

## §1 O que é esta onda

O pedido de exame **não tem documento em tela em momento nenhum** — pior que a
receita pré-Viva: nem print-area tardio. O túnel é de 654–1.094 px, o protocolo
nasce 650 px acima de quem emitiu, e o papel oficial só existe como PDF do
servidor atrás de um botão. Esta onda aplica o padrão Receita Viva **inteiro** na
anatomia do PEDIDO (que é a do PDF oficial — cabeçalho com selo de prioridade
ROTINA/URGENTE/URGENTÍSSIMO, blocos PRESCRITOR/PACIENTE, INDICAÇÃO com CID como
selo, EXAMES numerados com TUSS/SIGTAP e preparo em itálico, identificação do
documento, assinatura).

**Os 10 ACs estão no ticket (§5 dele) — todos obrigatórios**, incluindo: tecla a
tecla com delegação robusta a cards, lacuna pontilhada, **W≡Y com guarda própria
do objeto** (`PedidoExame.textoDoDocumento`, incluindo o estado emitido),
carimbo sem navegação + folha congelada, pena não engolida, CID pelo hidden
`exam-cid-escolhido`, M-D/A2, FAB que não cobre o emitir, fluxo físico
**inalterado** (síncrono via servidor), selo pós-emissão.

## §2 A peça central desta onda: o NÚCLEO nasce aqui (adjudicação 3 do parecer)

**Commit 1 — extração, comportamento zero:** nasce **`documento-nucleo.js`**
recebendo de `receituario.js` (por doação, semântica intacta): `lacuna` (com o
**modo inline** já no contrato — a lição do degenerado entra no núcleo DESDE O
nascimento), `esc`, **tinta por `data-bloco`**, o contrato **W≡Y**
(`montar`/`textoDoDocumento`/`MODOS`), o **FAB** com recolhimento por
IntersectionObserver, e as máscaras leves. **Prova de que a extração é
comportamento-zero: a suíte inteira da Receita Viva (browser + estática) verde
SEM adaptação nenhuma** — o `receituario.js` passa a consumir o núcleo e continua
sendo o gerador da receita com a anatomia dele.

**Commit 2 — a remontagem:** **`pedidoexame.js`**, gerador do pedido com anatomia
própria (adjudicação do parecer: `receituario.js` NÃO vira `documento.js`
parametrizado — "duas anatomias numa função só é a dupla posse pela porta dos
fundos"), consumindo o núcleo. Split pena/papel no `#submod-exames`, folha viva
(`#folha-viva-exame`) + **print-area próprio `#print-area-exame`** (adjudicação 1:
um alvo por objeto; o `#print-area` singular segue da receita), carimbo que
congela, estética **A1–A6 normativa** (`DESPACHO-ENG-020` §2 — palco creme,
serif no documento/sans na UI, borda `#D9D2C0` + sombra, lacuna legível ≥3:1,
papel ≥2/5 em 1366px).

## §3 Decisões já marteladas/endorçadas (não reabrir na PR)

1. **Selo do exame (AC10): "✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE"** — endossado
   no parecer (ARQUITETURA_EXAMES: a emissão digital abre a posse no cidadão);
   "rumo ao prestador" REJEITADO (anteciparia fato — lição do
   `pedido_agendado` fantasma). GO do Fabiano na onda + endosso no parecer.
2. **Fluxo físico NÃO muda** (AC9): `imprimirPedidoFisico()` segue síncrono via
   servidor; a print-area nova é alvo de W≡Y e conferência — o papel oficial
   continua nascendo no backend.
3. **CID no payload: FORA DE ESCOPO** — é defeito de contrato reconhecido
   (parecer §3.5), ticket de backend PRÓPRIO, depois das três ondas. A folha
   exibe o CID do estado do formulário; o objeto não o carrega — e esta onda
   não muda isso.

## §4 Intocáveis

Zero backend (endpoints, estados, ledger, custódia, migrações, CSVs) ·
`pdf_pedido_exame.py` intocado · M-D/A2 permanentes · nenhuma promessa
gov.br/em-breve · agendamento/coleta/bancada/J.10 fora · preparo editável fora
(débito futuro, como a posologia da receita).

## §5 Rito

1 PR, 2 commits (extração / remontagem) separados no corpo; AC×teste×arquivo
tabela (o gabarito é o `test_eng018_receita_viva.py` — copie a FORMA dos testes,
nunca o template do documento); vermelho-antes-do-verde nas guardas novas (a
sabotagem do W≡Y do exame tem que morder; a extração tem que deixar a receita
100% verde sem adaptação); suítes completas; CI gates+smokes. **A ratificação do
arquiteto inclui a conferência visual contra o `documento-referencia.pdf`** (a
régua) além das guardas. Merge só com RATIFICADO + martelo do Fabiano.

---

*Lavrado em 22/09/2026. A receita provou a mecânica; o exame prova a família — e
o núcleo nasce consumido por dois, nunca órfão.*
