# PicSaúde — Arquitetura do Agendamento Atomizado de Exames

> **Status:** Documento arquitetural ativo — v1.0
> **Ticket:** 51
> **Classificação de contribuição:** `module` — novo padrão de circulação sobre módulo de exames existente
> **Pré-requisitos:**
> - `NUCLEO_SANITARIO.md` — contrato de objetos sanitários
> - `ARQUITETURA_EXAMES.md` — Tickets 14–17
> - `ARQUITETURA_AGENDAMENTO.md` — Ticket 28
> - `CIRCULACAO_ATOMIZADA.md` — Ticket 44
> - `CIRCULACAO_E_OCORRENCIAS.md` — Ticket 40
> - `CLAUDE.md` §3 (custódia explícita), §4 (dispensação parcial como modelo), §5b (contrato de estados)
> **Implementação:** Tickets 52–57

---

## Mapa rápido

| Tópico | Seção |
|---|---|
| O problema do mundo real | 1 |
| O que permanece uno | 2 |
| O que se atomiza | 3 |
| A nova entidade: `circulacao_diagnostica` | 4 |
| Seleção dos exames pelo paciente | 5 |
| Privacidade operacional | 6 |
| Máquina de estados | 7 |
| Remarcação | 8 |
| Relação com o agendamento atual | 9 |
| Relação com os itens do pedido | 10 |
| Chaves do fluxo | 11 |
| Não confirmação do paciente | 12 |
| Eventos futuros de ledger | 13 |
| Relação com Ticket 40 (ocorrências) | 14 |
| Critérios de projeto | 15 |
| Sequência de implementação recomendada | 16 |
| Resumo executivo | 17 |

---

## 1. O problema do mundo real

O modelo atual de agendamento trata o pedido de exame como bloco rígido:
um pedido, um laboratório, um agendamento. Isso não reflete a prática.

Na realidade:

- Um mesmo pedido pode conter exames que o paciente não quer ou não consegue
  fazer no mesmo lugar no mesmo momento (hemograma pode ser feito na UBS;
  ressonância só em clínica especializada)
- Laboratórios diferentes têm infraestrutura para partes diferentes do pedido
- O paciente pode querer fazer alguns exames urgentes agora e outros depois
- Um laboratório pode aceitar parte do pedido e rejeitar o restante por capacidade
  ou falta de equipamento
- Agendar o pedido inteiro como bloco rígido força o paciente a fragmentar o pedido
  criando múltiplos pedidos novos — gerando redundância clínica e auditoria corrompida

**O problema central:** o pedido é uno clinicamente, mas sua execução é
distribuída operacionalmente. O modelo atual não tem como expressar essa diferença
sem violar a unidade do pedido.

**A consequência prática sem essa arquitetura:** o paciente é forçado a escolher
entre um único laboratório para todos os exames (perda de autonomia) ou criar
múltiplos pedidos derivados para subconjuntos (poluição clínica, rastreabilidade
fragmentada).

---

## 2. O que permanece uno

O pedido de exame **não é fragmentado** como ato clínico. Esta é uma invariante
inviolável do modelo.

O pedido continua sendo:

| Dimensão | Garantia |
|---|---|
| 1 ato clínico | Assinado uma vez, pelo prescritor, com sua responsabilidade |
| 1 protocolo | UUID único, imutável, base de toda rastreabilidade |
| 1 contexto diagnóstico | Indicação clínica e prioridade pertencem ao pedido inteiro |
| 1 documento-fonte | O PDF institucional é do pedido, não dos subconjuntos |

**Consequência direta:** a atomização não cria novos pedidos, não cria novos
atos médicos, não divide a responsabilidade do prescritor. O que se cria é um
objeto operacional intermediário que referencia um subconjunto dos itens do pedido.

Analogia com o modelo de prescrição: assim como na circulação atomizada da
prescrição (Ticket 44) a receita permanece una e cada medicamento recebe seu
próprio token de circulação, aqui o pedido permanece uno e cada subconjunto
de exames enviado a um laboratório recebe sua própria entidade de circulação.

---

## 3. O que se atomiza

O que se atomiza é exclusivamente a **circulação operacional dos itens**, e não
o pedido.

Podem ser atomizados por subconjunto:

| Etapa operacional | Atomizável? |
|---|---|
| Envio ao laboratório | Sim — paciente escolhe quais itens envia e para onde |
| Proposta de agendamento | Sim — laboratório propõe para o subconjunto recebido |
| Confirmação do paciente | Sim — paciente confirma por subconjunto |
| Desmarcação | Sim — por subconjunto, sem colapsar o pedido |
| Remarcação | Sim — nova proposta derivada para o mesmo subconjunto |
| Execução / coleta | Sim — laboratório registra coleta por subconjunto |

O que **não se atomiza:**

| Dimensão | Motivo |
|---|---|
| Identidade clínica do pedido | Ato médico é indivisível |
| Indicação clínica | Pertence ao pedido inteiro |
| Assinatura do prescritor | Não pode ser fracionada |
| Protocolo público | UUID único |

---

## 4. A nova entidade: `circulacao_diagnostica`

### Nome adotado e justificativa

O nome escolhido é **`circulacao_diagnostica`**.

Alternativas consideradas:

| Nome | Problema |
|---|---|
| `lote_circulacao_exames` | "lote" sugere operação logística, não sanitária |
| `chave_circulacao_diagnostica` | Confunde entidade com o artefato de autenticação (a chave) |
| `agendamento_atomizado` | Assume o agendamento como finalidade; a entidade precede e pode não gerar agendamento concreto |
| `circulacao_diagnostica` | Descreve o fenômeno corretamente: circulação de um objeto diagnóstico entre atores |

O nome `circulacao_diagnostica` é consistente com o vocabulário do sistema:
- `prescricao_custodia` — circulação de prescrições
- `tokens_apresentacao` — circulação de autorização de dispensação
- `circulacao_atomizada` — circulação por item de prescrição (Ticket 44)

### O que essa entidade representa

`circulacao_diagnostica` é o objeto que sustenta a interação entre paciente
e laboratório em torno de um subconjunto específico de exames de um pedido.

Ela:
- referencia o pedido de origem
- referencia o paciente
- referencia os itens selecionados (via tabela de vínculo)
- referencia o laboratório destinatário
- carrega a chave de circulação
- tem estados e ledger próprios
- tem validade

Ela **não é** o agendamento concreto. Ela **antecede** o agendamento.

### Por que não basta reutilizar o agendamento atual

O agendamento atual (Ticket 28) é um objeto sanitário leve que representa
uma marcação concreta já acordada — ele pressupõe que ambas as partes
já concordaram com data, hora e local.

A nova entidade resolve um problema diferente: ela representa a **intenção
de circulação** do paciente antes de qualquer acordo. Ela é o meio pelo qual:

1. o paciente declara quais exames quer realizar em qual laboratório
2. o laboratório recebe o subconjunto e tem informação suficiente para propor
3. a proposta do laboratório pode gerar — ou não — um agendamento concreto

Forçar o agendamento atual a representar essa etapa anterior criaria:
- estado `selecionado` sem significado em agendamentos concretos
- agendamentos sem data/hora (impedindo a invariante do objeto)
- confusão semântica entre "proposta recebida" e "agendamento confirmado"

A separação é necessária e limpa.

---

## 5. Seleção dos exames pelo paciente

### Fluxo de seleção

1. O paciente acessa seu pedido de exame via `cidadao.html`
2. Visualiza os itens com `status_item = 'pendente'`
3. Seleciona um subconjunto (um ou mais itens)
4. Informa o laboratório destinatário (CNES ou identificador interno)
5. O sistema gera uma `circulacao_diagnostica` e emite a chave de circulação

### O que a entidade referencia

```
circulacao_diagnostica
  ├── pedido_id          → pedido de exame de origem
  ├── paciente_id        → paciente que selecionou
  ├── laboratorio_id     → laboratório destinatário
  ├── chave_circulacao   → token de circulação (UUID ou código legível)
  ├── status             → máquina de estados própria (ver seção 7)
  ├── validade           → data de expiração da chave
  └── criado_em

circulacao_diagnostica_itens
  ├── circulacao_id      → FK → circulacao_diagnostica
  └── pedido_item_id     → FK → pedido_exame_itens
```

### Restrição de seleção

Um item do pedido com `status_item = 'agendado'` ou `status_item = 'coletado'`
não pode ser selecionado para nova circulação. Apenas itens `pendente` ou
`devolvido_laboratorio` (futuro) são elegíveis.

O mesmo item **não pode pertencer a duas circulações ativas simultaneamente**.
A constraint deve ser verificada na criação.

---

## 6. Privacidade operacional

### Princípio

> O laboratório deve receber apenas o subconjunto de exames que o paciente enviou.
> O pedido completo não é revelado ao laboratório, a menos que o paciente envie
> todos os itens no mesmo subconjunto.

### O que o laboratório vê ao receber a chave

| Campo | Visível ao laboratório? |
|---|---|
| Nome dos exames selecionados | Sim |
| Código TUSS / SIGTAP dos exames selecionados | Sim |
| Indicação clínica parcial (opcional, decisão do prescritor) | Configurável |
| Nome do paciente | Sim |
| CNS do paciente | Sim |
| Data de validade da chave | Sim |
| Prioridade dos itens selecionados | Sim |
| Total de itens do pedido original | Não |
| Outros itens não selecionados | Não |
| Nome do prescritor | Sim (necessário para o laboratório) |
| CRM / conselho do prescritor | Sim (necessário para o laboratório) |
| Outros pedidos do paciente | Não |

### Alinhamento com o modelo de prescrição

Este princípio é idêntico ao da circulação atomizada da prescrição (Ticket 44):
o dispensador vê apenas o item que o paciente apresenta, não a receita inteira.
A consistência é intencional.

### Exceção documentada

Se o pedido tiver apenas 1 item e o paciente o seleciona, o laboratório
recebe efetivamente o pedido completo. Isso é correto e não viola o princípio:
o paciente revelou tudo o que havia para revelar.

---

## 7. Máquina de estados da `circulacao_diagnostica`

### Estados

```
selecionado
  → enviado_laboratorio
    → proposta_recebida
      → confirmado_paciente   → realizado  (terminal)
      → desmarcado_paciente               (terminal)
    → desmarcado_laboratorio              (terminal)
    → arquivado_laboratorio               (terminal)
  → expirado                              (terminal — validade ultrapassada)
```

### Descrição de cada estado

| Estado | Descrição | Quem transita |
|---|---|---|
| `selecionado` | Paciente selecionou os itens; chave gerada ainda não enviada | Sistema (automático) |
| `enviado_laboratorio` | Paciente enviou/apresentou a chave ao laboratório | Paciente |
| `proposta_recebida` | Laboratório propôs data, hora, unidade e preparo | Laboratório |
| `confirmado_paciente` | Paciente aceitou a proposta | Paciente |
| `realizado` | Laboratório registrou a coleta efetiva | Laboratório |
| `desmarcado_paciente` | Paciente desmarcou antes ou após confirmação | Paciente |
| `desmarcado_laboratorio` | Laboratório desmarcou (não confirmação, incapacidade, etc.) | Laboratório |
| `arquivado_laboratorio` | Laboratório arquivou sem proposta ou após insucesso | Laboratório |
| `expirado` | Validade da chave ultrapassada sem realização | Sistema |

### Estados terminais

```
realizado · desmarcado_paciente · desmarcado_laboratorio · arquivado_laboratorio · expirado
```

### Estado vs. ocorrência

| Evento | Modelagem |
|---|---|
| "Laboratório solicitou confirmação 1 dia antes" | Ocorrência — não vira estado |
| "Paciente não respondeu à confirmação prévia" | Ocorrência — habilita ação do laboratório |
| "Laboratório desmarca por não confirmação" | Transição de estado: `confirmado_paciente → desmarcado_laboratorio` |
| "Preparo do exame informado" | Campo na proposta — não vira estado |
| "Laboratório atualiza horário da proposta" | Cria nova proposta derivada (ver seção 8) |

**Princípio:** se o evento não muda o que as partes podem fazer a seguir,
é ocorrência. Se muda, é estado.

---

## 8. Remarcação

### Decisão

Remarcação **cria uma nova `circulacao_diagnostica` derivada**, com
`origem_circulacao_id` apontando para a anterior. A entidade anterior é
encerrada no estado `desmarcado_laboratorio` ou `desmarcado_paciente`.

Este é o padrão estabelecido em todo o PicSaúde:

```
REC-001 (original) ← REC-002 (correção)     [prescrição]
AGD-001 (original) ← AGD-002 (remarcação)   [agendamento]
CDD-001 (original) ← CDD-002 (remarcação)   [circulacao_diagnostica]
```

### Por que não usar estado `remarcado`

Um estado `remarcado` criaria ambiguidade:
- A proposta anterior ainda vale?
- Qual é a data vigente?
- O paciente confirma o quê?

Com objeto derivado, cada `circulacao_diagnostica` tem exatamente uma proposta
vigente, uma chave, um ciclo de confirmação. A cadeia de derivações é auditável.

### Fluxo de remarcação

```
CDD-001: confirmado_paciente
  → paciente ou laboratório inicia remarcação
  → CDD-001 encerra: desmarcado_paciente ou desmarcado_laboratorio
  → CDD-002 criada: selecionado, com origem_circulacao_id = CDD-001.id
  → itens do pedido: permanecem agendado até confirmação de CDD-002
```

### Limite de remarcações

Nenhum limite técnico nesta versão. Monitorável via cadeia de `origem_circulacao_id`.
Política operacional (ex: máximo de 3 remarcações) pode ser implementada como
regra de negócio sem alterar o modelo de dados.

---

## 9. Relação com o agendamento atual

### Decisão: Opção B — a nova entidade antecede e alimenta o agendamento

A `circulacao_diagnostica` **antecede** o objeto `agendamento` existente
(Ticket 28). Quando a proposta do laboratório é confirmada pelo paciente,
ela pode gerar — opcionalmente — um `agendamento` concreto.

```
circulacao_diagnostica [enviado → proposta_recebida → confirmado_paciente]
  → gera → agendamento [criado → confirmado → realizado]
```

### Por que essa escolha

| Critério | Opção A (substituir) | Opção B (anteceder) |
|---|---|---|
| Impacto na arquitetura existente | Quebra o agendamento atual | Zero impacto |
| Semântica | Confunde proposta com marcação | Separa claramente proposta e marcação |
| Implementação em fases | Tudo de uma vez | Pode entregar em fases |
| Rastreabilidade | Perde contexto da proposta | Mantém histórico completo |

### Quando o agendamento é criado

O `agendamento` concreto é criado no momento em que o paciente confirma
a proposta. Ele recebe:
- `origem_circulacao_id` — vínculo com a entidade que o gerou
- `org_id` + `unidade_id` do laboratório
- data, hora e local da proposta confirmada

### MVP simplificado

No MVP, a criação do `agendamento` pode ser opcional. A `circulacao_diagnostica`
com `status = 'confirmado_paciente'` é suficiente para que o laboratório
identifique o paciente e realize a coleta. O `agendamento` como objeto separado
pode ser criado na fase 3 sem alterar o modelo central.

---

## 10. Relação com os itens do pedido

### Princípio de moderação

Evitar explosão prematura de estados nos itens. O item do pedido deve
refletir apenas o que é relevante para a rastreabilidade clínica, não
cada passo operacional da circulação.

### Mapa de transições por evento

| Evento | Transição no item | Modelagem |
|---|---|---|
| Paciente seleciona item | Nenhuma | Ocorrência — item ainda não foi entregue a ninguém |
| `circulacao_diagnostica` criada | Nenhuma | Ocorrência — proposta ainda não existe |
| Laboratório propõe | Nenhuma | Ocorrência — proposta não é coleta |
| Paciente confirma proposta | `pendente → agendado` | Transição de estado — há compromisso bilateral |
| Laboratório registra coleta | `agendado → coletado` | Transição de estado — dado clínico gerado |
| Paciente desmarca | `agendado → pendente` | Retorno — item disponível para nova circulação |
| Laboratório desmarca | `agendado → pendente` | Retorno — item disponível para nova circulação |
| `circulacao_diagnostica` expira | Sem efeito no item se não confirmada | Itens permanecem `pendente` |

### Consequência

Um item do pedido transita para `agendado` apenas quando há confirmação bilateral.
Antes disso, a existência de uma `circulacao_diagnostica` ativa referenciando
o item é rastreável via JOIN — sem necessidade de novo estado no item.

Isso preserva a coerência com o Ticket 40 (CIRCULACAO_E_OCORRENCIAS.md) e
evita estados intermediários sem semântica clínica.

---

## 11. Chaves do fluxo

### Decisão: uma chave principal com semântica de uso por fase

Adotado um modelo de **chave principal única** (`chave_circulacao`) associada
à `circulacao_diagnostica`, com uso diferenciado por fase.

A chave é um UUID gerado no momento da seleção, apresentável como:
- código alfanumérico legível (para comunicação humana, ex: SMS)
- QR Code (para leitura no balcão do laboratório)

### Uso por fase

| Fase | Ator | Uso da chave |
|---|---|---|
| Paciente envia ao laboratório | Paciente | Apresenta `chave_circulacao` ao laboratório |
| Laboratório acessa subconjunto | Laboratório | Lê `chave_circulacao` via endpoint público |
| Laboratório devolve proposta | Laboratório | Usa `chave_circulacao` como identificador no POST |
| Paciente confirma | Paciente | Confirma via `chave_circulacao` |
| Confirmação 1 dia antes | Ambos | Ocorrência registrada — mesma chave, sem nova chave |

### Por que não chaves derivadas

Chaves derivadas por fase (chave de envio ≠ chave de proposta ≠ chave de confirmação)
aumentariam a segurança em contextos de alta adversarialidade, mas adicionariam
complexidade sem benefício imediato no contexto do PicSaúde. O modelo de uma chave
única é auditável, implementável e suficiente para o MVP.

Esta decisão pode ser revisada quando o onboarding institucional de laboratórios
for implementado com JWT (ver CLAUDE.md §6b).

### Confirmação 1 dia antes

A confirmação antecipada (D-1) é uma **ocorrência operacional**, não um estado.
Ela deve ser registrada no ledger (`circulacao_confirmacao_previa`) mas não
altera o estado da `circulacao_diagnostica`. Seu efeito prático é habilitar a
ação de desmarcação pelo laboratório se o paciente não responder.

---

## 12. Não confirmação do paciente

### Cenário

1. Laboratório propõe → `proposta_recebida`
2. Laboratório envia confirmação D-1 (ocorrência)
3. Paciente não confirma nem desmarca
4. Laboratório decide desmarcar

### Modelagem adotada

A não confirmação é tratada como **combinação de ocorrência + ação explícita**:

1. Registro da ocorrência `paciente_nao_confirmou` no ledger (sem mudar estado)
2. Ação explícita do laboratório: `POST /circulacao/{chave}/desmarcar`
3. Transição: `proposta_recebida → desmarcado_laboratorio`

**Não existe timeout automático** que mude o estado sem ação humana. Esta é
uma decisão deliberada: automatismos que mudam estados de objetos clínicos
sem ação de um ator identificado violam o princípio de rastreabilidade do ledger.

O laboratório pode (e deve) registrar o motivo da desmarcação:
`motivo = 'paciente_nao_confirmou'`.

### Consequência nos itens

Itens em `agendado` retornam a `pendente`.
Itens ainda em `pendente` (proposta não confirmada) permanecem `pendente`.

---

## 13. Eventos futuros de ledger

Estes eventos devem ser criados nos Tickets 52–55. Não implementar antes do DDL.

| Evento | Quando ocorre | Ator |
|---|---|---|
| `circulacao_diagnostica_criada` | Paciente seleciona itens e gera chave | Paciente |
| `lote_exames_enviado_laboratorio` | Paciente apresenta chave ao laboratório | Paciente |
| `proposta_agendamento_recebida` | Laboratório registra proposta | Laboratório |
| `agendamento_confirmado_paciente` | Paciente confirma proposta | Paciente |
| `circulacao_confirmacao_previa` | Confirmação D-1 registrada | Laboratório ou Sistema |
| `paciente_nao_confirmou` | Laboratório registra ausência de confirmação | Laboratório |
| `agendamento_desmarcado_paciente` | Paciente desmarca | Paciente |
| `agendamento_desmarcado_laboratorio` | Laboratório desmarca | Laboratório |
| `lote_exames_arquivado_laboratorio` | Laboratório arquiva sem proposta | Laboratório |
| `lote_exames_realizado` | Laboratório registra coleta efetiva | Laboratório |
| `circulacao_exames_remarcada` | Nova circulação derivada criada | Qualquer ator |
| `circulacao_exames_expirada` | Validade ultrapassada | Sistema |

Todos os eventos são INSERT em tabela de ledger. Sem UPDATE, sem DELETE.

---

## 14. Relação com Ticket 40 (ocorrências)

O Ticket 40 (`CIRCULACAO_E_OCORRENCIAS.md`) formalizou o vocabulário para
situações entre emissão e execução. Este modelo de agendamento atomizado
é a primeira implementação concreta desse vocabulário no módulo de exames.

### Mapeamento de ocorrências do Ticket 40 para este fluxo

| Ocorrência (Ticket 40) | Equivalente neste modelo |
|---|---|
| Desmarcação | `desmarcado_paciente` / `desmarcado_laboratorio` |
| Arquivamento | `arquivado_laboratorio` |
| Não confirmação do paciente | Ocorrência `paciente_nao_confirmou` + ação do laboratório |
| Remarcação | Nova `circulacao_diagnostica` derivada |
| Falha de execução parcial | Registro de coleta parcial no momento de `realizado` |
| Devolução operacional do subconjunto | Item retorna a `pendente`; nova circulação pode ser criada |

### Extensão do vocabulário

Este ticket adiciona ao vocabulário do Ticket 40:
- Proposta como etapa distinta da marcação
- Confirmação bilateral como precondição da coleta
- Arquivamento sem proposta como saída válida

Esses conceitos devem ser incorporados em futura revisão de `CIRCULACAO_E_OCORRENCIAS.md`.

---

## 15. Critérios de projeto

Estes critérios são invariantes do modelo. Qualquer implementação que viole
um deles deve ser rejeitada antes de ser mergeada.

1. **Pedido permanece uno.** A `circulacao_diagnostica` nunca substitui,
   divide ou fragmenta o pedido de exame como ato clínico.

2. **Circulação pode ser atomizada por subconjunto.** O paciente tem autonomia
   para escolher quais itens envia, para onde e quando.

3. **Privacidade é por subconjunto.** O laboratório nunca recebe itens que
   o paciente não enviou explicitamente.

4. **Remarcação não bagunça o estado.** Toda remarcação cria objeto derivado.
   Nunca um estado `remarcado` em objeto existente.

5. **Preferir ocorrência e objeto derivado a explosão de estados.** Se um evento
   não muda o que os atores podem fazer, é ocorrência, não estado.

6. **O modelo deve ser implementável em fases.** Nenhuma fase deve exigir
   que todas as outras estejam prontas para ser útil isoladamente.

7. **Automações não transitam estados sem ator identificado.** Todo evento
   no ledger deve ter um ator responsável (paciente, laboratório ou sistema
   com motivo documentado).

8. **Item do pedido transita para `agendado` apenas com confirmação bilateral.**
   A existência de uma circulação ativa não é suficiente para mudar o estado do item.

---

## 16. Sequência de implementação recomendada

### Fase 1 — Estrutura de dados (Ticket 52)

- Tabela `circulacoes_diagnosticas`
- Tabela `circulacao_diagnostica_itens`
- Tabela `circulacao_diagnostica_eventos` (ledger próprio)
- Campo `origem_circulacao_id` em `circulacoes_diagnosticas`
- Estados da nova entidade em `backend/app/domain/states.py`
- `init_tables.py` atualizado e executado

**Entrega verificável:** tabelas existem no banco; estados declarados em `states.py`.

### Fase 2 — Backend: emissão da chave (Ticket 53)

- `POST /pedidos/{proto}/circulacao` — paciente seleciona itens e gera chave
- `GET /circulacao/{chave}` — laboratório consulta subconjunto (visão restrita)
- Evento: `circulacao_diagnostica_criada`, `lote_exames_enviado_laboratorio`
- Validação: item não pode estar em circulação ativa simultânea

**Entrega verificável:** chave gerada, laboratório consulta apenas subconjunto.

### Fase 3 — Backend: proposta do laboratório (Ticket 54)

- `POST /circulacao/{chave}/proposta` — laboratório registra proposta
- `POST /circulacao/{chave}/confirmar` — paciente confirma
- `POST /circulacao/{chave}/desmarcar` — paciente ou laboratório desmarca
- Transição de itens: `pendente → agendado` na confirmação
- Criação opcional de `agendamento` concreto (Ticket 28) na confirmação
- Eventos: `proposta_agendamento_recebida`, `agendamento_confirmado_paciente`,
  `agendamento_desmarcado_*`

**Entrega verificável:** ciclo proposta → confirmação → item `agendado` funcional.

### Fase 4 — Backend: realização e remarcação (Ticket 55)

- `POST /circulacao/{chave}/realizar` — laboratório registra coleta
- Transição de itens: `agendado → coletado`
- `POST /circulacao/{chave}/remarcar` — cria nova `circulacao_diagnostica` derivada
- `POST /circulacao/{chave}/arquivar` — laboratório arquiva sem proposta
- Eventos: `lote_exames_realizado`, `circulacao_exames_remarcada`,
  `lote_exames_arquivado_laboratorio`

**Entrega verificável:** coleta registrada; remarcação cria objeto derivado auditável.

### Fase 5 — Frontend do paciente (Ticket 56)

Em `cidadao.html`:
- Seleção de itens do pedido
- Geração e exibição da chave (texto + QR Code)
- Tela de proposta recebida (data, hora, preparo)
- Ação de confirmar
- Ação de desmarcar

**Entrega verificável:** paciente completa o fluxo de seleção → confirmação.

### Fase 6 — Frontend da clínica/laboratório (Ticket 57)

Em `clinica.html`:
- Leitura de chave de circulação
- Exibição do subconjunto recebido (visão restrita)
- Formulário de proposta (data/hora/unidade/preparo)
- Ação de remarcar
- Ação de arquivar
- Registro de realização/coleta

**Entrega verificável:** laboratório completa o fluxo de recepção → proposta → coleta.

---

## 17. Resumo executivo

Este resumo sintetiza as decisões arquiteturais centrais do documento.
É a referência para validação antes da implementação.

### 1. Unidade do pedido

O pedido de exame permanece um único ato clínico, com protocolo único,
indicação clínica única e assinatura única. A atomização não cria novos pedidos.

### 2. Entidade intermediária escolhida

**`circulacao_diagnostica`** — objeto operacional que representa a intenção do
paciente de realizar um subconjunto de exames em um laboratório específico.
Antecede e pode alimentar o agendamento concreto. Não substitui o pedido nem
o agendamento existente.

### 3. Máquina de estados

```
selecionado → enviado_laboratorio → proposta_recebida
  → confirmado_paciente → realizado           [terminal]
  → desmarcado_paciente                       [terminal]
  → desmarcado_laboratorio                    [terminal]
  → arquivado_laboratorio                     [terminal]
  → expirado                                  [terminal]
```

Confirmação D-1 e não confirmação do paciente são **ocorrências**, não estados.

### 4. Remarcação

Remarcação cria nova `circulacao_diagnostica` derivada com `origem_circulacao_id`.
Nunca um estado `remarcado` em objeto existente. Padrão idêntico ao restante do sistema.

### 5. Relação com o agendamento atual

**Opção B adotada:** `circulacao_diagnostica` antecede o agendamento. Quando o
paciente confirma uma proposta, pode ser criado um `agendamento` concreto
(Ticket 28). No MVP, o `agendamento` concreto é opcional — a circulação confirmada
é suficiente para a operação do laboratório.

### 6. Privacidade por subconjunto

O laboratório recebe apenas os itens que o paciente enviou explicitamente.
O pedido completo não é revelado. Princípio idêntico ao da circulação atomizada
da prescrição (Ticket 44).

### 7. Eventos futuros de ledger mapeados

12 eventos mapeados (seção 13). Todos seguem o padrão de ledger imutável do sistema.
Nenhum altera estados diretamente — cada evento é consequência de ação de um ator.

### 8. Sequência de implementação

6 fases: DDL → backend emissão → backend proposta → backend realização →
frontend paciente → frontend laboratório. Cada fase é útil isoladamente e
não bloqueia o núcleo sanitário existente.
