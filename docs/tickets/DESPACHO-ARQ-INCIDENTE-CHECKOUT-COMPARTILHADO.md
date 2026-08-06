# DESPACHO ARQ-INCIDENTE — Checkout compartilhado: incidente e mitigação estrutural

| Campo | Valor |
|---|---|
| **Despacho** | ARQ-INCIDENTE (incidente de coordenação 2026-08-02 ~15:04) |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) · Kimi 3 (frontend) · Fabiano (martelo + decisão de infraestrutura) |
| **Data** | 2026-08-02 |
| **Tipo** | Incidente de processo + proposta de mitigação estrutural |

---

## §1 O que aconteceu (verificado pelo arquiteto)

Às ~15:04 de 2026-08-02, dois agentes trabalhavam no **mesmo checkout físico** (não worktrees git separadas):

- O Kimi 3 tinha o HEAD em `local-extension/demo-ux-logo-a11y-autologin` (frontend).
- O Engenheiro fez `git commit` do `seed_demo.py` **sem verificar** `git branch --show-current`.
- O commit `e8d3c3f` (seed de exames) caiu na **branch do Kimi 3** e subiu no push dele (PR #130).

O Kimi 3 detectou e fez **cirurgia de ponteiros** (commit-tree/update-ref/force-push) para reparar:
1. Moveu `module/seed-exames-demo` para apontar a `e8d3c3f`.
2. Reconstruiu `local-extension/demo-ux-logo-a11y-autologin` sem o commit do seed.
3. Reescreveu o `seed_demo.py` no worktree como "trabalho não-commitado".

### Estado verificado pelo arquiteto (2026-08-02)

**✅ Correto no relato:**
- `module/seed-exames-demo` aponta para `e8d3c3f` (commit do Engenheiro) — **intacto**, commit message correta citando `DESPACHO-ENG-001` e `TICKET-SEED-EXAMES-DEMO`.
- `e8d3c3f` **só existe na branch do Engenheiro** (`git branch --contains` confirma).
- `local-extension/demo-ux-logo-a11y-autologin` está limpa: `56ae7a6` (mock) sobre `7b52fcf` (logo+a11y+autologin), sem o commit do seed.
- HEAD em `main`; `seed_demo.py` preservado no worktree (270 insertions, 3 deletions); `clinica.html` limpo.

**⚠️ Cicatriz que o Kimi 3 NÃO reportou (detectada pelo arquiteto):**
- `module/seed-exames-demo` contém o commit `7b52fcf` (logo+a11y+autologin) **abaixo** de `e8d3c3f` — ou seja, a branch do seed está baseada na branch do Kimi 3, **não em `main` puro**.
- Consequência: o PR do seed (quando aberto) vai mostrar diffs de frontend que não são dele — vai confundir o Revisor e inflar o diff.

**🟢 Nenhum conteúdo foi perdido.** A cirurgia de ponteiros funcionou no objetivo primário (commit do Engenheiro preservado na branch correta). Mas deixou a base da branch do seed poluída.

---

## §2 Causa-raiz — risco estrutural permanente

> Dois agentes compartilham o mesmo checkout físico. Qualquer `git commit` cai onde o HEAD estiver.

Isto **não é falha do Engenheiro nem do Kimi 3** — é uma limitação estrutural do setup. Vai acontecer de novo enquanto dois agentes operarem no mesmo diretório `.git`. O protocolo "verifique `git branch --show-current` antes de commitar" (que o Kimi 3 sugeriu) é **mitigação, não solução** — depende de disciplina de cada commit, falha no primeiro descuido.

---

## §3 Mitigação proposta (decisão do Fabiano)

### Opção 1 — Worktrees git separadas por agente (recomendada)

Cada agente trabalha na sua própria worktree git, apontando para o mesmo `.git` central:

```bash
git worktree add ../PicSaude_Eng    module/seed-exames-demo   # Engenheiro
git worktree add ../PicSaude_Kimi3  local-extension/...        # Kimi 3
# o checkout principal (main) fica pro arquiteto/Fabiano
```

**Vantagens:**
- HEAD isolado por worktree — commit de um agente nunca cai na branch do outro.
- Cada agente tem seu diretório de trabalho limpo.
- Mesmo repositório (mesmo `.git`) — branches compartilhadas, push/pull normal.
- Operação nativa do git, sem ferramenta externa.

**Custo:**
- Configuração inicial (3 diretórios em vez de 1).
- Cada worktree ocupa espaço em disco (mas compartilham o `.git`).
- O Fabiano precisa orquestrar (criar as worktrees antes de despachar trabalho).

### Opção 2 — Protocolo rigoroso (mitigação, não solução)

Manter checkout único, mas impor disciplina:
- **Antes de qualquer `git commit`:** `git branch --show-current` e confirmar que é a sua branch.
- **Antes de `git checkout`:** confirmar com `git status` que não há trabalho não-commitado alheio.
- Branches de trabalho sempre separadas de `main`.
- Nunca `git add .` — sempre `git add <arquivo-específico>`.

**Custo:** zero configuração. **Risco:** alto — depende de cada commit, falha no primeiro descuido.

### Opção 3 — Serialização (proibição de paralelo)

Um agente por vez. Sem paralelismo.

**Custo:** perde-se a vantagem do pipeline (escreve → revisa → implementa). **Risco:** zero de incidente, mas baixa produtividade.

---

## §4 Recomendação do arquiteto

**Opção 1 (worktrees) se for viável na sua infraestrutura.** Resolve a causa-raiz de vez. O protocolo rigoroso (Opção 2) fica como **defense-in-depth** (camada extra) mas não como linha principal.

Se a infraestrutura atual (mount SMB de rede, conforme relato do Kimi 3) dificultar worktrees, a Opção 2 com disciplina reforçada é o fallback.

---

## §5 Ação imediata — limpeza da base da branch do seed

Independente da decisão sobre mitigação estrutural, a branch `module/seed-exames-demo` precisa ser **rebaseada para `main` puro**, removendo o commit `7b52fcf` (frontend) da sua história:

```bash
# Engenheiro executa, na sua próxima atividade:
git checkout module/seed-exames-demo
git rebase --onto main 7b52fcf module/seed-exames-demo
# Resultado: e8d3c3f (seed) reescrito sobre main, sem o commit de frontend
git push --force-with-lease origin module/seed-exames-demo
```

Isto **não afeta o conteúdo** do commit `e8d3c3f` — apenas muda sua base. O PR do seed fica limpo.

---

## §6 Ação imediata — instrução de processo (válida já)

Até a mitigação estrutural ser decidida, todos os agentes devem seguir:

1. **Antes de `git commit`:** executar `git branch --show-current` e confirmar (mentalmente ou por log) que é a branch esperada.
2. **Nunca `git add .` ou `git add -A`:** sempre arquivos específicos (`git add <arquivo>`).
3. **Antes de `git checkout <branch>:** `git status` para confirmar que não há trabalho não-commitado que não seja seu.
4. **Se descobrir trabalho alheio no seu commit:** NÃO faça cirurgia de ponteiros sem falar com o arquiteto. Pause e relate.

---

## §7 Não fazer

- **Kimi 3:** não faça mais cirurgia de ponteiros (commit-tree/update-ref) sem falar comigo. Funcionou desta vez, mas é operação de risco que pode perder commits.
- **Engenheiro:** não tente rebasar a branch do seed sem falar comigo se não tiver familiaridade com `rebase --onto`.
- Ninguém faz `git push --force` em `main` ou em branch de outro agente sem autorização explícita.

---

## §8 Rastreabilidade

| Item | Estado |
|---|---|
| Commit do Engenheiro (`e8d3c3f`) | ✅ Preservado, intacto, na branch correta |
| Branch do Kimi 3 (PR #130) | ✅ Limpa, sem o commit do seed |
| Worktree do Engenheiro (`seed_demo.py`) | ✅ Preservado como não-commitado |
| Base da branch do seed | ⚠️ Poluída (rebase necessário — §5) |
| Causa-raiz | 🟡 Estrutural — checkout compartilhado (§2-§4) |

---

*Despacho emitido pelo arquiteto de backend. Incidente remediado tecnicamente, mas a causa-raiz (checkout compartilhado) exige decisão de infraestrutura do Fabiano (§3-§4).*
