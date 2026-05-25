# Extrair script de bootstrap demo dos 5 HTMLs para `js/demo-bootstrap.js`

> **Origem:** Jules — revisão de fim da Etapa 6 (2026-05-24), achado P2#4 (Duplicação).
> **Boa primeira contribuição:** ⭐⭐ (Frontend / JavaScript básico)
> **Dificuldade:** trivial — copiar-colar com pequena adaptação.
> **Estimativa:** 1-2 horas (inclui testar nos 5 HTMLs).

---

## Contexto

A Etapa 6 do PicSaúde introduziu o **modo demo** — quando o backend roda com `PICSAUDE_DEMO_MODE=true`, todos os frontends exibem um banner amarelo "MODO DEMO" no topo, lendo o estado de um endpoint público `/config/public`.

O script JavaScript que faz isso (chamar `/config/public`, decidir se exibe banner, renderizar a mensagem) **está duplicado em 5 arquivos HTML**:

- `index.html` (linhas ~341-371)
- `cidadao.html` (linhas ~266-276)
- `prescritor.html` (linhas ~241-251)
- `dispensador.html` (linhas ~279-289)
- `clinica.html` (linhas ~439-465)
- `validar.html` (linhas ~143-146)

Se a gente quiser mudar o layout do banner, hoje precisa editar 5+ arquivos. Toda mudança vira oportunidade de inconsistência.

## O que fazer

1. Criar um arquivo novo `js/demo-bootstrap.js` na raiz do projeto (irmão dos HTMLs).
2. Mover o conteúdo da função `picsaudeDemoBoot` para esse arquivo.
3. Em cada um dos 5 HTMLs, substituir o `<script>` inline por `<script src="js/demo-bootstrap.js"></script>`.
4. Confirmar que o banner ainda aparece corretamente em demo (`PICSAUDE_DEMO_MODE=true`) e some em modo normal.

## Cuidados

- O `index.html` tem **uma lógica a mais** (intercepta cards de role para fazer `/demo/login`) — esse pedaço pode ficar inline no `index.html` mesmo, ou virar uma segunda função no `demo-bootstrap.js` (`picsaudeDemoSelector`) chamada só pelo `index.html`. Decidir conforme preferir, mas explicar a escolha no PR.
- O `validar.html` tem comportamento ligeiramente diferente (selo "DEMO" em vez de banner). Verificar se o helper compartilhado serve ou se esse arquivo continua inline.
- **Não tocar em `clinica.html`** além do banner — o redirect para `/index.html` em demo é específico desse arquivo.

## Critério de aceite

- 1 commit, mensagem `refactor(frontend): extrair demo bootstrap para js/demo-bootstrap.js`
- Diff: arquivo novo `js/demo-bootstrap.js` + 5 HTMLs editados (substituição do script inline pelo `<script src>`)
- Teste manual:
  - `PICSAUDE_DEMO_MODE=true uvicorn backend.app.main:app --reload`
  - Abrir cada um dos 5 HTMLs no navegador → confirmar que banner aparece
  - `PICSAUDE_DEMO_MODE=false` (ou unset) → confirmar que banner some

## Onde pedir ajuda

- Dúvida sobre Git/PR: peça no canal da extensão antes de gastar tempo errado.
- Dúvida sobre rodar o backend: README.md tem comandos básicos.
- Dúvida sobre a lógica do banner: leia `backend/docs/tickets/TICKET-6-DEMO-MODE.md` §4.10.
