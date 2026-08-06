# TICKET-OPS-WORKTRES-POR-AGENTE — Worktrees git separadas por agente

| Campo | Valor |
|---|---|
| **ID** | TICKET-OPS-WORKTRES-POR-AGENTE |
| **Classe** | `ops` (infraestrutura de desenvolvimento — não afeta produção) |
| **Estado** | 🟢 **MARTELADO** (Fabiano, 2026-08-03) — executar |
| **Origem** | `DESPACHO-ARQ-INCIDENTE-CHECKOUT-COMPARTILHADO` §3 Opção 1 |
| **Para** | Fabiano (executa o setup) → arquiteto confirma funcionamento |

---

## §1 Por que (causa-raiz)

Dois agentes (Engenheiro + Kimi 3) compartilham o mesmo checkout físico em `/Volumes/fabianotonaco/Developer/PicSaude_Dev`. Qualquer `git commit` cai na branch onde o HEAD está — ocorreu um incidente em 2026-08-02 (~15:04) quando o commit do seed caiu na branch do frontend, requerendo cirurgia de ponteiros. **Worktrees isolam o HEAD por agente**, eliminando a causa-raiz.

## §2 Setup (Fabiano executa uma vez)

```bash
cd /Volumes/fabianotonaco/Developer/PicSaude_Dev

# Worktree do Engenheiro (backend)
git worktree add ../PicSaude_Eng

# Worktree do Kimi 3 (frontend)
git worktree add ../PicSaude_Kimi3

# O checkout principal (este diretório) fica com o arquiteto/Fabiano em main
```

Cada agente, ao iniciar trabalho, entra na sua worktree:
```bash
# Engenheiro
cd ../PicSaude_Eng && git checkout <branch-de-trabalho>

# Kimi 3
cd ../PicSaude_Kimi3 && git checkout <branch-de-trabalho>
```

## §3 Verificação pós-setup

```bash
git worktree list
# Deve mostrar 3 entradas:
# /Volumes/fabianotonaco/Developer/PicSaude_Dev      (main)
# /Volumes/fabianotonaco/Developer/PicSaude_Eng      (nova)
# /Volumes/fabianotonaco/Developer/PicSaude_Kimi3    (nova)
```

## §4 Pré-requisitos a confirmar

- **Mount SMB tolera worktrees:** o Engenheiro já usou worktree temporária com sucesso durante o rebase do seed (DESPACHO-ENG-003 §1) — sinal verde.
- **Espaço em disco:** cada worktree ocupa espaço próprio (mas compartilham o `.git` central, então objetos são deduplicados). Confirmar ~500MB livres por worktree.
- **O Engenheiro e o Kimi 3 precisam saber** que seus checkouts mudaram de diretório. Atualizar os despachos futuros com o novo path.

## §5 Protocolo pós-setup

- Cada agente opera na sua worktree.
- `git branch --show-current` antes de commitar (continua válido — defense in depth).
- `git add <arquivo>` sempre (idem).
- O checkout principal (`main`) só recebe merges — nenhum agente desenvolve direto nele.

## §6 Custos/benefícios

| | Antes (checkout único) | Depois (worktrees) |
|---|---|---|
| Conflito de HEAD | frequente (incidente 02/08) | impossível |
| Coordenação | protocolo rigoroso (frágil) | isolamento físico (robusto) |
| Setup | zero | uma vez |
| Espaço em disco | 1× | ~3× (com dedup) |

## §7 Não fazer

- Não compartilhar worktree entre agentes (perde o propósito).
- Não desenvolver no checkout principal (só merges).
- Não deletar worktree sem `git worktree remove` (deixa estado sujo).

---

*Ticket `ops` executado pelo setup do Fabiano. Confirmação de funcionamento pelo arquiteto após primeiro ciclo de trabalho paralelo.*
