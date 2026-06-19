# Arquitetura de Apoio à Decisão Clínica — PicSaúde (a "triangulação")

> Documento oficial de arquitetura. **Não contém implementação.**
> Status: **planejado** — discussão Fabiano + Engenheiro-Chefe (2026-06-19).
> Classe de contribuição: `module`, mas por tocar **juízo clínico** exige
> revisão central antes de código (ver CLAUDE.md §10).
> Extensão de [`ARQUITETURA_IA.md`](ARQUITETURA_IA.md) para o território que aquele
> documento deliberadamente evita ("Risco 5 — uso em contexto clínico indevido").

---

## Por que este documento existe

Tudo que o PicSaúde construiu até aqui — ledger, custódia, estados, emissão,
atestado, busca de CID/medicamento — é **infraestrutura**: determinística,
auditável, sem juízo clínico. A pergunta que o sistema responde é
*"isto está rastreável e bem-formado?"*.

A **triangulação** (apoio à decisão) é a **primeira peça que toca juízo clínico**:
*"que fármaco / que dose para esta condição?"*. Isso muda o patamar de risco e de
responsabilidade. Por isso ela é uma **trilha separada**, atrás de feature flag,
desligada na vitrine pública até o conteúdo clínico estar validado e assinado.

Este documento fixa a linha vermelha, o modelo de conteúdo e o contrato de
curadoria **antes** de qualquer linha de motor.

---

## Mapa rápido

| Tópico | Seção |
|---|---|
| Linha vermelha (apoio à decisão ≠ software que decide) | 1 |
| Relação com a IA farmacêutica existente | 2 |
| As duas camadas (2a fármaco→posologia · 2b condição→fármaco) | 3 |
| Modelo de conteúdo (tabela curada + proveniência) | 4 |
| Contrato de curadoria (autoria, validação, assinatura) | 5 |
| Escopo e não-escopo | 6 |
| Fontes de dado (DEF, bula, PCDT) — o que é aberto e o que não é | 7 |
| Comportamento em runtime (contrato de UX) | 8 |
| Proveniência e auditoria | 9 |
| Enquadramento regulatório (SaMD / CFM / LGPD) | 10 |
| Feature flag e rollout | 11 |
| Salvaguardas e riscos | 12 |
| Checklist de conformidade (antes de implementar) | 13 |
| Sequência de implementação | 14 |

---

## 1. Linha vermelha — apoio à decisão, nunca software que decide

**Princípio contratual (inviolável):**

> O **motor é do engenheiro** (determinístico, lookup, sem LLM — igual ao resto).
> O **conteúdo clínico** (qual fármaco / qual dose para qual condição) é
> **propriedade e responsabilidade da equipe clínica**. O sistema **só sugere**.

Em letra de forma, o motor:

| O motor PODE | O motor NUNCA |
|---|---|
| Oferecer uma sugestão **rotulada** e **editável** | Preencher um campo sozinho, sem confirmação |
| Mostrar a **fonte** (bula / PCDT) e o **status** da sugestão | Apresentar a sugestão como verdade ou ordem |
| Sugerir posologia usual a partir do fármaco escolhido (2a) | Bloquear, condicionar ou recusar a emissão |
| Sugerir 1ª linha a partir do CID (2b) | Embarcar conteúdo clínico **não assinado** |
| Deixar tudo em branco quando não houver conteúdo curado | Decidir pelo prescritor; substituir o julgamento |

O prescritor (CRM/CRO/…) é, sempre, o **responsável legal e clínico** final.

---

## 2. Relação com a IA farmacêutica (`ARQUITETURA_IA.md`)

A IA farmacêutica já existente é **assistiva e estrutural**: normaliza nome,
sugere `unidade_quantidade`/`forma`, alerta incoerência. Ela responde
*"isto está bem-formado?"* — e explicitamente **não entra** em contexto clínico.

Este módulo **entra** nesse contexto, mas de forma controlada. A diferença:

| | IA farmacêutica (existente) | Apoio à decisão (este doc) |
|---|---|---|
| Pergunta | "está bem-formado?" | "que fármaco/dose para esta condição?" |
| Risco | estrutural (baixo) | juízo clínico (alto) |
| Conteúdo | base técnica (CMED/ANVISA) | tabela **clínica curada e assinada** |
| Gatilho | sempre ativo | atrás de flag, conteúdo validado |

Ambos herdam o mesmo DNA: **lookup determinístico, sem alucinação, rastreável,
nunca decisório.**

---

## 3. As duas camadas

A triangulação se constrói em camadas, da menor para a maior responsabilidade:

### Camada 2a — `fármaco → posologia usual` (primeiro)

Ao selecionar o medicamento, o card oferece a **posologia usual** (adulto, dose
fixa) como sugestão editável. Origem objetiva: a **bula**. O prescritor já
decidiu o fármaco — o motor só poupa a digitação da posologia.

```
Dipirona 500 mg, comprimido
  → sugere: "1 comprimido de 6/6 h, se dor ou febre"   (editável · fonte: bula)
```

### Camada 2b — `condição (CID) → fármaco de 1ª linha` (depois)

Ao escolher a condição/CID, o motor sugere fármaco + concentração + forma +
posologia de 1ª linha, **ancorado no PCDT** correspondente.

```
Hipertensão (I10)
  → sugere: Losartana 50 mg, comprimido, "1 comp 1×/dia"
            (editável · fonte: PCDT de X, status Aprovado)
```

A 2b é **decisão terapêutica** — só entra quando a base clínica existir e estiver
assinada, e nunca a partir de varredura automática de texto livre de bula
(ver §7, alerta de engenharia).

---

## 4. Modelo de conteúdo — tabela curada + proveniência

O conteúdo é **dado de referência clínica** (não objeto sanitário, não ledger,
**sem dado de paciente**). Vive em tabelas versionadas, com proveniência à fonte
oficial. Esquema indicativo (a confirmar na implementação):

### 4a. `decisao_posologia` (camada 2a)

| Campo | Papel |
|---|---|
| `principio_ativo`, `concentracao`, `forma` | chave de casamento com o fármaco escolhido |
| `posologia_sugerida` | texto da posologia usual (adulto, dose fixa) |
| `fonte` / `fonte_ref` | "bula" / identificador (registro ANVISA) |
| `status_curadoria` | `rascunho` · `validado` |
| `validado_por`, `validado_em`, `versao` | assinatura + versionamento |
| `observacao` | ressalvas (ex.: "máx. 4 g/dia") |

### 4b. `decisao_condicao_terapia` (camada 2b)

| Campo | Papel |
|---|---|
| `codigo_cid`, `condicao_nome` | chave de casamento com a condição escolhida |
| `principio_ativo`, `concentracao`, `forma`, `posologia_sugerida` | a sugestão terapêutica |
| `linha` | `1a` (somente 1ª linha no MVP) |
| `pcdt_origem`, `pcdt_status` | proveniência ao protocolo (ex.: "Aprovado*") |
| `status_curadoria`, `validado_por`, `validado_em`, `versao` | assinatura + versionamento |

**Invariante:** o motor só serve linhas com `status_curadoria = validado`.
Conteúdo `rascunho` nunca chega ao prescritor.

---

## 5. Contrato de curadoria

```
A tabela de conteúdo é AUTORADA, VALIDADA e ASSINADA pela equipe clínica.

curadoria NUNCA:
  - é gerada por LLM ou inferida automaticamente de texto livre
  - chega ao prescritor sem status `validado`
  - perde a proveniência à fonte oficial (bula / PCDT)

curadoria SEMPRE:
  - registra quem validou, quando e qual versão
  - aponta para a fonte (registro de bula / PCDT + status)
  - é versionada (uma correção = nova versão, conteúdo anterior preservado)
```

O motor é construído contra um **contrato de dados**; o conteúdo entra depois,
assinado. Engenheiro entrega o motor vazio e testado; a clínica preenche.

---

## 6. Escopo e não-escopo

| No escopo (MVP) | **Fora** do escopo (MVP) |
|---|---|
| Adulto | Pediatria |
| Dose fixa | Dose por peso / superfície corporal |
| 1ª linha consolidada | 2ª/3ª linha, esquemas alternativos |
| Posologia usual | Ajuste renal/hepático, interações, contraindicações |
| Sugestão editável | Cálculo de dose, alertas de interação |

Pediatria, dose-por-peso e ajustes entram **depois**, com tratamento próprio e
salvaguardas adicionais — nunca esticando o MVP.

---

## 7. Fontes de dado — o que é aberto e o que não é

Verificado em spike (2026-06-19):

| Fonte | Aberta? | O que entrega | Uso |
|---|---|---|---|
| **DEF** (Dicionário de Especialidades Farmacêuticas, o livro) | ❌ Não — publicação comercial | bulas compiladas por indicação | **fora** (copyright) |
| **Bulário Eletrônico ANVISA** | Parcial | bula em **PDF** por medicamento (RDC 47/2009: seções Indicações/Posologia); Dados Abertos traz só o *cadastro* em CSV | **2a** — ler bula e curar |
| **PCDT / CONITEC** | Parcial | painel "Medicamentos por CID e PCDT" (Power BI); API/CSV aberta expõe só o **catálogo de 83 protocolos** (`descricao_do_nome`, `status`, `descricao_do_tipo`) | **2b** — catálogo como índice/proveniência; conteúdo curado do PDF |
| **RENAME** | ✓ | lista oficial de medicamentos essenciais | filtra a 2b para o que o SUS dispensa |

**Alerta de engenharia (crítico para a 2b):** a seção *Indicações* da bula é texto
livre, lista indicações múltiplas (incl. off-label) e casá-la ao CID por NLP gera
ruído — e ruído em sugestão de fármaco é **risco clínico**. Por isso a 2b ancora no
**PCDT** (cruzamento já feito e assinado por especialistas do MS), **não** em
varredura de bula. A bula entra só na 2a, onde a pergunta é objetiva.

**Consequência:** não existe atalho de "baixar a tabela CID→fármaco". O conteúdo da
2b é **curadoria a partir do PCDT**, com o catálogo aberto servindo de índice e de
carimbo de proveniência. Isso reforça a linha vermelha — a própria CONITEC afirma
que o painel *"não substitui a leitura do PCDT"*.

---

## 8. Comportamento em runtime (contrato de UX)

- A sugestão aparece como **texto editável** no campo, nunca como valor travado.
- Sempre acompanhada de **rótulo** e **fonte**: *"sugestão — confira dose,
  contraindicações e ajustes · fonte: bula / PCDT de X (Aprovado)"*.
- O prescritor pode **ignorar, aceitar ou editar** livremente.
- Ausência de conteúdo curado → **campo em branco**, sem erro, sem bloqueio.
- O motor **não** persiste nada novo do paciente; opera sobre a prescrição em
  edição. A emissão segue o fluxo normal (estados, ledger, custódia inalterados).

Endpoints indicativos (a detalhar): `POST /ia/decisao/posologia`,
`POST /ia/decisao/terapia` — entrada estrutural, saída = lista de sugestões com
proveniência. Sem efeito colateral clínico.

---

## 9. Proveniência e auditoria

Toda sugestão servida carrega: **fonte** (bula / PCDT), **referência** (registro /
protocolo + status) e **versão** do conteúdo curado. "Por que o sistema sugeriu X?"
tem resposta determinística — herança direta do princípio lookup da IA farmacêutica.

O que o prescritor efetivamente emitiu continua sendo o que vale e o que o ledger
registra; a sugestão é insumo, não decisão. O módulo **não** grava no ledger
clínico nem altera estados (não é objeto sanitário).

---

## 10. Enquadramento regulatório

- **SaMD / RDC 657/2022 (ANVISA):** o desenho — *só sugere, profissional revê a
  base (bula/PCDT visível) e decide de forma independente, conteúdo de fonte
  oficial* — busca manter o módulo na faixa de **apoio à decisão que não substitui
  o julgamento clínico**, e não na de "software que conduz a conduta" (dispositivo
  médico). A classificação formal deve ser **confirmada com especialista
  regulatório antes de produção** — este documento não a substitui.
- **CFM:** a responsabilidade da prescrição é do profissional; a sugestão nunca
  pode ser apresentada como prescrição automática.
- **LGPD:** as tabelas de conteúdo são **referência clínica, sem dado de paciente**;
  o motor opera sobre a prescrição em edição, sem novo armazenamento. Superfície
  LGPD mínima.

---

## 11. Feature flag e rollout

- Tudo atrás de flag (ex.: `PICSAUDE_DECISAO_CLINICA`), **desligada por padrão** e
  **desligada na vitrine pública** até o conteúdo estar validado e os disclaimers
  fechados.
- O motor pode ser construído, testado e revisado isolado; só acende na UI do
  prescritor quando Fabiano liga.
- A vitrine mantém as ajudas estruturais já existentes (busca de CID/medicamento);
  a sugestão de **dose/terapia** é tier de risco distinto e fica escura até liberar.

---

## 12. Salvaguardas e riscos

| Risco | Salvaguarda |
|---|---|
| Sugestão tomada como ordem | rótulo explícito + editável + fonte visível; nunca preenche/bloqueia |
| Conteúdo clínico errado ou desatualizado | curadoria assinada + versionada + proveniência; só `validado` é servido |
| Acoplamento com a emissão | módulo isolado; não grava ledger nem altera estados |
| Mineração de bula gerando ruído (2b) | 2b ancora no PCDT curado, nunca em NLP de indicações |
| Uso pediátrico/dose-por-peso indevido | fora do escopo MVP, declarado; motor não cobre |
| Exposição prematura na vitrine | feature flag desligada até validação |
| Enquadramento como SaMD | desenho de apoio à decisão + validação regulatória antes de produção |

---

## 13. Checklist de conformidade (antes de implementar)

- [ ] Conteúdo clínico **assinado** pela equipe clínica (não rascunho)
- [ ] Cada linha com proveniência à fonte oficial (bula / PCDT + status)
- [ ] Motor determinístico, sem LLM, rastreável (lookup)
- [ ] Sugestão sempre editável, rotulada e com fonte; nunca preenche/bloqueia
- [ ] Sem gravação no ledger clínico; sem alteração de estados
- [ ] Sem dado de paciente nas tabelas de conteúdo
- [ ] Feature flag desligada por padrão e na vitrine
- [ ] Escopo MVP respeitado (adulto, dose fixa, 1ª linha)
- [ ] Validação regulatória (SaMD) registrada antes de produção
- [ ] Revisão central do desenho (classe `module` que toca juízo clínico)

---

## 14. Sequência de implementação

1. **Este documento** — revisão conjunta (feito o desenho, antes do código).
2. **2a — PoC 5 fármacos:** Fabiano valida 5 posologias (adulto/dose fixa); o
   engenheiro constrói o motor `fármaco→posologia` + testes, atrás de flag.
3. **2a — expansão:** curadoria cresce dos 5 para o conjunto mais comum da APS.
4. **2b — índice:** ingerir o catálogo aberto de PCDTs (proveniência + status).
5. **2b — curadoria condição→fármaco:** equipe clínica encoda 1ª linha por PCDT.
6. **Liberação na vitrine:** só após conteúdo validado e disclaimers fechados.

---

## O que este módulo NÃO faz

- Não prescreve, não decide, não bloqueia, não preenche sozinho.
- Não calcula dose por peso, não cobre pediatria, não alerta interação (no MVP).
- Não usa LLM nem aprende com o uso.
- Não grava no ledger clínico nem cria/altera objeto sanitário.
- Não substitui a leitura da bula nem do PCDT — aponta para elas.
