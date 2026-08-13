# Descritivo — Módulo Cidadão — backend + frontend

| Campo | Valor |
|---|---|
| De | Kimi |
| Para | Fabiano Tonaco |
| Data | 2026-08-13 |
| Classe | `docs` |
| Escopo | Levantamento factual do estado em disco (branch `docs/handoff-2026-08-09`); nenhuma alteração de código |

---

## 1. Visão geral e persona

O módulo Cidadão é a **carteira digital** do papel **`paciente`**, identificado pelo
**CPF**. É o elo central da custódia: todo objeto sanitário digital (receita, pedido de
exame, atestado, laudo) **chega aqui** na emissão/liberação, e é daqui que o cidadão o
**movimenta** — transfere à farmácia ou ao laboratório, gera códigos de apresentação,
devolve ao médico, pede renovação, dá ciência de laudos.

A metáfora do produto é explícita no código: **o CPF é o PIX** — quem emite "envia para
o CPF", e o documento aparece na carteira sem ação do destinatário.

**Frontend:** `cidadao.html` (1 595 linhas, single-page; `apiFetch` central com Bearer;
token só em memória).
**Backend:** router `auth` (que no PicSaúde concentra o pacote `/paciente/*`),
`solicitacoes`, `tokens`, `prescricoes` (atomização), `pedidos_exame`, `laudos`,
`atestados`, `config_publico`, `demo`.

---

## 2. Jornada na tela (frontend `cidadao.html`)

### 2.1 Painel "Chaves de acesso (demo)"
Topo da página (mesmo padrão dos demais módulos, retoque de 2026-08-12). O cartão
**Cidadão · CPF** abre este módulo.

### 2.2 Acesso por OTP (linhas 259–285)
- **Tela de acesso:** só o CPF → `POST /auth/paciente/solicitar-codigo`.
  Em ambiente local o código sai no console do backend; em produção, por SMS/e-mail
  (comentário do próprio código).
- **Tela de validação:** código de 6 dígitos → `POST /auth/paciente/validar-codigo` →
  retorna **JWT com `role="paciente"`**, nome e CPF → entra na carteira.
- **Auto-login demo:** hidratação via `sessionStorage` (quem clicou "Entrar como
  Paciente" no índice) ou `POST /demo/login {role:"paciente"}` (KIMI3-002) — acesso
  direto por URL, pulando OTP.

### 2.3 Carteira (linhas 317–354)
Cartão do titular (nome + CPF) e cinco seções, nesta ordem (decisão de produto
documentada no HTML):

| Seção | Natureza | Ações do cidadão |
|---|---|---|
| **⚠ Alertas de vencimento** | prescrições a ≤ 7 dias da validade | botão **Renovar** |
| **Receitas** | objetos sob custódia do cidadão | token, transferir, devolver (ver §2.4) |
| **Atestados** | documento **final** (sobe acima de exames — F5-C3) | ler, **Baixar PDF** |
| **Pedidos de Exame Ativos** | objeto **intermediário** | **Transferir ao laboratório** (CNPJ) |
| **Laudos / Resultados** | resultado liberado pelo laboratório | **Baixar PDF**, **Dar ciência** |
| **Histórico de Prescrições** | linha do tempo | leitura |

**Polling de 30 s (F5-C2):** a carteira se atualiza sozinha — receita nova chega sem
clicar "Atualizar". 30 s (não 15 como o balcão) porque o cidadão é consumidor esporádico
mobile. Duas correções que o dispensador não tem: **o timer é limpo no logout** (o
`sair()` da farmácia não limpa, gerando storm de alerts) e **`visibilitychange` pausa
em aba oculta** e dispara refresh imediato ao voltar.

### 2.4 Ações sobre a receita (posse)

Cada card de receita ativa oferece:

- **📱 Token de Apresentação (Ticket 25 + Ticket 44):** `gerarToken` tenta primeiro a
  **circulação atomizada** — `POST /prescricoes/{proto}/tokens/atomizar`
  (`validade_minutos: 60`): se elegível, **cada item recebe código independente**
  ("cada farmácia verá apenas o item do código apresentado"), com QR por item, revogação
  individual e "Revogar todos". Se inelegível (classe controlada etc.) ou 409, cai para
  o **token único** da prescrição inteira (`POST /tokens/apresentacao`, retrocompat).
  QR via `GET /tokens/apresentacao/{codigo}/qr` (blob); revogação via `DELETE` —
  **idempotente, erros ignorados silenciosamente**. Tokens são efêmeros: mapa em
  memória, limpo a cada atualização da carteira, nunca em localStorage.
- **Autorizar Dispensação na Farmácia:** CNPJ (14 dígitos, demo já preenche a farmácia
  demo) → `POST /paciente/prescricoes/{proto}/transferir-farmacia`. Confirmação por
  `confirm()` e **modal pós-transferência (F5-C1)**: mostra o destino e oferece
  "Ver no histórico" — o card só some **depois** do ack visual, nunca durante
  (resolve a dor do "perdi a receita" vista no teste de circulação).
- **⚠️ Devolver ao Médico (COER-2):** área com motivo estruturado (remédio/apresentação
  errada, dose/posologia incorreta, dados do paciente incorretos, outros) + detalhe
  opcional → `POST /paciente/prescricoes/{proto}/devolver-prescritor`. A receita sai da
  posse do cidadão (`transferida_prescritor` — "Devolvida ao médico") e cai na **caixa
  de correções** do módulo Prescritor.

### 2.5 Pedidos de exame — o mesmo gesto do PIX
`transferirParaLaboratorio` espelha `transferirParaFarmacia`: CNPJ do laboratório →
`POST /pedidos-exame/{proto}/transferir-laboratorio` → o pedido cai na fila do
`clinica.html`. Rótulos de status traduzidos para o cidadão: `emitido` = "Com você",
`agendado` = "No laboratório", `coletado`, `em_analise`, `resultado_disponivel`.

**Decisão de produto registrada no código:** saíram desta tela o **agendamento**
(Ticket 29 — quem marca data é o laboratório) e a **chave de circulação** (Tickets 56/58
— exigia que o operador digitasse um código para descobrir o pedido). Ambos seguem no
backend e na tela do laboratório.

### 2.6 Atestados e laudos
- **Atestado:** chega na emissão (custódia prescritor→paciente transfere no POST — "o
  atestado É do paciente, o profissional entrega e não retém"). Sem botão de ação: só
  leitura (protocolo, título definido pelo conselho, finalidade, dias de afastamento —
  **ausência é informação**: atestado de comparecimento omite a linha) + Baixar PDF.
- **Laudo:** "chega ao paciente" quando o laboratório libera. Lista itens/conclusões,
  Baixar PDF e **Dar ciência** (`POST /laudos/{p}/ciencia-paciente`, quando
  `liberado` ou `ciencia_prescritor`); depois exibe "✓ Ciência registrada".

### 2.7 Perfil
"Dados do Cadastro Único": nome vem do backend; telefone/endereço gravados em
**localStorage** (`picsaude_perfil_{cpf}`) — preferências locais do aparelho.

---

## 3. Mapa frontend ↔ backend

| Função JS | Endpoint | RBAC |
|---|---|---|
| `solicitarCodigo` | `POST /auth/paciente/solicitar-codigo` | público |
| `validarCodigo` | `POST /auth/paciente/validar-codigo` → JWT `paciente` | público |
| `_autoLoginDemo` | `POST /demo/login` | público (demo_mode) |
| `carregarCarteira` | `GET /paciente/prescricoes` (posse + histórico) | paciente |
| `renderizarAlertas` | `GET /paciente/prescricoes/expirando?dias=7` | paciente |
| `solicitarRenovacao` | `POST /paciente/prescricoes/{p}/solicitar-renovacao` (201) | paciente |
| `transferirParaFarmacia` | `POST /paciente/prescricoes/{p}/transferir-farmacia` (201) | paciente |
| `confirmarDevolucaoMedico` | `POST /paciente/prescricoes/{p}/devolver-prescritor` (201) | paciente |
| `gerarToken` (atomizado) | `POST /prescricoes/{p}/tokens/atomizar` | paciente |
| `gerarToken` (fallback) | `POST /tokens/apresentacao` | paciente |
| `mostrarQrToken(Item)` | `GET /tokens/apresentacao/{codigo}/qr` | paciente |
| `revogarToken(Item)` / `revogarTodos` | `DELETE /tokens/apresentacao/{codigo}` | paciente |
| `carregarPedidosExame` | `GET /paciente/pedidos-exame` (posse + em_andamento) | paciente |
| `transferirParaLaboratorio` | `POST /pedidos-exame/{p}/transferir-laboratorio` | paciente, admin |
| `carregarAtestados` | `GET /paciente/atestados` (vigentes + histórico) | paciente |
| `baixarPdfAtestado` | `GET /atestados/{p}/pdf` | prescritor, admin, paciente |
| `carregarLaudos` | `GET /paciente/laudos` (disponíveis + histórico) | paciente |
| `darCienciaLaudo` | `POST /laudos/{p}/ciencia-paciente` | paciente |
| `baixarPdfLaudo` | `GET /laudos/{p}/pdf` | paciente (e demais autorizados) |

> Curiosidade arquitetural: o pacote `/paciente/*` vive no router **`auth.py`** —
> o router de autenticação do paciente cresceu e absorveu a carteira.

---

## 4. Backend relacionado que a UI **não** expõe

| Endpoint | Quem consome / observação |
|---|---|
| `POST /pedidos-exame/{p}/circulacao` (criar circulação diagnóstica) | **Decisão de produto**: chave de circulação saiu da tela do cidadão (Tickets 56/58); segue no backend |
| Agendamento de exame pelo paciente | Saiu da tela (Ticket 29); RBAC do `agendamentos.py` ainda aceita `paciente` |
| `POST /laudos/{p}/ciencia-prescritor` | **Prescritor** dá ciência do laudo |
| `POST /laudos` · `/assinar` · `/liberar` · `/encerrar` · `/cancelar` | **Laboratório** (backend pronto; UI do lab é próxima fase) |
| `GET /pedidos-exame/{p}/custodia`, `GET /atestados/{p}/custodia` | Trilha de custódia — índice/Lente de Auditoria |
| `GET /pacientes/me` | Dados do cidadão autenticado (endpoint existe; a tela usa o payload do login) |

---

## 5. Observações

1. **UX de confirmação é disciplina, não detalhe:** F5-C1 (modal pós-transferência com
   destino explícito), F5-C2 (polling com pausa em aba oculta), F5-C3 (atestado final
   acima de exame intermediário) — três decisões de produto com ticket, comentadas no
   próprio HTML.
2. **Atomização é o caminho preferido, o token único é o fallback** — e ambos são
   efêmeros por design (60 min, revogáveis, nunca persistidos).
3. **Devolução ao médico fecha o ciclo COER-2:** o cidadão é quem detecta o erro na
   ponta e devolve com motivo estruturado; o prescritor corrige e reemite como
   emissão derivada.
4. **O cidadão não agenda nem consulta chave de circulação** — a tela foi simplificada
   para o gesto único "informar CNPJ e transferir".
5. **Toasts:** `showToast` nasceu nesta tela e foi promovida ao `config.js`
   (TICKET-FALHA-SILENCIOSA-FRONTEND) — as outras telas reutilizam.
6. **Sem localStorage para sessão** (token em memória); apenas preferências de perfil e
   o bootstrap demo usam storage.

---

*Descritivo gerado por leitura direta de `cidadao.html` e dos routers `auth.py`,
`solicitacoes.py`, `tokens.py`, `prescricoes.py`, `pedidos_exame.py`, `laudos.py`
e `atestados.py`. Nenhuma linha de código foi alterada.*
