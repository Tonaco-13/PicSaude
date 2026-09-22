# DESPACHO-ENG-019 — Posologia por condição: a chave composta `(ativo, CID)`

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 21/09/2026 — martelo do Fabiano: *"vamos à posologia"* |
| **Classe** | `module` — `posologia_sugerida.py` + CSVs + request do endpoint; **semáforo intocado** |
| **Lei do ticket** | `docs/tickets/DESENHO-POSOLOGIA-POR-CONDICAO.md` (desenho do arquiteto, 13/09, sobre O SEU achado do fecho #263) — **viaja nesta PR** (commit o arquivo) |
| **Entrega** | 1 PR, ACs mapeados no corpo, canetas citadas |

---

## §1 O defeito — você mesmo o nomeou

*"`carregar_posologias` chaveia por princípio ativo, não por (ativo, CID). Nove das
minhas rows sobrescreveriam em silêncio a dose de HAS, asma e DM2 pela de IC e DPOC.
Retirei as nove e deixei guarda para a próxima falhar alto. O conserto real é module —
fica como ticket seu."* (fecho de 13/09). O índice é `dict[ativo_canônico → Posologia]`
(`backend/app/domain/posologia_sugerida.py:53`) — **a última row do CSV vence, em
silêncio**. Carvedilol na IC começando em 3,125 mg não pode calar por cima da dose de
HAS: é erro clínico silencioso.

## §2 O conserto (desenho §2, ratificado)

1. **Chave composta**: índice passa a `dict[(ativo_canônico, codigo_cid) → Posologia]`.
   O CSV **já tem a coluna `codigo_cid`** — o dado está pronto, é o índice que ignora.
2. **Busca com cadeia**: `POST /ia/posologia/sugerir` (`backend/app/routers/ia.py:592`)
   passa a receber o **CID da prescrição em curso** e sobe a mesma hierarquia do
   semáforo (`cadeia_cid`): `(ativo, I50.0)` → `(ativo, I50)` → bloco `(I10–I15)` se um
   dia existir → **sem sugestão** (degrada seguro, como hoje).
3. **Sem CID na request**: fallback ao comportamento atual **somente se o ativo é
   unívoco**; colisão sem CID = **silêncio + log** — nunca "última vence".
4. **As 9 rows exiladas voltam** (I50/J44) na MESMA PR, agora sob a chave certa — é a
   conclusão da sua própria retirada de 13/09.
5. **Proveniência**: a ficha de explicabilidade já carrega `condicao`; passa a carregar
   também **o CID casado** — transparência de qual condição fundamentou a dose.

**Frontend:** o request passa a levar o CID pelo **mesmo hidden input canônico do
typeahead** (`prescricao-cid-escolhido` — o eco do AC6 do ENG-018). Retrocompat
preservada quando o CID não vem (regra 3).

## §3 ACs (5 do desenho + 2 deste despacho)

| # | AC | Proveniência |
|---|---|---|
| 1 | Colisão (mesmo ativo, CIDs distintos) → **duas sugestões vivas**, cada uma casada pelo CID da prescrição; nenhuma sobrescrita silenciosa — **a guarda fail-loud que você deixou no ar vira o teste verde-após-o-fix** | desenho §3.1 |
| 2 | Sem CID + ativo unívoco → sugestão (retrocompat); sem CID + colisão → **silêncio + log**, nunca última-vence | §3.2 |
| 3 | Hierarquia respeitada (subcategoria cai na categoria) | §3.3 |
| 4 | **As 9 rows de I50/J44 de volta, com suas citações** — e **as doses de F41** (clonazepam 2–4 mg, clomipramina 100–150 mg — levantura F41 v2, #264/#266) como rows novas sob a chave composta | §3.4 + fila corrente 13/09 |
| 5 | Suíte de browser que usa posologia: **verde sem adaptação de roteiro** — o gesto na tela não muda; quem muda é o acerto do motor | §3.5 |
| 6 | Ficha de explicabilidade carrega o **CID casado** junto de `condicao` | desenho §2.5 |
| 7 | **CSVs: SÓ as 9 + as doses F41** — nenhum outro dado curado se mexe nesta PR (os flips da pilha do intensivo são PRs de curadoria futuras) | deste despacho |

## §4 Escopo e intocáveis

- Semáforo, ledger, custódia, estados: **intocados**. Nenhum endpoint novo — o
  `/posologia/sugerir` ganha o parâmetro opcional `codigo_cid`.
- A carga das demais condições (E78, F17, R52, M81, G40, L20, A30, G30, IST — os 10
  rascunhos na pilha) **NÃO entra aqui**: essa é curadoria com caneta, PR própria.
- Isto é o **destravador P-9**: metotrexato L20×L40, ciprofloxacino N39.0×IST,
  metronidazol A59×N76.0 dependem desta chave para flipar depois.

## §5 Rito

1 PR; corpo com AC×teste×arquivo + as canetas citadas: **13/09 verbatim "Merge e
canetas autorizados"** (base do retorno das 9 rows) e a **caneta F41 (#266)** (base das
doses). Vermelho-antes-do-verde: reintroduzir o last-wins tem que REPROVAR (a sabotagem
da guarda); suítes completas (unit + browser — baseline novo, pós-#268); CI
`gates`+`smokes`. Merge só com **RATIFICADO do arquiteto + martelo do Fabiano**.

---

*Despacho lavrado em 21/09/2026, no lugar da mensagem de 13/09 que nunca foi colada —
o desenho é o mesmo; o terreno andou (F41 flipada, baseline pós-#268) e está refletido
aqui. Uma função, uma chave, zero erro clínico calado.*
