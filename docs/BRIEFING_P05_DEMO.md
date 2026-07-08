# BRIEFING P0.5 — Demo Pública PicSaúde (revisado)

> Gerado pelo Conselheiro (cowork/MS) em 2026-07-04, após diagnóstico com evidência
> em código e produção. Substitui o briefing anterior do Z AI. Auto-contido:
> um agente sem contexto entende o estado em 5 minutos.

---

## 1. Papéis (correção ao briefing anterior)

| Agente | Papel |
|---|---|
| **code/MS** (Claude Code, VS Code) | Engenheiro-Chefe — implementa. Detém núcleo sob CODEOWNERS |
| **Conselheiro** (cowork/MS) | Portão de core, plano, guarda de invariantes — autor deste briefing |
| **Jules** | Auditoria contínua e pós-fato |
| **Z AI** | Apoio de integração frontend↔backend e priorização |
| **Fabiano** | Ratifica core, decide prioridades, executa testes manuais |

**Não existe "Cursor" no arranjo.** "Cowork" ≠ Cursor.

---

## 2. Estado consolidado

- **P0 fechado em produção.** Commit `879c7db` em `origin/main`, deployado no Render
  (push direto autorizado conforme CLAUDE.md §10 — **auditoria pós-fato do Jules pendente**).
- Gate programático 5/5 verde: `/demo/login` (dispensador e prescritor), `/auth/me/institucional`
  com `org_id=farmacia-demo`, JWT com claims corretas, 404 limpo em protocolo inexistente.
- `GET /config/public` em produção: `demo_mode=true`, `demo_roles=[prescritor,dispensador,paciente]`
  → interceptação dos cards da home está **ativa**.

## 3. Diagnóstico encerrado — não reinvestigar

### Hipótese A (deploy/cache) — DESCARTADA
O gate só passou porque o `seed_demo.py` corrigido (Fix 6, booleans) rodou no
`preDeployCommand` → deploy do `879c7db` concluiu. HTMLs servidos pelo mesmo serviço.
No repo: `DEV_MODE=false` (prescritor.html:861), `DEV_PRESET_CONTEXT=false`
(dispensador.html:510, prescritor.html:864).

### Hipótese OAuth2 do Z AI — FALSIFICADA (duas vezes)
1. O frontend **já envia** form-urlencoded `username`/`password`
   (dispensador.html:835-845, `URLSearchParams` + `x-www-form-urlencoded`).
2. O backend nem chega ao parsing: `backend/app/routers/login.py:50-59`,
   `_reject_if_demo()` — com `PICSAUDE_DEMO_MODE=true`, `POST /auth/token`
   devolve **403 por design** com `detail` = dict:
   `{"codigo": "demo_mode_ativo", "mensagem": "Login real desabilitado em modo demo. Use o seletor em /."}`

### Causa raiz do screenshot ("Login inválido: [object Object]")
1. Acesso direto a `dispensador.html` (sem passar pelo card) → tela de login **por design**.
2. Credenciais demo digitadas manualmente → 403 `demo_mode_ativo` **por design** (TICKET-6 P1#2).
3. `dispensador.html:848` concatena o dict `err.detail` numa string → `[object Object]`.
   **Único bug real: renderização de erro no frontend.**

Conclusão: **não há bug de login em produção.** Não existe fluxo de "farmácia real
logando" em modo demo — ele é desabilitado de propósito.

---

## 4. Escopo do P0.5 (fechar hoje)

### Tarefa 1 — code/MS: fix de renderização de erro (classe `local-extension`)
O helper correto **já existe**: `_extrairMsgErro(errData, fallback)` em
`prescritor.html:900` (trata string, lista 422 e dict com `.mensagem` — cobriria
o `demo_mode_ativo` exibindo a mensagem certa).

Ação: portar o helper para os outros 3 HTMLs e aplicar nos pontos mapeados:

```
dispensador.html : 848 (login) · 1083 · 1136 · 1321 · 1372 · 1526
clinica.html     : 858 (login) · 1073 · 1327 · 1352 · 1371 · 1393 · 1468 · 1598 · 1828 · 1854 · 1881 · 1915
cidadao.html     : 421
```

Opcional (recomendado, mesmo PR): na tela de login, se `/config/public` indicar
`demo_mode=true`, exibir aviso "Modo demonstração — use o seletor na página
inicial" com link para `/`. Evita que o próximo visitante repita o caminho do
screenshot.

Fluxo: <100 linhas, não toca núcleo → edição direta com teste, ou PR curto.
**Não tocar em `login.py`** (ver §5).

### Tarefa 2 — Fabiano: teste manual (única incógnita restante — Hipótese B/C)
Janela anônima → `picsaude.com.br` → clicar no card **Dispensador** (não digitar
URL). Esperado: dashboard direto. Repetir com **Prescritor**. Se cair em login:
F12 → Console (erros vermelhos) + Network (`/demo/login`, `/config/public`) e reportar.

### Tarefa 3 — Jules: auditoria pós-fato do `879c7db`
Diff completo; confirmar que não tocou núcleo (domain/, documento_canonico.py,
assinatura, ledger, custódia); registrar parecer.

### Critérios de fechamento do P0.5
- Card Dispensador e card Prescritor → dashboard direto em anônima, sem erro no Console.
- Login manual em demo mode exibe mensagem legível (nunca `[object Object]`).
- Parecer do Jules registrado.
- Confirmação humana (gate programático é necessário, não suficiente).

---

## 5. Guardrails específicos deste ciclo

- **NÃO "corrigir" `POST /auth/token`.** O 403 `demo_mode_ativo` é comportamento
  de design. Não trocar `OAuth2PasswordRequestForm` por JSON; não remover
  `_reject_if_demo`. Qualquer mudança ali é classe `core`-adjacente (auth) →
  portão do Conselheiro.
- Gates de verificação: python3 + `urllib.request` (curl não existe no Render Shell).
- Nunca assumir idempotência de seed sem testar contra o PostgreSQL do Render.
- Push direto em main: só com autorização explícita caso a caso (§10 CLAUDE.md).
  Padrão a partir de agora: PR.
- Nada liga `PICSAUDE_DECISAO_CLINICA`.

---

## 6. Decisão de prioridade (registrada por Fabiano em 2026-07-04)

**Sem demo externa agendada nas próximas 2 semanas → R6 é a prioridade pós-P0.5.**

- Fechado o P0.5, o code/MS retorna ao caminho crítico do piloto: **R6 — paridade
  byte-idêntica da serialização canônica WebCrypto ↔ Python** (bloqueador absoluto,
  exige teste de paridade verde + portão do Conselheiro + auditoria antes de merge).
- O **P1 da demo (paridade v27) vai para backlog**, sem data. Não iniciar sem nova
  decisão explícita de Fabiano.

## 7. Backlog P1 — paridade v27 (congelado, referência)

| Feature | Backend | Frontend | Esforço |
|---|---|---|---|
| Fila push de receitas no dashboard | NÃO | NÃO | L (4-6h) — atenção guardrail `org_id` (CLAUDE.md §6b) |
| Comprovante SNGPC COMPRADOR × PACIENTE | PARCIAL | NÃO | M (1-2h) |
| Exportação CSV SNGPC (BOM UTF-8) | PARCIAL | NÃO | M (2-3h) |
| Relatório consolidado de impressão | NÃO | NÃO | M (2h) |
| View de histórico por receita | SIM (`prescricao_eventos` via endpoint oficial — nunca SQL direto) | PARCIAL | S (1h) |

Referência de UX: `dispensador.txt` v27 (comportamento, não código — v27 é localStorage).

## 8. Formato de report (mantido do briefing anterior)

Hipótese investigada → Evidência (arquivo:linha + output) → Ação → Resultado
(status HTTP, body, comportamento) → Próximo passo. Nunca declarar "feito" sem
teste manual humano confirmado.
