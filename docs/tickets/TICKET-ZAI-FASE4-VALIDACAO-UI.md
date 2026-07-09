# TICKET-ZAI-FASE4 — Validação UI↔invariante do ciclo mínimo (Fase 4)

| Campo | Valor |
|---|---|
| **Para** | Z AI (revisor de integração — UX/DX, UI↔invariante) |
| **Classe** | `validação` (não escreve código de produto; valida o frontend contra os contratos do backend) |
| **Origem** | Fase 2 backend fechada (PR #84) + auditoria Jules (`JULES-AUDIT-PR84.md`) |
| **Pré-requisito** | PR #84 mergeado **e** frontend da Fase 4 construído (`dispensador.html`, ciclo mínimo) |
| **Quando** | Assim que a Fase 4 (frontend) começar — antes do teste manual do Fabiano |

## §1 Contexto (não reabrir)

Backend do ciclo está pronto e verificado (289 verdes PG): estorno objeto-derivado (T2), trigger Σ (T3), detenção prévia/auto-retenção (T1.5), demo Norte (T0.6), comprador no comprovante (T5), histórico (T6), CNES demo (T0.5b). A auditoria Jules do PR #84 confirmou os contratos de backend (auth no comprovante, minimização LGPD do comprador, determinismo). **Este ticket é só a camada de UI.**

**Ciclo mínimo a validar:** login demo → retenção → dispensar parcial → estornar → comprovante com comprador → histórico.

## §2 Mandato do Z AI

Validar que **cada invariante do backend tem correspondência visível e correta na UI**, e que **erro do backend renderiza legível** (nunca `[object Object]`, nunca tela branca). Não é revisão de código de produto — é UI↔invariante ponta-a-ponta.

## §3 Escopo de validação (checklist)

| # | O que validar | Contrato de backend |
|---|---|---|
| 1 | **Demo já logada** como Farmácia Demo, **sem modal manual de CNES** (cnes_verificado=true após T0.5b) | `POST /demo/login {role:'dispensador'}` + `GET /auth/me/institucional` → `cnes_verificado:true` |
| 2 | **Retenção com feedback visual** — banner de retenção + linha aparecendo na fila (a auto-retenção emite `custodia_transferida`; a UI deve refletir a posse) | `GET /dispensadores/fila` |
| 3 | **409 `item_nao_retido` renderiza legível** (responsabilidade explícita do Z AI) — só ocorre em produção; em demo há auto-retenção. Testar a mensagem `detail.mensagem`, não o objeto cru | `POST .../dispensar` → 409 `{codigo, mensagem}` |
| 4 | **Dispensar parcial** — saldo atualiza na fila (Σ efetivo) | `POST .../dispensar` → `saldo_restante` |
| 5 | **Estornar** — saldo **reposto** visível e item volta a ser dispensável; botão "desfazer baixa" chama o endpoint real | `POST /dispensacoes/{id}/estornar` → `saldo_restante` reposto |
| 6 | **Comprovante COMPRADOR × PACIENTE** — mostra os dois; **LGPD: só nome + documento do comprador, NUNCA endereço**; exige auth do dispensador (sem exposição pública) | `GET /dispensacoes/{id}/comprovante` (JSON/PDF), campo `comprador.{nome,documento,eh_paciente}` |
| 7 | **Histórico de retenções** — lista com `dispensacao_id` (linka comprovante/estorno), comprador e estado de estorno; ordem estável entre recarregamentos (determinismo) | `GET /dispensadores/historico` |

## §4 Achados do Jules relevantes ao Z AI

- **LGPD (minimização):** o backend só grava `comprador_nome` + `comprador_documento` (sem endereço). A UI **não pode** coletar nem exibir mais que isso no comprador. Confirmar no formulário do balcão e no comprovante.
- **Auth multi-role no comprovante:** dispensador é validado por CNPJ; a UI deve enviar o token do dispensador logado (não expor o comprovante sem auth).

## §5 Fora de escopo

- Fluxo hospitalar / IA farmacêutica / token de circulação (não são o ciclo mínimo).
- Devolução ao prescritor no balcão (decisão de produto pendente — não está no ciclo mínimo).
- Relatório consolidado de impressão e CSV SNGPC completo (cortados desta semana; T8 entrega só o botão que liga no endpoint existente).

## §6 Definição de "feito"

- Os 7 itens do §3 validados no navegador (janela anônima), cada erro do backend renderizando legível.
- Parecer do Z AI no PR da Fase 4 (verde / verde-com-notas / bloqueado).
- Só então: teste manual humano do Fabiano.

---

> **Nota de reconciliação (para o Conselheiro/code, não para o Z AI):** a sessão
> do Jules (`jules_session_5721862461686869013`) trouxe 2 melhorias reais **fora**
> do PR #84, numa branch que diverge (sem o T5): (a) `custodia.py:827` — desempate
> `, id DESC` no `ORDER BY` da recuperação do `_cnes_val` (aplicou o check de
> Determinismo a uma query que o T6 não tocou); (b) `CLAUDE.md §10` — padrão
> "estados computados não persistidos". **Puxar ambas para main** antes de fechar
> a Fase 2 (não bloqueia o Z AI).
