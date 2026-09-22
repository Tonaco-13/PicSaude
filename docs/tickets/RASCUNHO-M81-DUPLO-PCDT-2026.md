# RASCUNHO M81 DUPLO — semáforo + posologia, do PCDT 2025 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09. R2 lavrou este rascunho em 15/09 (regra (b), substituindo a incontinência urinária — elenco vazio, ver MANUAL R2) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Osteoporose — **Portaria Conjunta SAES/SECTICS nº 22, de 22/10/2025** (98 págs., `portaria-no-22-pcdt-da-osteoporose.pdf`), estagiada no corpus CONITEC com sha256. Edição novíssima (consulta pública nº 06/2023; revisão de romosozumabe/teriparatida de julho/2024 embutida) |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256: `7b1db1548263550c2fc6b85d66b4152df5b8b76e16606b575112bbd375e71d43`

> **Escopo CID (p. 3):** M80.x (osteoporose COM fratura patológica) · M81.x (SEM
> fratura) · M82.x (na mielomatose e outras doenças). Chave proposta para o semáforo:
> **M81** (ver §4.1).

---

## §1 O elenco oficial 2025 — 12 itens, duplamente citados

Enumerados no **item 7.2.7 MEDICAMENTOS (p. 12)** e no **7.2.8 ESQUEMAS DE
ADMINISTRAÇÃO (p. 12–13)**. Tratamento preferencial (p. 9): *"reposição de cálcio e
colecalciferol (vitamina D) associada ao uso de um bisfosfonato (alendronato ou
risedronato)"*; IV apenas para intolerância gastrintestinal/dificuldade de deglutição.

| # | Princípio ativo (chave) | Classe / papel | Apresentação (7.2.7) |
|---|---|---|---|
| 1 | alendronato de sódio | bisfosfonato oral — 1ª escolha | comp. 10 e 70 mg |
| 2 | risedronato sódico | bisfosfonato oral — 1ª escolha | comp. 35 mg |
| 3 | ácido zoledrônico | bisfosfonato IV | sol. infusão 5 mg/100 mL |
| 4 | pamidronato dissódico | bisfosfonato IV — reserva (ver §1a.5) | pó inj. 60 mg |
| 5 | carbonato de cálcio | suplemento — base do tratamento | comp. 1.250 mg (=500 mg elem.) |
| 6 | carbonato de cálcio + colecalciferol | suplemento associado | 500 mg + 200/400 UI; 600 mg + 400 UI |
| 7 | fosfato de cálcio tribásico + colecalciferol | suplemento associado | 600 mg elem. + 400 UI |
| 8 | raloxifeno | modulador seletivo do receptor de estrogênio | comp. 60 mg |
| 9 | estrogênios conjugados | reposição (climatério c/ sintomas vasomotores) | comp. 0,3 e 0,625 mg |
| 10 | romosozumabe | anticorpo anti-esclerostina — falha terapêutica/grave | sol. inj. 90 mg/mL |
| 11 | calcitonina | antirreabsortivo — **reserva estrita (§1a.4)** | sol. nasal 200 UI/dose |
| 12 | calcitriol | vitamina D ativa — **indicação estrita (§1a.3)** | cáps. 0,25 mcg |

## §1a Exclusões e reservas explícitas citadas (insumo para o 🟡 honesto)

1. **Teriparatida — EXCLUÍDA** (p. 11, seção 7.2.5 Romosozumabe): *"Em julho de 2024
   foram revisadas as evidências... A recomendação foi favorável à ampliação de uso do
   romosozumabe para o tratamento de osteoporose grave e falha terapêutica **e pela
   exclusão da teriparatida**"*. M81×teriparatida = 🟡 "excluída do PCDT" com citação.
2. **Denosumabe — ausente do elenco**: não aparece nas seções de tratamento
   (7.2.1–7.2.7); foi avaliado no Relatório de Recomendação nº 742/2022 (PICO do
   apêndice, p. 79). Wording do 🟡: "ausente do elenco do PCDT" (padrão
   `ausente_lista_exaustiva`).
3. **Calcitriol estrito (p. 10):** *"só é preconizado para pacientes com insuficiência
   renal crônica com DCE ≤30 mL/min, com osteomalácia hipofosfatêmica ou por deficiência
   de 1-alfa-hidroxilase, com insuficiência hepática ou hipoparatireoidismo"* —
   não substitui a reposição de colecalciferol.
4. **Calcitonina estrita (p. 12):** *"Permanece como opção terapêutica somente"*
   em osteonecrose de mandíbula/fratura atípica por bisfosfonato ou contraindicação
   absoluta aos outros; *"preconiza-se evitar seu uso ou limitar o uso prolongado"*.
5. **Pamidronato reserva (p. 11):** *"este Protocolo preconiza seu uso apenas em casos
   de indisponibilidade ou contraindicações ao ácido zoledrônico"*.
6. **"Férias" do bisfosfonato (p. 10):** após 5 anos de uso oral, pausa de 1 a 2 anos
   (fratura atípica de fêmur/necrose de mandíbula raras mas associadas ao longo prazo).
   Duração (p. 13): 5 anos (oral) · 3 anos (IV); extensível a 10/6 anos se risco
   elevado (T-escore < −3,0 ou fraturas). Romosozumabe: máx. 12 meses, seguindo
   bisfosfonato (p. 11, 13).

**Contraindicações dos orais (p. 10):** hipersensibilidade, hipocalcemia, gravidez e
lactação, IRC grave (DCE <30) e incapacidade de permanecer sentado/em pé 30–60 min após
a ingestão. Romosozumabe: não iniciar se IM/AVE no ano anterior; corrigir cálcio antes
(p. 11). Estrógenos: risco de AVE, câncer de mama e TEV; com progestágeno se útero
presente (p. 11, 13).

## §2 Rows propostas — `data/decisao_semaforo.csv` (M81, novo CID no semáforo)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta: `PCDT Osteoporose 2025 (Port. Conjunta SAES/SECTICS 22/2025, itens 7.2.7 e 7.2.8) + RENAME 2024`.
Versão proposta: `semaforo_m81_exaustiva_v1_2026-09`. Chave proposta: **M81** (ver §4.1
para M80/M82). `exaustivo=true` **só após sua assinatura**.

| principio_ativo | Ação proposta (M81) |
|---|---|
| alendronato de sódio · risedronato sódico | novas rows — 1ª linha |
| carbonato de cálcio · carbonato de cálcio + colecalciferol · fosfato de cálcio tribásico + colecalciferol | novas rows — base do tratamento |
| ácido zoledrônico · pamidronato dissódico | novas rows — IV (pamidronato com reserva na observação) |
| raloxifeno · estrogênios conjugados | novas rows |
| romosozumabe | nova row — osteoporose grave/falha terapêutica |
| calcitonina · calcitriol | novas rows — **com as indicações estritas estampadas na observação** (🟡-prone) |

## §3 Rows propostas — `data/posologia_sugerida.csv` (7.2.8, p. 12–13)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte proposta: `PCDT Osteoporose 2025 (Port. Conjunta 22/2025, item 7.2.8 p. 12–13)`.
Versão: `posologia_m81_v1_2026-09`. Condição: `Osteoporose` / `M81`.

| principio_ativo | posologia_usual (rascunho do 7.2.8) | observacao (rascunho) |
|---|---|---|
| alendronato de sódio | Tomar 10 mg/dia OU 70 mg 1 vez por semana, por via oral, em jejum com 200 mL de água; permanecer sentado/em pé por 30–60 min. | 1ª linha com cálcio+vitD (p. 9). Não usar se DCE <35 (p. 10). |
| risedronato sódico | Tomar 35 mg, 1 vez por semana, por via oral, em jejum 30 min antes da primeira refeição; sentado/em pé por 30 min. | 1ª linha. Monitorar função renal pré-existente 1-3 meses (p. 10). |
| ácido zoledrônico | 5 mg por via intravenosa, 1 vez ao ano. | Para intolerância/dificuldade de deglutição dos orais (p. 9-10). |
| pamidronato dissódico | 60 mg por via IV a cada 3 meses, diluído em 500 mL de SF 0,9%, infusão mínima de 2 horas. | Apenas se zoledrônico indisponível/contraindicado (p. 11). |
| carbonato de cálcio | Tomar 500 a 1.400 mg/dia de cálcio elementar, por via oral, fracionando no máximo 500 mg por vez. | Meta 1.000–1.200 mg/dia; <1.400 mg/dia por segurança CV (p. 9). |
| carbonato de cálcio + colecalciferol | 1 comprimido 1–2×/dia conforme apresentação (500–600 mg cálcio elem. + 200–400 UI). | Colecalciferol: 800–1.000 UI/dia (idosos ≥60a até 2.000 UI/dia) — p. 9–10. |
| fosfato de cálcio tribásico + colecalciferol | 600 a 1.200 mg/dia de cálcio elementar, fracionando no máximo 600 mg por vez, com 400 UI de colecalciferol por comprimido. | Alternativa de reposição associada. |
| raloxifeno | Tomar 60 mg por dia, por via oral. | Pós-menopausa; previne fratura vertebral (não quadril); risco TEV (p. 11). |
| estrogênios conjugados | Dose individualizada (0,3 ou 0,625 mg), por via oral. | Climatério com sintomas vasomotores; com progestágeno se útero presente (p. 11). |
| romosozumabe | 210 mg por via subcutânea, 1 vez por mês, por até 12 meses; suplementar cálcio e vitamina D. | Osteoporose grave/falha terapêutica (ampliação 2024, p. 11); não iniciar se IM/AVE no ano anterior (p. 11). |
| calcitonina | 400 UI/dia por via intranasal. | SÓ em osteonecrose de mandíbula/fratura atípica por bisfosfonato ou contraindicação absoluta; evitar uso prolongado (p. 12). |
| calcitriol | Tomar 0,25 mcg, 2 vezes ao dia, por via oral. | SÓ em IRC (DCE ≤30), osteomalácia hipofosfatêmica, defic. 1-alfa-hidroxilase, insuf. hepática ou hipoparatireoidismo (p. 10). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave CID** — o PCDT cobre M80.x, M81.x e M82.x (p. 3; 17 códigos listados).
   Proposta: rows sob **M81** (osteoporose sem fratura — o cenário de manutenção que a
   APS prescreve); M80 (com fratura) mereceria as mesmas rows — replicar dobraria a
   contagem. Alternativa: chave de 3 dígitos M81 cobrindo M81.0–M81.8 conforme o
   seletor de condição do prescritor. **Conferir contra os CIDs que a UI realmente
   oferece** (mesma pergunta do R52.1/R52.2).
2. **Suplementos como rows de semáforo?** cálcio/colecalciferol são base do tratamento
   (p. 9), mas o semáforo avalia fármaco×condição; incluir os 3 itens de suplemento
   como rows verdes é a leitura literal do 7.2.7 — decidir se a caneta os quer no
   elenco exaustivo ou apenas na posologia.
3. **Romosozumabe na APS?** o item está no elenco (falha terapêutica/osteoporose
   grave — via especializada, aplicação mensal SC). Manter como row (leitura literal)
   com observação, ou deixar 🟡-neutro até haver fluxo de dispensação — decisão de
   produto além da curadoria.
4. **Momento do flip** — regra do vagão (strip de dose): "Alendronato 70mg" é a
   apresentação semanal — o sufixo de dose importa aqui também.
5. **Cruzamento RENAME 2024** — confirmar os 12 (suspeita: romosozumabe é componente
   especializado; estrogênios conjugados podem ter saído); rascunhista prepara na
   sessão de assinatura.

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 15/09/2026, R2 do INTENSIVO PCDT, do PDF oficial
estagiado (sha256 `7b1db154…`). Elenco do item 7.2.7 e esquemas do 7.2.8 (p. 12–13);
preferencial de cálcio+vitD+bisfosfonato oral (p. 9); reservas e exclusões citadas
(p. 9–12); escopo CID (p. 3). Sua revisão contra o PDF é parte do rito — a assinatura
fecha.*

> **SELF-CHECK (R2, 15/09/2026):** 7 citações reabertas e conferidas contra o PDF —
> elenco 7.2.7 e esquema 7.2.8 do alendronato (p. 12), preferencial de tratamento
> (p. 9), zoledrônico anual (p. 12), romosozumabe mensal (p. 13), calcitriol estrito
> (p. 10) — ✅. **1 correção de página aplicada**: a exclusão da teriparatida estava
> citada como p. 9 e o PDF a traz na **p. 11** (seção 7.2.5) — corrigida neste
> documento. **7/7 ✅ pós-correção** (a lição da adjudicação da insulina funcionando:
> o PDF é o juiz).
