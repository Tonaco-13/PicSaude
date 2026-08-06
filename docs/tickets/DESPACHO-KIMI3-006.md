# DESPACHO KIMI3-006 — Painel "Chaves de acesso" no portal (substitui o banner amarelo)

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-006 (frontend puro, Parte B do plano do arquiteto) |
| **De** | Arquiteto (Z) |
| **Para** | Kimi 3 (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-06 |
| **Origem** | Plano do arquiteto §Parte B, ratificado após revisão do conselheiro (2026-08-06) |
| **Classe** | `local-extension` (frontend/UI — não altera semântica clínica) |
| **Pré-requisito** | `main` atual (pós-merge #130–134). Sem dependência de backend novo. |

---

## §1 Contexto — por que este ticket existe

O portal (`index.html`) hoje exibe, em modo demo, um **banner amarelo intrusivo** no topo
(`.demo-banner`: *"MODO DEMO — dados fictícios, nenhuma prescrição é real."*). O Fabiano
relatou que o aviso está **confuso**: ocupa o topo de todas as telas, não comunica *o que fazer*
nem mostra as chaves que conectam os módulos.

A observação do Fabiano, literal: *"Deixar assim: as chaves de cada módulo: 1 CNS prescritor;
1 CPF cidadão; 1 CNPJ dispensador; 1 CNPJ clínica/laboratório."*

**Decisão de produto (ratificada pelo conselheiro):** remover o banner amarelo do portal e, no
 lugar, renderizar um **painel discreto "Chaves de acesso (demo)"** listando as 4 identidades
 canônicas, com botão *copiar* cada. O aviso "dados fictícios" **não some** — migra para dentro
 do painel, mais discreto.

> **Nota de processo (lição registrada na sessão 2026-08-06):** este ticket é o *sobrevivente*
> de um plano maior. A Parte A (auto-login da clínica + persona demo) foi **cancelada** — já
> estava mergeada (#130–132) e no ar; o arquiteto a enxergou como gap por diagnosticar contra
> um checkout defasado. Regra permanente: *antes de diagnosticar estado do sistema, `git pull
> --ff-only` + `gh pr list`*. Aqui só a Parte B vira trabalho real.

---

## §2 O que fazer

### 2.1 `config.js` — adicionar `DEMO.prescritor` (fonte única)

Hoje o objeto `DEMO` (linhas 48–52) tem `cidadao`, `farmacia`, `clinica` — **não tem
`prescritor`**. O CNS da Dra. Demo vive apenas em `demo.py` e `seed_demo.py`. Adicionar:

```js
const DEMO = {
    prescritor: { cns: '980001112223334', nome: 'Dra. Demo Maria Souza' },   // NOVO
    cidadao:  { cpf:  '12345678909',    nome: 'João Demo da Silva' },
    farmacia: { cnpj: '99999999000191', nome: 'Farmácia Demo Central' },
    clinica:  { cnpj: '11222333000181', nome: 'Clínica Demo' },
};
```

**Concordância obrigatória** (régua do projeto — `test_guardrail_identidades_demo.py`):
o CNS `980001112223334` deve ser **idêntico** ao de `seed_demo.py::PRESCRITOR["cns"]` e ao
`sub` da persona `prescritor` em `demo.py`. Confirmar lendo os três antes de commitar.

### 2.2 `index.html` — remover banner amarelo, renderizar painel de chaves

No `picsaudeDemoBoot` (linhas ~348–413, dentro do bloco `if (!cfg.demo_mode) return;`):

1. **REMOVER** a injeção do `.demo-banner` (linhas ~354–364). O CSS `.demo-banner`
   (`#demo-mode-styles`, linhas ~327–346) pode ficar — não incomoda — ou ser limpo; fica a
   critério do Kimi, desde que nenhum banner apareça no topo.

2. **MANTER** intacta a interceptação dos cards (`ROLE_BY_HREF` + `POST /demo/login` +
   `sessionStorage`) e o auto-click `?demo_role=`.

3. **ADICIONAR** a renderização de um painel "Chaves de acesso (demo)", **apenas quando
   `cfg.demo_mode`**, posicionado abaixo dos cards de perfil (dentro do `<main>`). Conteúdo:

| Módulo | Chave | Valor (de `DEMO.*`, formatado) |
|---|---|---|
| 🩺 Prescritor | CNS | `formatarCNS(DEMO.prescritor.cns)` → `980.0011.1222.3334` |
| 👤 Cidadão | CPF | `formatarCPF(DEMO.cidadao.cpf)` → `123.456.789-09` |
| 💊 Dispensador | CNPJ | `formatarCNPJ(DEMO.farmacia.cnpj)` → `99.999.999/0001-91` |
| 🏥 Clínica/Laboratório | CNPJ | `formatarCNPJ(DEMO.clinica.cnpj)` → `11.222.333/0001-81` |

Cada linha com botão **📋 Copiar** → `navigator.clipboard.writeText(valorSemMascara)` +
`showToast('Chave copiada', 'success')` (toast já existe em `config.js`).

**Dentro do painel, linha discreta (não-banner):**
> *Demo — dados fictícios, nenhuma prescrição é real. Clique num perfil acima para entrar.*

Estilo: discreto, card branco com borda sutil (não amarelo, não topo-fixo). Espelhar a estética
do `.status-block` já existente no `index.html`.

### 2.3 `formatarCNS` — helper novo (não existe em `config.js`)

O `config.js` tem `formatarCPF` e `formatarCNPJ`, **mas não `formatarCNS`**. Adicionar um helper
ao lado dos outros (mesmo bloco, linhas ~66–78):

```js
/** Formata CNS (15 dígitos) como 980.0011.1222.3334. Aceita string com ou sem máscara. */
function formatarCNS(valor) {
    const d = String(valor || '').replace(/\D/g, '').slice(0, 15);
    if (d.length === 15) return `${d.slice(0,3)}.${d.slice(3,7)}.${d.slice(7,11)}.${d.slice(11,15)}`;
    return d;
}
```

(Formato alinhado ao `identificador_visivel` da persona prescritor em `demo.py:44`:
`"CNS 980 0011 1222 3334"` — usar pontos para consistência visual com CPF/CNPJ.)

---

## §3 Invariantes (não-negociáveis)

- **Fonte única:** nenhuma chave chumbada como literal no HTML. Tudo referencia `DEMO.*` do
  `config.js`. CNS de 15 dígitos não cai no `_CNPJ_RE` do guard-rail (lookbehind/lookahead
  `(?<!\d)\d{14}(?!\d)`), mas ao formatar com pontos a sequência já está quebrada — **dupla
  segurança**.
- **"Dados fictícios" permanece visível:** não remover o aviso de demo; apenas realocá-lo para
  dentro do painel, mais discreto. Esta é a ressalva nº 1 do conselheiro.
- **Fora de demo, o painel some:** o portal continua mostrando login real quando
  `cfg.demo_mode === false`. O painel é condicional ao modo demo.
- **Sem mudança de backend:** este ticket é `index.html` + `config.js` apenas.

---

## §4 Critérios de aceite

1. Banner amarelo `.demo-banner` **não aparece mais** no portal (nem no topo, nem em outro
   lugar como banner).
2. Em modo demo, o painel "Chaves de acesso (demo)" renderiza abaixo dos cards com as **4
   chaves corretas** (CNS prescritor, CPF cidadão, CNPJ dispensador, CNPJ clínica).
3. Cada botão "Copiar" copia o valor **sem máscara** e mostra `showToast` de sucesso.
4. A linha "dados fictícios" aparece **dentro** do painel (discreta).
5. Fora de demo (`demo_mode=false`), o painel **não aparece**.
6. Os 4 cards de perfil continuam funcionando (auto-login ao clicar).
7. `backend/tests/unit/test_guardrail_identidades_demo.py` **passa** (verde) — nenhum literal
   de CPF/CNPJ chumbado.
8. Sem erro de console.

---

## §5 Verificação

```bash
# Guard-rail de identidades (deve continuar verde)
cd backend && python -m pytest tests/unit/test_guardrail_identidades_demo.py -v

# Smoke manual: abrir index.html em demo, confirmar 4 chaves + botões copiar + sem banner
```

Se houver fixture de browser-E2E para o portal, adicionar caso leve:
`test_painel_chaves_demo_aparece_quando_demo_mode` — opcional, não bloqueia.

---

## §6 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add <arquivo-específico>`, nunca `git add .` / `-A`.
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## §7 Fluxo

1. Implemente (`config.js` + `index.html`).
2. Branch: `local-extension/painel-chaves-demo`.
3. Confirme `test_guardrail_identidades_demo.py` verde.
4. PR → Revisor audita → Conselheiro ratifica → Fabiano martela.

---

*Despacho emitido pelo arquiteto. Escopo mínimo (frontend puro, sem backend novo). Origem:
Parte B do plano, ratificada pelo conselheiro em 2026-08-06.*
