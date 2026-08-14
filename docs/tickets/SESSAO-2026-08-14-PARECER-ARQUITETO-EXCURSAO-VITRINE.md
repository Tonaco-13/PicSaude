# Sessão 2026-08-14 — Arquiteto: excursão na vitrine (3 objetos) + diagnóstico "tirar login da demo" + despachos série J

| Campo | Valor |
|---|---|
| **Arquiteto** | Z AI — redator |
| **Executor da excursão** | 3 agentes do arquiteto (HTTP puro contra `https://picsaude.com.br`, personas demo) |
| **Escopo** | Circulação E2E de receita, atestado e pedido de exames na vitrine ao vivo · diagnóstico do pedido do Fabiano (remover login da demo) · despachos J.1–J.6 |
| **Estado** | Motor aprovado na excursão; 2 bugs `core` e 1 furo `ops` despachados; login-demo diagnosticado e despachado como `module` |

---

## §1 A excursão (14:44–14:47 UTC, antes do reset das 15:00)

| Objeto | Protocolo | Ciclo percorrido | Veredito |
|---|---|---|---|
| **Receita** | `410b9c36-3518-45f8-b433-29ef0a89fb87` | emissão → custódia paciente → apresentação na farmácia → 2 itens dispensados → `dispensada` | ✅ Estados e custódia conformes ao contrato; Σ dispensada ≤ prescrito; comprovantes OK |
| **Atestado** | `bcc79a98-36a4-4718-aafa-e73196f9714e` | emissão → carteira do cidadão → PDF → validação pública neutra | ✅ Ciclo curto por natureza (sem dispensação/ciência); payload público sem dado clínico |
| **Pedido de exames** | `b1f799b6-9454-459f-9fda-55e068528e31` (+ agendamento `42c0ca91…`) | emissão → paciente transfere à clínica → agendar/confirmar/realizar → em análise → resultados | ⚠️ Ciclo funcional, mas termina em bug de máquina de estados (J.1) |

Invariantes preservados em todos os três: transições de custódia apenas pelas vias permitidas,
nenhum UPDATE/DELETE observável sobre eventos, estados coerentes com `domain/states*.py`.

## §2 Achados (triagem)

| # | Achado | Classe | Severidade | Destino |
|---|---|---|---|---|
| 1 | `derivar_status_pedido` deriva `encerrado` direto de "todos os itens em `resultado_disponivel`" — o estado `resultado_disponivel` do pedido é inalcançável; `POST /encerrar` devolve 422 circular; itens nunca chegam a `encerrado`; evento `pedido_encerrado` nunca existe | **core** (máquina de estados) | alta — apaga o momento "resultado disponível ao cidadão", coração da narrativa | **J.1** |
| 2 | Documento canônico com `integro: false`: hash de emissão usa nome normalizado MAIÚSCULO; reconstrução no GET lê `pacientes.nome` Title Case do banco — hash nunca bate; `/validacao` acusa falsa adulteração | **core** (documento canônico) | alta — pior mensagem possível em demo pública | **J.2** |
| 3 | CNES quebrado na vitrine: "Banco CNES não encontrado: `/app/app/../../data/pix_saude_demo.db`" (path mal resolvido no deploy) — score de confiança "baixo" em toda operação | **ops** | média | **J.4** |
| 4 | Coleta via `/agendamentos/{ag}/realizar` transiciona itens para `coletado` sem emitir `pedido_coletado` no ledger do pedido — trilha do objeto com buraco | core (semântica de ledger) | média | **J.5** (decisão) |
| 5 | `GET /eventos` exige admin/integrador; nenhuma persona demo acessa — o ledger é invisível na vitrine | ops (existe flag pronta) | média (narrativa) | **J.6.a** |
| 6 | Atestado: validação pública sempre `assinado: false` (assinatura bloqueada em DEMO_MODE) · token de apresentação devolve "Prescrição não encontrada" para atestado | module/docs | baixa | **J.6.b** |
| 7 | 401 isolado "Signature verification failed" com token fresco (não reproduzido) — suspeita de segredo/restart no deploy | ops | baixa (vigilância) | nota em J.4 |

Correções de percurso (sem ticket): a apresentação do paciente no balcão é rota própria
(`POST /paciente/prescricoes/{proto}/transferir-farmacia`), não o `/custodia/transferir` —
comportamento correto (regra V6), registrado aqui para o roteiro de demonstração.

## §3 Diagnóstico — "tirar login da Demo" (pedido do Fabiano)

**Sintoma relatado:** às vezes a vitrine "cai para o login" no meio da experiência.

**Causa-raiz encontrada no código — não é bug, é ciclo de vida:**

1. `JWT_ACCESS_TTL_MINUTES = 15` (`app/config.py:35`). Excursão que passa de 15 min → 401.
2. No 401, os 4 módulos mostram **"Sessão expirada. Faça login novamente."** e chamam `sair()`,
   que devolve a tela de acesso (login/OTP) — ex.: `prescritor.html:2013, 3323, 3496`;
   `cidadao.html:406` para o poll da carteira.
3. O auto-login demo (KIMI3-002 §1) existe nos 4 módulos, mas **só roda no carregamento da
   página** — não recupera sessão que expira no meio do uso.

**O que "tirar o login" significa arquiteturalmente:** o JWT/RBAC **não pode sair** (é `core`;
`/demo/login` emite JWT real e o `require_role` nem sabe que é demo — este é o design correto).
O que sai é o **atrito**: em modo demo, login vira invisível — sessão nasce sozinha, renasce
sozinha quando expira, e nenhuma tela de acesso/sessão expirada é jamais vista.

**Interferência com os bugs J.1/J.2: nenhuma.** São camadas ortogonais — J.1/J.2 são lógica de
domínio no backend (máquina de estados e documento canônico); o problema do login é ciclo de
vida de sessão no frontend. Corrigir um não toca o outro. A única intersecção é cosmética:
com sessão expirando, o visitante pode ver o 401 antes de ver qualquer bug.

**Decisão arquitetural (Z):** implementar como **re-login transparente** — ver J.3.

## §4 Despachos — série J

### J.1 (core · martelo do Fabiano) — `resultado_disponivel` inalcançável no pedido de exame

- **Arquivo:** `backend/app/domain/states_exame.py::derivar_status_pedido` (~linhas 176–181).
- **Problema:** `resultado_disponivel` consta em `_PRIORIDADE_ESTADO` mas é filtrado como
  terminal em `ativos_sem_resultado` — o loop nunca o devolve; com todos os itens em
  `resultado_disponivel`, cai no ramo "todos terminais" → `encerrado`.
- **Correção:** pedido deve repousar em `resultado_disponivel` quando todos os itens o estão;
  `encerrado` só via `POST /encerrar` (que então emite `pedido_encerrado` e promove itens a
  `encerrado`). Atualizar DDL-doc/AGENTS §7 se necessário + testes unit/integração.
- **AC:** emissão → … → resultado em N itens deixa pedido em `resultado_disponivel`;
  `/encerrar` 200; itens `encerrado`; evento `pedido_encerrado` no ledger.
- **Classificação:** `core` (máquina de estados oficial) — exige martelo do Fabiano no PR.

### J.2 (core · martelo do Fabiano) — hash do documento canônico nunca casa (caixa do nome)

- **Arquivos:** `backend/app/routers/prescricoes.py` (~255 e ~420) ×
  `backend/app/domain/documento_canonico.py::montar_documento_de_conn`.
- **Problema:** emissão serializa `normalize_nome(payload.nome_paciente)` (MAIÚSCULAS);
  reconstrução lê `pacientes.nome` (Title Case do seed) → `integro: false` universal +
  mensagem "conteúdo pode ter sido alterado após emissão".
- **Correção (mínima e canônica):** aplicar a MESMA normalização na reconstrução
  (`montar_documento_de_conn` normaliza o nome lido do banco antes de serializar).
  Verificar o mesmo round-trip em atestados e pedidos de exame (mesmo padrão de hash).
- **AC:** para receita emitida na vitrine com paciente seed: `GET /documento` →
  `integro: true`; `GET /validacao` sem alerta de adulteração.
- **Classificação:** `core` (documento canônico) — martelo do Fabiano.

### J.3 (module) — Demo sem login visível (re-login transparente)

- **Problema:** 401 após 15 min derruba para tela de acesso (§3).
- **Correção:** nos 4 módulos (`prescritor.html`, `dispensador.html`, `clinica.html`,
  `cidadao.html`), quando `cfg.demo_mode`:
  1. Interceptador único de 401 → `POST /demo/login` com o papel corrente → grava
     sessionStorage → **retry da requisição original uma vez**; só mostra erro se o retry falhar.
  2. `sair()` em demo não exibe tela de acesso (reentra ou permanece no dashboard).
  3. Poll da carteira do cidadão (`cidadao.html:406`) recupera em vez de parar.
- **NÃO fazer:** remover JWT/RBAC, alterar `auth/`, ou tocar `require_role` — isso é `core`
  e não é necessário. Frontend-only + endpoint `/demo/login` já existente.
- **AC:** navegar 20+ min contínuos nos 4 módulos sem ver "Sessão expirada" nem tela de login;
  E2E browser simulando expiração (token adulterado) + auto-recuperação.
- **Classificação:** `module`.

### J.4 (ops) — path do CNES quebrado no deploy + vigilância JWT

- **Problema:** checagens CNES buscam `/app/app/../../data/pix_saude_demo.db` — resolução de
  path duplicada (`app/app`) no deploy; score de confiança "baixo" em toda a vitrine.
- **Correção:** resolver o path do banco CNES uma única vez (config), sem `../../`; conferir
  no ambiente Render/planilha de deploy qual variável aponta o SQLite demo.
- **Vigilância (item §2.7):** 401 "Signature verification failed" isolado com token fresco —
  verificar no log do deploy se há restart com `PICSAUDE_JWT_SECRET` gerado por boot (se for
  o caso, fixar o secret no ambiente).
- **AC:** operação na vitrine exibe verificação CNES OK (score alto); sem 401 de assinatura
  nos logs por 24h.
- **Classificação:** `ops`.

### J.5 (core · decisão do Fabiano) — coleta invisível no ledger do pedido

- **Problema:** `/agendamentos/{ag}/realizar` transiciona itens para `coletado` e emite
  apenas `agendamento_realizado` (ledger do agendamento) — o ledger do **pedido** não registra
  a coleta.
- **Recomendação do arquiteto:** emitir `pedido_coletado` no ledger do pedido dentro da
  transição (mantém a trilha do objeto sanitário completa — princípio do NUCLEO_SANITARIO).
  Alternativa aceitável: documentar como simplificação MVP no AGENTS §7 (nota já existe para
  `realizado → coletado`).
- **Classificação:** `core` (semântica de ledger) — martelo do Fabiano entre as duas opções.

### J.6 (module/ops · narrativa demo, não bloqueia)

- **a.** Ledger visível na vitrine: ligar `PICSAUDE_DEMO_ADMIN=true` no deploy (o
  `/demo/login` já expõe persona admin com essa flag — `_papeis_demo_disponiveis`) e avaliar
  no guia onde o visitante vê os eventos. Zero código.
- **b.** Atestado: guia da demo explica `assinado: false` (assinatura ICP-Brasil é
  deliberadamente bloqueada em DEMO_MODE); mensagem do token para protocolo de atestado
  distingue tipo de objeto (404 "Prescrição não encontrada" → "objeto não suportado").
- **Classificação:** module/docs.

## §5 Ordem recomendada

1. **J.2** primeiro (uma linha de domínio, desbloqueia a narrativa de integridade).
2. **J.1** (core, com testes — é o coração do "resultado disponível ao cidadão").
3. **J.3** (module, frontend-only — a experiência "sem login" que o Fabiano pediu).
4. **J.4** em paralelo (ops de deploy).
5. **J.5/J.6** após os acima — decisão de martelo e polimento.

J.1 e J.2 em PR único separado (`core`), martelo do Fabiano; J.3/J.6 em PR `module`; J.4 direto
na config de deploy (sem PR de código, se for só env/path).

---

*Parecer redigido pelo arquiteto (Z AI) em 2026-08-14, a partir da excursão de 3 agentes na
vitrine `picsaude.com.br` e verificação no código. **Martelos do Fabiano dados em 14/08:**
J.1, J.2 e J.5 aprovados para correção (J.5 emitindo `pedido_coletado`); J.3, J.4 e J.6
confirmados. Despacho ao engenheiro: `DESPACHO-ENG-010-SERIE-J-EXCURSAO-VITRINE.md`.*
