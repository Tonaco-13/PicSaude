# RASCUNHO G20 DUPLO — semáforo + posologia, do PCDT da Doença de Parkinson 2025 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Intensivo PCDT 21–25/09/2026, R2 (ter 22/09), regra (b) — prevalência APS (o próprio PCDT, p. 3: *"A identificação… e o encaminhamento ágil… dão à Atenção Primária um caráter essencial"*) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Doença de Parkinson — **Portaria Conjunta SAES/SECTICS nº 16, de 01/08/2025** (Rel. CONITEC 957/2024; 77 págs.), estagiado em `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/pcdt-doenca-de-parkinson.pdf` |
| **Estado** | 🟡 Rascunho — aguardando caneta do Fabiano. SEM FLIP |

---

## §1 O elenco oficial — 10 substâncias, triplamente citadas

**TECI – Termo de Esclarecimento (p. 29):** *"AMANTADINA, BIPERIDENO, CLOZAPINA,
ENTACAPONA, LEVODOPA + BENSERAZIDA, LEVODOPA + CARBIDOPA, PRAMIPEXOL, RASAGILINA,
TRIEXIFENIDIL E RIVASTIGMINA"*.

**§6.5 Medicamentos/apresentações (p. 14–15):** amantadina 100 mg · biperideno 2 mg
e 4 mg LP · clozapina 25/100 mg · entacapona 200 mg · levodopa+benserazida 100/25 e
200/50 · levodopa+carbidopa 200/50 e 250/25 · pramipexol 0,125/0,25/1 mg · rasagilina
1 mg · rivastigmina cápsulas 1,5–6 mg + adesivos 9/18 mg + solução 2 mg/mL ·
triexifenidil 5 mg.

**Quadro 5 (p. 15–17)** — esquemas **com fase** (Inicial · Avançada · Condições
especiais): monoterapia inicial = levodopa (carb. ou bens.) OU pramipexol OU
rasagilina (p. 10, *"cinco medicamentos… em monoterapia"* contando as duas
levodopas).

**CID-10 do protocolo (§2, p. 3):** `G20 Doença de Parkinson` — CID único, sem
dilema de chave.

**Notas finas com âncora:**
- **Selegilina DESCONTINUADA no Brasil** — p. 10: migração para rasagilina sem
  redução gradual. Não é row.
- **Rotigotina: avaliada e FORA do elenco** — Questão 1 do Apêndice (p. 34–51):
  para "sintomas noturnos, wearing off ou freezing", a rotigotina *"parece ser capaz
  de promover benefícios"* (p. 35) MAS *"a incorporação da rotigotina resultaria em
  aumento dos gastos para o sistema"* (p. 35; impacto +R$ 93 mi/5 anos, p. 51) —
  não entrou no TECI nem no Quadro 5. **G20 × rotigotina = 🟡 "avaliada e não
  incorporada"**, com citação.

## §2 Rows propostas — `data/decisao_semaforo.csv`

Fonte proposta: `PCDT Parkinson 2025 (Port. Conjunta SAES/SECTICS 16/2025, TECI p. 29 + Quadro 5 p. 15–17)`.
Versão proposta: `semaforo_g20_v1_2026-09`. **10 rows, chave G20:**

| # | Princípio ativo (chave) | Fase (Quadro 5 — vai na observação) |
|---|---|---|
| 1 | levodopa + carbidopa | Inicial · Avançada |
| 2 | levodopa + benserazida | Inicial · Avançada |
| 3 | pramipexol | Inicial · Avançada |
| 4 | rasagilina | Inicial · Avançada |
| 5 | amantadina | Inicial · Avançada (discinesias — p. 12 com ressalva de uso) |
| 6 | entacapona | Avançada (flutuação; p. 12 alerta contra uso p/ induzir discinesias) |
| 7 | triexifenidil | Inicial · Avançada (tremor predominante) |
| 8 | biperideno | Inicial · Avançada |
| 9 | clozapina | **Condições especiais** (psicose na DP) |
| 10 | rivastigmina | **Condições especiais** (declínio cognitivo na DP) |

> As duas associações de levodopa são chaves DISTINTAS (protocolo as lista separadas
> — sem colisão canon). Nenhum destes 10 ativos existe hoje no CSV: **flip sem
> dependência P-9**.

## §3 Rows propostas — `data/posologia_sugerida.csv` (Quadro 5, p. 15–17)

| Princípio ativo | posologia_usual (rascunho do Quadro 5) |
|---|---|
| levodopa + benserazida | 200/50 mg/dia em ≥2 administrações; média eficaz 600–750 mg/dia; máx 2.000 mg/dia (p. 15) |
| levodopa + carbidopa | 250/25 mg/dia em ≥2 administrações; máx 2.000 mg/dia de levodopa (p. 15) |
| pramipexol | 0,375 mg/dia em 3 doses, +a cada 5–7 dias; manutenção 0,375–4,5 mg/dia (p. 16) |
| rasagilina | 1 mg/dia (p. 16) |
| amantadina | 100 mg 12/12h isolada; inicial 100 mg/dia podendo chegar a 400 mg/dia; retirada gradual 1–2 sem (p. 16) |
| entacapona | 200 mg com cada dose de levodopa; máx 2 g/dia (p. 16) |
| triexifenidil | 0,5–1 mg 2x/dia com incrementos a cada 3–5 dias; usual até 10 mg/dia; máx 15 mg/dia (p. 16) |
| biperideno | 2–8 mg/dia, iniciando 1 mg 2x/dia; não interromper abruptamente (p. 16) |
| clozapina | 12,5 mg/dia inicial, +12,5 mg (máx 2 aumentos/semana); média 25–37,5 mg/dia; **nunca >100 mg/dia** (p. 17) |
| rivastigmina | Oral: 1,5 mg 2x/dia → máx 6 mg 2x/dia; adesivo: 9 mg/24h → 18 mg/24h após ≥4 semanas (p. 17) |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Clozapina e rivastigmina** são "condições especiais" (psicose/declínio
   cognitivo NA DP) — entram como rows com observação (mesmo dilema resolvido nas
   reações do A30) ou ficam fora do semáforo do prescritor? **Recomendo entrar**:
   elenco completo é a lei da exaustividade; a observação carrega o contexto.
2. **Fase como observação, não como chave** — o protocolo gradua por fase, não por
   CID (CID único). A observação da row leva "Inicial · Avançada" / "Condições
   especiais" conforme o Quadro 5.
3. **Rotigotina 🟡 com relatoria** — "avaliada (Questão 1, Rel. 957/2024) e não
   incorporada (custo)" — manter como exclusão citada.
4. **Amantadina/entacapona** têm ressalvas de uso no texto (p. 11–12: uso
   indiscriminado de entacapona "com o intuito de induzir discinesias" é rechaçado) —
   entram com observação de ressalva citada.

## §5 Self-check

**Executado na mesma rodada (R2, ter 22/09/2026):** 9 citações reabertas contra o PDF
(extração fresca pypdf) — **9/9 ✅ de primeira, nenhuma correção necessária**.
Âncoras confirmadas: G20 (p. 3) · monoterapia inicial e selegilina descontinuada
(p. 10) · Quadro 5 título (p. 15) · pramipexol/entacapona (p. 16) · clozapina
(p. 17) · TECI 10 substâncias (p. 29) · rotigotina custo (p. 35).

---

*Rascunho lavrado na R2 do intensivo 21–25/09 (ter 22/09/2026, 09:01 BRT). SEM FLIP,
SEM PR, SEM código — só docs. A caneta é do Fabiano.*
