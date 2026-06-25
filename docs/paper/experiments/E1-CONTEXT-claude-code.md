# Contexto para o Claude Code (VS Code) — rodar o experimento E1 full-stack

> Cole este arquivo (ou aponte para ele) ao iniciar a sessão no Claude Code.
> Você é o **Engenheiro-executor**. Sua missão: implementar e **rodar** o experimento E1
> autoritativo (full-stack) e produzir os números que entram na Seção IV do paper do CBEB.

---

## 1. Missão em uma linha

Elevar o E1 *preliminar de nível-domínio* (já rodado) à execução **full-stack** sobre o sistema real, medindo as propriedades de auditabilidade por construção, e entregar tabela + JSON reprodutíveis.

## 2. Leia primeiro, nesta ordem

1. `docs/paper/experiments/E1-PLANO-EXPERIMENTAL.md` — o protocolo passo a passo (Fases 0–5). **É a sua especificação.**
2. `docs/paper/experiments/E1-HANDOFF-claude-codex-jules.md` — divisão de papéis e o que NÃO fazer.
3. `docs/paper/NARRATIVA-CANONICA-PICSAUDE.md` — vocabulário canônico e guardas de honestidade (o que o paper pode/não pode afirmar).
4. `CLAUDE.md` §1–§6 (invariantes: imutabilidade, ledger, custódia, dispensação parcial) e §10 (taxonomia de contribuição).
5. Base de apoio já existente: `docs/paper/experiments/e1_auditability.py` + `e1_results.json` (preliminar); `backend/app/domain/states.py`; `backend/app/domain/documento_canonico.py`.

## 3. O que construir e rodar

Siga as Fases 0–5 do plano. Em resumo:

- **Fase 0** — Postgres efêmero + schema + `DEMO_MODE` + semente fixa; baseline limpo.
- **Fase 1** — gerar corpus (N≥1.000, alvo 5.000) **somente via** `POST /prescricoes` e `POST /prescricoes/fisica`, reusando `backend/seed_demo.py` e as fixtures de `backend/tests/integration/conftest.py`.
- **Fase 2** — conduzir ciclos de vida via endpoints (custódia, dispensação parcial/total, devoluções) — reusar `tests/integration/test_dispensacoes.py` e `test_custodia_devolucao.py`.
- **Fase 3** — medir M1 (fechamento), M2 (replay do ledger persistido), M3 (Σ dispensado ≤ prescrito), M4 (imutabilidade — reusar `test_ledger_imutabilidade.py`), M5 (adulteração via `montar_documento_de_conn` vs `assinatura_hash` armazenado — reusar `test_integridade.py`), M6 (determinismo).
- **Fase 4** — controles anti-gaming (transições ilegais via endpoint → 4xx; equilíbrio happy/adversarial; reprodutibilidade).
- **Fase 5** — tabela + `e1_fullstack_results.json`; atualizar a tabela da Seção IV em `docs/paper/CBEB-2026-DRAFT-v3-PT.md`.

## 4. Restrições inegociáveis (do contrário o experimento é inválido)

- **Só endpoints oficiais.** Zero `INSERT/UPDATE/DELETE` direto em tabelas clínicas; zero inserção direta em `*_eventos`.
- **Não "fazer o número fechar".** Proibido alterar `domain/states.py`, `documento_canonico.py` ou qualquer máquina de estados para forçar resultado.
- **RBAC real.** Atores sintéticos com papéis/credenciais corretos; sem atalho de admin que mascare verificação.
- **Replay honesto.** M2 lê o **ledger persistido**, não uma estrutura paralela que já conhece o estado.
- **Caveat de devolução.** Os fluxos de devolução desviam do modelo formal (`states.py`, nota CODEX 4E.2). Escopar fora das métricas de transição OU reportar como *desvio documentado* — **nunca** como violação silenciosa. **Não corrigir o desvio aqui** (é ticket core próprio).
- **Dados 100% sintéticos / `DEMO_MODE`.** Nenhum dado real; CPF do prescritor não trafega.
- **🚧 Guarda R6.** Se qualquer parte tocar **assinatura ou serialização canônica** (WebCrypto↔Python), **PARE e escale ao conselheiro** antes de implementar. M5/M6 usam o hash já existente — não reimplemente a canonicalização.

## 5. Se um critério não bater

Não maquie. Uma divergência (ex.: replay < 100%) pode ser **bug real de persistência de estado** — reporte com o protocolo afetado e abra como achado/ticket. O experimento serve à verdade do sistema, não à narrativa.

## 6. Entregáveis

- Harness em `docs/paper/experiments/` (ou `backend/tests/experiments/`), com **comando único** documentado e semente fixa.
- `e1_fullstack_results.json` versionado + tabela de resultados.
- Commit isolado (classe `module`/test). **Ordem:** seu commit → revisão CODEX → ajustes → Jules → conselheiro funde no paper.
