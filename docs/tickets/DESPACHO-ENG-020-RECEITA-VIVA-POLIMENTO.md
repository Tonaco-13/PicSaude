# DESPACHO-ENG-020 — Receita Viva onda 1.1: o polimento que devolve a alma visual

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 21/09/2026 — origem: martelo do Fabiano ("o design não ficou igual") + parecer Kimi (uso real) + auditoria visual do arquiteto |
| **Classe** | `module` — frontend apenas (`receituario.css`, `receituario.js`, `prescritor.html`); **zero backend, zero CSV** |
| **Lei** | `DESENHO-RECEITA-VIVA.md` + **este despacho, que é o ADENDO ESTÉTICO NORMATIVO que faltou no ENG-018** — o protótipo (`conceitos-prescritor/` + capturas) passa a ser referência normativa para os itens §2 abaixo |
| **Momento de colar** | **APÓS a ENG-019 pousar** — a árvore está com a posologia em andamento |
| **Entrega** | 1 PR, ACs mapeados no corpo |

---

## §1 Três consertos pontuais (evidenciados)

1. **Plural da unidade** (achado Kimi §4.1, uso real): a folha rende "30
   comprimido". Correção no `_item` do `receituario.js` — **uma correção, três
   superfícies curadas** (folha viva, print-area, 2ª via). É o gesto que demonstra
   a martelada ② pagando.
2. **Placeholder truncado**: "DDD + Númer…" no campo de telefone (auditoria visual
   do arquiteto). Ou o campo alarga, ou o placeholder encurta honesto.
3. **O bloco gov.br Nuvem sai da vitrine (por ora)** — martelo do Fabiano 21/09
   (*"a assinatura gov saiu também do frontend… para deixar a vitrine limpa"*, ao
   confirmar a ausência de despacho): o cartão "Emissão Digital — Assinatura
   gov.br (Nuvem)" com o botão ☁️ e a promessa "disponível em breve" **sai do
   `prescritor.html` renderizado**. **Escopo cirúrgico:** (a) só a APRESENTAÇÃO —
   o modo `gov_br_nuvem` no domínio (`domain/assinatura.py`), endpoints e ledger
   ficam intocados; (b) o link "🪪 Meu certificado ICP-Brasil" **fica** (tem modal
   funcional — o stub MVP de assinatura registrado); (c) a volta do bloco é o
   dia do **Ticket 21** (assinatura digital real). AC: guarda estática — nenhuma
   promessa "gov.br"/"em breve" no HTML servido do prescritor.

## §2 Adendo estético NORMATIVO — o protótipo vira lei nestes seis itens

> **Adjudicação de escopo (arquiteto):** o tratamento de "mesa de papel" aplica-se
> ao **PALCO do documento** (`.receita-palco` e a folha), não à pele inteira do
> app — o restante do prescritor mantém a skin da casa. A metáfora mora onde o
> papel está; reversível e contida.

| # | AC | Especificação normativa (referência: `conceitos-prescritor/capturas/03-desktop-pena-e-papel.png`) |
|---|---|---|
| A1 | **Palco creme** | O palco do documento em creme quente (~`#F7F5EF`), não cinza frio — a mesa onde o papel assenta |
| A2 | **Tipografia dual** | O DOCUMENTO em serif editorial (título "Receituário Médico" e corpo do documento); a UI (formulário, painéis) permanece sans. O W≡Y compara texto — a troca de família é cromo de modo, mas o CONTEÚDO continua nascendo só do estado |
| A3 | **Papel de verdade** | Folha com borda quente (~`#D9D2C0`), sombra de papel, canto levemente arredondado — lê-se "folha", não "card de dashboard" |
| A4 | **Selo de custódia pós-emissão** | Após emitir, a folha recebe o selo verde **"TRANSMITIDA · CUSTÓDIA AO PACIENTE"** com rotação ~-8° (como no protótipo). **É conteúdo do ESTADO emitido, não cromo de modo** — nasce no carimbo e vale nos dois alvos (W≡Y intocado); no rascunho não existe (ainda não houve transmissão) |
| A5 | **Lacuna legível** | O pontilhado existe (Kimi viu em runtime) mas está tímido: linha pontilhada com contraste suficiente para ler-se como "o branco esperando a caneta" — convite, não sussurro |
| A6 | **Proporções** | Painel do papel com ≥ ~40% da largura em 1366px+; a pena (formulário + painéis de IA/semáforo) segue legível — estende o AC5 original, agora com número |

**Invariantes que permanecem intocados:** W≡Y verde (nenhuma regra CSS esconde
conteúdo por modo — a cláusula do `receituario.css` segue); caixa-alta do fármaco
na função, nunca em `text-transform`; M-D/A2; carimbo sem navegação; fluxo físico.

## §3 Flag de decisão (não bloqueia a PR)

**Conselho da Dra. Demo** (achado Kimi §4.2): o emitente demo mostra lacuna
"registro profissional" — honesto, mas estranho na vitrine. Se o Fabiano disser
sim, o seed ganha um conselho fictício no padrão demo (ex.: "CRM-PE 00000-DEMO") —
gesto `curadoria`/seed que pode viajar nesta PR ou na seguinte.

## §4 Rito

1 PR; AC×teste×arquivo no corpo (A1–A6 testáveis: tokens de cor, família de fonte
aplicada ao alvo certo, presença+rotação do selo pós-emissão com W≡Y verde,
contraste da lacuna, proporção mínima); vermelho-antes-do-verde nas guardas novas;
suítes completas; CI `gates`+`smokes`; merge só com **RATIFICADO do arquiteto +
martelo do Fabiano**.

---

*Lavrado em 21/09/2026. A onda 1 cumpriu a promessa mecânica; esta devolve a
promessa visual. O papel volta a parecer papel — e o selo de custódia passa a
nomear, na tela, o momento em que a posse nasce.*
