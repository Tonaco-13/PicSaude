# RASCUNHO D57 DUPLO — semáforo + posologia, do PCDT da Doença Falciforme 2024 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Intensivo PCDT 21–25/09/2026, R3 (qua 23/09), regra (b) — **relevância regional**: doença falciforme é de alta prevalência no Nordeste/PE (casa UFPE/PJ324); seguimento crônico compartilhado com a APS (proto-gramas de triagem neonatal, profilaxia antimicrobiana e ácido fólico) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Doença Falciforme — **Portaria Conjunta SAES/SECTICS nº 16, de 01/11/2024** (Rel. CONITEC 924/2024; 89 págs.), estagiado em `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/pcdt-da-doenca-falciforme.pdf` (+ resumido no corpus) |
| **Estado** | 🟡 Rascunho — aguardando caneta do Fabiano. SEM FLIP |

---

## §1 O elenco oficial — TECI com 6, §7.3.7 com 11 (divergência registrada)

**TECI – Termo de Esclarecimento (p. 40):** *"ÁCIDO FÓLICO, ALFAEPOETINA,
BENZILPENICILINA BENZATINA (PENICILINA G), ERITROMICINA, FENOXIMETILPENICILINA
(PENICILINA V) E HIDROXIUREIA"*.

**§7.3.7 Medicamentos (p. 17–18)** lista 11: as 6 do TECI **mais** amoxicilina,
amoxicilina+clavulanato, azitromicina, cefalexina e ceftriaxona — estas últimas
para **antibioticoterapia das infecções intercorrentes** (Quadro 4, p. 19–20), não
para o tratamento da doença falciforme. **Divergência registrada como fato**
(mesma família da lista×código do EVENTOS_ENCAMINHAMENTO): o TECI cobre os
crônicos/específicos; as 5 antimicrobianas são arsenal de intercorrência. Ver §4.2.

**CID-10 do protocolo (§2, p. 3):** `D57.0` com crise · `D57.1` sem crise ·
`D57.2` transtornos heterozigóticos duplos — **CID triplo** (§4.1).

**Notas com âncora:**
- **Hidroxiureia é citotóxica manipulável**: cápsulas 500 mg dissolvidas em água
  (≥25 kg) ou comprimido revestido 100 mg fracionável (<25 kg); manipulação em
  farmácia com boas práticas (p. 18).
- **Analgésicos das crises de dor seguem o PCDT da Dor Crônica** (p. 20 — o nosso
  R52 já lavrado; nota de ponte, sem rows aqui).
- Gravidez: **ácido fólico 5 mg/dia** (dose maior — p. 21); HU suspensa 3 meses
  antes da concepção (p. 21); AINEs restritos 18–30 semanas (p. 21).

## §2 Rows propostas — `data/decisao_semaforo.csv`

Fonte proposta: `PCDT Doença Falciforme 2024 (Port. Conjunta SAES/SECTICS 16/2024, TECI p. 40 + §7.3.7/7.3.8 p. 17–19)`.
Versão proposta: `semaforo_d57_v1_2026-09`. **6 rows (o TECI), chave D57 (proposta — §4.1):**

| # | Princípio ativo (chave) | Papel |
|---|---|---|
| 1 | hidroxiureia | terapia-modificadora base (15→35 mg/kg/dia) |
| 2 | ácido fólico | suplementação 1 mg/dia (demanda hemolítica) |
| 3 | fenoximetilpenicilina | profilaxia pneumocócica <5 anos (penicilina V oral) |
| 4 | benzilpenicilina benzatina | profilaxia IM alternativa à V oral (por peso, 4/4 semanas) |
| 5 | estolato de eritromicina | profilaxia na alergia à penicilina |
| 6 | alfaepoetina | anemia crônica selecionada (12.000 UI/semana SC/IV) |

> 🟡 honesto pelo portão: D57 × as 5 antimicrobianas de intercorrência e ×
> analgésicos = ver §4.2 (decisão de escopo) — a citação da divergência vai na row.

## §3 Rows propostas — `data/posologia_sugerida.csv` (§7.3.8 + Quadro 3, p. 18–19)

| Princípio ativo | posologia_usual (rascunho) |
|---|---|
| hidroxiureia | 15 mg/kg/dia VO dose única inicial; +5 mg/kg/dia a cada 4 semanas até máx 35 mg/kg/dia ou toxicidade; tempo indeterminado com resposta (p. 18) |
| ácido fólico | 1 mg/dia (recomendação internacional do protocolo); gravidez 5 mg/dia; <1 ano/<10 kg sem dose sérica: 2,5 mg 3×/semana (p. 19, p. 21) |
| fenoximetilpenicilina | Profilaxia do diagnóstico aos 5 anos; 15–25 kg: 250 mg (400.000 UI) 12/12h (Quadro 3, p. 19) |
| benzilpenicilina benzatina | IM 4/4 semanas por peso: ≤10 kg 300.000 UI · 10–20 kg 600.000 UI · >20 kg 1.200.000 UI (Quadro 3, p. 19) |
| estolato de eritromicina | Alergia à penicilina: 20 mg/kg 2×/dia (40 mg/kg/dia) (Quadro 3, p. 19) |
| alfaepoetina | 12.000 UI/semana divididas em 3 aplicações de 4.000 UI, SC ou IV (p. 18) |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave D57 guarda-chuva.** O protocolo declara D57.0/.1/.2 (p. 3). Recomendo
   **D57** (mesma lógica de L40/M81): a cadeia do semáforo casa a subcategoria na
   categoria e o elenco é o mesmo nas formas.
2. **As 5 antimicrobianas de intercorrência** (amoxicilina, amox+clav, azitromicina,
   cefalexina, ceftriaxona — §7.3.7/Quadro 4): **recomendo NÃO virar rows** — tratam
   a INFECÇÃO intercorrente, não a doença falciforme; virar rows faria o semáforo
   acender 🟢 para "D57×azitromicina" num contexto de protocolo de infecção.
   Alternativa: rows com observação de canal (precedente biológicos L40). Caneta
   decide; a divergência TECI×§7.3.7 está registrada como fato.
3. **P-9 (nota)**: ceftriaxona e azitromicina colidirão com o rascunho de IST
   (A54/A56/A57) e benzilpenicilina benzatina com a sífilis (A51/A52) — a chave
   composta `(ativo, CID)` (mergeada no #269) resolve por construção; as doses
   divergem por condição (ex.: benzatina ≤10 kg 300.000 UI no D57 × 2,4 MI no A51)
   — **o pôster perfeito do porquê da chave**.
4. **Hidroxiureia na APS**: início/titulação é hematologia; a row informa o
   contexto (o semáforo informa, não proíbe — mesma régua dos biológicos).

## §5 Self-check

**Executado na mesma rodada (R3, qua 23/09/2026):** 11 citações reabertas contra o
PDF (extração fresca pypdf) — **11/11 ✅ de primeira**. Âncoras: portaria (p. 1) ·
CID triplo D57.0/.1/.2 (p. 3) · HU apresentações e dose (p. 18) · epoetina 12.000
UI (p. 18) · Quadro 3 benzatina por peso e eritromicina (p. 19) · ácido fólico
1 mg/dia (p. 19) e 5 mg/dia na gravidez (p. 21) · TECI 6 substâncias (p. 40).

---

*Rascunho lavrado na R3 do intensivo 21–25/09 (qua 23/09/2026, 09:01 BRT). SEM FLIP,
SEM PR, SEM código — só docs. A caneta é do Fabiano.*
