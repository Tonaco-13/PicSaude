# RASCUNHO L20 DUPLO — semáforo + posologia, do PCDT 2025 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09. Lavrado em 17/09 pela R4 como **RESGATE da R3** (cron de qua 16 não disparou — ver MANUAL R3/R4) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Dermatite Atópica — **Portaria Conjunta nº 28, de 27/11/2025** (56 págs., `pcdt-da-dermatite-atopica.pdf`), edição novíssima |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256: `8751987f2beaa7572dfca7d09abac08f77efe5c60aea1f58ba37ad4a8cac7553`

> **Escopo CID (p. 3):** L20.0 (prurigo de Besnier) e L20.8 (outras dermatites
> atópicas). Chave proposta: **L20**.

---

## §1 O elenco oficial 2025 — 8 medicamentos, duplamente citados

Enumerados no **item 6.4 MEDICAMENTOS (p. 21)** e distribuídos por gravidade/faixa
etária nos **Quadros 8 e 9 (p. 14–16)**. Primeira linha (6.2, p. 14): tópicos
(pomadas/cremes) + **ciclosporina e metotrexato** na DA moderada a grave.

| # | Princípio ativo (chave) | Via | Apresentações (6.4) | Posição (Quadro 9) |
|---|---|---|---|---|
| 1 | acetato de hidrocortisona | tópico | creme 10 mg/g | leve → grave, todas as idades |
| 2 | dexametasona | tópico | creme 1 mg/g | leve → grave, todas as idades |
| 3 | furoato de mometasona | tópico | creme/pomada 1 mg/g | idem — **acima de 2 anos** (*) |
| 4 | tacrolimo | tópico | pomada 0,3 ou 1 mg/g | idem — **acima de 2 anos** (*) |
| 5 | ciclosporina | sistêmico | cáp. 25/50/100 mg; sol. 100 mg/mL | moderada a grave, sem restrição |
| 6 | metotrexato | sistêmico | comp. 2,5 mg; inj. 25 mg/mL | moderada a grave, sem restrição |
| 7 | dupilumabe | sistêmico (SC) | sol. inj. 200/300 mg | **grave refratária, 6 meses a <12 anos** |
| 8 | upadacitinibe | sistêmico (VO) | comp. LP 15 mg | **grave refratária, 12 a <18 anos** |

(*) marcação do Quadro 9 (p. 15–16): "Acima de 2 anos".

**Refratariedade (Quadro 8, p. 15):** dupilumabe e upadacitinibe só para *"Grave com
falha, intolerância ou contraindicação à ciclosporina ou ao metotrexato e que possuem
indicação à terapia sistêmica"* — populações etárias distintas. Metas de resposta
(EASI-50/75, SCORAD, p. 14) balizam continuidade.

## §1a Exclusões explícitas citadas (insumo para o 🟡 honesto)

1. **Dupilumabe e upadacitinibe em ADULTOS/IDOSOS** — p. 21 (6.3.3): *"Após avaliação
   da Conitec, os medicamentos dupilumabe e upadacitinibe não foram incorporados ao SUS
   para tratamento de adultos ou idosos com DA (**Portaria SECTICS/MS nº 53/2025**).
   Assim, este Protocolo não preconiza o uso dos medicamentos nesta população."*
   → L20×dupilumabe em adulto = 🟡 "não incorporado p/ adultos (Port. 53/2025)";
   a row verde vale SÓ para a população 6m–<18a do Quadro 8.
2. **Tacrolimo/mometasona <2 anos** — marcação do Quadro 9 e contraindicações (6.6,
   p. 23): mometasona "menores de dois anos"; tacrolimo "menores de dois anos". 🟡-nota.
3. **Antibióticos tópicos/curativos oclusivos** — não preconizados (texto 6.2.1);
   **ciclosporina + fototerapia UV não é recomendada** (p. 22).
4. **Tacrolimo via sistêmica/pimecrolimo** — pimecrolimo ausente do 6.4 (elenco);
   wording "ausente do elenco do PCDT".

**Contraindicações (6.6, p. 23):** dexametasona (TB cutânea, varicela, fungo/herpes);
hidrocortisona (TB/sífilis cutânea, vírus, rosácea, dermatite perioral); ciclosporina
(IRC, neoplasia ativa, lactação, infecções ativas, TB sem tratamento, HAS não
controlada); metotrexato (aleitamento, IR/IH grave, álcool, infecções graves).

## §2 Rows propostas — `data/decisao_semaforo.csv` (L20, novo CID no semáforo)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta: `PCDT Dermatite Atópica 2025 (Port. Conjunta 28/2025, item 6.4 p. 21 e Quadros 8–9 p. 14–16) + RENAME 2024`.
Versão proposta: `semaforo_l20_exaustiva_v1_2026-09`. Chave: **L20**. `exaustivo=true`
**só após sua assinatura**.

| principio_ativo | Ação proposta |
|---|---|
| acetato de hidrocortisona · dexametasona · furoato de mometasona · tacrolimo | novas rows — tópicos (mometasona/tacrolimo com "acima de 2 anos" na observação) |
| ciclosporina · metotrexato | novas rows — sistêmicos moderada/grave |
| dupilumabe | nova row — **observação: só 6m–<12a refratária; adulto = 🟡 Port. 53/2025** |
| upadacitinibe | nova row — **observação: só 12–<18a refratária; adulto = 🟡 Port. 53/2025** |

## §3 Rows propostas — `data/posologia_sugerida.csv` (6.5, p. 21–23)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte: `PCDT Dermatite Atópica 2025 (Port. Conjunta 28/2025, item 6.5, p. 21–23)`.
Versão: `posologia_l20_v1_2026-09`. Condição: `Dermatite atópica` / `L20`.

| principio_ativo | posologia_usual (rascunho do 6.5) | observacao (rascunho) |
|---|---|---|
| acetato de hidrocortisona | Aplicar camada fina do creme 2–3×/dia sob ligeira fricção; após melhora, 1×/dia na maioria dos casos. | Lactentes/crianças <4a: não prolongar por mais de 3 semanas (p. 21). |
| dexametasona | Aplicar o creme 1–3×/dia por períodos inferiores a 30 dias; manutenção 2×/semana. | Uso prolongado de corticoide tópico: evitar. |
| furoato de mometasona | Aplicar camada fina sobre a área afetada 1×/dia. | Não usar curativo oclusivo salvo indicação médica; >2 anos. |
| tacrolimo | Iniciar com pomada 1 mg/g 2×/dia até desaparecer da lesão; manutenção 0,3–1 mg/g 1×/dia 2×/semana nas áreas recorrentes, com 2–3 dias de intervalo entre aplicações. | ≥16a: iniciar com 1 mg/g; 2–16a: conforme bula; >2 anos. |
| ciclosporina | Via oral, dose conforme curso da doença (aguda → remissão; manutenção → evitar recorrência). Uso por 8–12 meses (extensível +1 ano se bem tolerada); desmame reduzindo 0,5–1,0 mg/kg/dia a cada 2 semanas. | Incorporada em 2022 para moderada/grave sem restrição de idade (p. 17). Nefrotoxicidade — monitorar função renal (p. 21). |
| metotrexato | ≥16 anos: 15–25 mg/semana, VO ou injetável. 2–16 anos: 0,4–0,6 mg/kg/semana (10–15 mg/m²/semana). | SEMANAL (não diário — p. 21); suplementar ácido fólico. |
| dupilumabe | SC, dose por peso/idade: 6m–5a (5–<15 kg): 200 mg inicial, depois 200 mg 4/4 semanas; (15–<30 kg): 300 mg 4/4s. 6–<12a: 600 mg → 200–300 mg 2/4s conforme peso. | Rodízio de local de injeção; inspecionar a solução antes (p. 22). Só 6m–<12a refratária. |
| upadacitinibe | Tomar 15 mg/dia, via oral, inteiro com água, aproximadamente no mesmo horário. | 12–<18a com peso ≥40 kg. Não partir/abrir/mastigar (p. 23). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Dupilumabe/upadacitinibe — verde com cláusula ou 🟡 por padrão?** As rows são
   verdes SÓ nas populações etárias dos Quadros 8/9; adulto = não incorporado (Port.
   53/2025). O semáforo não distingue idade — decidir: row com observação forte
   (recomendado) vs. deixar ambos 🟡 até o semáforo ter metadado de população.
2. **Metotrexato compartilhado** — M81 (revisão R52 não — mas G40 não usa; **R52 não
   traz**; porém F32/depressão? não) — atenção à lição do #261: `carregar_posologias`
   indexa por princípio ativo; L20×metotrexato 15–25 mg/SEMANA é dose radicalmente
   diferente de outras condições — a colisão do índice é erro clínico calado.
   Confirmar contra o DESENHO-POSOLOGIA-POR-CONDICAO (chave composta) antes do flip.
3. **Chave CID** — L20.0/L20.8 listados; proposta L20 genérica. Confirmar contra o
   seletor de condição do prescritor (P-6).
4. **Momento do flip** — regra do vagão (strip de dose): "Tacrolimo 0,3mg/g" vs
   "1mg/g" e as faixas de peso do dupilumabe.
5. **Cruzamento RENAME 2024** — confirmar os 8 (dupilumabe/upadacitinibe em componente
   especializado); rascunhista prepara na sessão de assinatura.

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 17/09/2026 (R4, resgatando a R3 do INTENSIVO
PCDT), do PDF oficial estagiado (sha256 `8751987f…`). Elenco do item 6.4 (p. 21);
esquemas do 6.5 (p. 21–23); Quadros 8–9 (p. 14–16); exclusão de dupilumabe/upadacitinibe
em adultos com âncora Port. SECTICS 53/2025 (p. 21); contraindicações do 6.6 (p. 23);
escopo CID (p. 3). Sua revisão contra o PDF é parte do rito — a assinatura fecha.*

> **SELF-CHECK (R4, 17/09/2026):** 5 citações reabertas e conferidas contra o PDF —
> elenco 6.4 do tacrolimo (p. 21), exclusão de dupilumabe/upadacitinibe em adultos com
> âncora Portaria SECTICS 53/2025 (p. 21), tópicos do Quadro 9 (p. 15), metotrexato
> 15–25 mg/semana (p. 22), CID L20.0 (p. 3) — **5/5 ✅**.
