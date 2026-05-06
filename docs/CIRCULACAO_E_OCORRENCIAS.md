# PicSaúde — Circulação, Devoluções e Registro de Ocorrências

> **Classificação:** `docs`
> **Dependências:** `NUCLEO_SANITARIO.md`, `MAQUINA_ESTADOS_CUSTODIA.md`,
> `ARQUITETURA_AGENDAMENTO.md`
> **Status:** Contrato arquitetural — pré-teste de campo

---

## Por que este documento existe

O PicSaúde modela bem dois pontos de um ciclo sanitário:

1. **a emissão** — quando o objeto é criado e assinado
2. **a execução** — quando o objeto é dispensado, coletado ou laudado

O que ainda não está formalizado é **o que acontece entre esses dois pontos** quando o cuidado não segue seu curso natural: o paciente recusa, o prestador devolve, o agendamento é desmarcado, o item não é executado.

Sem um contrato explícito para esses momentos, o teste de campo vai registrar os incidentes, mas o sistema não vai ter vocabulário para interpretá-los. Adapters futuros não vão conseguir distinguir "item devolvido" de "item não iniciado". Análises de efetividade vão confundir encerramento planejado com falha operacional.

Este documento define:

- o conceito de **circulação digital**
- a distinção entre **encerramento local** e **circulação**
- o modelo de **devoluções** totais e por item
- o modelo de **recusa / desmarcação / arquivamento**
- o artefato futuro **Registro de Ocorrências e Ambiguidade**
- os impactos futuros em estados, ledger e adapters — **sem implementar ainda**
- a sequência recomendada de implementação

---

## Mapa rápido

| Seção | Conteúdo |
|---|---|
| 1 | Conceito de circulação — encerramento local vs. digital |
| 2 | Regimes de destino — taxonomia |
| 3 | Devoluções — total, parcial, por item |
| 4 | Matriz de atores — quem pode fazer o quê |
| 5 | Agendamento — fluxo real refinado |
| 6 | Registro de Ocorrências e Ambiguidade |
| 7 | Ocorrência vs. estado — princípio de moderação |
| 8 | Impacto futuro na máquina de estados |
| 9 | Impacto futuro no ledger |
| 10 | Relação com adapters e piloto |
| 11 | Sequência recomendada |

---

## 1. Conceito de circulação

### 1.1 Encerramento local

Um objeto sanitário tem **encerramento local** quando:

- é materializado em papel (impresso e/ou assinado fisicamente)
- não é transmitido ao sistema digital como objeto circulante
- o registro no banco existe apenas como **rastro de emissão** — não como objeto ativo

**Consequência direta:**

- o objeto não pode ser aceito, recusado, devolvido ou executado digitalmente
- não gera cadeia de custódia
- não entra no fluxo de dispensação, coleta ou laudagem digital
- o ledger recebe dois eventos e encerra: `{objeto}_impresso` + `encerrado_localmente`
- o status do objeto é `encerrada_localmente` (terminal)
- itens ficam com `encerrado_fisico` (terminal)

**Exemplos:**

- receita impressa sem registro digital do paciente
- pedido de exame impresso na consulta
- atestado físico entregue em mãos

**Princípio:**

> Encerramento local é uma saída do sistema, não uma falha. O objeto cumpriu sua função no papel. O PicSaúde não precisa rastrear o que acontece depois.

---

### 1.2 Circulação digital

Um objeto sanitário **circula digitalmente** quando:

- é emitido com identificação real do paciente
- é transmitido ao sistema e passa para custódia do paciente ou do prestador
- pode sofrer transições após a emissão

**A circulação começa** no momento em que a custódia é transferida do prescritor para o paciente (`prescritor → paciente`).

**A circulação termina** quando o objeto atinge um estado terminal:
- `dispensada` / `executado` / `laudado` — execução completa
- `cancelada` — revogação clínica
- `expirada` — validade esgotada
- `encerrada_localmente` — saída para o papel (não entra no ciclo)

**Durante a circulação**, o objeto pode ser:

| Evento | Significado |
|---|---|
| **aceito** | o destinatário recebe e retém |
| **recusado** | o destinatário rejeita antes de executar |
| **devolvido** | o destinatário inicia execução mas reverte |
| **executado parcialmente** | parte do objeto foi executada |
| **arquivado** | execução impossibilitada por razão operacional |
| **remarcado** | novo momento de execução acordado (via novo objeto derivado) |

---

## 2. Regimes de destino

Um objeto sanitário, ao final de sua vida, se enquadra em um dos seguintes **regimes de destino**:

### 2.1 Regimes já implementados

| Regime | Estado final | Quando ocorre |
|---|---|---|
| `encerrado_localmente` | `encerrada_localmente` | Emissão exclusivamente física |
| `executado` | `dispensada` / `encerrado` / estado equiv. | Execução completa de todos os itens |
| `cancelado` | `cancelada` | Revogação clínica ou administrativa |
| `expirado` | `expirada` / `expirado` | Validade esgotada sem execução |

### 2.2 Regimes que precisam ser formalizados

| Regime | Descrição | Implementação sugerida |
|---|---|---|
| `devolvido_totalmente` | Todo o objeto foi devolvido antes de qualquer execução | Novo estado ou evento — decidir por objeto |
| `parcialmente_devolvido` | Parte dos itens foi devolvida ou não executada | Tratado no nível do item (ver seção 3) |
| `arquivado` | Objeto não executado por razão operacional não-clínica | Evento de ledger + possível estado terminal |

### 2.3 O que é estado e o que é ocorrência

Nem todo regime precisa virar estado na máquina de estados. A regra é:

> **Estado** → quando a transição muda o comportamento do sistema em relação ao objeto (quem pode acessá-lo, o que pode ser feito com ele).
>
> **Ocorrência** → quando o evento deve ser registrado, mas não muda o fluxo principal do objeto.

| Situação | Estado ou ocorrência? | Justificativa |
|---|---|---|
| Paciente devolve prescrição inteira | Estado (`pendente`) | O objeto volta ao ciclo do prescritor |
| Prestador arquiva pedido sem coleta | Estado terminal ou evento | Depende se o pedido pode ser reaberto |
| Paciente falta ao agendamento | Estado (`nao_compareceu`) — já implementado | O itens voltam a `pendente` |
| Item não coletado por falta de reagente | Ocorrência | O item fica `pendente`; a causa é registrada |
| Agendamento desmarcado pelo paciente | Estado (`cancelado`) — já implementado | Novo agendamento pode ser derivado |

---

## 3. Devoluções

### 3.1 Princípio da granularidade

> **A devolução deve ser tratada, sempre que possível, no nível do item — não do objeto inteiro.**

Isso preserva a prescrição (ou pedido) como unidade válida mesmo quando apenas parte do conteúdo retorna.

A soma `Σ(devolvido) + Σ(executado) ≤ Σ(prescrito/solicitado)` deve sempre ser verdadeira por objeto.

---

### 3.2 Devolução total

**Definição:** O objeto inteiro retorna ao remetente ou à fila disponível, sem que nenhum item tenha sido executado.

**Quando ocorre:**

- paciente recusa a prescrição antes de qualquer dispensação
- clínica recusa pedido de exame antes de qualquer coleta
- dispensador identifica erro de prescrição antes de dispensar

**Comportamento esperado:**

- todos os itens retornam ao estado `pendente` ou `devolvido_prescritor`
- a custódia é transferida de volta ao prescritor
- o objeto retorna a `pendente` ou a um estado que permita nova tentativa
- um evento de ledger documenta a devolução com motivo e ator

**Distinção com cancelamento:**

> `cancelada` = decisão clínica (erro, contraindicação, mudança terapêutica).
> Devolução total = decisão operacional ou do paciente; o objeto permanece clinicamente válido.

---

### 3.3 Devolução parcial / por item

**Definição:** Apenas parte dos itens do objeto retorna ou deixa de ser executada.

**Quando ocorre:**

- dispensador não tem um dos medicamentos da prescrição
- apenas um exame do pedido não pode ser realizado
- paciente desiste de retirar parte dos medicamentos

**Comportamento esperado:**

- apenas os itens afetados mudam de estado
- o objeto não é cancelado; fica `parcialmente_dispensada` ou status equivalente
- os itens não afetados continuam seu fluxo normal
- um evento de ledger por item documenta o retorno

**Invariante:**

```
Σ quantidade_dispensada_por_item ≤ quantidade_prescrita_por_item
```

Esta invariante já existe para dispensação; deve ser estendida para outros objetos.

---

### 3.4 Estados de item para devoluções

Os estados de item já existentes cobrem o essencial:

| Estado | Significado | Terminal? |
|---|---|---|
| `devolvido_paciente` | Abandono de compra; item pode ser tentado novamente | Não |
| `devolvido_prescritor` | Erro clínico identificado; aguarda nova prescrição | Sim (*) |
| `cancelado` | Revogação clínica | Sim |

Para objetos além da prescrição (pedido de exame, laudo), vocabulário equivalente deve ser definido em cada `domain/states_*.py` quando o caso de uso real surgir.

---

## 4. Matriz de atores — quem pode fazer o quê

| Ator | Pode devolver | Pode recusar | Pode arquivar | Pode remarcar |
|---|---|---|---|---|
| **Prescritor** | Recebe devolução; pode gerar nova prescrição derivada | — | — | Emite novo objeto com `origem_*_id` |
| **Paciente** | Devolve prescrição / pedido ao prescritor | Recusa agendamento | — | Não — solicita ao prestador |
| **Dispensador** | Devolve item ao paciente (abandono) ou ao prescritor (erro) | — | — | — |
| **Clínica / Laboratório** | Devolve pedido ao prescritor (erro técnico) | Recusa pedido antes de iniciar | Arquiva pedido sem execução | Propõe nova data (remarcação) |
| **Administrador** | Pode arquivar por decisão operacional | — | Sim — escopo institucional | — |

**Regra geral:**

> Quem detém a custódia em um dado momento é o ator que pode iniciar a devolução naquele momento.

---

## 5. Agendamento — fluxo real refinado

O módulo de agendamento (Ticket 28/29) já prevê remarcação como novo objeto derivado. Este documento consolida o fluxo completo visto do lado do paciente e da clínica.

### 5.1 Fluxo esperado em campo

```
Clínica / Laboratório
  └─► propõe / cria agendamento (status: criado)
          │
          ▼
      Paciente
      ├─► aceita implicitamente (aguarda confirmação)
      │       └─► agendamento → confirmado
      │
      └─► desmarca (cancela antes do horário)
              └─► agendamento → cancelado (motivo: desmarcado_paciente)
                      └─► itens do pedido voltam a: pendente
                              └─► Clínica pode:
                                  ├─► arquivar pedido (sem nova tentativa prevista)
                                  └─► propor nova data (novo agendamento derivado)
```

### 5.2 Desmarcação pelo paciente

**Estado resultante:** `cancelado` (já existente)
**Motivo no ledger:** `desmarcado_paciente`
**Impacto nos itens do pedido:** `agendado → pendente`

Este comportamento já está implementado. O que falta é documentar o vocabulário do `motivo` no ledger para que adapters e análises de campo possam distinguir "cancelado porque foi remarcado" de "cancelado por desistência".

**Vocabulário de motivos recomendado para `agendamentos`:**

| `motivo` | Significado |
|---|---|
| `desmarcado_paciente` | Paciente cancelou antes do horário |
| `desmarcado_prestador` | Clínica cancelou (indisponibilidade) |
| `remarcado` | Cancelado para criação de novo objeto derivado |
| `nao_compareceu` | Paciente não apareceu (já cobre o estado `nao_compareceu`) |
| `recusado_prestador` | Clínica recusou o pedido antes de agendar |

### 5.3 Remarcação — princípio preservado

> **Remarcação = novo objeto derivado.** Não existe estado `remarcado`.

O agendamento original recebe `cancelado` com `motivo = 'remarcado'`.
O novo agendamento recebe `origem_agendamento_id` apontando para o anterior.

Isso já está definido em `ARQUITETURA_AGENDAMENTO.md`. Este documento não altera esse contrato — apenas registra que o vocabulário de `motivo` deve ser formalizado antes do piloto.

### 5.4 Arquivamento pelo prestador

**Quando ocorre:** A clínica decide que o pedido não pode ser executado e não será remarcado.

**Comportamento esperado:**

- agendamento → `cancelado` (motivo: `arquivado_prestador`)
- itens do pedido: `pendente → cancelado` (decisão técnica) ou `pendente → encerrado` (sem nova tentativa)
- um evento de ocorrência é gerado no Registro de Ocorrências (ver seção 6)

**Nota:** A decisão entre `cancelado` e um novo estado `arquivado` deve ser tomada com base no uso real do campo. Por enquanto, o vocabulário de `motivo` é suficiente.

---

## 6. Registro de Ocorrências e Ambiguidade

### 6.1 Para que serve

O Registro de Ocorrências e Ambiguidade (`ocorrencias`) é um **artefato de observabilidade clínica e operacional** — não é uma tabela de negócio principal.

Seu propósito é capturar, durante o teste de campo e operação real, dois tipos de eventos que o sistema hoje não registra estruturalmente:

**A. Ambiguidades semânticas** — quando o vocabulário do objeto não mapeia claramente para terminologias externas (TUSS, SIGTAP, CID, CBO).

Exemplos:
- termo clínico genérico ("exame de sangue") que não tem código TUSS único
- diagnóstico com CID ambíguo entre dois capítulos
- procedimento que tem código TUSS mas não tem SIGTAP correspondente
- medicamento prescrito sem DCI, apenas nome comercial

**B. Ocorrências operacionais** — quando o fluxo é interrompido por razão não-clínica.

Exemplos:
- devolução total ou parcial de item
- recusa de agendamento pelo paciente ou prestador
- desmarcação após confirmação
- arquivamento por impossibilidade operacional
- pagamento não concluído no balcão
- erro de identificação (CPF, CNS)

### 6.2 Distinção entre ocorrência e evento de ledger

| Dimensão | Evento de ledger | Ocorrência |
|---|---|---|
| **Propósito** | Rastrear transições de estado do objeto | Registrar incidente para análise posterior |
| **Obrigatoriedade** | Todo evento relevante deve estar no ledger | Ocorrências são registradas quando identificadas |
| **Mutabilidade** | Imutável — nunca UPDATE/DELETE | Imutável — nunca UPDATE/DELETE |
| **Detalhe** | Estruturado (tipo de evento + dados_json) | Semi-estruturado (tipo + texto_livre + campos normalizados) |
| **Impacto no objeto** | Pode alterar status do objeto | Não altera estado do objeto diretamente |

**Relação entre os dois:**

Um mesmo incidente pode gerar **ambos**:
- um evento no ledger (ex: `item_devolvido`)
- uma ocorrência no registro (com texto_livre, motivo e contexto operacional)

O ledger registra **o que aconteceu**. O registro de ocorrências registra **por que aconteceu e o que foi feito**.

### 6.3 Estrutura conceitual da tabela `ocorrencias`

```sql
-- Esta tabela NÃO existe ainda — definição conceitual para implementação futura.
-- Não criar sem atualizar NUCLEO_SANITARIO.md e CLAUDE.md.

ocorrencias (
  id                    INTEGER PRIMARY KEY,

  -- Identificação do objeto afetado
  objeto_tipo           TEXT NOT NULL,   -- 'prescricao' | 'pedido_exame' | 'agendamento' | 'laudo'
  protocolo             TEXT NOT NULL,   -- UUID do objeto
  item_id               INTEGER NULL,    -- NULL = objeto inteiro; X = item específico

  -- Escopo institucional
  org_id                TEXT NULL,       -- conforme convenção de rollout incremental (CLAUDE.md §6b)
  unidade_id            TEXT NULL,

  -- Ator que registrou a ocorrência
  ator_tipo             TEXT NOT NULL,   -- 'prescritor' | 'paciente' | 'dispensador' | 'clinica' | 'admin'
  ator_id               TEXT NOT NULL,   -- CNS, CPF, CNPJ conforme ator_tipo

  -- Classificação da ocorrência
  tipo_ocorrencia       TEXT NOT NULL,   -- 'semantica' | 'operacional'
  subtipo_ocorrencia    TEXT NOT NULL,   -- ver vocabulário abaixo

  -- Conteúdo
  texto_livre_origem    TEXT NULL,       -- texto original, como digitado/falado
  texto_normalizado     TEXT NULL,       -- versão limpa/padronizada

  -- Terminologias envolvidas (nullable — preencher quando aplicável)
  codigo_tuss           TEXT NULL,
  codigo_cid            TEXT NULL,
  codigo_sigtap         TEXT NULL,

  -- Resolução
  decisao_tomada        TEXT NULL,       -- o que o sistema ou o operador decidiu
  justificativa         TEXT NULL,       -- motivo da decisão
  impacto_no_fluxo      TEXT NULL,       -- 'nenhum' | 'item_devolvido' | 'objeto_arquivado' | ...

  -- Metadados
  observacoes           TEXT NULL,
  data_ocorrencia       TEXT NOT NULL,   -- ISO 8601 UTC
  created_at            TEXT NOT NULL
)
```

### 6.4 Vocabulário de subtipos

**Tipo: `semantica`**

| Subtipo | Descrição |
|---|---|
| `termo_clinico_ambiguo` | Termo sem mapeamento único em TUSS/CID |
| `cid_ambiguo` | CID aplicável a múltiplas categorias |
| `tuss_sem_sigtap` | Código TUSS sem equivalente SIGTAP |
| `medicamento_sem_dci` | Prescrição por nome comercial, não DCI |
| `quantidade_inconsistente` | Quantidade incompatível com posologia declarada |

**Tipo: `operacional`**

| Subtipo | Descrição |
|---|---|
| `devolucao_item_paciente` | Item devolvido por abandono de compra |
| `devolucao_item_prestador` | Item devolvido por erro ou impossibilidade técnica |
| `devolucao_total_paciente` | Objeto inteiro devolvido pelo paciente |
| `recusa_agendamento_paciente` | Paciente cancelou antes do horário |
| `recusa_agendamento_prestador` | Prestador não pôde atender |
| `desmarcacao_apos_confirmacao` | Cancelado após confirmação (ambas as partes) |
| `arquivamento_prestador` | Prestador arquivou sem execução |
| `pagamento_nao_concluido` | Falha de pagamento no balcão |
| `erro_identificacao` | CPF, CNS ou CNPJ inconsistente com documento físico |
| `objeto_nao_encontrado` | Protocolo apresentado não localizado no sistema |

---

## 7. Ocorrência vs. estado — princípio de moderação

### 7.1 O risco de proliferar estados

Cada novo estado na máquina de estados tem um custo:

- todas as queries precisam considerar o novo estado
- adapters precisam ser atualizados
- tests precisam cobrir novas transições
- documentação precisa ser atualizada em CLAUDE.md e no DDL PostgreSQL

**Regra de moderação:**

> Só criar novo estado quando a mudança altera o **comportamento do sistema** em relação ao objeto.
> Se a mudança é apenas informacional (queremos saber o que aconteceu), usar evento de ledger + ocorrência.

### 7.2 Tabela de decisão

| Situação | Estado novo necessário? | Alternativa preferível |
|---|---|---|
| Paciente devolve prescrição inteira | Não (usa `pendente` existente) | Evento `custodia_transferida` + ocorrência |
| Item devolvido por falha técnica | Não (usa `devolvido_prescritor` existente) | Evento `item_devolvido_prescritor` + ocorrência com `subtipo = devolucao_item_prestador` |
| Agendamento desmarcado pelo paciente | Não (usa `cancelado` existente) | Evento `agendamento_cancelado` com `motivo = desmarcado_paciente` |
| Agendamento arquivado sem remarcação | Eventualmente sim — decidir em campo | Por ora: `cancelado` com `motivo = arquivado_prestador` |
| Prescrição recusada por completo antes de qualquer dispensação | Não (usa `pendente` ou `cancelada`) | Ocorrência com `subtipo = devolucao_total_paciente` |
| Pedido de exame com item não executável | Não (item fica `pendente`) | Ocorrência com `subtipo = devolucao_item_prestador` |

### 7.3 Quando criar novo estado

Um novo estado é justificado quando **pelo menos duas** das seguintes condições forem verdadeiras:

1. A UI precisa mostrar o objeto diferente naquele estado
2. Um adapter externo precisa filtrar objetos naquele estado
3. A transição de volta daquele estado requer lógica específica
4. O estado apareceu com frequência real no piloto

---

## 8. Impacto futuro na máquina de estados

Esta seção **identifica** possíveis refinamentos futuros. Nenhum estado é criado aqui.

### 8.1 Prescrição

A máquina atual cobre bem os casos digitais. Um possível refinamento futuro:

| Possível novo estado | Condição para criar |
|---|---|
| `recusada` | Se o campo revelar que o dispensador recusa a prescrição inteira com frequência e isso precisa ser rastreado separadamente de `cancelada` |
| `arquivada` | Se prescrições ficarem "em aberto" sem consumo por período longo e o sistema precisar distingui-las de `expirada` |

**Recomendação atual:** aguardar dados do campo. Os estados existentes cobrem o ciclo normal.

### 8.2 Pedido de exame

| Possível refinamento | Condição |
|---|---|
| Estado `recusado_prestador` | Se clínicas recusarem pedidos antes de agendar com frequência |
| Estado `parcialmente_executado` | Análogo a `parcialmente_dispensada` — se itens parciais forem frequentes |

### 8.3 Agendamento

O modelo atual (ver `ARQUITETURA_AGENDAMENTO.md`) cobre os casos principais. Possível refinamento:

| Possível refinamento | Condição |
|---|---|
| Campo `motivo` obrigatório em `cancelado` e `nao_compareceu` | **Alta prioridade** — deve ser implementado antes do piloto para distinguir subtipos em análise de campo |
| Estado `proposto` (agendamento aguardando aceitação do paciente) | Se o campo revelar que pacientes frequentemente não comparecem a agendamentos não confirmados |

### 8.4 Laudo

| Possível refinamento | Condição |
|---|---|
| Estado `devolvido_prescritor` no laudo | Se o fluxo de ciência revelar que prescritores frequentemente rejeitam laudos antes de tomar conduta |

### 8.5 Princípio geral

> O sistema não deve criar estados preventivamente. Cada novo estado deve nascer de um padrão observado no campo real. A máquina de estados do MVP é deliberadamente enxuta — esta é uma qualidade, não uma limitação.

---

## 9. Impacto futuro no ledger

Eventos que **podem** surgir após o piloto. Nenhum é criado agora.

| Evento futuro | Objeto | Quando ocorre |
|---|---|---|
| `objeto_devolvido_totalmente` | qualquer | Devolução integral antes de qualquer execução |
| `item_devolvido_tecnico` | prescrição / pedido | Item devolvido por impossibilidade técnica do prestador |
| `objeto_arquivado_prestador` | qualquer | Prestador encerra objeto sem execução |
| `agendamento_desmarcado_paciente` | agendamento | Paciente cancela agendamento confirmado |
| `agendamento_proposto_prestador` | agendamento | Prestador propõe data ao paciente (se fluxo de confirmação for adotado) |
| `ocorrencia_semantica_registrada` | qualquer | Ambiguidade capturada no balcão ou na clínica |
| `objeto_expirado_por_inatividade` | prescrição / pedido | Distinção entre expirado por validade e expirado por falta de uso |

**Restrição inviolável:** O ledger continua imutável. Esses eventos são adicionados quando os casos de uso reais forem implementados — nunca retroativamente.

---

## 10. Relação com adapters e piloto

### 10.1 Por que este contrato importa antes do campo

O teste de campo vai, inevitavelmente, produzir situações de interrupção:

- um paciente vai devolver uma receita
- uma clínica vai recusar um pedido
- um agendamento vai ser desmarcado com menos de 24h
- um item vai ser dispensado parcialmente

Sem este contrato, o piloto não tem como **classificar** esses eventos. A equipe vai registrar "deu erro" ou "não funcionou", mas o sistema não vai ter dados para distinguir:

- erro técnico de recusa intencional
- devolução por erro clínico de devolução por falta de estoque
- desmarcação por desistência de desmarcação para remarcar

### 10.2 O que os adapters precisarão

Quando adapters de HIS, TISS ou e-SUS forem construídos (após G4A), eles precisarão consumir eventos com semântica explícita de circulação.

Um adapter que exporta para TISS precisa distinguir:

```
procedimento executado        → faturar
procedimento não executado    → não faturar
procedimento parcialmente     → faturar proporcional
procedimento recusado         → registrar glosa / devolução
```

Sem este vocabulário formalizado, o adapter terá que inferir estado a partir de ausência de dados — o que produz inconsistências.

### 10.3 O que está pronto para o campo

| Capacidade | Estado |
|---|---|
| Emissão digital e física | ✅ |
| Dispensação total e parcial | ✅ |
| Devolução por item (dispensador → paciente / prescritor) | ✅ |
| Agendamento com cancelamento e `nao_compareceu` | ✅ |
| Laudo com ciência paciente / prescritor | ✅ |
| Registro de ocorrências | ❌ — **a implementar após piloto** |
| Campo `motivo` obrigatório em cancelamentos | ⚠️ — **recomendado antes do piloto** |

---

## 11. Sequência recomendada de implementação

### Fase imediata — antes do piloto

1. **Formalizar `motivo` em cancelamentos de agendamento**
   - Campo `motivo` em `agendamentos` (nullable inicialmente; obrigatório a partir do piloto)
   - Vocabulário: `desmarcado_paciente`, `desmarcado_prestador`, `remarcado`, `recusado_prestador`
   - Impacto: baixo (campo + evento de ledger)

2. **Formalizar vocabulário de motivos no ledger existente**
   - `custodia_transferida` já tem `dados_json` — adicionar campo `motivo` no JSON
   - Sem migração — apenas convenção para novos registros

### Fase pós-piloto (baseada em dados reais)

3. **Implementar tabela `ocorrencias`**
   - Criar model, router e endpoints básicos (POST para registrar, GET filtrado por protocolo)
   - Acoplamento leve: não altera objetos existentes

4. **Analisar padrões de interrupção coletados**
   - Quais subtipos de ocorrência foram mais frequentes?
   - Quais demandaram mudança de estado vs. apenas registro?

5. **Refinar máquina de estados com base nos dados**
   - Criar novos estados somente para padrões com frequência real e impacto operacional
   - Atualizar `domain/states*.py`, DDL PostgreSQL e CLAUDE.md

6. **Implementar eventos de ledger adicionais**
   - Somente para os eventos que emergirem como necessários no passo 5

---

## Resultado esperado

Ao final deste documento, o PicSaúde tem linguagem explícita para descrever o ciclo completo do cuidado:

```
Cuidado emitido
  └─► encerrado localmente (papel, sem circulação digital)

  └─► em circulação digital
        ├─► executado (total)
        ├─► executado parcialmente
        ├─► devolvido por item
        ├─► devolvido totalmente
        ├─► recusado (sem execução)
        └─► arquivado (sem previsão de nova tentativa)
```

E tem um caminho claro para capturar, durante o piloto, **o que aconteceu** (ledger), **por que aconteceu** (ocorrências) e **com que frequência** (análise de campo) — antes de adicionar complexidade na máquina de estados.

---

## Referências internas

| Documento | Relação |
|---|---|
| `NUCLEO_SANITARIO.md` | Contrato base de qualquer objeto sanitário |
| `MAQUINA_ESTADOS_CUSTODIA.md` | Estados e transições da prescrição |
| `ARQUITETURA_AGENDAMENTO.md` | Fluxo completo de agendamento, incluindo remarcação |
| `ARQUITETURA_EXAMES.md` | Estados do pedido de exame |
| `ARQUITETURA_LAUDO.md` | Estados do laudo |
| `ARQUITETURA_G4A.md` | Event Publishing Layer — necessária antes de qualquer adapter |
| `CLAUDE.md` | Princípios invioláveis — imutabilidade, ledger, custódia, estados |
