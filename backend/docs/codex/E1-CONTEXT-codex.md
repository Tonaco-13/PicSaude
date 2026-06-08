# Contexto para o Codex — reproduzir e revisar o experimento E1 full-stack

> Cole este arquivo (ou aponte para ele) ao iniciar a sessão do Codex.
> Seu papel aqui tem **duas frentes**: (A) **reproduzir/rodar** o protocolo E1 de forma
> independente, para verificar que os números não são artefato de uma única implementação;
> e (B) aplicar a **lente de segurança / RBAC / anti-gaming** sobre o harness do Claude Code.

---

## 1. Missão em uma linha

Cross-check independente do experimento E1 (auditabilidade por construção) + auditoria de que o harness não burla nem se auto-realiza.

## 2. Leia primeiro

1. `docs/paper/experiments/E1-PLANO-EXPERIMENTAL.md` — o protocolo (Fases 0–5) e os critérios de aceitação.
2. `docs/paper/experiments/E1-HANDOFF-claude-codex-jules.md` — seu escopo (§2) e o anti-escopo (qualidade/metodologia é do Jules).
3. O commit do Claude Code: o harness full-stack + `e1_fullstack_results.json`.
4. `docs/paper/experiments/e1_auditability.py` + `e1_results.json` (preliminar, para comparação).
5. `CLAUDE.md` §1–§6, §10 (invariantes e taxonomia).

## 3. Frente A — Reprodução independente

- Rode o protocolo das Fases 0–5 **no seu ambiente** (PostgreSQL efêmero, semente fixa).
- Como as métricas de hash/estado são determinísticas, M2 (replay), M5 (adulteração) e M6 (determinismo) devem bater **exatamente**; M1/M3/M4 devem dar os mesmos valores esperados (0 ilegais, 0 violações).
- Reporte qualquer divergência entre a sua execução e a do Claude Code — divergência é sinal de não-reprodutibilidade ou de dependência de ambiente, e precisa ser explicada antes de os números irem ao paper.

## 4. Frente B — Lente de segurança / RBAC / anti-gaming

Audite o harness do Claude Code quanto a:

- **Sem bypass:** escreve exclusivamente por endpoints oficiais — zero SQL direto em tabelas clínicas, zero `INSERT` direto em `*_eventos`.
- **RBAC real:** atores sintéticos com papéis corretos; ownership respeitado; sem atalho de admin mascarando verificação.
- **Replay honesto:** M2 lê o **ledger persistido**, não uma estrutura paralela em memória.
- **Integridade real:** M5 passa pelo `assinatura_hash` **armazenado** (via `montar_documento_de_conn`), não por recomputo isolado que nunca tocou o banco.
- **Anti-circularidade:** há estímulo adversarial; o experimento não valida só o caminho-feliz que ele mesmo gera.
- **Sintético / `DEMO_MODE`:** nenhum dado real; CPF do prescritor não trafega.
- **Caveat de devolução:** o desvio documentado (`states.py`, nota CODEX 4E.2) está **reportado**, não escondido nem "corrigido" dentro do experimento.

## 5. Anti-escopo e guarda

- **Não cobrir** estilo, manutenibilidade, definições estatísticas finas — isso é do **Jules**.
- **🚧 Guarda R6:** se identificar que o harness toca assinatura ou serialização canônica (WebCrypto↔Python), sinalize como bloqueador — essa área passa pelo conselheiro antes de qualquer mudança.

## 6. Saída

- Relatório em `backend/docs/codex/` (padrão da casa): resultado da reprodução (Frente A) + achados de segurança/anti-gaming (Frente B), com severidade.
- Veredito: os números do E1 estão prontos para entrar na Seção IV do paper? (sim / sim-com-ajustes / não — com motivos).
