# Descritivo — Módulo Laboratório (Clínica) — backend + frontend

| Campo | Valor |
|---|---|
| De | Kimi |
| Para | Fabiano Tonaco |
| Data | 2026-08-13 |
| Classe | `docs` |
| Escopo | Levantamento factual do estado em disco (branch `docs/handoff-2026-08-09`); nenhuma alteração de código |

> **Nota:** este descritivo foi solicitado no lugar da remoção da seção
> "🔬 Circulação Diagnóstica" do `clinica.html`, ação **cancelada** pelo Fabiano em
> 2026-08-13 ("vamos cancelar a ação por enquanto"). A seção permanece no módulo.

---

## 1. Visão geral e persona

O módulo Laboratório é a superfície do papel **`dispensador`** no arco diagnóstico
(exames), identificado pelo **CNPJ da unidade** — mesma identidade usada pela farmácia
no arco de dispensação. O laboratório não cria pedidos: ele **recebe** pedidos de exame
que o cidadão transfere à unidade ("o exame chega como um pix", metáfora do GAP-4),
e sobre eles executa o ciclo operacional:

```
fila → busca do pedido → agendamento → coleta (por item) → resultado (por item)
                                 ↘ circulação diagnóstica (delegação do cidadão)
```

Escopo institucional: todo dado é filtrado por `org_id + unidade_id` (§6b do CLAUDE.md);
o JWT do dispensador carrega o CNPJ da unidade e o backend só devolve o que pertence a ela.

**Frontend:** `clinica.html` (2 577 linhas, single-page, fetch direto ao backend).
**Backend:** FastAPI — routers `dispensadores`, `pedidos_exame`, `agendamentos`,
`circulacao_diagnostica`, `clinicas`, `prestadores` (CNES) e `auth`.

---

## 2. Jornada na tela (frontend `clinica.html`)

### 2.1 Painel "Chaves de acesso (demo)"
Topo da página, compartilhado com os demais módulos (`renderizarPainelChavesDemo` do
`config.js` — retoque de 2026-08-12). Botões **📋 Copiar** por perfil. Clicar no cartão
**Clínica/Laboratório · CNPJ** abre direto este módulo.

### 2.2 Login (linhas 547–584)
- Formulário "Acesso Laboratório": CNPJ da unidade + senha → `POST /auth/token`.
- Botão **"Localizar Cadastro Nacional (CNES)"** antes do login
  (`abrirModalCNESPreLogin`) — cadastro institucional sem sessão.

### 2.3 Onboarding institucional (Ticket 45, linhas 587–605)
- Banner obrigatório: identificar o estabelecimento no **CNES** antes de agendar/coletar.
- Opção de escape: "Preencher manualmente no painel" (`_pularOnboarding`).
- Contexto carregado por `GET /auth/me/institucional` (`_carregarContextoInstitucional`).

### 2.4 Dashboard pós-login (linhas 608–702)
Header: tag "Módulo Laboratório", nome do estabelecimento, botões
**🔬 Relatório (CSV)**, **🔬 Relatório (PDF)**, **💰 Faturamento**, "← Portal", "Sair".

Blocos, em ordem:

| Bloco | O que faz |
|---|---|
| **Banner de risco CNES** (Ticket 46) | Se contexto não verificado: alerta + "Corrigir agora" |
| **Fila de Exames** (GAP-4) | Pedidos sob custódia da unidade; contador, ↻ Atualizar, **polling de 30 s** (`_iniciarPollingFila`) |
| **Buscar Pedido de Exame** | Input de protocolo → consulta direta |
| **Contexto Institucional** (Tickets 43+45) | Dados do estabelecimento + botão localizar CNES |
| **Resultado** | 3 cards: Pedido de Exame · Agendamento · Exames Solicitados |
| **Circulação Diagnóstica** (Ticket 57) | Busca por chave hex (12 chars) + operação completa da circulação |

### 2.5 Fila e abertura do pedido
- `carregarFilaExames` → `GET /dispensadores/fila-exames` → `_renderizarFilaExames`.
- `abrirPedidoDaFila(protocolo)`: preenche `#busca-protocolo` e chama `buscarPedido()` —
  a fila é o atalho para a busca.

### 2.6 Card "Pedido de Exame" (leitura)
`renderizarPedido` (linhas 1292–1346): protocolo, status, paciente (nome/CPF),
prescritor (nome/CNS), emissão, prioridade, validade, indicação clínica + CID,
e o **widget de confiança CNES** (`_renderizarValidacaoCNES`, graceful — null não render).
**Sem botões de ação** no card: o laboratório não cancela/encerra pedido pela UI.

### 2.7 Card "Agendamento"
- `carregarAgendamentos` → `GET /pedidos-exame/{p}/agendamentos`.
- Ações expostas: **criar** (`criarAgendamento` → `POST /agendamentos`),
  **confirmar** (`confirmarAgendamento`), **cancelar** (`cancelarAgendamento`),
  **realizar** (`realizarAgendamento`).
- **Não expõe** remarcar nem "não compareceu" — coerente com o RBAC (ver §3).

### 2.8 Card "Exames Solicitados" (por item)
`renderizarItens` (linhas 1620–1663): nome do exame, quantidade, **TUSS/SIGTAP**,
badge de status e ação condicional:

| `status_item` | Ação na UI |
|---|---|
| `agendado` | Botão **Registrar coleta** → `POST .../itens/{id}/coletar` |
| `coletado` | Botão **Registrar resultado** → `POST .../itens/{id}/resultado` (KIMI3-007; prompt de resumo, ex. "Glicemia 92 mg/dL") |
| `em_analise` | ⏳ "Em análise — resultado em breve" |
| `resultado_disponivel` | ✓ "Resultado disponível" |

Após resultado, `recarregarPedido()` — o estado autoritativo vem sempre do backend.

### 2.9 Circulação Diagnóstica (Ticket 57)
Busca por **chave de circulação** (hex 12, ex. `A3F1C2B4E5D6`) → `GET /circulacao/{chave}`
→ `renderizarCirculacao` (paciente, prescritor, itens, validade, proposta, badges por
status via `_STATUS_CIRC_LABEL` + `_TERMINAIS_CIRC`).

Ações conforme o estado:

| Ação JS | Endpoint | Efeito |
|---|---|---|
| `enviarProposta` | `POST /circulacao/{chave}/proposta` | Lab propõe data/local |
| `realizarCirculacao` | `POST /circulacao/{chave}/realizar` | Terminal — circulação cumprida |
| `desmarcarCirculacao` | `POST /circulacao/{chave}/desmarcar` | Desmarcação |
| `enviarRemarcacao` | `POST /circulacao/{chave}/remarcar` | Gera **circulação derivada** (nova chave) |

> A mesma chave também é consultável pela **Lente de Auditoria** no índice
> (`index.html`), que exibe a trilha pública do objeto sanitário.

### 2.10 Relatórios e faturamento (header)
- `abrirRelatorioExames(fmt)` → `GET /clinicas/relatorio.csv|pdf`
- `abrirFaturamento(fmt)` → `GET /clinicas/faturamento.csv|pdf`
- Download via `_baixarArquivoClinica`/`_baixarBlob`.

### 2.11 Modal CNES
`/prestadores/buscar-cnes?modulo=clinica&q=` (pré-login) e `/prestadores/buscar?q=`
(logado): busca, seleção e cadastro manual do estabelecimento.

### 2.12 Robustez da UI
`esc()` anti-XSS em toda interpolação; `_extrairMsgErro` para `detail` do FastAPI;
`handleUnauthorized` (401/403 → volta ao login); máscaras e formatadores de data.

---

## 3. Mapa frontend ↔ backend (com RBAC)

| Função JS (`clinica.html`) | Endpoint | RBAC |
|---|---|---|
| `fazerLogin` | `POST /auth/token` | público |
| `_carregarContextoInstitucional` | `GET /auth/me/institucional` | autenticado |
| `carregarFilaExames` | `GET /dispensadores/fila-exames` (`?status=`, `?cnpj=` p/ admin) | dispensador, admin |
| `buscarPedido` | `GET /pedidos-exame/{protocolo}` | dispensador (custódia), prescritor, paciente, admin |
| `carregarAgendamentos` | `GET /pedidos-exame/{p}/agendamentos` | prescritor, paciente, admin, **dispensador** |
| `criarAgendamento` | `POST /agendamentos` | prescritor, paciente, admin, **dispensador** |
| `confirmarAgendamento` | `POST /agendamentos/{id}/confirmar` | prescritor, admin, **dispensador** |
| `realizarAgendamento` | `POST /agendamentos/{id}/realizar` | prescritor, admin, **dispensador** |
| `cancelarAgendamento` | `POST /agendamentos/{id}/cancelar` | prescritor, paciente, admin, **dispensador** |
| `registrarColeta` | `POST /pedidos-exame/{p}/itens/{id}/coletar` (201) | dispensador, admin |
| `registrarResultado` | `POST /pedidos-exame/{p}/itens/{id}/resultado` (201) | dispensador (ENG-007), admin |
| `buscarCirculacao` | `GET /circulacao/{chave}` | dispensador, prescritor, paciente, admin |
| `enviarProposta` | `POST /circulacao/{chave}/proposta` | dispensador, admin |
| `realizarCirculacao` | `POST /circulacao/{chave}/realizar` | dispensador, admin |
| `desmarcarCirculacao` | `POST /circulacao/{chave}/desmarcar` | paciente, dispensador, admin |
| `enviarRemarcacao` | `POST /circulacao/{chave}/remarcar` | dispensador, admin |
| `abrirRelatorioExames` | `GET /clinicas/relatorio.csv\|pdf` | dispensador |
| `abrirFaturamento` | `GET /clinicas/faturamento.csv\|pdf` | dispensador |
| modal CNES | `GET /prestadores/buscar-cnes` · `GET /prestadores/buscar` | público / autenticado |

> No router de agendamentos, o comentário do próprio código fixa a convenção:
> **"dispensador = clínica/lab MVP"** — o papel farmacêutico é reutilizado para a
> unidade diagnóstica enquanto não existe papel próprio de laboratório.

---

## 4. Backend relacionado que a UI **não** expõe

Endpoints do mesmo domínio que existem no backend mas **não têm chamada no `clinica.html`**:

| Endpoint | Quem consome / por que não está na tela |
|---|---|
| `POST /pedidos-exame` · `POST /pedidos-exame/fisica` | **Prescritor** cria o pedido (módulo Prescritor) |
| `POST /pedidos-exame/{p}/transferir-laboratorio` | **Cidadão** transfere a custódia ao lab ("pix") |
| `POST /pedidos-exame/{p}/cancelar` · `.../encerrar` | Prescritor/cidadão; lab só opera, não extingue |
| `GET /pedidos-exame/{p}/pdf` · `POST .../pdf-assinado` · `GET .../qr` | Emissão/verificação documental — prescritor e índice |
| `GET /pedidos-exame/{p}/custodia` | Trilha de custódia (usada por outras superfícies) |
| `POST /pedidos-exame/{p}/agendar` (atalho no pedido) | Equivalente ao `POST /agendamentos` |
| `POST /agendamentos/{id}/remarcar` · `.../nao-compareceu` | RBAC **exclui dispensador** — só prescritor/paciente/admin |
| `POST /pedidos-exame/{p}/circulacao` (criar) | **Cidadão/admin** cria a circulação; o lab só opera sobre ela |
| `POST /circulacao/{chave}/confirmar` | **Cidadão/admin** confirma a proposta do lab |
| **`laudos.py`** inteiro (criar/física, assinar, liberar, ciência-paciente/prescritor, encerrar, cancelar) | Arco de laudos existe no backend; **emissão de laudo pela UI do laboratório é próxima fase** |

A circulação persiste trilha no ledger imutável `circulacao_diagnostica_eventos`
(mesma disciplina de imutabilidade do ledger de custódia — §1 do CLAUDE.md).

---

## 5. Observações

1. **Circulação Diagnóstica segue no módulo.** A remoção pedida em 2026-08-13 foi
   cancelada na sequência; a seção (linhas 685–699 + funções JS) está intacta.
2. **Dois caminhos para a mesma chave:** a busca interna do módulo (operação: proposta,
   realizar, desmarcar, remarcar) e a **Lente de Auditoria** do índice (leitura pública
   da trilha). Se um dia a seção sair do `clinica.html`, a Lente já cobre a consulta —
   mas não as ações operacionais, que são exclusivas do lab autenticado.
3. **Identidade dupla do papel `dispensador`:** farmácia e laboratório dividem o mesmo
   role. O `?modulo=clinica` na busca CNES e o escopo por CNPJ da unidade são o que
   diferencia as superfícies hoje.
4. **Registro de resultado é mínimo propositalmente** (prompt de resumo livre); o laudo
   estruturado (`laudos.py`) ainda não tem tela.
5. **Polling de 30 s** na fila é o único comportamento "vivo" da página; todo o resto é
   dirigido por ação do operador.

---

*Descritivo gerado por leitura direta de `clinica.html` e dos routers
`dispensadores.py`, `pedidos_exame.py`, `agendamentos.py`,
`circulacao_diagnostica.py`, `clinicas.py`, `laudos.py` e `prestadores.py`.
Nenhuma linha de código foi alterada.*
