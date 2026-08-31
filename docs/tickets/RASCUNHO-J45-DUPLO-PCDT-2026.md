# RASCUNHO J45 DUPLO — semáforo + posologia, do PCDT da Asma 2026 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Vagão §2 (fila reordenada 07/08: E11 → J45) · "bote a fila para andar", Fabiano 30/08 |
| **Rascunhista** | Arquiteto (Z), **com a extração da máquina (#224) como matéria-prima** — primeira levantura que nasce da camada 1 |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | **PCDT da Asma — Portaria Conjunta SAES/SCTIE nº 43, de 24/03/2026**, 55 págs., no corpus (`corpus-conitec-2026-08-30/pcdt-da-asma.pdf`, sha256 no `SHA256SUMS.txt`) |
| **Estado** | ✅ **ASSINADO — Fabiano, 31/08/2026** ("E11 e J45 assinado"), com as recomendações do §4 aplicadas: combinação `formoterol + budesonida` INCLUÍDA; fluticasona/salmeterol FORA (anexo histórico); sessão dupla com E11. Executado na **PR #233**: 11 rows no semáforo + 11 na posologia, fonte Port. Conjunta SAES/SCTIE 43/2026. Guarda: `test_semaforo_flip_e11_j45.py` (exclusões teofilina/montelucaste 🟡, p. 36) |

---

## §1 O elenco 2026 — 11 chaves individuais + 1 combinação

Extraído da máquina (§7.4.1, p. 37–41) e **validado contra o PDF pelo arquiteto**
(varredura de fármacos comuns de asma no documento inteiro). A máquina agrupou
por subseção (pares); para o semáforo, **as chaves são individuais** — a CSV é
por `principio_ativo`, e "beclometasona" prescrita sozinha tem que acender 🟢:

| # | Chave proposta | Evidência no PDF |
|---|---|---|
| 1 | beclometasona | §7.4.1 + Quadro 10 (p. 38), doses por faixa etária |
| 2 | budesonida | §7.4.1 + Quadro 10 e 11 (p. 38) |
| 3 | salbutamol | §7.4.1 (p. 39), exacerbações |
| 4 | fenoterol | §7.4.1 (p. 39), alternativa ao salbutamol |
| 5 | prednisona | §7.4.1 (p. 38), corticoide oral |
| 6 | prednisolona | §7.4.1 (p. 38), incluindo pediátrico |
| 7 | mepolizumabe | §7.4.1 (p. 39), asma grave |
| 8 | omalizumabe | §7.4.1 (p. 39–41), Quadros 12–13 |
| 9 | benralizumabe | §7.4.1 (p. 40) |
| 10 | dupilumabe | §7.4.1 (p. 41) |
| 11 | **formoterol+budesonida** (combinação) | §7.4.1 + Quadro 11 (p. 38) — estratégia AIR/MART |

**Por que a row 11 existe:** o protocolo nomeia a **combinação** como o
medicamento da estratégia preferencial (AIR/MART, Quadro 11) — e `canon_ativo`
não decompõe combinações: "Formoterol+Budesonida" digitada não casa com as
chaves individuais de formoterol nem de budesonida. Sem a row própria,
**amarelo falso sistemático** na estratégia de primeira linha do protocolo.
(As chaves individuais 2 e "formoterol" ficam cobertas pelas rows próprias —
formoterol isolado consta como componente; ver §4.1.)

**Exclusões explícitas (🟡 honesto, com citação):** p. 36, §7.3.2 (gestantes):
*"teofilinas orais e, quando necessários… antagonistas do receptor de leucotrieno
(**os dois últimos não estão incorporados no SUS para asma**)"* — teofilina e
montelucaste não aparecem em lugar nenhum do elenco. J45×teofilina e
J45×montelucaste = 🟡 "fora do protocolo SUS", citação p. 36.

**Ponto aberto — fluticasona/salmeterol:** constam no **anexo histórico**
(p. 54–55, relatórios/portarias 2010–2021 que o protocolo consolida) e numa
menção de equivalência de dose (p. 13), **mas não no elenco vigente do §7.4.1**.
Recomendação do rascunhista: fora do elenco 2026; se você discordar (a Portaria
74/2021 consta no anexo como incorporação própria), linha própria com fonte
declarada. Decisão sua na assinatura.

## §2 Rows propostas — `data/decisao_semaforo.csv` (J45, `exaustivo=false` até assinatura)

Fonte para todas: `PCDT Asma 2026 (Port. Conjunta SAES/SCTIE 43/2026, §7.4.1, p. 37-41)`.
Versão proposta: `semaforo_j45_exaustiva_v1_2026-08`. O flip `exaustivo=true`
**não depende de código** (strip de dose já mergeado, #220) — só da sua assinatura.

## §3 Rows propostas — `data/posologia_sugerida.csv` (dupla, mesma assinatura)

Da `posologia_bruta` da máquina, aparada pelo rascunhista (a bruta é
matéria-prima — lição do RELATORIO-EXTRACAO §"linearização"); condicionantes
clínicas (faixa etária, gravidade, IgE/peso) ficam na `observacao`, como no E11:

| principio_ativo | posologia_usual (rascunho) | observacao (rascunho) |
|---|---|---|
| beclometasona | Inalatório, 1 a 2 aplicações/dia conforme apresentação; dose por faixa (baixa/média/alta) no Quadro 10. | ≥12 anos: 200–500 mcg/dia (baixa); crianças 6–11: 100–200. Título pMDI/DPI na prescrição. |
| budesonida | Inalatório, 1 a 2 aplicações/dia; dose por faixa no Quadro 10. | ≥12 anos: 200–400 mcg/dia (baixa); crianças 6–11: 100–200. |
| formoterol+budesonida | Inalatório. AIR: 1 inalação sob demanda (etapas 1–2). MART: 1–2 inalações 1–2×/dia + sob demanda (etapas 3–5). Máx. 12 inalações/dia. | Estratégia preferencial do protocolo (Quadro 11); apresentações 200/6 e 100/6 mcg. |
| salbutamol | 4 a 10 jatos (100 mcg) a cada 20 min na 1ª hora de exacerbação; depois 4–10 jatos a cada 3–4 h conforme resposta. | pMDI com espaçador; uso excessivo diário = sinal degravidade. |
| fenoterol | Mesmo esquema do salbutamol na exacerbação (alternativa). | — |
| prednisona | 40 a 50 mg/dia (ou equivalente), por 5 a 7 dias, na exacerbação grave. | Baixa dose crônica (≤7,5 mg/dia) só como último recurso em asma grave. |
| prednisolona | Adulto: 40–50 mg/dia por 5–7 dias. Crianças 6–11: 1–2 mg/kg/dia (máx. 40 mg), 3–5 dias. | Dose única diária, matinal preferida. |
| mepolizumabe | 100 mg subcutâneo a cada 4 semanas (≥12 anos); 40 mg (6–11 anos). | Asma grave; segurança <6 anos não estabelecida. |
| omalizumabe | 75–600 mg SC a cada 2–4 semanas, por IgE basal (UI/mL) e peso. | Quadros 12–13; suporte para anafilaxão nas 3 primeiras doses. |
| benralizumabe | 30 mg SC a cada 4 semanas (3 primeiras doses), depois a cada 8 semanas. | Sem ajuste em idosos/renal/hepático. |
| dupilumabe | 600 mg inicial (2×300) + 300 mg a cada 2 semanas; ou 400 mg inicial + 200 mg q2s. Crianças 6–11 por peso. | Com corticoide oral: esquema 600/300. Ver também PCDT Dermatite Atópica. |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Row da combinação** `formoterol+budesonida` — recomendo INCLUIR (amarelo-falso
   sistemático na estratégia preferencial sem ela; §1).
2. **Fluticasona/salmeterol** — recomendo fora do elenco (anexo histórico);
   discordando, row com fonte 74/2021 declarada.
3. **Momento do flip** — recomendo **sessão dupla E11+J45**: um ato de assinatura,
   dois CIDs exaustivos, dois 🟢 na vitrine (E11×dapagliflozina acende junto).
4. **Grafias** — sem problema de qualificador aqui (não há par "humana");
   teofilina/montelucaste ficam apenas nas exclusões, sem rows.

## §5 Gestão de paralelismo

Mesma do E11: nenhum arquivo servido muda até a assinatura; superfície disjunta
do engenheiro (G3/flip da abertura); o flip das CSVs é um commit de dados
curados com `validado_por=Fabiano Tonaco Borges` + bump de versão.

---

*Rascunho lavrado pelo arquiteto em 30/08/2026: extração da máquina (#224)
confrontada com o PDF (varredura de elenco e exclusões p. 36, 54–55); toda
dose citada com página. Sua revisão contra o PDF é parte do rite — a
assinatura fecha.*
