# DESPACHO KIMI3-005 — Persona clínica no portal (`index.html`)

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-005 (frontend do ADENDO-SEED-EXAMES-PERSONA-CLINICA) |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Kimi 3 (implementa) · cc: Revisor · Fabiano |
| **Data** | 2026-08-02 |
| **Origem** | `docs/tickets/ADENDO-SEED-EXAMES-PERSONA-CLINICA.md` §3.2 (lacuna detectada pelo Engenheiro) |
| **Classe** | `local-extension` (frontend puro) |

---

## §1 O que fazer

Adicionar `'clinica.html': 'clinica'` ao mapeamento `ROLE_BY_HREF` em `index.html`, para que o card "Clínica / Laboratório" no portal faça auto-login demo (1 clique, sem senha).

**Arquivo:** `index.html`, função `picsaudeDemoBoot` (~linha 367).

**Mudança:**
```js
// Antes
const ROLE_BY_HREF = {
    'prescritor.html':  'prescritor',
    'dispensador.html': 'dispensador',
    'cidadao.html':     'paciente',
};

// Depois
const ROLE_BY_HREF = {
    'prescritor.html':  'prescritor',
    'dispensador.html': 'dispensador',
    'cidadao.html':     'paciente',
    'clinica.html':     'clinica',    // ADENDO — persona clínica no /demo/login
};
```

Com isto, o seletor de personas passa a atribuir `data-demo-role="clinica"` ao card da clínica e, no clique, chama `POST /demo/login {role: 'clinica'}` antes de redirecionar pra `clinica.html`.

## §2 Verificar `clinica.html:881` (provável não-mudança)

O gate de role em `clinica.html:881` hoje aceita `data.role === 'dispensador' || 'admin'`. A persona clínica traz `role: 'dispensador'` (Q1=(a)) — então o gate **já passa**.

**Ação:** confirmar lendo o trecho. Se já passa (esperado), **não mudar nada**. Se por acaso checar outro campo, ajustar — mas não é o esperado.

## §3 Dependência

Este trabalho **depende do backend do adendo** (Engenheiro, `demo.py`):
- `_PERSONAS["clinica"]` e `"clinica"` em `_papeis_demo_disponiveis()` — PR do seed (`module/seed-exames-demo`).

**Sem o backend, o `POST /demo/login {role: 'clinica'}` devolve 403 `papel_demo_indisponivel`.** Então: implemente o frontend, mas o PR só faz sentido depois do seed mergear (ou junto — coordene com o Engenheiro).

## §4 Critérios de aceite

1. Card "Clínica / Laboratório" no portal ganha `data-demo-role="clinica"`.
2. Clicar nele chama `POST /demo/login {role: 'clinica'}` e redireciona pra `clinica.html` autenticado (após o backend do adendo).
3. `clinica.html` abre sem tela de senha (gate passa com `role: 'dispensador'`).
4. Sem erro de console.
5. Não quebra os outros 3 cards (prescritor/dispensador/cidadao continuam funcionando).

## §5 Browser-E2E (opcional, no `test_demo_sem_login.py`)

```python
def test_clinica_autologin_pelo_portal(browser_demo):
    """Card da clínica no portal auto-loga e abre clinica.html sem senha."""
    # (depende do backend do adendo)
```

## §6 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add <arquivo-específico>`, nunca `git add .` / `-A`.
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar comigo.

## §7 Fluxo

1. Implemente (`index.html` + confirmar `clinica.html:881`).
2. Branch: `local-extension/persona-clinica-portal` (ou adicione commit a uma branch existente se fizer sentido — mas não à do seed, que é do Engenheiro).
3. PR após o backend do adendo mergear (ou coordinate pra irem casados).
4. Revisor audita.
5. Eu ratifico. Fabiano martela.

---

*Despacho emitido pelo arquiteto de backend. Escopo mínimo (1 linha no `ROLE_BY_HREF` + confirmação). Dependente do backend do adendo.*
