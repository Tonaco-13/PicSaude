# TICKET-G4A — Cobertura do outbox + Adapter TISS (guia-301)

| Campo | Valor |
|---|---|
| **Fase** | Arco G4A — Event Publishing Layer (cierre de cobertura + 1º adapter) |
| **Classe** | **`module`** (Trab.1: cierre de cobertura) + **`adapter`** (Trab.2: TISS guia-301) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro · cc: Revisor · Conselheiro |
| **Base** | `main@f361ab8` (verificação in-loco pelo arquiteto, 2026-08-09) |
| **Estado** | ⏳ Redigido **v3** — corrige falsos gaps da v2 (re-verificação completa dos callers). Aguarda ratificação do conselheiro + `/login` do Engenheiro. |

---

## §0 Premissa corrigida (não reabrir)

**O briefing histórico afirmava:** *"G4A não existe / bloqueia TISS; o outbox escreve mas
não tem consumer."* — **FALSA**, verificada in-loco em `f361ab8`.

**A realidade:** G4A está **~90% construído e em produção**. Helper, endpoints, tabela,
auth G4B parcial e wiring em 6 routers já existem. O que falta é **fechar 1 gap de
cobertura** (custódia) e construir o **1º adapter real** (TISS) que justifica a camada existir.

> **Lição de processo (eco do V2 §1.1):** antes de declarar "backend novo" ou "gap de
> cobertura", inventariar `adapters/`, `domain/outbox.py`, `routers/eventos.py` e os helpers
> `_gravar_evento*`, e **re-verificar cada caller com janela larga** (não heurística de grep
> apertada). A v2 deste ticket declarou 2 falsos gaps (agendamento + laudo) por heurística
> curta demais; a v3 abaixo os retirou após re-verificação completa. O processo pegou o erro
> do próprio arquiteto — como já havia pegado o do conselheiro no V2.

---

## §1 Verificação in-loco — o que JÁ existe (mapa de reuse)

| Componente | Onde | Status |
|---|---|---|
| Helper `registrar_outbox()` | `backend/app/domain/outbox.py:27` | ✅ isolamento correto (falha silenciada + log) |
| `GET /eventos` (poll + cursor) | `backend/app/routers/eventos.py:41` | ✅ `org_id`/`desde`/`limite`/`objeto_tipo` |
| `POST /eventos/{id}/ack` | `backend/app/routers/eventos.py:143` | ✅ idempotente, sem DELETE |
| Auth G4B parcial (`admin` + `integrador`) | `backend/app/auth/dependencies.py:154` | ✅ `X-Api-Key` com `org_id` enforçado |
| Tabela `eventos_publicacao` | `alembic/versions/037d38d98806_baseline_schema_manual.py:587` + `4b1ce80a017d` (instance_id) | ✅ em produção |
| Diretório de adapters | `backend/app/adapters/` (`sncr_factory.py`, `sncr_interface.py`, `sncr_stub.py`) | ✅ padrão factory+interface+stub estabelecido |
| Testes | `backend/tests/test_eventos_publicacao.py`, `test_outbox_hardening.py` | ✅ existem |

### §1.1 Cobertura real por objeto — re-verificação completa dos callers (v3)

Mapeamento feito por script que lê o **bloco completo** de cada chamada (não janela fixa de
grep). Eventos da §7 da `ARQUITETURA_G4A.md`:

| Objeto | Eventos §7 previstos | Wired (re-verificado) | Veredito |
|---|---|---|---|
| `prescricao` | `prescricao_emitida`, `prescricao_impressa`, `encerrada_localmente` | 3/3 (`prescricoes.py:591/873/892`) | ✅ completo |
| `pedido_exame` | `pedido_emitido`, `pedido_coletado`, `resultado_registrado`, `pedido_cancelado`, `pedido_encerrado` | 5/5 (`pedidos_exame.py:368/874/951/1080/1166`) | ✅ completo |
| `agendamento` | `criado`, `confirmado`, `realizado`, `cancelado`, `nao_compareceu`, `remarcado` (+ criado-remarcação) | **8/8** callers passam `ag_context` (`agendamentos.py:369/483/530/571/610/666/671/697`) | ✅ **completo** *(v2 dizia "2 mudos" — erro de heurística)* |
| `laudo` | `laudo_emitido`, `laudo_assinado`, `laudo_liberado`, `ciencia_registrada`, `laudo_encerrado` | todos passam `protocolo` (`laudos.py` `_evento` condicional) | ✅ **completo** |
| `atestado` | (fora da §7) | `atestado_emitido` (`atestados.py:534`) | ✅ bônus |
| **`custodia`** | **`custodia_transferida`** | **0/1** — `_gravar_evento` (`custodia.py:171`) só chama `registrar_evento_ledger` | ❌ **GAP ÚNICO** |

> **Nota sobre eventos fora da §7:** `laudo_impresso` (`laudos.py:514`) e `laudo_criado`
> (`:431`) não passam todos `protocolo`, mas **não estão na §7** — são eventos de emissão
> física/criação sem semântica de publicação externa. Não são gap do arco; são escolha
> deliberada. Se o conselheiro quiser publicá-los, vira decisão de produto, não bug.

---

## §2 Trabalho 1 — Cierre de cobertura: `custodia_transferida` no outbox (DESPACHO-ENG-010)

**Classe:** `module` (enxerto) · **Risco:** baixo · **Sem mudança core, sem estado novo.**

### §2.1 O gap (único)

`custodia.py:_gravar_evento` (`:171`) é o helper que grava eventos de custódia. Ele **só**
delega a `registrar_evento_ledger`. O evento `custodia_transferida` — emitido no choke-point
único `transferir_posse` (`custodia.py:247`) — **nunca** chega ao `eventos_publicacao`.

O adapter TISS (Trabalho 2) precisa saber quando um item muda de mãos para compor a guia
(rastreabilidade de posse). Sem isto, a camada G4A tem um buraco no objeto mais central do
sistema (a custódia é o coração do §5a).

### §2.2 Trabalho

1. Em `custodia.py:_gravar_evento`, espelhar no outbox **quando** `tipo_evento ==
   "custodia_transferida"`, chamando `registrar_outbox` com o mesmo `instance_id`
   (mesma transação — coerência forense, padrão `agendamentos.py:198-238`).
2. `objeto_tipo` = `"custodia"`; `objeto_id` = protocolo da prescrição (resolver via
   `_get_prescricao_by_protocolo` já existente, `custodia.py:125`). `org_id`/`unidade_id`
   = `None` por ora (escopo institucional da prescrição é nullable na spec §4 da arquitetura).
3. **Invariantes:** nenhum estado novo; ledger inalterado (só adiciona derivação outbox);
   `registrar_outbox` já engole falhas silenciosamente (isolamento §2.4 G4A — falha de outbox
   nunca impacta fluxo clínico).

### §2.3 Fora de escopo (Trabalho 1)

- `org_id`/`unidade_id` populados em custódia (nullable por spec; onboarding institucional
  é G4B).
- Eventos fora da §7 (`laudo_impresso`, etc.) — decisão de produto, não deste arco.

---

## §3 Trabalho 2 — Adapter TISS guia-301 (DESPACHO-ENG-011)

**Classe:** **`adapter`** (§10 do CLAUDE.md) · **Risco:** médio · **GATE DURO:** Trabalho 1 mergeado **e provado**.

> **Classificação corrigida v2:** a v1 rotulava este trabalho como `module`. Isso estava
> **errado** — o §10 do CLAUDE.md define `adapter` como classe própria com regras duras
> (NUNCA escreve em tabela clínica / NUNCA emite evento no ledger via SQL / SEMPRE consome
> endpoints oficiais / SEMPRE tem store próprio / SEMPRE é versionado à parte). Chamar de
> `module` pularia a **revisão de contrato de interface** que a classe `adapter` exige.
> Flag do conselheiro, procedente.

### §3.0 Checklist de contrato de interface (obrigatório, classe `adapter`)

Antes de qualquer código, o adapter deve passar por esta revisão (§10):

- [ ] **Consume endpoints oficiais** — só `GET /eventos` + `POST /eventos/{id}/ack` (+ join
      read-only em tabelas clínicas para enriquecer TUSS/paciente, **nunca escrita**).
- [ ] **Não escreve em tabela clínica** — `prescricao_*`, `pedido_exame_*`, `laudo_*`,
      `*_eventos` (ledger) são intocáveis. A única escrita é `ack` em `eventos_publicacao`
      (tabela de **publicação**, não clínica).
- [ ] **Não emite evento no ledger via SQL** — o adapter só lê; quem emite é o core.
- [ ] **Store próprio** — se o adapter precisar persistir (ex.: XML gerado, hash de envio),
      tabela própria (`tiss_guias_*`), fora do schema clínico. No MVP stub, store = nada
      (retorno síncrono); registrar como decisão.
- [ ] **Observável** — logs estruturados + health check (padrão `sncr_*`).
- [ ] **Versionado independentemente** — versão TISS (4.01) explícita no contrato;
      bumping de versão = novo método, não mutação.

### §3.1 Morada e padrão (adapter, classe própria §10)

Seguir o padrão `sncr_*` já estabelecido em `backend/app/adapters/` (adapter é a classe
canônica para integração externa; o SNCR é o precedente a espelhar):

- `backend/app/adapters/tiss_factory.py` — seletor (stub vs real, como `sncr_factory`).
- `backend/app/adapters/tiss_interface.py` — contrato (`gerar_guia_301(eventos) -> bytes`).
- `backend/app/adapters/tiss_stub.py` — implementação demo/determinística (XML TISS 4.01).
- `backend/app/routers/integracoes.py` — `router = APIRouter(prefix="/integracoes", ...)`,
  com `POST /integracoes/tiss/guia-301`.

> O adapter **não** mora em `pedidos_exame.py` nem em `clinicas.py`. É domínio de integração
> externa — camada própria, coerente com §10 (*adapter NUNCA escreve em tabelas clínicas*).

### §3.2 Fluxo do adapter (read-only sobre o outbox)

```
POST /integracoes/tiss/guia-301  (role: admin | integrador c/ X-Api-Key)
   │  body: { org_id?, periodo_inicio, periodo_fim }
   ▼
1. GET interno sobre eventos_publicacao
     WHERE objeto_tipo = 'pedido_exame'
       AND tipo_evento IN ('pedido_emitido','resultado_registrado','pedido_encerrado')
       AND org_id = <do chamador>
       AND criado_em ∈ [periodo_inicio, periodo_fim]
2. Para cada evento: POST interno /eventos/{id}/ack  (marca consumido)
3. Transformação payload → XML TISS 4.01 (ans:guiaResumo, guiaConsulta/SAD/SP-SAD)
4. Retorna XML (ou PDF do stub) — nenhum INSERT/UPDATE em tabela clínica
```

**Invariantes (§10 / §2 da arquitetura):**
- **Read-only** sobre `eventos_publicacao` e tabelas clínicas (join só para enriquecer
  TUSS/paciente — nunca escreve).
- O `ack` é a única escrita, e é **no outbox** (tabela de publicação), nunca em ledger.
- Falha de transformação NÃO dá `ack` (evento volta a ficar disponível no próximo poll).
- `org_id` enforçado pela credencial (`require_eventos_access`, já existe).

### §3.3 Decisões de produto (a ratificar)

| Decisão | Detalhe |
|---|---|
| **Versão TISS** | 4.01 (vigente). Schema XML da ANS como referência de campo. |
| **Escopo MVP** | Guia de consulta + SP/SAD (procedimentos) — **não** internação/honorário. |
| **Stub determinístico** | `tiss_stub` gera XML válido para demo; o factory seleciona real quando existir credencial ANS (não existe hoje → stub é a implementação ativa). |
| **Sem e-gressão física** | O endpoint **retorna** o XML/PDF; não há POST automático pra operadora. E-gressão = arco futuro (depende de credenciamento ANS). |

### §3.4 Fora de escopo (Trabalho 2)

- E-gressão/transmissão à operadora (credenciamento ANS — bloqueio regulatório, não técnico).
- Versões TISS ≠ 4.01.
- Guia de internação/honorário.
- Validação do XML contra o XSD da ANS no gate (backlog — entra como `TODO` no stub).

---

## §4 Critérios de aceite do arco G4A

1. `custodia_transferida` aparece em `eventos_publicacao` após qualquer transferência de
   posse (prova: teste de mutação quebra se o wiring for removido).
2. **Cobertura §7 100%** — após ENG-010, **todos** os objetos da §7 (prescrição, pedido_exame,
   agendamento, laudo, custódia) publicam. Prova: teste parametrizado que, para cada evento
   da §7, gera o evento e afirma linha em `eventos_publicacao`.
3. `POST /integracoes/tiss/guia-301` retorna XML TISS 4.01 válido para um período, escopado
   por `org_id` do chamador.
4. O adapter **nunca** escreve em `prescricao_*`, `pedido_exame_*`, `laudo_*`, `*_eventos`
   (ledger). Única escrita = `ack` em `eventos_publicacao` (prova: grep de INSERT/UPDATE no
   diff do adapter — só em `eventos_publicacao` via endpoint oficial).
5. **Checklist de contrato de interface (§3.0) preenchido e auditado** — sem isto o adapter
   não é `adapter`, é `module` disfarçado, e o §10 é violado.

---

## §5 Ordem de execução (sequenciamento explícito — flag conselheiro v2)

```
FATIA A — ENG-010 (cierre de cobertura: custodia_transferida no outbox)
   │   classe `module`, enxerto, baixo risco, sem GATE externo
   │   → PR próprio → merge → PROVADO (evento de custódia confirmado no outbox em produção)
   ▼
   ══════ GATE DURO: ENG-010 mergeado E provado ══════
   ▼
FATIA B — ENG-011 (adapter TISS guia-301)
        classe `adapter`, médio risco, checklist §3.0 obrigatório
```

- **O adapter NÃO cavalga cobertura em construção no mesmo PR.** O §10 é claro: G4A tem que
  **existir** antes de qualquer adapter. "Existir" aqui = cobertura fechada, mergeada e
  provada — não "em construção no arco ao lado". É o "backend antes de frontend" aplicado a
  camadas.
- **ENG-010 e ENG-011 são PRs separados, em turnos separados.** Não abrir ENG-011 enquanto
  ENG-010 não estiver verde na main.
- **ENG-011 depende de ENG-010** porque o adapter consome `custodia_transferida` — sem ele,
  a guia TISS tem buraco de rastreabilidade de posse.
- Trab.1 é `module` (enxerto dentro do domínio existente, sem contrato externo novo). Trab.2
  é `adapter` (contrato externo, store próprio, revisão de interface — §10).

---

## §6 Fora de escopo (bloqueado / backlog)

- **G4B completo** — webhooks, retry/backoff, at-least-once, role `integrador` com
  onboarding institucional formal (a auth parcial já existe; o resto é arco próprio).
- **E-gressão TISS à operadora** — bloqueio regulatório (credenciamento ANS), não técnico.
- **Outros adapters** (HIS, LIS, HL7, e-SUS) — mesmo padrão, arcos futuros pós-TISS.
- **Validação XSD da ANS no gate** — backlog (TODO no stub).
- **Publicar eventos fora da §7** (`laudo_impresso`, `laudo_criado`) — decisão de produto,
  não deste arco.

---

## §7 Âncoras de código (verificado 2026-08-09, commit `f361ab8`)

| Item | Arquivo:linha |
|---|---|
| Helper outbox | `backend/app/domain/outbox.py:27` |
| `GET /eventos` | `backend/app/routers/eventos.py:41` |
| `POST /eventos/{id}/ack` | `backend/app/routers/eventos.py:143` |
| Auth eventos (admin + integrador) | `backend/app/auth/dependencies.py:154` |
| Tabela outbox (baseline) | `backend/alembic/versions/037d38d98806_baseline_schema_manual.py:587` |
| Tabela outbox (instance_id) | `backend/alembic/versions/4b1ce80a017d_etapa4b_add_instance_id.py:83` |
| **GAP** — `_gravar_evento` custódia (só ledger, sem outbox) | `backend/app/routers/custodia.py:171` |
| **GAP** — chamada `custodia_transferida` no choke-point | `backend/app/routers/custodia.py:247` |
| Helper agendamento (precedente de wiring ledger+outbox) | `backend/app/routers/agendamentos.py:198` |
| Helper laudo (precedente de wiring ledger+outbox) | `backend/app/routers/laudos.py:286` |
| Padrão adapter (a espelhar) | `backend/app/adapters/sncr_factory.py`, `sncr_interface.py`, `sncr_stub.py` |
| Bloqueio TISS por G4A (doc, **a revisar**) | `CLAUDE.md:731` |
| Arquitetura G4A (spec) | `docs/ARQUITETURA_G4A.md` |

---

## §8 Nota de governance — `CLAUDE.md:731` a atualizar

A linha `CLAUDE.md:731` afirma: *"Sem G4A, adapters não têm onde se conectar. Não iniciar
adapter de HIS, TISS, HL7, e-SUS..."*. **Este ticket prova que a premissa está defasada** —
G4A existe. Após o merge do ENG-010 (cierre de cobertura), esta linha deve ser **revisada**
para refletir: *"G4A ativo; adapter TISS liberado após ENG-010. E-gressão à operadora ainda
bloqueada por credenciamento ANS."* — como docs-PR separado, não neste arco.

---

## §9 Nota de honestidade processual (v2 → v3)

A **v2** deste ticket declarou **3 gaps** de cobertura (custódia + agendamento + laudo).
A re-verificação completa dos callers (script com janela de bloco inteiro, não grep de 6
linhas) mostrou que **2 eram falsos**:

- **agendamento:** os 8 callers de `_gravar_evento_agendamento` **todos** passam
  `ag_context`. A heurística de grep apertada da v2 não alcançava o argumento em chamadas
  multi-linha.
- **laudo:** os eventos da §7 **todos** passam `protocolo`. `laudo_impresso` (que não passa)
  está **fora da §7** — não é gap do arco.

Restou **1 gap real** (custódia), que é o escopo do ENG-010. Registrada como lição: âncora
de ticket envelhece e heurística de grep engana — re-verificar por bloco antes de declarar
gap. O processo pegou o erro do próprio arquiteto, como já havia pegado o do conselheiro no
V2 (§1.1) e o do conselheiro no despacho original (§0).

---

*Documento emitido pelo arquiteto. Fundamentado em verificação in-loco (`f361ab8`), não em
briefing de terceiros. Despachos derivados (ENG-010, ENG-011) em arquivos separados após
ratificação.*
