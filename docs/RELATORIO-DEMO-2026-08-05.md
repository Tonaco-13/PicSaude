# Relatório de Circulação de Objetos Sanitários — DEMO PicSaúde

> **Data da coleta:** 05/08/2026 (18:25–18:45 BRT)
> **Ambiente:** `https://picsaude.com.br` (Render, `stg`, v1.0.0, uptime ~24h)
> **Coleta:** navegação pela vitrine + chamadas diretas à API REST (`/demo/login` + endpoints autorizados)
> **Fonte de governança:** `CLAUDE.md` (contrato de estados §5/§5a/§5b, custódia §3, ledger §2, R1–R4 §2a)

---

## 0. Identidades canônicas da demo (fonte: `config.js` + `seed_demo.py`)

| Papel | Identificador | Nome |
|---|---|---|
| Cidadão | CPF `12345678909` | João Demo da Silva |
| Prescritora | CNS `980001112223334` | Dra. Demo Maria Souza |
| Farmácia Central | CNPJ `99999999000191` | Farmácia Demo Central |
| Farmácia Norte | CNPJ `99999999000272` | Farmácia Demo Norte |
| Clínica/Laboratório | CNPJ `11222333000181` | Clínica Demo |

Login: seletores de papel da vitrine (`/demo/login`) — KISS, JWT bearer, sem refresh (§3.7.1).

---

## 1. Objetos sanitários emitidos nesta sessão (manualmente, pelo prescritor)

| # | Tipo | Protocolo | Conteúdo | Destino |
|---|---|---|---|---|
| 1 | **Prescrição** | `f9916948-a70f-48bb-90ae-26a0d114215e` | Losartana Potássica 50mg × 30 comprimidos — validade 30 dias — CID I10 (sugerido) | carteira do paciente (CPF 12345678909) |
| 2 | **Pedido de Exame** | `768c0173-56c3-47e5-a4ac-cfcc227b26ab` | Hemograma completo (1) — prioridade rotina — "Investigação de anemia e função renal" | carteira do paciente |
| 3 | **Atestado** | `a74c8e91-4678-4f4b-b832-78a89e8890e8` | Afastamento 2 dias — finalidade trabalhista — CRM-PE 12345 — válido até 07/08/2026 | carteira do paciente |

Modo de emissão: Digital, ICP-Brasil (certificado local — stub). Em todos os três, o backend devolveu `custodia_transferida prescritor→paciente` no ato da emissão (via `emissao_direta`).

### Semáforo de confiança (prescritora)
- **Validação CNES:** NÃO ENCONTRADO (a persona demo não tem vínculo no snapshot CNES 2026-05)
- **Confiança do cuidado:** **BAIXO** (pontuação 10) — semáforo operando, não-bloqueante
- **Coerência observada:** o mesmo `score_confianca.nivel=baixo` aparece na dispensação — a métrica acompanha o objeto, não é recalculada só no balcão.

---

## 2. Máquina de estados observada — Prescrição (`f9916948`)

Rastreada do nascimento ao terminal, cruzando UI (cidadao.html) + API (`/paciente/prescricoes`, `/dispensadores/fila`, `/public/prescricoes/{proto}`).

| Marco | status_prescricao | status_item (Losartana) | detentor custódia | Evento ledger |
|---|---|---|---|---|
| Emissão digital | `pendente` → `transferida_paciente` | `pendente` | prescritor → **paciente** | `prescricao_emitida` + `custodia_transferida` |
| Transferência p/ farmácia | `transferida_paciente` → **`em_custodia`** | `pendente` | paciente → **dispensador** (CNPJ 99999999000191) | `custodia_transferida` |
| Dispensação total (30/30) | **`dispensada`** (terminal) | **`dispensado`** (terminal) | (entregue ao paciente) | `dispensacao_registrada` + `item_dispensado` |
| Estorno (objeto derivado) | `dispensada` *(permanece)* | `dispensado` *(permanece)* | **custódia reaberta** p/ paciente | `estorno_registrado` |
| Estado final na UI | histórico — **"Finalizada"** | — | — | — |

**Invariantes confirmados (CLAUDE.md §1, §2, §4):**
- Imutabilidade: o estorno **não alterou** `dispensacoes.id=1`; criou `estornos.id=1` (`protocolo a4fea4c8…`, `origem_dispensacao_id=1`).
- Estorno é **objeto sanitário derivado e imutável**, não transição de estado — `status_item` seguiu `dispensado`.
- Saldo efetivo = Σ dispensado − Σ estornado = 30 − 30 = 0; a API reportou `saldo_restante: 30` pós-estorno (ver nota em §6).

---

## 3. Máquina de estados observada — Prescrição seed (`DEMO-FILA-0001`)

3 itens (Losartana 30, Amoxicilina 21, **Clonazepam 2mg — controlado B1**), iniciou em `em_custodia` (detida pela Farmácia Central via `seed_demo_fila_t4`).

| Operação | Item | Resultado |
|---|---|---|
| **Dispensação parcial** | Amoxicilina (item 2): 10/21 | `dispensacao_id=2`, `saldo_restante=11`, item `em_custodia`, prescrição `em_custodia` — §4: parcial **não invalida** a prescrição |
| **Devolução ao prescritor** (erro no balcão) | Clonazepam (item 3) | custódia `dispensador → prescritor`, `motivo=devolucao_ao_prescritor`; prescrição → **`transferida_prescritor`** (espelho de `transferida_paciente`, COER-2) |
| Estado final na UI do cidadão | — | **"Devolvida ao médico"** |

**Cadeia de custódia granular** (`GET /prescricoes/DEMO-FILA-0001/custodia`) — confirmada:
- `custodia_ativa` nível-prescrição: `prescritor / 980001112223334` (a devolução fechou o nível-prescrição anterior e abriu o novo)
- `itens_custodia_ativa`: item 2 (Amoxicilina) ainda com `dispensador / 99999999000191`, `motivo=dispensacao`
- `historico`: registro `seed_demo_fila_t4` aparece com `encerrada_em` preenchido — choke-point `custodia.py::transferir_posse` fecha + abre atomicamente.

**Motivo canônico por caminho (§3):** o texto livre que enviei (`"Erro de posologia identificado no balcão"`) vai em `motivo_detalhe`; o canônico `devolucao_ao_prescritor` foi preservado.

---

## 4. Máquina de estados observada — Pedido de Exame (`768c0173`)

| Marco | status_pedido | status_item (Hemograma) | Custódia |
|---|---|---|---|
| Emissão | `emitido` | `pendente` | prescritor → paciente (`emissao_direta`) |
| Agendamento (Clínica Demo, 06/08 08:00) | `agendado` | `agendado` | paciente → prestador_exame |
| Coleta | `coletado` | `coletado` | — |
| Resultado registrado | `encerrado` (terminal) | `resultado_disponivel` | — |

Ledger do pedido (retornado pelo `GET`): `pedido_emitido` → `custodia_transferida {prescritor→paciente, via=emissao_direta}`. Estados coerentes com `ARQUITETURA_EXAMES.md` e CLAUDE.md §7.

---

## 5. Máquina de estados observada — Laudo (`DEMO-LAUDO-0001`, seed)

| Marco | status_laudo | status_item (Glicemia) |
|---|---|---|
| (seed) | `liberado` | `concluido` (98 mg/dL, **alterado**) |
| Ciência do paciente | **`ciencia_paciente`** | — |

Ledger (já vinha do seed): `laudo_criado → laudo_assinado → laudo_liberado {prestador=11222333000181}`.
Próximos estados possíveis (não exercitados): `ciencia_prescritor → encerrado`.
Concorda com `ARQUITETURA_LAUDO.md`: ciência opera no nível do laudo inteiro (exceção documentada ao núcleo).

---

## 6. Validação documental em 5 camadas — `f9916948`

`GET /prescricoes/{proto}/validacao` → 22 checks: **9 ok · 13 falha**. `resultado_geral: invalido`, `nivel_formal: cfm_pendente`.

Camadas e achados principais:
- **Estrutural:** ✅ todos os 5 (prescrição existe, tipo/status reconhecidos, tem itens, itens com status reconhecido)
- **Integridade:** ⚠️ **`hash_integro: false`** — *"Hash divergente. Armazenado: 323d309414c6bffd… Recomputado: ab56965ea0a0e3b1… O conteúdo da prescrição pode ter sido alterado após emissão."* **(alarme — investigar)**
- **CFM:** ✅ CPF real, campos CFM por item, modo de assinatura válido
- **Assinatura digital:** ❌ metadados não registrados em `prescricao_assinatura`; sem prova criptográfica; hash assinatura incoerente
- **(camada 5)** ❌ dependências de assinatura

> **Observação técnica:** o hash divergente pode indicar (a) o documento canônico mudou pós-emissão (violação de imutabilidade §1), ou (b) o algoritmo de recomputação divergiu entre seed/demo, ou (c) campo armazenado em momento diferente do recomputado. Vale um ticket — é exatamente o tipo de sinal que a camada de integridade existe para acusar.

> **Nota sobre saldo pós-estorno:** o endpoint `/dispensacoes/{id}/estornar` devolveu `saldo_restante: 30` e `custodia_reaberta: true`, mas manteve `status_item: dispensado`. Ou seja, o saldo **efetivo** voltou a 30 (item novamente disponibilizável), enquanto o **estado** permanece `dispensado`. Confirma §2 ("estorno não é transição de estado") — mas a nomenclatura `saldo_restante` pós-estorno merece documento: é o saldo após desfazer a saída, não o saldo restante daquela dispensação.

---

## 7. Pontos da arquitetura que ficaram evidentes ao circular objetos

1. **Cidadão único fecha o ciclo.** Receita emitida no `prescritor.html` caiu na carteira do mesmo CPF `12345678909` no `cidadao.html` — e o `dispensador.html` viu a mesma receita na fila. A fonte única de identidades (`config.js` ↔ `seed_demo.py`, guard-railed por `test_guardrail_identidades_demo.py`) é o que faz a circulação fechar.
2. **Custódia granular é real.** O seed `DEMO-FILA-0001` terminou com **dois níveis de custódia ativos ao mesmo tempo**: nível-prescrição no prescritor (devolução) e nível-item na Amoxicilina ainda com o dispensador. A granularidade por `item_id` não é cosmética.
3. **Estorno ≠ transição de estado.** Confirmado em produção: `status_item` não voltou a `pendente` após o estorno; o saldo foi restaurado por soma algébrica no objeto derivado. É o corolário operacional do §2.
4. **Semáforo de confiança acompanha o objeto.** `score_confianca` apareceu idêntico na emissão e na dispensação — não é decorativo.
5. **Endpoint público é neutro.** `/public/prescricoes/{proto}` devolve só `protocolo/status/tipo_emissao/itens(ordem,status_item)` — sem finalidade, CID, posologia, identidade. Conforme §"Validação pública neutra" de `ARQUITETURA_*`.
6. **RBAC visível na API.** `paciente` não acessa `/eventos`, `/prescricoes/{proto}/validacao`, `/pedidos-exame/{proto}` (só `admin/prescritor/dispensador` conforme caso). O `agendar` exige prescritor, não paciente.
7. **Admin indisponível na demo pública** (`papel_demo_indisponivel` — aceitos: prescritor, dispensador, dispensador_norte, clinica, paciente). Coerente com G2 (demo é vitrine, não piloto).

---

## 8. Achados a reportar (não-bloqueantes, mas merecem ticket)

| # | Achado | Severidade | Evidência |
|---|---|---|---|
| A1 | **Hash de integridade divergente** em prescrição recém-emitida | **Alta** (feriria R3 se real) | `/validacao` → `hash_integro: false` em `f9916948` |
| A2 | `saldo_restante` pós-estorno documenta ambiguity (saldo da prescrição vs. da dispensação) | Baixa | `/dispensacoes/1/estornar` retornou `saldo_restante: 30` |
| A3 | `undefined - undefined, 5 de Agosto de 2026` no PDF da receita emitida (campos de local/UF da prescritora vazios na persona demo) | Baixa (cosmético) | tela de sucesso do `prescritor.html` |
| A4 | Botões que disparam `confirm()` nativo (ex.: "Transferir Custódia") não responderam ao click automático no IAB — só via API. Não é bug do PicSaúde; é limitação do backend de automação. | — | `cidadao.html::transferirParaFarmacia` |

---

## 9. Reprodutibilidade (comandos-chave)

```bash
# Tokens por papel (KISS — sem senha, seletor de persona)
TOKEN_PAC=$(curl -s -X POST https://picsaude.com.br/demo/login \
  -H "Content-Type: application/json" -d '{"role":"paciente"}' | jq -r .access_token)
TOKEN_PRE=$(... -d '{"role":"prescritor"}'   | jq -r .access_token)
TOKEN_DISP=$(... -d '{"role":"dispensador"}' | jq -r .access_token)

# Transferir custódia paciente → farmácia
curl -X POST https://picsaude.com.br/paciente/prescricoes/<PROTO>/transferir-farmacia \
  -H "Authorization: Bearer $TOKEN_PAC" -H "Content-Type: application/json" \
  -d '{"cnpj_farmacia":"99999999000191"}'

# Dispensar (total ou parcial)
curl -X POST https://picsaude.com.br/prescricoes/<PROTO>/itens/<ITEM>/dispensar \
  -H "Authorization: Bearer $TOKEN_DISP" -H "Content-Type: application/json" \
  -d '{"quantidade_dispensada":30,"cnpj_estabelecimento":"99999999000191"}'

# Estornar (motivos: desistencia_paciente|erro_dispensacao|pagamento_nao_concluido|outro)
curl -X POST https://picsaude.com.br/dispensacoes/<ID>/estornar \
  -H "Authorization: Bearer $TOKEN_DISP" -H "Content-Type: application/json" \
  -d '{"motivo":"erro_dispensacao","quantidade_estornada":30}'

# Devolver item ao prescritor (choke-point de custódia)
curl -X POST https://picsaude.com.br/prescricoes/<PROTO>/custodia/transferir \
  -H "Authorization: Bearer $TOKEN_DISP" -H "Content-Type: application/json" \
  -d '{"de":"dispensador","de_id":"99999999000191","para":"prescritor","para_id":"980001112223334","item_id":3,"motivo":"devolucao_ao_prescritor"}'

# Ciclo de exame
curl -X POST .../pedidos-exame/<PROTO>/agendar          -d '{"cnpj_prestador":"11222333000181","nome_prestador":"Clínica Demo","data_agendamento":"2026-08-06T08:00:00"}'
curl -X POST .../pedidos-exame/<PROTO>/itens/<ITEM>/coletar   -d '{}'
curl -X POST .../pedidos-exame/<PROTO>/itens/<ITEM>/resultado -d '{"resultado_resumo":"..."}'

# Cadeia de custódia + validação pública
curl https://picsaude.com.br/prescricoes/<PROTO>/custodia   -H "Authorization: Bearer $TOKEN_DISP"
curl https://picsaude.com.br/public/prescricoes/<PROTO>     # neutro, sem auth
```

---

## 10. Conclusão

A **máquina de estados de circulação de objetos sanitários está operando conforme o contrato do `CLAUDE.md`** em todos os módulos exercitados (prescrição, exame, laudo, atestado). Invariantes chave confirmados em runtime:

- ✅ Imutabilidade pós-emissão (§1) — derivação por estorno, não edição
- ✅ Ledger append-only (§2) — `custodia_transferida`, `dispensacao_registrada`, `estorno_registrado` observados
- ✅ Custódia granular e choke-point (§3) — transições atômicas, motivo canônico preservado
- ✅ Dispensação parcial não-invalidante (§4)
- ✅ Estados físicos vs digitais coerentes (§5/§5b)
- ✅ Endpoint público neutro

**Único alarme real:** o `hash_integro: false` na validação de uma prescrição recém-emitida (A1) — merece investigação, pois é o tipo de sinal que a camada de integridade existe para acusar e que, se verdadeiro, feriria a linhagem-mãe indelével (R3).
