# DESPACHO ENG-005 — Commit do F5-C3 órfão (lista explícita, 2 commits)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-005 |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) |
| **Data** | 2026-08-03 |
| **Origem** | Martelo do Fabiano: "F5-C3 = VERDE; arquiteto ratifica; Engenheiro commita por lista explícita (2 commits: module + ops), sem arrastar a lápide do DDL" |
| **Parecer Fable 5** | Dispensado — o Fabiano homologou VERDE diretamente |

---

## §1 Ratificação do arquiteto

O Fabiano homologou o F5-C3 como VERDE. Eu já tinha avaliado o código na sessão anterior (etapa C de UX do cidadão, 31/31 testes verdes conforme KIMI3-001 §0). **Ratifico.** Você commita.

## §2 Verificação de working tree (FIZ ANTES de despachar)

Inspecionei cada arquivo modified/untracked da working tree pra te dar a **lista exata**. Confirmei:

- **`cidadao.html`** (modified) — **F5-C3 puro** (159 linhas diff: `.atestado-card` CSS, reordenação, F5-C2 polling). **Sem resíduo do Kimi 3** (zero ocorrências de `autoLoginDemo`/`KIMI3`/`header-logo-link` — ele commitou na própria branch). ✅
- **`test_smokes.py`** (modified) — diff de **1 hunk só**: `.exame-card` → `.atestado-card` (linhas 317-320). É F5-C3.
- **`test_f5_etapa_c_cidadao.py`** (untracked) — F5-C3 (suíte E2E, 258 linhas).
- **`conftest.py`** (modified) — fixtures `external`/`base_url`/`demo_externa_viva`. **NÃO é F5-C3** — é infra externa (F5-B5), vai no commit `ops`.
- **`pytest.ini`** (modified) — marker `external`. **NÃO é F5-C3** — vai no commit `ops`.
- **`test_f5_externo_picsaude.py`** (untracked) — E2E externo. **NÃO é F5-C3** — vai no commit `ops`.
- **`docs/picsaude_ddl_postgres_v1.sql`** (modified) — **lápide Q3 (NÃO commitar aqui)**. Vai em ticket próprio.
- **`docs/tickets/TICKET-F5-FATIA-B-...md`** (modified) — doc residual, NÃO commitar aqui.

## §3 Os 2 commits (lista explícita)

### Commit 1 — `module`: F5-C3 (Etapa C de UX do cidadão)

**Branch:** `module/f5-c3-cidadao` (criar nova a partir de `main`).

**Arquivos (3, lista exata):**
```
cidadao.html
backend/tests/browser/test_smokes.py
backend/tests/browser/test_f5_etapa_c_cidadao.py
```

**Mensagem sugerida:**
```
feat(cidadao): etapa C de UX — atestado-card, reordenação, polling carteira [F5-C3]

F5-C1: modal pós-transferência + toast enriquecido.
F5-C2: polling carteira 30s + pause em aba oculta + _pararCarteiraPoll em sair/401/403.
F5-C3: classe .atestado-card (verde) + reordenação Receitas→Atestados→Exames→Laudos.

test_smokes.py: seletor .exame-card → .atestado-card (acompanhando F5-C3).
test_f5_etapa_c_cidadao.py: suíte E2E (258 linhas).

31/31 verdes. Parecer Fable 5 dispensado (homologação direta do Fabiano, 2026-08-03).
```

### Commit 2 — `ops`: infra de teste externo (F5-B5)

**Branch:** `ops/infra-teste-externo` (criar nova a partir de `main`).

**Arquivos (3, lista exata):**
```
backend/pytest.ini
backend/tests/browser/conftest.py
backend/tests/browser/test_f5_externo_picsaude.py
```

**Mensagem sugerida:**
```
test(ops): infra de teste externo contra demo pública [F5-B5]

- pytest.ini: marker `external`.
- conftest.py: fixtures `base_url` + `demo_externa_viva` (skip automático se offline).
- test_f5_externo_picsaude.py: E2E contra picsaude.com.br (B1/B2/B3 + máquina de estados).

Testes marcados `external` pulam em suíte local; só rodam contra demo pública.
```

## §4 ⚠️ NÃO commitar (cuidado explícito)

```
docs/picsaude_ddl_postgres_v1.sql    ← lápide Q3, vai em ticket próprio (seu ou meu)
docs/tickets/TICKET-F5-FATIA-B-...   ← doc residual, fora de escopo
```

A lápide do DDL é trabalho meu (Q3 do parecer Fable 5 sobre exames), **não arraste**.

## §5 Protocolo de pasta compartilhada (regra permanente)

- **`git branch --show-current` antes de todo commit.**
- **`git add <arquivo>` sempre, nunca `git add .` / `-A`.**
- **Worktree temporária** se o HEAD compartilhado estiver em outra branch (padrão homologado em ENG-003 §1).
- Trabalho alheio no seu caminho: pause e relate.

## §6 Após os commits

1. Push das 2 branches.
2. Abra **2 PRs** (cite `DESPACHO-ENG-005`):
   - PR `module`: F5-C3 (3 arquivos).
   - PR `ops`: F5-B5 (3 arquivos).
3. Avise aqui. Eu ratifico verde (já está avaliado) e encaminho ao martelo do Fabiano.

## §7 Não fazer

- Não commitar `docs/picsaude_ddl_postgres_v1.sql` (lápide é ticket separado).
- Não commitar `docs/tickets/TICKET-F5-FATIA-B-...md`.
- Não usar `git stash` (pasta compartilhada).
- Não misturar os 2 commits (module ≠ ops).

## §8 Coordenadas

| Artefato | Caminho |
|---|---|
| Handoff original | `docs/tickets/HANDOFF-FRONTEND-KIMI3.md` |
| Despacho F5C3-MERGE (original) | `docs/tickets/DESPACHO-F5C3-MERGE.md` |
| Estados do cidadão | `CLAUDE.md` §5a/§5b |

---

*Despacho emitido pelo arquiteto de backend. Lista explícita verificada contra a working tree. Martelo do Fabiano recebido.*
