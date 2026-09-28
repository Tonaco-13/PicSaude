# DESPACHO ENG-026 — a caneta das pendências do lote

| Campo | Valor |
|---|---|
| **O que é** | Execução das 6 decisões da `PENDENCIAS-CANETA-EM-LOTE-2026-09.md` (A1–A6) + o destino das seeds K21/E03 (P-1/P-2), em PR única de curadoria |
| **Classe** | `curadoria` — dados (CSVs), guardas (testes) e docs; **zero backend/app** |
| **Autorização** | Fabiano, 28/09/2026, verbatim: **"A1 fora · A2 espelha F00 · A3 mantém · A4 espelha A52 em A53 · A5 mantém · A6 volta às 8 rows · K21 por diretriz · E03 semente"** |
| **Base** | `origin/main` pós-#277 (a caneta em lote já vive: 33 CIDs exaustivos, +143/+143 rows) |
| **Destinatário** | Engenheiro. RATIFICADO do arquiteto antes do martelo do Fabiano |
| **Irmãos** | `PENDENCIAS-CANETA-EM-LOTE-2026-09.md` · `RASCUNHO-L20-DUPLO` §1a/§2/§3 · `RASCUNHO-IST-DUPLO` §1 Quadro 15 |

---

## §1 O critério refinado — normativo a partir daqui

A caneta A6 refina o critério do verde (o J44 o estabeleceu; o L20 o completou):

> **🟢 = reconhecido no protocolo E disponível no SUS** — sendo a
> disponibilidade atestada por **RENAME ∨ incorporação vigente que nomeie o
> fármaco**. A coluna `fonte` da row declara qual dos dois atesta; citar a
> RENAME como se o fármaco lá estivesse, quando ele não está, continua sendo
> erro (o padrão da row-alias do valproato é o modelo: a fonte registra a
> ausência em vez de fingir presença).

A incorporação vigente vale como prova quando **mais nova que o snapshot da
RENAME** (PCDT de nov/2025 contra RENAME de 2024) e quando **nomeia o fármaco
para a indicação** da row. Protocolo antigo recomendando fármaco que ninguém
incorporou por nome (o caso fluticasona/J44) continua amarelo.

## §2 Gesto por item

### A1 · B92 — FORA (nenhum gesto de dado)
B92 permanece sem row e sem exaustividade — neutro é o silêncio honesto para
"sequelas sem escopo farmacológico". Exaustivo-com-zero-rows seria mecanismo
novo para um canto; não se gasta mecanismo em canto. Resolver a entrada A1 no
`PENDENCIAS-CANETA-EM-LOTE-2026-09.md` (✔️ com o verbatim e a data).

### A2 · F00 — ESPELHA G30 (+4 semáforo, +4 posologia)
- `decisao_semaforo.csv`: 4 rows sob **F00** (donepezila · galantamina ·
  rivastigmina · memantina), espelho exato das de G30 — mesma fonte (PCDT
  Alzheimer 2025, Port. Conjunta SAES/SCTIE 27/2025, item 6.2.2 p. 12 e Quadro
  5 p. 13 + RENAME 2024) acrescida de `"alias F00←G30 por caneta 28/09"`;
  `versao: semaforo_f00_alias_v1_2026-09`; `exaustivo=true`. F00 entra no
  conjunto exaustivo.
- `posologia_sugerida.csv`: 4 rows sob F00, **texto idêntico** às de G30.
- `_REPETE_POR_PROTOCOLO`: 4 entradas novas (donepezila, galantamina,
  rivastigmina, memantina) — citação: mesmo protocolo, mesmo Quadro 5 (p. 13);
  o espelho repete **por decisão de caneta**, não por falha de chave.
- **Guarda NOVA:** F00 ≡ G30 — elenco e posologia. Espelho que deriva reprova.

### A3 · valproato em idade fértil — MANTÉM (nenhum gesto de dado)
Row única com observação permanece. A camada de **metadados de população**
(valproato, romosozumabe, e o que vier) fica registrada como candidata à trilha
de explicabilidade — decisão de produto, não de curadoria. Resolver A3 no
PENDENCIAS com esse encaminhamento.

### A4 · A53 — ESPELHA A52, ESQUEMA TARDIO (+2 semáforo, +2 posologia)
- `decisao_semaforo.csv`: 2 rows sob **A53** (benzilpenicilina benzatina ·
  doxiciclina), fonte idem A52 (PCDT IST, Port. SCTIE/MS 12/2021, Quadro 15
  p. 23–24) acrescida de `"alias A53←A52 por caneta 28/09; duração ignorada
  trata-se como tardia"`; `versao: semaforo_a53_alias_v1_2026-09`;
  `exaustivo=true`. A53 entra no conjunto exaustivo.
- `posologia_sugerida.csv`: 2 rows sob A53 com o texto de A52 (benzatina 2,4 MI
  IM 1×/semana × 3 semanas; doxiciclina 100 mg 12/12h 30 dias).
- `_REPETE_POR_PROTOCOLO`: benzilpenicilina benzatina e doxiciclina ganham
  entradas (A52×A53, citação do Quadro 15 — duração ignorada = tardia).
  Neurossífilis segue fora do escopo ambulatorial (documentado no rascunho §1).
- **Guarda NOVA:** A53 ≡ A52 (mesma disciplina do espelho F00).

### A5 · romosozumabe e os 3 suplementos — MANTÉM (nenhum gesto de dado)
Reconhecido (elenco do PCDT) e disponível (passou no cruzamento RENAME); via
especializada e contraindicação cardíaca moram na observação, onde devem morar.
Revisita no dia em que houver fluxo de dispensação distinto. Resolver A5 no
PENDENCIAS.

### A6 · L20 — VOLTA ÀS 8 ROWS (+2 semáforo, +2 posologia)
- `decisao_semaforo.csv`: 2 rows — **furoato de mometasona** (tópico; obs.
  "acima de 2 anos — Quadro 9 p. 15–16") e **dupilumabe** (SC; obs. "só
  6m–<12a refratária grave (Quadro 8 p. 15); adulto NÃO incorporado — Port.
  SECTICS/MS nº 53/2025"). Ambas `exaustivo=true`, `versao:
  semaforo_l20_exaustiva_v2_2026-09` (**bump de caneta** — padrão I10 v2; o
  elenco de L20 muda de 6 para 8 na segunda assinatura).
- `fonte` das duas rows, o padrão que §1 exige: *PCDT Dermatite Atópica 2025
  (Port. Conjunta 28/2025, Quadros 8–9 p. 14–16, item 6.4 p. 21) — incorporação
  vigente que nomeia o fármaco; RENAME 2024 (254 págs.) não alcança o protocolo
  (nov/2025)* — declarado, não oculto.
- `posologia_sugerida.csv`: as 2 rows do §3 do rascunho (p. 21–23): mometasona
  "aplicar camada fina 1×/dia"; dupilumabe conforme o rascunho cita (dose por
  peso/idade do Quadro 8).
- **INVERTER** a guarda `TestOCruzamentoRenameMudouRows::
  test_mometasona_e_dupilumabe_ficaram_fora_do_verde_do_l20` → agora exige
  **verde COM a fonte decorada** do §1. A inversão **não é apagar**: se a fonte
  das rows citar a RENAME como se lá estivessem, a guarda NOVA reprova — o
  verde desta caneta vive da incorporação declarada, não de proxy emprestado.

### Seeds — K21 por diretriz · E03 semente
- **K21** (P-1 → decidido: **levantura por diretriz estagiada**, padrão
  F32/F41): staging da diretriz brasileira de DRGE que a levantura eleger
  (sha256 + MANIFEST, rito de adendo), rascunho E11/J45 com **idade da fonte
  declarada** no campo `fonte`. Entra na ordem de seleção da próxima semana —
  **não é gesto desta PR**.
- **E03** (P-2 → decidido: **permanece semente fonte-RENAME**): sai da ordem de
  seleção. Quando o PCDT adulto pousar no corpus, cura-se por fonte canônica.
- **Nesta PR:** atualizar o `PLANO-CURADORIA-PCDT-AUTOMATICA.md` (§4 ordem de
  seleção e §6 pendências — P-1/P-2 resolvidos nestes termos) e resolver as
  entradas A1/A3/A5 do PENDENCIAS.

## §3 Pendência nova — P-11 (nomeada, não adjudicada)

Re-conferência das **exclusões gêmeas** do J44/I50 sob o critério refinado do
§1: **fluticasona** e **glicopirrônio** (J44) · **bisoprolol** e **ivabradina**
(I50). Para cada: procurar portaria de incorporação que a nomeie para a
indicação. Achando, a row volta pelo mesmo rito do L20 (fonte decorada + guarda
invertida); não achando, a razão da exclusão ganha *"re-conferido 28/09 sob
critério refinado"*. Verificação de ~1h, próxima sessão de curadoria. **O
critério não pode derivar em silêncio por CID** — ou re-confere todos os
excluídos-por-RENAME, ou o refinamento vira exceção sem regra.

## §4 Números-alvo (ACs verificáveis)

| O quê | De | Para |
|---|---|---|
| CIDs exaustivos | 33 | **35** (+F00, +A53) |
| rows `decisao_semaforo.csv` | 225 | **233** (+4 F00, +2 A53, +2 L20) |
| rows `posologia_sugerida.csv` | 192 | **200** (+4 F00, +2 A53, +2 L20) |
| `_REPETE_POR_PROTOCOLO` | 2 entradas | **8** (+4 Alzheimer, +2 sífilis) |
| Guardas | — | F00≡G30 · A53≡A52 (novas) · A6 invertida · conjuntos exatos (lote §"as 25 condições" e i10_v2 touch) atualizados para 35 |

**Rito das guardas:** vermelho-antes-do-verde em cada guarda nova/invertida;
**sabotagem obrigatória na A6** (row com fonte citando RENAME como presença →
reprova). Suíte unitária inteira verde no pós-merge local antes do push.

## §5 Rito e limites

- **PR única de curadoria:** CSVs + guardas + PENDENCIAS resolvidas + PLANO
  atualizado + este despacho viajando no corpo. **Zero backend/app.**
- O **registro do martelo** (verbatim do Fabiano, 28/09) viaja no corpo da PR —
  regra da casa: registro em PR.
- Arquiteto **RATIFICA com prova própria** (guardas re-rodadas em worktree
  contra o head da PR) antes do martelo do Fabiano.
- Dúvida vira **pendência escrita de volta**, nunca adjudicação da engenharia.

---

*Lavrado pelo arquiteto (Z) em 28/09/2026. A caneta foi do Fabiano; o que este
despacho faz é torná-la executável sem segunda interpretação.*
