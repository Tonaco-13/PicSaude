# Descritivo — Portal (índice) e Verificação Pública — backend + frontend

| Campo | Valor |
|---|---|
| De | Kimi |
| Para | Fabiano Tonaco |
| Data | 2026-08-13 |
| Classe | `docs` |
| Escopo | Levantamento factual do estado em disco (branch `docs/handoff-2026-08-09`); nenhuma alteração de código |

---

## 1. Visão geral

O Portal (`index.html`, 863 linhas) é a **porta de entrada pública** do PicSaúde —
não é um módulo autenticado, é o hall que amarra os quatro. Três responsabilidades:

1. **Selecionar o perfil** e despachar para o módulo certo (com auto-login demo);
2. **Lente de Auditoria** — motor de visualização da circulação de **qualquer objeto
   sanitário**, em visão neutra (existência e estado, nunca conteúdo clínico);
3. **Status da instância** — saúde e versão do backend, sem dependências externas.

A página `validar.html` (406 linhas) é a **verificação pública de autenticidade** de
uma prescrição — cartão de entrada dela fica no próprio Portal.

---

## 2. Portal (`index.html`)

### 2.1 Cabeçalho e apresentação
Logo institucional, título "Plataforma de Custódia Sanitária Digital" e a linha de
fluxo: **1. Prescritor emite → 2. Cidadão recebe na carteira → 3. Dispensador atende
no balcão** — com link para o **guia completo** (`guia.html`).

### 2.2 Cards de perfil (linhas 432–480)

| Card | Destino | Persona demo (`/demo/login`) |
|---|---|---|
| 🩺 Prescritor | `prescritor.html` | `prescritor` |
| 💊 Dispensador | `dispensador.html` | `dispensador` |
| 👤 Cidadão | `cidadao.html` | `paciente` |
| 🏥 Clínica / Laboratório | `clinica.html` | `clinica` (adendo à persona) |
| 🔍 Verificar Prescrição | `validar.html` | — (público, sem login) |
| ⚙️ Administrador | **comentado** — `admin.html` não existe neste momento | — |

**Demo boot (TICKET-6, linhas 342–402):** se `GET /config/public` indicar
`demo_mode`, os cards ganham badge DEMO e o clique é **interceptado**: chama
`POST /demo/login {role}`, grava o JWT em `sessionStorage` (`picsaude_demo_*`) e
navega — o módulo destino hidrata a sessão e pula a tela de senha. O parâmetro de URL
`?demo_role=X` dispara o clique automaticamente. Fora de demo, os cards são links
comuns.

> **Decisão de 2026-08-12 (registrada no código):** o painel "Chaves de acesso
> (demo)" **não aparece no índice** — só nos módulos, na borda superior de cada tela.
> O índice fica limpo como portal; no lugar do antigo painel entrou a Lente.

### 2.3 Lente de Auditoria — Circulação PicSaúde (linhas 483–544, 671–859)

Nasceu em 2026-08-12 generalizando o motor de busca da "Circulação Diagnóstica" do
módulo Laboratório para **qualquer objeto sanitário**, no mesmo formato visual
(cartão + linha de busca + botão) em tom institucional azul — "é uma lente de
auditoria do portal, não uma operação de laboratório".

**Ordem de resolução da chave digitada** (mínimo 4 caracteres):

1. **Formato de chave de circulação diagnóstica** (hex 8–16, sem hífen, ex.
   `A3F1C2B4E5D6`) **e** sessão demo ativa → `GET /circulacao/{chave}` (endpoint
   autenticado, com o token demo da sessão). Renderização **neutra**: status,
   validade da chave e **quantidade** de exames — nunca paciente, prescritor ou nomes
   de exame ("auditoria vê estado; operação fica no módulo Clínica/Laboratório").
2. **Endpoints públicos neutros**, na ordem da tabela abaixo — o payload já nasce
   neutro no backend (sem clínica, sem identidade); a lente só apresenta protocolo,
   `tipo_emissao`, badges de status por item, e (atestados) assinado/vigente.
3. **Nada encontrado** → feedback com o próximo passo (R4: nunca calar) — inclusive a
   mensagem distingue "formato de chave de circulação sem sessão ativa → entre pelo
   card da Clínica/Laboratório".

| Tipo consultável | Endpoint público | Campo de status |
|---|---|---|
| 📄 Receita | `/public/prescricoes/{protocolo}` | `status_prescricao` |
| 🧪 Pedido de exame | `/public/exames/{protocolo}` | `status_pedido` |
| 🩺 Atestado | `/public/atestados/{protocolo}` | `status` |
| 📋 Laudo | `/public/laudos/{protocolo}` | `status_laudo` |
| ↗️ Encaminhamento | `/public/encaminhamentos/{protocolo}` | `status_encaminhamento` |
| ↩️ Contrarreferência | `/public/contrarreferencias/{protocolo}` | `status_contrarreferencia` |

Os **badges seguem o Contrato de Estados** (CLAUDE.md §5a/§5b): o tom (vermelho/
amarelo/verde/azul) deriva da família do estado — cancelado/expirado/revogado,
pendente/proposta, confirmado/dispensado/vigente, emitido/em custódia.

### 2.4 Status da instância (linhas 546–550, 582–668)
`GET /health` + `GET /health/version` com timeout por `AbortSignal`: ambiente, versão,
uptime formatado. Rodapé com os mesmos links ("Saúde da instância" · "Versão") e a
identidade legal: AGPL-3.0, registro de programa no INPI (BR 51 2026 002267-3),
marcas em análise, responsável técnico e contato.

---

## 3. Verificação pública (`validar.html`)

- **Busca por protocolo** → `GET /public/prescricoes/{protocolo}` (sem autenticação).
- **Resultado:** protocolo, tag de tipo de emissão, badge e rótulo de status,
  itens da prescrição com status individual, e o **QR Code da prescrição** com URL de
  compartilhamento (`copiarLink`).
- **Autoload:** abrir com `?protocolo=...` (o QR impresso aponta para cá) já dispara
  a verificação.
- Mantém o painel "Chaves de acesso (demo)" no topo (TICKET-6) — é tela de módulo
  para efeito do padrão visual, embora o acesso seja público.

---

## 4. Mapa frontend ↔ backend

| Função JS | Endpoint | Autenticação |
|---|---|---|
| `picsaudeDemoBoot` (índice e validar) | `GET /config/public` | pública |
| clique em card (demo) | `POST /demo/login {role}` | pública (demo_mode) |
| Lente — circulação | `GET /circulacao/{chave}` | Bearer (token demo da sessão) |
| Lente — objetos | `GET /public/{prescricoes,exames,atestados,laudos,encaminhamentos,contrarreferencias}/{protocolo}` | pública, payload neutro |
| Status da instância | `GET /health` · `GET /health/version` | pública |
| `buscar` (validar.html) | `GET /public/prescricoes/{protocolo}` | pública |

---

## 5. Observações

1. **O índice é a única tela sem o painel de chaves** — decisão explícita de
   2026-08-12, registrada em comentário no código; a Lente ocupa o lugar.
2. **A Lente é a materialização da "lente de auditoria" pedida na conversa de
   2026-08-12**: mesmo motor da Circulação Diagnóstica do laboratório, generalizado
   para todo objeto sanitário, em visão neutra — e a remoção da seção do
   `clinica.html` (cancelada em 2026-08-13) permanece como opção futura, já que a
   consulta pela chave existe aqui (mas não as ações operacionais).
3. **Encaminhamento e contrarreferência** já têm endpoints públicos neutros e aparecem
   na Lente — o Núcleo Sanitário (§7) está parcialmente exposto à auditoria antes de
   ter módulo próprio.
4. **Administrador é o único perfil sem módulo**: o card existe comentado no HTML,
   aguardando `admin.html` (o papel `auditor`/`admin` já existe no RBAC do backend —
   ex.: relatórios de dispensações em `relatorios.py`).
5. **Validação pública é deliberadamente mínima**: existência, estado e itens — o
   conteúdo clínico e a identidade das partes nunca saem por `/public/*`.

---

*Descritivo gerado por leitura direta de `index.html`, `validar.html` e dos routers
`publico.py`, `circulacao_diagnostica.py`, `health.py`, `demo.py` e
`config_publico.py`. Nenhuma linha de código foi alterada.*
