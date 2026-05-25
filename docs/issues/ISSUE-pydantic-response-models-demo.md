# Criar Pydantic Response Models para `/demo/login`, `/demo/info` e `/config/public`

> **Origem:** Jules — revisão de fim da Etapa 6 (2026-05-24), achado P2#2 (Type).
> **Boa primeira contribuição:** ⭐⭐⭐ (Backend Python / FastAPI / Pydantic)
> **Dificuldade:** baixa — 3 classes Pydantic + 1 linha em cada decorator.
> **Estimativa:** 2-3 horas (inclui aprender Pydantic se for a primeira vez).

---

## Contexto

A Etapa 6 introduziu 3 endpoints novos no PicSaúde:

- `POST /demo/login` — retorna `{access_token, role, nome, sub}`
- `GET /demo/info` — retorna `{personas: [...], proximo_reset, ultimo_reset}`
- `GET /config/public` — retorna `{version, demo_mode, demo_admin, demo_roles, proximo_reset, instance_id}`

Esses 3 endpoints retornam **dicionário Python genérico** (`-> dict`). Isso significa que:

1. O **Swagger / OpenAPI** (gerado automaticamente em `/docs`) **não mostra o schema** da resposta — só "object", sem detalhar campos.
2. Um desenvolvedor frontend ou cliente externo que consome a API **não tem contrato** — precisa testar e adivinhar a estrutura.
3. Mudanças acidentais no shape da resposta **não são pegas por testes**.

A solução padrão FastAPI é criar **Pydantic Response Models** e declarar `response_model=...` no decorator.

## O que fazer

### 1. Em `backend/app/routers/demo.py`

Criar duas classes Pydantic (perto do topo do arquivo, depois dos imports):

```python
from pydantic import BaseModel
from typing import List, Optional

class DemoLoginOut(BaseModel):
    access_token: str
    role: str
    nome: str
    sub: str

class DemoPersona(BaseModel):
    role: str
    nome: str
    sub: str
    identificador_visivel: str

class DemoInfoOut(BaseModel):
    personas: List[DemoPersona]
    proximo_reset: str
    ultimo_reset: Optional[str] = None
```

E nos decorators, adicionar `response_model`:

```python
@router.post("/login", status_code=200, response_model=DemoLoginOut, summary="...")
def demo_login(payload: DemoLoginIn) -> DemoLoginOut:
    ...

@router.get("/info", response_model=DemoInfoOut, summary="...")
def demo_info() -> DemoInfoOut:
    ...
```

### 2. Em `backend/app/routers/config_publico.py`

```python
from pydantic import BaseModel
from typing import List, Optional

class ConfigPublicOut(BaseModel):
    version: str
    demo_mode: bool
    demo_admin: bool
    demo_roles: List[str]
    proximo_reset: Optional[str] = None
    instance_id: Optional[str] = None  # sempre None — não vazamos instance real

@router.get("/public", response_model=ConfigPublicOut, summary="...")
def get_config_publico(response: Response) -> ConfigPublicOut:
    response.headers["Cache-Control"] = "no-store"
    ...
```

### 3. Confirmar Swagger

- Rodar `uvicorn backend.app.main:app --reload`
- Abrir `http://127.0.0.1:8000/docs`
- Conferir que `/demo/login`, `/demo/info`, `/config/public` agora mostram schema completo de resposta (com campos e tipos).

## Cuidados

- Manter o `Cache-Control: no-store` em `/config/public` — é P3#10 do TICKET-6, não pode quebrar.
- O `sub` do `/demo/login` é CNS (prescritor), CNPJ (dispensador) ou CPF (paciente). Tipo continua `str` (não há razão para tipos específicos por role nesta passagem — pode ser refator futuro).
- Tests existentes em `backend/tests/test_demo_mode.py` devem continuar passando. Rodar `pytest tests/test_demo_mode.py -v` antes e depois para confirmar.

## Critério de aceite

- 1 commit, mensagem `feat(api): adicionar Pydantic Response Models p/ endpoints demo + config/public`
- `pytest tests/test_demo_mode.py tests/test_config_guards.py -v` → mesmo número de verdes (sem regressão)
- Swagger em `/docs` mostra schemas completos nos 3 endpoints
- Endpoints continuam retornando JSON estruturalmente idêntico (nada quebra clientes existentes)

## Onde pedir ajuda

- Pydantic básico: https://docs.pydantic.dev/latest/concepts/models/
- FastAPI response_model: https://fastapi.tiangolo.com/tutorial/response-model/
- Dúvida no canal da extensão antes de quebrar coisa que não dá pra ver.
