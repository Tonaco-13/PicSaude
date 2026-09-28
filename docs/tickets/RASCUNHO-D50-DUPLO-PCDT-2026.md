# RASCUNHO D50 DUPLO — semáforo + posologia, do PCDT de Anemia por Deficiência de Ferro 2014 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Intensivo PCDT 21–25/09/2026, R3 (qua 23/09), regra (b) — **a nova draftável de maior volume APS** (crianças 6–59 meses, gestantes, mulheres em idade reprodutiva); primeira condição lavrada sobre o **adendo pós-batch** (P-10, estagiado 22/09) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT Anemia por Deficiência de Ferro — **Portaria SAS/MS nº 1.247, de 10/11/2014** (20 págs.; **formato antigo** — pré-CONITEC padrão atual), estagiado em `data/fontes-oficiais/pcdt/adendos-pos-batch/pcdt_anemia_deficienciaferro_2014.pdf`, sha256 `94ead687…` no MANIFEST |
| **Estado** | 🟡 Rascunho — aguardando caneta do Fabiano. SEM FLIP |

---

## §1 O elenco oficial — 2 substâncias, citadas

**§8.3 FÁRMACOS (p. 10):**

| Via | Fármaco | Apresentações citadas |
|---|---|---|
| Oral | **sulfato ferroso** | 40 mg de ferro elementar/comprimido · 25 mg/mL solução · 5 mg/mL xarope |
| IV | **sacarato de hidróxido férrico** | 100 mg frasco-ampola 5 mL |

**TECI/Guia de orientação (p. 18):** *"sulFAto Ferroso pArA AnemiA por
deFiciênciA de Ferro"* — o guia do paciente cobre o sulfato ferroso.

**Notas com âncora:**
- **Ácido fólico NÃO é fármaco do PCDT** — aparece como coadjuvante obrigatório da
  gestante no esquema (*"60 a 200 mg/dia de ferro elementar associadas a 400 mcg/dia
  de ácido fólico"*, p. 10) e no texto (p. 8). Ver §4.2.
- **Ferro IV é hospitalar**: *"A dose deve ser administrada em hospital, em infusão
  IV lenta"* (p. 10) — o mesmo desenho de canal dos biológicos do L40.
- **DRC tem protocolo próprio**: *"Para o tratamento da ADF na doença renal crônica,
  ver o PCDT específico"* (p. 10) — o `pcdt_anemia_doencarenalcronica.pdf` do corpus.
- Tratamento por **6 meses após a Hb normalizar** (repor reservas — p. 10, §8.5).

## §2 Rows propostas — `data/decisao_semaforo.csv`

Fonte proposta: `PCDT Anemia Ferropriva 2014 (Port. SAS/MS 1247/2014, §8.3 p. 10)`.
Versão proposta: `semaforo_d50_v1_2026-09`. **2 rows, chave D50 (proposta — §4.1):**

| # | Princípio ativo (chave) | Observação |
|---|---|---|
| 1 | sulfato ferroso | 1ª linha oral; 3 apresentações (p. 10) |
| 2 | sacarato de hidróxido férrico | IV hospitalar — intolerância oral/urgência (p. 10) |

> 🟡 honesto pelo portão: D50 × qualquer outro ferro (fumarato, gluconato,
> hidróxido férrico polimaltosado) = fora do §8.3, com esta citação.

## §3 Rows propostas — `data/posologia_sugerida.csv` (§8.4, p. 10)

| Princípio ativo | posologia_usual (rascunho do §8.4) |
|---|---|
| sulfato ferroso | Crianças: 3–6 mg/kg/dia de ferro elementar (máx 60 mg/dia) · Gestantes: 60–200 mg/dia + 400 mcg/dia de ácido fólico · Adultos: 120 mg/dia · Idosos: 15 mg/dia · tratar por 6 meses após Hb normalizar (p. 10) |
| sacarato de hidróxido férrico | Fórmula: Ferro (mg) = (Hb desejada − Hb atual) × peso × 2,4 + 500; IV lenta 30 min em hospital, 1–3×/semana (≥48h de intervalo), máx 300 mg/dose (p. 10) |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave D50 sem declaração do PCDT.** O formato antigo (2014) **não traz seção
   CID-10** (a seção do falciforme 2024, por exemplo, traz). Proposta: **D50**
   (anemia ferropriva, o código da condição-título) — com esta nota lavrada; se o
   seletor do prescritor oferecer D50.0/D50.9, a cadeia do semáforo casa na
   categoria.
2. **Ácido fólico da gestante** (400 mcg/dia, coadjuvante citado no esquema): row
   própria em D50 ou observação da row do sulfato ferroso? **Recomendo observação**
   — o §8.3 não o lista como fármaco do protocolo; row nova seria interpretação
   além da fonte.
3. **Sacarato IV como row**: canal hospitalar (como os biológicos do L40 — que
   entraram com observação de canal). Recomendo entrar; a 🟢/🟡 informa, não proíbe.
4. **Frescor**: edição 2014 é a VIGENTE (catálogo aberto 08/2025: "Aprovado*", sem
   "Em atualização"; foi o que a página oficial serviu ao courier em 22/09). Se uma
   edição nova publicar, re-sondagem antes da caneta.

## §5 Self-check

**Executado na mesma rodada (R3, qua 23/09/2026):** 9 citações reabertas contra o PDF
(extração fresca pypdf) — **9/9 ✅ de primeira**. Âncoras: portaria (p. 1) · §8.3
completo incluindo as 3 apresentações orais + IV (p. 10) · esquemas por população
(crianças/gestantes/adultos/idosos — p. 10, idosos também p. 15) · fórmula IV
hospitalar (p. 10) · 6 meses pós-Hb (p. 10) · remissão à DRC (p. 10).

---

*Rascunho lavrado na R3 do intensivo 21–25/09 (qua 23/09/2026, 09:01 BRT). SEM FLIP,
SEM PR, SEM código — só docs. A caneta é do Fabiano.*
