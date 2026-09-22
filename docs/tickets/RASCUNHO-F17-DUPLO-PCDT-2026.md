# RASCUNHO F17 DUPLO — semáforo + posologia, do PCDT 2020 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09. R1 lavrou este rascunho em 14/09 (slot 2: seeds K21 e E03 não têm PCDT no corpus — ver MANUAL; F17 entrou pela regra (b), prevalência APS) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT do Tabagismo — **Portaria Conjunta SCTIE/SAES nº 10, de 16/04/2020** (67 págs., `pcdt_tabagismo.pdf`), estagiada no corpus CONITEC com sha256. O resumido oficial (2021) confirma a mesma portaria |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256 `pcdt_tabagismo.pdf`: `bd3476aae32adff7069800c9ef3df247a5cea8aadd30ffffb11b65505c25f3d2`
sha256 resumido 2021: `d77b6b7d32d36e4183abb55e408355d268cda77f65283e596953912a07de8a16`

> **Convenção de página:** citações por página do PDF (pypdf). O corpo do protocolo tem
> offset — a Tabela 1 está na **p. 37 do PDF = p. 29 impressa**.

---

## §1 O elenco oficial 2020 — 4 itens, duplamente citados

Enumerados no **item 7.3 FÁRMACOS (p. 19–20)** e na **Tabela 1 – Medicamentos para
tratamento da dependência à nicotina (p. 37–38)**. Hierarquia declarada (p. 19): a
**TRN combinada** (adesivo + goma/pastilha) *"é o tratamento preferencial por sua maior
eficácia"*; alternativas: bupropiona isolada, TRN isolada, ou bupropiona + TRN isolada.

| # | Princípio ativo (chave) | Forma | Apresentações (7.3, p. 19–20) |
|---|---|---|---|
| 1 | cloridrato de bupropiona | comprimido LP | 150 mg (liberação prolongada) |
| 2 | nicotina | adesivo transdérmico (liberação lenta) | 7, 14 e 21 mg |
| 3 | nicotina | goma de mascar (liberação rápida) | 2 mg |
| 4 | nicotina | pastilha (liberação rápida) | 2 mg |

**Condição de uso (p. 19–20):** farmacoterapia independe da carga tabágica e do grau de
Fagerström, mas não se usa em contraindicados ou em quem recusa medicamento; a TRN
(inclusive combinada) **só se inicia na data de cessação** e nunca concomitante com
cigarro (7.5.1, p. 20). Em psiquiátricos (depressão, esquizofrenia) ou contraindicação à
TRN, considerar bupropiona com avaliação de especialista em saúde mental (p. 19).

## §1a Exclusões explícitas citadas (insumo para o 🟡 honesto)

1. **Vareniclina** — p. 41–42: *"Salienta-se que não foi considerada a vareniclina no
   tratamento do tabagismo, visto ter sido este medicamento avaliado e não recomendado
   pela CONITEC, conforme o Relatório de Recomendação nº 468 – Julho de 2019, e a
   Portaria nº 41/SCTIE/MS, de 24 de julho de 2019, que não a incorporou ao SUS."*
   F17×vareniclina = 🟡 "não incorporada ao SUS" com citação dupla.
2. **Nortriptilina, citisina, clonidina** — **ausentes das 67 páginas** (varredura
   completa). Wording do 🟡: "ausente do elenco do PCDT" (padrão `ausente_lista_exaustiva`).

**Contraindicações (7.7, p. 22–23):** bupropiona — epilepsia, convulsão febril na
infância, tumor SNC, TCE prévio, EEG anormal, IMAO (intervalo de 15 dias); interage com
carbamazepina, barbitúricos, fenitoína, antipsicóticos, corticoides, hipoglicemiantes.
Adesivo — IAM <15 dias, arritmias graves, angina instável, DVIP, úlcera péptica, doenças
cutâneas, gravidez e lactação. Goma — incapacidade de mascar, lesões de mucosa, ATM,
prótese dentária móvel. Pastilha — mucosa, úlcera péptica, prótese móvel, edema de Reinke.
**Risco de convulsão (7.6.3, p. 22):** 1:1.000 na dose máxima de 300 mg — por isso o
comprimido não pode ser partido/triturado (Tabela 1, p. 38).

## §2 Rows propostas — `data/decisao_semaforo.csv` (F17, novo CID no semáforo)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta: `PCDT Tabagismo 2020 (Port. Conjunta SCTIE/SAES 10/2020, item 7.3 e Tabela 1) + RENAME 2024`.
Versão proposta: `semaforo_f17_exaustiva_v1_2026-09`. `status_curadoria=validado` e
`exaustivo=true` **só após sua assinatura** (e o momento do flip, §4.3).

**Pergunta de chave (§4.1):** nicotina é UM principio_ativo em TRÊS formas. Proposta
base = **2 rows** (bupropiona, nicotina), com as formas na observação; alternativa =
**4 rows** (nicotina-adesivo, nicotina-goma, nicotina-pastilha) para casar com o que a
prescrição nomeia.

| principio_ativo (proposta base) | Ação proposta |
|---|---|
| cloridrato de bupropiona | **nova row** — chave curta `bupropiona`? ver §4.2 |
| nicotina | **nova row** — TRN: adesivo 7/14/21 mg + goma 2 mg + pastilha 2 mg |

## §3 Rows propostas — `data/posologia_sugerida.csv` (Tabela 1, p. 37–38)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte proposta: `PCDT Tabagismo 2020 (Port. Conjunta 10/2020, Tabela 1 p. 37–38 e item 7.5 p. 20–21)`.
Versão proposta: `posologia_f17_v1_2026-09`. Condição: `Tabagismo` / `F17`.

| principio_ativo | posologia_usual (rascunho da Tabela 1) | observacao (rascunho) |
|---|---|---|
| cloridrato de bupropiona | Do 1º ao 3º dia: 1 comprimido de 150 mg pela manhã. Do 4º ao 84º dia: 150 mg pela manhã + 150 mg 8 horas após (máx. 300 mg/dia; 2ª dose nunca após as 16h). | Comprimido inteiro — não partir/triturar (risco de convulsão). Idosos e IRC/hepatopatia: 150 mg/dia (7.5.4, p. 21). Sujeito a Portaria SVS 344/98. |
| nicotina (adesivo) | 1ª a 4ª semana: 21 mg/24h; 5ª a 8ª: 14 mg/24h; 9ª a 12ª: 7 mg/24h. Dose inicial conforme cigarros/dia: 6–10 → 7 mg; 11–19 → 14 mg; ≥20 → 21 mg (7.5.2, p. 20). Não exceder 42 mg/dia. | Aplicar pela manhã em área coberta, rodízio de locais, mesma hora (Tabela 1). Até 5 cigarros/dia: SEM adesivo — só goma/pastilha. |
| nicotina (goma) | 1 goma de 2 mg nos momentos de fissura; não ultrapassar 5 gomas de 2 mg/dia. Técnica: mascar até sabor forte, estacionar na bochecha ~2 min, repetir por 30 min. | Copo de água antes (neutralizar pH). Contra: mucosa, ATM, prótese móvel. |
| nicotina (pastilha) | 1 pastilha de 2 mg nos momentos de fissura; não ultrapassar 5 pastilhas de 2 mg/dia. Mover de lado a lado até dissolver (20–30 min). | Não partir, mastigar ou engolir; não comer/beber com a pastilha. Contra: edema de Reinke, prótese móvel. |
| nicotina (TRN combinada) | Adesivo conforme esquema acima + goma ou pastilha para fissura. Tratamento PREFERENCIAL (p. 19). Associação de adesivos (>20 cigarros/dia): 21+7, 21+14 ou 21+21 mg/dia, retirando 7 mg/semana (7.5.3, p. 20–21). | Iniciar só na data de cessação; nunca com cigarro (7.5.1, p. 20). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave da nicotina** — 1 row `nicotina` (formas na observação) vs 3 rows por forma
   (`nicotina adesivo/goma/pastilha`, citando a mesma portaria) vs rows-alias. A
   prescrição do PNCT nomeia a forma ("adesivo de nicotina"); o `canon_ativo` não
   normaliza forma farmacêutica. Recomendação do rascunhista: **3 rows por forma +
   1 row-âncora `nicotina`** (total 4), todas citando a mesma Tabela 1 — espelha a
   adjudicação das grafias da insulina (E11 §4.5): previne amarelo-falso na digitação.
2. **Chave da bupropiona** — o PCDT diz "cloridrato de bupropiona" (7.3, p. 19);
   F32 (depressão, já exaustiva) provavelmente usa chave `bupropiona`. Unificar a chave
   entre os dois CIDs (mesma substância) — conferir antes do flip para não criar par
   `bupropiona`/`cloridrato de bupropiona` divergente.
3. **Momento do flip** — regra do vagão: `exaustivo=true` só depois do merge do strip
   de dose; aqui o risco é "Bupropiona 150mg" e "Adesivo 21mg" darem amarelo-falso.
4. **Goma/pastilha 4 mg** — o 7.5.2a (p. 20) cita *"3 gomas/pastilhas de 4 mg"* para
   ≤5 cigarros/dia, mas o elenco 7.3 e a Tabela 1 só trazem **2 mg**. Inconsistência
   interna do PCDT: registrar como nota no rascunho (não criar row de 4 mg — o elenco
   oficial não a lista) e decidir se merece nota na fonte.
5. **Cruzamento RENAME 2024** — confirmar componente (o próprio PCDT manda: *"Verificar
   na RENAME vigente em qual componente da Assistência Farmacêutica se encontram os
   medicamentos preconizados"*, nota do Termo, p. 35). O rascunhista pode preparar o
   cruzamento na sessão de assinatura.

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 14/09/2026, R1 do INTENSIVO PCDT, do PDF oficial
estagiado (sha256 `bd3476aa…`). Elenco do item 7.3 (p. 19–20); esquemas da Tabela 1
(p. 37–38) e do 7.5 (p. 20–21); exclusão da vareniclina citada das p. 41–42 e da
referência à Portaria nº 41/SCTIE/MS/2019 (p. 53); contraindicações do 7.7 (p. 22–23).
Sua revisão contra o PDF é parte do rito — a assinatura fecha.*

> **SELF-CHECK (R1, 14/09/2026):** 7 citações reabertas e conferidas contra o PDF —
> bupropiona 4º–84º dia (p. 38), adesivo 21→14→7 mg por semanas (p. 37), elenco 7.3
> bupropiona LP 150 mg (p. 19) e goma/pastilha 2 mg (p. 20), risco de convulsão 1:1.000
> (p. 22), exclusão da vareniclina (frase que atravessa a quebra p. 41→42, citada como
> 41–42) + âncora Portaria 41/SCTIE/MS/2019 (p. 42) — **7/7 ✅**.
