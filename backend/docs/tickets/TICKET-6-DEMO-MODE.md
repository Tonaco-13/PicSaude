# TICKET 6 — DEMO_MODE: ambiente público de demonstração com sessões pré-semeadas

> **Classe (CLAUDE.md §10):** `core` — toca autenticação (`auth/jwt.py`, `auth/dependencies.py`), boot do servidor (`main.py` guardrails), configuração (`config.py`), banco (`database.py`), endpoint público novo (`/config/public`), seeds canônicos e ledger via `instance_id` específico de demo.
> **Pacto:** Regra 2 estrita — volume estimado ~780 linhas (backend + frontend + testes).
> **Data:** 2026-05-24
> **Predecessor:** Etapa 5 fechada em `2bf5e7d`. HEAD do main = `2bf5e7d`.
> **Sucessor:** Etapa 7 (Dockerfile) — DEMO_MODE configurado via env no container.
> **Redigido por:** Arquiteto rodada 0 sobre 7 decisões fechadas com Fabiano em 2026-05-24. Aguarda CODEX rodada 1 antes de passar ao Code.

---

## §1 Contexto

O PicSaúde tem backend funcional (~140 testes verdes) com 5 etapas de segurança fechadas (Etapa 4 instance_id; 5A entrega/carteira; 5B OTP; 5C autorização mínima em 11 endpoints; 5D guard JWT). Falta um modo público de demonstração antes de subir o frontend a uma URL pública (Etapa 8).

A demanda é **deixar qualquer visitante (potencial usuário, contribuidor, avaliador regulatório) explorar o sistema** sem expor:
- credenciais reais (CPF/CNS/CNPJ de cidadãos e profissionais),
- prescrições reais (com efeito jurídico/regulatório),
- telas administrativas (que não pertencem ao MVP ambulatorial público).

O risco a evitar é o oposto também: que dados reais de produção entrem no ambiente demo, ou que prescrições demo sejam confundidas com reais (e usadas para fraude, por exemplo, em farmácia que recebe o PDF impresso).

### §1.1 Tese central

> **DEMO_MODE é um modo explícito, safe-by-default off, que substitui login real por sessões demo pré-semeadas e reversíveis, sem admin público e sem dados reais.**

Quatro corolários:

1. **Explícito:** controlado por `PICSAUDE_DEMO_MODE=true` no backend; frontend descobre via `GET /config/public`. Frontend nunca liga demo sozinho.
2. **Safe-by-default off:** `PICSAUDE_DEMO_MODE` ausente ou ≠ `true` → comportamento atual (login real com OTP). Sem fallback "dev".
3. **Substitui (não coexiste com) login real:** quando `DEMO_MODE=true`, o endpoint `/auth/login` (OTP) é desabilitado e o seletor demo é a única forma de entrar.
4. **Sem admin público e sem dados reais:** `admin` fora do demo público (modo separado opcional via `PICSAUDE_DEMO_ADMIN=true`); DB demo é arquivo/schema separado do DB de produção.

### §1.2 Por que isso é bloqueador de deploy (Etapa 8)

Sem demo público, o deploy precisa ou:
- subir só backend e disponibilizar `/docs` (Swagger) — péssima experiência para sanitaristas avaliarem o MVP, e expõe estrutura interna a curiosos;
- subir frontend com OTP real — requer canal SMS/email funcionando em produção (custo + setup); criar contas de teste cria superfície de ataque desnecessária; visitante sem CPF cadastrado nunca consegue entrar.

DEMO_MODE resolve ambos: visitante clica "Demo" e está dentro do sistema em 1 segundo, com dados claramente fictícios.

---

## §2 Inventário de mudanças

### §2.1 Backend (estimativa ~330 linhas)

| Arquivo | Mudança | Volume |
|---|---|---|
| `app/config.py` | Adicionar `PICSAUDE_DEMO_MODE`, `PICSAUDE_DEMO_ADMIN`, `PIX_SAUDE_DEMO_DB` | ~5 linhas |
| `app/main.py` | Novo guardrail `_validate_demo_mode_at_boot` (mesmo padrão do 5D) | ~40 linhas |
| `app/database.py` | **Helper compartilhado `_resolve_sqlite_db_path()`** reusado pelo engine top-level **E pelo `get_conn()`** (P1#1 CODEX rodada 1) — sem isso, demo continua lendo prod | ~20 linhas |
| `app/routers/demo.py` | **Novo** — `POST /demo/login` (emite JWT demo por role), `GET /demo/info` (lista personas + reset previsto) | ~120 linhas |
| `app/routers/config_publico.py` | **Novo** — `GET /config/public` (retorna `demo_mode`, `demo_roles`, `version`, `proximo_reset`) | ~40 linhas |
| `app/main.py` (registro de routers) | Registrar `demo` e `config_publico` somente quando flag ativa | ~10 linhas |
| `app/routers/auth.py` + `login.py` | Quando `DEMO_MODE=true`, **7 endpoints** retornam 403 `demo_mode_ativo`: `/auth/token`, `/auth/registrar`, `/auth/bootstrap`, `/auth/refresh`, `/auth/paciente/solicitar-codigo`, `/auth/paciente/validar-codigo` (login.py linhas 78/154/167/129/307/354) + `/auth/paciente/enviar-codigo` e `/auth/paciente/validar-codigo` legados (auth.py linhas 42/84) | ~35 linhas |
| `app/domain/pdf_prescricao.py` | Marca d'água "DEMO" diagonal quando `instance_id` for de demo | ~25 linhas |
| `seed_demo.py` (novo) | Personas canônicas: 1 prescritor + 1 dispensador + 1 paciente (com carteira digital pré-criada para fluxo entrega) | ~100 linhas |
| `scripts/reset_demo_db.py` (novo) | Script idempotente: derruba DB demo, recria tabelas, roda `seed_demo`. Rodável manualmente ou via cron. | ~50 linhas |

### §2.2 Frontend (estimativa ~180 linhas, P2#7 CODEX rodada 1)

| Arquivo | Mudança | Volume |
|---|---|---|
| `index.html` | Banner amarelo "MODO DEMO" quando `/config/public.demo_mode=true`; segmented control com 3 botões (Prescritor / Dispensador / Paciente) substituindo login real | ~80 linhas |
| `prescritor.html` | Banner permanente + leitura de `?demo_role=prescritor` ou `sessionStorage` | ~25 linhas |
| `dispensador.html` | Espelho de `prescritor.html` | ~25 linhas |
| `cidadao.html` | Espelho de `prescritor.html` (papel paciente) | ~20 linhas |
| `clinica.html` | **Banner + redirect para `index.html` quando `demo_mode=true`** (P2#7 CODEX rodada 1 — tem login próprio em `/auth/token` e `DEV_PRESET_CONTEXT=true`; sem banner cria tela quebrada/confusa em demo) | ~20 linhas |
| `validar.html` | **Aviso visual "Prescrição DEMO" quando validação retorna documento emitido em modo demo** (P2#7 CODEX rodada 1) — fica público mas marcado | ~10 linhas |

### §2.3 Testes (estimativa ~300 linhas)

| Arquivo | Cenários |
|---|---|
| `tests/test_demo_mode.py` (novo) | 10 cenários: boot com flag, seletor de role emite JWT correto, /auth/login bloqueado em demo, /config/public retorna estado, admin fora do demo público, isolamento DB demo vs prod, marca d'água no PDF, banner UI, instance_id demo nos eventos, guardrail prod+demo simultâneo aborta boot |

---

## §3 Decisões de design (7 decisões fechadas com Fabiano em 2026-05-24)

### §3.1 Seletor de role

**Mecanismo:** segmented control visível em `index.html` quando `demo_mode=true`. Aceita também `?demo_role=prescritor|dispensador|paciente` em qualquer rota — frontend grava em `sessionStorage` e redireciona para a página do papel.

**Onde o estado mora:** `sessionStorage` (limpa ao fechar aba; não vaza entre sessões; não persiste no navegador). NÃO usar cookie ou `localStorage`.

**Defesa em camadas:** frontend **ignora** `?demo_role=...` se `/config/public` retornar `demo_mode=false`. Backend nunca confia no frontend (CLAUDE.md §3); `/demo/login` rejeita request quando `DEMO_MODE=false`.

### §3.2 Papéis cobertos

| Papel | Demo público (`DEMO_MODE=true`) | Modo admin opcional (`DEMO_ADMIN=true`) |
|---|---|---|
| `prescritor` | ✅ | ✅ |
| `dispensador` | ✅ | ✅ |
| `paciente` | ✅ | ✅ |
| `admin` | ❌ | ✅ |
| `auditor` | ❌ | ❌ (fluxo de fiscalização — não pertence a demo) |
| `integrador` | ❌ | ❌ (API Key institucional — não pertence a demo) |

`admin` fora do demo público porque admin expõe telas internas, aumenta superfície de ataque e cria ruído comercial (visitante vê opções que não pertencem ao MVP ambulatorial). Se a equipe interna precisar demonstrar admin, sobe instância com `PICSAUDE_DEMO_ADMIN=true` (flag separada).

### §3.3 Seeds canônicos

Dados sintéticos fixos, não aleatórios. Reprodutibilidade > variedade.

**Identificadores DIFERENTES dos do `seed_dev.py`** (P3#8 CODEX rodada 1) — evita colisão acidental se alguém rodar os dois seeds no mesmo DB e facilita detecção de "qual seed gerou esse dado" em auditoria.

| Persona | Identificador | Nome | Notas |
|---|---|---|---|
| Prescritor | CNS `980001112223334` (15 dígitos, soma módulo 11 válida; prefixo "98" claramente sintético) | Dra. Demo Maria Souza | Diferente de `seed_dev.py:48` (`123456789012345`) |
| Dispensador | CNPJ `99999999000191` (14 dígitos, DV válido, claramente sintético) | Farmácia Demo Central | Diferente de `seed_dev.py:54` (`12345678000199`) |
| Paciente | CPF `12345678909` (DV válido, é o CPF "famoso de teste" no Brasil — escolha intencional: marketing/comunicação) | João Demo da Silva | **Novo** — `seed_dev.py` não cria paciente hoje; ticket adiciona |

Todos os nomes começam com "Demo" ou "Dr(a). Demo" para serem visualmente óbvios como sintéticos. Os identificadores escolhidos passam pelo validator de CPF (task #44 ainda aberta — não bloqueia o ticket porque o validator não existe hoje, mas os CPFs já são DV-válidos para quando existir).

**Sobre `role="paciente"` vs `role="cidadao"` (P2#4 CODEX rodada 1):** o `domain/roles.py:35` declara `cidadao` como role válido, mas os routers operacionais (`pacientes.py:21` e o fluxo de carteira/prescrição) usam `paciente`. Este ticket usa **`role="paciente"`** por compatibilidade com os routers atuais. Corrigir o contrato de roles (`cidadao` vs `paciente`) é fora do escopo deste ticket — abrir como dívida #55 se necessário, após confirmar que CODEX/Code aceita a divergência sem regressão.

### §3.4 Flag e descoberta

**Backend (fonte de verdade):**
```python
# config.py — additions
PICSAUDE_DEMO_MODE: bool = os.getenv("PICSAUDE_DEMO_MODE", "").lower() == "true"
PICSAUDE_DEMO_ADMIN: bool = os.getenv("PICSAUDE_DEMO_ADMIN", "").lower() == "true"
PIX_SAUDE_DEMO_DB: str = os.getenv("PIX_SAUDE_DEMO_DB", "../../data/pix_saude_demo.db")
```

`PICSAUDE_DEMO_ADMIN` só tem efeito quando `PICSAUDE_DEMO_MODE=true` (admin standalone fora de demo é absurdo).

**Frontend (descobre via API):**
```javascript
// index.html — boot script
const resp = await fetch('/config/public');
const { demo_mode, demo_roles, proximo_reset } = await resp.json();
if (demo_mode) {
  document.body.classList.add('demo');
  renderBanner(proximo_reset);
  renderSeletor(demo_roles);  // ['prescritor', 'dispensador', 'paciente']
}
```

### §3.5 Estado do DB demo — reset horário

DB demo é **arquivo/schema separado** (§3.6). Reset é **horário** via script `scripts/reset_demo_db.py`, idempotente, agendado por cron (configuração do cron entra na Etapa 8/deploy, fora do escopo deste ticket).

`/config/public` retorna `proximo_reset` (ISO 8601 UTC) calculado como "próxima hora cheia". Banner exibe "Reset em XX min" para usuário entender o ciclo.

**Por que horário (não por sessão, não persistente):**
- Por sessão: frustra o fluxo "emiti prescrição → dispenso na próxima aba" (UX ruim para demonstração completa).
- Persistente: acumula lixo, polui experiência do próximo visitante.
- Horário: equilíbrio — visitante tem ~1h para explorar; depois fresh para o próximo.

### §3.6 Isolamento DB demo vs DB de produção

**Arquivo/schema separado.** Não é "mesmo DB + prefixo" nem "mesmo DB + flag `is_demo` por linha". Razões:

1. **CLAUDE.md §6b (escopo institucional):** `org_id`/`unidade_id` são para multi-instituição real, não para isolamento de dados sintéticos. Misturar conflita semanticamente.
2. **Auditoria simples:** "dados de demo nunca chegam em queries de produção" vira propriedade física do arquivo/schema, não regra que precisa ser respeitada em cada query.
3. **Risco regulatório:** mesmo se 99% das queries respeitassem o filtro `is_demo=false`, basta uma query de relatório esquecer e dados sintéticos aparecem em métricas reais.

**Mecanismo:**
- SQLite (modo demo padrão): `PIX_SAUDE_DEMO_DB=../../data/pix_saude_demo.db`. `database.py` resolve `DB_PATH` para esse caminho quando `PICSAUDE_DEMO_MODE=true`.
- PostgreSQL (modo demo em produção hospedada, se aplicável): usar schema `demo` (e.g. `DATABASE_URL=postgresql://.../picsaude?options=-csearch_path=demo`). Mas modo demo em PG não é caso de uso comum do MVP — provavelmente fica SQLite.

### §3.7 Login real vs demo — exclusivo

Inventário real dos endpoints (mapeado contra o código, P1#2 CODEX rodada 1):

| Endpoint | Arquivo:linha | Bloqueio em demo |
|---|---|---|
| `POST /auth/token` (login profissional via senha) | `login.py:78` | ✅ 403 `demo_mode_ativo` |
| `POST /auth/registrar` (criar usuário) | `login.py:154` | ✅ 403 (sem autoregistro em demo) |
| `POST /auth/bootstrap` (primeiro admin) | `login.py:167` | ✅ 403 (sem bootstrap em demo) |
| `POST /auth/refresh` | `login.py:129` | ✅ 403 (KISS — sem refresh em demo; ver §3.7.1) |
| `POST /auth/paciente/solicitar-codigo` (novo OTP paciente) | `login.py:307` | ✅ 403 |
| `POST /auth/paciente/validar-codigo` (novo) | `login.py:354` | ✅ 403 |
| `POST /auth/paciente/enviar-codigo` (OTP legado) | `auth.py:42` | ✅ 403 |
| `POST /auth/paciente/validar-codigo` (legado) | `auth.py:84` | ✅ 403 |
| `GET /auth/me/institucional` | `login.py:246` | ✅ permitido (contexto institucional é leitura autenticada que demo precisa) |
| `POST /demo/login` | `demo.py` (novo) | ✅ único caminho de entrada em demo |

Quando `PICSAUDE_DEMO_MODE=false` (default):
- Todos os endpoints acima funcionam normalmente.
- `/demo/login` retorna 404 (router não registrado).
- `/config/public` retorna `demo_mode=false` e o frontend renderiza login real normal.

#### §3.7.1 KISS — sem refresh em demo (P2#5 CODEX rodada 1)

`/auth/refresh` (login.py:129) reidrata a sessão consultando `usuarios.identificador`. Para que refresh demo funcionasse, o `seed_demo` precisaria criar `usuarios` para os 3 papéis (incluindo paciente, que hoje não tem `usuarios` no `seed_dev`). 

**Decisão KISS:** `/demo/login` emite **apenas access token** (sem refresh). Quando o token expirar (15 min — `JWT_ACCESS_TTL_MINUTES`), o frontend chama `/demo/login` de novo. Justificativa: sessões demo são exploratórias (~15-60 min), o custo de re-login é trivial, e elimina a necessidade de seedar `usuarios.identificador` para paciente. Fica documentado como anti-escopo (§7) que "refresh demo" não está no MVP — se a UX provar ser dolorosa, abrir follow-up para seedar paciente em `usuarios` + permitir refresh.

---

## §4 Especificação por arquivo

### §4.1 `app/config.py` (adições, ~7 linhas)

```python
# Linha ~47, após PICSAUDE_INSTANCE_ORG_ID

# ---------------------------------------------------------------------------
# DEMO_MODE (Ticket 6) — ambiente público de demonstração
# ---------------------------------------------------------------------------
PICSAUDE_DEMO_MODE:  bool = os.getenv("PICSAUDE_DEMO_MODE",  "").lower() == "true"
PICSAUDE_DEMO_ADMIN: bool = os.getenv("PICSAUDE_DEMO_ADMIN", "").lower() == "true"
PIX_SAUDE_DEMO_DB:   str  = os.getenv(
    "PIX_SAUDE_DEMO_DB",
    os.path.join(os.path.dirname(__file__), "../../data/pix_saude_demo.db"),
)
# UUID v4 fixo do instance_id de demo (P1#3 CODEX rodada 1).
# Valor sugerido para o operador exportar quando subir demo:
#   PICSAUDE_INSTANCE_ID=00000000-0000-4000-8000-00000000d3d3
#   PICSAUDE_INSTANCE_ID_PATH=data/.instance_id.demo
# Documentar em docs/PLANO-PRODUCAO-V2.md §7 (Dockerfile/deploy).
```

**Importante (P1#3 CODEX rodada 1):** o `instance.py:87` resolve o path do arquivo `.instance_id` via `PICSAUDE_INSTANCE_ID_PATH` (já existe). E `instance.py:253` respeita `PICSAUDE_INSTANCE_ID` env var quando `PICSAUDE_ENV != "prod"` (já existe). **Não precisamos criar `PICSAUDE_DEMO_INSTANCE_ID` novo** — basta o operador de demo exportar `PICSAUDE_INSTANCE_ID=<UUID v4 fixo>` + `PICSAUDE_INSTANCE_ID_PATH=data/.instance_id.demo` antes de subir. Isso garante: (a) UUID v4 válido (sem "demo-..." inválido); (b) arquivo `.instance_id` separado do de produção (não compartilha raiz); (c) instance_id persistente entre resets de DB (porque é env var + arquivo, não derivado do DB demo que é recriado).

### §4.2 `app/main.py` (guardrail + roteamento, ~40 linhas)

**Antes da linha 88 (`_validate_jwt_secret_at_boot(...)`):**

```python
def _validate_demo_mode_at_boot(env: str, demo: bool) -> None:
    """
    Guardrail de produção — recusa boot se PICSAUDE_DEMO_MODE=true e
    PICSAUDE_ENV=prod simultaneamente.

    Razões:
    - Produção nunca pode subir em modo demo (mistura dados reais e fictícios).
    - DEMO_MODE substitui login real — produção sem login é inaceitável.

    Em dev/test, modo demo é aceitável. Função pura — testável.

    Raises:
        RuntimeError: quando env == "prod" e demo == True.
    """
    if env == "prod" and demo:
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ERRO DE CONFIGURAÇÃO — INICIALIZAÇÃO BLOQUEADA              ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  PICSAUDE_ENV=prod e PICSAUDE_DEMO_MODE=true são             ║\n"
            "║  incompatíveis. Modo demo nunca pode rodar em produção.      ║\n"
            "║                                                              ║\n"
            "║  Para demo: PICSAUDE_ENV=dev ou stg.                         ║\n"
            "║  Para produção: PICSAUDE_DEMO_MODE não definida.             ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        )


from app.config import PICSAUDE_DEMO_MODE  # noqa: E402

_validate_demo_mode_at_boot(PICSAUDE_ENV, PICSAUDE_DEMO_MODE)
```

**No bloco de import de routers (linha 17):**

```python
# Routers do modo demo só são registrados quando flag ativa.
from app.routers import demo as demo_router_module
from app.routers import config_publico as config_publico_router_module
```

**No bloco de registro de routers (provavelmente após `app.include_router(...)` dos outros):**

```python
app.include_router(config_publico_router_module.router)  # sempre — frontend precisa do estado
if PICSAUDE_DEMO_MODE:
    app.include_router(demo_router_module.router)
```

### §4.3 `app/database.py` (helper compartilhado, ~20 linhas) — **REESCRITO após P1#1 CODEX rodada 1**

**O risco que esta seção fecha:** o `database.py` atual resolve `DATABASE_URL` no import top-level (linha 17-23) usando `DB_PATH`. Mas a função `get_conn()` (linha 218-239) **importa `DB_PATH` de novo, do `config`, ignorando qualquer roteamento que tenha sido feito no engine**. Como os routers usam `get_tx()` → `get_conn()`, demo continuaria lendo/escrevendo no SQLite de produção.

**Fix obrigatório:** criar um helper único `_resolve_sqlite_db_path()` no próprio `database.py`, e usá-lo nos DOIS pontos.

```python
# Linha ~13 (logo após o logger, ANTES da resolução de DATABASE_URL)

def _resolve_sqlite_db_path() -> str:
    """
    Resolve o path SQLite respeitando PICSAUDE_DEMO_MODE.
    Usado pelo engine SQLAlchemy E pelo get_conn() — garante isolamento real.
    P1#1 TICKET-6 / CODEX rodada 1.
    """
    from app.config import DB_PATH, PICSAUDE_DEMO_MODE, PIX_SAUDE_DEMO_DB
    return PIX_SAUDE_DEMO_DB if PICSAUDE_DEMO_MODE else DB_PATH


# Linha 21-23 (substituir o bloco atual)
if _USE_SQLITE:
    _resolved_db_path = _resolve_sqlite_db_path()
    DATABASE_URL = f"sqlite:///{_resolved_db_path}"
    from app.config import PICSAUDE_DEMO_MODE as _DEMO  # apenas para log
    logger.warning(
        "DATABASE_URL não configurada — fallback para SQLite (%s, path=%s). "
        "Para produção: export DATABASE_URL=postgresql://...",
        "modo demo" if _DEMO else "modo dev",
        _resolved_db_path,
    )

# Linha 227 (substituir a importação direta de DB_PATH)
def get_conn():
    if _USE_SQLITE:
        import sqlite3
        _sqlite_path = _resolve_sqlite_db_path()  # ← FIX P1#1
        if not os.path.exists(_sqlite_path):
            raise RuntimeError(f"SQLite DB não encontrado: {_sqlite_path}")
        # ... resto idêntico
```

**Verificação obrigatória:** teste §5.6 abaixo cobre exatamente este cenário (chama `get_conn()` diretamente com `DEMO_MODE=true` e confirma que abre o DB demo, não o de produção).

Para PG: a fonte de verdade do schema demo fica em `DATABASE_URL` (`options=-csearch_path=demo`). Não é responsabilidade deste ticket gerenciar criação do schema (entra em scripts de provisionamento da Etapa 8).

### §4.4 `app/routers/demo.py` (novo, ~100 linhas)

Endpoints:

- `POST /demo/login` — recebe `{role: "prescritor"|"dispensador"|"paciente"|"admin"}`. Valida role contra `_papeis_demo_disponiveis()`. Carrega persona canônica do DB demo. Emite **apenas access token** via `criar_access_token(sub, role, nome)` em `auth/jwt.py:56` (KISS — §3.7.1, P2#5 CODEX rodada 1). Retorna `{access_token, role, nome, sub}`. **Não exige autenticação prévia** — endpoint é o ponto de entrada do demo. **Sem refresh token** — frontend chama `/demo/login` de novo se expirar.
- `GET /demo/info` — retorna `{personas: [{role, nome, sub, identificador_visivel}], proximo_reset: "ISO timestamp", ultimo_reset: "ISO timestamp"}`. Para frontend mostrar antes do clique.
- Estrutura `_papeis_demo_disponiveis()` retorna `["prescritor", "dispensador", "paciente"] + (["admin"] if PICSAUDE_DEMO_ADMIN else [])`.
- Cada papel tem uma persona única em modo demo (não há "qual prescritor você quer ser" — é único).

**JWT_SECRET continua obrigatório em demo** (P1#3 5D continua valendo — guardrail `_validate_jwt_secret_at_boot` aborta boot se secret fraco). O JWT emitido tem o mesmo formato do JWT real (`sub`, `role`, `nome`, `tipo: "access"`). Isso garante que **5C continua funcionando** — o owner check em `prescricoes.py` etc. compara `sub` JWT com `cns_prescritor` do payload; em demo, o frontend preenche `cns_prescritor` com o CNS da persona canônica, e bate.

**`role` do paciente é `"paciente"`, não `"cidadao"`** (P2#4 CODEX rodada 1) — ver §3.3 fim. Se `PERFIS_VALIDOS` em `domain/roles.py` rejeitar, abrir #55 como dívida do contrato de roles.

### §4.5 `app/routers/config_publico.py` (novo, ~40 linhas)

```python
from fastapi import APIRouter, Response

@router.get("/config/public")
def get_config_publico(response: Response):
    # P3#10 CODEX rodada 1 — proximo_reset muda com o tempo;
    # cache do navegador atrasaria o banner.
    response.headers["Cache-Control"] = "no-store"
    return {
        "version":       PICSAUDE_VERSION,
        "demo_mode":     PICSAUDE_DEMO_MODE,
        "demo_admin":    PICSAUDE_DEMO_ADMIN,
        "demo_roles":    _papeis_demo_disponiveis() if PICSAUDE_DEMO_MODE else [],
        "proximo_reset": _proximo_reset_horario() if PICSAUDE_DEMO_MODE else None,
        "instance_id":   None,  # NÃO expor instance_id real publicamente
    }
```

Endpoint público — sem autenticação. **Não vaza nada sensível** (versão é pública; demo_mode é estado público; roles são lista fixa). `Cache-Control: no-store` garante que o banner não fica atrasado (P3#10 CODEX rodada 1).

### §4.6 `app/routers/auth.py` e `app/routers/login.py` (bloquear 8 endpoints em demo, ~35 linhas) — **REESCRITO após P1#2 CODEX rodada 1**

Lista correta dos endpoints (mapeada contra o código real, não inventada):

**`login.py` — 6 endpoints:**
- `POST /auth/token` (linha 78)
- `POST /auth/refresh` (linha 129) — bloqueio KISS, §3.7.1
- `POST /auth/registrar` (linha 154)
- `POST /auth/bootstrap` (linha 167)
- `POST /auth/paciente/solicitar-codigo` (linha 307)
- `POST /auth/paciente/validar-codigo` (linha 354)

**`auth.py` — 2 endpoints (legados):**
- `POST /auth/paciente/enviar-codigo` (linha 42)
- `POST /auth/paciente/validar-codigo` (linha 84)

**Permitido em demo:** `GET /auth/me/institucional` (login.py:246) e todos os endpoints autenticados em `auth.py:126+` (`/paciente/prescricoes`, etc.) — autenticação já garantida pelo `require_role`; demo entra via `/demo/login`.

**Padrão de bloqueio** — repetir no topo de cada um dos 8 handlers:

```python
from app.config import PICSAUDE_DEMO_MODE

if PICSAUDE_DEMO_MODE:
    raise HTTPException(
        status_code=403,
        detail={
            "codigo": "demo_mode_ativo",
            "mensagem": "Login real desabilitado em modo demo. Use o seletor em /.",
        },
    )
```

**Sobre KISS vs helper** (P2 CODEX rodada 1, respondida): por serem 8 endpoints concentrados em 2 arquivos, **manter inline** (KISS, padrão do 5C). Se virar 12+ em algum follow-up, refatorar para `reject_if_demo` dependency.

**`/auth/refresh` bloqueado:** consequência direta da decisão KISS §3.7.1 (sem refresh em demo). Frontend chama `/demo/login` de novo na expiração.

### §4.7 `app/domain/pdf_prescricao.py` (marca d'água DEMO, ~20 linhas) — **SIMPLIFICADO após P2#6 CODEX rodada 1**

Adicionar parâmetro `is_demo: bool = False` na função de geração. Quando `True`, desenhar texto "DEMO" diagonal em fonte grande, cor cinza translúcida, sobre cada página.

**Determinação de `is_demo` = `PICSAUDE_DEMO_MODE` runtime.** O chamador (em `routers/prescricoes.py:930` — `get_pdf_prescricao`) passa `PICSAUDE_DEMO_MODE` direto.

**Por que não derivar do `instance_id` da prescrição (P2#6 CODEX rodada 1):** confirmado que `prescricoes` (o model em `app/models/prescricao.py:11`) **não tem campo `instance_id`** — `instance_id` mora no ledger (`prescricao_eventos`) e no outbox. Derivar via consulta ao primeiro evento da prescrição seria possível mas custa um JOIN extra por PDF gerado, sem ganho real no caso comum (PDF gerado enquanto demo ainda está ativo).

**Trade-off documentado:** se demo for desligado mas o DB demo for preservado e algum cliente legado consulte um PDF antigo via API, o PDF sai sem marca d'água. Aceitável para MVP. Se vier a importar (forense), abrir follow-up **#59** (renumerado de #56 em 2026-05-25 — colisão com GFI de `js/demo-bootstrap.js`) para derivar via consulta ao evento (`tipo_evento='prescricao_emitida'` em `prescricao_eventos`, comparando `instance_id` com `PICSAUDE_INSTANCE_ID` configurado para demo).

### §4.8 `seed_demo.py` (novo, ~100 linhas)

Idempotente. Cria 3 personas canônicas + paciente com "carteira digital" (necessária porque 5A rejeita emissão sem carteira). Estrutura espelha `seed_dev.py`.

Personas (§3.3, identificadores novos P3#8 CODEX rodada 1):
- **Prescritor:** CNS `980001112223334`, nome "Dra. Demo Maria Souza", role `prescritor`. Insert em `usuarios` (senha não importa — não há OTP em demo, mas o owner check de 5C compara `sub` JWT com `cns_prescritor`, então precisa estar em `prescritores` também) e `prescritores`.
- **Dispensador:** CNPJ `99999999000191`, nome "Farmácia Demo Central". Insert em `usuarios`, `prestadores`, `unidades`.
- **Paciente:** CPF `12345678909`, nome "João Demo da Silva". Insert em `pacientes`. **NÃO inserir em `usuarios`** (KISS §3.7.1 — sem refresh em demo, paciente não precisa de `usuarios.identificador` para reidratar sessão).

> **Nota sobre "carteira digital" do paciente:** a tabela `carteiras_digitais` não existe hoje (Dívida B-Carteira #36 ainda aberta). Para o MVP do demo, basta o paciente existir em `pacientes` com um marcador equivalente que o 5A aceita como "tem carteira" (provavelmente `paciente_existia=True` da inferência §3.1 do TICKET-5A). Code valida durante implementação consultando como 5A está checando hoje. Se precisar de mais, abrir follow-up para "carteira mockada do paciente demo".

> **`role="paciente"`, não `"cidadao"`** (P2#4 CODEX rodada 1): coerente com os routers operacionais (`pacientes.py:21`). Validar contra `PERFIS_VALIDOS` em `domain/roles.py:35` durante implementação.

### §4.9 `scripts/reset_demo_db.py` (novo, ~50 linhas)

Script idempotente:

1. Aborta se `PICSAUDE_ENV=prod` ou se `PICSAUDE_DEMO_MODE` não estiver setado.
2. Conecta no `PIX_SAUDE_DEMO_DB`.
3. Drop + recria todas as tabelas via `init_db()` do `database.py`.
4. Roda `seed_demo.main()`.
5. Imprime resumo.

Uso: `cd backend && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py`. Em produção/cron: `0 * * * * cd /app && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py >> /var/log/picsaude/demo-reset.log 2>&1`.

### §4.10 Frontends — **EXPANDIDO após P2#7 CODEX rodada 1**

`index.html` (~80 linhas):
- Boot script chama `/config/public` **dentro do `<head>` (síncrono ou no early `<script>` do `<body>`)** para evitar flash de UI sem banner. Adiciona `class="demo-loading"` ao `<body>` por default (CSS esconde o banner) e troca para `class="demo"` quando a resposta chega.
- Se `demo_mode=true`:
  - Renderiza banner amarelo top: "MODO DEMO — dados fictícios, nenhuma prescrição é real. Reset em XX min."
  - Renderiza segmented control com 3 botões: "Entrar como Prescritor / Dispensador / Paciente".
  - Cada clique → `POST /demo/login` com role → grava `access_token` em `sessionStorage` → redireciona para `/{prescritor,dispensador,cidadao}.html`.
  - Se URL tem `?demo_role=X`, executa o clique automaticamente.
- Se `demo_mode=false`:
  - Renderiza fluxo de login real atual (preservado).

`prescritor.html`, `dispensador.html`, `cidadao.html` (~25 linhas cada):
- Boot script chama `/config/public`.
- Se `demo_mode=true`, mostra banner permanente top + lê token de `sessionStorage`.
- Se `demo_mode=false`, comportamento atual.

**`clinica.html` (~20 linhas) — P2#7 CODEX rodada 1:**
- Boot script chama `/config/public`.
- Se `demo_mode=true`: renderiza banner amarelo "MODO DEMO" + mensagem "Use o seletor em / para entrar" + botão "Ir para o seletor" que redireciona para `index.html`. **Não tenta fazer login via `/auth/token`** (que está bloqueado em demo).
- Se `demo_mode=false`: comportamento atual (login profissional via `/auth/token` + `DEV_PRESET_CONTEXT=true`).

**`validar.html` (~10 linhas) — P2#7 CODEX rodada 1:**
- Continua público (validação é caminho público).
- Quando a resposta de `GET /prescricoes/{proto}/validacao` indica que a prescrição foi emitida em modo demo (campo a definir — pode vir como flag `is_demo` no response da validação, OU consultando `/config/public` para saber se o sistema atual está em demo), exibir **selo amarelo "PRESCRIÇÃO DEMO — sem efeito clínico"** próximo ao status de validação.

---

## §5 Critérios de aceite — testes obrigatórios (10 cenários)

Arquivo: `backend/tests/test_demo_mode.py`.

### §5.1 `test_boot_com_demo_mode_true_carrega_router_demo`
- Setup: `PICSAUDE_DEMO_MODE=true`, `PICSAUDE_ENV=dev`.
- Assert: `GET /demo/info` retorna 200; lista 3 personas.
- Assert complementar: sem flag, `GET /demo/info` retorna 404.

### §5.2 `test_seletor_emite_jwt_com_sub_correto_por_role`
- Para cada papel em `["prescritor", "dispensador", "paciente"]`:
  - `POST /demo/login` com `{role: <papel>}`.
  - Decodificar JWT retornado.
  - Assert: `payload["role"] == <papel>`, `payload["sub"]` = identificador canônico da persona (CNS/CNPJ/CPF), `payload["nome"]` começa com "Demo" ou "Dr(a). Demo".

### §5.3 `test_auth_login_bloqueado_em_demo_mode`
- Setup: `DEMO_MODE=true`.
- Request: `POST /auth/login` com payload válido.
- Assert: 403 com `codigo: "demo_mode_ativo"`. Idem para `/auth/verificar-otp` e `/login/usuario`.

### §5.4 `test_config_publico_retorna_estado`
- `GET /config/public` (sem auth) com `DEMO_MODE=true`:
  - Assert: `demo_mode=true`, `demo_roles=["prescritor", "dispensador", "paciente"]`, `proximo_reset` é ISO timestamp.
  - Assert: `response.headers["Cache-Control"] == "no-store"` (P3#10 CODEX rodada 1).
- Idem com `DEMO_MODE=false`:
  - Assert: `demo_mode=false`, `demo_roles=[]`, `proximo_reset=null`.

### §5.5 `test_admin_fora_do_demo_publico`
- `DEMO_MODE=true`, `DEMO_ADMIN=false`.
- `POST /demo/login` com `{role: "admin"}` → 422 ou 403 (papel não disponível).
- `GET /config/public` → `demo_roles` não contém `admin`.

### §5.5b `test_admin_dentro_do_demo_admin`
- `DEMO_MODE=true`, `DEMO_ADMIN=true`.
- `POST /demo/login` com `{role: "admin"}` → 200, JWT válido com `role=admin`.
- `GET /config/public` → `demo_roles` contém `admin`.

### §5.6 `test_isolamento_db_demo_vs_prod`
- **Importante (P3#9 CODEX rodada 1):** `database.py` e `main.py` resolvem config no import top-level. Para alternar `PICSAUDE_DEMO_MODE` no mesmo processo de teste, use **subprocess** (`subprocess.run([...], env=...)`) ou **`importlib.reload`** de `app.database` + `app.config`. Sem isso, o teste passa por engano (false-green) porque o engine já foi resolvido com a primeira flag vista.
- Criar arquivo `pix_saude_pe.db` (prod) com 1 paciente "Real Maria".
- Setar `DEMO_MODE=true`, `PIX_SAUDE_DEMO_DB=/tmp/test_demo.db`.
- Reload de `app.database` + inicializar app + rodar `seed_demo.main()`.
- Assert: `get_conn()` chamado diretamente abre `/tmp/test_demo.db` (P1#1 — testar a função, não só o engine).
- Assert: query em `pacientes` retorna persona demo (João Demo), **não** Real Maria.
- Trocar para `DEMO_MODE=false`, reinicializar (subprocess ou reload).
- Assert: query em `pacientes` retorna Real Maria, **não** João Demo.

### §5.7 `test_pdf_com_marca_dagua_demo`
- `DEMO_MODE=true`. Persona prescritor emite prescrição via `POST /prescricoes`. Gerar PDF via `GET /{proto}/pdf`.
- Assert: bytes do PDF contêm string "DEMO" como texto desenhado (parseável via `pdfplumber` ou `PyPDF2`).
- Caminho `DEMO_MODE=false`: PDF não contém "DEMO" como marca d'água.

### §5.8 `test_banner_ui_aparece_em_demo`
- Teste integração frontend (Playwright ou request mock):
  - `DEMO_MODE=true` → resposta de `/` (ou `index.html`) contém classe `.demo` ou marker no DOM após boot script.
  - `DEMO_MODE=false` → marker ausente.

### §5.9 `test_instance_id_demo_nos_eventos`
- `DEMO_MODE=true`. Persona prescritor emite prescrição.
- Assert: linha em `prescricao_eventos` tem `instance_id` igual ao instance_id de demo (formato a calibrar com Code — pode ser prefixo `demo-` ou UUID determinístico).

### §5.10 `test_guard_prod_e_demo_simultaneo_aborta_boot`
- **Padrão de teste (P3#9 CODEX rodada 1):** testar a **função pura** `_validate_demo_mode_at_boot(env, demo)` diretamente em `tests/test_config_guards.py` (mesmo padrão do `_validate_jwt_secret_at_boot` do 5D). Isso evita reload de módulos para esse cenário específico.
- Testes da função pura:
  - `_validate_demo_mode_at_boot("prod", True)` → `RuntimeError` com texto "INICIALIZAÇÃO BLOQUEADA".
  - `_validate_demo_mode_at_boot("prod", False)` → não levanta.
  - `_validate_demo_mode_at_boot("dev", True)` → não levanta.
  - `_validate_demo_mode_at_boot("dev", False)` → não levanta.
- Teste integrado opcional (subprocess): subir uvicorn com `PICSAUDE_ENV=prod PICSAUDE_DEMO_MODE=true` e confirmar exit code não-zero + mensagem em stderr.

---

## §6 Verificação automatizada

### Pré-implementação (Code grep)

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Confirmar que PICSAUDE_DEMO_MODE não existe ainda em lugar nenhum
grep -rn "PICSAUDE_DEMO_MODE\|demo_mode" backend/app/ 2>&1 | head
# Esperado: zero matches (campo novo)

# 2. Confirmar guardrails atuais (modelo a seguir)
grep -nE "_validate.*_at_boot" backend/app/main.py
# Esperado: _validate_jwt_secret_at_boot

# 3. Confirmar seed_dev.py atual (modelo a seguir para seed_demo.py)
wc -l backend/seed_dev.py
# Esperado: ~280 linhas
```

### Pós-implementação

```bash
# 1. Novo módulo demo registrado condicionalmente
grep -n "PICSAUDE_DEMO_MODE\|demo_router_module" backend/app/main.py
# Esperado: pelo menos 2 matches (import condicional + include_router condicional)

# 2. seed_demo.py criado
ls -la backend/seed_demo.py backend/scripts/reset_demo_db.py
# Esperado: ambos existem

# 3. Endpoints OTP bloqueiam quando flag ativa
grep -n "demo_mode_ativo" backend/app/routers/auth.py backend/app/routers/login.py
# Esperado: pelo menos 3 matches (login, verificar-otp, login/usuario)

# 4. Suite focal — 10/10 verdes
cd backend
pytest tests/test_demo_mode.py -v
# Esperado: 10/10 pass

# 5. Suite completa — sem regressão
pytest -q
# Esperado: contagem de falhas igual à de antes do 6 (27 pré-existentes inalteradas)
```

---

## §7 Anti-escopo

Itens explicitamente **fora deste ticket**:

- **Cron real no servidor.** Reset horário tem o script (`scripts/reset_demo_db.py`), mas o agendamento via cron entra no Dockerfile / deploy (Etapa 7/8). Documentar comando esperado em `docs/PLANO-PRODUCAO-V2.md §7`.
- **Carteira digital persistente** (Dívida B-Carteira #36). O paciente demo tem carteira sinalizada da forma mais simples possível com o modelo atual. Refator para tabela `carteiras_digitais` formal fica para depois.
- **Validator de CPF nos schemas** (#44). CPFs do seed escolhidos com DV válido, mas se #44 for implementado e usar regra mais estrita, os seeds podem precisar atualizar — não bloqueia o ticket.
- **Cluster catálogo regulatório #39, /health/db #40, etc.** — todos fora.
- **`clinica.html` e `validar.html`** — fora do banner desta passada.
- **Login social (Google, gov.br)** — não pertence ao MVP.
- **Múltiplas personas por papel** ("escolha entre Dr. João, Dra. Maria") — fora; uma persona única por papel.
- **Histórico/seed com prescrições pré-existentes** ("para você ver a tela populada") — fora; seed começa vazio, visitante popula durante a sessão.

### §7.1 Dívidas previstas (abrir como tasks ao final do ticket)

| Tema | Severidade |
|---|---|
| Reset horário rodado por cron no Dockerfile + monitoramento | Bloqueador deploy (Etapa 8) |
| Carteira digital formal para o paciente demo (Dívida B-Carteira #36) | Pós-MVP |
| Sub-personas (múltiplos prescritores demo, multi-prescritor cross-tenant) | Pós-MVP |

---

## §8 Predecessoras e classe

- **Predecessor:** Etapa 5 fechada em `2bf5e7d`. Etapa 4 fechada em `9cc339f`. Sem dependência circular.
- **Classe:** `core` — toca autenticação (`auth/jwt.py`, `auth/dependencies.py`), boot (`main.py`), config, banco, endpoint público novo. CLAUDE.md §10 lista "RBAC e autenticação" e "Protocolos públicos" como core obrigatório.
- **Volume previsto:** ~330 backend + ~150 frontend + ~300 testes = ~780 linhas. Regra 2 estrita aplica.
- **Bloqueador de deploy** (Etapa 8 — não dá para subir frontend público sem demo + sem login real funcionando).

---

## §9 Prompt sugerido ao Code

Consolidado em **§12** após integração da CODEX rodada 1 (taxa 10/10).

---

## §10 Observações CODEX rodada 1 (2026-05-24) — integradas

CODEX revisou a rodada 0 do ticket contra o repo real em `/Users/fabianotonacoborges/PicSaude_Dev` e retornou **3 P1 + 4 P2 + 3 P3**. **Taxa de aceitação: 10/10.**

| # | Sev | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | P1 | `database.py:21` engine vs `database.py:227` `get_conn()` — ambos importam `DB_PATH` separadamente; demo continuaria lendo prod se só o engine fosse roteado | ✅ Aceito integral | §2.1 atualizado; §4.3 REESCRITO com helper `_resolve_sqlite_db_path()` compartilhado; §5.6 teste adicional sobre `get_conn()` direto |
| 2 | P1 | Endpoints citados (`/auth/login`, `/auth/verificar-otp`, `/login/usuario`) não existem no código atual. Reais: `/auth/token`, `/auth/refresh`, `/auth/registrar`, `/auth/bootstrap`, `/auth/paciente/{solicitar,validar}-codigo` (login.py) + `/auth/paciente/{enviar,validar}-codigo` (auth.py legados) | ✅ Aceito integral | §2.1 atualizado; §3.7 tabela com inventário real; §4.6 REESCRITO |
| 3 | P1 | "`instance_id` específico de demo" não garantido — demo pode reutilizar `.instance_id` compartilhado; `demo-...` é UUID inválido | ✅ Aceito integral | §3.7+§4.1: usar `PICSAUDE_INSTANCE_ID=<UUID v4 fixo>` + `PICSAUDE_INSTANCE_ID_PATH=data/.instance_id.demo` (env vars já existentes em `instance.py:97`+`instance.py:253`) |
| 4 | P2 | `roles.py:35` declara `cidadao` mas routers usam `paciente` (inconsistência latente) | ✅ Aceito | §3.3 + §4.4 + §4.8 nota explícita "demo usa `role=paciente`" + abrir #55 como dívida de contrato de roles se Code/CODEX rodada 2 detectar rejeição em `PERFIS_VALIDOS` |
| 5 | P2 | Refresh token reidrata sessão via `usuarios.identificador`. Seed precisaria criar `usuarios` para paciente também | ✅ Aceito (KISS) — não emitir refresh em demo | §3.7.1 novo; §4.4 sem refresh; §4.6 bloqueia `/auth/refresh` também; §4.8 paciente NÃO entra em `usuarios` |
| 6 | P2 | Marca d'água por `instance_id` não encaixa: `prescricoes` (`models/prescricao.py:11`) não tem `instance_id`; ele mora no ledger/outbox | ✅ Aceito (KISS) — `is_demo=PICSAUDE_DEMO_MODE` runtime | §4.7 SIMPLIFICADO; trade-off documentado (PDF antigo perde marca se demo for desligado) + follow-up **#59** condicional (renumerado de #56 em 2026-05-25) |
| 7 | P2 | `clinica.html` tem login próprio em `/auth/token` + `DEV_PRESET_CONTEXT=true` — sem tratamento demo, vira tela quebrada | ✅ Aceito integral | §2.2 expandido (clinica.html + validar.html no escopo); §4.10 REESCRITO com banner+redirect em clinica e selo "DEMO" em validar |
| 8 | P3 | Reaproveitar CNS/CNPJ do `seed_dev.py` aumenta risco de colisão | ✅ Aceito | §3.3: identificadores NOVOS (CNS `980001112223334`, CNPJ `99999999000191`; CPF do paciente mantido — escolha intencional de marketing) |
| 9 | P3 | Testes que alternam `PICSAUDE_DEMO_MODE` precisam subprocess ou `importlib.reload` (config resolvida no import) | ✅ Aceito | §5.6 nota explícita; §5.10 padrão da função pura `_validate_demo_mode_at_boot` (sem reload) |
| 10 | P3 | `/config/public` retorna `proximo_reset` volátil — sem `Cache-Control: no-store`, banner fica atrasado | ✅ Aceito | §4.5 header adicionado; §5.4 assert do header |

### §10.1 Respostas às perguntas direcionadas (rodada 0 → rodada 1)

CODEX respondeu às 9 perguntas que deixei reservadas em §10 rodada 0:

- **`criar_access_token` é a função certa** → §4.4 confirmado.
- **JWT_SECRET continua obrigatório em demo** → §4.4 reforçado (5D continua valendo).
- **Não forçar PG no teste de isolamento** → §5.6 cobre SQLite só (PG fica em scripts da Etapa 8).
- **Helper `reject_if_demo` local OK** → §4.6 inline KISS (8 endpoints, 2 arquivos — não vale abstração).
- **Ledger demo é ledger normal no DB demo + `instance_id` demo UUID v4 fixo** → §3.7 + §4.1 (env vars existentes do `instance.py`).

### §10.2 Achados pendentes para rodada 2 (pós-impl)

Nenhum no momento. A rodada 1 cobriu o ticket inteiro. Rodada 2 atacará o commit do Code.

---

## §11 Status final — Etapa 6 FECHADA (2026-05-27)

### §11.1 Marcos da Etapa 6

| Marco | Commit | Data | Conteúdo |
|---|---|---|---|
| TICKET-6 — rodada 0 + impl | `94f73cd` | 2026-05-24 | feat(6) DEMO_MODE com sessões pré-semeadas + 7 decisões + isolamento DB + boot guards |
| TICKET-6.1 — follow-up X.Y após CODEX rodada 2 (3 P1 + 2 P2) | `9eb7228` | 2026-05-24 | fix(6.1) isolamento CNES via helper compartilhado + hidratação demo no frontend + guard JWT hermético |
| TICKET-6 — arquivamento docs | `a01fec6` | 2026-05-24 | docs(6) arquivar TICKET-6 + TICKET-6.1 + briefings CODEX/Jules + renumeração #56-58 → #59-61 |
| TICKET-DX-PRE-EXTENSAO — Regra 3 (Jules audit P2#4 + P2#10) | `5db20ef` | 2026-05-26 | fix(dx) conftest skip module-level sem PG + bloco Windows nos ISSUEs |
| TICKET-6.2 — follow-up X.Y após checklist §4.2 + CODEX rodada 0 sobre logs | `6c0da36` | 2026-05-27 | fix(6.2) demo correções pré-reunião — CNES graceful + rate limit 10x demo + UUID/REC-XXXX no comprovante físico |

### §11.2 Trilha CODEX

- **Rodada 1** (pré-impl, sobre rodada 0 do TICKET-6) — integrada em §10 do TICKET-6: 3 P1 + 4 P2 + 3 P3, taxa 10/10.
- **Rodada 2** (pós-impl, sobre `94f73cd`) — briefing em `backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md`: 3 P1 + 2 P2 + 1 P3. P1#1 (CNES), P1#2 (hidratação frontend), P1#3 (guard JWT) → resolvidos em `9eb7228` (TICKET-6.1).
- **Jules** (fim de etapa, em paralelo à rodada 2) — briefing em `backend/docs/codex/JULES-RODADA-FIM-ETAPA6.md`: resposta lateral, 6 órfãos triados (4 para §11.5 abaixo; 2 para README + CONTRIBUTING-EXTENSAO).
- **Rodada 0 ad-hoc** (sobre logs do demo, 2026-05-26) — 3 achados emergentes do checklist manual §4.2: CNES schema/fallback, rate limit hostil, mismatch REC-XXXX vs UUID → resolvidos em `6c0da36` (TICKET-6.2).
- **Rodada 3** (pós-pós-impl, sobre range `9eb7228..6c0da36`, 2026-05-27) — **zero P1**. 1 P2 emergente sobre Fix C (calibração do critério, não bug do código — ver §11.4 abaixo).

### §11.3 Achados do CODEX rodada 3 (2026-05-27) integrados

| # | Severidade | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | — | TICKET-6.1 P1#1 CNES validado | ✅ confirmado | helper `_resolve_sqlite_db_path` + fixture patcha helper |
| 2 | — | TICKET-6.1 P1#2 hidratação frontend validado | ✅ confirmado | sem race com `/config/public`, role divergente limpa sessão |
| 3 | — | TICKET-6.1 P1#3 guard JWT validado | ✅ confirmado | smoke `test_smoke_import_time_em_prod_falha` passa |
| 4 | — | TICKET-6.2 Fix A graceful CNES validado | ✅ confirmado | try/except só engole "no such table"; outras OperationalError re-raise |
| 5 | — | TICKET-6.2 Fix B rate limit validado | ✅ confirmado | multiplicador import-time aceitável; brute force OTP em demo bloqueado por `demo_mode_ativo` |
| 6 | P2 | TICKET-6.2 Fix C — cenário "física online → UUID sem hint" não atingível no comprovante imediato (fire-and-forget viola sincronia) | ✅ Aceito como calibração documental, não fix técnico | §11.4 abaixo + nota inline em §3.4 do TICKET-6.2 |

### §11.4 Lapidação documentada — Fix C e o contrato fire-and-forget

O critério §3.4 do TICKET-6.2 dizia que receita física com backend online deveria exibir UUID sem hint no comprovante. CODEX rodada 3 demonstrou que esse cenário **não é atingível** no comprovante imediato sem violar o contrato fire-and-forget do CLAUDE.md §6: `exibirSucessoEImpressao` roda **antes** do `.then()` da promessa `/prescricoes/fisica` resolver, então `protocolo_backend` está sempre undefined no momento da impressão, independente do backend estar online.

**Calibração correta:** receita física **sempre** exibe REC-XXXX + hint amber no comprovante imediato, por design. O paciente acessa o UUID depois, via outro caminho (entrar como paciente, abrir a receita no histórico, copiar protocolo dali). Isso é coerente com:

- CLAUDE.md §6 — emissão física é fire-and-forget; impressão não pode depender de backend online.
- Princípio do PicSaúde como plataforma de circulação auditável: receita física tem trade-off explícito de menor rastreabilidade pública, e o hint amber **é o sistema sendo honesto sobre essa diferença** (não bug).

**Achado pedagógico** (para a reunião com extensionistas 2026-05-27 e além): o P2 do CODEX revelou uma incoerência entre o critério de aceite (escrito pelo Arquiteto) e o contrato arquitetural (escrito no CLAUDE.md ontem). O critério estava errado, não o código. Esse é o tipo de tensão que aparece quando se escreve critério sem revisar contrato — e exemplo bonito de como CODEX como revisor independente captura inconsistências que o próprio Arquiteto não percebe.

Atualização do critério §3.4 do TICKET-6.2: trocar "Receita física com backend online → comprovante mostra UUID, sem hint" por "Receita física → comprovante **sempre** mostra REC-XXXX + hint amber, por contrato fire-and-forget". Nota inline já registrada no §10 do TICKET-6.2.

### §11.5 Órfãos do Jules-audit (registrados, não bloqueiam)

Quatro órfãos do briefing do Jules que viraram dívida documentada (não entraram em ticket próprio porque escopo pequeno):

- §3.1 Jules — diagnóstico `radon cc` sobre `/demo/login` (complexidade declarada pelo próprio Code, sem ação imediata).
- §3.2/§3.8 Jules — duplicação de `_reject_if_demo` em 6 endpoints. Aceitável; fica como GFI eventual.
- §3.3 Jules — naming `PIX_SAUDE_` (legado) vs `PICSAUDE_` (canônico). Vira issue de naming refactor pós-Etapa 8.

### §11.6 Achado lateral identificado pelo CODEX rodada 3 (fora do escopo)

CODEX reportou 7 falhas pré-existentes em `test_binding_icp.py` (CPF OID parsing) **fora do range/escopo** desta etapa. Vira ticket próprio pós-reunião: `TICKET-BINDING-ICP-CPF-OID-PARSING` (a abrir). Não bloqueia Etapa 6.

### §11.7 Bloqueador seguinte

Etapa 5C-bis — autorização mínima nos 5 subdomínios sucessores (pedidos de exame, laudos, agendamentos, circulação diagnóstica, hospitalar). Decidida em 2026-05-26 (ver §11.1 do TICKET-5C-BIS-0-HELPER-OWNERSHIP e PLANO-PRODUCAO-V2 v2.1).

---

## §12 Prompt final ao Code

Pronto para implementação. Integrada: CODEX rodada 1 (3 P1 + 4 P2 + 3 P3 — taxa 10/10).

````
Tarefa: TICKET-6 — DEMO_MODE com sessões pré-semeadas.
Classe: core (toca config, boot, auth, database, ledger via instance_id).
Pacto: Regra 2 estrita (volume ~780 linhas: ~330 backend + ~180 frontend + ~300 testes).

LOCAL DO TICKET
───────────────
backend/docs/tickets/TICKET-6-DEMO-MODE.md

LEIA O TICKET INTEIRO antes de implementar — em especial:
  §1.1 tese central, §3 (7 decisões + KISS §3.7.1),
  §4 (spec por arquivo, com helper compartilhado §4.3),
  §5 (10 cenários — incluir nota P3#9 sobre subprocess/importlib.reload),
  §7 anti-escopo, §10 (achados CODEX rodada 1).

CONTEXTO REGULATÓRIO (§1)
─────────────────────────
LGPD + CLAUDE.md §4 (proteção de dados é estrutural). Demo público nunca pode
expor ou misturar dados reais. Demo nunca pode subir em produção.

ESCOPO
──────
TOCAR (produção — 5 arquivos editados + 5 arquivos novos):
  - backend/app/config.py            (V1 — adicionar 3 flags + nota instance_id)
  - backend/app/main.py              (V2 — guardrail _validate_demo_mode_at_boot + registro condicional)
  - backend/app/database.py          (V3 — helper _resolve_sqlite_db_path REUSADO no get_conn) ★ P1#1
  - backend/app/routers/auth.py      (V6 — bloquear 2 endpoints OTP legados) ★ P1#2
  - backend/app/routers/login.py     (V6 — bloquear 6 endpoints OTP/login profissional) ★ P1#2
  - backend/app/routers/demo.py      (V4 — NOVO — /demo/login + /demo/info)
  - backend/app/routers/config_publico.py (V5 — NOVO — /config/public com Cache-Control)
  - backend/app/domain/pdf_prescricao.py (V7 — is_demo runtime; marca d'água diagonal)
  - backend/seed_demo.py             (V8 — NOVO — 3 personas com IDs novos)
  - backend/scripts/reset_demo_db.py (V9 — NOVO — drop+recreate+seed)

TOCAR (frontend — 6 arquivos):
  - index.html         (banner+seletor; boot script no <head> para evitar flash)
  - prescritor.html, dispensador.html, cidadao.html (banner permanente + sessionStorage)
  - clinica.html       (banner + redirect para index quando demo_mode=true) ★ P2#7
  - validar.html       (selo "PRESCRIÇÃO DEMO" quando aplicável) ★ P2#7

TOCAR (testes):
  - backend/tests/test_demo_mode.py        (10 cenários §5.1-§5.10)
  - backend/tests/test_config_guards.py   (extender com _validate_demo_mode_at_boot — função pura, P3#9)

NÃO TOCAR (anti-escopo §7):
  - Cron real no servidor (entra na Etapa 7/8 — Dockerfile/deploy)
  - Tabela carteiras_digitais formal (Dívida B-Carteira #36)
  - Validator de CPF nos schemas (#44)
  - Refresh token em demo (KISS §3.7.1 — sem; abrir **#60** se UX provar dolorosa — renumerado de #57 em 2026-05-25, colisão com GFI de Pydantic Response Models)
  - Múltiplas personas por papel
  - Cluster catálogo #39, /health/db #40, etc.

PADRÃO P1#1 OBRIGATÓRIO — helper compartilhado em database.py
─────────────────────────────────────────────────────────────
Criar _resolve_sqlite_db_path() ANTES da resolução de DATABASE_URL (linha ~13).
Usar nos DOIS pontos: bloco linha 21-23 (engine) E função get_conn() linha 227.
Se você só rotear o engine, get_conn() continua importando DB_PATH direto e
demo escreve no DB de produção. Ver §4.3 para código completo.

PADRÃO P1#2 OBRIGATÓRIO — 8 endpoints corretos
──────────────────────────────────────────────
NÃO INVENTAR endpoints. Inventário real:
  login.py:78,129,154,167,307,354 + auth.py:42,84
Bloqueio inline em cada um (KISS — 8 endpoints, 2 arquivos, sem dependency).
Mensagem padrão: codigo="demo_mode_ativo".

PADRÃO P1#3 OBRIGATÓRIO — instance_id demo
──────────────────────────────────────────
NÃO criar PICSAUDE_DEMO_INSTANCE_ID nova. Reusar:
  PICSAUDE_INSTANCE_ID=<UUID v4 fixo>           ← instance.py:253 já respeita
  PICSAUDE_INSTANCE_ID_PATH=data/.instance_id.demo ← instance.py:97 já respeita
Documentar no .env.example (criar/atualizar) e em config.py como comentário.

CONVENÇÕES (§3.5 do 5C reaproveitadas)
──────────────────────────────────────
- Chaves do payload de erro em português: codigo + mensagem.
- Status code: 403 para rejeição em demo; 200 para sucesso GET; 201 para POST.
- role="paciente" (NÃO "cidadao") — P2#4.
- /config/public retorna Cache-Control: no-store — P3#10.
- /demo/login NÃO emite refresh token (KISS §3.7.1) — P2#5.
- Marca d'água: is_demo = PICSAUDE_DEMO_MODE runtime (KISS) — P2#6.
- Banner UI: boot script no <head> ou início do <body> para evitar flash.
- Seeds: identificadores NOVOS, diferentes de seed_dev.py — P3#8.

TESTES OBRIGATÓRIOS (§5 — 10 cenários)
──────────────────────────────────────
§5.1  boot com flag carrega /demo/* (sem flag → 404)
§5.2  /demo/login emite JWT com sub canônico por role (3 personas)
§5.3  8 endpoints OTP/login bloqueados com codigo="demo_mode_ativo"
§5.4  /config/public retorna estado E Cache-Control: no-store
§5.5  admin fora do demo público
§5.5b admin dentro de DEMO_ADMIN=true
§5.6  isolamento DB: get_conn() abre DB demo, não prod ★ P1#1
§5.7  PDF tem marca d'água "DEMO" parseável
§5.8  banner UI aparece em demo (integração frontend)
§5.9  eventos de ledger têm instance_id demo
§5.10 _validate_demo_mode_at_boot(prod, true) raise; demais OK

Testes que alternam PICSAUDE_DEMO_MODE no mesmo processo precisam SUBPROCESS
ou importlib.reload de app.database + app.config (§5.6, P3#9).

VERIFICAÇÃO PRÉ-IMPLEMENTAÇÃO
─────────────────────────────
  grep -rn "PICSAUDE_DEMO_MODE\|demo_mode" backend/app/ 2>&1 | head
  → zero matches (campo novo)

  grep -nE "@router\.(post|get)" backend/app/routers/login.py
  → confirmar linhas 78,129,154,167,307,354

VERIFICAÇÃO PÓS-IMPLEMENTAÇÃO
─────────────────────────────
  ls -la backend/app/routers/demo.py backend/app/routers/config_publico.py
  → ambos existem

  grep -n "demo_mode_ativo" backend/app/routers/auth.py backend/app/routers/login.py | wc -l
  → 8

  grep -n "_resolve_sqlite_db_path" backend/app/database.py | wc -l
  → 3 (declaração + 2 usos)

  cd backend && pytest tests/test_demo_mode.py -v
  → 10/10 verdes

  pytest -q
  → sem regressão (27 falhas pré-existentes inalteradas)

COMMITS ESPERADOS
─────────────────
Pode ser um único commit (preferido) ou dois (backend + frontend).
Sugestão de mensagem única:

  feat(6): demo mode com sessões pré-semeadas + isolamento DB + 7 decisões

  TICKET-6 fechado após CODEX rodada 1 (3 P1 + 4 P2 + 3 P3, taxa 10/10).
  Resolve bloqueador de deploy da Etapa 8 (frontend público sem
  expor login real nem dados reais).

  Backend:
  - config.py: PICSAUDE_DEMO_MODE + DEMO_ADMIN + DEMO_DB
  - main.py: guardrail _validate_demo_mode_at_boot (5D pattern)
  - database.py: helper _resolve_sqlite_db_path compartilhado
                 (engine + get_conn — fix P1#1)
  - auth.py + login.py: bloqueio de 8 endpoints OTP/login real
  - demo.py: POST /demo/login (access-only KISS), GET /demo/info
  - config_publico.py: GET /config/public com Cache-Control: no-store
  - pdf_prescricao.py: marca d'água "DEMO" runtime
  - seed_demo.py: 3 personas com IDs novos (980001112223334,
                  99999999000191, 12345678909)
  - scripts/reset_demo_db.py: cron horário (setup na Etapa 8)

  Frontend:
  - index/prescritor/dispensador/cidadao.html: banner+seletor
  - clinica.html: banner+redirect (P2#7)
  - validar.html: selo "DEMO" (P2#7)

  10 testes em tests/test_demo_mode.py + extensão de test_config_guards.

  Refs: backend/docs/tickets/TICKET-6-DEMO-MODE.md
        CLAUDE.md §3, §4 (backend é fonte de verdade; proteção estrutural)

PREDECESSORAS
─────────────
HEAD atual do main: 2bf5e7d (Etapa 5 fechada).
Confirmar com `git log -1 --oneline`. Se não bater, `git pull --rebase origin main`.

NÃO ESQUEÇA
───────────
- Ticket é a fonte de verdade. Em dúvida: relea §3 + §4 + §10.
- chaves codigo+mensagem em português (não code+message).
- role="paciente" (não "cidadao") — checar PERFIS_VALIDOS em domain/roles.py.
- Sem refresh em demo (§3.7.1) — /demo/login retorna SÓ access_token.
- Testes com alternância de flag precisam subprocess/importlib.reload (§5.6/§5.10).
- /config/public DEVE ter Cache-Control: no-store (§4.5 + §5.4).
- Helper _resolve_sqlite_db_path REUSADO em get_conn() (§4.3 — sem isso vaza prod).
- Documentar PICSAUDE_INSTANCE_ID + PATH no .env.example/.env.demo.example.
- Reporte separadamente as falhas pré-existentes após pytest -q.
- NÃO criar PICSAUDE_DEMO_INSTANCE_ID nova — reusar instance.py existente.
- NÃO emitir refresh em demo.
- NÃO inventar endpoints — usar os 8 reais mapeados em §3.7.
````


---

> **Status do ticket (2026-05-24 — pronto para Code):**
> Rodada 0 (Arquiteto) ✅ — 7 decisões fechadas com Fabiano
> CODEX rodada 1 (revisão da spec) ✅ — 3 P1 + 4 P2 + 3 P3 integrados em §10 (taxa 10/10)
> Fabiano: aprovado ✅ (Caminho "já vai para Code", sem rodada 1.5)
> §12 (prompt operacional ao Code) ✅
> Code — aguarda implementação
> CODEX rodada 2 (pós-implementação) — pendente
