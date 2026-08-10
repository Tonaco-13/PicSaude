# PARECER-REVISOR — Estorno não chega ao cidadão

| Campo | Valor |
|---|---|
| **Revisa** | `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO` |
| **Papel** | Revisor de tickets (parecer **consultivo** — opina, não bloqueia; volta ao Fabiano quando destoa) |
| **Data** | 2026-08-10 |
| **Veredito** | 🔴 **NÃO pronto para o Engenheiro** — bug real, mas o fix reverte decisão ratificada (`TICKET-B0`) e contradiz invariante do CLAUDE.md sem reconhecer. **Destoa → volta ao Arquiteto/Fabiano.** |
| **Base do parecer** | Leitura do código real (não da caracterização do ticket): `dispensacoes.py`, `states.py`, `custodia.py`, `auth.py`, `tests/integration/test_estorno.py` |

> Método: parecer sobre mudança `core` não se apoia na descrição de terceiros. Todos os
> achados abaixo estão ancorados em `arquivo:linha` verificados nesta revisão.

---

## §1 O que o ticket acertou (crédito)

- **Bug confirmado no código.** Após estorno total, a carteira do cidadão fica vazia e
  `POST /paciente/prescricoes/{proto}/devolver-prescritor` retorna 409. Real e reproduzível.
- **Linha-raiz certa.** A origem está em `backend/app/routers/dispensacoes.py:635-641`.
- **Classificação `core` correta** — toca `domain/states.py` + cadeia de custódia.

---

## §2 Correções factuais ao ticket (precisão importa num parecer core)

1. **O handler NÃO "deixa de reabrir custódia".** Ele reabre — para o **dispensador**,
   deliberadamente (`dispensacoes.py:635-641`, `para_tipo="dispensador"`, motivo canônico
   `estorno_reposicao_saldo`). O §4.1 do ticket descreve isso corretamente; o §7 trata como
   esquecimento. Não é.

2. **Esse destino é TESTADO e ratificado.** `tests/integration/test_estorno.py:147`
   (`test_redispensa_apos_estorno_usa_saldo_reposto`) consagra: estorno repõe saldo → item
   **re-dispensável na farmácia** — e usa **exatamente o motivo `desistencia_paciente`**, o
   mesmo da repro. Origem: `TICKET-B0-DISPENSABILIDADE-POR-SALDO`. Logo, o fix **reverte o
   TICKET-B0**; não corrige uma omissão. Exige martelo do Fabiano — não é mecânico.

3. **A carteira decide por `p.status`, não pela custódia** (`auth.py:184-194`). Portanto,
   mexer só na custódia **não** conserta a visibilidade — a alavanca é o *status da
   prescrição*, derivado do *status do item*. Qualquer solução passa por status.

4. **`_recalcular_status_prescricao` nem é chamado no estorno** e lê `status_item`
   (`custodia.py:253-308`). O passo "regredir para `transferida_paciente`" do ticket depende
   inteiramente de mutar o item antes.

---

## §3 Conflitos com invariantes que o ticket não reconhece

| # | Conflito | Onde |
|---|---|---|
| **A** | Reverte decisão ratificada/testada (re-dispensação pós-estorno) | `TICKET-B0` + `test_estorno.py:147` |
| **B** | A linha `estorno_registrado` do CLAUDE.md §2 e `states.py:157-162` afirmam **"NÃO é transição de estado do item"** — mutar para `devolvido_paciente` contradiz o contrato | CLAUDE.md §2 · `states.py:157` |
| **C** | A aresta `dispensado → devolvido_paciente` **não existe**: `TRANSICOES_ITEM["dispensado"] = {"estornado"}` | `states.py:143-152` |
| **D** | `dispensada` é **terminal** (§5b · `states.py:64-88`). Regredir a prescrição viola o contrato de terminais | CLAUDE.md §5b |

Nenhum é opcional: se o fix for adiante sem emendar A–D **no mesmo PR**, o contrato de
estados fica auto-contraditório — o tipo de dívida que o §9/§2a existem para impedir.

---

## §4 Lacunas de escopo (o ticket só cobriu o caso total, motivo único)

- **Motivo-dependência.** `MOTIVOS_ESTORNO` (`states.py:166`) mistura casos com destinos
  diferentes: `erro_dispensacao` (farmácia corrige e re-dispensa — fica na farmácia) vs.
  `desistencia_paciente` / `pagamento_nao_concluido` (cidadão recupera). Regra cega "sempre ao
  paciente" **quebra `erro_dispensacao`** e a máquina `BLOQUEADOS_HARD_DISPENSA`. Precisa de
  destino **por motivo**.
- **Estorno parcial.** `status_item` é enum único; estorno é por quantidade. Item com 21
  dispensados e 10 estornados não pode ser "dispensado" e "devolvido_paciente" ao mesmo tempo.
  O ticket só trata o estorno total.
- **Estorno de 1 item entre vários.** `_recalcular` resumiria a prescrição inteira para
  `transferida_paciente` mesmo havendo outro item legitimamente dispensado. Aceitável? Precisa
  de nota do Arquiteto.

---

## §5 Sobre o `prompt()` / "caiu" (§6 do relatório)

Defeito real, mas **separado** — é `module`/robustez (fire-and-forget + diálogo do IAB), não
`core` de estados. Merece **ticket próprio**. Nota: a repro do bug de backend usou a **REST
direta**, então o "caiu" pode ser o *hang* do `prompt()`, falha distinta — investigar em
paralelo, sem bloquear o core.

---

## §6 Recomendação (consultiva)

Duas famílias, para o Arquiteto escolher com o martelo do Fabiano:

- **Opção Y — mutar estado (instinto do ticket):** `dispensado → devolvido_paciente` +
  `_recalcular → transferida_paciente` + custódia → paciente, **roteado por motivo**. Read-side
  quase de graça (carteira e `devolver_prescritor` já aceitam `devolvido_paciente` +
  `transferida_paciente`). Custo: emendar A–D honestamente. `devolvido_paciente` = "abandono de
  compra" (§5a) casa com `desistencia_paciente` e destrava retry **e** devolução ao médico.
- **Opção X — posse computada:** manter o item imutável (`dispensado`) e derivar a posse da
  **tabela de custódia + saldo efetivo** (não de `p.status`). Honra o derived-object/R1/§10 e
  resolve o parcial de graça. Custo: reescrever carteira + guards perto do choke-point de
  custódia (risco de dupla posse).

**Inclinação do Revisor:** **Opção Y, roteada por motivo** — `erro_dispensacao` permanece
re-dispensável na farmácia (preserva o TICKET-B0 onde faz sentido); os demais voltam ao
cidadão — com as emendas A–D no mesmo PR. Menor superfície de risco junto à custódia do que
reescrever a carteira. **Decisão é do Fabiano**, porque reverte parte do TICKET-B0.

---

## §7 Encaminhamento

Parecer é consultivo e **destoa** → próximo passo não é o Engenheiro, é o **Arquiteto (Z AI)
reescrever a spec** resolvendo: (1) X vs Y com martelo; (2) destino por motivo; (3) estorno
parcial; (4) enumerar as edições completas de contrato (tabelas de `states.py` + linha do
ledger no CLAUDE.md + §5a/§5b + DDL + teste nos dois dialetos); (5) desmembrar o ticket de
frontend. O **Apêndice A** abaixo já esboça a Opção Y para acelerar essa reescrita.

---
---

# Apêndice A — Esboço de spec: Opção Y (mutação de estado roteada por motivo)

> **Status:** esboço do Revisor para *inclinar* a decisão — **não** é spec ratificada. O
> Arquiteto assume, o Fabiano martela. Classe `core`. Requer teste nos dois dialetos.

## A.1 Princípio

O estorno continua sendo **objeto sanitário derivado e imutável** (a `dispensacoes` e a
`estornos` NÃO são mutadas — §1/§2a preservados). O que muda é o **destino da posse e o
estado do item**, que passam a depender do **motivo** do estorno. O saldo efetivo segue
`Σ dispensado − Σ estornado` (contábil, inalterado).

## A.2 Tabela de roteamento por motivo (o coração da spec)

| `motivo` | Destino da custódia | `status_item` após estorno **total** | Racional |
|---|---|---|---|
| `desistencia_paciente` | **paciente** | `devolvido_paciente` | Cidadão desistiu → recupera a receita p/ retry ou devolver ao médico (§3) |
| `pagamento_nao_concluido` | **paciente** | `devolvido_paciente` | Pagamento falhou → cidadão leva a receita p/ outra farmácia |
| `erro_dispensacao` | **dispensador** (mantém atual) | `dispensado` (não muta) | Erro de registro da própria farmácia → re-dispensa ali (preserva TICKET-B0) |
| `outro` | **paciente** (default seguro) | `devolvido_paciente` | Default para o lado do cidadão (regulatoriamente conservador) |

> A régua "cidadão recupera, exceto erro operacional da farmácia" é a candidata do Revisor.
> **Ponto de martelo do Fabiano:** confirmar se `pagamento_nao_concluido` volta ao cidadão
> ou permanece re-dispensável na farmácia (há defesa clínica para os dois).

## A.3 Estorno parcial (o caso que o ticket não cobriu)

`status_item` é enum único; não representa "10 devolvidos, 11 ainda dispensados". Regra
proposta:

- **Estorno total** (Σ estornado do item == Σ dispensado): aplica a coluna `status_item` da
  tabela A.2 (para os motivos "cidadão recupera").
- **Estorno parcial** (Σ estornado < Σ dispensado): **NÃO muta `status_item`** — o item
  segue `dispensado`; a fração revertida vive só no saldo efetivo (comportamento atual
  preservado). A posse volta ao paciente **apenas quando o saldo do item retorna integralmente**
  (i.e., o item deixa de ter entrega líquida). Isso evita um item meio-devolvido-meio-entregue
  sem representação honesta no enum.

> Alternativa a debater com o Arquiteto: permitir posse ao paciente já no parcial, tratando a
> visibilidade pela custódia. Isso puxa para a Opção X e aumenta o risco — o Revisor
> **não** recomenda no primeiro corte.

## A.4 Edições de contrato exigidas (todas no MESMO PR — senão o contrato fica contraditório)

1. **`states.py` — `TRANSICOES_ITEM`**: adicionar a aresta
   `"dispensado": frozenset({"estornado", "devolvido_paciente"})`.
2. **`states.py` — `EVENTOS_ITEM`**: mapear
   `("dispensado", "devolvido_paciente"): "item_devolvido_paciente"`.
3. **`states.py:157-162`** (nota do estorno): reescrever — o item **passa a mutar** para
   `devolvido_paciente` nos motivos "cidadão recupera"; o `dispensado → estornado` segue
   scaffolding dormente (não usado).
4. **CLAUDE.md §2** (linha `estorno_registrado` do vocabulário do ledger): emendar o trecho
   "**não** uma transição de estado do item" para refletir a mutação condicional por motivo.
5. **CLAUDE.md §5a/§5b**: registrar a transição `dispensado → devolvido_paciente` e a nova
   saída da terminalidade condicional (ver item 6).
6. **Terminalidade de `dispensada`/`dispensado` (Conflito D):** decidir e documentar. Opção
   do Revisor — **manter os rótulos como terminais no caso geral**, e declarar a
   regressão pós-estorno como **exceção explícita e nomeada** no contrato (à moda do
   COER2-POS-MERGE-FIX), não como afrouxamento geral do terminal. Isso mantém a guarda
   forte e documenta a única brecha legítima.
7. **DDL** (`docs/picsaude_ddl_postgres_v1.sql`): refletir qualquer CHECK/enum de estados
   afetado (verificar se há constraint de transição no banco).

## A.5 Mudança no handler (`dispensacoes.py:608-657`)

Após criar o objeto-estorno e calcular `saldo_efetivo`, ramificar por motivo:

```
destino, novo_status_item = _rota_estorno(motivo, estorno_total=saldo_efetivo_do_item_integral)

if destino == "dispensador":
    # comportamento atual (TICKET-B0): re-retém p/ a farmácia, item não muta
    transferir_posse(..., "paciente", None, "dispensador", cnpj, "estorno_reposicao_saldo", ...)

elif destino == "paciente":
    # NOVO: devolve ao cidadão
    if novo_status_item:                    # só no estorno total
        _transicionar_item(conn, item_id, "devolvido_paciente")   # valida via TRANSICOES_ITEM
        registrar_evento(... "item_devolvido_paciente" ...)
    transferir_posse(..., de="dispensador"/cnpj, para="paciente", cpf_paciente,
                     motivo_canonico="devolucao_pos_estorno", ...)   # choke-point (COER-2)
    _recalcular_status_prescricao(conn, prescricao_id, agora)        # → transferida_paciente
```

Pontos de disciplina:
- **Toda transição de posse pelo choke-point `transferir_posse`** — nunca `_fechar`+`_abrir`
  à mão (COER-2). Novo `motivo` canônico sugerido: `devolucao_pos_estorno` (o T6/histórico
  separa do `estorno_reposicao_saldo`).
- **`transferir_posse` para paciente precisa do CPF** — hoje o handler passa `paciente_id`;
  confirmar que o CPF do paciente está disponível na query de `disp` (adicionar JOIN em
  `pacientes` se faltar).
- **Item terminal → sem custódia órfã.** Ao devolver ao paciente, garantir que não sobra
  custódia ativa do dispensador (o `_fechar` interno do choke-point cobre, mas exige teste).

## A.6 Retorno da API (`dispensacoes.py:644-657`)

`status_item` e `status_prescricao` no corpo passam a refletir o novo estado quando o
motivo devolve ao cidadão (hoje ecoam o valor antigo). Campo `destino_custodia`
(`"paciente"` | `"dispensador"`) explícito ajuda o frontend a decidir a mensagem.

## A.7 Cobertura de teste exigida (dois dialetos)

- `desistencia_paciente` total → item `devolvido_paciente`, prescrição `transferida_paciente`,
  custódia ativa do **paciente**, carteira do cidadão mostra em POSSE.
- Cidadão consegue `devolver-prescritor` após o estorno (a via §3 destravada).
- Cidadão consegue re-`transferir-farmacia` após o estorno (retry).
- `erro_dispensacao` total → comportamento TICKET-B0 **intacto** (item `dispensado`,
  re-dispensável, custódia do dispensador) — teste de regressão.
- Estorno **parcial** de qualquer motivo → item **não muta**, saldo efetivo reposto (regressão
  do comportamento atual).
- Sem custódia órfã (unicidade `uq_custodia_ativa_*`) em todos os ramos.
- Ledger: `estorno_registrado` + `item_devolvido_paciente` + `custodia_transferida`
  (`devolucao_pos_estorno`) na sequência correta.

## A.8 Fora do escopo desta spec (tickets irmãos)

- Robustez do `prompt()` / "caiu" no `dispensador.html` — ticket `module` próprio.
- Migração para posse computada (Opção X) — não fazer; registrado como alternativa rejeitada
  no primeiro corte.
