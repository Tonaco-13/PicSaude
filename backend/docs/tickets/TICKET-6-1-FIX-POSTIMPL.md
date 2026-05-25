# TICKET 6.1 — Correções pós-impl do TICKET-6 (CODEX rodada 2)

> **Classe (CLAUDE.md §10):** `core` — fecha P1 de isolamento DB demo↔prod, P1 de
> hidratação de sessão no frontend e P1 de regressão de teste do guard JWT.
> **Pacto:** Regra 2 estrita — volume estimado ~120 linhas (backend + frontend + 1 teste).
> **Data:** 2026-05-24
> **Predecessor:** `94f73cd feat(6): demo mode com sessões pré-semeadas + isolamento DB + 7 decisões`
> **Sucessor:** TICKET-6 fechado em §11 após Code aplicar 6.1 (rodada 3 do CODEX confirma zero P1).
> **Origem:** `backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md` — 3 P1 + 2 P2 + 1 P3.

---

## §1 Contexto

CODEX rodada 2 (pós-impl) revisou o commit `94f73cd` e devolveu **6 achados**
que impedem o fechamento do TICKET-6:

| # | Sev | Resumo | Decisão |
|---|---|---|---|
| 1 | P1 | `cnes_prescritor._get_cnes_conn()` importa `DB_PATH` direto → demo lê prod | **fix** |
| 2 | P1 | `index.html` grava `picsaude_demo_token` mas nenhuma página de destino hidrata sessão | **fix** |
| 3 | P1 | `test_smoke_import_time_em_prod_falha` quebra: guard de `DATABASE_URL` dispara antes do guard de `PICSAUDE_JWT_SECRET` | **fix** |
| 4 | P2 | `POST /auth/registrar` faz `Depends(require_role("admin"))` antes do `_reject_if_demo()` → 401 em vez de 403 demo_mode_ativo | **fix** |
| 5 | P2 | `seed_demo.py` só aborta em `PICSAUDE_ENV=prod`; sem `PICSAUDE_DEMO_MODE=true` semeia o DB errado | **fix** |
| 6 | P3 | `domain/roles.py` continua tipando só `cidadao`; `PERFIS_VALIDOS` não tem `paciente` | **follow-up** (não bloqueia 6.1) |

**Critério de aceite:** após este ticket, rodar `pytest tests/test_demo_mode.py
tests/test_config_guards.py -v` deve retornar **25/25 verdes**, e o reset+seletor
demo precisa entregar uma sessão funcional em prescritor/dispensador/cidadão sem
cair no fluxo de OTP/DEV_PRESET_CONTEXT.

P3#6 fica como dívida aberta (#55) — não bloqueia este ticket.

---

## §2 Inventário de mudanças

### §2.1 Backend (~70 linhas)

| Arquivo | Mudança | Volume |
|---|---|---|
| `backend/app/domain/cnes_prescritor.py` | Trocar `DB_PATH` direto pelo helper `_resolve_sqlite_db_path()` em `_get_cnes_conn()` (P1#1) + remover import morto de `DB_PATH` | ~10 linhas |
| `backend/app/routers/health.py` | Remover import morto de `DB_PATH` (P1#1, satélite) | ~1 linha |
| `backend/app/routers/login.py` | Converter `_reject_if_demo()` em **dependency** e colocá-la **antes** do `Depends(require_role(...))` no `/auth/registrar` (P2#4); aplicar o mesmo padrão preventivamente nos demais 5 endpoints já protegidos por `_reject_if_demo()` para evitar reincidência | ~25 linhas |
| `backend/seed_demo.py` | Espelhar o guard duplo do `reset_demo_db.py`: além de `PICSAUDE_ENV=prod`, abortar se `PICSAUDE_DEMO_MODE != "true"` (P2#5) | ~8 linhas |
| `backend/tests/test_config_guards.py` | Tornar `test_smoke_import_time_em_prod_falha` hermético: setar `DATABASE_URL=sqlite:///:memory:` no env do subprocess (P1#3) | ~3 linhas |

### §2.2 Frontend (~50 linhas)

| Arquivo | Mudança | Volume |
|---|---|---|
| `prescritor.html` | Boot script lê `picsaude_demo_token/role/sub/nome` do `sessionStorage`; se presente, hidrata `jwtAccessToken` + `sessaoAtual`, suprime `DEV_PRESET_CONTEXT` e abre dashboard direto (P1#2) | ~20 linhas |
| `dispensador.html` | Espelho de `prescritor.html` no fluxo de hidratação (P1#2) | ~15 linhas |
| `cidadao.html` | Espelho de `prescritor.html` no fluxo de hidratação (P1#2) | ~15 linhas |

Notas:
- `clinica.html` **não recebe hidratação** — em demo o banner redireciona o usuário para `index.html` (§4.10 do TICKET-6). Sem persona demo, sem hidratação.
- `validar.html` continua público — sem sessão.

---

## §3 Spec por arquivo

### §3.1 `backend/app/domain/cnes_prescritor.py` — P1#1

**O risco que esta seção fecha:** `_get_cnes_conn()` faz `sqlite3.connect(DB_PATH)`
direto, ignorando o roteamento demo. Em demo, `_resolve_sqlite_db_path()` aponta
para `pix_saude_demo.db`, mas o CNES continua puxando `pix_saude_pe.db` (prod).
Isso quebra o critério explícito P1#1 do TICKET-6 (§4.3 do ticket pai): "Helper
compartilhado REUSADO" — `_get_cnes_conn()` é o terceiro ponto que faltou cobrir.

**Decisão arquitetural:** seguir a opção (a) sugerida pelo Codex — **usar o
helper compartilhado**. Consequência aceita: em demo, `pix_saude_demo.db` não
tem tabelas CNES; toda validação CNES retornará `nao_encontrado`. Isso é
aceitável porque:
- A persona demo usa CNS sintético (`980001112223334`) que **não existiria** no
  snapshot DataSUS real de qualquer forma.
- `validar_cns_prescritor()` nunca bloqueia emissão — retorna dict, não exceção.
- A alternativa (variável `CNES_DB_PATH` separada apontando para snapshot público
  sanitizado) é um refinamento pós-MVP, não bloqueia o demo.

**Patch (linha ~44):** substituir o import de `DB_PATH`:

```python
# ANTES
from app.config import CBO_PREFIXES, CNES_SNAPSHOT_MES, CNES_SNAPSHOT_REF, DB_PATH

# DEPOIS
from app.config import CBO_PREFIXES, CNES_SNAPSHOT_MES, CNES_SNAPSHOT_REF
```

**Patch (linha ~50-62):** reescrever `_get_cnes_conn()`:

```python
def _get_cnes_conn() -> sqlite3.Connection:
    """Abre conexão SQLite read-only ao banco CNES.

    Usa `_resolve_sqlite_db_path()` (TICKET-6 P1#1 / 6.1) — em demo, abre o DB
    demo (sem tabelas CNES → toda validação retorna `nao_encontrado`, aceitável
    porque persona demo usa CNS sintético e a validação CNES é não-bloqueante).
    """
    import os
    from app.database import _resolve_sqlite_db_path

    db_path = _resolve_sqlite_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco CNES não encontrado: {db_path}")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
```

**Cuidado de ciclo de imports:** o import de `_resolve_sqlite_db_path` fica
**dentro** da função (lazy) para evitar ciclo com `app.database` durante o
import-time de `app.config`.

### §3.2 `backend/app/routers/health.py` — P1#1 satélite

**Patch (linha 24):** remover `DB_PATH` do import — está marcado como morto pelo
linter e foi flagado pelo Codex:

```python
# ANTES
from app.config import DB_PATH, PICSAUDE_ENV, PICSAUDE_INSTANCE_ORG_ID, PICSAUDE_VERSION

# DEPOIS
from app.config import PICSAUDE_ENV, PICSAUDE_INSTANCE_ORG_ID, PICSAUDE_VERSION
```

Confirmar com `grep -n DB_PATH backend/app/routers/health.py` — esperado: zero matches.

### §3.3 `backend/app/routers/login.py` — P2#4 (ordem demo guard × RBAC)

**Risco:** `Depends(require_role(...))` roda **antes** do corpo da função. Em
demo, requisição sem token bate em `require_role` e devolve `401 Not
authenticated` — não o `403 demo_mode_ativo` documentado em §3.5 do TICKET-5C e
prometido em §3.7 do TICKET-6.

**Decisão:** transformar `_reject_if_demo()` em **dependency** e injetá-la na
assinatura **antes** de qualquer outra dependency (FastAPI resolve dependencies
na ordem declarada). Aplicar nos 6 handlers do `login.py` que hoje chamam
`_reject_if_demo()` no corpo, para eliminar a categoria de bug.

**Patch (linhas ~48-58):** renomear o helper e adaptá-lo a uso como dependency
(continua trivialmente chamável como função pura — sem `Depends()` na assinatura
do próprio helper):

```python
# Linha ~48 — mantém o helper, mas a função já é compatível com Depends().
# Renomear para destacar uso como dependency é OPCIONAL (KISS: manter nome).
def _reject_if_demo() -> None:
    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "demo_mode_ativo",
                "mensagem": "Login real desabilitado em modo demo. Use o seletor em /.",
            },
        )
```

**Patch nas 6 rotas — converter chamadas no corpo em `Depends(_reject_if_demo)`
**na primeira posição** da assinatura (antes de qualquer `require_role`):**

```python
# linha ~78 — /auth/token
@router.post("/token", response_model=TokenOut, summary="Login profissional via senha")
def login(body: LoginIn, _demo=Depends(_reject_if_demo)):
    # remover a chamada inline `_reject_if_demo()` no corpo
    ...

# linha ~129 — /auth/refresh
@router.post("/refresh", response_model=TokenOut, summary="Renova access token")
def refresh(body: RefreshIn, _demo=Depends(_reject_if_demo)):
    ...

# linha ~170 — /auth/registrar  ← caso explicitamente quebrado pelo Codex P2#4
@router.post("/registrar", status_code=201, summary="Registra novo usuário")
def registrar(
    body: RegistrarIn,
    _demo=Depends(_reject_if_demo),               # ← demo guard PRIMEIRO
    _admin=Depends(require_role("admin")),        # ← RBAC só depois
):
    # remover a chamada inline `_reject_if_demo()` no corpo
    return _criar_usuario(body)

# linha ~184 — /auth/bootstrap
@router.post("/bootstrap", status_code=201, summary="Cria o primeiro usuário admin (bootstrap)")
def bootstrap(body: RegistrarIn, _demo=Depends(_reject_if_demo)):
    ...

# linha ~307 — /auth/paciente/solicitar-codigo
def solicitar_codigo(body: PacienteSolicitarIn, _demo=Depends(_reject_if_demo)):
    ...

# linha ~354 — /auth/paciente/validar-codigo
def validar_codigo(body: PacienteValidarIn, _demo=Depends(_reject_if_demo)):
    ...
```

**Aplicar o mesmo padrão preventivamente em `backend/app/routers/auth.py`** — os
2 endpoints legados (`/paciente/enviar-codigo` linha 42 e `/paciente/validar-codigo`
linha 84) já chamam `_reject_if_demo()` no corpo. Como nenhum deles tem `Depends`
de RBAC antes, o bug atual não ocorre lá; mas converter para dependency é higiene
arquitetural (zero risco, fecha a categoria).

### §3.4 `backend/seed_demo.py` — P2#5

**Risco:** sem `PICSAUDE_DEMO_MODE=true`, `_resolve_sqlite_db_path()` devolve
`DB_PATH` (prod/dev). Quem rodar `python3 seed_demo.py` sem a flag insere as 3
personas demo no banco errado.

**Patch (linhas ~180-188):** espelhar o guard duplo do `reset_demo_db.py:36-46`:

```python
def main() -> None:
    env = os.getenv("PICSAUDE_ENV", "")
    if env == "prod":
        print("❌ ABORTANDO: seed_demo não pode rodar em PICSAUDE_ENV=prod.")
        sys.exit(1)

    demo = os.getenv("PICSAUDE_DEMO_MODE", "").lower()
    if demo != "true":
        print(
            "❌ ABORTANDO: PICSAUDE_DEMO_MODE precisa ser 'true' para semear o DB demo.\n"
            "   Sem a flag, get_conn() roteia para o DB de dev/prod (TICKET-6.1 P2#5)."
        )
        sys.exit(1)

    print("\n=== seed_demo.py — TICKET-6 ===")
    # ... resto idêntico
```

### §3.5 `backend/tests/test_config_guards.py` — P1#3

**Risco:** o teste de smoke do guard JWT sobe um subprocess `import app.main`
com `PICSAUDE_ENV=prod` e **sem** `PICSAUDE_JWT_SECRET`. Mas `main.py:32-46`
roda primeiro o guard de `DATABASE_URL` (também ausente), que aborta com
mensagem sobre `DATABASE_URL`, antes do guard JWT (linha 88).

**Decisão:** o teste valida especificamente o guard JWT — torná-lo hermético
setando uma `DATABASE_URL` fake no env do subprocess. Reordenar guards em
main.py é mais invasivo e arrisca regredir `test_smoke_import_time_em_prod_falha`
para o guard DB (que também tem mensagem "INICIALIZAÇÃO BLOQUEADA" — passaria
por engano).

**Patch (linha ~79-80):**

```python
def test_smoke_import_time_em_prod_falha():
    """..."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "PICSAUDE_ENV": "prod"}
    env.pop("PICSAUDE_JWT_SECRET", None)            # força uso do default
    env["DATABASE_URL"] = "postgresql://stub:stub@localhost:5432/stub"  # ← FIX P1#3
    # DATABASE_URL fake-mas-pg passa pelo guard de _USE_SQLITE (linha 32),
    # permitindo que o teste atinja o guard JWT real (linha 88).
    ...
```

**Não setar `sqlite:///:memory:`** — esse formato dispara `_USE_SQLITE=True` e o
guard DB volta a abortar antes do JWT. O importante é qualquer URL não-SQLite
válida.

### §3.6 Frontends — P1#2

**Padrão (replicar nos 3 arquivos):** boot script no início do `<body>` (após
o banner DEMO já existente) faz:

1. Lê `picsaude_demo_token` do `sessionStorage`.
2. Se ausente → não faz nada (preserva fluxo atual: OTP/`DEV_PRESET_CONTEXT`).
3. Se presente → **antes** de qualquer outra inicialização:
   - Suprime `DEV_PRESET_CONTEXT` (setar a const para `false` antes do bloco
     que a consulta; o jeito mais simples é colocar o script ANTES do
     `<script>` que declara `DEV_PRESET_CONTEXT = true`).
   - Hidrata `jwtAccessToken = token` e popula `sessaoAtual` com `cns/cnpj/cpf`
     e `nome` do `sessionStorage`.
   - Valida que `role` do sessionStorage bate com a página
     (`prescritor` em `prescritor.html`, etc). Se não bater, limpa
     `sessionStorage` e redireciona para `/`.
   - Pula tela de login e chama o handler de "logado com sucesso" da página
     (no `prescritor.html` é o trecho ~linha 1126-1155; replicar a chamada
     correspondente em cada página).

#### `prescritor.html` (~20 linhas)

Inserir o bloco **antes** do `<script>` que declara `DEV_PRESET_CONTEXT` (~linha 778):

```html
<script>
  // TICKET-6.1 P1#2 — hidrata sessão a partir do seletor demo em index.html.
  // Executa ANTES do <script> principal, que lê DEV_PRESET_CONTEXT como const.
  (function hidratarSessaoDemo() {
    try {
      const token = sessionStorage.getItem('picsaude_demo_token');
      const role  = sessionStorage.getItem('picsaude_demo_role');
      if (!token || !role) return;                  // sem token demo → fluxo normal
      if (role !== 'prescritor') {                  // role errada para esta página
        sessionStorage.clear();
        window.location.replace('/');
        return;
      }
      // sinaliza para o script principal pular DEV_PRESET_CONTEXT e OTP
      window.__PICSAUDE_DEMO_SESSAO__ = {
        token: token,
        sub:   sessionStorage.getItem('picsaude_demo_sub'),
        nome:  sessionStorage.getItem('picsaude_demo_nome'),
        role:  role,
      };
    } catch (_e) { /* sessionStorage indisponível → fallback silencioso */ }
  })();
</script>
```

E **dentro** do `<script>` principal, no início (antes da declaração de
`DEV_PRESET_CONTEXT` ~linha 784, ou ajustando o `if (DEV_PRESET_CONTEXT && !medicoLogado)`
~linha 2884), adicionar:

```javascript
// TICKET-6.1 P1#2 — se sessão demo presente, hidrata e pula OTP+DEV_PRESET.
if (window.__PICSAUDE_DEMO_SESSAO__) {
  const s = window.__PICSAUDE_DEMO_SESSAO__;
  jwtAccessToken = s.token;
  sessaoAtual    = { fluxo: 'demo', cns: s.sub, nome: s.nome, role: s.role };
  // Trocar abaixo: chamar o mesmo handler que executa após /auth/token sucesso
  // (no prescritor.html, é o bloco ~linha 1126-1155 que popula UI pós-login).
  // Code: localizar a função que "abre o dashboard pós-login" e chamá-la aqui.
  // Suprimir DEV_PRESET_CONTEXT: já não dispara porque medicoLogado=true.
}
```

> **Nota ao Code:** o "handler pós-login" varia entre as 3 páginas. Em
> `prescritor.html` é o caminho que segue após `data.access_token` em ~linha 1126.
> Refatorar o bloco em função nomeada (`abrirDashboardPosLogin()`) e chamá-la
> tanto do fluxo OTP quanto do fluxo demo é a forma mais limpa. Se um refactor
> dessa magnitude estoura a Regra 2, copiar inline é aceitável (volume curto).

#### `dispensador.html` (~15 linhas)

Mesmo padrão. Role esperada: `dispensador`. Persona traz CNPJ no `sub` (não CNS).
Adaptar `sessaoAtual` para `{ fluxo: 'demo', cnpj: s.sub, nome: s.nome, role: s.role }`.

#### `cidadao.html` (~15 linhas)

Mesmo padrão. Role esperada: `paciente`. Persona traz CPF no `sub`. Adaptar
`sessaoAtual` para `{ fluxo: 'demo', cpf: s.sub, nome: s.nome, role: s.role }`.

#### Não-alvos

- `clinica.html`: em demo o banner redireciona para `/index.html` (sem persona
  demo). **Não hidratar.**
- `validar.html`: público. **Não hidratar.**

---

## §4 Critérios de aceite — testes obrigatórios

### §4.1 P1#1 — isolamento CNES

Adicionar em `tests/test_demo_mode.py`:

```python
def test_cnes_conn_em_demo_usa_db_demo(tmp_path, monkeypatch):
    """
    Em DEMO_MODE, _get_cnes_conn() deve abrir o DB demo (não o prod).
    Hoje (pré-6.1), abriria pix_saude_pe.db direto via DB_PATH.
    """
    demo_db = tmp_path / "test_demo.db"
    demo_db.write_bytes(b"")  # arquivo vazio (existe; abrir nem precisa de schema)
    monkeypatch.setenv("PICSAUDE_DEMO_MODE", "true")
    monkeypatch.setenv("PIX_SAUDE_DEMO_DB", str(demo_db))

    # Recarrega config+database para refletir env (P3#9 do TICKET-6)
    import importlib
    import app.config, app.database
    importlib.reload(app.config)
    importlib.reload(app.database)
    import app.domain.cnes_prescritor as cnes_mod
    importlib.reload(cnes_mod)

    conn = cnes_mod._get_cnes_conn()
    try:
        # SQLite expõe o path do DB aberto via PRAGMA database_list.
        rows = conn.execute("PRAGMA database_list").fetchall()
        paths = [r[2] for r in rows if r[1] == "main"]
        assert str(demo_db) in paths[0], (
            f"esperava {demo_db} no PRAGMA database_list, obtido: {paths}"
        )
    finally:
        conn.close()
```

### §4.2 P1#2 — hidratação frontend

**Teste manual obrigatório** (não há suite Playwright neste projeto):

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev
PICSAUDE_DEMO_MODE=true PICSAUDE_ENV=dev uvicorn backend.app.main:app --reload
# (em outro terminal) preparar DB demo
PICSAUDE_DEMO_MODE=true python3 backend/seed_demo.py
# abrir http://127.0.0.1:8000/index.html
```

Checklist:
- [ ] Banner amarelo "MODO DEMO" aparece em `index.html`.
- [ ] Botão "Entrar como Prescritor" redireciona para `prescritor.html` JÁ
      logado (sem tela de login, sem OTP). Header mostra "Dra. Demo Maria Souza".
- [ ] Botão "Entrar como Dispensador" idem com "Farmácia Demo Central".
- [ ] Botão "Entrar como Paciente" idem com "João Demo da Silva".
- [ ] Em cada página, `localStorage`/`sessionStorage` do DevTools mostra o token
      e a role correta.
- [ ] `Network` mostra requisições com `Authorization: Bearer ...` (sem 401).
- [ ] Acessar `prescritor.html` direto (sem passar pelo seletor) ainda funciona
      no fluxo OTP/`DEV_PRESET_CONTEXT` (regressão).

### §4.3 P1#3 — guard JWT hermético

Já coberto pelo próprio fix em `test_smoke_import_time_em_prod_falha`. Confirmar:

```bash
cd backend && .venv/bin/pytest tests/test_config_guards.py -v
# Esperado: 9 passed (5 puros JWT + 4 puros demo + 1 smoke), zero failed.
```

### §4.4 P2#4 — /auth/registrar devolve 403 demo_mode_ativo

Adicionar em `tests/test_demo_mode.py`:

```python
def test_registrar_em_demo_retorna_403_demo_mode_ativo(client_demo):
    """
    Em DEMO_MODE, POST /auth/registrar sem token deve devolver 403 com
    codigo='demo_mode_ativo' (não 401 'Not authenticated' do require_role).
    """
    resp = client_demo.post("/auth/registrar", json={
        "identificador": "12345678901",
        "senha":          "qualquer",
        "role":           "prescritor",
        "nome":           "Teste",
    })
    assert resp.status_code == 403, (resp.status_code, resp.text)
    body = resp.json()
    assert body.get("detail", {}).get("codigo") == "demo_mode_ativo"
```

(Reusar fixture `client_demo` que já existe no `test_demo_mode.py` do TICKET-6;
se não existir, criar com `PICSAUDE_DEMO_MODE=true` via subprocess/reload.)

### §4.5 P2#5 — seed_demo aborta sem flag

Adicionar em `tests/test_demo_mode.py`:

```python
def test_seed_demo_aborta_sem_demo_mode_flag(tmp_path):
    """
    Sem PICSAUDE_DEMO_MODE=true, seed_demo.py deve abortar com exit !=0
    (TICKET-6.1 P2#5).
    """
    import subprocess, sys, os
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ}
    env.pop("PICSAUDE_DEMO_MODE", None)
    env["PICSAUDE_ENV"] = "dev"
    result = subprocess.run(
        [sys.executable, "seed_demo.py"],
        env=env, cwd=backend_dir, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert "PICSAUDE_DEMO_MODE" in result.stdout + result.stderr
```

---

## §5 Verificação

### Pré-implementação

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Confirmar import morto de DB_PATH em cnes + health
grep -n "from app.config import.*DB_PATH" backend/app/domain/cnes_prescritor.py backend/app/routers/health.py
# Esperado: 2 matches (ambos)

# 2. Confirmar que _reject_if_demo é chamado no corpo (não como Depends)
grep -n "_reject_if_demo()" backend/app/routers/login.py
# Esperado: 6 matches (linhas 103, 146, 180, 193, 338, 383)

# 3. Confirmar que seed_demo.py não checa PICSAUDE_DEMO_MODE
grep -n "PICSAUDE_DEMO_MODE" backend/seed_demo.py
# Esperado: 1 match (apenas o print de debug)

# 4. Reproduzir falha do smoke
cd backend && .venv/bin/pytest tests/test_config_guards.py::test_smoke_import_time_em_prod_falha -v
# Esperado: FAILED (com "DATABASE_URL" na mensagem do AssertionError)
```

### Pós-implementação

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Imports limpos
grep -n "from app.config import.*DB_PATH" backend/app/domain/cnes_prescritor.py backend/app/routers/health.py
# Esperado: zero matches

# 2. _reject_if_demo como dependency em login.py
grep -nE "Depends\(_reject_if_demo\)" backend/app/routers/login.py
# Esperado: >= 6 matches

# 3. seed_demo com guard duplo
grep -n "PICSAUDE_DEMO_MODE" backend/seed_demo.py
# Esperado: >= 2 matches (guard + print de debug)

# 4. Suite focal verde
cd backend && .venv/bin/pytest tests/test_demo_mode.py tests/test_config_guards.py -v
# Esperado: 25/25 (TICKET-6 original) + 3 novos (P1#1, P2#4, P2#5) = 28/28 verdes

# 5. Suite completa sem regressão
.venv/bin/pytest -q
# Esperado: contagem de falhas idêntica à do commit 94f73cd (27 pré-existentes)
```

---

## §6 Anti-escopo

- **P3#6 (`domain/roles.py` desatualizado):** NÃO incluído neste ticket. Abrir
  follow-up #55 ("Atualizar contrato de roles: substituir `cidadao` por `paciente`
  ou aceitar ambos em `PERFIS_VALIDOS`"). Não bloqueia porque `require_role("paciente")`
  hoje não consulta `PERFIS_VALIDOS`.
- **Variável `CNES_DB_PATH` separada:** mencionado em §3.1 como refinamento
  pós-MVP. O fix atual usa `_resolve_sqlite_db_path()` direto. Se em rodada
  futura o demo precisar de validação CNES funcional, abrir follow-up **#61**
  (renumerado de #58 em 2026-05-25 — colisão com GFI de `seed_common.py`).
- **Refactor de `prescritor.html`/`dispensador.html`/`cidadao.html` para extrair
  `abrirDashboardPosLogin()` em função nomeada:** sugerido em §3.6 mas não
  obrigatório. Copiar inline é aceitável se o refactor estourar a Regra 2.
- **Suite Playwright para teste P1#2:** fora — projeto não tem infra. Validação
  é manual (§4.2).

---

## §7 Prompt final ao Code

Pronto para implementação. Copiar e colar no chat do Claude Code no VS Code.

````
Tarefa: TICKET-6.1 — correções pós-impl do TICKET-6 (CODEX rodada 2).
Classe: core (isolamento DB, dependency order auth, regressão de teste).
Pacto: Regra 2 estrita (~120 linhas: ~70 backend + ~50 frontend + 3 testes novos).

LOCAL DO TICKET
───────────────
backend/docs/tickets/TICKET-6-1-FIX-POSTIMPL.md

LEIA O TICKET INTEIRO antes de editar — especialmente:
  §3 (spec por arquivo), §4 (testes obrigatórios), §6 (anti-escopo).

CONTEXTO
────────
Origem: backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md
HEAD atual = 94f73cd (TICKET-6 mergeado). Confirme com `git log -1 --oneline`.
6 achados; 5 entram no escopo (3 P1 + 2 P2). P3#6 fica como dívida #55.

ESCOPO (5 arquivos backend + 3 frontend + 1 teste editado + 3 testes novos)
──────

EDITAR BACKEND:
  - backend/app/domain/cnes_prescritor.py
      P1#1 — remover import de DB_PATH; _get_cnes_conn() passa a usar
      _resolve_sqlite_db_path() (import LAZY dentro da função para
      evitar ciclo com app.database). Ver §3.1 do ticket.

  - backend/app/routers/health.py
      P1#1 satélite — remover DB_PATH do import (uso morto). Ver §3.2.

  - backend/app/routers/login.py
      P2#4 — converter _reject_if_demo em dependency e colocá-la PRIMEIRO
      na assinatura dos 6 handlers que hoje chamam no corpo (rotas
      /token, /refresh, /registrar, /bootstrap, /paciente/solicitar-codigo,
      /paciente/validar-codigo). Em /registrar especificamente, _demo
      precisa vir ANTES de _admin=Depends(require_role("admin")). Ver §3.3.

  - backend/app/routers/auth.py
      Higiene preventiva: aplicar o mesmo padrão Depends(_reject_if_demo)
      nos 2 endpoints legados (/paciente/enviar-codigo linha 42,
      /paciente/validar-codigo linha 84). Ver §3.3 fim.

  - backend/seed_demo.py
      P2#5 — espelhar guard duplo do scripts/reset_demo_db.py: abortar
      tanto em PICSAUDE_ENV=prod quanto em PICSAUDE_DEMO_MODE != "true".
      Mensagem alinhada com a do reset. Ver §3.4.

EDITAR TESTE:
  - backend/tests/test_config_guards.py
      P1#3 — em test_smoke_import_time_em_prod_falha, setar
      env["DATABASE_URL"] = "postgresql://stub:stub@localhost:5432/stub"
      antes do subprocess.run. NÃO usar sqlite:///:memory: (dispara
      _USE_SQLITE). Ver §3.5.

EDITAR FRONTEND:
  - prescritor.html, dispensador.html, cidadao.html
      P1#2 — boot script lê picsaude_demo_token/role/sub/nome do
      sessionStorage; se presente: valida role esperada da página,
      seta jwtAccessToken + sessaoAtual, suprime DEV_PRESET_CONTEXT
      e abre dashboard direto. Em cada página, role esperada é
      diferente (prescritor/dispensador/paciente) e o sub vira
      cns/cnpj/cpf respectivamente. Ver §3.6 com snippets.
      NÃO TOCAR clinica.html e validar.html (§6).

ADICIONAR 3 TESTES NOVOS em backend/tests/test_demo_mode.py:
  - test_cnes_conn_em_demo_usa_db_demo (P1#1) — §4.1
  - test_registrar_em_demo_retorna_403_demo_mode_ativo (P2#4) — §4.4
  - test_seed_demo_aborta_sem_demo_mode_flag (P2#5) — §4.5

NÃO TOCAR (anti-escopo §6):
  - backend/app/domain/roles.py (P3#6 vira dívida #55)
  - clinica.html, validar.html (sem hidratação em demo)
  - Criar CNES_DB_PATH novo (refinamento pós-MVP, follow-up #61 — renumerado de #58 em 2026-05-25)

PADRÃO P1#1 — import lazy
─────────────────────────
Em cnes_prescritor._get_cnes_conn(), o import de _resolve_sqlite_db_path
DEVE estar dentro da função (não no topo do módulo) para evitar ciclo
de import com app.database (que importa de app.config no top-level).

PADRÃO P2#4 — ordem das dependencies
────────────────────────────────────
FastAPI resolve dependencies na ordem em que aparecem na assinatura.
_reject_if_demo PRECISA vir antes de qualquer require_role / require_*.
Caso /auth/registrar é o explícito; replicar em todas as 6 rotas mesmo
que só /registrar tenha o bug hoje — fecha a categoria.

PADRÃO P1#3 — DATABASE_URL stub
───────────────────────────────
Usar "postgresql://stub:stub@localhost:5432/stub" (não sqlite). O guard
em main.py:32 só dispara se _USE_SQLITE=True; uma URL pg passa direto
mesmo que o engine real nunca abra a conexão (o teste valida só
import-time, não query-time).

VERIFICAÇÃO PRÉ-IMPLEMENTAÇÃO
─────────────────────────────
  cd /Users/fabianotonacoborges/PicSaude_Dev
  grep -n "from app.config import.*DB_PATH" backend/app/domain/cnes_prescritor.py backend/app/routers/health.py
  # Esperado: 2 matches

  grep -n "_reject_if_demo()" backend/app/routers/login.py
  # Esperado: 6 matches no corpo (linhas 103, 146, 180, 193, 338, 383)

  cd backend && .venv/bin/pytest tests/test_config_guards.py::test_smoke_import_time_em_prod_falha -v
  # Esperado: FAILED com "PICSAUDE_JWT_SECRET" not in stderr

VERIFICAÇÃO PÓS-IMPLEMENTAÇÃO
─────────────────────────────
  cd /Users/fabianotonacoborges/PicSaude_Dev

  grep -n "from app.config import.*DB_PATH" backend/app/domain/cnes_prescritor.py backend/app/routers/health.py
  # Esperado: zero matches

  grep -nE "Depends\(_reject_if_demo\)" backend/app/routers/login.py
  # Esperado: >= 6 matches

  grep -nE "Depends\(_reject_if_demo\)" backend/app/routers/auth.py
  # Esperado: >= 2 matches (legados)

  grep -n "PICSAUDE_DEMO_MODE" backend/seed_demo.py
  # Esperado: >= 2 matches

  cd backend && .venv/bin/pytest tests/test_demo_mode.py tests/test_config_guards.py -v
  # Esperado: 28/28 verdes (25 originais + 3 novos)

  .venv/bin/pytest -q
  # Esperado: contagem de falhas igual à do 94f73cd (27 pré-existentes)

VALIDAÇÃO MANUAL FRONTEND (obrigatória — P1#2)
──────────────────────────────────────────────
  cd /Users/fabianotonacoborges/PicSaude_Dev
  PICSAUDE_DEMO_MODE=true python3 backend/seed_demo.py
  PICSAUDE_DEMO_MODE=true PICSAUDE_ENV=dev uvicorn backend.app.main:app --reload &
  open http://127.0.0.1:8000/index.html

  Checklist (§4.2):
  - [ ] Banner amarelo MODO DEMO em index
  - [ ] "Entrar como Prescritor" → prescritor.html já logado como "Dra. Demo Maria Souza"
  - [ ] "Entrar como Dispensador" → dispensador.html já logado como "Farmácia Demo Central"
  - [ ] "Entrar como Paciente" → cidadao.html já logado como "João Demo da Silva"
  - [ ] Network: Authorization: Bearer ... presente, sem 401
  - [ ] Acesso direto a prescritor.html sem passar pelo seletor: OTP/DEV_PRESET_CONTEXT
        funciona normalmente (regressão)

COMMIT ESPERADO
───────────────
Mensagem sugerida (um único commit):

  fix(6.1): isolamento CNES + hidratação demo no frontend + guard JWT hermético

  TICKET-6.1 fecha 3 P1 + 2 P2 do CODEX rodada 2 sobre TICKET-6 (94f73cd).

  P1#1 — cnes_prescritor._get_cnes_conn agora usa _resolve_sqlite_db_path
         (helper compartilhado); remove import morto de DB_PATH em health.py
  P1#2 — prescritor/dispensador/cidadao.html hidratam sessão do
         sessionStorage e suprimem DEV_PRESET_CONTEXT em demo
  P1#3 — test_smoke_import_time_em_prod_falha vira hermético via
         DATABASE_URL stub pg
  P2#4 — /auth/registrar e demais 5 rotas: _reject_if_demo vira dependency
         executada antes de require_role
  P2#5 — seed_demo.py exige PICSAUDE_DEMO_MODE=true (mesmo guard do
         reset_demo_db.py)

  P3#6 (roles.py) abre como dívida #55. CNES_DB_PATH separado abre como
  follow-up #61 se demo precisar de validação CNES funcional
  (renumerado de #58 em 2026-05-25 — colisão com GFI de seed_common.py).

  Refs: backend/docs/tickets/TICKET-6-1-FIX-POSTIMPL.md
        backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md

NÃO ESQUEÇA
───────────
- Ticket é a fonte de verdade. Em dúvida: §3 + §4.
- import lazy de _resolve_sqlite_db_path em cnes_prescritor (§3.1).
- _reject_if_demo PRIMEIRO na assinatura, ANTES de require_role (§3.3).
- DATABASE_URL stub deve ser pg, NÃO sqlite:///:memory: (§3.5).
- Suprimir DEV_PRESET_CONTEXT em demo — não basta hidratar, precisa não-disparar (§3.6).
- Role validation no boot script: se role do sessionStorage não bate com
  a página, limpar sessionStorage e redirecionar para / (§3.6).
- Reporte separadamente as 27 falhas pré-existentes após pytest -q.
- NÃO mexer em clinica.html / validar.html / roles.py (§6).
````

---

## §8 Status do ticket

> **2026-05-24 — pronto para Code:**
> Origem: CODEX rodada 2 (3 P1 + 2 P2 + 1 P3 — P3 fica como dívida #55) ✅
> Spec por arquivo (§3) ✅
> Testes obrigatórios (§4) ✅
> Verificações pré/pós (§5) ✅
> Anti-escopo (§6) ✅
> Prompt operacional (§7) ✅
> Code — aguarda implementação
> CODEX rodada 3 (pós-impl 6.1) — pendente, fecha §11 do TICKET-6 original
