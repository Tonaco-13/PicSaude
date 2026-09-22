# RASCUNHO E28 DUPLO — semáforo + posologia, do PCDT da Síndrome dos Ovários Policísticos 2019 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Intensivo PCDT 21–25/09/2026, R2 (ter 22/09), regra (b) — *"a endocrinopatia mais frequente em mulheres em idade reprodutiva… 6%–19%"* (p. 2) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Síndrome dos Ovários Policísticos — **Portaria Conjunta SAES/SCTIE nº 6, de 02/07/2019** (Rel. CONITEC 445/2019; 188 págs.), estagiado em `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/pcdt-sindrome-dos-ovrios-policsticos.pdf` (corpus traz também o resumido e a edição ISBN para conferência) |
| **Estado** | 🟡 Rascunho — aguardando caneta do Fabiano. SEM FLIP |

---

## §1 O elenco oficial — 6 fármacos, triplamente citáveis

**§7 FÁRMACOS (p. 9–10):**

| Classe | Fármaco | Apresentação citada |
|---|---|---|
| Anticoncepcional hormonal | **etinilestradiol + levonorgestrel** | 0,03 mg + 0,15 mg |
| Progestogênio | **acetato de medroxiprogesterona** | 10 mg |
| Progestogênio | **noretisterona** | 0,35 mg |
| Antiandrogênio | **ciproterona** | 50 mg |
| Sensibilizador da insulina | **metformina** | 500/850 mg liberação normal |

**TECI (p. 21):** *"acetato de medroxiprogesterona, ciproterona, etinilestradiol
mais levonorgestrel, metformina e noretisterona"* — bate com o §7.

**CID-10 do protocolo (§2, p. 2):** `E28.2 Síndrome dos ovários policísticos` **e**
`L68.0 Hirsutismo` — **CID dupla** (ver §4.1).

**Exclusões e notas com âncora:**
- **Tiazolidinedionas NÃO recomendadas** (p. 9): *"rosiglitazona e pioglitazona
  não são recomendadas em mulheres com SOP, por não haver evidência de
  superioridade… em relação à metformina"* + pioglitazona teratogênica. 🟡 honesto
  com citação dupla.
- **Espironolactona e flutamida** aparecem SÓ em estudos do Apêndice (p. 108) e no
  monitoramento (p. 11, potássio) — **não estão no §7/TECI**: fora do elenco.
- **Letrozol ausente** do protocolo (indução de ovulação não é escopo deste PCDT;
  estudos de metformina+clomifeno no Apêndice, p. 142).
- Cirurgia bariátrica "considerando os critérios adotados no âmbito do SUS" (p. 9).

## §2 Rows propostas — `data/decisao_semaforo.csv`

Fonte proposta: `PCDT SOP 2019 (Port. Conjunta SAES/SCTIE 6/2019, §7 p. 9–10 + TECI p. 21)`.
Versão proposta: `semaforo_e28_v1_2026-09`. **6 rows, chave E28.2 (proposta — §4.1):**

| # | Princípio ativo (chave) |
|---|---|
| 1 | etinilestradiol + levonorgestrel |
| 2 | acetato de medroxiprogesterona |
| 3 | noretisterona |
| 4 | ciproterona |
| 5 | metformina ⚠️ P-9 — ver §4.2 |
| 6 | metformina (L68.0? — só se a chave dupla for aprovada, §4.1) |

> E28.2 × qualquer fármaco fora do §7 (espironolactona, flutamida, letrozol,
> pioglitazona, rosiglitazona) = 🟡 com as citações de §1.

## §3 Rows propostas — `data/posologia_sugerida.csv` (§1.6 Esquemas, p. 10)

| Princípio ativo | posologia_usual (rascunho do §1.6) |
|---|---|
| etinilestradiol + levonorgestrel | 1 comprimido (0,03+0,15 mg) ao dia por 21 dias/mês; esquemas curtos 3–4 cp/dia por 4–5 dias p/ sangramento disfuncional (p. 10) |
| acetato de medroxiprogesterona | 10 mg/dia por 10–12 dias do ciclo (p. 10) |
| noretisterona | 0,35 mg/dia em uso contínuo (efeito anticoncepcional) (p. 10) |
| ciproterona | 12,5/25/50 mg/dia VO no esquema 21/7, **em associação ao anticoncepcional oral** (p. 10) |
| metformina | Iniciar 500 mg VO após o jantar; aumentar 500–1.000 mg/semana até máx 2.550 mg/dia; dividir 2–3x/dia (liberação rápida) ou 1.000 mg 1–2x/dia (prolongada) (p. 10) |

## §4 Pontos de decisão (só o Fabiano decide)

1. **CID dupla E28.2 + L68.0** (família P-6, como G30×F00): o protocolo lista as
   duas. **Recomendo chavear em E28.2** (a condição-tratado; hirsutismo é
   manifestação) com nota; L68.0 fica para decisão futura se o seletor do
   prescritor o oferecer como indicação própria.
2. **⚠️ P-9 (dependência dura): metformina E28.2 × E11** — mesma substância, teto
   igual (2.550 mg/dia) mas contexto e escalada distintos (SOP inicia pós-jantar).
   Com a chave `(ativo, CID)` da PR **#269** (RATIFICADA, ainda não mergeada), as
   duas convivem; **o flip de E28 só sai depois do merge do #269**. Os outros 5
   fármacos não colidem com nada no CSV.
3. **Anticoncepcional como row do semáforo** — EE+levonorgestrel é prescrito para
   SOP E para contracepção (fora do semáforo). A row vale para o contexto
   E28.2/L68.0; fora dele, neutro — sem problema de desenho, apenas registrar.
4. **Freshness**: edição 2019 vigente no corpus (com resumido + ISBN); o catálogo
   aberto 08/2025 **não lista SOP** (defasado — ausência não é evidência). Se
   houver edição mais nova fora do corpus, a caneta decide conferir antes do flip.

## §5 Self-check

**Executado na mesma rodada (R2, ter 22/09/2026):** 8 citações reabertas contra o PDF
(extração fresca pypdf) — **8/8 ✅ de primeira**. Âncoras confirmadas: CID dupla
E28.2+L68.0 (p. 2) · §7 completo incluindo metformina 500/850 (p. 9) ·
tiazolidinedionas não recomendadas (p. 9; também p. 165 no Apêndice) · esquemas §1.6
ciproterona 21/7 e metformina máx 2.550 (p. 10) · TECI (p. 21).

---

*Rascunho lavrado na R2 do intensivo 21–25/09 (ter 22/09/2026, 09:01 BRT). SEM FLIP,
SEM PR, SEM código — só docs. A caneta é do Fabiano.*
