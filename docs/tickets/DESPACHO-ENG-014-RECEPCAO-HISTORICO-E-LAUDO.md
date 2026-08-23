# DESPACHO ENG-014 — recepção, histórico e laudo×item (série pós-J)

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) |
| **Emitido** | 2026-08-20, via chat do arquiteto |
| **Registro** | Transcrito do chat pelo próprio autor em 23/08, com o adendo v2 de 22/08 (frente 1) |
| **Origem** | Propostas do Fabiano em 20/08 (pós-passeio na vitrine) + análise do arquiteto |
| **Execução** | #175/#176/#177/#178/#179 — série encerrada |

---

## Martelos do Fabiano (20/08, chat do arquiteto — aprovados com "Estou de
acordo com sua recomendação" → "Aprovado")

- **(a) "Abrir o laudo = dar ciência"** — o evento nomeia a ABERTURA (fato
  real); a ciência é consequência DERIVADA, declarada como regra.
- **(b) "Faturamento ancorado na liberação"** — leitura é coluna informativa
  de relatório/histórico, **nunca gatilho** de faturamento.

## PR A [module] — RECEPTÃO DA CLÍNICA

- clinica.html, do cartão da fila: "Agendar" (POST /agendamentos),
  "Executar agora" (coleta direta, martelo J.7), "Executar agendado"
  (POST /agendamentos/{p}/realizar — sem janela de horário).
- **GUARD obrigatório no mesmo PR:** POST /agendamentos com escopo por item
  sob custódia — até então agendava TODOS os pendentes do pedido, inclusive
  itens que a unidade não detém (mesma família do anti-vazamento AC vi do
  J.10; achado da análise do arquiteto). Default = os detidos; item alheio → 403.
- Contrato do cidadão INTOCADO: custódia segue fonte da posse; o selo
  "Agendado" do cartão reage sozinho (provado na vitrine em 20/08).

## PR B [module] — ABA HISTÓRICO (clinica.html)

Read-only: itens concluídos da unidade, laudos liberados, projeção de
custódia/ledger — mesma fonte do relatório. Subir sem o selo "Lido"; o selo
entra com o PR C.

## PR C [module] — LAUDO × POSSE POR ITEM + CIÊNCIA DA ABERTURA

- Conforme `docs/tickets/DESENHO-LAUDO-POSSE-POR-ITEM-E-ABERTURA.md`.
  ACs (i)–(vii) do §8 do desenho.
- Sinalizados: evento novo no vocabulário (governança ARQUITETURA_LAUDO +
  AGENTS §7) e migração da coluna `aberto_em` nos dois dialetos.

## Adendo (22/08) — frente 1, decisão v2 após §3-stop do engenheiro

O §2 v1 presupunha elo `laudo_item → pedido_item` inexistente (errata do
arquiteto registrada no desenho). Decisão: **o elo de verdade com a leitura
fraca como ponte registrada** — `laudo_itens.pedido_item_id` (migração nos
dois dialetos, nullable, sem backfill), criação por dispensador exige o elo,
legados operáveis pelo predicado grossa do #172 (`dispensador_tem_algo_no_pedido`).
ACs (viii)–(x) acrescentadas.

**Ordem:** A e B independentes; C após ler o desenho. Gates completos + E2E.

---

*Despacho emitido pelo arquiteto (Z) em 20/08; adendo v2 em 22/08; registro
durável em 23/08.*
