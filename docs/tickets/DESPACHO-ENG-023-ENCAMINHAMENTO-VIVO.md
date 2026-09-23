# DESPACHO-ENG-023 — Encaminhamento Vivo: a terceira circulação ganha o papel que nunca teve

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 23/09/2026 — sequência martelada (*"vamos, exames primeiro"* — Exame ✔ NO AR; esta é a segunda da ordem: Encaminhamento → depois Atestado) |
| **Classe** | `module` — frontend puro |
| **Lei do ticket** | `docs/tickets/DESENHO-ENCAMINHAMENTO-VIVO.md` (Kimi, **COM VISTO**) + `PARECER-ARQ-ENXAME-DEMAIS-OBJETOS-2026-09-22.md` (adjudicações) — **commit ambos na PR** |
| **Régua visual** | `conceitos-encaminhamento/` (moc + capturas) · **`documento-referencia.pdf` = o papel canônico** |
| **Base** | `origin/main` atualizado (`479cc7c`) |
| **Entrega** | 1 PR (o núcleo já existe — esta onda é consumação, não extração) |

---

## §1 O que é esta onda

O encaminhamento é o único dos quatro objetos cujo **papel inteiro aponta para
alguém** — e hoje esse alguém não aparece em lugar nenhum da tela: o documento
só existe **na revisão** (um passo antes do ponto de não-retorno) e é escondido
logo após a emissão (`form.reset()`, `prescritor.html:1921`), virando linha de
lista. Sem impressão própria (`enc_tem_print_proprio: false`). Evidência da Kimi
com protocolo real: `12e1bf3f-d47c-4054-a66b-b3ec0e7455fd`.

**O padrão inteiro, na anatomia própria** (que NÃO é a da receita): split
pena/papel, **DESTINATÁRIO em destaque** (caixa azul de dois fios com
especialidade em corpo maior, finalidade e CNS — a assinatura deste papel), a
**frase gerada visível** ("Encaminho o(a) paciente X para *finalidade* em
*ESPECIALIDADE*"), itens numerados com procedimento/motivo, lacunas, tinta por
`data-bloco`, carimbo que congela, selo rotacionado, FAB mobile, estética A1–A6.

## §2 As três perguntas do ticket — respondidas (não reabrir na PR)

1. **Alvo Y (§3.a dele): o documento canônico v2 promovido a papel.** A folha
   espelha um a um os campos que o SHA-256 congela
   (`_documento_canonico_encaminhamento()`, `routers/encaminhamentos.py:197-256`).
   A onda **cria o alvo de impressão que o objeto nunca teve**:
   `#print-area-encaminhamento` (adjudicação print-area-por-objeto), alimentado
   pelo gerador único. **Sem endpoint novo; PDF/QR público segue fora de escopo**
   (DESENHO-ENCAMINHAMENTO-UX §10).
2. **Selo (§3.b): "✓ EMITIDO · CUSTÓDIA AO CIDADÃO"** — endossado no parecer (a
   emissão digital abre a posse no cidadão, motivo canônico `emissao_digital` do
   AGENTS; a variante "COM O CIDADÃO" fica de fora — o selo nomeia o fato
   jurídico do ledger, não a etiqueta da lista). Conteúdo do estado emitido, não
   cromo de modo (W≡Y intocado).
3. **Núcleo (§3.c): pergunta dissolvida por construção.** O
   `documento-nucleo.js` nasceu no #273 — **o `encaminhamento.js` é o terceiro
   consumidor**. Se algo do núcleo precisar crescer para vestir este objeto (ex.:
   a caixa de destinatário como bloco enfatizado), a peça SOBE ao núcleo no mesmo
   PR com a receita e o exame verdes sem adaptação (a régua da extração segue
   valendo).

## §3 Os 10 ACs do ticket (§5 dele) — todos obrigatórios

Tecla a tecla (finalidade, typeahead de especialidade com escape OUTRA, CNS,
CID, justificativa, itens com delegação robusta) · lacuna legível (A5) · **W≡Y
com guarda própria** (`textoDoDocumento(folha) === textoDoDocumento(print)` no
mesmo estado, incluso o emitido) · carimbo sem navegação + **congelamento** ·
pena não engolida (≥40% em 1366px, typeaheads legíveis) · **especialidade pelo
valor canônico** (hidden do typeahead) · M-D/A2 + **máscara de CNS
`000 0000 0000 0000`** · FAB que não cobre o emitir · **fluxo de emissão não
muda** (revisão → confirmar → POST com o mesmo payload; suítes do ENG-016 verdes
sem adaptação de roteiro) · estética A1–A6 completa.

## §4 Intocáveis

Zero backend (o endpoint já aceita `procedimento`/`motivo` por item —
`routers/encaminhamentos.py:573-577` — nenhum campo novo) · estados/ledger/
custódia intocados · contrarreferência fora (Fork 3, onda própria) · regulação
segue badge honesto sem engine · "sugestão de destino" convive, não entra no
papel · nenhuma promessa gov.br.

## §5 Rito

1 PR; AC×teste×arquivo (gabarito: `test_eng018`/`test_eng022` — a FORMA, nunca o
template do documento); vermelho-antes-do-verde (a sabotagem do W≡Y do
encaminhamento tem que morder); suítes completas (a receita E o exame verdes sem
adaptação — prova de que o núcleo não regrediu); CI gates+smokes. **Ratificação
do arquiteto inclui a conferência visual contra o `documento-referencia.pdf`**
(a régua), ao vivo pós-merge. Merge só com RATIFICADO + martelo do Fabiano.

---

*Lavrado em 23/09/2026. O exame provou que a família existe; o encaminhamento
devolve à terceira circulação o que ela nunca teve — um papel que aponta para
alguém, visível a cada tecla, antes do ponto de não-retorno.*
