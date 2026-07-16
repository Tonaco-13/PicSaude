# ROTEIRO DA DEMO V27 — dispensador: circulação fluída + SNGPC espelhado

| Campo | Valor |
|---|---|
| **Objetivo** | Demonstrar a **circulação fluída** de um objeto sanitário e o **relatório SNGPC espelhado no dispensador**, provando ao vivo os invariantes do PicSaúde. |
| **Tese** | A demo é um **laboratório de invariantes**: cada ato prova uma regra do CLAUDE.md/§2a — *a verdade deriva do ledger, nunca do rótulo ou de uma projeção editável.* |
| **Pré-condição** | Fatia B mergeada (B0→§5.A→B1→B2→B3) sobre R2. `seed_demo.py` rodado: Farmácia Central (`99999999000191`) com 1 receita sob custódia; Farmácia Norte (`99999999000272`) vazia. |
| **Decisões incorporadas** | (1) duas farmácias, roteiro pedagógico, sem seletor de troca (re-login por CNPJ); (2) fila pull 15s; (3) devolução integral/re-apresentação A→B **cortadas** — não aparecem no roteiro. |

> **Ao apresentador:** cada ato traz **[Clique]** (o que fazer) e **[Lição]** (o invariante que ficou
> provado). O poder da demo não é a tela bonita — é que **você não consegue trapacear**: o sistema não
> deixa apagar, não deixa duplicar, não deixa a farmácia vizinha ver o que não é dela.

---

## Ato 0 — Entrada com contexto verificado (fluxos #1, #2)

- **[Clique]** Login como **Central** (`99999999000191` + senha). Dashboard abre com o estabelecimento
  identificado no CNES (busca na base nacional).
- **[Lição]** O objeto clínico é global; a **operação é contextual** (CLAUDE.md §6b). Quem opera está
  amarrado a um CNPJ verificado — isso vai importar no Ato 6.

## Ato 1 — Fila e dispensação individualizada por item (fluxos #5, #6)

- **[Clique]** Mostrar a **Fila de Dispensação** (atualiza sozinha a cada 15s — pull). Uma receita,
  itens com **saldo**. Dispensar **um item** pelo botão ✓ Dispensar → modal de lote (Portaria 344/98) →
  confirmar. O saldo do item cai.
- **[Lição]** Dispensação é **granular por item**, não pela receita inteira. A soma dispensada **nunca**
  supera o prescrito (CLAUDE.md §4) — o sistema recusa se você tentar.

## Ato 2 — Comprovante COMPRADOR × PACIENTE (fluxo #11)

- **[Clique]** No sucesso da dispensação, abrir **📄 Comprovante**. Mostrar os dois blocos: quem
  **retirou** (comprador/portador) × para quem é a **indicação clínica** (paciente).
- **[Lição]** O portador pode não ser o paciente — e o comprovante registra os dois, **sem endereço**
  (minimização de PII, LGPD). Só nome + documento.

## Ato 3 — O momento-laboratório: estorno e re-dispensação (fluxos #7 + B0)

> **Este é o coração da demo.** É onde a tese "a verdade deriva do ledger" fica **visível e
> irrefutável**.

- **[Clique]** Estornar a dispensação que você acabou de fazer (⏪ Estornar → motivo). Mostrar:
  **o saldo é reposto** e o sistema diz *"o item volta a poder ser dispensado"*.
- **[Clique]** Voltar à fila: a receita **reapareceu**, o item está **acionável de novo**. Dispensar
  outra vez — **funciona**.
- **[Lição]** O estorno **não apagou** a dispensação: adicionou um **objeto de reversão** ao ledger. A
  dispensabilidade voltou porque é lida do **saldo efetivo** (Σ dispensado − Σ estornado), não de um
  rótulo. Se lêssemos o rótulo `dispensado`, o item ficaria "congelado" — foi exatamente o furo que o
  **B0** corrigiu. *A verdade é o ledger, não o carimbo.*

## Ato 4 — A receita sai da fila e vira histórico; o comprovante estornado se declara (fluxos #10 + B3)

- **[Clique]** Quando a receita esgota as ações, ela **sai da fila** e fica no **Histórico de
  Retenções**. Abrir o comprovante da dispensação **estornada**: ele mostra, inequívoco,
  **⏪ DISPENSAÇÃO ESTORNADA** com o **protocolo do estorno**.
- **[Lição]** Nada some, nada é editado. O comprovante da operação estornada **continua existindo** e
  **se declara** estornado — auditoria perfeita. O **protocolo da receita é o mesmo** antes e depois
  (regra de ouro, §6b): a identificação da receita emitida é **imutável**.

## Ato 5 — Relatório SNGPC espelhado: escrituração por movimento (fluxos #12, #13)

- **[Clique]** No cabeçalho da fila, **🖨️ Relatório Consolidado** (view de impressão) e **SNGPC
  (CSV/PDF)** (baixa o arquivo). Mostrar que **cada dispensação é uma linha** e **cada estorno é outra
  linha** (reversão), com o **saldo escriturado** do item.
- **[Lição]** O relatório é **projeção do ledger** (§2a R1): reexecutar o mesmo período dá o **mesmo
  resultado, sempre**. Cada movimento aparece **uma única vez** (§2a R2 — duplicidade seria alarme de
  fraude, e o R2 fecha essa porta no gate). "Estorno limpa o relatório" = **efeito contábil líquido
  zero** (a linha de reversão repõe o saldo), **não** deleção.

## (Ato 6 — Isolamento por CNPJ) — CORTADO da demo apresentada (decisão Fabiano, 2026-07-12)

> **Decisão:** a demo roda em **uma única farmácia (Central)**. Encerra no Ato 5. Motivo: fidelidade —
> a troca para a Norte, sob a trava do modo demo, só roda por atalho de console (inapresentável). Melhor
> uma farmácia impecável que duas com truque.

**O invariante NÃO foi perdido — só não é encenado.** O isolamento por CNPJ está **intacto no código**
(relatório travado ao CNPJ do JWT, Fatia A) e **verificado** (API: relatório da Norte = 0 linhas). A
Norte **permanece no seed** (vazia) — custa nada e mantém o isolamento testável.

**Nota falada opcional (se um comprador técnico — sobretudo do setor público — perguntar):**
> "Cada farmácia só enxerga o próprio livro — travado ao CNPJ do JWT, garantido por teste automatizado.
> Numa versão da demo com duas farmácias, isso vira uma cena ao vivo."

**Volta ao vivo quando quiser (v2):** basta o cartão "Farmácia Norte" no portal demo
(`TICKET-DEMO-PORTAL-NORTE.md` — backlog). Pequeno; o backend `dispensador_norte` já existe.

---

## Encerramento (a frase que fecha)

> Tudo o que você viu — dispensar, estornar, re-dispensar, imprimir — **deriva de um único
> livro-razão imutável**. Você não conseguiu apagar uma dispensação, não conseguiu duplicar um
> movimento, e o número da receita nunca mudou. A auditoria não é um relatório que a gente gera
> **depois**; é a **arquitetura** que estava lá o tempo todo.

## Fora do roteiro (dito ao vivo, se perguntarem)

- **Push em tempo real?** A fila atualiza por polling de 15s — suficiente para a demo; push é P2.
- **Devolução ao médico / re-apresentação entre farmácias?** Existem no modelo, **cortadas** desta
  fatia (P1 backlog) — não são necessárias para provar a circulação fluída.
- **Registro ANVISA / linhagem-mãe no relatório?** Vêm nas próximas fatias (R3, R4) — o relatório já é
  reproduzível e único hoje; aqueles enriquecem a coluna, não mudam o invariante.
