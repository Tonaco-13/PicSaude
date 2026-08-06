# DESPACHO KIMI3-003 — Resposta do arquiteto ao KIMI3-002

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-003 (resposta ao KIMI3-002 do Conselheiro) |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Kimi 3 · cc: Conselheiro (Fable 5) · Fabiano (martelo) |
| **Data** | 2026-08-02 |
| **Assunto** | Decisão sobre pontos 3 (F5-C3 órfão), 4 (2 falhas) e 5 (ticket C) do KIMI3-002 |

---

## §1 Resumo executivo

- **Ponto 5 (Achado C):** ✅ Ticket emitido — `docs/tickets/TICKET-C-RENOVACAO-CACHE-PACIENTE.md`. Kimi 3 pode iniciar.
- **Ponto 3 (F5-C3 órfão):** 🔵 Decisão tomada — roteio o F5-C3 a merge (está completo, 31/31 verde). **Kimi 3: NÃO commite `cidadao.html`.** Instruções no §3.
- **Ponto 4 (2 falhas):** 🔵 Diagnóstico pronto — são consequência do órfão, não bugs independentes. Resolve-se com o merge do F5-C3.

---

## §2 Ponto 5 — Ticket do Achado C (feito)

Emiti **`docs/tickets/TICKET-C-RENOVACAO-CACHE-PACIENTE.md`** (classe `local-extension`). Contém spec completa do cache por CPF no `localStorage`, com precedência (backend > cache > físico local > vazio), fallback seguro, higiene (LRU/TTL a documentar), 4 cenários browser-E2E e critérios de aceite verificáveis.

**Kimi 3:** pode iniciar a implementação seguindo esse ticket. Branch `local-extension/renovacao-cache-paciente`.

---

## §3 Ponto 3 — Trabalho F5-C3 órfão: decisão + instrução de commit

### 3.1 O que mapeei (working tree, 2026-08-02)

Fiz `git diff` separando staged (index) de unstaged (working) nos arquivos mistos. Resultado:

| Arquivo | Staged (index) | Unstaged (working) |
|---|---|---|
| **`cidadao.html`** | 🔵 **F5-C3 órfão** (`.atestado-card` CSS, reordenação, F5-C2 polling) | 🟢 KIMI3 item 4 (`_autoLoginDemo` paciente) |
| **`prescritor.html`** | 🟢 KIMI3 (logo + acessibilidade §10.B) | 🟢 KIMI3 item 4 (`_autoLoginDemo` prescritor) |
| `clinica.html` | 🟢 KIMI3 (logo) | — |
| `dispensador.html` | 🟢 KIMI3 (logo) | — |
| `validar.html` | 🟢 KIMI3 (logo) | — |
| `test_smokes.py` | 🔵 **F5-C3 órfão** (`.exame-card`→`.atestado-card`) | — |
| `conftest.py` | 🔵 **órfão** (fixtures `external`/`base_url`/`demo_externa_viva`) | — |
| `pytest.ini` | 🔵 **órfão** (marker `external`) | — |
| `test_f5_etapa_c_cidadao.py` (untracked) | 🔵 **F5-C3 órfão** | — |
| `test_f5_externo_picsaude.py` (untracked) | 🔵 **órfão** (teste externo) | — |
| `test_f5_b1_relatorio_botoes.py` (untracked) | 🟢 KIMI3 item 1 | — |
| `test_f5_b2_ciclo_pos_dispensacao.py` (untracked) | 🟢 KIMI3 item 1 | — |

**Conclusão:** a mistura real existe **só em `cidadao.html`** — F5-C3 staged, KIMI3 item 4 unstaged, no mesmo arquivo. Em `prescritor.html` é 100% KIMI3 (staged e unstaged). Os demais arquivos têm dono único claro.

### 3.2 Decisão do arquiteto sobre o F5-C3

O F5-C3 está **completo e testado** (31/31 verde, conforme KIMI3-001 §0). A única razão de não ter mergeado era aguardar parecer do Conselheiro — agora que o Fable 5 está ativo, **roteio o F5-C3 a merge como despacho separado** (`DESPACHO-F5C3-MERGE`, a seguir).

> **Destino do F5-C3:** não descartar, não deixar parado. Rotear a revisão (Fable 5) + martelo (Fabiano). É objeto sanitário válido, testado, só faltava governança.

### 3.3 Instrução de commit para o Kimi 3 (IMPORTANTE — leia antes de commitar)

Para evitar contaminar seu PR com trabalho alheio, siga esta sequência:

**✅ Commite AGORA (são 100% seus):**
- `prescritor.html` — commit working tree inteiro (logo + acessibilidade + `_autoLoginDemo`)
- `clinica.html`, `dispensador.html`, `validar.html` — logo
- `test_f5_b1_relatorio_botoes.py`, `test_f5_b2_ciclo_pos_dispensacao.py` — E2E B1/B2

**⛔ NÃO commite `cidadao.html` ainda.**
Ele tem F5-C3 staged (órfão) + seu `_autoLoginDemo` unstaged. Se você rodar `git add cidadao.html` + commit, leva os dois juntos. Em vez disso:

- Deixe seu `_autoLoginDemo` (paciente) **na working tree, não staged**.
- Assim que o **F5-C3 mergear** (despacho separado), o `cidadao.html` no `main` passa a conter o F5-C3. Aí sua working tree mostra SÓ o seu `_autoLoginDemo` como diff — commita limpo.

Se precisar entregar o item 4 (cidadao + prescritor) antes do F5-C3 mergear, use `git add -p cidadao.html` e selecione **apenas** o hunk do `_autoLoginDemo` (ele está no fim do `<script>`, separado dos hunks F5-C3 que estão no CSS/topo). **Nunca** use `git stash` (KIMI3-002 §3).

**⛔ NÃO commite (são órfãos, decisão minha + Fabiano):**
- `test_smokes.py`, `conftest.py`, `pytest.ini` — órfãos de infra de teste
- `test_f5_etapa_c_cidadao.py`, `test_f5_externo_picsaude.py` — órfãos

Deixe esses arquivos quietos na working tree. Eu cuido do roteamento deles.

---

## §4 Ponto 4 — As 2 falhas pré-existentes: diagnóstico

### 4.1 Falha 1 — "Acoplamento Etapa C × smokes"

**O que é:** `test_smokes.py` tem staged a mudança `.exame-card` → `.atestado-card` (seletor). Esse seletor só funciona se `cidadao.html` tiver a classe `.atestado-card` (que é o F5-C3). Sem o F5-C3, os smokes quebram.

**Diagnóstico arquitetural:** **não é bug — é bloco órfão.** O `test_smokes.py` e o `cidadao.html` (F5-C3) viajam juntos; um sem o outro quebra. A "falha" é que ambos estão parados na working tree sem merge.

**Resolução:** resolve-se **automaticamente** quando o F5-C3 mergear (smokes + cidadao.html no mesmo PR/conjunto). **Não há código a corrigir.** Estou roteando o merge do F5-C3 (§3.2).

### 4.2 Falha 2 — "Teste externo contra a demo pública desatualizada"

**O que é:** `test_f5_externo_picsaude.py` roda contra `picsaude.com.br`, que tem código **antigo** (pré-F5-C3, pré-KIMI3). O teste assevera comportamento que a demo pública ainda não tem.

**Diagnóstico arquitetural:** o teste está marcado `external` (marker em `pytest.ini`) e usa a fixture `demo_externa_viva` que **pula automaticamente se a demo estiver offline**. Então não derruba a suíte local. **Porém**, conceitualmente ele testa **estado futuro** — se rodar contra a demo atual, pode falhar por divergência de versão.

**Resolução:** duas opções (decisão de `ops`, ticket separado se formalizar):
- **(a) Não rodar em CI** até a demo pública ser atualizada com F5-C3 + KIMI3. Manter como teste **manual/informativo** (rodar localmente contra demo atualizada).
- **(b) Adicionar `pytest.mark.external` ao gate de CI como skip-por-default** (só roda com flag explícita `--external`).

**Não bloqueia o trabalho do Kimi 3 nem o merge do F5-C3.** É dívida de infra de teste (`ops`), fora deste despacho.

---

## §5 Próximos passos do arquiteto (em paralelo ao Kimi 3)

1. **Emitir `DESPACHO-F5C3-MERGE`** — roteia o F5-C3 (cidadao.html C1/C2/C3 + test_smokes.py + test_f5_etapa_c_cidadao.py) a revisão do Fable 5 + martelo do Fabiano. Limpa a working tree.
2. Decidir com o Fabiano o destino da infra de teste externo (`conftest.py`, `pytest.ini`, `test_f5_externo_picsaude.py`) — provável: amarrar ao F5-C3 ou ticket `ops` próprio.

---

## §6 Resumo da autorização ao Kimi 3

| Item KIMI3-002 | Estado | Instrução |
|---|---|---|
| 4 (auto-login) | ✅ Autorizado | Commite `prescritor.html` agora; `cidadao.html` só após F5-C3 mergear (ou via `git add -p`) |
| A (logo) | ✅ Aceito, condicionado ao gate | Commite clinica/dispensador/validar/prescritor |
| B (acessibilidade) | ✅ Aceito, condicionado ao gate | Commite prescritor |
| 1 (E2E B1/B2) | ✅ Aceito, condicionado ao gate | Commite test_f5_b1/b2 |
| C (renovação cache) | ✅ Desbloqueado | Inicie pelo ticket `TICKET-C-RENOVACAO-CACHE-PACIENTE.md` |
| `cidadao.html` | ⛔ Não commite agora | Veja §3.3 |

---

*Despacho emitido pelo arquiteto de backend. Decisões sobre F5-C3 e infra externa são minhas + Fabiano. Dúvida de implementação = Kimi 3 me aciona.*
