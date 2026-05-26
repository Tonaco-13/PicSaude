# Centralizar helpers de seed em `backend/seed_common.py`

> **Origem:** Jules — revisão de fim da Etapa 6 (2026-05-24), achado P2#3 (Duplicação).
> **Boa primeira contribuição:** ⭐⭐⭐ (Backend Python / refactoring básico)
> **Dificuldade:** baixa — extrair funções já prontas para arquivo novo.
> **Estimativa:** 2-3 horas (inclui testes manuais nos dois seeds).

---

## Contexto

O PicSaúde tem dois scripts de seed para popular o banco de dados com dados de teste/demo:

- `backend/seed_dev.py` — seeds para ambiente de desenvolvimento (1 prescritor, 1 farmácia, 1 hospital, 1 USF).
- `backend/seed_demo.py` — seeds para o modo demo público (3 personas canônicas: Dra. Demo Maria, Farmácia Demo Central, João Demo da Silva).

Os dois arquivos compartilham helpers quase idênticos:

| Helper | seed_dev.py | seed_demo.py |
|---|---|---|
| `_garantir_usuario(conn, identificador, nome, role)` | ~linha 95-118 | ~linha 95-118 (idêntico) |
| `_garantir_prescritor(conn, cns, nome)` | ~linha 125-141 | ~linha 125-141 (idêntico) |
| `_garantir_prestador(conn, org_id, nome, ...)` | ~linha 148-195 | ~linha 148-195 (quase idêntico) |
| `_agora()` | ~linha 87 | ~linha 87 (idêntico) |

Se a gente precisar mudar como `usuarios` é populado (ex: adicionar campo novo), hoje precisa editar 2 arquivos. Risco real de divergência silenciosa.

## O que fazer

### 1. Criar `backend/seed_common.py`

Mover os 4 helpers para esse arquivo novo. Manter assinaturas idênticas (não refatorar API).

```python
# backend/seed_common.py
"""
Helpers compartilhados entre seed_dev.py e seed_demo.py.

Manter este arquivo focado em INSERTs idempotentes (UPSERTs / get-or-create).
Não incluir lógica específica de personas — isso fica em cada seed.
"""
from datetime import datetime, timezone
import uuid

from app.auth.jwt import hash_senha


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def garantir_usuario(conn, identificador: str, nome: str, role: str, senha: str) -> None:
    """Cria usuário se não existir; atualiza senha se já existir."""
    # ... mover de seed_dev.py linha 95-118
    pass


def garantir_prescritor(conn, cns: str, nome: str) -> None:
    """Cria registro em `prescritores` se não existir."""
    # ... mover de seed_dev.py linha 125-141
    pass


def garantir_prestador(conn, org_id: str, nome: str, tipo: str, cnpj: str,
                       unidade_id: str, unidade_nome: str, unidade_tipo: str) -> None:
    """Cria registro em `prestadores` + `unidades` se não existir."""
    # ... mover de seed_dev.py linha 148-195
    pass
```

Note que removi o underscore inicial (eram `_garantir_*` privados; agora são públicos do módulo `seed_common`).

### 2. Editar `backend/seed_dev.py`

Substituir as definições locais por imports:

```python
# No topo, junto dos outros imports:
from seed_common import garantir_usuario, garantir_prescritor, garantir_prestador, _agora

# Remover as definições de _garantir_usuario, _garantir_prescritor, _garantir_prestador, _agora
# (linhas ~87-195)

# No main(), trocar chamadas:
# ANTES: _garantir_usuario(conn, ..., SENHA_TESTE)
# DEPOIS: garantir_usuario(conn, ..., SENHA_TESTE)  (mesmo nome sem underscore)
```

### 3. Editar `backend/seed_demo.py`

Mesmo padrão do seed_dev.

### 4. Verificar que seeds continuam funcionando

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev/backend

# seed_dev (modo dev)
PICSAUDE_ENV=dev python3 seed_dev.py
# Esperado: mesma saída de antes ("usuario X criado/atualizado", etc.)

# seed_demo (modo demo)
PICSAUDE_ENV=dev PICSAUDE_DEMO_MODE=true python3 seed_demo.py
# Esperado: mesma saída de antes (3 personas demo criadas/atualizadas)
```

## Cuidados

- `seed_demo.py` tem helper específico `_garantir_paciente` (linha 148+) que **não existe** no seed_dev. **Não mover** — fica em `seed_demo.py` mesmo. Só os 4 listados acima são compartilhados.
- Manter `_agora()` no `seed_common.py` (é trivial mas evita import circular se virar útil em outros lugares).
- **Não tocar** em `seed_demo.py:39-56` (constantes das personas: CNS, CNPJ, CPF, nomes). São dados, não helpers.
- Tests existentes (`pytest -q`) devem continuar verdes.

## Como rodar em diferentes sistemas

Os exemplos com `PICSAUDE_DEMO_MODE=true uvicorn ...` (ou `PICSAUDE_DEMO_MODE=true python3 seed_demo.py`) assumem bash (Linux/macOS/WSL). Em Windows nativo, use uma das variantes abaixo:

**PowerShell (Windows):**
```powershell
$env:PICSAUDE_DEMO_MODE="true"
uvicorn app.main:app --reload
```

**CMD (Windows):**
```cmd
set PICSAUDE_DEMO_MODE=true
uvicorn app.main:app --reload
```

**Bash (Linux / macOS / WSL):**
```bash
PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload
```

Para desligar o modo demo, feche o terminal ou faça `unset PICSAUDE_DEMO_MODE` (bash) / `Remove-Item Env:PICSAUDE_DEMO_MODE` (PowerShell) / `set PICSAUDE_DEMO_MODE=` (CMD).

## Critério de aceite

- 1 commit, mensagem `refactor(seed): extrair helpers compartilhados para seed_common.py`
- Diff: arquivo novo `seed_common.py` + diff -100/+5 em `seed_dev.py` + diff -100/+5 em `seed_demo.py`
- `pytest -q` sem regressão (mesmo número de falhas pré-existentes)
- Teste manual: `seed_dev.py` e `seed_demo.py` rodam com mesma saída visual de antes.

## Onde pedir ajuda

- Imports relativos vs absolutos em Python: dúvida comum, peça no canal antes de quebrar.
- Padrão de seed: ler `backend/seed_dev.py` inteiro antes de começar — é o exemplo canônico.
- Modo demo em geral: `backend/docs/tickets/TICKET-6-DEMO-MODE.md`.
