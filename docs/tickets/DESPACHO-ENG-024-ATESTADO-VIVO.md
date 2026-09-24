# DESPACHO-ENG-024 — Atestado Vivo: o degenerado — a prova de verdade da família

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 23/09/2026 — última onda da sequência martelada (Receita ✔ · Exame ✔ · Encaminhamento ✔ NO AR `8decd69`; esta fecha os quatro forms de emissão) |
| **Classe** | `module` — frontend puro |
| **Lei do ticket** | `docs/tickets/DESENHO-ATESTADO-VIVO.md` (Kimi, **COM VISTO**) + `PARECER-ARQ-ENXAME-DEMAIS-OBJETOS-2026-09-22.md` — **commit ambos na PR** |
| **Régua visual** | `conceitos-atestado/` (moc + capturas + `vitrine-atestado-oficial.pdf` = o Y real de hoje) · **`documento-referencia.pdf` = o papel canônico** |
| **Base** | `origin/main` (`8decd69`) |
| **Entrega** | 1 PR (`atestado.js` = quarto consumidor do núcleo) |

---

## §1 O que é esta onda

O atestado é **o degenerado monolítico**: 18 campos, 1.104 px de túnel, nenhum
item, nenhuma lista — **uma frase que o CFM manda fechar**. O documento não
existe em tela em momento nenhum; o único texto pré-emissão é a caixa da IA
Documental carimbada "RASCUNHO — SEM VALIDADE LEGAL". O padrão inteiro aqui:
split pena/papel, **a lacuna INLINE dentro da frase** ("Atesto, para fins
_finalidade_, que…"), os dois ramos ao vivo (comparecimento ⇄ afastamento — a
folha ensina a regra de domínio), tinta por **região nomeada**, carimbo que
congela, selo por fluxo, FAB, A1–A6.

## §2 As perguntas do ticket — respondidas (não reabrir na PR)

1. **Alvo Y (pergunta 1): a print-area do atestado é espelho de conferência.**
   A folha viva + `#print-area-atestado` (print-area por objeto) são renders da
   mesma função geradora; **o papel oficial continua nascendo no servidor**
   (`pdf_atestado.py` intocado — um renderizador oficial, menor atrito). E a
   **guarda FORTE deste objeto é folha ≡ domínio**: o corpo da folha confere
   com o `corpo_documento` do `POST /ia/documentos/atestado/validar` para o
   mesmo estado (`texto_atestado.py` é a fonte única da frase — protegida por
   `test_atestado_espelho.py`). O Y de cada objeto é onde a verdade dele mora.
2. **Selo (pergunta 3): "✓ EMITIDO · CUSTÓDIA AO PACIENTE" é FATO.** A cautela
   da Kimi pediu o fato na mesa — e o fato está: `atestados.py:440` registra
   custódia prescritor → paciente **na própria emissão** (INSERT em
   `atestado_custodia:540`; evento `custodia_transferida:548`; GET
   `/atestados/{p}/custodia:722`). Físico: "🖨 IMPRESSO · EMISSÃO FÍSICA — SEM
   CUSTÓDIA DIGITAL", com o hash virando a nota honesta "não gerado — emissão
   física".
3. **Título oficial na folha viva: SIM** (adjudicado — precedente Receita Viva:
   a folha é o documento se formando; título por conselho: ATESTADO
   MÉDICO/ODONTOLÓGICO). A proibição MANTIDA no rascunho da IA Documental
   (artefato de feature diferente).
4. **Núcleo: dissolvido por construção.** `atestado.js` = quarto consumidor do
   `documento-nucleo.js`. As duas lições do degenerado já estão no contrato
   desde o nascimento (região nomeada; lacuna inline — que estreou no #274).
   Peça nova que este objeto pedir sobe ao núcleo no mesmo PR, com os três
   irmãos verdes sem adaptação.

## §3 Os 11 ACs do ticket (§5 dele) — todos obrigatórios

Tecla a tecla (todos os 14 campos) · **lacuna inline com pontuação fechando em
volta** · W≡Y nos dois modos + **a guarda folha ≡ `corpo_documento`** · carimbo
sem navegação + emitida não se edita · pena não engolida · **os dois ramos
fecham como o domínio** (cláusula clínica nos quatro casos; observação como
acréscimo, nunca substituição) · **conselho muda o documento inteiro** (CFM↔CFO,
CRM/CRO) + CPF mascarado · M-D/A2 · FAB (a versão variádica do núcleo —
aproveita) · fluxo físico honesto · selo por fluxo com rotação.

## §4 Intocáveis

Zero backend — **`texto_atestado.py`, `pdf_atestado.py`, o endpoint de PDF, a IA
Documental: intocados** (a folha convive com a validação; absorver é outro
ticket) · estados/ledger/custódia intocados · o achado do typeahead de CID
("gripe" sem sugestão) é débito do typeahead, não desta onda · nenhuma promessa
gov.br.

## §5 Rito

1 PR; AC×teste×arquivo (gabarito dos três anteriores — a FORMA, nunca o
template); vermelho-antes-do-verde (a sabotagem do W≡Y do atestado tem que
morder; a guarda folha≡domínio tem que reprovar divergência injetada); suítes
completas — **receita, exame E encaminhamento verdes sem adaptação** (a prova
de que o núcleo não regrediu nos três); CI gates+smokes. **Ratificação inclui a
conferência visual contra o `documento-referencia.pdf`**, pós-merge. Merge só
com RATIFICADO + martelo do Fabiano.

---

*Lavrado em 23/09/2026. O atestado é o objeto que não tem onde se esconder —
sem itens, uma frase. Se a folha a fecha diante do prescritor e o carimbo cai
na mesma folha, o padrão deixa de ser o padrão da receita e vira **o padrão da
casa**.*
