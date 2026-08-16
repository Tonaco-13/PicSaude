# INÍCIO AQUI — Engenheiro

> Ponto único de orientação. Leia isto antes de qualquer ticket.

Você é o Engenheiro do PicSaúde. Repo: `/Volumes/fabianotonaco/Developer/PicSaude_Dev`
Branch: `docs/sessoes-11-12-agosto` (**NÃO** commit/push — trabalho na árvore).

## Onde está seu plano

```
planejamento/demo-laboratorio-laudo-cidadao/
  README.md                          ← índice + ordem de execução
  01-contexto-visao-decisoes.md      ← LEIA ANTES de qualquer ticket (visão, RBAC, princípios)
  TICKET-F-frontend-bancada.md
  TICKET-G-frontend-laudo-ui.md
  TICKET-H-demo-e2e.md
```

## O que fazer, em ordem, um por vez

1. **Ticket F** — gesto "Enviar à bancada" no `clinica.html`.
2. **Ticket G** — UI de laudo estruturado (pedra angular); depende de F.
3. **Ticket H** — demo E2E + `web-gui-tester`; depende de F e G.

**Já feito (não refazer):** Tickets B, C, A, D, E + fix do `test_4d2`. O backend do laudo e o
endpoint `/em-analise` estão prontos e aprovados.

## Padrão de qualidade + formato de relatório

`docs/tickets/SESSAO-2026-08-13-TICKETS-B-C-DEMO-LAB.md` — use o MESMO formato (tabela de cabeçalho,
seções, arquivos alterados, gates com contagens, achados, estado, próximos passos).

## Disciplina (não negociável)

- **Gates verdes:** rode o `-k` da CI (`.github/workflows/gates.yml:101`) **mais** os smokes de
  browser (`tests/browser`) — `clinica.html` está no path do `gates-browser`.
- **Relatório ao fim de cada ticket:** `docs/tickets/SESSAO-2026-08-1{3,4}-TICKET-{F,G,H}-DEMO-LAB.md`.
- **Em dúvida, gate vermelho ou teste que não casa com o `-k`:** NÃO chute — registre o bloqueio no
  relatório e **pare**. Escalar para o arquiteto é melhor que entregar às cegas.
- **Sem commit/push** sem ordem expressa.
