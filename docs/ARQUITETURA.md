# PicSaúde — Visão Arquitetural v1.0

> Documento de referência para desenvolvimento, produto e whitepaper técnico.

---

## Definição

O PicSaúde é uma **plataforma de custódia sanitária digital** baseada em
máquina de estados, onde objetos assistenciais circulam entre prescritores,
cidadãos e instituições com rastreabilidade completa, controle granular por
item e histórico imutável de eventos — permitindo emissão, renovação,
correção, dispensação parcial, devolução e auditoria sanitária sem perda
da integridade do histórico.

---

## Princípio fundamental

> No PicSaúde, nenhum objeto sanitário é editado após emissão.
> Qualquer alteração gera um novo objeto derivado, mantendo o histórico
> completo do anterior.

```
REC-001 ← REC-002 ← REC-003
```

Isso preserva rastreabilidade clínica, auditabilidade sanitária,
segurança jurídica e integridade do ledger.

---

## Objetos assistenciais

A prescrição de medicamentos é o **primeiro objeto implementado**.
O modelo é generalizável a qualquer artefato do cuidado em saúde:

| Objeto | Cadeia típica |
|---|---|
| Prescrição | emissão → custódia → dispensação |
| Exame | pedido → coleta → análise → laudo → retorno |
| Agendamento | solicitação → reserva → confirmação → comparecimento |
| Laudo | produção → assinatura → liberação → ciência |
| Internação | indicação → autorização → admissão → alta → contrarreferência |
| Encaminhamento | solicitação → referência → atendimento → contrarreferência |

---

## Modelo de custódia sanitária

Todo objeto sanitário possui:
- Identificador único (`protocolo` UUID)
- Estado atual (`status`)
- Custodiante atual (`prescricao_custodia`)
- Histórico imutável de eventos (`prescricao_eventos`)
- Possibilidade de transição controlada entre atores

### Cadeia de custódia da prescrição

```
prescritor → cidadão → dispensador → (cidadão | prescritor)
```

A cadeia **não é linear nem irrevogável**. A custódia pode avançar,
retornar, ser parcial, ser cancelada ou gerar nova emissão.

### Transições permitidas

| De | Para | Motivo |
|---|---|---|
| prescritor | paciente | Emissão digital |
| paciente | dispensador | Apresentação no balcão |
| dispensador | paciente | Abandono de compra / devolução parcial |
| dispensador | prescritor | Erro de prescrição identificado |
| paciente | prescritor | Devolução voluntária |

Cada transição gera evento imutável no ledger.

---

## Granularidade por item terapêutico

A unidade real de operação sanitária não é apenas a prescrição,
mas também **cada item terapêutico individualmente**.

```
Item A → dispensado
Item B → devolvido ao paciente   (pode tentar em outra farmácia)
Item C → devolvido ao prescritor  (erro: aguarda correção)
```

### Estados do item

```
pendente              ← estado inicial
em_custodia           ← dispensador reteve para dispensação
dispensado            ← entregue ao paciente
devolvido_paciente    ← abandono; disponível para nova dispensação
devolvido_prescritor  ← erro identificado; aguarda correção
cancelado             ← cancelamento definitivo
estornado             ← dispensação revertida após registro
```

---

## Cenários de negócio suportados

### Dispensação parcial
O cidadão não consegue pagar todos os medicamentos.
- Itens pagos → `dispensado`
- Itens não pagos → `devolvido_paciente` (volta a `pendente`)
- A prescrição não é invalidada
- Possível continuar em outra farmácia

### Erro identificado pelo paciente
Medicamento inesperado, dose incorreta, quantidade incompatível.
- Item retorna ao prescritor → `devolvido_prescritor`
- Evento `erro_prescricao_identificado` gravado no ledger
- Prescrição original preservada; nova emissão com `tipo_emissao='correcao'`

### Erro identificado pelo farmacêutico
Dose fora de padrão, concentração inexistente, posologia ambígua.
- Mesma lógica do cenário anterior
- Ator: `dispensador`

### Emissão exclusivamente física
O prescritor opta por não iniciar a cadeia digital.
- Status final: `encerrada_localmente`
- Evento: `prescricao_impressa`
- Sem custódia digital; sem transferência

---

## Ledger sanitário imutável

Toda ação relevante gera evento em `prescricao_eventos`.

| Evento | Quando |
|---|---|
| `prescricao_emitida` | POST /prescricoes |
| `prescricao_renovada` | tipo_emissao='renovacao' |
| `prescricao_corrigida` | tipo_emissao='correcao' |
| `prescricao_impressa` | emissão física |
| `custodia_transferida` | POST /custodia/transferir |
| `dispensacao_registrada` | POST /itens/{id}/dispensar (total) |
| `dispensacao_parcial` | POST /itens/{id}/dispensar (parcial) |
| `item_dispensado` | status_item → dispensado |
| `item_devolvido_paciente` | POST /itens/{id}/devolver para=paciente |
| `item_devolvido_prescritor` | POST /itens/{id}/devolver para=prescritor |
| `erro_prescricao_identificado` | devolução com motivo de erro |
| `pagamento_nao_concluido` | abandono no balcão |

O ledger deve ser imutável, auditável, cronológico e completo.

---

## Comprovante de dispensação

Gerado a cada dispensação. Campos obrigatórios:

- Identificador da dispensação
- Protocolo da prescrição
- Medicamento, dose/concentração, apresentação
- Quantidade dispensada
- Lote, fabricante, validade
- Nome e idade do paciente
- Nome e CPF do comprador
- Estabelecimento dispensador
- Data e hora da dispensação

Formatos: impressão imediata, PDF, registro interno.

---

## Relatórios de auditoria e regulação

Campos mínimos para exportação:

| Campo | Fonte |
|---|---|
| protocolo | prescricoes.protocolo |
| medicamento, dose, apresentação | prescricao_itens |
| lote, fabricante, validade | dispensacoes |
| nome/idade paciente | pacientes |
| CPF comprador | pacientes.cpf |
| data dispensação | dispensacoes.dispensado_em |
| estabelecimento | dispensacoes.cnpj_estabelecimento |
| prescritor + CNS | prescritores |
| tipo de emissão | prescricoes.tipo_emissao |
| status item/prescrição | prescricao_itens / prescricoes |

Formatos: PDF (auditoria formal), CSV (análise), DOCX (institucional).

---

## Modelo de dados (tabelas da aplicação)

```
pacientes                ← CPF, nome, telefone
prescritores             ← CNS, nome
estabelecimentos_proprios ← CNPJ, nome_fantasia
prescricoes              ← protocolo(UUID), prescritor_id, paciente_id, status,
                           tipo_emissao, origem_prescricao_id, assinatura_modo
prescricao_itens         ← prescricao_id, nome_medicamento, status_item
prescricao_eventos       ← ledger imutável (sem UPDATE/DELETE)
prescricao_custodia      ← detentor_tipo, detentor_id, item_id (NULL=prescrição inteira)
dispensacoes             ← prescricao_item_id, cnpj_estab, quantidade_dispensada
codigos_login            ← CPF, codigo OTP, expiracao
```

---

## Modelo de Assinatura e Validade Formal

A assinatura digital em prescrições no PicSaúde segue a **Resolução CFM 2.299/2021**,
que exige certificado ICP-Brasil ou serviço gov.br para validade jurídica plena.
O modelo distingue dois perfis de uso:

### Perfis de uso

| Perfil | Descrição | `assinatura_modo` |
|---|---|---|
| Operacional | Rastreada no sistema sem pretensão de validade CFM | `null` |
| CFM (ICP-Brasil) | Declara certificado digital A1/A3 ICP-Brasil | `icp_brasil_local` |
| CFM (gov.br) | Declara assinatura em nuvem gov.br | `gov_br_nuvem` |
| Física | Impressão em papel, sem cadeia digital | — (endpoint `/fisica`) |

### Nível de validade formal (`nivel_formal`)

Calculado em runtime, retornado nas respostas dos endpoints de criação.
Não armazenado no banco nesta versão (será coluna na migração PostgreSQL).

| Valor | Origem |
|---|---|
| `fisica` | Endpoint `/prescricoes/fisica`, status `encerrada_localmente` |
| `operacional` | `assinatura_modo = null` |
| `cfm_pendente` | `assinatura_modo = icp_brasil_local`; hash não armazenado (MVP) |
| `cfm_gov_br_pendente` | `assinatura_modo = gov_br_nuvem`; módulo em implantação |

### Campos obrigatórios por modo

Para prescrições com `assinatura_modo` em `MODOS_COM_VALIDADE_CFM`
(`icp_brasil_local`, `gov_br_nuvem`), o backend exige:

- **Prescritor:** `cns_prescritor`, `nome_prescritor`
- **Paciente:** `cpf_paciente` real (não sentinela `00000000000`), `nome_paciente`
- **Por item:** `nome_medicamento`, `quantidade` (int > 0), `posologia` (não vazio)

Prescrições `operacionais` (sem `assinatura_modo`) não têm essa validação —
úteis para integrações de sistemas hospitalares que não emitem certificado.

### Nota sobre assinatura — duas camadas

A assinatura no PicSaúde tem **duas camadas distintas** (registradas em
`backend/app/domain/pdf_assinatura.py:22-30`):

1. **Metadados declarados do payload canônico** (`assinatura_registrada`,
   endpoint `POST /prescricoes/{proto}/assinatura`) — camada **stub MVP**. O
   sistema aceita os metadados declarados pelo cliente sem validação
   criptográfica; o status é sempre `assinatura_pendente`.

2. **PAdES-B no PDF** (`pdf_assinado_pades`) — **implementada desde o Ticket 21**
   (`pyhanko==0.34.1`, `cryptography==44.0.0`). Assinatura criptográfica real
   embutida no PDF, validável offline (Adobe Reader / `pyhanko.sign.validation`).
   O certificado ICP-Brasil do profissional (`.pfx`) é guardado **cifrado
   (AES-256-GCM)** na tabela `prescritor_certificados` e decifrado só em memória
   no ato da assinatura. Aplica-se a: prescrição comum, receituário (controle
   especial), atestado e pedido de exame — todas via `POST /{proto}/pdf-assinado`.

A frase acima, na versão original deste documento, afirmava que a integração
ICP-Brasil real estava "planejada para versão pós-MVP". Isso descrevia o estado
**anterior** ao Ticket 21 e foi corrigido em 2026-07-24. O `assinatura_hash` da
camada declarativa segue como dívida (ver `assinatura.py:26-27`); o hash
criptográfico do PAdES vive dentro do PDF assinado.

### Fonte de verdade

```
backend/app/domain/assinatura.py
```

Novos modos ou alterações nas regras de assinatura devem ser feitos
exclusivamente nesse arquivo, com reflexo nesta seção e no DDL PostgreSQL.

---

## Banco de dados

- **Atual:** SQLite em `data/pix_saude_pe.db`
- **Futuro:** PostgreSQL (DDL em `docs/picsaude_ddl_postgres_v1.sql`)
- CNES (dados públicos) e aplicação coexistem no mesmo banco SQLite
