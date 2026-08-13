# Descritivo — Módulo Farmácia (Dispensador) — backend + frontend

| Campo | Valor |
|---|---|
| De | Kimi |
| Para | Fabiano Tonaco |
| Data | 2026-08-13 |
| Classe | `docs` |
| Escopo | Levantamento factual do estado em disco (branch `docs/handoff-2026-08-09`); nenhuma alteração de código |

---

## 1. Visão geral e persona

O módulo Farmácia é a **workstation de balcão** do papel **`dispensador`**,
identificado pelo **CNPJ do estabelecimento** — o mesmo papel que o módulo Laboratório
reusa no arco diagnóstico ("dispensador = clínica/lab MVP"), mas aqui no seu habitat
original: a **dispensação de medicamentos**.

É o módulo regulatório mais denso do sistema: cada baixa é **ato sanitário** com
escrituração (Portaria SVS/MS nº 344/1998), registro no ledger imutável, comprovante
**COMPRADOR × PACIENTE**, estorno com motivo estruturado e exportação **SNGPC**.
A disciplina B0–B3 (ver CLAUDE.md §5b) domina a tela: **acionabilidade e saldo vêm
prontos do backend — o cliente nunca recalcula estado.**

**Frontend:** `dispensador.html` (2 715 linhas, single-page; sessão em memória).
**Backend:** routers `dispensadores`, `dispensacoes`, `custodia` (dispensar/devolver),
`hospitalares`, `tokens`, `prescricoes`, `publico`, `prestadores` (CNES), `ia`,
`config_publico`, `demo` e `auth`.

---

## 2. Jornada na tela (frontend `dispensador.html`)

### 2.1 Painel "Chaves de acesso (demo)"
Topo da página (padrão comum, retoque de 2026-08-12). O cartão **Dispensador · CNPJ**
abre este módulo.

### 2.2 Login (linhas 353–383)
- "Acesso Farmácia": CNPJ + senha → `POST /auth/token`.
- **"Localizar Cadastro Nacional (CNES)"** pré-login (`abrirModalCNESPreLogin`).
- **Auto-login demo** (KIMI3-002): `POST /demo/login {role:"dispensador"}` quando
  `demo_mode` ativo; hidratação via `sessionStorage` para quem veio do índice.

### 2.3 Onboarding e contexto institucional (Tickets 43/45/46/60)
- **Onboarding (Ticket 45):** "Identifique seu estabelecimento" antes de dispensar —
  localizar no CNES ou "Preencher manualmente no painel".
- **Banner de risco (Ticket 46):** "⚠ Operando com contexto não verificado no CNES" +
  "Corrigir agora". O **gate leve** (`_confirmarContextoManual`) bloqueia a dispensação
  até confirmação explícita — com justificativa documentada: "um clique que morre em
  silêncio faz o balconista clicar de novo e depende só da idempotência do backend (R2)
  para não virar dispensação duplicada. A UI não deve terceirizar isso."
- **Soft guard de tipo (Ticket 60):** tipos válidos para o módulo são
  `farmacia`, `hospital`, `usf` — fora disso, banner de escopo.
- **Contexto institucional** vem de `GET /auth/me/institucional` (org_id + unidades).

### 2.4 Fila de Dispensação (T4, linhas 428–452)
- `GET /dispensadores/fila` — receitas **sob custódia ativa desta farmácia**, polling de
  **15 s** (workstation de balcão; o cidadão tem 30 s).
- **B2 §4.1:** a receita só aparece enquanto tiver ao menos um item **acionável**
  (`i.acionavel` computado no backend: saldo_efetivo > 0 e status fora dos bloqueios
  duros — **nunca recalculado no cliente**). Sem item acionável, sai da fila e fica só
  no histórico.
- Por item: nome + concentração, **selo 🔴 controlado** (R4-FRONTEND — só o controlado
  ganha selo; "ausência informa"), saldo `saldo/quantidade` com **unidade fiel à
  receita** (Eureka 2 — "1 do quê?": o número nunca aparece sem a unidade, que vem do
  item e não tem campo para trocar).
- Ações por item acionável: **✓ Dispensar** (abre o modal de lote) e **← Paciente**
  (devolução no balcão).
- Barra de relatórios no cabeçalho: **🖨️ Relatório Consolidado**, **SNGPC CSV**,
  **SNGPC PDF**, período DD/MM/AAAA (padrão: últimos 30 dias, escopo = CNPJ logado).

### 2.5 Modal de baixa (linhas 465–497)
Dispensar exige **escrituração**: quantidade (≤ saldo, com unidade pluralizada ao lado),
**lote** (obrigatório), fabricação e validade (máscara DD/MM/AAAA) →
`POST /prescricoes/{p}/itens/{id}/dispensar` com `origem_contexto`
(`cnes_verificado` × `manual`).

### 2.6 Devoluções do balcão (B2 §4.3)
- **← Paciente:** `POST /prescricoes/{p}/itens/{id}/devolver {para:"paciente"}` —
  o item volta à carteira do cidadão.
- **Devolução ao médico: a AÇÃO foi removida da UI** (fila e painel). O endpoint de
  backend (dispensador→prescritor) e os badges de estado `devolvido_prescritor`
  **permanecem** — só o disparo saiu; quem devolve ao médico hoje é o **cidadão**
  (COER-2, ver descritivo do módulo Cidadão).

### 2.7 Ciclo pós-dispensação (Fase 4)
A mensagem de sucesso carrega o `dispensacao_id` e oferece:
- **📄 Comprovante** (`GET /dispensacoes/{id}/comprovante?formato=json|pdf`): modal
  **COMPRADOR × PACIENTE** (quem retira pode não ser o titular), medicamento, lote,
  dispensador — com **carimbo inequívoco de estorno** no topo quando aplicável
  (B3 §5.B: `estorno_total` e `quantidade_restante` vêm prontos do backend; a UI
  **nunca infere** "parcial" comparando quantidades no cliente).
- **⏪ Estornar** (`POST /dispensacoes/{id}/estornar {motivo}`, 201): motivo em enum —
  `pagamento_nao_concluido`, `desistencia_paciente`, `erro_dispensacao`, `outro`.
  **Opção B (ratificada):** `desistencia_paciente` e `pagamento_nao_concluido`
  devolvem a posse ao **cidadão** dentro do próprio estorno; os demais motivos
  **retêm** na farmácia (o item volta a poder ser dispensado, saldo reposto).
  O prompt vazio não estorna — "o estorno é objeto sanitário derivado; silêncio aqui
  deixa a dúvida 'estornei ou não?' sobre um registro de ledger".

### 2.8 Histórico de Retenções da unidade
`GET /dispensadores/historico` — receitas que passaram pelo balcão (Fase 4).

### 2.9 Consultar Prescrição (linhas 499–533)
Duas portas de entrada para a mesma tela de itens:
- **Por protocolo (UUID):** `GET /public/prescricoes/{protocolo}` — consulta pública.
- **Por código de apresentação (Ticket 25):** `POST /tokens/apresentacao/resolver` —
  o código de 8 caracteres que o cidadão gerou na carteira (inclusive **atomizado**,
  Ticket 44: o token resolve **um item só**, e a farmácia vê apenas ele —
  `_renderizarItemAtomizado`).

Na tela de itens: widget de **validação CNES** (`GET /prescricoes/{p}/validacao`,
camadas; aviso destacado quando `divergente`), **Score de Confiança do Cuidado**
(Ticket 50), badges de status por item, e as ações por item acionável (dispensar com
quantidade; dev. ao paciente). **IA no balcão:** `_iaDispConsultar` consulta
`POST /ia/medicamentos/sugerir` por item (apoio não bloqueante).

### 2.10 Modalidade Hospitalar (Ticket 27)
Seletor **Farmácia/USF × 🏥 Hospitalar**. No modo hospitalar: contexto `org_id` +
`unidade_id` (obrigatórios), setor, leito e **dose unitária** (→ quantidade de doses)
→ `POST /prescricoes/{p}/itens/{id}/dispensar/hospitalar` (router `hospitalares`).

---

## 3. Mapa frontend ↔ backend

| Função JS | Endpoint | RBAC |
|---|---|---|
| `fazerLogin` | `POST /auth/token` | público |
| `_carregarContextoInstitucional` | `GET /auth/me/institucional` | autenticado |
| `carregarFila` (polling 15 s) | `GET /dispensadores/fila` | dispensador, admin |
| `carregarHistorico` | `GET /dispensadores/historico` | dispensador, admin |
| `consultarProtocolo` | `GET /public/prescricoes/{protocolo}` | público |
| `resolverToken` | `POST /tokens/apresentacao/resolver` | dispensador |
| `_carregarCnesWidget` | `GET /prescricoes/{p}/validacao` | autenticado |
| `_confirmarLoteFila` / `_dispensarAmbulatorial` | `POST /prescricoes/{p}/itens/{id}/dispensar` | dispensador |
| `_dispensarHospitalar` | `POST /prescricoes/{p}/itens/{id}/dispensar/hospitalar` (201) | dispensador, admin |
| `_devolverFila` (paciente) | `POST /prescricoes/{p}/itens/{id}/devolver` | dispensador, prescritor, admin |
| `estornarDispensacao` | `POST /dispensacoes/{id}/estornar` (201) | dispensador, admin |
| `verComprovante` / `baixarComprovantePdf` | `GET /dispensacoes/{id}/comprovante?formato=json\|pdf` | dispensador, prescritor, auditor, admin |
| `exportarSngpc('csv')` | `GET /dispensadores/relatorio.csv` (escrituração SNGPC) | dispensador |
| `exportarSngpc('pdf')` / consolidado | `GET /dispensadores/relatorio.pdf` | dispensador |
| `_iaDispConsultar` | `POST /ia/medicamentos/sugerir` | prescritor, dispensador, admin |
| modal CNES | `GET /prestadores/buscar-cnes?modulo=dispensador` · `/prestadores/buscar` | público / autenticado |
| `_autoLoginDemo` | `POST /demo/login` | público (demo_mode) |

> Toda a PII (paciente/comprador/prescritor) nos relatórios fica atrás de
> `require_role("dispensador")` — nota explícita no router.

---

## 4. Backend relacionado que a UI **não** expõe

| Endpoint | Quem consome / observação |
|---|---|
| `GET /dispensadores/busca` | Busca de estabelecimentos (outras superfícies) |
| `GET /dispensadores/fila-exames` | A mesma farmácia-role, no **Laboratório** (`clinica.html`) |
| `POST /prescricoes/{p}/itens/{id}/devolver {para:"prescritor"}` | Endpoint ativo, **sem gatilho na UI** (B2 §4.3) |
| `GET /relatorios/dispensacoes.csv\|pdf` | **Auditor/admin** — relatório sanitário de dispensações (RBAC separado do relatório operacional do balcão) |
| `GET /tokens/apresentacao/{codigo}/qr` | Cidadão (geração do QR é dele; a farmácia só resolve o código) |

---

## 5. Observações

1. **O cliente nunca computa estado.** `acionavel`, `saldo_efetivo`, `estorno_total`,
   `quantidade_restante`, validação CNES — tudo vem pronto do backend (B0/B3). O
   frontend renderiza; não infere. É a aplicação mais estrita do Contrato de Estados
   (CLAUDE.md §5b).
2. **Estorno com roteamento de custódia (Opção B):** o motivo decide para onde a posse
   vai — desistência/pagamento devolvem ao cidadão; erro de dispensação retém na
   farmácia. Foi o ponto do bug de smokes de 2026-08-12 (PR #155).
3. **Duas velocidades de polling por persona:** 15 s no balcão, 30 s na carteira — e o
   código do cidadão registra que **não portou** dois bugs conhecidos daqui (timer não
   limpo no logout; sem pausa em aba oculta). Débito técnico conhecido e documentado.
4. **Comprador ≠ paciente é cidadão de primeira classe:** o comprovante distingue quem
   retira de quem é titular — necessário para escrituração correta.
5. **Modalidade hospitalar** é o embrião do Núcleo Sanitário interno (org/unidade/setor/
   leito, dose unitária) — §7 do AGENTS.md/CLAUDE.md.
6. **Ações destrutivas sempre nomeadas:** dispensar exige contexto CNES confirmado;
   estornar exige motivo; devolver exige confirmação. Nenhum clique morre em silêncio.

---

*Descritivo gerado por leitura direta de `dispensador.html` e dos routers
`dispensadores.py`, `dispensacoes.py`, `custodia.py`, `hospitalares.py`,
`relatorios.py`, `tokens.py`, `publico.py`, `prestadores.py` e `ia.py`.
Nenhuma linha de código foi alterada.*
