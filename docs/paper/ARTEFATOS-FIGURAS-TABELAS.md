# Artefatos para o artigo CEBEB — figuras, Table I e métricas (verificados no código)

> Extraído de `backend/app/domain/states_*.py` e do repositório em 2026-06-14.
> **Todos os estados/transições abaixo são os reais** (não a simplificação do 1º draft).
> Mermaid + fallback em texto. Preenche as LACUNAs de Fig.1–3, Table I e §VI.

---

## §VI — Métricas da implementação de referência (preenche a LACUNA)

| Métrica | Valor |
|---|---|
| Linhas de código (`backend/app/`, sem testes) | ~31.700 |
| Routers (camada de API) | 32 |
| Models (ORM) | 43 |
| Endpoints (rotas) | 137 |
| Migrations Alembic (esquema único PG/SQLite) | 15 |
| **Tipos de objeto sanitário com máquina de estados própria** | **7** |
| Objetos com ledger append-only próprio (`*_eventos`) | 8 |
| Objetos com cadeia de custódia (`*_custodia`) | 5 |
| **Suíte de testes** | **1.341 funções de teste em 73 arquivos** |
| Gate de teste | dual-DB: SQLite + **PostgreSQL efêmero** (pega divergências invisíveis em SQLite) |

> ⚠️ Honestidade (para você decidir se entra no paper): o **gate de CI** (unit + integração
> selecionada contra Postgres) está verde; a suíte ampla SQLite tem ~16 falhas **pré-existentes**
> em módulos não relacionados (parsing de cert ICP, auth de integrador). Não afeta a tese, mas
> "1.341 testes, todos verdes" seria impreciso — prefira "1.341 testes; gate dual-DB de CI verde".

---

## TABLE I — Instâncias do núcleo (VERIFICADA; substitui a do draft)

| Objeto | Fluxo (estados reais) | Estados terminais | Cadeia de custódia |
|---|---|---|---|
| **Prescrição** | pendente → transferida_paciente → em_custodia → parcialmente_dispensada → dispensada | dispensada · cancelada · expirada · **encerrada_localmente** (físico) | prescritor → paciente → dispensador → (paciente \| prescritor) |
| **Pedido de exame** | emitido → agendado → coletado → em_analise → resultado_disponivel → encerrado | encerrado · cancelado · expirado · encerrado_fisico | prescritor → paciente → prestador_exame → paciente |
| **Laudo** | em_producao → assinado → liberado → ciencia_paciente / ciencia_prescritor → encerrado | encerrado · cancelado · expirado · encerrado_fisico | prestador_exame → (paciente \| prescritor) |
| **Agendamento** | criado → confirmado → realizado | realizado · cancelado · nao_compareceu | — *(nenhuma; compromisso bilateral — exceção documentada)* |
| **Circulação diagnóstica** | selecionado → enviado_laboratorio → proposta_recebida → confirmado_paciente → realizado | realizado · desmarcado_paciente · desmarcado_laboratorio · arquivado_laboratorio · expirado | paciente → laboratório *(mediada por token de apresentação)* |
| **Encaminhamento** | emitido → (em_regulacao) → agendado → atendido → contrarreferido → encerrado | encerrado · cancelado · expirado · **negado** · encerrado_fisico | prescritor(origem) → paciente → prescritor(destino) → paciente |
| **Contrarreferência** *(derivada)* | registrada | cancelada | destino → origem · `origem_encaminhamento_id` |

**Nota — Dispensação:** não é objeto próprio; é ato dentro do fluxo da prescrição, com a invariante
**Σ dispensado ≤ prescrito**. Variante hospitalar (subdomínio operacional): prescritor → farmácia
hospitalar → (unidade de enfermagem) → paciente.

**Correções vs. o draft:** (1) a prescrição tem 4 terminais, incluindo o físico `encerrada_localmente`;
(2) o laudo tem estados de *ciência* explícitos (paciente/prescritor); (3) o encaminhamento tem o
terminal específico `negado`; (4) a **circulação diagnóstica** é um 7º objeto (estava ausente da
Table I do draft) — vale incluir ou citar como instância adicional.

---

## FIGURE 1 — As sete propriedades invariantes do objeto sanitário rastreável

```mermaid
graph LR
    OSR(("Objeto Sanitário<br/>Rastreável"))
    OSR --- a["(a) Identidade global<br/>protocolo UUID"]
    OSR --- b["(b) Imutabilidade<br/>+ linhagem (origem_id)"]
    OSR --- c["(c) Ledger append-only<br/>*_eventos (só INSERT)"]
    OSR --- d["(d) Custódia explícita<br/>e granular (item/objeto)"]
    OSR --- e["(e) Máquina de estados<br/>finita (digital vs físico)"]
    OSR --- f["(f) Documento canônico<br/>+ hash SHA-256"]
    OSR --- g["(g) Ownership desde<br/>o nascimento + público neutro"]
```

---

## FIGURE 2 — Ciclo de vida da prescrição (fluxo digital vs físico)

```mermaid
stateDiagram-v2
    [*] --> pendente: emissão digital
    pendente --> transferida_paciente
    transferida_paciente --> em_custodia
    em_custodia --> parcialmente_dispensada
    em_custodia --> dispensada
    em_custodia --> transferida_paciente: devolução ao paciente
    parcialmente_dispensada --> dispensada

    pendente --> cancelada
    transferida_paciente --> cancelada
    em_custodia --> cancelada
    parcialmente_dispensada --> cancelada
    pendente --> expirada
    transferida_paciente --> expirada
    parcialmente_dispensada --> expirada

    dispensada --> [*]
    cancelada --> [*]
    expirada --> [*]

    state "FLUXO FÍSICO" as fis {
        [*] --> encerrada_localmente: emissão em papel
        encerrada_localmente --> [*]
    }
```

Fallback (texto): **Digital** — pendente → transferida_paciente → em_custodia →
{parcialmente_dispensada → dispensada}; `cancelada`/`expirada` alcançáveis de estados não-terminais;
`em_custodia → transferida_paciente` modela a devolução ao paciente (abandono). **Físico** — caminho
separado, terminal único `encerrada_localmente`, **sem** custódia digital.

---

## FIGURE 3 — Cadeia de custódia + linhagem de derivação

```mermaid
graph TD
    subgraph CUSTODIA["Cadeia de custódia (prescrição)"]
        P1[prescritor] -->|emissão digital| PA[paciente]
        PA -->|apresentação no balcão| D[dispensador]
        D -->|abandono / devolução| PA
        D -->|erro de prescrição| P1
    end

    subgraph LINHAGEM["Linhagem de derivação (origem_*_id)"]
        R1[REC-001 original] -->|correção| R2[REC-002]
        R2 -->|renovação| R3[REC-003]
        PE[pedido_exame] -.->|origina| LA[laudo]
        EN[encaminhamento] -.->|origina| CR[contrarreferência]
    end
```

Fallback (texto): **Custódia** — detentor único a cada momento; transições declaradas
(prescritor→paciente→dispensador→paciente/prescritor); granularidade objeto-inteiro **ou** item.
**Linhagem** — correção/renovação encadeiam versões do mesmo artefato (`origem_prescricao_id`);
derivação **entre** objetos liga artefatos causalmente relacionados: laudo deriva de pedido de exame,
contrarreferência deriva de encaminhamento — cada derivação com **autor distinto, documento e hash
próprios**.

---

## Citações regulatórias — VERIFICADAS na web (fecha LACUNAs [6] e [12])

**[12] ANVISA, RDC nº 1.000/2025** — estabelece regras para a **prescrição eletrônica de
medicamentos sujeitos a controle especial**, retenção e notificação de receita, em território
nacional; altera pontos da **Portaria SVS/MS 344/98**. Foco em **rastreabilidade** e redução de
fraude via **assinatura digital obrigatória** e integração ao **SNCR (Sistema Nacional de Controle
de Receituários)**. Vigência para controlados a partir de **13/02/2026**; CPF do paciente
obrigatório; SNCR pleno previsto até **30/09/2026**. *(Confere com o uso no projeto — "RDC
1.000/2025" está correto.)*

**[6] Resolução CFM nº 2.299/2021** — regulamenta a **emissão de documentos médicos eletrônicos**;
publicada no **DOU de 26/10/2021** (aprovada em 30/09/2021), em vigor após 60 dias (~25/12/2021). O
**Art. 4º** exige **assinatura digital ICP-Brasil com NGS2** (Nível de Garantia de Segurança 2),
garantindo validade jurídica, autenticidade, autoria e **não-repúdio**. *(Confere com o draft —
"[6] CFM 2.299/2021 mandates ICP-Brasil signing" está correto.)*

> Fontes: gov.br/anvisa (webinar RDC 1.000/2025); Anfarmag / ITI / CFM (Resolução 2.299/2021,
> Art. 4º). Verificado em 2026-06-14.

---

## Parágrafo de métodos — o gate dual-DB (sugestão de redação p/ §VI)

> The reference implementation runs on PostgreSQL in production and SQLite in development under a
> single Alembic-managed schema. A **dual-database test gate** executes the suite against an
> ephemeral PostgreSQL instance, not only against SQLite. This is not redundant: SQLite's permissive
> typing (e.g., accepting an integer literal for a boolean column, or lax NULL handling) silently
> masks defects that surface only under PostgreSQL's strict typing. In our development this gate
> repeatedly caught latent defects that were **invisible on SQLite** — for instance, a boolean column
> written with an integer literal passed every SQLite test yet raised a type-mismatch error on
> PostgreSQL, meaning a code path that *appeared* fully tested was in fact broken under
> production-equivalent conditions. The methodological claim is narrow but practical: for
> dual-database clinical systems, **the production database must be inside the test gate** — a green
> bar on the development database is necessary but not sufficient.

*(Honesto e vivido: foi exatamente assim que pegamos os bugs `dose_unitaria` e `ativo` — invisíveis
em SQLite, quebrados na PG. É, possivelmente, a contribuição de engenharia mais defensável do paper.)*

---

*Fonte: `backend/app/domain/states_{prescricao,exame,laudo,agendamento,circulacao_diagnostica,encaminhamento,contrarreferencia}.py`.
Métricas de `backend/app` e `backend/tests`. Citações regulatórias verificadas na web. Verificado em 2026-06-14 — nada inventado.*
