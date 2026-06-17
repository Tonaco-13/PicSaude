# Deploy no Render — PicSaúde (Etapa 8)

> Blueprint: [`render.yaml`](../render.yaml) na raiz. Este documento é o checklist
> operacional. Pré-requisito fechado: gap `estabelecimentos_cnes` ausente na PG
> (degradação graciosa no login-prestador — branch `fix/estabelecimentos-cnes-pg`).

## 1. Variáveis de ambiente (vitrine de demonstração)

> A vitrine pública roda em **modo demonstração** (`stg` + `DEMO_MODE`), **não** em
> `prod`: o boot **proíbe** prod+demo simultâneos, e o objetivo é o visitante
> percorrer o loop **sem barreira de login** (seletor de papéis), com dados fictícios.
> A própria casa serve as telas (vitrine "uma casa só", mesma origem, sem CORS).

| Variável | Origem | Obrigatória | Observação |
|---|---|---|---|
| `PICSAUDE_ENV` | `render.yaml` → `stg` | ✅ | Não-prod por design (prod+demo é recusado no boot) |
| `PICSAUDE_DEMO_MODE` | `render.yaml` → `true` | ✅ | Seletor de papéis + dados fictícios + telas servidas pela casa |
| `DATABASE_URL` | `fromDatabase` (auto) | ✅ | Render injeta do `picsaude-db`. Normalizado `postgres://`→`postgresql://` no código |
| `PICSAUDE_JWT_SECRET` | `generateValue` (auto) | ✅ | Render gera segredo forte (login real fica desligado no demo, mas mantido robusto) |
| `PICSAUDE_BASE_URL` | manual (`sync: false`) | ✅ | `https://<serviço>.onrender.com` — usado em links/tokens |
| `PICSAUDE_FRONTEND_DIR` | Dockerfile → `/app/frontend` | auto | Onde os HTMLs foram copiados; o `main.py` resolve daí |
| `PFX_ENCRYPTION_KEY` | manual | ⛔ só se assinatura real | Hoje stub; setar quando sair do stub ICP-Brasil. NUNCA no repo |

> **Para um deploy real `prod`** (login real, futuro piloto): `PICSAUDE_ENV=prod`
> e **sem** `PICSAUDE_DEMO_MODE` — aí a casa expõe só a API e as telas ficam num
> host estático. É outro deploy, com onboarding — fora do escopo da vitrine.

## 2. Passos

1. **Render → New → Blueprint** → conectar `github.com/Tonaco-13/PicSaude`.
2. Render lê `render.yaml`: provisiona `picsaude-db` (Postgres) + `picsaude-backend` (Docker).
3. Setar manualmente `PICSAUDE_BASE_URL` (a URL só existe após o 1º deploy — pode
   setar depois e re-deployar).
4. **Apply**. Na tela de Apply, conferir os **planos pagos** (web `starter`, Postgres
   `basic-256mb` ou o slug equivalente que a Render mostrar) — escolha deliberada de
   não-hibernar/não-expirar. O `preDeployCommand` roda `alembic upgrade head`.
5. Verificar: `GET https://<serviço>.onrender.com/health` → `200`.

### Ligar o domínio `picsaude.com.br` (depois do 1º deploy)

1. Render → serviço `picsaude-backend` → **Settings → Custom Domains** → adicionar
   `picsaude.com.br` (e/ou `www.picsaude.com.br`).
2. A Render mostra um registro **CNAME** (ou A/ALIAS para o apex). Criar esse registro
   no painel de DNS onde o `picsaude.com.br` foi comprado (ex: Registro.br).
3. Esperar a propagação (minutos a horas) — a Render emite o **HTTPS automático**.
4. Atualizar `PICSAUDE_BASE_URL` para `https://picsaude.com.br` e re-deployar.

## 3. Verificações pós-deploy

- [ ] `/health` retorna `200`.
- [ ] **`GET /` abre a porta de entrada** (seletor de papéis: Prescritor · Dispensador
      · Cidadão · Validação) — a vitrine "uma casa só" servindo o loop.
- [ ] `alembic upgrade head` aplicou todas as migrations (logs do preDeploy).
- [ ] Login-prestador (caminho 200) não dá 500 mesmo sem `estabelecimentos_cnes`
      carregada → `cnes_verificado: false` (degradação graciosa).
- [ ] Um POST de emissão digital persiste e o ledger registra o evento (vivo).

## 4. Pendências conhecidas (não bloqueiam o deploy)

- **`estabelecimentos_cnes` vazia na PG**: o login degrada graciosamente
  (`cnes_verificado: false`). Carga/migração do snapshot CNES é trabalho separado.
- **Planos pagos** (web `starter` + Postgres `basic-256mb`): decisão de Fabiano
  (2026-06-16) — domínio próprio `picsaude.com.br`, então a casa não pode hibernar
  nem a gaveta expirar. Custo ~lanche/mês por serviço; confirmar slugs na tela de Apply.

> ⚠️ O `render.yaml` é fiel ao código, mas **não foi validado contra um deploy
> Render real**. Tratar o primeiro deploy como smoke test, conferindo os logs.
