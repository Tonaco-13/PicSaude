# TICKET-RODAPE-CONTATO — Rodapé do guia.html sem nome/e-mail pessoal + e-mail institucional no index.html

| Campo | Valor |
|---|---|
| **Classe** | `local-extension` (customização institucional que não altera semântica clínica) |
| **Para** | Arquiteto (este spec) → Engenheiro (Claude/Code terminal) → Conselheiro (Cowork) → martelo Fabiano |
| **Origem** | Despacho do Fabiano, 2026-07-25: "tirar meu nome e email desta página: guia.html e inserir o email contato@picsaude.com.br na página index" |
| **Pré-requisito** | `main` atual (pós PR #125 — rebuild PG demo) |

## §1 Contexto (não reabrir)

O `guia.html` (página pública de explicação do PicSaúde) hoje exibe no rodapé o **nome civil, vínculo acadêmico (UFPE) e e-mail pessoal institucional (fabiano.borges@ufpe.br)** do responsável técnico. Em produção pública (picsaude.com.br), isso expõe identificação pessoal + canal de contato individual — desnecessário para a finalidade da página (que é explicar o produto, não Localizar uma pessoa). E-mail institucional próprio (`contato@picsaude.com.br`) é o canal correto, e ele pertence ao rodapé do `index.html` (vitrine), não do `guia.html` (explicação).

**Decisão de produto (Fabiano, 2026-07-25):**
- `guia.html`: **remover** o bloco de contato pessoal inteiro (nome + UFPE + e-mail UFPE).
- `index.html`: **inserir** `contato@picsaude.com.br` como canal institucional. O nome do responsável técnico ("Dr. Fabiano Tonaco Borges") **permanece** no `index.html` (já está lá — linha 514).

### Por que `local-extension` e não `docs`

Mexer em PII (remover nome + e-mail pessoal de página pública) não é "só documentação" — é mudança de exposição de dado pessoal em página web pública. Embora o sentido clínico do sistema não seja alterado, a classe `local-extension` é a correta porque (a) não toca em núcleo (NUCLEO_SANITARIO, ledger, estados, custódia), (b) não quebra contrato público existente, (c) não adiciona campo obrigatório a tabela do núcleo. Mas **exige checklist PII-EXAUSTIVIDADE** (LEARNINGS 2026-07-09) — ver §4.

## §2 Invariantes (não-negociáveis)

- **§10 (PII-EXAUSTIVIDADE):** antes do merge, o PR **deve** listar TODOS os sites (arquivos) onde o nome "Fabiano Tonaco Borges" e o e-mail "fabiano.borges@ufpe.br" aparecem no código ou em páginas servidas. Justificativa inline para qualquer site que NÃO seja tocado por este PR.
- **R1 (reprodutibilidade):** nenhuma mudança no backend, ledger, ou domínio. Só HTML.
- **Não-quebra de contrato público:** nenhum endpoint público muda. Nenhuma rota `/public/*` é tocada.

## §3 Contrato (estado atual dos rodapés — verificado em 2026-07-25)

### 3.1 `index.html` rodapé (linhas 504-523)
```
<footer>
  <div class="footer-inner">
    <div>
      ...PicSaúde © 2026 ...
      ...Distribuído sob GNU AGPL-3.0...
      ...Programa de computador registrado no INPI...
      Responsável técnico: Dr. Fabiano Tonaco Borges.   ← linha 514, PERMANECE
    </div>
    <nav class="footer-links">
      <a id="link-health">Saúde da instância</a>
      <a id="link-version">Versão</a>
    </nav>
  </div>
</footer>
```
**E-mail NÃO existe aqui hoje.**

### 3.2 `guia.html` rodapé (linhas 419-430)
```
<footer class="footer">
  <div class="demo-hooks">
    <span class="label">Veja na demonstração</span>
    <code>DEMO-FILA-0001</code> ...
    <code>DEMO-ATESTADO-0001</code> ...
  </div>
  <div class="contact">                                  ← BLOCO INTEIRO SAI
    <span class="name">Prof. Dr. Fabiano Tonaco Borges</span>
    <span class="org">Universidade Federal de Pernambuco</span>
    <a href="mailto:fabiano.borges@ufpe.br">fabiano.borges@ufpe.br</a>
  </div>
</footer>
```
**Decisão:** o `<div class="contact">` inteiro sai — as 3 linhas (nome, org, e-mail) formam uma unidade de "contato pessoal do Prof. Dr.". Deixar só a UFPE (após remover nome+email) criaria informação órfã. O bloco `.demo-hooks` **permanece** (não é contato pessoal; é orientação de demo).

### 3.3 CSS `.contact` em `guia.html` (linhas 235-239, 248, 254)
Após remover o bloco, as regras `.contact`, `.contact .name`, `.contact .org`, `.contact a`, `.contact a:hover` ficam **sem uso** (código morto CSS). Ver §4.4 sobre decisão explícita.

## §4 Spec de implementação

### 4.1 Arquivos tocados
- `index.html` — inserir linha de e-mail no rodapé
- `guia.html` — remover bloco `.contact` (HTML + tratar CSS morto)

### 4.2 `index.html` — INSERIR e-mail

Na `<div>` interna do rodapé, **após** a linha 514 (`Responsável técnico: Dr. Fabiano Tonaco Borges.`), adicionar nova linha:

```html
<div class="footer-brand" style="margin-top:4px; font-size:11px; opacity:.85;">
  Contato: <a href="mailto:contato@picsaude.com.br"
              style="color:inherit; text-decoration:underline;">contato@picsaude.com.br</a>.
</div>
```

Estilo idêntico às linhas adjacentes (11px, opacidade .85) pra manter hierarquia visual. O `<a>` tem `color: inherit` pra não destacar demais — a UFPE/AGPL não são links, contato é, mas discreto.

### 4.3 `guia.html` — REMOVER bloco `.contact`

Remover as linhas 425-429 (o `<div class="contact">...</div>` inteiro). O `<div class="demo-hooks">` (linhas 420-424) **permanece**.

### 4.4 Código morto CSS — decisão explícita

Após §4.3, as regras `.contact*` (linhas 235-239) ficam sem uso. **2 opções:**

- **(A) Remover as regras CSS** junto (limpo — git blame mostra a razão)
- **(B) Deixar comentado com referência a este ticket** (preserva intent pra futuro)

**Recomendação Arquiteto: opção (A)** — remover. Razão: CSS morto é dívida. As regras de responsividade `.contact { text-align: left }` (linha 248) e `.contact .name { background: #fff !important }` (linha 254, modo print/dark) também saem — são sobre o mesmo elemento. Engenheiro justifica A ou B no PR.

### 4.5 Checklist PII-EXAUSTIVIDADE (obrigatório antes do merge)

Rodar e colar output literal no PR:

```bash
# Nome civil (aparece onde?)
grep -rnE "Fabiano Tonaco Borges|Fabiano Borges" --include="*.html" --include="*.py" --include="*.md" .

# E-mail UFPE (aparece onde?)
grep -rnE "fabiano\.borges@ufpe\.br" --include="*.html" --include="*.py" --include="*.md" .

# E-mail contato@picsaude.com.br (já existe em algum lugar?)
grep -rnE "contato@picsaude\.com\.br" --include="*.html" --include="*.py" --include="*.md" .
```

**Esperado após implementação:**
- `guia.html`: zero ocorrências de Fabiano/fabiano.borges@ufpe.br
- `index.html`: 1 ocorrência de Fabiano (mantida, linha 514) + 1 ocorrência de contato@picsaude.com.br (nova)
- Demais arquivos: justificar inline cada ocorrência remanescente (ex.: `LICENSE`, `COMMERCIAL-LICENSE.md`, `README.md` — prováveis, sem impacto web público)

## §5 Critérios de aceite

1. **`guia.html` rodapé** não contém `<div class="contact">`, nem nome "Fabiano", nem e-mail UFPE
2. **`guia.html` rodapé** mantém o bloco `.demo-hooks` (DEMO-FILA-0001 etc.) intacto
3. **`index.html` rodapé** mantém "Responsável técnico: Dr. Fabiano Tonaco Borges." (linha 514 — não remover)
4. **`index.html` rodapé** tem nova linha com `contato@picsaude.com.br` como `<a href="mailto:">`
5. **CSS morto tratado** (opção A ou B do §4.4, justificada no PR)
6. **Checklist §4.5 colado no PR** com output literal dos 3 greps
7. **Nenhum erro de console** ao carregar `index.html` e `guia.html` no browser (gate de smokes cobre)
8. **Browser-E2E verde** — ver §6

## §6 Browser-E2E (obrigatório no aceite)

Não há arquivo novo — reusar o gate existente. Rodar smokes contra `app_demo` local:
```bash
cd backend
python -m pytest tests/browser/test_smokes.py -v
```
**Critério:** todos os smokes verdes (incluindo `TestGuiaNaVitrine::test_guia_responde_e_renderiza` e `test_link_da_landing_abre_o_guia`, que cobrem `guia.html`).

Opcional (se o engenheiro julgar necessário): adicionar asserção específica em `test_smokes.py::TestGuiaNaCarteira` ou nova classe:
```python
def test_guia_sem_contato_pessoal_no_rodape(page, app_demo):
    page.goto(f"{app_demo}/guia.html", wait_until="networkidle")
    body = page.locator("body")
    expect(body).not_to_contain_text("fabiano.borges@ufpe.br")
    expect(body).not_to_contain_text("Prof. Dr. Fabiano")

def test_index_tem_contato_institucional(page, app_demo):
    page.goto(f"{app_demo}/index.html", wait_until="networkidle")
    body = page.locator("body")
    expect(body).to_contain_text("contato@picsaude.com.br")
```

## §7 Fora de escopo

- Mudar o rodapé de outros HTMLs secundários (`dispensador.html`, `prescritor.html`, `cidadao.html`, `clinica.html`, `validar.html`) — dívida separada (mencionada na pendência #4 da sessão de rebuild)
- Criar `docs/SOBRE.md` (pendência #3 da sessão de rebuild)
- Migrar o e-mail para um formulário de contato — decisão de produto futura
- Remover o nome do rodapé do `index.html` — explicitamente NÃO (instrução do Fabiano: manter)

## §8 Fluxo de aprovação

1. Engenheiro (Claude/Code terminal) implementa + roda smokes + checklist §4.5
2. Conselheiro (Cowork) dá parecer — foco: PII-EXAUSTIVIDADE completa (§4.5) + opção A/B do CSS justificada
3. Arquiteto (ZCode) ratifica verde do Conselheiro ou pede ajuste
4. Martelo do Fabiano + merge
5. Deploy (manual ou CI) — verificar ao vivo em picsaude.com.br/guia.html e /index.html

## §9 Não fazer

- Não remover "Responsável técnico: Dr. Fabiano Tonaco Borges." do `index.html` (instrução explícita do Fabiano: nome permanece, só insere e-mail)
- Não remover o bloco `.demo-hooks` do `guia.html`
- Não adicionar novo endpoint
- Não tocar em `LICENSE`, `COMMERCIAL-LICENSE.md`, `README.md` (autores legíveis em arquivo de licença é diferente de exibição pública web)
- Não mergear sem o checklist §4.5 colado no PR

## §10 Coordenadas com trabalhos em pausa

| Trabalho | Relação |
|---|---|
| **Etapa C de UX (F5-C1/C2/C3)** | Pausada por decisão do Fabiano. Independente deste ticket — pode rodar em paralelo. |
| **Infra de teste externo (TICKET-F5-B5-GATE-EXTERNO)** | Independente |
| **Sessão de rebuild PG (PR #125)** | Pré-requisito satisfeito — demo está limpa |
