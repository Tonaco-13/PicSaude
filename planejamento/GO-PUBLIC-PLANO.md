# Plano Go-Public (estacionado) — PicSaúde público no Git

> **Status:** ESTACIONADO em 2026-08-13. Retomar quando o Fabiano decidir o deploy/flip público.
> Origem: conversa de arquitetura (Z) com o Fabiano em 2026-08-13.
> **Não executar agora** — aguarda sinal. Prioridade do momento: fechar a demo laboratório.

---

## O objetivo (nas palavras do Fabiano)

Tornar o PicSaúde público no git (hoje privado). **Compartilhar os motores.** Sem caixa para abrir a
plataforma ao público, sem disposição para virar vendedor. A demo laboratório é o veículo.

## Decisões já tomadas

- **Licença:** **AGPL-3.0 já está** (`LICENSE` na raiz; badge + seção no `README.md`). Sem ação.
- **Fachada pública:** **curadoria / showcase limpo** (motor + docs oficiais + demo + README;
  ruído de processo fica privado ou em pasta marcada "internos").

## Recalibração honesta da distância (Z, 2026-08-13)

A fundamentação está **~90% pronta**: `LICENSE` (AGPL) + `COMMERCIAL-LICENSE.md` (licença dupla) +
`CONTRIBUTOR-LICENSE.md` (CLA) + `DISCLAIMER.md` + `ETHICS.md` + `DATA-PROTECTION.md` +
`CONTRIBUTING-EXTENSAO.md` + `README.md` com Quick Start de 5 min + **INPI registrado** (BR 51 2026
002267-3) + **marca depositada** (classes 9 e 44).

**Distância real: ~2–3 dias** quando retomarmos. Não é infra; é **narrativa + curadoria + segurança**.

### A angústia "sem grana / sem virar vendedor" já tem resposta no papel
**AGPL + licença comercial + marca/INPI** é exatamente o design pra isso: compartilha nos termos
dele (AGPL); quem quiser uso fechado vem até ele (comercial = receita passiva, não venda); ninguém
apropria o nome (marca). **Ele não precisa ser vendedor nem hospedar.** Reconhecer isso tira o peso.

---

## O ÚNICO gap real: narrativa (o maior alavanque)

O `README.md` vende PicSaúde como **"sistema de prescrição digital (RDC 1.000/2025, PAdES-B)"**. Mas
o motor virou maior: **infraestrutura de objetos sanitários com custódia cidadã** —
`docs/NUCLEO_SANITARIO.md`, prescrição **+ exame + laudo + custódia explícita do cidadão**. A joia
compartilhável é o **Núcleo / custódia cidadã**, e **nem aparece no README**.

**Fechamento:** a demo laboratório (laudo indo à custódia do cidadão) é a **prova exata** da tese
maior. O trabalho em curso é a evidência do repositioning.

**Recomendação:** reframe do README — **prescrição/RDC 1.000 como ganho de porta** (concreto,
pesquisável, regulado) + **custódia cidadã / Núcleo Sanitário como tese profunda**.

---

## Trilha "go-public" (4 tickets, executar ao retomar)

| # | Ticket | Classe | Resumo |
|---|---|---|---|
| **GP-1** | Reframe do README | docs | De "app de prescrição" → "plataforma de objetos sanitários com custódia cidadã" (prescrição como gancho). Maior alavanque. Citar `NUCLEO_SANITARIO.md` e a demo laboratório como prova. |
| **GP-2** | Curadoria da fachada (showcase limpo) | ops/docs | Excluir da fachada: `inbox/`, `.zcode/`, `planejamento/` (working docs), `docs/tickets/` (despachos/pareceres). Decidir histórico (ver abaixo). |
| **GP-3** | Auditoria de segredos/PII no histórico | ops/segurança | **Não-negociável antes do flip.** Varrer: chaves, `.env`, CPFs reais, tokens, credenciais demo. Confirmar `seed_demo.py` 100% sintético. |
| **GP-4** | Hygiene do README | docs | Contagens de teste inconsistentes (badge 1267 × stack 146 × real 326/419/61) — unificar e atualizar. Reframe "deploy público em preparação" / "GIF após deploy" → "rode local em 5 min" como história primária (não precisa de host). |

### Decisão pendente (só do Fabiano) — histórico
- **Histórico cheio + árvore curada** (recomendado se GP-3 passar limpo): a jornada de engenharia é
  crédito/rigor; só não linkar os internos pelo README.
- **Histórico limpo** (`git filter-repo` ou repo novo com commit inicial curado): fachada impecável,
  mais trabalho, arrisca deixar segredo pra trás se GP-3 for fraca.
- Como o repo ainda é **privado**, há luxo de escolha.

---

## Estado da demo laboratório (contexto para o retomar)

- **Pronto e verificado:** B, C (`core`), A, D, E + fix `test_4d2`.
- **Dia 2 pronto e verificado:** F, G, H + fix da vitrine (500 no faturamento).
- **Em curso (engenheiro):** pacote I de polimento — I.1 patient-gap (+ laudo-exists), I.2 seletor
  TUSS/SIGTAP, I.3 `codigo_sigtap` no seed, I.4 403 não derruba sessão, I.5 time-bomb do
  `test_regras_receituario`.
- **Após I verde:** commits — PR 1 (`core` C, isolado, martelo do Fabiano) + PR 2 (resto da demo).
- Ver despacho: `docs/tickets/SESSAO-2026-08-13-PARECER-ARQUITETO-FGH.md`.

---

## Gatilho para retomar

Quando o Fabiano disser "vamos ao deploy/go-public": abrir GP-1 a GP-4 (2–3 dias, R$0, sem venda).
O momento natural é **após a demo laboratório commitada** — ela é a prova da tese para o README.

---

*Plano estacionado pelo arquiteto (Z AI) em 2026-08-13. Retomar mediante sinal do Fabiano.*
