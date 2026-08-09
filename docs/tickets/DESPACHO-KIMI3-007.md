# DESPACHO KIMI3-007 — UI da clínica/lab: registrar resultado, relatório de exames, faturamento

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-007 (frontend puro + consumo de novos endpoints do arco V2) |
| **De** | Arquiteto (Z) |
| **Para** | Kimi 3 (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-07 (revalidado 2026-08-09 contra `f361ab8`) |
| **Origem** | `TICKET-MODULO-CLINICA-V2.md` §3/§4/§5/§6 |
| **Classe** | `local-extension` (frontend/UI — não altera semântica clínica do backend) |
| **Pré-requisito (GATE DURO)** | ✅ **SATISFEITO** — ENG-007 (#141), ENG-008 (#142), ENG-009 (#145) **mergeados** em `f361ab8`. Os endpoints `/clinicas/relatorio.*` e `/clinicas/faturamento.*` existem e aceitam `dispensador`. Sem bloqueio — implemente direto. |

---

## §1 Contexto — por que este ticket existe

> **Revalidação 2026-08-09 (`f361ab8`):** o GATE DURO do backend está **satisfeito** — todos os
> endpoints que este despacho consome (`/pedidos-exame/{proto}/itens/{id}/resultado`,
> `/clinicas/relatorio.{csv,pdf}`, `/clinicas/faturamento.{csv,pdf}`) existem e aceitam
> `dispensador`. As âncoras `clinica.html:1452/1454/1477/478` foram confirmadas in-loco. Este é o
> **gate duro real pendente** pra fechar o arco V2 e destravar a demo clínica/lab.

`clinica.html` hoje opera o ciclo de coleta, mas tem **lacunas de UI** marcadas explicitamente como
"próxima fase" via mock-tags (`clinica.html:1452`, `:1454`):

```js
// clinica.html:1451-1455  (main@3162af9)
} else if (item.status_item === 'coletado') {
  acoesHtml = `<span class="laudo-aguardo mock-aviso">Aguardando laudo
    <small class="mock-tag">⚠ Emissão de laudo pela UI: próxima fase</small></span>`;
} else if (['em_analise','resultado_disponivel'].includes(item.status_item)) {
  acoesHtml = `<span class="laudo-aguardo mock-aviso">Laudo em andamento
    <small class="mock-tag">⚠ Emissão de laudo pela UI: próxima fase</small></span>`;
}
```

E não há nenhum link de **relatório** nem **faturamento** em nenhum lugar do módulo. O arco V2 fecha
isto: R1 (registrar resultado), R3 (relatório de exames), R4 (faturamento), R2 (aviso ao paciente
via estado).

> **Sobre R1:** realizar e coletar **já funcionam** para a clínica — `coletar` tem botão
> (`clinica.html:1447`, `registrarColeta` `:1477`) e o endpoint `/agendamentos/{proto}/realizar`
> já aceita `dispensador`. O que falta é o **botão de registrar resultado** (depende do backend
> ENG-007, que estende `require_role` ao `dispensador`).

---

## §2 O que fazer

### 2.1 Botão "Registrar resultado" — substitui o mock-tag `:1452`

Hoje, item `coletado` mostra o mock *"Aguardando laudo — próxima fase"*. Substituir por um botão
que chama `POST /pedidos-exame/{proto}/itens/{id}/resultado` (endpoint `pedidos_exame.py:974`,
após ENG-007 aceitar `dispensador`):

```js
} else if (item.status_item === 'coletado') {
  acoesHtml = `<button class="btn-resultado" id="btn-resultado-${item.id}"
      onclick="registrarResultado(${item.id})">
      Registrar resultado
    </button>`;
} else if (item.status_item === 'em_analise') {
  acoesHtml = `<span class="laudo-aguardo">Em análise — resultado em breve.</span>`;
} else if (item.status_item === 'resultado_disponivel') {
  acoesHtml = `<span class="laudo-pronto">✓ Resultado disponível</span>`;
}
```

Nova função `registrarResultado(itemId)` — espelhar `registrarColeta` (`clinica.html:1477-1504`):
`fetch` com `authHeaders()`, `body: JSON.stringify({resultado_resumo: ...})`, tratar 401/403 via
`handleUnauthorized()`. Coletar o `resultado_resumo` via `prompt()` simples ou um mini-form inline
(não abrir modal complexo — MVP). Após sucesso, `atualizarStatusUI` (`:1506`) + `recarregarPedido`.

### 2.2 Botão "Realizar agendamento" — no card de agendamento `:594-598`

O card `#card-agendamento` (`clinica.html:594-598`) já tem `#feedback-agendamento` e
`#conteudo-agendamento`. Adicionar botão "Confirmar realização" quando o agendamento está
`confirmado`, chamando `POST /agendamentos/{proto}/realizar` (`agendamentos.py:493`). Espelhar o
padrão de fetch já usado para `/agendamentos/{proto}/confirmar` (`clinica.html:~1328`).

### 2.3 Relatório de exames + Faturamento — no header `:468-482`

O `<header class="header">` (`clinica.html:468-482`) hoje tem logo + `← Portal` + tag de módulo +
`#header-sessao` (nome + Sair). Adicionar dois botões em `.header-right` (visíveis só logado, após
`#header-sessao`):

```html
<button type="button" class="btn-rel" onclick="abrirRelatorioExames('csv')">🔬 Relatório (CSV)</button>
<button type="button" class="btn-rel" onclick="abrirRelatorioExames('pdf')">🔬 Relatório (PDF)</button>
<button type="button" class="btn-rel" onclick="abrirFaturamento('csv')">💰 Faturamento (CSV)</button>
```

**Padrão de download** — espelhar `dispensador.html`: função `_baixarBlob` (`dispensador.html:1602`)
e `exportarSngpc` (`dispensador.html:1695`): `fetch(BACKEND + '/clinicas/relatorio.csv?' + qs,
{headers: authHeaders()})` → `resp.blob()` → download. **Nunca** `<a href>` direto (precisa do
`Authorization`). Query params opcionais de período (default = backend traz últimos 30 dias).

Novas funções: `abrirRelatorioExames(fmt)` → `/clinicas/relatorio.{fmt}`;
`abrirFaturamento(fmt)` → `/clinicas/faturamento.{fmt}`.

### 2.4 R2 — Aviso ao paciente (sem backend novo)

R2 é **leitura de estado**, não push. Confirmar que a carteira do cidadão (`cidadao.html`) já
mostra o status `agendado` + data quando consulta `GET /pedidos-exame/{proto}`. Se sim, **nenhum
trabalho nesta UI** — o aviso aparece no lado do cidadão por polling (padrão F5-C2). Se faltar
mostrar `data_agendamento` na resposta, reportar como follow-up (não bloqueia este despacho).

---

## §3 Invariantes (não-negociáveis)

- **Sem chumbado:** valores vêm do backend; nada de protocolos/CNPJ como literais no JS.
- **Auth em todos os fetchs:** sempre `headers: authHeaders()`. Downloads via `fetch`+`blob`,
  **nunca** `<a href>` (vai sem auth e falha).
- **401/403 → `handleUnauthorized()`:** todo fetch novo trata como `registrarColeta:1488`.
- **Sem estado no cliente:** após registrar resultado, **recarregar do backend**
  (`recarregarPedido`, `:1538`); não deduzir status localmente.
- **Mock-tags removidos:** `clinica.html:1452` e `:1454` não podem sobreviver — são o critério de
  aceite explícito de que a UI deixou de ser "próxima fase".
- **Dependência de backend (GATE DURO):** os botões de resultado/relatório/faturamento **só
  funcionam após ENG-007/008/009 mergeados**. Se implementar antes, os botões devem ficar
  desabilitados com tooltip "aguardando backend" — não apontar para endpoint inexistente.

---

## §4 Critérios de aceite

1. Item `coletado` mostra botão **"Registrar resultado"** (não o mock-tag); ao clicar, registra e o
   item transita para `resultado_disponivel` (recarregado do backend).
2. Itens `em_analise`/`resultado_disponivel` mostram estado legível (sem o mock-tag "próxima fase").
3. Card de agendamento mostra botão **"Confirmar realização"** quando `confirmado`; ao clicar,
   chama `/agendamentos/{proto}/realizar` e itens transitam para `coletado`.
4. Header logado mostra botões de **Relatório (CSV/PDF)** e **Faturamento (CSV)**; clique baixa o
   arquivo via `fetch`+`blob` com auth.
5. Todo fetch novo trata 401/403 via `handleUnauthorized()`.
6. Mock-tags `clinica.html:1452` e `:1454` **removidos** (grep não os encontra).
7. Sem erro de console; sem chamada a endpoint inexistente.
8. Fora de demo/login, os botões do header não aparecem.

---

## §5 Verificação

```bash
# Garantir que backend V2 está mergeado (GATE DURO)
git log --oneline | grep -E "ENG-007|ENG-008|ENG-009"   # devem aparecer

# Grep de saneamento — mock-tags não devem existir mais
grep -n "próxima fase\|mock-tag\|mock-aviso" clinica.html   # deve retornar vazio

# Smoke manual (modo demo, persona clínica):
# 1. Buscar pedido DEMO-EXAME-0001; item agendado → coletar → registrar resultado
# 2. Confirmar transição coletado → (resultado registrado) → resultado_disponivel
# 3. Header → Relatório (CSV) → baixa arquivo com os exames da clínica
# 4. Header → Faturamento (CSV) → baixa agregação por TUSS
```

Se houver fixture browser-E2E (`tests/` externo), adicionar caso leve:
`test_clinica_registra_resultado_e_baixa_relatorio` — opcional, não bloqueia.

---

## §6 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add clinica.html` — nunca `git add .` / `-A`.
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## §7 Fluxo

1. Confirme GATE DURO: ENG-007/008/009 mergeados. Se não, **pause e relate**.
2. Implemente (`clinica.html` apenas).
3. Branch: `local-extension/kimi3-007-ui-clinica`.
4. Confirme §5 (grep mock-tags vazio + smoke).
5. PR `[KIMI3]` → Revisor audita → Conselheiro ratifica → Fabiano martela.

---

## §8 Anexo de implementação (UI-detail) — verificado `3162af9`

> **Adendo do arquiteto (2026-08-07):** enriquecido enquanto o backend corre, para o Kimi 3 executar
> sem ambiguidade no instante em que o gate cair. Toda âncora é `file:line` verificado in-loco.

### §8.1 Helpers a **portar** de `dispensador.html` → `clinica.html`

`clinica.html` **não tem** nenhum helper de relatório/download — eles vivem em `dispensador.html`.
Portar (copiar+adaptar) este conjunto:

| Helper | Origem (`dispensador.html`) | Para quê |
|---|---|---|
| `_baixarBlob(blob, filename)` | `:1602-1608` | Download via `URL.createObjectURL` + `<a download>` — **nunca** `<a href>` ao endpoint |
| `_isoLocal(dt)` | `:1616-1621` | `Date → 'YYYY-MM-DD'` (local, sem desvio de fuso) |
| `_brParaISO(br)` | `:1627-` | `'DD/MM/AAAA' → 'YYYY-MM-DD'` (valida período do mini-form) |
| `_periodoParams` / `_validarPeriodo` / `_initRelatorioPeriodo` | `:1627-1710` (bloco) | Mini-form de período (de/ate) + validação |

`clinica.html` **já tem** estes (reusar, não duplicar):

| Helper | Onde (`clinica.html`) | Assinatura |
|---|---|---|
| `authHeaders()` | `:684-688` | `{ 'Content-Type': 'application/json', Authorization: Bearer <jwt> }` |
| `handleUnauthorized()` | `:824-827` | alert + `logout()` — chamar em todo 401/403 |
| `_extrairMsgErro(errData, fallback)` | `:829-835` | normaliza `detail` (string/array/obj) |
| `recarregarPedido()` | `:1538-1550` | `GET /pedidos-exame/{proto}` + `renderizarPedido` — chamar após mutação |
| `atualizarStatusUI(itemId, novoStatus)` | `:1506-` | refresh visual do item |

### §8.2 Botão "Registrar resultado" — substitui `clinica.html:1452`

Remover o mock-tag e inserir botão. Função nova `registrarResultado(itemId)`, espelhando
`registrarColeta` (`clinica.html:1477-1504`) — mesmo esqueleto: desabilita botão → fetch → trata
401/403/422 → `atualizarStatusUI` + `recarregarPedido`. A única diferença é o body:

```js
async function registrarResultado(itemId) {
  const resumo = prompt('Resumo do resultado (ex.: "Glicemia 92 mg/dL"):');
  if (resumo == null) return;                      // cancelou
  const btn = document.getElementById('btn-resultado-' + itemId);
  if (btn) { btn.disabled = true; btn.textContent = 'Registrando…'; }
  try {
    const resp = await fetch(
      BACKEND + '/pedidos-exame/' + encodeURIComponent(pedidoAtual.protocolo) +
      '/itens/' + itemId + '/resultado',
      { method: 'POST', headers: authHeaders(), body: JSON.stringify({ resultado_resumo: resumo }) }
    );
    if (resp.status === 401 || resp.status === 403) { handleUnauthorized(); return; }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      if (btn) { btn.disabled = false; btn.textContent = 'Registrar resultado'; }
      alert('Erro: ' + _extrairMsgErro(err, String(resp.status)));
      return;
    }
    const data = await resp.json();
    atualizarStatusUI(itemId, data.status_item || 'resultado_disponivel');
    recarregarPedido();                            // estado autoritativo vem do backend
  } catch (_) {
    if (btn) { btn.disabled = false; btn.textContent = 'Registrar resultado'; }
    alert('Falha de rede ao registrar resultado.');
  }
}
```

> **Endpoint** (pós ENG-007): `POST /pedidos-exame/{proto}/itens/{id}/resultado`, body
> `{resultado_resumo?: string, resultado_url?: string}` (`ResultadoIn`, `pedidos_exame.py:969-971`).
> **Não** há campo de arquivo neste despacho — upload de laudo é outra fatia (fora de escopo V2).

### §8.3 Estados `em_analise` / `resultado_disponivel` (`clinica.html:1453-1454`)

Sem botão aqui — só exibição legível (hoje é mock-tag "próxima fase"):

```js
} else if (item.status_item === 'em_analise') {
  acoesHtml = `<span class="laudo-aguardo">⏳ Em análise — resultado em breve.</span>`;
} else if (item.status_item === 'resultado_disponivel') {
  acoesHtml = `<span class="laudo-pronto">✓ Resultado disponível</span>`;
}
```

### §8.4 Botões de relatório + faturamento no header (`clinica.html:478-481`)

Inserir **dentro** de `#header-sessao` (que é `hidden` até logar — os botões só aparecem logados),
antes do botão Sair:

```html
<div class="header-right hidden" id="header-sessao">
  <span class="header-user" id="header-nome-clinica"></span>
  <button type="button" class="btn-rel" onclick="abrirRelatorioExames('csv')">🔬 Relatório (CSV)</button>
  <button type="button" class="btn-rel" onclick="abrirRelatorioExames('pdf')">🔬 Relatório (PDF)</button>
  <button type="button" class="btn-rel" onclick="abrirFaturamento('csv')">💰 Faturamento</button>
  <button class="btn-logout" onclick="logout()">Sair</button>
</div>
```

Portar o CSS `.btn-rel` de `dispensador.html:299-300` para o `<style>` de `clinica.html`.

Funções (espelhar `exportarSngpc` `dispensador.html:1711-1747`):

```js
async function abrirRelatorioExames(fmt) {
  // mini-form de período (portar _initRelatorioPeriodo/_periodoParams de dispensador.html)
  const qs = new URLSearchParams(/* período ISO, se houver */).toString();
  const nome = `relatorio_exames_${_isoLocal(new Date())}.${fmt}`;
  try {
    const resp = await fetch(`${BACKEND}/clinicas/relatorio.${fmt}` + (qs ? `?${qs}` : ''),
                             { headers: authHeaders() });
    if (resp.status === 401 || resp.status === 403) { handleUnauthorized(); return; }
    if (!resp.ok) { /* _extrairMsgErro + alert */ return; }
    _baixarBlob(await resp.blob(), nome);
  } catch (_) { alert('Falha de rede ao baixar relatório.'); }
}

async function abrirFaturamento(fmt='csv') {   // análogo, endpoint /clinicas/faturamento.${fmt}
  ...
}
```

**GATE DURO lembrete:** se ENG-008/009 ainda não mergeados, os botões devem ficar `disabled` com
tooltip "aguardando backend" — não apontar para endpoint inexistente.

### §8.5 R2 — aviso ao paciente (verificar, não construir)

Antes de declarar "feito", confirmar que `GET /pedidos-exame/{proto}` (consumido por `cidadao.html`,
não por `clinica.html`) já devolve `status + data_agendamento`. Se sim, **zero trabalho nesta UI** —
o aviso é no lado do cidadão (polling, padrão F5-C2). Se faltar o campo, reportar como follow-up
(não bloqueia este despacho).

### §8.6 Microcopy "sem dose" no campo princípio ativo — `prescritor.html` (item do conselheiro)

> **Escopo diverso:** este item é em **`prescritor.html`**, não `clinica.html`. Anexado a este
> despacho por decisão do conselheiro (KIMI3-007 "ganha um item").

**Problema:** o campo de princípio ativo (`prescritor.html:1747`, classe `.med-nome`) aceita que o
prescritor digite a dose junto ("Losartana 50mg"). Hoje o placeholder é só `"Princípio Ativo / Nome *"`,
sem hint. A dose digitada flui direto para `canon_ativo` (`semaforo_decisao.py:159`) — que **não faz
strip de dose** — e quebra o lookup exato por dict-key (`:272-273`), gerando **amarelo falso** em
CIDs exaustivos (hoje I10; amanhã E11/J45/F32/N39.0).

**Observação:** a dose tem campo próprio na mesma linha — `.med-conc` ("Concentração *",
`prescritor.html:1748`). Logo, dose em `.med-nome` é erro de entrada que o microcopy corrige.

**O que fazer (2 opções, escolher a mais consistente):**

- **Opção A (placeholder extendido) — mais leve:**
  ```html
  <input ... class="form-input med-nome"
    placeholder="Princípio ativo (sem dose) *" ...>
  ```
- **Opção B (hint dinâmico) — espelha o precedente `.med-posolog-nota` (`prescritor.html:2634-2641`):**
  ```html
  <input ... class="form-input med-nome" placeholder="Princípio Ativo / Nome *" ...>
  <div class="med-nome-nota" style="font-size:11px;color:#64748b;margin-top:4px;">
    Só o princípio ativo, sem dose (ex.: "Losartana", não "Losartana 50mg").
  </div>
  ```
  Inserir via `insertAdjacentElement('afterend', ...)` no template de `adicionarMedicamento`
  (`:1730-1750`), igual ao padrão já usado para posologia.

**Recomendação do arquiteto:** Opção A (placeholder) — mais barata, zero JS, bate com a convenção
dominante do card (placeholder como microcopy). Se o conselheiro preferir visibilidade maior, Opção B.

> **Mitigação parcial do bug canon_ativo (item 1 do martelo):** este microcopy reduz a frequência do
> amarelo falso, mas **não o elimina** — um prescritor pode ignorar o hint. O fix real é o strip de
> dose em `canon_ativo` (ticket separado, core-adjacente).

---

## §9 Lista de checagem final (para o Kimi 3)

- [ ] Mock-tags `clinica.html:1452` e `:1454` removidos (grep "próxima fase"/"mock-tag" vazio).
- [ ] `registrarResultado(itemId)` definida; chama endpoint de `resultado`, trata 401/403, recarrega.
- [ ] Helpers portados: `_baixarBlob`, `_isoLocal`, `_brParaISO`, mini-form de período.
- [ ] Botões de relatório + faturamento em `#header-sessao` (só visíveis logado); CSS `.btn-rel`.
- [ ] Se backend V2 ainda não mergeado: botões `disabled` + tooltip (GATE DURO).
- [ ] Todos os fetchs usam `authHeaders()`; downloads via `_baixarBlob`, nunca `<a href>`.
- [ ] Sem erro de console; sem chamada a endpoint inexistente.
- [ ] Após mutações (coleta, resultado): `recarregarPedido()` — estado autoritativo vem do backend.
- [ ] **Microcopy "sem dose"** em `prescritor.html:1747` (§8.6).

---

*Despacho emitido pelo arquiteto. Frontend puro, consumo dos endpoints do arco V2. Origem:
TICKET-MODULO-CLINICA-V2 §3/§4/§5/§6. GATE DURO: backend ENG-007/008/009 mergeado. Anexo §8
enriquecido em 2026-08-07 enquanto o backend corre, para execução sem ambiguidade. §8.6 (microcopy
"sem dose", `prescritor.html`) anexado por instrução do conselheiro.*
