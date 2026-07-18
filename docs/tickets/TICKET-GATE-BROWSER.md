# TICKET-GATE-BROWSER — smokes de navegador (opção C, híbrido)

**Classe:** `ops` (workflow + testes) · com um achado `core` embutido (ver §5)
**Origem:** o defeito do PR #103 — o seletor de conselho do atestado ficava vazio
por *temporal dead zone*, e nenhum gate pegou.

---

## 1. A decisão

Adotar **pytest-playwright** com escopo **mínimo**, em duas camadas:

| Camada | Onde | Quando roda | Pergunta que responde |
|---|---|---|---|
| Guardas estáticas | `tests/unit/test_frontend_atestado.py` (8 testes, já existiam) | **todo PR** | "o código está na ordem certa?" |
| Smokes de navegador | `tests/browser/` (novo) | **só PR que toca `**.html`** + nightly | "a tela abre?" |

O defeito do #103 só nasce em PR que toca a tela. Rodar um navegador num PR de
ledger é pagar por nada. Estático é a primeira linha (rápido, todo PR);
navegador é a segunda, onde o estático é cego.

### Por que playwright-python, e não Puppeteer/Cypress

O repo é **Python puro** — não há `package.json` nem `node_modules`.
`pytest-playwright` roda dentro do pytest que já existe e traz o próprio
Chromium (não depende de Chrome no runner). Puppeteer ou Cypress trariam uma
toolchain Node inteira para quatro smokes.

---

## 2. O que foi entregue

| Arquivo | Papel |
|---|---|
| `.github/workflows/gates-browser.yml` | Workflow **separado** do `gates.yml`. `paths: ['**.html', …]` + cron nightly + `workflow_dispatch` |
| `backend/tests/browser/conftest.py` | Sobe o app em DEMO_MODE contra SQLite efêmero; coleta erros de JS/rede |
| `backend/tests/browser/test_smokes.py` | Os 4 smokes |
| `requirements-browser.txt` | `pytest-playwright`, **fora** do `requirements.txt` para não onerar o gate principal |

Os smokes ficam fora de `tests/unit` e `tests/integration` de propósito — o gate
atual chama essas duas pastas **por nome**, então não é afetado. Um `pytest` cru
a partir de `backend/` também não quebra para quem não instalou o extra: o
`conftest` da pasta se auto-ignora se o Playwright não estiver presente.

### Os 4 smokes

| # | Smoke | Marcadores auditados |
|---|---|---|
| a | Portal → cada card entra no módulo | 5 cards, `<body>` monta |
| b | Fila do dispensador | `.fila-saldo` **com unidade** · `.fila-selo-controlado` presente |
| c | Prescritor → aba Atestado: seletor de conselho **populado** | valores `CFM`/`CFO` **e** rótulos `CRM`/`CRO` |
| d | Zero erro de console em cada tela | `pageerror` · `console.error` · respostas ≥ 400 |

É **smoke, não regressão de UI**. Nada de pixel, cor ou espaçamento — isso
envelhece mal e vira ruído.

#### Nota sobre o smoke (d)

Recusa de autenticação é o app **funcionando**. `clinica.html` não tem persona no
`/demo/login` (a própria tela avisa), então `POST /auth/token` responde 403 numa
visita anônima. O coletor tolera **401/403** e nada mais — um 500 ou um 404 de
asset continuam derrubando o smoke. A tolerância é por *status + URL* (listener
de `response`), não por casar texto de console.

---

## 3. Teste de mutação — o aceite

> "Guarda que não falha quando deveria é decoração."

Foram necessárias **três** tentativas até reproduzir o #103 de verdade. As duas
primeiras são tão informativas quanto a que funcionou:

| # | Mutação | Smoke (c) | Guarda estática | Por quê |
|---|---|---|---|---|
| 1 | Mover o bloco de bootstrap para **antes** da declaração `let` | ✅ **passou** (não pegou) | ❌ **falhou** (pegou) | `readyState === 'loading'` → registra `DOMContentLoaded`, que dispara **depois** da declaração. Não há TDZ: é *cheiro de código*, não bug de runtime |
| 2 | **Acrescentar** chamada síncrona antes da declaração | ✅ passou | — | O bootstrap correto ainda rodava depois e **repopulava** o seletor. O `try/catch` engolia o `ReferenceError` |
| 3 | **Mover** o bootstrap para uma chamada síncrona antes da declaração | ❌ **falhou** | ❌ falhou | Reprodução fiel: seletor com **1 option** (só o placeholder) — o sintoma exato do #103 |

Restaurado o arquivo, tudo verde de novo (15 smokes + 8 guardas estáticas).

**A conclusão que importa:** a mutação #1 mostra as duas camadas fazendo trabalhos
**diferentes** — a estática pegou o que o navegador (corretamente) não pegou. Isso
é a justificativa empírica da opção C: nenhuma das duas substitui a outra.

Roteiro de reprodução da mutação #3:

```python
bootstrap = "        if (document.readyState === 'loading') {\n…"  # bloco inteiro
decl      = "        let _catalogoConselhos = [];\n"
s = s.replace(bootstrap, "")                                   # tira do lugar certo
s = s.replace(decl, "        _montarSeletoresRegistroAtestado();\n" + decl)
```

---

## 4. Dívida #98 — o bônus previsto

O job reconstrói o banco demo à mão (`init_tables.py` + `seed_demo.py` com
`PICSAUDE_DEMO_MODE=true`), que é exatamente a receita que a dívida #98 nos
obriga a repetir. **O CI agora prova que a receita funciona.**

Quando #98 for paga (o demo entrar no Alembic), o passo de preparação do banco
sai do `conftest`.

---

## 5. Achado `core` embutido — triggers de imutabilidade do ledger

**A receita não funcionava.** Na primeira execução do gate, `init_tables.py`
quebrou com `no such table: main.prescricao_eventos`.

Causa: `create_all` roda no engine do SQLAlchemy, que resolve o path por
`_resolve_sqlite_db_path()` — e esse resolver **redireciona para
`PIX_SAUDE_DEMO_DB` quando `PICSAUDE_DEMO_MODE=true`**. Mas cinco
`sqlite3.connect()` do `init_tables.py` importavam `app.config.DB_PATH` **direto**,
ignorando o redirecionamento. Com DEMO_MODE ligado, os dois apontavam para
**arquivos diferentes**.

O crash não era o pior. Medido antes da correção:

```
banco demo:  48 tabelas · 0 triggers      ← ledger SEM proteção de banco
banco dev:    0 tabelas · 0 triggers      ← arquivo vazio criado à toa
```

Ou seja: o ambiente da **vitrine** ficava sem os triggers que impedem
`UPDATE`/`DELETE` no ledger — a proteção que sustenta CLAUDE.md §2. Quem
ignorasse o traceback teria um banco demo com tabelas e nenhuma imutabilidade.

**Correção:** um helper único `_sqlite_path()`, que delega ao mesmo resolver do
engine; os cinco sites passam por ele. Depois:

```
banco demo:  48 tabelas · 14 triggers  (7 tabelas de ledger × 2)   exit 0
banco dev:   não criado
```

Modo não-demo verificado sem regressão (48 tabelas · 14 triggers).

> Isto é `core` por tocar a proteção do ledger. Está aqui porque **o gate de
> navegador o descobriu** — não havia como implementar o ticket sem tropeçar nele.
> Merece o martelo do Fabiano em separado.

---

## 6. Fora de escopo

- Regressão visual / snapshot de pixel
- Smokes para `admin.html` (não está no DOM do portal — só em comentário)
- `dispensador_norte`: aceito pelo `/demo/login` mas ausente de `demo_roles`,
  logo inalcançável pelo portal. Divergência **pré-existente**, não tocada aqui.
