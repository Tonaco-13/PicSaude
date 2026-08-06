# ADENDO-SEED-EXAMES-PERSONA-CLINICA — Persona clínica no `/demo/login` (lacuna da spec original)

| Campo | Valor |
|---|---|
| **ID** | ADENDO-SEED-EXAMES-PERSONA-CLINICA |
| **Classe** | `module` (estende `TICKET-SEED-EXAMES-DEMO`) |
| **Estado** | 🟢 **SPEC PRONTA** — lacuna detectada pelo Engenheiro na implementação |
| **Origem** | Devolutiva do Engenheiro (2026-08-02): "critério 5 (persona clínica no /demo/login)" |
| **Adendo a** | `docs/tickets/TICKET-SEED-EXAMES-DEMO.md` |

---

## §1 A lacuna (erro da spec original)

O `TICKET-SEED-EXAMES-DEMO.md` §2 mandava criar `_garantir_usuario` + `_garantir_prestador` da clínica no `seed_demo.py`. **Mas isso só cria o login na tabela `usuarios`** — não registra a persona no fluxo `/demo/login`.

Verificado em 2026-08-02:
- `demo.py:76` `_papeis_demo_disponiveis()` retorna `["prescritor", "dispensador", "dispensador_norte", "paciente"]` — **sem clínica**.
- `demo.py:38` `_PERSONAS` tem prescritor/dispensador/dispensador_norte/paciente/admin — **sem persona de clínica**.
- `index.html:367` `ROLE_BY_HREF` mapeia prescritor/dispensador/cidadao — **sem `clinica.html`**.

**Consequência:** mesmo após o seed, a clínica **continua inacessível pela demo** — o seletor de 1 clique não a auto-loga, e não há JWT demo obtível sem CNPJ/senha reais. O Gap 2 (sem persona demo de laboratório) **não foi fechado**.

> **Admissão do arquiteto:** esta lacuna é minha. O ticket-fonte cobria o "quem a clínica é" (tabela) mas não cobria o "como a clínica entra na demo" (fluxo de login). O Engenheiro detectou na implementação — bom achado.

---

## §2 Spec — o que adicionar

### 2.1 Backend — `_PERSONAS` e `_papeis_demo_disponiveis` em `demo.py`

Adicionar a persona clínica em `_PERSONAS` (depois de `dispensador_norte`):

```python
# Q1=(a) ratificada — clínica/laboratório da demo: mesma role `dispensador`
# (compartilhada), com CNPJ próprio (separação por estabelecimento).
# Espelha o padrão do `dispensador_norte` (segunda farmácia): mesmo papel,
# muda só o CNPJ/estabelecimento. A role `prestador_exame` é ticket `core`
# agendado (TICKET-CORE-ROLE-PRESTADOR-EXAME); quando entrar, esta persona
# migra pra ela.
"clinica": {
    "role":  "dispensador",
    "sub":   "11222333000181",   # CNPJ da CLINICA (seed_demo.py)
    "nome":  "Clínica Demo",
    "identificador_visivel": "CNPJ 11.222.333/0001-81",
},
```

Adicionar `"clinica"` em `_papeis_demo_disponiveis()`:

```python
def _papeis_demo_disponiveis() -> list[str]:
    base = ["prescritor", "dispensador", "dispensador_norte", "clinica", "paciente"]
    if PICSAUDE_DEMO_ADMIN:
        base.append("admin")
    return base
```

> **Notas:**
> - A chave do dict é `"clinica"` (o que vem no `payload.role` do `POST /demo/login`), mas o `role` interno do JWT é `"dispensador"` (Q1=(a)). Exatamente o padrão do `dispensador_norte`.
> - `sub` é o CNPJ `11222333000181` — bate com a constante `CLINICA` em `seed_demo.py:89`. **Confirmar** que este CNPJ é o que o `_garantir_usuario` grava na tabela `usuarios` (deve ser, pois ambos vêm da mesma constante).

### 2.2 Frontend — `ROLE_BY_HREF` em `index.html`

Adicionar `'clinica.html': 'clinica'` ao mapeamento:

```js
const ROLE_BY_HREF = {
    'prescritor.html':  'prescritor',
    'dispensador.html': 'dispensador',
    'cidadao.html':     'paciente',
    'clinica.html':     'clinica',    // ADENDO — persona clínica no /demo/login
};
```

Isto faz o seletor de 1 clique atribuir `data-demo-role="clinica"` ao card da clínica, e o portal chamar `POST /demo/login {role: 'clinica'}` no clique.

### 2.3 Frontend — `clinica.html` (verificar gate de role)

O `clinica.html:881` hoje só aceita `data.role === 'dispensador' || 'admin'`. **A persona clínica tem `role: 'dispensador'`** (Q1=(a)), então o gate **já passa** — não precisa mudar.

> Confirmar: a resposta do `/demo/login` para `role: 'clinica'` traz `data.role === 'dispensador'` (porque `_PERSONAS["clinica"]["role"] = "dispensador"`). Se o frontend checa `data.role`, passa. Se checa `payload.role` original, precisa ajustar — mas o padrão do código é checar `data.role` (o do JWT).

---

## §3 Quem implementa o quê

| Mudança | Arquivo | Quem | Classe |
|---|---|---|---|
| `_PERSONAS["clinica"]` | `backend/app/routers/demo.py` | **Engenheiro** (backend) | `module` |
| `"clinica"` em `_papeis_demo_disponiveis` | `backend/app/routers/demo.py` | **Engenheiro** | `module` |
| `ROLE_BY_HREF` com `clinica.html` | `index.html` | **Kimi 3** (frontend) | `local-extension` |
| Gate de role em `clinica.html` | `clinica.html` | **Kimi 3** (verificar, provável não-mudança) | `local-extension` |

> **Decisão:** o Engenheiro pode tocar `demo.py` no mesmo PR do seed (é o mesmo escopo — persona clínica da demo) **OU** abrir PR separado. Recomendo **mesmo PR** (a persona sem o seed é órfã; o seed sem a persona é inacessível).

---

## §4 Critérios de aceite (adicionais ao ticket-fonte)

1. `POST /demo/login {"role": "clinica"}` retorna JWT com `role: "dispensador"`, `sub: "11222333000181"`, `nome: "Clínica Demo"`.
2. `_papeis_demo_disponiveis()` inclui `"clinica"`.
3. `GET /config/public` expõe `"clinica"` em `demo_roles`.
4. Clicar no card "Clínica / Laboratório" no portal (`index.html`) chama `POST /demo/login {role: 'clinica'}` e redireciona pra `clinica.html` autenticado.
5. `clinica.html` abre sem tela de senha (o gate de role passa — `data.role === 'dispensador'`).
6. A clínica logada consegue buscar `DEMO-EXAME-0001` por protocolo.

---

## §5 Browser-E2E

Adicionar ao `test_demo_sem_login.py` (Kimi 3) ou teste análogo:

```python
def test_clinica_autologin_pelo_portal(browser_demo):
    """Card da clínica no portal auto-loga e abre clinica.html sem senha."""
    # Navegar pro portal
    # Clicar no card "Clínica / Laboratório"
    # Assert: redirecionou pra clinica.html
    # Assert: não há tela de login visível
    # Assert: clínica consegue buscar DEMO-EXAME-0001
```

---

## §6 Não fazer

- Não introduzir role `prestador_exame` aqui (é `core`, ticket agendado).
- Não mudar o gate de `clinica.html:881` se já passar com `role: 'dispensador'`.
- Não criar endpoint novo.

---

## §7 Rastreabilidade

| Artefato | Caminho |
|---|---|
| Ticket-fonte (a adendar) | `docs/tickets/TICKET-SEED-EXAMES-DEMO.md` |
| Devolutiva do Engenheiro (origem) | 2026-08-02 |
| Código `_PERSONAS` | `backend/app/routers/demo.py:38-74` |
| Código `_papeis_demo_disponiveis` | `backend/app/routers/demo.py:76-80` |
| Código `ROLE_BY_HREF` | `index.html:367-371` |
| Constante `CLINICA` | `backend/seed_demo.py:88-91` |

---

*Adendo emitido pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Reconhece lacuna da spec original detectada pelo Engenheiro. Estende o escopo do seed pra cobrir a ponta do `/demo/login`.*
