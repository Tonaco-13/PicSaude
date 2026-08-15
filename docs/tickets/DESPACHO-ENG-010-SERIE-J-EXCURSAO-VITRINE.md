# DESPACHO ENG-010 — Série J: correções da excursão na vitrine + login invisível na demo

| Campo | Valor |
|---|---|
| **Despacho** | ENG-010 (série J — 6 tickets originados da excursão de 14/08 na vitrine) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Fabiano (martelos dados, abaixo) |
| **Data** | 2026-08-14 |
| **Origem** | `SESSAO-2026-08-14-PARECER-ARQUITETO-EXCURSAO-VITRINE.md` (§2 triagem · §4 despachos J.1–J.6) |
| **Base** | `main` em `c85442f` (pós-merge #159/#160) |
| **Classes** | J.1/J.2/J.5 = **`core`** (martelados) · J.3 = `module` · J.4 = `ops` · J.6 = `module`/`ops` |

---

## §1 Contexto

Excursão de 3 agentes do arquiteto na vitrine (`picsaude.com.br`, 14/08 ~14:44–14:47 UTC) circulou
receita, atestado e pedido de exames pelo ciclo completo. Motor aprovado; achados triados no
parecer de origem. O Fabiano decidiu ainda: **demo sem login visível** (re-login transparente).

## §2 Martelos do Fabiano (2026-08-14) — decisão fechada

| Ticket | Decisão |
|---|---|
| **J.1** (`core`) | **APROVADO para correção.** Máquina de estados do pedido deve alcançar `resultado_disponivel`; resolver o 422 circular do `/encerrar`. |
| **J.2** (`core`) | **APROVADO para correção.** Hash do documento canônico deve tratar corretamente a caixa do nome do paciente. |
| **J.3** (`module`) | Mantém decisão: demo com login invisível, via re-login transparente no frontend (interceptador de 401 → re-emite `/demo/login`). |
| **J.4** (`ops`) | Mantém decisão: corrigir path do CNES no deploy + vigilância do 401 de assinatura. |
| **J.5** (`core`) | **APROVADO seguindo recomendação do arquiteto:** emitir `pedido_coletado` no ledger do pedido na coleta via agendamento. |
| **J.6** | Narrativa/ativação: ligar `PICSAUDE_DEMO_ADMIN=true` (ledger visível) + guia do `assinado: false`. |

## §3 Instrução de execução — LER PRIMEIRO

> **Regra do Fabiano (verbatim):** *"Na implementação, o engenheiro deve avaliar os fixes
> propostos. Se discordar de algum ponto técnico, não segue em frente — retorna o problema
> ao arquiteto para reavaliação antes de qualquer alteração no código."*
>
> Ou seja: os fixes abaixo são propostas do arquiteto com martelo do Fabiano sobre a
> **decisão**; a **forma técnica** continua sujeita ao seu julgamento. Discordou → para,
> escreve a discordância com evidência (código/teste) e devolve ao arquiteto. Nada de
> improviso no `core`.

## §4 O que fazer (detalhe completo no parecer de origem, §4)

### J.1 — `core`: `resultado_disponivel` inalcançável no pedido
`backend/app/domain/states_exame.py::derivar_status_pedido` (~L176–181): todos os itens em
`resultado_disponivel` caem no ramo "todos terminais" → `encerrado`. Corrigir para o pedido
repousar em `resultado_disponivel`; `encerrado` apenas via `POST /pedidos-exame/{proto}/encerrar`
(emite `pedido_encerrado`, itens → `encerrado`). AC: emissão → … → resultado em N itens deixa
pedido em `resultado_disponivel`; `/encerrar` 200; itens `encerrado`; evento no ledger.
Atualizar AGENTS §7 / DDL-doc se houver divergência textual.

### J.2 — `core`: hash do documento canônico (caixa do nome)
Emissão serializa `normalize_nome(payload.nome_paciente)` (MAIÚSCULAS) —
`prescricoes.py` ~L255/L420; reconstrução lê `pacientes.nome` Title Case —
`documento_canonico.py::montar_documento_de_conn`. **Correção mínima:** aplicar a mesma
normalização na reconstrução. **Verificar o round-trip análogo em atestados e pedidos de exame**
(mesmo padrão de hash). AC: receita emitida na vitrine com paciente seed → `GET /documento`
`integro: true`; `GET /validacao` sem alerta de adulteração.

### J.5 — `core`: `pedido_coletado` no ledger do pedido
`/agendamentos/{ag}/realizar` transiciona itens para `coletado` sem evento no ledger do
pedido (só `agendamento_realizado` no do agendamento). Emitir `pedido_coletado` por item na
mesma transação. AC: realizar agendamento gera `agendamento_realizado` **e** `pedido_coletado`
(no ledger do pedido).

### J.3 — `module`: login invisível na demo
Nos 4 módulos (`prescritor.html`, `dispensador.html`, `clinica.html`, `cidadao.html`), quando
`cfg.demo_mode`: interceptador único de 401 → `POST /demo/login` com o papel corrente → grava
sessionStorage → **retry da requisição original uma vez**; `sair()` em demo não exibe tela de
acesso; poll da carteira (`cidadao.html:406`) recupera em vez de parar. **NÃO fazer:** remover
JWT/RBAC, alterar `auth/` ou `require_role` (isso é `core` e desnecessário). Aproveitar para
tratar os 403-como-sessão-expirada remanescentes (`clinica.html:1263, 1359, 1652, 1681, 1700,
1725, 2383`). AC: 20+ min contínuos nos 4 módulos sem "Sessão expirada" nem tela de login;
E2E browser simulando expiração + auto-recuperação.

### J.4 — `ops`: CNES no deploy + vigilância JWT
Checagens CNES buscam `/app/app/../../data/pix_saude_demo.db` — path duplicado (`app/app`) no
deploy; score de confiança "baixo" na vitrine inteira. Resolver o path uma única vez (config),
sem `../../`. Vigilância: 401 isolado "Signature verification failed" com token fresco (14/08,
não reproduzido) — conferir no log do deploy se `PICSAUDE_JWT_SECRET` é gerado por boot (se sim,
fixar no ambiente). Se a correção for só env/config, pode ir sem PR de código — documentar no
relatório onde foi alterado.

### J.6 — `module`/`ops`: narrativa
(a) Ligar `PICSAUDE_DEMO_ADMIN=true` no deploy (o `/demo/login` já expõe persona admin com essa
flag — zero código) e sinalizar no guia onde o visitante vê os eventos. (b) Guia da demo explica
`assinado: false` (assinatura ICP-Brasil bloqueada em DEMO_MODE); corrigir mensagem do token para
protocolo de atestado ("Prescrição não encontrada" → distinguir tipo de objeto).

## §5 Estratégia de PR e gates

1. **PR 1 (`core`): J.1 + J.2 + J.5** — branch `fix/serie-j-core`. Merge aguarda **martelo do
   Fabiano no PR** (padrão da casa para `core`; os martelos acima autorizam a implementação,
   não o merge).
2. **PR 2 (`module`): J.3 + J.6.b** — branch `fix/serie-j-demo-ux`, base no PR 1.
3. **J.4 + J.6.a:** config de deploy, direto (documentar no relatório).
4. Gates obrigatórios verdes antes de reportar: unit + integração + browser completos. Nos
   tickets `core`, incluir testes de regressão específicos (AC de J.1/J.2/J.5).
5. Ordem sugerida: J.2 → J.1 (uma linha de domínio primeiro, depois a máquina de estados) →
   J.5 → J.3 → J.4/J.6. J.4 pode correr em paralelo.

## §6 Registro e limites

- Relatório em `docs/tickets/SESSAO-2026-08-14-TICKET-SERIE-J-*.md` (padrão da casa), com
  evidências (testes, prints de resposta da API).
- **Não commita sem ordem** (regra contínua). Ao terminar os PRs, reporta e aguarda.
- Escalonamento: §3 acima — discordância técnica em qualquer ticket → para e devolve ao arquiteto.

---

*Despacho emitido pelo arquiteto (Z) em 2026-08-14, na sequência do parecer da excursão e dos
martelos do Fabiano (mesma data).*
