# TICKET-GOV-BOT-REVISOR — Conta/bot de Revisor com identidade GitHub própria

| Campo | Valor |
|---|---|
| **ID** | TICKET-GOV-BOT-REVISOR |
| **Classe** | `ops` (infraestrutura de governança — não afeta código de produção) |
| **Estado** | 🟡 **REGISTRADO** — gatilho definido, não executar antes do gatilho |
| **Origem** | Martelo Q1=(a) do Fabiano (2026-08-04): "abra ticket para (a) (bot de Revisor) com gatilho 'primeiro colaborador externo ou piloto real'" |
| **Para** | Fabiano (setup) → arquiteto ratifica |
| **Cobertura provisória** | Q1=(b) disciplina humana (review comment + assinatura do Fabiano) — válido até este ticket executar |

---

## §1 Por que (problema de hoje)

O GitHub **proíbe** `gh pr approve` / `gh pr request-changes` no próprio PR. Hoje o Revisor (Claude Code) e **todos os autores** de PR (Kimi 3, Engenheiro, Fabiano) compartilham a mesma conta GitHub (`Tonaco-13`).

Consequência: o estado formal de review (✅ approve / 🔴 request-changes) **não é mecanicamente executável**. O Revisor registra os vereditos como *review comment* com o parecer no corpo — válido como **trilha de auditoria**, mas não trava `branch protection`.

O "gate bloqueante" hoje depende de **disciplina humana** (alguém ler o comentário do Revisor antes de mergear). Funciona no modelo atual (1 operador, alta confiança), **quebra** quando entra colaborador externo ou piloto real — exatamente os gatilhos que o Fabiano definiu.

## §2 O que resolve (objetivo)

Uma conta/bot de Revisor com identidade GitHub própria permite:

1. **Aprovar / pedir-mudanças de fato** — o estado formal trava branch protection.
2. **Gate mecanicamente executável** — branch protection rejeita merge sem approve do bot.
3. **Separação de papéis auditável** — autor ≠ revisor no histórico do PR.
4. **Escalabilidade** — válido quando o time crescer além do Fabiano operando tudo.

## §3 Gatilho (não executar antes)

O setup só deve ser executado quando **qualquer** destes ocorrer (o que vier primeiro):

- **G1 — Primeiro colaborador externo.** Qualquer pessoa fora da conta `Tonaco-13` abrindo PR ou pedindo acesso. Neste ponto a disciplina humana deixa de ser suficiente (o Revisor não pode mais assumir que o autor = Fabiano).
- **G2 — Piloto real.** Quando a demo pública (`picsaude.com.br`) passar de "vitrine interna" para "piloto com usuários reais" (parceiro, cliente, hospital). O risco de um merge indevido sai do realm de "reinicia a demo" e entra no realm de "expõe dado real".
- **G3 — Segundo operador.** Qualquer outra pessoa (estagiário, dev contratado, parceiro técnico) passando a committar com regularidade.

Até lá: **Q1=(b) prevalece** (disciplina humana + review comment).

## §4 O que criar (quando o gatilho disparar)

### Opção A — Conta de bot (recomendada)

1. Criar uma conta GitHub de uso do Revisor (ex.: `picsaude-revisor-bot`).
2. Adicionar como colaborador no repo com permissão de leitura + review.
3. Gerar um **Personal Access Token** (fine-grained, escopos: `pull_requests: write` para approve/request-changes).
4. Configurar o token no ambiente onde o Revisor roda (variável de ambiente, nunca no repo).
5. O Revisor passa a usar `gh` autenticado como o bot — `gh pr approve` / `gh pr request-changes` funcionam.
6. Adicionar o bot como **required reviewer** no branch protection de `main`.

### Opção B — GitHub App (mais robusto, mais setup)

Se o time for crescer muito ou houver requisito de auditoria formal:
- Criar um GitHub App (instalado no repo), com permissões `pull_requests: write`.
- Mais setup, mas não consome seat (se a organização for criada).
- Deferir para depois do piloto se a Opção A bastar.

**Recomendação do arquiteto:** Opção A no primeiro gatilho (rápida, resolve o problema); migrar para Opção B se/when o time passar de 3 operadores.

## §5 Branch protection (configuração no GitHub)

Após o bot criado (Opção A), configurar branch protection em `main`:

| Regra | Valor |
|---|---|
| Require pull request before merging | ✅ |
| Required approvals | **1** (do bot de Revisor) |
| Dismiss stale pull request approvals when new commits are pushed | ✅ |
| Require status checks to pass | ✅ (CI existente) |
| Restrict who can push to matching branches | ✅ (apenas admin) |

Isto torna o gate **mecanicamente executável**: nem o Fabiano consegue mergear sem o approve do bot.

## §6 Não fazer

- **Não** executar o setup antes do gatilho (G1/G2/G3) — overhead sem benefício no modelo atual.
- **Não** commitar o token do bot no repo (nem em `.env`, nem em docs) — sempre variável de ambiente.
- **Não** dar permissão de `admin` ou `write` ao bot — só review + read.
- **Não** desligar a disciplina humana (review comment do Revisor) mesmo depois do bot — defense in depth.

## §7 Pré-requisitos a confirmar (no disparo)

- Conta GitHub disponível para o bot (email único, sem conflito com `Tonaco-13`).
- Permissão de admin no repo para configurar branch protection (Fabiano tem).
- Ambiente do Revisor consegue ler variável de ambiente (confirmar onde o Claude Code roda hoje).

## §8 Custos/benefícios

| | Hoje (Q1=b) | Após este ticket (Q1=a) |
|---|---|---|
| Gate mecanicamente executável | ❌ (disciplina) | ✅ (branch protection) |
| Custo de setup | zero | 1 conta + 1 token + config |
| Trilha de auditoria | review comment (bom) | approve/reject formal (melhor) |
| Escala com colaboradores | frágil | robusto |

## §9 Coordenadas

| Artefato | Caminho |
|---|---|
| Ratificação que motivou este ticket | `docs/tickets/TICKET-REVIEW-RATIFICACAO-PR129-134.md` § "Q1" |
| Workflow de PR review | este ticket + `CLAUDE.md` (governança) |

---

*Ticket `ops` registrado. Gatilho definido pelo Fabiano (2026-08-04): "primeiro colaborador externo ou piloto real". Até lá, Q1=(b) disciplina humana prevalece.*
