# Deploy no Render — PicSaúde (Etapa 8)

> Blueprint: [`render.yaml`](../render.yaml) na raiz. Este documento é o checklist
> operacional. Pré-requisito fechado: gap `estabelecimentos_cnes` ausente na PG
> (degradação graciosa no login-prestador — branch `fix/estabelecimentos-cnes-pg`).

## 1. Variáveis de ambiente (prod)

| Variável | Origem | Obrigatória | Observação |
|---|---|---|---|
| `PICSAUDE_ENV` | `render.yaml` → `prod` | ✅ | Ativa o guard de boot (recusa SQLite + JWT default) |
| `DATABASE_URL` | `fromDatabase` (auto) | ✅ | Render injeta do `picsaude-db`. Normalizado `postgres://`→`postgresql://` no código |
| `PICSAUDE_JWT_SECRET` | `generateValue` (auto) | ✅ | ≥32 chars, sem `TROQUE_EM_PRODUCAO` — senão o boot falha (5D guard) |
| `PICSAUDE_BASE_URL` | manual (`sync: false`) | ✅ | `https://<serviço>.onrender.com` — usado em links/tokens |
| `PICSAUDE_DEMO_MODE` | **não setar** | — | Ausente = `false`. Em prod real não há seletor de papéis demo |
| `PFX_ENCRYPTION_KEY` | manual | ⛔ só se assinatura real | Hoje stub; setar quando sair do stub ICP-Brasil. NUNCA no repo |

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
- [ ] Boot **não** caiu no guard (logs sem "JWT_SECRET inseguro" / "SQLite em prod").
- [ ] `alembic upgrade head` aplicou todas as migrations (logs do preDeploy).
- [ ] Login-prestador (caminho 200) não dá 500 mesmo sem `estabelecimentos_cnes`
      carregada → `cnes_verificado: false` (degradação graciosa).
- [ ] Um POST de emissão digital persiste e o ledger registra o evento.

## 4. Pendências conhecidas (não bloqueiam o deploy)

- **`estabelecimentos_cnes` vazia na PG**: o login degrada graciosamente
  (`cnes_verificado: false`). Carga/migração do snapshot CNES é trabalho separado.
- **Planos pagos** (web `starter` + Postgres `basic-256mb`): decisão de Fabiano
  (2026-06-16) — domínio próprio `picsaude.com.br`, então a casa não pode hibernar
  nem a gaveta expirar. Custo ~lanche/mês por serviço; confirmar slugs na tela de Apply.

> ⚠️ O `render.yaml` é fiel ao código, mas **não foi validado contra um deploy
> Render real**. Tratar o primeiro deploy como smoke test, conferindo os logs.
