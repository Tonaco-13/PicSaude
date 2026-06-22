# Arquitetura de Apoio à Decisão Clínica — PicSaúde (a "triangulação")

> Documento oficial de arquitetura. **Não contém implementação.**
> Status: **planejado** — desenho convergido Fabiano + Engenheiro-Chefe (2026-06-21).
> Classe de contribuição: `module`, mas por tocar **juízo clínico** exige
> revisão central antes de código (ver CLAUDE.md §10).
> Extensão de [`ARQUITETURA_IA.md`](ARQUITETURA_IA.md) para o território que aquele
> documento deliberadamente evita ("Risco 5 — uso em contexto clínico indevido").

---

## A virada de desenho (2026-06-21) — validador, não recomendador

A primeira versão deste plano previa **recomendar fármaco a partir da indicação
clínica** (condição → fármaco). Fabiano reformulou — e a reformulação é o coração
deste documento:

> **O sistema NÃO sugere o fármaco. O prescritor escolhe; o sistema CONFERE a
> coerência da escolha com a indicação e devolve um sinal discreto.**

A diferença é pequena na frase e enorme no risco:

| | Recomendar (descartado) | **Validar (este desenho)** |
|---|---|---|
| Quem decide a terapia | o sistema sugere | **o prescritor** |
| Papel do sistema | propõe conduta | **confere e sinaliza** |
| Risco regulatório | beira "software que prescreve" (SaMD) | apoio à decisão (baixo) |
| Agência do médico | nudge em direção a uma escolha | **preservada — nunca bloqueia** |

**Analogia:** não é o sistema dizendo "receite isto". É o **farmacêutico de balcão
conferindo** — *"esse remédio bate com o diagnóstico?"* — sem nunca tirar a caneta
da mão do médico. Como um corretor ortográfico: **sublinha, não reescreve.**

---

## Mapa rápido

| Tópico | Seção |
|---|---|
| Linha vermelha (validar, nunca recomendar/bloquear) | 1 |
| As três funções (busca · validação · posologia) | 2 |
| A régua do semáforo (🟢🟡🔴) e a fadiga de alerta | 3 |
| A triangulação — como o sinal é computado | 4 |
| Fontes de dado (PCDT espinha · bula · CID · RENAME) | 5 |
| Faseamento (coerência → contraindicação) | 6 |
| Modelo de conteúdo (curado, assinado, proveniência) | 7 |
| Runtime / UX (sinal discreto, não-bloqueante) | 8 |
| Enquadramento regulatório | 9 |
| Salvaguardas e riscos (fadiga de alerta no centro) | 10 |
| Checklist de conformidade | 11 |
| Sequência de implementação | 12 |

---

## 1. Linha vermelha

**Princípio contratual (inviolável):**

> O **motor é do engenheiro** (determinístico, lookup, sem LLM). O **conteúdo
> clínico** (as regras 🟢🟡🔴) é **propriedade e responsabilidade da equipe
> clínica**, derivado de fonte oficial (PCDT). O sistema **valida e sinaliza** —
> **nunca recomenda fármaco, nunca bloqueia, nunca preenche** a escolha.

| O sistema PODE | O sistema NUNCA |
|---|---|
| Hierarquizar a busca por relevância (nome) | Ordenar a busca para induzir um fármaco |
| Sinalizar a coerência da escolha (🟢🟡🔴) | Escolher o fármaco pelo prescritor |
| Mostrar a fonte do sinal (PCDT, bula) | Bloquear/recusar a emissão (nem no 🔴) |
| Sugerir a **posologia usual do fármaco já escolhido** (editável) | Sugerir **qual** fármaco usar |
| Ficar em silêncio/neutro quando não souber | Inventar conteúdo clínico (sem curadoria) |

O prescritor (CRM/CRO/…) é, sempre, o **responsável legal e clínico** final.

---

## 2. As três funções

### 2.1 Busca hierarquizada (já implementada)
Ao digitar o medicamento, a busca prioriza **correspondência por substring** no
princípio ativo e ordena por concentração — relevância, **não** recomendação.
(Implementado em `lookup_def.buscar_medicamentos`; é o fix do escitalopram.)

### 2.2 Validação por semáforo (núcleo deste documento)
Depois que o prescritor **escolhe** o fármaco, o sistema triangula a escolha
contra a **indicação clínica (CID)** e devolve um **sinal discreto** 🟢🟡🔴
(seção 3). Não-bloqueante.

### 2.3 Apoio à posologia (companheiro)
Ao escolher o fármaco, o sistema pode oferecer a **posologia usual** (adulto,
dose fixa) como sugestão **editável** — ajuda a *executar* a escolha, não a
*fazer* a escolha. Origem: bula. (É o antigo "PoC de 5 fármacos"; permanece
válido sob a mesma linha vermelha.)

> As três funções compartilham a tese: **ajudar/conferir a escolha, jamais
> fazê-la.** O que foi descartado é só a recomendação `condição → fármaco`.

---

## 3. A régua do semáforo

O sinal é **discreto** (um ponto colorido junto ao fármaco) e **não-bloqueante**.

| Sinal | Significado | Quando acende |
|---|---|---|
| 🟢 **Perfeito** | escolha coerente | em condição **exaustiva**, o fármaco consta na lista **completa** do PCDT |
| 🟡 **Atenção** | fora do protocolo | em condição **exaustiva**, o fármaco **não** consta na lista completa — confira |
| **(silêncio) Neutro** | sem julgamento | condição **sem curadoria exaustiva** → o semáforo se cala (nem 🟢) |
| 🔴 **Alerta** | perigo real | **contraindicação** (fármaco-doença, alergia, interação) — **Fase 2** |

### Lei da exaustividade (princípio fundamental — achado de Fabiano)
> Uma lista 🟢 **incompleta não é neutra**: ela privilegia os fármacos curados e
> desencoraja os válidos omitidos — recomendação pela porta dos fundos. Logo:
>
> **O semáforo só JULGA uma condição cuja lista 🟢 é EXAUSTIVA em relação ao
> PCDT. Senão, ele se CALA (neutro) — nem 🟢.**
>
> Mostrar verde só para os fármacos que curamos já seria o viés. Assim o semáforo
> é **autoritativo quando fala** (lista completa) e **honesto quando se cala**.
> No dado: coluna `exaustivo` por condição; o motor (`semaforo_decisao.py`)
> aplica o portão da exaustividade ANTES de qualquer sinal. Condições-semente
> entram como **não exaustivas** (silenciosas) até a lista completa ser curada e
> assinada.

### Princípio crítico — o 🔴 é conservador (fadiga de alerta)
> Se o sistema pintar de vermelho toda escolha que ele "não conhece", o
> prescritor **aprende a ignorar** — e o alerta perde valor justamente quando
> importa. Por isso: **incerteza → 🟡 (neutro, honesto); 🔴 só com evidência
> forte de perigo.** O 🟡 é o estado mais comum e não é uma falha — é o sistema
> dizendo "não tenho base para afirmar".

**Calibração (decisão clínica de Fabiano):** o padrão adotado é — *fármaco
claramente fora da indicação, mas sem perigo* → **🟡**; **🔴** reservado a
contraindicação/perigo real. A equipe clínica pode recalibrar este limiar.

---

## 4. A triangulação — como o sinal é computado

```
        indicação clínica (texto)
                 │  (IA CID v1 — já existe)
                 ▼
              CID-10 ───────────────┐
                                     │
   fármaco escolhido ──► princípio   │   PCDT/CONITEC: CID ↔ fármaco aprovado
   (pelo prescritor)     ativo  ─────┼──►  (espinha do 🟢)
                                     │
                                     │   bula: indicação farmacológica
                                     ├──►  (reforço cauteloso)
                                     │
                                     └──►  base de contraindicações (fase 2)
                                              │
                                              ▼
                                      🟢 / 🟡 / 🔴  (não-bloqueante)
```

- **Entrada:** o CID (da indicação clínica, via IA CID já existente) + o
  princípio ativo do fármaco que o prescritor escolheu.
- **Regra determinística:** o fármaco consta como tratamento do CID no PCDT/
  curadoria? → 🟢. Não consta / desconhecido → 🟡. Contraindicação registrada
  → 🔴.
- **Saída:** sinal + a **fonte** que o gerou (ex.: "PCDT de Hipertensão" /
  "bula" / "—"). Rastreável, como toda IA do PicSaúde.

---

## 5. Fontes de dado (verificadas — spike 2026-06-19)

| Fonte | Papel | Aberta? |
|---|---|---|
| **PCDT / CONITEC** (painel "Medicamentos por CID e PCDT") | **espinha do 🟢** — CID ↔ fármaco aprovado, curado e assinado pelo MS | catálogo aberto; cruzamento nos PDFs (curadoria) |
| **Bula (ANVISA Bulário)** | reforço da indicação farmacológica | PDF por medicamento (texto livre — usar com cautela) |
| **CID-10 (DATASUS)** | ligação indicação → código | ✓ (já no sistema) |
| **RENAME** | filtra ao que o SUS dispensa | ✓ |
| **DEF (livro)** | — | ❌ comercial; fora |

**Alerta de engenharia:** a indicação da bula é texto livre e ruidosa. Ela
**reforça**, nunca **arbitra** o sinal. O 🟢 nasce do **PCDT** (cruzamento já
feito e assinado por especialistas), não de NLP sobre bula.

---

## 6. Faseamento

- **Fase 1 — coerência de indicação.** 🟢 (PCDT/curadoria) e 🟡 (desconhecido).
  O 🔴 só para descasamento claro. Sai com PCDT + curadoria, sem base nova.
- **Fase 2 — contraindicação verdadeira.** 🔴 por fármaco-doença, alergia e
  interação. Exige **base de contraindicações própria** (mais rica) — entra
  depois, com curadoria dedicada.

---

## 7. Modelo de conteúdo

Dado de **referência clínica** (não objeto sanitário, não ledger, **sem dado de
paciente**), versionado e com proveniência:

| Campo | Papel |
|---|---|
| `codigo_cid`, `condicao_nome` | a condição |
| `principio_ativo` | o fármaco aprovado para ela |
| `sinal_base` | 🟢 (aprovado no PCDT) — base do verde |
| `pcdt_origem`, `pcdt_status` | proveniência (qual protocolo, status) |
| `status_curadoria`, `validado_por`, `validado_em`, `versao` | assinatura clínica |

**Invariante:** o motor só serve regras com `status_curadoria = validado`.
Determinístico, sem LLM. Conteúdo **curado e assinado** pela equipe clínica.

---

## 8. Runtime / UX

- O sinal aparece como **ponto colorido discreto** junto ao fármaco escolhido,
  com a **fonte** ao toque/hover. Nunca um modal que interrompe.
- **Não-bloqueante:** nem o 🔴 impede a emissão — registra-se a decisão do
  prescritor (e, idealmente, fica no rastro de auditoria que houve alerta).
- Ausência de base → 🟡 silencioso (sem ruído).
- O motor **não** grava no ledger clínico nem altera estados; opera sobre a
  prescrição em edição.

---

## 9. Enquadramento regulatório

- **SaMD / RDC 657/2022 (ANVISA):** validar a escolha do profissional (que
  decide de forma independente, vê a fonte e não é bloqueado) é **apoio à
  decisão** — postura ainda **mais segura** que recomendar conduta. Classificação
  formal a confirmar com especialista regulatório antes de produção.
- **CFM:** a responsabilidade é do profissional; o sinal nunca vira ordem.
- **LGPD:** tabelas de referência clínica, **sem dado de paciente**; superfície
  mínima.

---

## 10. Salvaguardas e riscos

| Risco | Salvaguarda |
|---|---|
| **Fadiga de alerta** (🔴 em excesso → ignorado) | 🔴 conservador; incerteza vira 🟡; calibração clínica |
| Sinal tomado como ordem | discreto, não-bloqueante, fonte visível |
| Mineração de bula gerando ruído | 🟢 nasce do PCDT; bula só reforça |
| Conteúdo errado/desatualizado | curadoria assinada + versionada + proveniência |
| Indução por ordenação da busca | busca ordena por relevância de **nome**, não por indicação |
| Acoplamento com a emissão | módulo isolado; não grava ledger nem altera estados |
| Enquadramento como SaMD | desenho de validação + validação regulatória antes de produção |

---

## 11. Checklist de conformidade (antes de implementar)

- [ ] Conteúdo clínico (regras do semáforo) **assinado** pela equipe clínica
- [ ] Cada regra com proveniência à fonte oficial (PCDT / bula + status)
- [ ] Motor determinístico, sem LLM, rastreável
- [ ] Sistema **valida e sinaliza** — nunca recomenda fármaco, nunca bloqueia
- [ ] 🔴 conservador (sem fadiga de alerta); incerteza → 🟡
- [ ] Sem gravação no ledger clínico; sem alteração de estados
- [ ] Sem dado de paciente nas tabelas de conteúdo
- [ ] Feature flag desligada por padrão e na vitrine
- [ ] Validação regulatória (SaMD) registrada antes de produção
- [ ] Revisão central do desenho (classe `module` que toca juízo clínico)

---

## 12. Sequência de implementação

1. **Este documento** — desenho convergido (validador, não recomendador).
2. **Busca hierarquizada** — ✅ feito (relevância por substring).
3. **Semáforo v1 (coerência):** ingerir o cruzamento CID ↔ fármaco (PCDT/CONITEC),
   curar/assinar, e acender 🟢/🟡 na escolha do prescritor — atrás de flag.
4. **Apoio à posologia:** validar as 5 posologias-semente e o motor `fármaco →
   posologia` (companheiro).
5. **Semáforo v2 (contraindicação):** base própria de contraindicações → 🔴.
6. **Liberação na vitrine:** só após conteúdo validado e disclaimers fechados.

---

## O que este módulo NÃO faz

- Não recomenda qual fármaco usar; não decide a terapia.
- Não bloqueia, não condiciona, não preenche a escolha (nem no 🔴).
- Não calcula dose por peso, não cobre pediatria (no MVP da posologia).
- Não usa LLM nem aprende com o uso.
- Não grava no ledger clínico nem cria/altera objeto sanitário.
- Não substitui a leitura do PCDT nem da bula — aponta para elas.
