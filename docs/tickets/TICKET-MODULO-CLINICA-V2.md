# TICKET-MODULO-CLINICA-V2 — Módulo Clínica/Laboratório: visão R1–R4

| Campo | Valor |
|---|---|
| **Fase** | V2 — arco regulatório do módulo Clínica/Laboratório (decidido 2026-08-07) |
| **Classe** | `module` (R3/R4 backend novo) + enxerto RBAC mínimo (R1) + UI (KIMI3-007) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (R1/R3/R4 backend) · Kimi 3 (UI) · cc: Revisor · Conselheiro |
| **Origem** | Insumos do conselheiro (regime de prova, `main@3162af9`) + verificação in-loco do arquiteto |
| **Pré-requisito (GATE DURO)** | `main` atual (`3162af9`). Sem dependência de G4A (R4 é read-only). |
| **Estado** | ⏳ Redigido. Despachos derivados pendentes de execução. |

---

## §0 Decisões de produto ratificadas (não reabrir)

1. **Faturamento (R4) = relatório interno** — projeção **read-only** do ledger de exames
   (`pedido_exame_eventos`), no espelho do SNGPC do dispensador. **Não** é guia TISS; **não**
   cria estado novo; **não** escreve no ledger nem move custódia.
2. **Aviso ao paciente (R2) = polling por estado**, não push/outbox. Coerente com F5-C2 (carteira
   do cidadão que consulta `GET /pedidos-exame/{proto}`). Sem infra de notificação user-facing.
3. **Guia TISS (adapter externo) = bloqueada por G4A** — fora de escopo V2. `CLAUDE.md:731`:
   *"Sem G4A, adapters não têm onde se conectar."*
4. **Role `dispensador` = proxy da clínica/lab** (comentários `pedidos_exame.py:646`, `:815`:
   *"dispensador = clínica/lab (MVP, futuro: prestador)"*). A distinção clínica-vs-farmácia hoje é
   por **contexto de dados** (exames vs dispensações), não por role.

---

## §1 Contexto (verificado em `3162af9`, grep `--exclude-dir=__pycache__`)

O módulo Clínica/Laboratório (`clinica.html`) já opera o ciclo de coleta: login por CNPJ,
busca de pedido, agendamento, coleta de itens, circulação diagnóstica (PIX-style). O arco V2
fecha 4 recursos pendentes:

- **R1** — Realizar/coletar/registrar resultado do exame.
- **R2** — Agendar com aviso ao paciente (via estado, não push).
- **R3** — Relatório de exames do próprio prestador (CSV/PDF).
- **R4** — Faturamento (projeção interna do ledger).

### §1.1 Insumos do conselheiro vs. verificação in-loco — divergências resolvidas

O conselheiro forneceu insumos em "regime de prova". O arquiteto verificou cada um diretamente no
código. **Duas premissas do briefing inicial do arquiteto se mostraram falsas** e foram corrigidas
antes da redação (registro de processo abaixo):

| Premissa (briefing inicial) | Veredito in-loco | Prova |
|---|---|---|
| "Gap 1 (ownership por CNPJ) é um martelo a construir, caminho crítico" | ❌ **FALSA** — já existe e está wired | `_assert_dispensador_dono_pedido` (`pedidos_exame.py:594-616`); wired em `get_pedido_exame:656-657` e `coletar_item_exame:835-836` |
| "`/realizar` não existe (R1 é majoritariamente backend novo)" | ❌ **FALSA** — existe em `agendamentos.py` | `realizar_agendamento` (`agendamentos.py:493-496`), aceita `dispensador` |
| "R3 não tem endpoint; precedentes em `dispensadores.py:452/483`" | ✅ CONFIRMADO | inventário dos 12 routes de `pedidos_exame.py`; nenhum relatório agregado |
| "R2 sem infra de notificação" | ✅ CONFIRMADO (com nuance) | `outbox.py` existe mas é **publicação de eventos G4A**, não user-facing; sem dispatcher |
| "G4A bloqueia TISS" | ✅ CONFIRMADO | `CLAUDE.md:731` |

> **Nota de processo:** o conselheiro estava **correto** no ponto 5 do parecer ("coletar/realizar
> aceitam dispensador"). O erro foi do arquiteto, que na primeira varredura procurou `/realizar`
> apenas em `pedidos_exame.py` e concluiu pela inexistência. **Lição:** antes de declarar "backend
> novo", inventariar os routers correlatos (`agendamentos.py`, `circulacao_diagnostica.py`).

---

## §2 Estado atual do backend de exames (mapa de reuse)

| Recurso | Onde está | Status |
|---|---|---|
| Coletar item | `POST /pedidos-exame/{proto}/itens/{id}/coletar` (`pedidos_exame.py:811`) | ✅ aceita `dispensador`, ownership wired |
| Realizar agendamento | `POST /agendamentos/{proto}/realizar` (`agendamentos.py:493`) | ✅ aceita `dispensador`; MVP: realizado→coletado |
| Registrar resultado | `POST /pedidos-exame/{proto}/itens/{id}/resultado` (`pedidos_exame.py:974`) | ⚠️ **exclui `dispensador`** (`:979`: `require_role("prescritor","admin")`) |
| Ownership por CNPJ | `_assert_dispensador_dono_pedido` (`pedidos_exame.py:594`) | ✅ existe, reusável |
| Relatório (exames) | — | ❌ não existe |
| Ledger de exames | `pedido_exame_eventos` (`ledger.py:77-84`) | ✅ disponível para projeção read-only |

---

## §3 R1 — Realizar / Coletar / Registrar resultado

**Estado:** realizar e coletar **prontos** (endpoints aceitam `dispensador`). O único gap de backend
é permitir que o `dispensador` **registre o resultado** do exame que ele próprio realizou.

### §3.1 Gap real (estreito)

`registrar_resultado_item` (`pedidos_exame.py:974-979`) exclui `dispensador`:

```python
usuario=Depends(require_role("prescritor", "admin")),  # :979
```

Comentário `:992-993`: *"só o prescritor dono registra resultado; admin bypassa. Conjunto de papéis
inalterado (§4.4/§8.3: sem dispensador aqui)."*

A guarda de ownership que o `dispensador` precisaria ali **já existe** (`_assert_dispensador_dono_pedido`),
basta ser wireada no corpo — espelhando `coletar_item_exame:835-836`.

### §3.2 Trabalho de backend (DESPACHO-ENG-007)

1. Adicionar `"dispensador"` ao `require_role(...)` em `:979`.
2. No corpo, ramificar: se `papel == "dispensador"`, chamar
   `_assert_dispensador_dono_pedido(conn, pedido["id"], ident)` (igual a `:835-836`).
3. Critério de aceite: dispensador **não-dono** leva 403 (`nao_e_dono_do_pedido_exame`);
   dispensador **dono** registra normalmente; prescritor/admin inalterados.

**Invariantes:** nenhum estado novo; ledger escreve `pedido_em_analise` + `resultado_registrado`
como hoje (`:1039`, `:1069`); `_recalcular_e_atualizar_status_pedido` (`:627`) continua derivando.

---

## §4 R2 — Agendar com aviso ao paciente

**Estado:** backend de agendamento existe (`POST /agendamentos/{proto}/...`). O "aviso" **não** é
push — é **mudança de estado visível por polling** na carteira do cidadão (padrão F5-C2).

### §4.1 Trabalho (sem backend novo — entra no despacho KIMI3-007)

- Confirmar que `GET /pedidos-exame/{proto}` (já acessível ao paciente via `cidadao.html`) expõe o
  status `agendado` com `data_agendamento` — se sim, o aviso é puramente de UI no lado do cidadão.
- Sem escrita no ledger além do `pedido_agendado` (`:787`) que já existe.

---

## §5 R3 — Relatório de exames (CSV/PDF)

**Estado:** não existe. Precedente canônico: `GET /dispensadores/relatorio.{csv,pdf}`
(`dispensadores.py:452/483`), escopado por CNPJ do próprio prestador.

### §5.1 Decisão de morada

O router `dispensadores.py` (prefix `/dispensadores`) é **específico de farmácia/SNGPC**. A
clínica/lab compartilha o role `dispensador` mas tem **contexto de dados de exames**. Logo o
endpoint de relatório de exames **não** mora em `dispensadores.py`. Opções:

- **Opção A (recomendada):** novo router leve `/clinicas` (`backend/app/routers/clinicas.py`),
  prefix `/clinicas`, com `GET /clinicas/relatorio.csv` e `/clinicas/relatorio.pdf`. Isola o
  domínio clínico-laboratorial de farmácia; prepara o solo para futuras rotas de clínica.
- **Opção B:** dentro de `pedidos_exame.py` como `GET /pedidos-exame/relatorio.csv` (sem `{proto}`).
  Menos arquivos, mas mistura relatório agregado com rotas por-protocolo.

> Recomendação do arquiteto: **Opção A** — o domínio clínica/lab tende a crescer (R4, TUSS,
> futuras integracões), e o `/dispensadores` já mostrou o custo de acumular escopos.

### §5.2 Trabalho (DESPACHO-ENG-008)

1. Criar `backend/app/routers/clinicas.py` com `router = APIRouter(prefix="/clinicas", ...)`.
2. `GET /clinicas/relatorio.csv` e `/clinicas/relatorio.pdf`, ambos:
   - `usuario=Depends(require_role("dispensador"))`
   - `cnpj = normalize_cnpj(usuario["sub"])` (padrão `dispensadores.py:460`)
   - Query params `data_inicio` / `data_fim` (default últimos 30 dias, via `_janela_periodo`)
   - Fonte de dados: `pedido_exame_custodia` (join por CNPJ) + `pedido_exame_eventos` (timeline de
     status por item) — read-only, nenhum INSERT/UPDATE.
3. Registrar em `main.py`: `app.include_router(clinicas.router)`.
4. Critério de aceite: clínica só vê pedidos **sob sua custódia atual**; CSV com cabeçalho
   `protocolo,item,codigo_tuss,status,data_coleta,data_resultado`; PDF com aviso de truncagem se
   >1000 registros (padrão `_MAX_REGISTROS_PDF`).

---

## §6 R4 — Faturamento (projeção interna do ledger)

**Estado:** greenfield. Ledger `pedido_exame_eventos` disponível. **Decisão cravada:** relatório
interno read-only, **não** guia TISS.

### §6.1 Trabalho (DESPACHO-ENG-009)

1. `GET /clinicas/faturamento.{csv,pdf}` (mesmo router de R3), escopado por CNPJ do JWT.
2. Projeção sobre `pedido_exame_eventos WHERE tipo_evento IN ('resultado_registrado',
   'pedido_encerrado')` + join com `pedido_exame_custodia` (CNPJ prestador) + `pedido_exame_itens`
   (codigo_tuss para agregação por procedimento).
3. **Invariantes (§10 / §1 da governança):**
   - **Nenhum** estado novo em `ESTADOS_PEDIDO_EXAME`.
   - **Nenhuma** escrita no ledger (`pedido_exame_eventos`) nem em custódia.
   - Classe `module` — não toca core.
   - Não depende de G4A (read-only; nada é publicado a sistema externo).

### §6.2 Fora de escopo (bloqueado)

- **Guia TISS** — exige Event Publishing Layer (G4A) com dispatcher/e-gressão. Hoje o outbox
  (`outbox.py:27`) escreve em `eventos_publicacao` mas **não tem consumer/dispatcher**
  (`eventos.py:51` só expõe o polling). Bloqueio confirmado em `CLAUDE.md:731` + `ETHICS.md:57-59`.
- **Seed/normalização TUSS** — backlog; `codigo_tuss` hoje é nullable com base curada de 35 proc.

---

## §7 Critérios de aceite do arco V2

1. `dispensador` (clínica/lab) dono do pedido registra resultado; não-dono leva 403.
2. `GET /clinicas/relatorio.csv` retorna apenas exames sob custódia atual do CNPJ do JWT.
3. `GET /clinicas/faturamento.csv` retorna agregação por procedimento (TUSS), read-only.
4. Nenhum estado novo em `ESTADOS_PEDIDO_EXAME`; nenhuma escrita nova no ledger.
5. UI da clínica (`clinica.html`) expõe realizar/coletar/resultado/faturar/relatório; mock-tags
   (`clinica.html:1452/1454`) substituídos por controles reais.

---

## §8 Fora de escopo

- Guia TISS / adapter externo (bloqueado por G4A).
- Papel `prestador` distinto de `dispensador` (comentário `:815`: *"futuro: prestador"*).
- Normalização/seed TUSS ampliada (backlog).
- Notificação push/SMS ao paciente (decisão: polling).

---

## §9 Fluxo de aprovação

```
Parecer conselheiro (regime de prova)
  → Arquiteto verifica in-loco (este ticket, §1.1)
  → Despachos derivados:
       DESPACHO-ENG-007 (R1 resultado p/ dispensador)  — enxerto RBAC
       DESPACHO-ENG-008 (R3 relatório de exames)       — backend novo
       DESPACHO-ENG-009 (R4 faturamento read-only)      — backend novo
       DESPACHO-KIMI3-007 (UI clínica)                  — frontend
  → PR → Revisor audita → Conselheiro ratifica → Fabiano martela
```

---

## §10 Anexo — âncoras de código (verificado 2026-08-07, commit `3162af9`)

| Item | Arquivo:linha |
|---|---|
| `_assert_dispensador_dono_pedido` (ownership por CNPJ) | `backend/app/routers/pedidos_exame.py:594-616` |
| wired em consulta | `pedidos_exame.py:656-657` |
| wired em coletar | `pedidos_exame.py:835-836` |
| `coletar_item_exame` (aceita dispensador) | `pedidos_exame.py:811-815` |
| `realizar_agendamento` (aceita dispensador) | `backend/app/routers/agendamentos.py:493-496` |
| `registrar_resultado_item` (exclui dispensador) | `pedidos_exame.py:974-979` |
| `_normalizar_identidade_jwt` (CNPJ do sub) | `backend/app/utils/helpers.py:50-72` |
| `normalize_cnpj` | `backend/app/utils/helpers.py:18-22` |
| Precedente relatório CSV (dispensador/farmácia) | `backend/app/routers/dispensadores.py:452-480` |
| Precedente relatório PDF (dispensador/farmácia) | `backend/app/routers/dispensadores.py:483-517` |
| Ledger de exames (schema) | `backend/app/domain/ledger.py:77-84` |
| Eventos canônicos de exame | `backend/app/domain/states_exame.py:128-143` |
| `derivar_status_pedido` | `backend/app/domain/states_exame.py:159-188` |
| Bloqueio TISS por G4A (doc) | `CLAUDE.md:731` |
| UI clínica — mock-tags a substituir | `clinica.html:1452,1454` |
| UI clínica — header (lar do "relatório") | `clinica.html:468-482` |

---

*Documento de visão emitido pelo arquiteto. Fundamentado em verificação in-loco (`3162af9`),
não em briefing de terceiros. Despachos derivados em arquivos separados.*
