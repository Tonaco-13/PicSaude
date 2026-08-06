# DESPACHO F5C3-MERGE — Roteia o trabalho F5-C3 órfão a merge

| Campo | Valor |
|---|---|
| **Despacho** | F5C3-MERGE |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Conselheiro (Fable 5) → Fabiano (martelo) · cc: Kimi 3 (não trabalha neste) |
| **Data** | 2026-08-02 |
| **Origem** | KIMI3-002 §3 (F5-C3 órfão na working tree) + KIMI3-003 §3.2 |
| **Estado** | 🟡 **Aguarda parecer do Conselheiro + martelo do Fabiano** |

---

## §1 Contexto

O trabalho **F5-C3 (Etapa C de UX do cidadão)** está completo há semanas (31/31 testes verdes, conforme KIMI3-001 §0) mas **parado na working tree**, sem merge. Foi deixado "aguardando parecer do Conselheiro" — agora que o Fable 5 está ativo, roteio a revisão formal.

O F5-C3 não é lixo nem experimental — é **objeto sanitário válido e testado**, só faltava governança.

### Por que sair da working tree AGORA

O Kimi 3 está trabalhando ativamente nesta pasta. O `cidadao.html` está **misturado**: F5-C3 (staged) + `_autoLoginDemo` do Kimi 3 (unstaged), no mesmo arquivo. Enquanto o F5-C3 não mergear, o Kimi 3 não consegue commitar o item 4 (cidadao) limpo. **Merge do F5-C3 limpa a working tree e desbloqueia o Kimi 3.**

---

## §2 O que está no F5-C3 (escopo do merge)

Mapeamento `git diff` confirmado em 2026-08-02:

| Arquivo | Estado | Conteúdo |
|---|---|---|
| `cidadao.html` | staged | F5-C1 (modal pós-transferência + toast enriquecido) · F5-C2 (polling carteira 30s + pause em aba oculta + `_pararCarteiraPoll` em `sair()`/401/403) · F5-C3 (classe `.atestado-card` + reordenação Receitas→Atestados→Exames→Laudos→Histórico) |
| `backend/tests/browser/test_smokes.py` | staged | `.exame-card` → `.atestado-card` (seletor acompanhando F5-C3) |
| `backend/tests/browser/test_f5_etapa_c_cidadao.py` | untracked (novo) | 258 linhas — suíte E2E do F5-C3 |
| `backend/tests/browser/conftest.py` | staged | fixtures `external`/`base_url`/`demo_externa_viva` (infra de teste externo — Ticket F5-B5) |
| `backend/pytest.ini` | staged | marker `external` |
| `backend/tests/browser/test_f5_externo_picsaude.py` | untracked (novo) | E2E externo contra picsaude.com.br |

> ⚠️ **`conftest.py`, `pytest.ini`, `test_f5_externo_picsaude.py`** são tecnicamente **F5-B5** (gate externo), não F5-C3. Mas estão acoplados na mesma working tree. **Decisão:** mergear junto pra limpar a pasta de uma vez — são `ops`/infra de teste, sem impacto clínico. (Alternativa: separar em 2 PRs. Decisão do Engenheiro/Fabiano.)

---

## §3 Classe de contribuição

- **F5-C1/C2/C3 (`cidadao.html`, `test_smokes.py`, `test_f5_etapa_c_cidadao.py`):** `module` (frontend do módulo do cidadão + testes).
- **Infra externa (`conftest.py`, `pytest.ini`, `test_f5_externo_picsaude.py`):** `ops` (gate de CI / infra de teste).

Nenhum dos dois é `core`. Não toca núcleo (NUCLEO_SANITARIO, ledger, estados, custódia, RBAC).

---

## §4 Invariantes a verificar no parecer (Fable 5)

- **R1 (reprodutibilidade):** o polling de 30s é UX-only; não altera estados do backend nem ledger.
- **§10 (estados computados não persistidos):** a reordenação visual (Atestados acima de Exames) é renderização; `i.estornado`, `i.acionavel`, `status_item` continuam vindos do backend.
- **Sem mudança de contrato público:** nenhum endpoint novo/alterado.
- **Testes E2E afirmam sobre DOM renderizado** (lição COER-2 reafirmada), não sobre respostas de API isoladas.

---

## §5 Decisões embutidas (pra Fable 5 validar)

1. **30s e não 15s** para o polling do cidadão: cidadão é consumidor esporádico mobile; dispensador é workstation de balcão. Metade do custo de rede/bateria. (Justificativa inline no código.)
2. **Pause em aba oculta via `visibilitychange`:** economia de bateria em aba escondida — o dispensador não tem essa correção.
3. **`_pararCarteiraPoll()` em `sair()` e 401/403:** evita storm de fetches/emojis pós-logout — correção de bug conhecido do dispensador que **não** foi portado.

---

## §6 Bloqueios e dependências

- **Pré-requisito:** nenhum. O F5-C3 é independente.
- **Desbloqueia:** o item 4 (cidadao `_autoLoginDemo`) do Kimi 3 — após merge, `cidadao.html` no `main` terá o F5-C3, e a working tree do Kimi 3 mostrará só o `_autoLoginDemo` como diff limpo.
- **Não desbloqueia:** a "falha do teste externo" (KIMI3-002 §4) — essa é `ops`, e a demo pública precisa ser atualizada com F5-C3 + KIMI3 antes de o teste externo ser ligado em CI.

---

## §7 Fluxo de aprovação

1. **Criselheiro (Fable 5):** parecer sobre F5-C3 (§4 invariantes, §5 decisões embutidas).
2. **Arquiteto (GLM-5.2):** ratifica verde ou pede ajuste.
3. **Engenheiro (Claude Code/terminal):** prepara branch + commits (separando do trabalho do Kimi 3 conforme KIMI3-003 §3.3) + roda gate local.
4. **Fabiano:** martelo + merge.
5. Deploy → demo pública atualizada.

---

## §8 Não fazer

- Não usar `git stash` (KIMI3-002 §3) — pasta compartilhada.
- Não commitar junto com trabalho do Kimi 3 (item 4, A, B, E2E B1/B2) — branches separadas.
- Não alterar a semântica do polling pra além do UX (sem mudar endpoints, sem criar estados).

---

*Despacho emitido pelo arquiteto de backend. Kimi 3: este despacho é só informativo pra você — você NÃO trabalha no F5-C3. Aguarde o merge pra commitar `cidadao.html` limpo.*
