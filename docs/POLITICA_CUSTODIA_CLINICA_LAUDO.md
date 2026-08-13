# Política de Custódia Clínica do Laudo

| Campo | Valor |
|---|---|
| **Classificação** | `local-extension` / `docs` — declara política e mapeia o existente; **não altera semântica clínica** (estados, ledger, custódia) |
| **Origem** | Decisão #2 da demo Laboratório (`planejamento/demo-laboratorio-laudo-cidadao/`, Ticket A) |
| **Vigência** | 2026-08-13 |
| **Escopo** | Objeto sanitário `laudo`. Não altera prescrição, pedido de exame, atestado |

---

## 1. O princípio

> **A custódia clínica do laudo é do cidadão. O laboratório guarda o rastro forense — protocolo,
> hash SHA-256, ledger imutável, cadeia de custódia — e o mínimo legal exigido do Responsável
> Técnico.**

Duas frases que a política **não** diz, de propósito:

- **Não** dizemos "o laboratório não armazena dados". Diríamos uma ilegalidade: RDC 302/2005,
  a Resolução CFM 2.052/2013 e a própria LGPD **obrigam** o laboratório a reter registros por prazo
  determinado. Prometer zero seria prometer o que a norma proíbe.
- **Não** dizemos que o cidadão é o único detentor. O cidadão detém a **custódia clínica** — posse e
  acesso primário ao conteúdo. O laboratório detém o **rastro** e o mínimo legal do RT. São coisas
  distintas, e a distinção é o conteúdo desta política.

O que muda em relação à prática comum do setor não é a retenção — é **quem tem a posse primária**.
No modelo corrente, o laudo nasce e morre no sistema do laboratório e o cidadão recebe uma cópia. No
PicSaúde, o laudo é **transferido** ao cidadão por um ato registrado, e o que fica no laboratório é o
suficiente para provar o que aconteceu, não para reter o conteúdo como ativo.

---

## 2. Isto não é teoria — mapeamento ao backend existente

Cada afirmação da política já é materializada por código em produção. As âncoras abaixo foram
conferidas em 2026-08-13.

### 2.1 A custódia passa ao cidadão por ato explícito

`POST /laudos/{proto}/liberar` (`backend/app/routers/laudos.py:771`) transiciona
`assinado → liberado` e grava a transferência de posse em `laudo_custodia`
(`laudos.py:815-822`), com `de = <cnpj_prestador>` e `para = 'paciente'`.

O CNPJ gravado é o da **unidade autenticada**, não um valor declarado no corpo da requisição:
quando quem libera é o `dispensador`, o CNPJ vem do JWT e o payload é ignorado
(`laudos.py:796`, TICKET-C). Posse provada, não posse declarada — sem isso, a cadeia de custódia
não valeria como prova.

### 2.2 O rastro é imutável

`laudo_eventos` é ledger append-only. A imutabilidade **não é convenção de código**: está declarada
em `backend/app/domain/ledger_imutabilidade.py:57` e instalada como **trigger de banco** nos dois
dialetos (SQLite e PostgreSQL) por migração Alembic — conforme CLAUDE.md §9. O banco **recusa**
`UPDATE` e `DELETE` na tabela; não há endpoint, script ou caminho administrativo que os aceite.

Guarda executável: `backend/tests/test_ledger_imutabilidade.py` (gate próprio no
`.github/workflows/gates.yml`, rodando nos dois dialetos).

### 2.3 O documento tem impressão digital

`assinatura_hash` é o SHA-256 do documento canônico, calculado em `_calcular_hash`
(`laudos.py:158`) e gravado na criação (`laudos.py:526-528`). É o que permite ao cidadão — ou a um
auditor — provar que o laudo em mãos é o mesmo que o laboratório emitiu, **sem depender do
laboratório para isso**. O hash viaja no PDF institucional.

### 2.4 Quem produziu fica registrado, e não se confunde com quem assina

O `autor_id` é **sempre** o Responsável Técnico (CNS). Quando a unidade produz em nome dele, o
evento `laudo_criado` grava `produzido_por` e `produzido_por_cnpj` (`laudos.py:539-541`), e
`laudo_liberado` grava `liberado_por` (`laudos.py:829-831`). A pergunta de auditoria — *foi a
unidade ou o próprio RT?* — tem resposta no ledger, não em inferência.

### 2.5 O cidadão tem a carteira, não um portal do laboratório

`GET /paciente/laudos` (`backend/app/routers/auth.py:512`) serve os laudos do cidadão autenticado.
A carteira é renderizada em `cidadao.html:693-756` — listar, baixar o PDF (`baixarPdfLaudo`,
`:751`) e **dar ciência** (`darCienciaLaudo`, `:742`).

A ciência é ato **do cidadão**. Quem produziu o laudo não dá ciência por ele: `ciencia-paciente`
exige papel `paciente` e valida que o CPF autenticado é o do laudo
(`laudos.py:_assert_paciente_dono`). O dispensador que produziu o laudo é barrado ali — foi mantido
fora dessa superfície de propósito no TICKET-C.

---

## 3. Base regulatória da retenção mínima

A retenção do laboratório não é escolha de produto — é obrigação. Os três instrumentos que a impõem:

### RDC Anvisa nº 302/2005 — funcionamento de laboratórios clínicos

Impõe ao laboratório a guarda de registros dos serviços prestados, incluindo laudos e dados que
permitam a **rastreabilidade** do exame, por prazo definido, sob responsabilidade do serviço. O
laboratório precisa poder reconstituir o que fez — a norma é sobre rastreabilidade, e é exatamente
o que o ledger + cadeia de custódia entregam.

### Resolução CFM nº 2.052/2013 — responsabilidade técnica

Vincula o laudo a um **Responsável Técnico identificado**, que responde pelo conteúdo. Um laudo sem
RT identificável é um laudo sem responsável — por isso o `autor_id` é sempre o RT, e por isso a
unidade que opera a tela **declara** o CNS do RT em vez de assumir a autoria.

### LGPD (Lei 13.709/2018)

Impõe **minimização** (art. 6º, III) e assegura direitos ao titular, mas **não revoga** a retenção
obrigatória do controlador: o art. 16, I, ressalva expressamente a conservação de dados para
cumprimento de obrigação legal ou regulatória. Minimização e retenção legal convivem — e a forma de
fazê-las conviver é exatamente esta política: reter o **mínimo com finalidade legal** (rastro
forense + registro do RT), e dar ao titular a **posse primária** do conteúdo clínico.

> Este documento não é parecer jurídico. Descreve como a arquitetura se posiciona diante dessas
> normas; a validação jurídica institucional é responsabilidade de quem opera a instância.

---

## 4. Exceção documentada ao NUCLEO_SANITARIO

O `NUCLEO_SANITARIO.md` trata custódia como posse única e transferível. O laudo introduz um
refinamento que precisa ficar declarado para não ser lido como incoerência:

> **Custódia clínica** (posse e acesso primário ao conteúdo) e **retenção legal** (rastro forense +
> mínimo do RT) são camadas distintas. A transferência da primeira ao cidadão **não extingue** a
> segunda no laboratório.

Isto é exceção **legítima e nomeada**, no espírito da seção "O que o Laudo Revela sobre o Núcleo" de
`docs/ARQUITETURA_LAUDO.md` — em particular o Refinamento 3, que já registrou que a custódia do
laudo nasce no prestador, e não no prescritor. A presente política é a contrapartida: onde ela
**termina**.

Nenhum estado novo. Nenhuma tabela nova. Nenhuma alteração de transição. A cadeia
`prestador → paciente` já existente é suficiente para expressar a política inteira.

---

## 5. O que esta política não autoriza

- **Não** autoriza o laboratório a reter o conteúdo clínico como ativo comercial. A vedação a
  monetização de dado do paciente é `ETHICS.md`, com guarda executável em
  `backend/tests/test_guardrail_sem_monetizacao.py`.
- **Não** autoriza exportação em massa. Guarda executável em
  `backend/tests/test_guardrail_sem_exportacao_massa.py`.
- **Não** autoriza transmissão a sistema externo. Sem a camada de publicação de eventos (G4A) não
  existe adapter — CLAUDE.md §10.

---

## 6. Referências

- `docs/ARQUITETURA_LAUDO.md` — arquitetura do módulo; seção "Produção do laudo pelo dispensador
  (unidade) em nome do RT" documenta o modelo que esta política pressupõe.
- `docs/NUCLEO_SANITARIO.md` — contrato do objeto sanitário.
- `CLAUDE.md` §2 (ledger imutável), §3 (custódia), §9 (migração como autoridade de schema),
  §10 (taxonomia de contribuição).
- `ETHICS.md` — não-objetivos éticos.
- Tickets: `planejamento/demo-laboratorio-laudo-cidadao/TICKET-A-politica-custodia-clinica.md`
  (esta política), `TICKET-B` (fluxo bancada), `TICKET-C` (RBAC do dispensador).

---

*Política declarada em 2026-08-13. Classe `local-extension`/`docs`: declara e mapeia, não altera
semântica clínica. Alterações neste documento que impliquem mudança de estados, ledger ou custódia
deixam de ser `local-extension` e passam a exigir revisão central (`core`).*
