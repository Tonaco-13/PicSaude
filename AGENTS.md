# ⚠️ OBSOLETO — Fonte de governança: `CLAUDE.md`

> **Este arquivo está congelado desde o commit inicial (`9d15a3f`, "PicSaúde 1.0.0") e
> NÃO será mais atualizado.** Permanece como snapshot histórico do escopo original
> de prescrição.
>
> A fonte de governança do projeto é **`CLAUDE.md`** (root), que evoluiu com:
> - §2a — Regras de ouro do relatório regulatório (R1–R4)
> - §5a/§5b — Referência e Contrato de Estados (incl. `transferida_prescritor`)
> - §9 — Migração como autoridade de schema (Alembic)
> - §10 — Taxonomia de contribuição (estados computados não persistidos)
> - Atualizações do COER-2 e arcos regulatórios
>
> **Consulte `CLAUDE.md` para qualquer decisão de implementação.**

---

# PicSaúde — Princípios arquiteturais obrigatórios (snapshot histórico)

> Este arquivo é lido automaticamente pelo Codex a cada sessão.
> Qualquer desenvolvedor ou agente que atue neste projeto deve seguir
> estas regras antes de qualquer decisão de implementação.

---

## MAPA RÁPIDO

| Tópico | Seção |
|---|---|
| Regras invioláveis (imutabilidade, ledger, custódia, dispensação parcial) | 1 · 2 · 3 · 4 |
| Estados de prescrição física vs digital | 5 |
| Referência completa de estados (prescrição e item) | 5a |
| Contrato de Estados (invariantes + fonte de verdade) | 5b |
| Emissão exclusivamente física + fire-and-forget | 6 |
| Convenções técnicas (CPF sentinela) | 6a |
| Escopo institucional (org_id + unidade_id) — convenção e guardrail | 6b |
| Modelo generalizável + Núcleo Sanitário (exames, laudos, internações…) | 7 |
| Estrutura de arquivos do projeto | 8 |
| Criar tabelas novas | 9 |
| Taxonomia de contribuição — classificação obrigatória de mudanças | 10 |
