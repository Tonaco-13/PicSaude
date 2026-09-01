# Roteiro da demo — Laboratório: da custódia ao laudo em posse do cidadão

| Campo | Valor |
|---|---|
| **Origem** | `planejamento/demo-laboratorio-laudo-cidadao/TICKET-H-demo-e2e.md` — caminho gerencial, removido do histórico pelo GP-3/B2 (31/08); citação histórica, não navegável |
| **Vigência** | 2026-08-13 |
| **Prova executável** | `backend/tests/browser/test_demo_lab_e2e.py` — este roteiro, sem ninguém clicando |

---

## A frase que a demo prova

> O laboratório **opera a trilha sanitária** do exame — recebe a custódia, coleta, manda à bancada,
> produz o laudo e o **libera ao cidadão**. O laudo clínico fica em posse do cidadão; o laboratório
> retém **rastro forense + mínimo legal**.

---

## Antes de começar

- Banco de demo semeado (`PICSAUDE_DEMO_MODE=true alembic upgrade head` + `seed_demo.py`).
- Personas no painel "Chaves de acesso demo" — cidadão, prescritor e clínica.
- Três abas: `prescritor.html`, `cidadao.html`, `clinica.html`.

> **Fale isto na abertura:** tudo que vai aparecer é **projeção de um ledger imutável**. Nenhuma
> tela edita objeto sanitário emitido — cada gesto vira evento.

---

## 1 · Prescritor emite o pedido

**Onde:** `prescritor.html`

Emita um pedido com dois exames — por exemplo **Hemograma Completo** e **Glicemia de Jejum** —
classificados nas duas tabelas (`codigo_tuss` **e** `codigo_sigtap`).

> **Por que os dois códigos:** é o que permite, no passo 5, contar a **mesma** produção por
> pagadores diferentes — plano de saúde e SUS.

## 2 · Cidadão entrega a posse ao laboratório

**Onde:** `cidadao.html` → carteira de exames

O CNPJ da clínica já vem preenchido. Um clique em **Transferir Custódia**.

> **Fale isto:** é o **mesmo gesto** da receita. O cidadão não "compartilha um arquivo" — ele
> **transfere a posse**, e isso vira `custodia_transferida` no ledger.

## 3 · Laboratório recebe e processa

**Onde:** `clinica.html` (login da clínica — papel `dispensador`, CNPJ)

1. **Fila de Exames** — o pedido chegou sozinho. Sem digitar protocolo. Abra pelo card.
2. **Registrar coleta** — o item vai a `coletado`.
3. **Enviar à bancada** — informe o setor (ex.: *bioquímica*). O item vai a `em_analise` e passa a
   exibir **"Na bancada — aguardando laudo"**.
   > **Fale isto:** `setor` é *work-area*, texto livre. O PicSaúde é a **trilha sanitária, não o
   > LIMS** — analisador, técnico e fila de equipamento são do sistema do laboratório.
4. **🔬 Produzir laudo** — o editor abre pré-preenchido com os exames que estão na bancada.
   - Por exame: **resultado**, **conclusão** (normal / alterado / indeterminado / inconclusivo) e
     **valor de referência**.
   - **Responsável Técnico** já preenchido.
   > **Fale isto — é o coração:** quem opera é a **unidade** (CNPJ), mas o laudo é **sempre
   > atribuído ao RT** (CNS). O CNPJ fica no ledger como *produtor*, **nunca** como autor.
5. **Assinar e liberar ao cidadão.**
   > **Fale isto:** neste instante a **custódia clínica passa ao cidadão**
   > (`laudo_custodia: prestador → paciente`). O laboratório fica com protocolo, hash SHA-256,
   > ledger e cadeia de custódia. Ver `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md`.

## 4 · Cidadão recebe o laudo

**Onde:** `cidadao.html` → carteira de laudos

O laudo está lá, com a conclusão por exame. **Baixar PDF** e **Dar ciência**.

> **Fale isto:** ele não pediu acesso ao sistema do laboratório. O laudo **é dele**.

## 5 · Laboratório fecha o ciclo

**Onde:** `clinica.html`, aba ainda aberta no pedido

1. O painel do laudo avança para **"Ciência do cidadão"** (poll de 30s).
2. **Faturamento** — no cabeçalho, o seletor ao lado do botão escolhe a tabela:
   - **TUSS (planos)** → baixe. Depois troque para **SIGTAP (SUS)** → baixe de novo.
   - Abra os dois CSVs lado a lado: **mesma produção, códigos diferentes**. O critério vai no nome
     do arquivo e no cabeçalho da planilha, então não há como confundir qual é qual.

   > **Fale isto, sem falhar:** é **classificação e contagem internas**. **Não** é guia TISS nem
   > APAC — transmitir a operadora ou ao SUS depende da camada de publicação de eventos (G4A), que
   > **não existe ainda**. Prometer transmissão aqui seria vender o que não temos.

---

## Se algo falhar na apresentação

| Sintoma | Causa provável |
|---|---|
| Pedido não aparece na Fila | A custódia não foi transferida (passo 2) ou o CNPJ do login não é o da clínica |
| "Produzir laudo" não aparece | Nenhum item em `em_analise` — falta o passo 3.3. Se o laudo já foi liberado, é o esperado: o ciclo fechou |
| Erro ao produzir laudo citando paciente | O pedido não tem paciente identificado (ex.: emissão física com CPF sentinela) |
| Painel do laudo não avança | O poll é de 30s. Recarregar a página **não** perde o vínculo: a tela readota o laudo pelo backend |

---

*Roteiro validado de ponta a ponta em 2026-08-13 por `test_demo_lab_e2e.py`, atravessando três
telas e dois perfis.*
