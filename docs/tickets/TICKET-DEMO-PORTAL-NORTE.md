# TICKET-DEMO-PORTAL-NORTE — cartão "Farmácia Norte" no portal demo (destrava o Ato 6)

| Campo | Valor |
|---|---|
| **Classe** | `local-extension` / demo-infra — **não toca semântica clínica** (login demo + portal). |
| **Prioridade** | **Backlog / v2 do roteiro (rebaixado 2026-07-12).** Fabiano decidiu rodar a demo com **uma única farmácia (Central)** — o Ato 6 foi cortado da demo apresentada. Este ticket deixa de ser pré-vitrine; vira a emenda **opcional** que traz o isolamento de volta como cena ao vivo quando o público (ex.: setor público/regulador) justificar. Não bloqueia nada. |
| **Para** | code/MS |
| **Origem** | Ensaio de montagem da Fatia B (2026-07-11): o modo demo bloqueia `/auth/token` (403 "Login real desabilitado") e o portal demo só oferece o cartão da Central → **não há como chegar na Farmácia Norte pelo navegador**. Descompasso entre o roteiro (assumia re-login por CNPJ) e a trava do modo demo. |
| **Correção do arquiteto** | A decisão §0.1 ("sem seletor, re-login por CNPJ") tinha premissa errada — demo-mode não permite login real. A mecânica correta e fiel é um **cartão no portal**, não um seletor dentro do app do dispensador (aquele segue rejeitado). |

## Objetivo

O portal demo (`/`) passa a oferecer **dois cartões de dispensador**: **Farmácia Central**
(`99999999000191`, já existe) e **Farmácia Norte** (`99999999000272`). Clicar em cada um entra em modo
demo **como aquela farmácia** (sem senha), com JWT **escopado ao CNPJ correspondente**.

Isso torna o **Ato 6 apresentável**: o visitante clica Norte, abre o relatório, vê **vazio** — a prova
viva do isolamento por CNPJ, sem console, sem digitar credencial.

## Escopo

1. **Demo-login já suporta a Norte** — verificado no ensaio: `POST /demo/login {role:'dispensador_norte'}`
   emite JWT com `sub` = CNPJ da Norte. **Backend pronto; nada a fazer aqui** (confirmar apenas que o
   role está estável e escopado). O ticket é, na prática, só o item 2.
2. **Portal (`/`) mostra o cartão da Norte** ao lado do da Central (mesmo componente/estilo), chamando
   `role:'dispensador_norte'` no clique — o mesmo caminho da linha de console do ensaio, agora como
   botão pedagógico. É o grosso (e talvez a totalidade) do trabalho.
3. **Invariante preservado:** o JWT da Norte é escopado ao CNPJ da Norte → o relatório da Norte já
   volta 0 linhas (confirmado na API no ensaio). Nenhuma mudança na lógica de relatório/escopo — só o
   caminho de entrada.

## Fora de escopo

- Login real por CNPJ+senha em modo demo (continua **bloqueado** — trava de segurança proposital).
- Seletor de troca **dentro** do app do dispensador (rejeitado; a troca é pelo portal).
- Qualquer mudança na Fatia B ou na lógica clínica.

## Critérios de aceite

1. Portal demo exibe cartões **Central** e **Norte**; clicar em cada um entra logado como a farmácia
   certa (CNPJ no `sub` do JWT).
2. Logado como Norte, `GET /dispensadores/relatorio.csv` volta **0 linhas** (isolamento) — Ato 6 roda
   no navegador, sem console.
3. Nenhuma regressão no login da Central nem na trava do `/auth/token` real em modo demo.
4. `seed_demo.py` mantém Norte **vazia** (estado do roteiro).

## Nota de processo (LEARNINGS candidata)

Ao escrever roteiro/UX que dependa de autenticação, **verificar as travas do modo demo** — o que vale
no login real (CNPJ+senha) pode estar bloqueado na vitrine. O ensaio de montagem é onde esse tipo de
descompasso aparece; registrar como achado, corrigir a spec, não improvisar na apresentação.
