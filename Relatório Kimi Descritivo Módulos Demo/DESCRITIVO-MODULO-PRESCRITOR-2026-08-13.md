# Descritivo — Módulo Prescritor — backend + frontend

| Campo | Valor |
|---|---|
| De | Kimi |
| Para | Fabiano Tonaco |
| Data | 2026-08-13 |
| Classe | `docs` |
| Escopo | Levantamento factual do estado em disco (branch `docs/handoff-2026-08-09`); nenhuma alteração de código |

---

## 1. Visão geral e persona

O módulo Prescritor é a superfície do papel **`prescritor`**, identificado pelo **CNS**
(15 dígitos). É o módulo **emissor** do sistema: é aqui que nascem os três objetos
sanitários do PicSaúde — **receita**, **pedido de exame** e **atestado** — organizados
em três submódulos numa única página, com navegação por abas.

O princípio estrutural é o da **custódia digital**: a emissão digital transfere o objeto
à carteira do cidadão ("o CPF é o PIX que faz o documento chegar à carteira dele"), com
protocolo rastreável, hash de integridade e ledger imutável. A **emissão física**
(impressão) existe como caminho terciário, sem custódia digital — fire-and-forget,
com aviso regulatório explícito na tela (Res. CFM 2.299/2021).

**Frontend:** `prescritor.html` (4 565 linhas, single-page, fetch direto ao backend,
JWT em memória — não persiste em localStorage).
**Backend:** routers `prescricoes`, `prescritor`, `pedidos_exame`, `atestados`,
`solicitacoes`, `ia`, `pacientes`, `config_publico`, `demo` e `auth`.

---

## 2. Jornada na tela (frontend `prescritor.html`)

### 2.1 Painel "Chaves de acesso (demo)"
Topo da página (TICKET-6, retoque de 2026-08-12 via `renderizarPainelChavesDemo` do
`config.js`). Clicar no cartão **Prescritor · CNS** abre este módulo.

### 2.2 Acesso (linhas 371–472)
- **Tela de acesso:** botão "Entrar com gov.br" (**visual, sem handler — placeholder**)
  **ou** CNS/e-mail + senha → `POST /auth/token` (OAuth2 form). O módulo rejeita
  login cujo `role` não seja `prescritor`/`admin` ("Utilize o módulo correto").
- **"Localizar Cadastro Nacional (CNES)"**: abre a **busca de profissional**, que usa
  a base **mock local `BASE_CNES_MOCK`** (constante JS) — diferente do módulo
  Laboratório, que consulta o backend (`/prestadores/buscar-cnes`).
- **Vinculação** (`tela-vincular`): dados de contato, registros em conselhos
  (múltiplos, adicionar/remover), endereço profissional → gera **OTP de 6 dígitos
  no cliente** (`Math.random`) e valida na `tela-validacao`; o cadastro é gravado no
  **localStorage** (`pix_saude_db_v27`). Fluxo legado local — não toca o backend.
- **Auto-login demo** (KIMI3-002): se `demo_mode` ativo e sem sessão hidratada,
  chama `POST /demo/login {role:"prescritor"}` e entra direto no dashboard, pulando
  senha/OTP. O JWT é real; o RBAC "não sabe que é demo" (§11).
- Hidratação de sessão demo via `sessionStorage` (`picsaude_demo_*`); role errado
  redireciona ao portal.

### 2.3 Dashboard (linhas 516–539)
- Cartão do profissional: nome, registros (conselhos), CNS, botão **🔄 Atualizar Painel**.
- **🔁 Solicitações de Renovação** (`carregarSolicitacoesRenovacao` →
  `GET /prescritor/solicitacoes-renovacao`): pedidos de renovação feitos pelo cidadão;
  `responderRenovacao(id, decisao)` → `POST .../responder` com `decisao`, `observacao`
  e `nova_prescricao_protocolo` (quando a renovação vira nova prescrição).
- **⚠️ Receitas Devolvidas para Correção** (`carregarCaixaDeCorrecoes`): itens com
  `status_item = devolvido_prescritor` vindos do painel backend (fonte de verdade;
  motivo vem do ledger). Botão **"Corrigir e Reemitir"** (`carregarParaEdicao`)
  pré-preenche o formulário com `tipo_emissao = "correcao"` e `origem_prescricao_id`.
- Abas de submódulos: **Receita · Exames · Atestado**.

### 2.4 Submódulo Receita (linhas 541–648)
- **Dados Clínicos do Paciente:** nome, idade, telefone, endereço completo.
- **Indicação Clínica (opcional, IA CID):** texto livre sugere CID(s); o 1º CID vai em
  `codigo_cid` (Ticket 36).
- **Prescrição Terapêutica:** N fármacos (`adicionarMedicamento`), cada card com busca
  assistida (ver §3, IA).
- **Modo de Emissão:**
  - **CPF/CNI do paciente** (obrigatório p/ digital) + botão **"Verificar Carteira"**
    (`GET /pacientes/{cpf}/carteira`, Ticket 63). Validação rígida de 11 dígitos.
  - **Primário — ICP-Brasil:** "🔐 Assinar e Emitir com Certificado Local (A1/A3)" →
    `assinatura_modo = icp_brasil_local`. Link "🪪 Meu certificado ICP-Brasil" abre o
    modal de upload do `.pfx` ao cofre (`POST /prescritor/certificado`).
  - **Secundário — gov.br (nuvem):** marcado "Em Implantação" (`gov_br_nuvem`).
  - **Terciário — Física:** "🖨️ Apenas Imprimir Físico (sem envio digital)" com aviso
    amarelo: sem protocolo, sem custódia, não atende CFM 2.299/2021
    (`imprimirDireto` → `POST /prescricoes/fisica`).
- **Emissão digital** (`emitirReceitaDigital` → `POST /prescricoes`): payload com CPF,
  itens, `indicacao_clinica`/`codigo_cid` opcionais, e **`enviar_ao_paciente` só quando
  a carteira existe** (Ticket 63/5A — paciente sem carteira não bloqueia a emissão;
  a tela de sucesso oferece o link de acesso). Suporta `tipo_emissao`:
  `nova` / `correcao` / `renovacao` (com `origem_prescricao_id`).
- **Tela de sucesso:** protocolo, badge de nível formal
  (`calcularNivelFormalFrontend`), validação CNES, status da entrega à carteira,
  bloco **"Assinar com ICP-Brasil e baixar PDF"** (PAdES — senha usada uma vez, não
  guardada), "Imprimir 2ª Via / Físico", "Nova Prescrição", "Minhas Prescrições".
  Área de impressão com receituário formatado (emitente, paciente, fármacos, tag de
  assinatura digital ou tag amarela de emissão física).

### 2.5 Submódulo Exames (Ticket 32, linhas 654–715)
- Dados do paciente (nome, CPF/CNI, prioridade rotina/urgente/urgentíssimo),
  indicação clínica com IA CID.
- **Exames Solicitados:** N itens (`adicionarExame`), cada um com **normalização
  assistida por IA** (nome padronizado + código TUSS, não bloqueante).
- Emissão: "📋 Emitir Pedido de Exame Digital" → `POST /pedidos-exame`; a chave de
  entrega é o CPF do paciente. Alternativa "🖨️ Apenas Imprimir Físico" →
  `POST /pedidos-exame/fisica`.
- Pós-emissão: `baixarPdfExame` (`GET /pedidos-exame/{p}/pdf`) e `assinarExame`
  (`POST .../pdf-assinado`).

### 2.6 Submódulo Atestado Assistido (Ticket 39 / IA Documental, linhas 722–905)
Princípio exibido na tela: **"A IA não escreve o atestado — ela garante que esteja
correto."** Campos:
- Paciente (nome, CPF), **finalidade** (trabalhista, estudantil, judicial,
  administrativo, previdenciário INSS, outro), **tipo** (comparecimento × afastamento
  — estado de UI; o backend deriva de `dias_afastamento`, §10, sem coluna `tipo`).
- Dias de afastamento (travado em 0 no tipo comparecimento), história clínica,
  CID opcional ("registrado só com anuência do paciente"), data e município
  (exigência CFM), horas (só comparecimento; o backend proíbe horas com dias>0 — NAND).
- **Registro profissional:** conselho + UF + número; as opções de conselho vêm do
  backend (`/config/public`), nunca hardcoded — o conselho define o **título** do
  documento (médico/odontológico).
- **Observação complementar:** acrescenta um parágrafo ao corpo, **nunca substitui**
  os campos estruturados (impede divergência entre documento e carteira do cidadão).
- Botão **"↗ Preencher com dados da prescrição atual"** (reuso do contexto clínico).
- Ações: **Validar atestado** (`POST /ia/documentos/atestado/validar` — IA Documental,
  resultado renderizado em `#ia-atestado-container`), **🔏 Emitir atestado digital**
  (`POST /atestados`), **🖨️ Imprimir físico** (`POST /atestados/fisica`), Limpar.
- Pós-emissão: `baixarPdfAtestado` e `assinarAtestado` (PAdES).

### 2.7 Histórico de Emissões
`renderizarHistoricoMedico` (linha 2247): lista as prescrições do painel backend com
ações por item — **Renovar** (`renovarReceita`, `tipo_emissao = "renovacao"`) e
carregar para edição/correção. Fallback para localStorage quando o backend está offline.

### 2.8 Perfil de Acesso
`tela-perfil`: endereço, contatos e registros profissionais — gravados **no
localStorage** (configuração do aparelho, não vai ao backend).

---

## 3. Camada de IA (router `ia.py` — stateless, não bloqueante)

| Função JS | Endpoint | Papel | Uso |
|---|---|---|---|
| `_consultarIa` | `POST /ia/medicamentos/sugerir` | prescritor, dispensador, admin | Sugestão farmacológica |
| `_buscarMedicamentos` | `POST /ia/medicamentos/buscar` | idem | Autocomplete multi-resultado |
| `_selecionarMedicamento` | `POST /ia/medicamentos/apresentacoes` | idem | Embalagens reais (CMED) |
| `_avaliarSemaforo` | `POST /ia/decisao/validar` | prescritor, admin | Semáforo fármaco ↔ CID (não-bloqueante, ficha explicativa) |
| `_sugerirPosologia` | `POST /ia/posologia/sugerir` | prescritor, admin | Posologia usual (não-vinculante) |
| `_consultarIaCid` | `POST /ia/cid/buscar` | prescritor, admin | Busca CID por texto (receita, exame, atestado) |
| `_consultarIaExame` | `POST /ia/exames/normalizar` | prescritor, dispensador, admin | Nome padronizado + TUSS por item |
| `validarAtestado` | `POST /ia/documentos/atestado/validar` | prescritor, admin | Validação estrutural do atestado |

Todas as consultas são por debounce, com estado de carregamento por card, e **nunca
gravam nada** — o médico decide; a IA sugere/valida.

---

## 4. Mapa frontend ↔ backend (emissão e painel)

| Função JS | Endpoint | RBAC |
|---|---|---|
| `fazerLoginDireto` | `POST /auth/token` | público (role prescritor/admin exigido na tela) |
| `_autoLoginDemo` | `POST /demo/login` | público (demo_mode) |
| `_carregarPainelBackend` | `GET /prescritor/prescricoes` (histórico + correções) | prescritor |
| `carregarSolicitacoesRenovacao` | `GET /prescritor/solicitacoes-renovacao` | prescritor |
| `responderRenovacao` | `POST /prescritor/solicitacoes-renovacao/{id}/responder` | prescritor |
| `verificarCarteiraPaciente` / `_verificarCarteiraExame` | `GET /pacientes/{cpf}/carteira` | autenticado |
| `emitirReceitaDigital` | `POST /prescricoes` (201) | prescritor |
| `imprimirDireto` | `POST /prescricoes/fisica` (201) | prescritor |
| `assinarBaixarPdf` | `POST /prescricoes/{p}/pdf-assinado` (PAdES-B) | prescritor |
| `enviarCertificado` | `POST /prescritor/certificado` (upload .pfx) | prescritor |
| `emitirPedidoExame` | `POST /pedidos-exame` (201) | prescritor |
| `imprimirPedidoFisico` | `POST /pedidos-exame/fisica` (201) | prescritor |
| `baixarPdfExame` | `GET /pedidos-exame/{p}/pdf` | prescritor, dispensador, admin |
| `assinarExame` | `POST /pedidos-exame/{p}/pdf-assinado` | prescritor |
| `validarAtestado` | `POST /ia/documentos/atestado/validar` | prescritor, admin |
| `emitirAtestado` | `POST /atestados` (201) | prescritor |
| `imprimirAtestadoFisico` | `POST /atestados/fisica` (201) | prescritor |
| `baixarPdfAtestado` | `GET /atestados/{p}/pdf` | prescritor, admin, paciente |
| `assinarAtestado` | `POST /atestados/{p}/pdf-assinado` | prescritor |
| seletor de conselhos | `GET /config/public` (catálogo de conselhos) | público |

---

## 5. Backend relacionado que a UI **não** expõe

| Endpoint | Quem consome |
|---|---|
| `POST /paciente/prescricoes/{proto}/solicitar-renovacao` | **Cidadão** pede renovação (módulo Cidadão) |
| `POST /prescricoes/{protocolo}/atomizar` | **Cidadão** atomiza a circulação — um token por item ativo |
| `GET /prescricoes/{protocolo}/documento` | Verificação documental (prescritor/admin via outras superfícies) |
| `GET /atestados/{protocolo}` · `GET /atestados/{p}/custodia` | Cidadão e índice (trilha de custódia) |
| Operações sobre o pedido de exame (coletar, resultado, agendar…) | **Laboratório** (`clinica.html`) — o prescritor só emite |
| Dispensação, devolução ao prescritor, estorno | **Farmácia** (`dispensador.html`) — origem da caixa de correções |

---

## 6. Observações

1. **Dupla fonte de dados:** backend é fonte de verdade para histórico/correções;
   `localStorage` (`pix_saude_db_v27`) é fallback offline e guarda dados que o backend
   não persiste (demografia do paciente, validade por item) — recuperados só se a
   prescrição foi emitida **deste aparelho** (match por `protocolo_backend`).
2. **CNES do prescritor é mock local** (`BASE_CNES_MOCK`), ao contrário do Laboratório,
   que já consulta `/prestadores/buscar-cnes` no backend. Divergência de maturidade
   entre módulos a registrar numa futura frente.
3. **gov.br aparece duas vezes como placeholder:** botão de login sem handler e modo de
   assinatura "Em Implantação".
4. **OTP de vinculação é client-side** (gerado por `Math.random`, exibido em DEV_MODE) —
   fluxo de demonstração, não de produção.
5. **Correção e renovação são emissões derivadas de primeira classe**: `tipo_emissao`
   + `origem_prescricao_id` preservam a genealogia no backend (o endpoint do painel já
   exclui da caixa de correções as receitas com correção-filha).
6. **Segurança:** JWT só em memória; 401 desloga, 403 de ownership **não** desloga
   (mostra a mensagem em PT do backend); acessibilidade de campos obrigatórios com
   feedback inline persistente (KIMI3-001 §10.B) sem desligar a validação nativa.

---

*Descritivo gerado por leitura direta de `prescritor.html` e dos routers
`prescritor.py`, `prescricoes.py`, `atestados.py`, `pedidos_exame.py`,
`solicitacoes.py`, `ia.py`, `pacientes.py`, `demo.py` e `config_publico.py`.
Nenhuma linha de código foi alterada.*
