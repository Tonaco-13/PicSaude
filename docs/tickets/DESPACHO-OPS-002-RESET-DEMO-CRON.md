# DESPACHO OPS-002 — Reset diário automatizado da vitrine (cron do Render)

| Campo | Valor |
|---|---|
| **Despacho** | OPS-002 |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa o PR) — **Fabiano aplica o Blueprint** |
| **Data** | 2026-08-27 |
| **Classe** | `ops` — `render.yaml` + guarda de verificação num script de ops + docs. Nenhuma semântica clínica, ledger, estado ou custódia é tocada |
| **Origem** | Pergunta do Fabiano ao engenheiro (27/08): *"vamos limpar os objetos sanitários da demo? tem como fazer isso periodicamente e automaticamente?"* — parecer do engenheiro confirmado pelo arquiteto contra o código |
| **Estado** | 🟢 **Martelado (Fabiano, 27/08)**: M1 autorizado, M2 = diário 04:00 BRT. Implementação liberada ao engenheiro — o "Apply" do Blueprint segue sendo gesto do Fabiano |
| **Parecer do engenheiro** | ✅ Recebido e incorporado (27/08) — §9. Viabilidade confirmada; **uma emenda aceita** (§4.1) |

---

## §0 A pergunta, e a resposta em uma linha

**Limpar:** sim — e "limpar objetos sanitários" tem **uma única forma legal**: o reset
inteiro que já existe (`reset_demo_db.py`, versionado desde o #124a). **Periodicamente
e automaticamente:** sim — via **cron service do Render, declarado no `render.yaml`**,
com a credencial nunca saindo da custódia da plataforma. Este despacho especifica o
formato exato e as duas guardas novas que a automação exige.

## §1 Os dois fatos que moldam a solução (confirmados no código)

**1. Não existe meio-termo — e isso é força, não limitação.** O ledger é imutável por
**trigger de banco** (16 triggers de imutabilidade + 1 de saldo efetivo, §3.2 do
docstring do script): o Postgres **recusa fisicamente** UPDATE/DELETE nas tabelas
clínicas. "Limpar só as excursões, preservando seed" não é uma opção mais cara — é
tecnicamente inviável, e ceder à conveniência da demo não está em pauta. O caminho
sancionado é o destrutivo-total: `DROP SCHEMA CASCADE → alembic upgrade head →
seed_demo.main()` — apaga tudo (inclusive catálogo) e reconstrói do canônico.

**2. A credencial da vitrine não circula — nunca circulou.** O docstring §5 do script
declara: *"NENHUM agente recebe a DATABASE_URL da vitrine — a execução no Render é de
Fabiano."* Automatizar **não pode** significar um agente (ou um job disparado por
agente, ou uma secret de terceiros) segurando essa credencial. O que automação significa
aqui: **a própria plataforma executa**, com a `DATABASE_URL` injetada pelo Render no
runtime do job — do mesmo jeito que já faz para o web service. Nenhum agente vê, ninguém
dispara na mão, a custódia da credencial continua inteira dentro do Render.

O script **já antecipou esta exata forma de uso**: o docstring §3.3/§3.4 e
`_confirmacao_ok` contemplam explicitamente "job não-interativo no Render" via
`--sim-eu-quero`. As guardas de ambiente (`PICSAUDE_ENV` ≠ prod, `PICSAUDE_DEMO_MODE =
true`) estão preservadas "mesmo em automação" (comentário do próprio `_checar_guardas`).
**Zero mudança obrigatória no caminho de destruição.**

## §2 A decisão de desenho (arquiteto)

**Veículo: bloco `cron` no `render.yaml` — não configuração só no dashboard.**

Responde à pergunta que o engenheiro deixou em aberto ("preparo o bloco yaml, ou você
configura no dashboard e eu fico de fora?"): **prepara o bloco yaml.** Motivos:

- **Infra versionada é auditável e sobrevive ao re-provisionamento.** Config de
  dashboard é invisível ao repo — perderia-se num rebuild da conta, e ninguém que
  clona o repo (lição do Quick Start, #200) saberia que o reset diário existe.
- **O gate do Fabiano permanece o "Apply".** O blueprint é manual-sync por decisão
  dele: o Render propõe o diff, ninguém aplica sozinho. Automatizar a **execução**
  não automatizou o **deploy da automação**.

**Por que não GitHub Actions agendado** (os `cron` de `gates.yml`/`gates-browser.yml`
são 06:00/06:20 UTC e só tocam CI sintético — não confundir): um workflow agendado
precisaria da `DATABASE_URL` como secret do GitHub — duplicando a custódia da credencial
**para fora do Render**. Rejeitado por violar o §1.2 no nascedouro.

**Por que diário, e não "só quando estiver sujo":** detectar sujeira exige régua do que
é seed vs. excursão — estado extra para poupar um job de 2 minutos. O simples e honesto:
todo dia de madrugada, vitrine nova de manhã.

## §3 O bloco `render.yaml` (spec literal)

```yaml
  # ── Reset diário da vitrine (DESPACHO-OPS-002) ──────────────────────────
  # DROP SCHEMA → alembic upgrade head → seed_demo — destrutivo POR DESIGN.
  # As guardas do script continuam valendo: aborta em PICSAUDE_ENV=prod,
  # exige PICSAUDE_DEMO_MODE=true, e --sim-eu-quero é o assentimento
  # não-interativo do §3.3 (alvo ecoado no log antes do DROP).
  # Manual-sync: NADA disto aplica sem o "Apply" do Fabiano no dashboard.
  - type: cron
    name: picsaude-demo-reset
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .
    plan: starter            # conferir custo/plano na tela de Apply, como o db
    schedule: "0 7 * * *"    # 07:00 UTC = 04:00 America/Sao_Paulo (UTC−3 fixo) — §5
    dockerCommand: python3 scripts/reset_demo_db.py --sim-eu-quero
    envVars:
      - key: PICSAUDE_ENV
        value: stg
      - key: PICSAUDE_DEMO_MODE
        value: "true"
      - key: DATABASE_URL
        fromDatabase:
          name: picsaude-db
          property: connectionString
```

Notas de implementação para o engenheiro:

- `dockerCommand` sobrepõe o CMD do Dockerfile (que sobe uvicorn) — sem ele, o "cron"
  rodaria o servidor. Validar a sintaxe do campo contra a doc atual do Render (o
  cabeçalho do próprio yaml avisa que o blueprint nunca foi validado contra deploy real).
- O `WORKDIR /app` do Dockerfile deixa o script em `/app/scripts/reset_demo_db.py` —
  o `dockerCommand` acima já resolve o caminho relativo.
- Verificar que a cadeia de imports do script (`app.database` → `app.config`) não exige
  `PICSAUDE_JWT_SECRET` em runtime — a checagem de segredo mora no boot do `main.py`,
  não no import; se algum import exigir, declarar a env no bloco com `generateValue`.
- Região: preferir a mesma do `picsaude-db` (latência do DROP/seed) — conferir na tela
  de Apply e anotar no yaml se o campo for necessário.
- `plan` tem default para cron novo (0.5c-512mb) se omitido — mantemos `starter`
  explícito pelo AC 6 (custo visível na hora do Apply); simplificar depois é uma linha.

## §4 A guarda nova que a automação exige: sentinela pós-seed

O OPS-001 §1 documentou o modo de falha: **o seed é best-effort (`try/except` engole
erro)** — a vitrine pode meio-semar **silenciosamente**. No caminho manual, o verificador
era o Fabiano (OPS-001 §4, checklist SQL de sentinelas). Um cron diário não tem
verificador humano: **a verificação precisa virar código**, ou a automação fabrica
meio-seeds mudos toda madrugada com o job marcando sucesso.

**Emenda no `reset_demo_db.py`** (ainda `ops` — é pós-condição de ferramenta, não
semântica clínica): ao fim do `main()`, conferir que as **sentinelas de protocolo que o
próprio seed declara** nasceram — no mínimo o trio canônico do OPS-001 §4
(`DEMO-EXAME-0001`, `DEMO-EXAME-0002`, `DEMO-LAUDO-0001`); a lista completa
(`DEMO-FILA-0001`, `DEMO-ATESTADO-0001`, …) sai de **uma única fonte**, o
`seed_demo.py` — não hardcodar no despacho uma lista que apodrece. Faltando qualquer
uma: mensagem explícita no stdout e **exit ≠ 0** — o Render marca o job como falho e
o erro fica visível no dashboard, em vez de silêncio verde.

Testes (vermelho antes do verde):

- seed sabotado (sentinela suprimida por monkeypatch) → `main` termina com exit ≠ 0 e
  nomeia a sentinela ausente;
- percurso feliz no dialeto SQLite de dev → exit 0.

**§4.1 — A segunda guarda: `lock_timeout` no DROP** *(emenda do parecer do engenheiro,
aceita pelo arquiteto, mesma PR e mesma classe `ops` — sem martelo novo).*

O buraco, nomeado: sem `lock_timeout`, se o pool do web service tiver uma transação
aberta segurando lock em qualquer tabela do schema, o `DROP SCHEMA CASCADE` espera
**indefinidamente** — o job morre no timeout opaco da plataforma, e **a sentinela do §4
nunca é alcançada**: não sai exit ≠ 0 nomeado, só um "job timed out" mudo no Render. A
guarda de verificação só protege resets que **terminam**; esta guarda garante que o
reset termine.

A emenda: `SET lock_timeout = '15s'` imediatamente antes do DROP, na mesma transação de
`_reset_postgres()`. É `lock_timeout` e não `statement_timeout` de propósito — o
primeiro erra **especificamente em contenção** (SQLSTATE 55P03); o segundo abortaria até
um DROP legitimamente lento sem contenção nenhuma. Descartado de propósito:
`pg_terminate_backend()` nas conexões do web — mataria transações alheias por conta
própria; "falhar alto" não pode virar "silenciar o outro lado". Uma linha, ramo PG,
beneficia o caminho manual de graça.

**Emenda de declaração no mesmo PR** — o docstring §5 diz hoje *"a execução no Render é
de Fabiano"*; com o cron, passa a ser de Fabiano **ou do cron do Render configurado por
ele** — agente continua fora, sempre. Declarado e executado não podem divergir (a lição
do vocabulário do encaminhamento). A primeira metade da frase — *nenhum agente recebe a
DATABASE_URL* — **não muda uma vírgula**.

## §5 Janela e cadência

**Diário, 07:00 UTC = 04:00 America/São_Paulo** (UTC−3 fixo — o Brasil não tem DST).

- O porquê da madrugada: o reset dura < 2 min (OPS-001 §5), mas **derruba qualquer
  sessão no meio do fluxo** — a vitrine é sempre-ligada por decisão de 16/06. Às 04:00
  o tráfego real é mínimo.
- **A equivalência UTC↔BRT vai escrita inline no yaml** (comentário do `schedule`).
  Esta casa já foi mordida duas vezes pela armadilha UTC-vs-local (o 500 do
  faturamento por fuso; o #192, janela de relatório que o CI nunca via porque rodava
  em UTC). O agendamento do Render é em UTC; quem mexer na linha precisa ver as duas
  horas ao mesmo tempo.
- Nota: não há conflito com os gates de CI (06:00/06:20 UTC) — rodam em runners do
  GitHub, sem contato com a vitrine. Corrida com deploy simultâneo às 04:00 BRT é
  teoricamente possível (predeploy migrando enquanto o job derruba o schema) e
  probabilisticamente irrelevante — registrado, não guardado.

## §6 Critérios de aceite

1. `render.yaml` declara o cron service conforme §3; sem `dockerCommand` o job subiria
   o servidor — o AC é que o comando executado é o reset, com `--sim-eu-quero`.
2. Reset que termina com seed incompleto termina com **exit ≠ 0** e sentinela ausente
   nomeada no log — nos dois dialetos.
3. Nenhuma guarda do script é enfraquecida: `PICSAUDE_ENV=prod` aborta;
   `PICSAUDE_DEMO_MODE` obrigatório; sem `--sim-eu-quero` e sem TTY, aborta antes do
   DROP (comportamento atual de `_confirmacao_ok` preservado).
4. Docstring §5 reescrito: execução por Fabiano ou pelo cron configurado por ele;
   "nenhum agente recebe a DATABASE_URL" intacto.
5. Nada aplica sozinho: o PR entra com a nota de que o Fabiano precisa aplicar o
   Blueprint sync no dashboard (manual-sync, como `PICSAUDE_DECISAO_CLINICA`).
6. O corpo do PR lista o custo recorrente novo (serviço cron no plano) para decisão
   consciente no Apply.
7. DROP sob contenção de lock termina em **falha nomeada** em ≤ 15 s (SQLSTATE 55P03)
   — não em hang até o timeout da plataforma; o `SET lock_timeout` precede o DROP na
   mesma transação, e o erro chega ao log antes de qualquer sentinela contar algo.

## §7 Martelos pendentes do Fabiano (nada abre sem eles)

> **MARTELADOS em 27/08 pelo Fabiano:** M1 ✅ autorizado · M2 ✅ diário, 04:00 BRT.
> O **Apply do Blueprint** continua sendo o terceiro gesto — embutido, não explícito:
> sem ele, o bloco é texto.

- **M1 — Autorizar a execução automatizada em si.** A frase no código diz que a
  execução no Render é sua; este despacho a estende ao cron do Render. A custódia da
  credencial não muda (permanece 100% dentro do Render) — o que muda é o **gesto**: de
  manual-your para platform-scheduled-by-you. É sua linha, seu martelo.
- **M2 — A cadência.** Proposto: diário, 04:00 BRT. Alternativas (semanal, horário
  diferente) são uma linha de `schedule`. O martelo é seu; o §5 documenta o trade-off.

O **Apply do Blueprint** é o terceiro gesto — embutido, não explícito: sem ele, o bloco
é texto.

## §8 O que NÃO muda

- As guardas do `reset_demo_db.py` (ambiente, alvo, assentimento) — nenhuma é
  contornada pela automação; o script foi desenhado para isto.
- O caminho manual continua íntegro e first-class: OPS-001 §2 (pré-condições) e §4
  (verificação) seguem sendo o checklist de toda execução manual.
- Este despacho **suplanta apenas o §5 do OPS-001** (janela de execução: de "Fabiano
  decide na hora" para "04:00 BRT, diário") — e só quando martelado.
- Blueprint manual-sync; gates de CI; predeploy por deploy.

---

## §9 Parecer do engenheiro (recebido e incorporado, 27/08)

Conferido contra o código, não contra a leitura. Vereditos:

| Ponto | Veredito |
|---|---|
| `dockerCommand` em `type: cron` + `runtime: docker` | ✅ confere na spec oficial do Render (consultada via docs, não memória) |
| `PICSAUDE_JWT_SECRET` na cadeia de imports do script | ✅ não exige — fallback em `app/config.py:33`; a guarda real mora no boot (`app/main.py:89`, só `PICSAUDE_ENV=prod`); o script nunca importa `app.main` |
| Lista de sentinelas do §4 | ✅ as **5** são exaustivas e todas chamadas dentro de `main()`: `DEMO-EXAME-0001/0002`, `DEMO-LAUDO-0001`, `DEMO-FILA-0001`, `DEMO-ATESTADO-0001` — os demais hits de `DEMO-` são `unidade_id`, não protocolo |
| WORKDIR/COPY no container; HEALTHCHECK | ✅ `alembic.ini`, `seed_demo.py` e `scripts/` caem onde `_BACKEND_ROOT` espera; HEALTHCHECK não interfere em job one-shot |
| **Gap: `lock_timeout` no DROP** | **Emenda aceita — incorporada no §4.1 e no AC 7** |

Nada implementado — aguarda os martelos do §7, como mandava o despacho.

---

*Despacho do arquiteto, 2026-08-27, a partir do parecer do engenheiro conferido contra
`reset_demo_db.py` (docstring §2/§3.2/§3.3/§5), `render.yaml` e DESPACHO-OPS-001.
Emendado no mesmo dia com o parecer de viabilidade (§9). Implementação é do engenheiro;
os martelos do §7 são do Fabiano.*
