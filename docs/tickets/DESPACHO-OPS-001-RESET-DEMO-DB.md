# DESPACHO OPS-001 — Reset da demo DB no Render (pós-merge do #131)

| Campo | Valor |
|---|---|
| **Despacho** | OPS-001 |
| **De** | Arquiteto (GLM-5.2) |
| **Para** | Fabiano (executa no Render) — arquiteto confirma pré-condições |
| **Data** | 2026-08-04 |
| **Origem** | Martelo Q2 do Fabiano (2026-08-04): "reset só após #131 na main; emita o despacho de ops" |
| **Pré-requisito bloqueante** | **#131 mergeado em `main` e deployado no Render** |

---

## §1 Por que só agora (e por que depois do #131)

O `DEMO-EXAME-0002` introduzido pelo seed de exames precisa nascer com o **elo de origem** `prescritor → paciente` (CLAUDE.md §2/§3: objeto sem elo de origem é órfão). Esse elo só existe na versão canônica do seed, que está no **#131** (errata `ec2708c`).

Se rodarmos o reset **antes** do #131 estar em `main` + deployado:
- O `DEMO-EXAME-0002` nasceria **órfão** (versão pré-errata do seed).
- A cadeia de custódia ficaria incompleta: `paciente → laboratório` sem o `prescritor → paciente` precedente.
- A falha é **silenciosa** (o seed é best-effort, `try/except` engole erro) — o CI ficaria verde e o órfão entraria em produção sem alarme.

Portanto: **o reset é bloqueado até o deploy do #131**.

## §2 Gatilho (condição precisa)

O reset pode ser executado quando **todas** as seguintes forem verdadeiras:

1. ✅ PR #131 mergeado em `main` (merge commit visível em `git log main`).
2. ✅ Deploy automático do Render concluído para o commit que inclui o #131 (status do serviço = `live`).
3. ✅ Confirmação de que o código deployado contém o elo de origem:
   ```bash
   # No serviço do Render (shell) ou na imagem deployada:
   grep -c "Elo de origem" /app/seed_demo.py
   # Deve retornar >= 1
   ```

Se a contagem do grep retornar 0, **ABORTAR** — o deploy não pegou o #131, e rodar o reset introduz o órfão.

## §3 Comando de execução

Conforme o docstring de `backend/scripts/reset_demo_db.py`:

```bash
cd /app && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py --sim-eu-quero
```

**Parâmetros:**
- `PICSAUDE_DEMO_MODE=true` — obrigatório (o script recusa sem isto).
- `--sim-eu-quero` — flag de confirmação de destruição (o script é destrutivo: DROP SCHEMA + remigração).

O script:
1. Faz `DROP SCHEMA` no PostgreSQL da demo.
2. Re-rodada as migrações Alembic (schema authority — CLAUDE.md §9).
3. Executa `seed_demo.py` — que agora (pós-#131) inclui o elo de origem.

## §4 Pós-reset (verificação)

1. **Confirmar que os 3 protocolos sentinela nasceram** (não confiar em "CI verde" — o seed é best-effort):
   ```sql
   -- No console do Render (PostgreSQL da demo):
   SELECT protocolo, status FROM pedidos_exame WHERE protocolo LIKE 'DEMO-EXAME-%';
   SELECT protocolo, status FROM laudos WHERE protocolo = 'DEMO-LAUDO-0001';
   -- Deve retornar 2 pedidos (0001, 0002) e 1 laudo (0001).
   ```

2. **Confirmar o elo de origem** (o objeto que justifica esperar o #131):
   ```sql
   SELECT de, para, dados_json->>'motivo' AS motivo
   FROM pedido_exame_custodia
   WHERE pedido_id = (SELECT id FROM pedidos_exame WHERE protocolo = 'DEMO-EXAME-0002')
   ORDER BY transferido_em;
   -- Deve retornar >= 2 linhas: prescritor→paciente (motivo='emissao') E paciente→laboratório.
   ```
   Se faltar a linha `prescritor → paciente`, o reset rodou contra código sem o #131 — **órfão em produção**. Relatar e re-executar após confirmar o deploy.

3. **Smoke rápido da vitrine**: acessar a demo pública e confirmar que a persona `clinica` aparece no seletor `/demo/login` e que o `DEMO-LAUDO-0001` aparece no portal do cidadão.

## §5 Janela de execução

O reset é **destrutivo** e **público** (a demo é ao vivo em `picsaude.com.br`). Recomendo:

- **Horário:** fora do horário comercial de demonstração (o Fabiano decide a janela).
- **Duração esperada:** < 2 minutos (DROP + migrate + seed).
- **Comunicação:** se houver piloto/parceiro olhando a demo, avisar antes.

## §6 ⚠️ Não fazer

- **Não** rodar o reset antes do #131 em `main` + deploy confirmado (introduz órfão §3).
- **Não** rodar sem a verificação do grep (`§2` passo 3) — é a única guarda automatizada contra deploy falso.
- **Não** rodar sem `--sim-eu-quero` (o script recusa — masRegistrar para rastreabilidade).
- **Não** rodar contra `DATABASE_URL` de produção (o script opera no schema da demo; confirmar a conexão antes).

## §7 Rollback

Se o reset falhar mid-way (DROP feito, migrate quebra):

1. O schema da demo fica vazio — a demo pública retorna erro 500.
2. **Re-executar** o script (é idempotente após DROP — nada a limpar antes).
3. Se o migrate persistir em falhar: o problema é de schema (Alembic), não de seed. Acionar o arquiteto — **não** improvisar SQL manual.

## §8 Coordenadas

| Artefato | Caminho |
|---|---|
| Script de reset | `backend/scripts/reset_demo_db.py` |
| Origem do script (PG-capaz) | `docs/tickets/TICKET-DEMO-RESET-PG.md` |
| Seed canônico (com elo) | `backend/seed_demo.py` (pós-merge do #131) |
| Ratificação do review | `docs/tickets/TICKET-REVIEW-RATIFICACAO-PR129-134.md` |
| Estados de exame/laudo | `CLAUDE.md` §5a/§5b |

---

*Despacho emitido pelo arquiteto. Pré-condição (#131 deployado) é bloqueante — não contornável. Martelo Q2 do Fabiano recebido.*
