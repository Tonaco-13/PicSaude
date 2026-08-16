# Continuidade — Arquiteto (Z) — PicSaúde

> Handoff para retomar em outro chat. Leia isto primeiro. Atualizado em 2026-08-14, fim do
> dia — série J em PRs + Render fechado pelo Fabiano.

---

## Quem é quem

- **Z (você):** arquiteto do PicSaúde. **Não escreve código de produção** — verifica no código o que o
  engenheiro entrega, dá parecer, segura invariantes, classifica mudanças (`core`/`module`/`docs`/`ops`,
  AGENTS.md §10). O martelo final em `core` é do Fabiano.
- **Engenheiro:** Claude Code no Terminal do Mac. Executa tickets/despachos, roda gates, **não
  commita** sem ordem, registra relatório em `docs/tickets/`.
- **Fabiano Tonaco:** líder/arquiteto-líder. Martelo em `core`. Dono do repo (privado, AGPL-3.0).
- **Caminho do repo:** `/Users/fabianotonaco/Developer/PicSaude_Dev` (no Terminal do engenheiro).
  O ambiente do arquiteto vê o mesmo repo em `/Volumes/fabianotonaco/Developer/PicSaude_Dev`
  (sandbox bind-mount) — **mesmos arquivos, só path diferente.**

## Estado atual (14/08, fim do dia) — SÉRIE J EM PRs · RENDER FECHADO

**Série J (ENG-010):** J.1/J.2/J.5 (core), J.3/J.6.b (module) implementados, gates verdes
(integração completa 466 · unit 436 · browser 68) e **revisados no código pelo arquiteto**
(`SESSAO-2026-08-14-PARECER-ARQUITETO-SERIE-J-REVISAO.md`). Em PRs abertos com CI verde:

| PR | Conteúdo | Estado |
|---|---|---|
| **#161** | `core` — J.1 (resultado_disponivel alcançável) + J.2 (hash canônico, 2 sítios) + J.5 (pedido_coletado) | OPEN, MERGEABLE, CI verde. **Merge AUTORIZADO pelo Fabiano (14/08 noite)** — engenheiro mergeia por squash. |
| **#162** | `module` — J.3 (re-login transparente em config.js, 4 módulos) + J.6.b (token distingue objeto) | OPEN, base no #161. Depois do merge do #161: rebase `--onto` + reapontar base para main. |

**J.4 adjudicado (c)+(a)** — score baixo = verdade (CNS sintético); AC revisto com errata do
arquiteto. **Parte do Render o Fabiano FEZ na mão (14/08 noite):**
- `/data/pix_saude_demo.db` criado via Shell (tabelas CNES + 2 farmácias demo) → `FileNotFoundError` morto.
  ⚠️ **Efêmero**: morre a cada redeploy; enquanto o micro-ticket durável não entra, re-rodar o
  snippet (está no histórico do chat de 14/08 e no §Render abaixo).
- `PICSAUDE_DEMO_ADMIN=true` no Environment → persona admin ("Demo Admin") **no ar** no `/demo/login` (ledger visível).
- Conferido: `PICSAUDE_JWT_TTL_MIN=480` · `PICSAUDE_JWT_SECRET` fixo presente · `PICSAUDE_DEMO_MODE=true`.
- Ctx: dados do demo vivem no PostgreSQL (persistem); o SQLite do demo serve SÓ à validação CNES.

## Próximos passos (ordem)

1. **Confirmar que o #161 foi mergeado** (Fabiano autorizou) e o #162 rebaseado/mergeado.
   Conferir: `gh pr view 161` e `gh pr view 162` (estado MERGED) + gates verdes na main.
2. **Reset manual da vitrine (SIGTAP)** — agora sim, pós-merge, via Shell do Render:
   `cd /app && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py --sim-eu-quero`
   (e re-rodar o snippet do SQLite CNES se houve redeploy entre a criação e o uso).
3. **Despachar J.7 + micro-ticket do CNES durável + J.8/J.9** — despacho ENG-011 a redigir:
   - J.7 (`core`): transferir-laboratorio não agenda (custódia ≠ agenda) — **martelo do Fabiano pendente** (parecer favorável do arquiteto).
   - J.4-companheiro (`ops`): predeploy cria o SQLite demo CNES (mata a efemeridade do /data).
   - J.8 (`module`): abas do laboratório (Recepção/Agendamento/Realização/Bancada).
   - J.9 (`module`): abas do cidadão (Receita/Exames/Atestado).
   - Linha do guia sobre score baixo (CNS sintético) — engenheiro já escreveu a linha, conferir.
4. **Docs não commitados:** pareceres série J + revisão + `Fabiano.md` + este arquivo estão na
   árvore (main) sem commit — decidir com o Fabiano quem commita (padrão: engenheiro sob ordem,
   junto do PR ou em commit docs separado).
5. Série J + J.7–J.9 resolvidas → **plano go-public** (`planejamento/GO-PUBLIC-PLANO.md`).

## Go-public — estacionado

Plano completo em **`planejamento/GO-PUBLIC-PLANO.md`**. Resumo:
- **Licença já AGPL-3.0** (+ licença comercial dupla + INPI + marca) — a angústia "sem grana/sem
  vendedor" já tem resposta no papel.
- **Distância real ~2–3 dias**, quase tudo é narrativa + curadoria + segurança.
- **Único gap real:** reframe do README de "prescrição digital" → "objetos sanitários + custódia
  cidadã" (prescrição como gancho). A demo laboratório é a prova da tese.
- Trilha GP-1..GP-4 (README reframe · curadoria showcase limpo · auditoria de segredos · fix
  contagens de teste). Gatilho: "Fabiano diz vamos ao deploy".

## Itens rastreados (não bloqueiam)

- **Série J estendida (14/08, bloco `Fabiano.md`):** J.7 (core · martelo pendente) —
  `transferir-laboratorio` agenda itens sem agendamento (custódia ≠ agenda); J.8 (module) —
  UI do laboratório em abas Recepção/Agendamento/Realização/Bancada; J.9 (module) — UI do
  cidadão em abas Receita/Exames/Atestado. Entra no despacho ENG-011 (não nos PRs #161/#162).
- **403 como sessão expirada** ainda em `registrarAgendamento*` e circulação (`clinica.html:1263,
  1359, 1652, 1681, 1700, 1725, 2383`) — mesma classe do J.3; tratar junto.
- **401 "Signature verification failed" isolado** na vitrine (14/08, não reproduzido) — vigilância
  no J.4 (possível secret/restart no deploy).
- Go-public trilha (acima).

## Referências rápidas

- Pareceres do arquiteto (13/08): `docs/tickets/SESSAO-2026-08-13-PARECER-ARQUITETO-{B-C, PACOTE-ADE, FGH}.md`
- Parecer do arquiteto (14/08, excursão + série J): `docs/tickets/SESSAO-2026-08-14-PARECER-ARQUITETO-EXCURSAO-VITRINE.md`
- Relatórios do engenheiro (13/08): `docs/tickets/SESSAO-2026-08-13-TICKET-{B-C, F, G, H, I, COMMITS}-DEMO-LAB.md`
- Plano + tickets da demo: `planejamento/demo-laboratorio-laudo-cidadao/` (`README.md`, `INICIO-AQUI.md`)
- Plano go-public: `planejamento/GO-PUBLIC-PLANO.md`
- Princípios: `AGENTS.md` (§10 taxonomia), `docs/NUCLEO_SANITARIO.md`

## Princípios que não podem esquecer

Objetos sanitários imutáveis após emissão · ledger INSERT-only · `encerrado_fisico ≠ cancelado` ·
CPF sentinela `'00000000000'` · adapter/transmissão externa **só com G4A** (§10) · diagnosticar
antes de agir (cruzar fontes; observar efeito ≠ observar causa).

---

*Handoff atualizado pelo arquiteto (Z) em 2026-08-14. Retome lendo isto + o parecer da série J (martelos J.1/J.2/J.5 pendentes).*
