# TICKET-F5-B5 — Gate de CI para o teste browser externo (contra picsaude.com.br)

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — Fatia B, ticket de infraestrutura |
| **Classe** | `ops` (CI/CD) |
| **Para** | Revisor de tickets → engenheiro devops → martelo Fabiano |
| **Origem** | Dívida deixada pelo TICKET-F5-B4 (teste browser externo): o teste existe, mas não tem gate de CI que o rode. |
| **Pré-requisito** | `main` atual com `backend/tests/browser/test_f5_externo_picsaude.py` mergeado (TICKET-F5-B4). |

## §1 Contexto (não reabrir)

O TICKET-F5-B4 estabeleceu o padrão "teste browser contra URL externa" pela primeira vez no repo. O arquivo `test_f5_externo_picsaude.py` cobre a dívida dos tickets B1/B2/B3 (browser-E2E que nunca foi escrito quando a Fatia B foi mergeada). Por decisão do Fabiano (sessão de 2026-07-25), o B4 entregou **só o arquivo** — gate de CI ficou separado pra não misturar preocupações.

Este ticket (B5) fecha esse ciclo: criar o workflow que roda o teste externo numa cadência que faça sentido (a demo pública reseta diariamente; um gate por PR seria caro e não-determinístico).

### Por que este ticket é `ops` e não `module`

Não altera semântica clínica nem UI. Cria um workflow de CI novo. Não toca em `app_demo`, `gates.yml`, ou no gate de PR existente (`gates-browser.yml`).

## §2 Invariantes (não-negociáveis)

- **R1 (reprodutibilidade):** o teste externo nunca derruba o gate de PR — falha de rede não é falha de build.
- **§10 (PII):** o workflow não loga JWT nem dados de paciente; só logs de asserção do Playwright.
- **Não-acoplamento com gates.yml:** o gate principal (unit + integration) continua sem dependência de rede.

## §3 Spec de implementação

### 3.1 Workflow novo: `.github/workflows/gates-browser-externo.yml`

Triggers:
```yaml
on:
  schedule:
    - cron: "30 6 * * *"        # 06:30 UTC diário (após o reset da demo)
  workflow_dispatch:             # gatilho manual
    inputs:
      demo_url:
        description: "URL da demo (default: picsaude.com.br)"
        required: false
        default: "https://picsaude.com.br"
```

Job único:
```yaml
jobs:
  externo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Instalar deps
        working-directory: backend
        run: |
          pip install -r ../requirements-browser.txt
          python -m playwright install --with-deps chromium
      - name: Teste externo
        working-directory: backend
        env:
          PICSAUDE_DEMO_URL: ${{ github.event.inputs.demo_url || 'https://picsaude.com.br' }}
        run: |
          python -m pytest tests/browser/test_f5_externo_picsaude.py -v -m external \
            --screenshot=only-on-failure \
            --tracing=retain-on-failure \
            --output=test-results
      - name: Publicar rastro de falha
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: smokes-externo-falha
          path: backend/test-results/
          if-no-files-found: ignore
```

### 3.2 Ativação dos artefatos de falha

O workflow `gates-browser.yml` (CI existente) já tem o passo `actions/upload-artifact` para `backend/test-results/`, mas nada escreve lá. Os testes externos escrevem ao adicionar `--screenshot=only-on-failure --tracing=retain-on-failure --output=test-results` à invocação do pytest. Quando um teste falha, sobe:

- **Screenshot PNG** do momento da falha
- **Trace** do Playwright (clicável em trace.playwright.dev)
- **Vídeo** da execução

### 3.3 Por que nightly e não por PR

- **Custo:** cada run baixa chromium (~150 MB) e executa 6 cenários que mutam a demo pública.
- **Não-determinismo:** a demo pública é resetada diariamente (`proximo_reset` em `/config/public`); um PR às 14:50 pode falhar porque a demo está prestes a resetar às 15:00.
- **Isolamento:** múltiplos PRs rodando simultaneamente competiriam pela mesma demo.

O nightly pós-reset (`06:30 UTC`) é a janela estável. Para validação ad-hoc, `workflow_dispatch` com input de URL permite apontar para preview de PR.

## §4 Critérios de aceite

1. Workflow `gates-browser-externo.yml` criado, com os 3 triggers (cron, dispatch, dispatch com input).
2. Execução manual (workflow_dispatch) verde contra `https://picsaude.com.br`.
3. Execução nightly verde por 3 dias consecutivos (estabilidade).
4. Em falha simulada (ex: quebrar um seletor), os artefatos (screenshot + trace) são publicados e baixáveis.
5. `gates.yml` (gate de PR principal) **não foi alterado** — confirmação por diff.
6. `gates-browser.yml` (gate de PR de HTML) **não foi alterado** — confirmação por diff.

## §5 Fora de escopo

- Testar contra a farmácia Norte (`99999999000272`) como controle negativo do B1 §5.n.7 — fica como extensão futura do B4.
- Browser Firefox/WebKit — repo é chromium-only.
- Webhooks de notificação de falha (Slack/email) — dívida de observabilidade separada.
- Métricas de uptime da demo pública — dívida de ops separada.

## §6 Não fazer

- Não adicionar o teste externo ao gate de PR (path-filter do `gates-browser.yml`) — ele depende de rede.
- Não logar JWT ou PII nos logs do CI.
- Não usar `continue-on-error` — falha de demo real deve ser visível.
- Não rodar contra picsaude.com.br fora da janela pós-reset sem justificativa.
