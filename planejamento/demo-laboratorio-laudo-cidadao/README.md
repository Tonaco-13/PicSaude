# Demo Laboratório — Laudo Cidadão + Bancada Leve

> Plano de execução em tickets para o engenheiro (Claude Code no Terminal).
> Origem: sessão de arquitetura com o Fabiano Tonaco em 2026-08-13.
> Janela: 13–14 de agosto de 2026 (hoje/amanhã).

---

## A visão (uma frase)

O laboratório **opera a trilha sanitária** do exame (recebe custódia → agenda → coleta →
**bancada** → **produz laudo** → **libera ao cidadão**); o laudo clínico fica em **custódia do
cidadão**; o laboratório retém apenas **rastro forense + mínimo legal**. Leveza, auditabilidade,
rastreabilidade.

## O contrato da demo (decisões validadas)

| # | Decisão | Detalhe |
|---|---|---|
| 1 | Laudo estruturado completo no `clinica.html` | Produzir (itens: conclusão/valor-referência/resumo) → assinar → liberar ao cidadão → ver ciência. Substitui o prompt livre. |
| 2 | Política formal de custódia clínica do cidadão | Doc declarando: laudo clínico = cidadão; rastro + mínimo legal = lab (RDC 302/CFM/LGPD). |
| 3 | Três fontes pagadoras | Particular (ciclo completo) + agregação TUSS + agregação SIGTAP. Sem transmissão a operadora/SUS (G4A). |
| 4 | Gesto "Enviar à bancada" | Transição `coletado → em_analise` com evento leve (setor). Sem virar LIMS. |
| 5 | RBAC core aprovado | Dispensador (CNPJ) produz/assina/libera o laudo **declarando o CNS do RT**; RT continua sendo `autor_id`. Ownership via **custódia do pedido vinculado** (sem nova coluna). |

## Escopo — o que NÃO muda (já está pronto)

- **Lado cidadão, ponta a ponta:** `cidadao.html` já tem carteira de laudos
  (`carregarLaudos`/`renderizarLaudos`/`darCienciaLaudo`/`baixarPdfLaudo` — linhas 693–756);
  backend `GET /paciente/laudos` (`backend/app/routers/auth.py:512`);
  Lente de Auditoria lê laudos (`index.html:695`). **Zero trabalho do lado do cidadão.**
- Backend do laudo **completo** (`backend/app/routers/laudos.py`).
- Custódia cidadão→lab, agendamento, coleta, circulação diagnóstica — operacionais.

## Tickets (execute nesta ordem)

| Ordem | Ticket | Classe | Depende de | Resumo |
|---|---|---|---|---|
| 1 | `01-contexto-visao-decisoes.md` | (leitura) | — | Contexto compartilhado. **Leia antes de qualquer ticket.** |
| 2 | `TICKET-A-politica-custodia-clinica.md` | `docs` | — | Doc da política de custódia clínica do laudo. |
| 3 | `TICKET-B-endpoint-bancada.md` | `module` | — | `POST .../itens/{id}/em-analise` (materializa o estado `em_analise`). |
| 4 | `TICKET-C-rbac-laudo-dispensador.md` | `core` ⚠️ | — | Estende laudo ao dispensador (RT declarado; ownership via pedido). **Núcleo — exige cuidado e testes.** |
| 5 | `TICKET-D-faturamento-tuss-sigtap.md` | `module` | — | `agrupar_por=tuss\|sigtap` nos endpoints de faturamento. |
| 6 | `TICKET-E-arquitetura-laudo-update.md` | `docs` | C | Documenta o modelo dispensador-produz-sob-RT + bancada. |
| 7 | `TICKET-F-frontend-bancada.md` | `module` | B | Gesto "Enviar à bancada" no `clinica.html`. |
| 8 | `TICKET-G-frontend-laudo-ui.md` | `module` | C | UI de laudo estruturado no `clinica.html` (pedra angular). |
| 9 | `TICKET-H-demo-e2e.md` | `ops`/test | A–G | Roteiro end-to-end da demo + checagem com `web-gui-tester`. |

> **Dia 1 (backend + docs):** A, B, C, D, E.
> **Dia 2 (frontend + demo):** F, G, H.

## Guardrails obrigatórios (AGENTS.md)

- **`core` (Ticket C):** RBAC é núcleo. Aprovação central já concedida pelo arquiteto (Fabiano).
  Testes de ownership são **obrigatórios** — unidade A não pode operar laudo da unidade B.
- **Imutabilidade:** ledger (`*_eventos`) nunca recebe UPDATE/DELETE. Objetos sanitários emitidos
  não são editados (geram derivados).
- **Nenhum adapter / transmissão externa:** TUSS/SIGTAP são agregação **interna**. Guia TISS/APAC
  depende de G4A (AGENTS.md §10) — **não implementar**.
- **Sem schema change:** o Ticket C usa custódia do pedido (dado existente). **Não criar coluna nova.**
- **Estados:** nenhum estado novo. `em_analise` já existe no contrato (`states_exame.py:88`).

## Como executar (sugestão de fluxo para o Claude Code)

1. Criar branch: `feat/demo-lab-laudo-cidadao` a partir de `docs/sessoes-11-12-agosto` (ou `main`).
2. Ler `01-contexto-visao-decisoes.md`.
3. Executar os tickets na ordem acima; rodar `pytest` após cada ticket de backend.
4. Ao final, executar `TICKET-H` (roteiro + `web-gui-tester`).

## Referências rápidas de arquivos

| Área | Arquivo | Âncoras |
|---|---|---|
| Estados exame | `backend/app/domain/states_exame.py` | ESTADOS_ITEM `:88`, TRANSICOES_ITEM `:115`, EVENTOS `:128` (`pedido_em_analise` `:134`) |
| Estados laudo | `backend/app/domain/states_laudo.py` | ESTADOS `:51`, TRANSICOES `:75`, EVENTOS `:119` |
| Router laudo | `backend/app/routers/laudos.py` | criar `:317`, get `:538`, assinar `:591`, liberar `:651`, encerrar `:819`, cancelar `:866`, pdf `:931`, helpers ownership `:212-275` |
| Router pedidos | `backend/app/routers/pedidos_exame.py` | coletar `:960`, resultado `:1123` (aceita `:1176`, update `:1201`) |
| Router clínicas | `backend/app/routers/clinicas.py` | SQL faturamento `:227`, agregar `:247`, endpoints `:361/:395` |
| Model item exame | `backend/app/models/pedido_exame_item.py` | codigo_tuss `:25`, codigo_sigtap `:26` |
| Frontend clínica | `clinica.html` | renderizarItens `:1620`, registrarColeta `:1669`, authHeaders `:763`, header `:537` |
| Frontend cidadão | `cidadao.html` | carteira de laudos `:693-756` (já pronto) |
