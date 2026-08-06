# RUNBOOK — Mitigação do checkout compartilhado (pronto pra executar)

| Campo | Valor |
|---|---|
| **Estado** | 🟢 **PRONTO** — aguarda o Fabiano escolher Opção 1/2/3 e dizer "go" |
| **Origem** | `DESPACHO-ARQ-INCIDENTE-CHECKOUT-COMPARTILHADO` §3 |
| **Evidência de viabilidade** | O Engenheiro já usou worktree temporária no rebase do seed (2026-08-02) e funcionou |

---

## Opção 1 — Worktrees separadas por agente (RECOMENDADA, pronta pra executar)

### Setup (o Fabiano roda uma vez)

```bash
cd /Volumes/fabianotonaco/Developer/PicSaude_Dev

# Worktree do Engenheiro (backend)
git worktree add ../PicSaude_Eng -b wip/eng 2>/dev/null || git worktree add ../PicSaude_Eng

# Worktree do Kimi 3 (frontend)
git worktree add ../PicSaude_Kimi3 -b wip/kimi3 2>/dev/null || git worktree add ../PicSaude_Kimi3

# Checkout principal (main) continua com o arquiteto/Fabiano
```

Cada agente, ao iniciar trabalho:
```bash
cd ../PicSaude_Eng        # (ou PicSaude_Kimi3)
git checkout <sua-branch> # cada um na sua, HEAD isolado
```

### Pré-requisitos
- Confirmar que o mount SMB de rede tolera worktrees (o Engenheiro já testou com temporária — sinal verde).
- O Fabiano cria as worktrees **antes** de despachar trabalho paralelo.

### Vantagem
HEAD isolado por worktree — commit de um agente nunca cai na branch de outro. Resolve a causa-raiz.

---

## Opção 2 — Protocolo rigoroso (defense-in-depth, não solução)

Manter checkout único + disciplina obrigatória (já emitida no DESPACHO-ARQ-INCIDENTE §6):
- `git branch --show-current` antes de todo commit.
- `git add <arquivo>` sempre, nunca `git add .` / `-A`.
- Trabalho alheio no caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## Decisão pendente
Fabiano escolhe 1 / 2 / 3 (serialização). Recomendação: **Opção 1**. Opção 2 fica como camada extra mesmo que a 1 entre.
