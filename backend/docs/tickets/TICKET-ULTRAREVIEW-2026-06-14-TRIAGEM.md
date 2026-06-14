# Triagem — Ultra-review ampla de 2026-06-14

| Campo | Valor |
|---|---|
| **Origem** | `claude ultrareview` rodou em modo **repositório inteiro** (não escopado ao PR #16). |
| **Escopo** | Foto de dívidas pré-existentes do projeto todo. **Não** é do E2 (E2 saiu limpo — só M5, by-design). |
| **Método** | Cada achado verificado contra o código (regra "verificar, não confiar"). |

> ⚠️ Este doc existe para **de-ruidar** o relatório: 7 dos 13 críticos/altos são **falsos** (o
> revisor não leu o `CLAUDE.md` — §6b, Alembic-como-deploy, §6a). Não reabrir os falsos.

## Veredito — Críticos + Altos (13)

| ID | Achado | Veredito | Prova / motivo |
|---|---|---|---|
| C1 | DDL enum Postgres só 4 estados → deploy quebra | ❌ Moot | `status_item_t` não existe nas migrations; deploy é **Alembic** (String), não o `.sql` legado |
| C2 | Desvios de máquina de estados (devoluções) | 📋 Já ticketado | Documentado em `states.py:153-167`; `TICKET-COERENCIA-DEVOLUCOES` |
| C3 | `devolver-prescritor` pula `em_custodia` | 📋 Já ticketado | Mesmo caso do C2 (`auth.py:302`) |
| C4 | Hash v2 quebra revalidação de v1 | ❌ Falso | `unidade_quantidade` nunca esteve no v1; não há hash v1 legado a quebrar |
| H1 | `DEV_PRESET_CONTEXT=true` nos HTML | 🟡 By-design (Etapa 6) | Auto-login dev contra seed; JWT só em memória. **Resíduo real:** flag hardcoded → prod precisa do flip |
| H2 | XSS via innerHTML | ❌ Falso | Valores = CPF só-dígitos / UUID do servidor; `_cEsc` nem existe no arquivo citado |
| H3 | tokens.py commit-then-raise persiste estado | ❌ Falso | Grava só na tabela de auditoria (uso bloqueado); zero estado clínico |
| H4 | hospitalares UPDATE prescricoes sem `org_id` | ❌ Falso | `prescricoes` **não tem** coluna `org_id` (§6b: rollout incremental) |
| **H5** | **`devolver_item` sem check de custódia** | ✅ **REAL** | `custodia.py:747` valida item/status mas nunca checa se o ator detém a custódia |
| H6 | quantidade NULL → rejeição silenciosa | ❌ Falso | NULL→saldo 0→**409 explícito** (`custodia.py:636`) |
| H7 | CPF sentinela sem validação em digital | ❌ Falso | Emissão digital **rejeita** o sentinela (`prescricoes.py:185`) |
| **H8** | **outbox engole exceção sem traceback** | ✅ **REAL (nit)** | `outbox.py:84` `.warning()` sem `exc_info` — engolir é by-design (G4A), mas cego p/ diagnóstico |
| H9 | localStorage clínico em claro | 🟡 By-design (§6) | Inerente ao fire-and-forget; demo MVP |

**Placar:** 7 falsos · 2 já-ticketados · 2 by-design · **2 reais-novos (H5, H8)**. Médios/baixos não triados aqui (M5 = fork-R do E2, by-design).

## Ações reais (as duas que sobraram)

### H5 → **5C-BIS-F: ownership em `custodia.py`** (classe `core` — cadeia de custódia)
A varredura 5C-BIS (A–E) cobriu os objetos novos; o **fluxo original** de `custodia.py` ficou de
fora. 3 endpoints mutantes sem os helpers de ownership: `transferir` (346), `dispensar` (517),
`devolver` (747). **Ressalva:** parte é mediada por **token de apresentação** (autz diferente de
CNS/CPF) — exige sanity-read próprio para separar "descoberto" de "token-mediado". É `core` →
spec + martelo do Fabiano + revisão central antes de implementar. Não é fix de contrabando.

### H8 → fix trivial de observabilidade
`outbox.py:84`: trocar `.warning(msg)` por `.warning(msg, exc_info=True)`. Classe `ops`. Mantém o
engolir (by-design G4A), só captura o stack trace. PR pequeno.

---

*Triado por Claude (Engenheiro-Chefe) em 2026-06-14, verificando cada achado contra o código.
Os 7 falsos são consequência de o revisor não ter lido o `CLAUDE.md`.*
