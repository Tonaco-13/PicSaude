# RELATORIO-EXTRACAO-PCDT.md — Camada 1, TICKET (fila do vagão PCDT)

Gerado por `backend/scripts/extrair_snapshot_pcdt.py`. Saída em `data/fontes-oficiais/pcdt/extracao/` — grau rascunho por construção, nunca servida, nunca commitada como verdade.

## E11 — PCDT Diabete Melito Tipo 2

- Rows extraídas: **8**
- Citação-base: PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026

| principio_ativo | posologia_bruta (início) | citação |
|---|---|---|
| metformina | 500 mg ou 850 mg 2550 mg 2 a 3 vezes Sulfonilureias | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |
| glibenclamida | 5 mg 20 mg 1 a 2 vezes | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |
| gliclazida | 30 mg ou 60 mg 120 mg 1 vez iSGLT2 | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |
| dapagliflozina | 10 mg 10 mg 1 vez | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |
| insulina NPH | Dose inicial 0,1-0,2 U/kg/diaa,b Em pessoas com obesidade e resistênci… | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 |
| insulina regular | Dose inicial de 3 U a 4 U e titular de acordo com a glicemia pós- pran… | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 |
| Insulina análoga de ação rápida | Dose inicial de 3 U a 4 U e titular de acordo com a glicemia pós- pran… | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |
| Insulina análoga de ação prolongada | Dose inicial 0,1 U- 0,2 U/kg/diaa,b. Em pessoas com obesidade e resist… | PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026, Quadro 15, p. 39 + Quadro 18, p. 47 (elenco confirmado) |

### Falhas de extração (declaradas, não escondidas)

- 'insulina regular' não bate literalmente no Quadro 15 — usada a variante 'insulina humana regular' (qualificador 'humana' presente no PDF, ausente em decisao_semaforo.csv). Achado de nomenclatura, não erro de leitura.
- 'insulina NPH' não bate literalmente no Quadro 15 — usada a variante 'insulina humana NPH' (qualificador 'humana' presente no PDF, ausente em decisao_semaforo.csv). Achado de nomenclatura, não erro de leitura.
- 'insulina NPH' achado no Quadro 15 mas NÃO confirmado no texto do Quadro 18 — conferir manualmente.
- 'insulina regular' achado no Quadro 15 mas NÃO confirmado no texto do Quadro 18 — conferir manualmente.

## J45 — PCDT da Asma

- Rows extraídas: **8**
- Citação-base: PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026

| principio_ativo | posologia_bruta (início) | citação |
|---|---|---|
| Beclometasona e budesonida | doses diárias tot ais sugeridas para corticoides inalatórios, dividida… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Prednisona e prednisolona | para adolescentes e adultos, a do se recomendada de prednisolona (ou e… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Formoterol + budesonida | para adultos e adolescentes, recomenda-se geralmente a formulação de 2… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Salbutamol ou fenoterol | em casos de exacerbações leves a moderadas, o salbutamol pode ser admi… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Mepolizumabe | em adultos e adolescentes a partir de 12 anos, a dose preconizada é de… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Omalizumabe | dose e frequência são determinadas pelo nível sérico basal de IgE (UI/… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Benralizumabe | 30 mg por injeção subcutânea a cada 4 semanas nas três primeiras doses… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |
| Dupilumabe | em pacientes adultos e adolescentes (≥12 anos) com asma grave e que es… | PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026, §7.4.1 Esquemas de administração, p. 38-41 |

### Falhas de extração (declaradas, não escondidas)

(nenhuma)

## Comparação E11 — máquina × RASCUNHO-E11-DUPLO-PCDT-2026.md §1

O AC principal desta rodada: se a máquina bate com o humano nos 8 itens do elenco, o pipeline está provado.

| Item do elenco humano (§1) | Máquina achou? | Nota |
|---|---|---|
| metformina | ✅ sim |  |
| glibenclamida | ✅ sim |  |
| gliclazida | ✅ sim |  |
| dapagliflozina | ✅ sim |  |
| insulina NPH | ✅ sim |  |
| insulina humana regular | 🟡 nomenclatura | máquina achou 'insulina regular' (mesmo termo do decisao_semaforo.csv, sem o qualificador) — candidato a RENAME pendente, não divergência de conteúdo clínico |
| insulina análoga de ação rápida | ✅ sim |  |
| insulina análoga de ação prolongada | ✅ sim |  |

**Itens extras que a máquina achou e não estão no elenco humano de 8:**
- insulina regular

**Resultado: 7/8 itens do elenco humano confirmados literalmente pela máquina; +1 por só nomenclatura (🟡, ver nota — conteúdo clínico presente, nome-chave pendente de rename no decisao_semaforo.csv).**

### Limitação conhecida — linearização de tabela no Quadro 15

O Quadro 15 é uma tabela (medicamento × dose habitual × dose máxima × frequência); `pypdf.extract_text()` lineariza célula a célula em ordem de leitura, não por linha visual. Duas consequências observadas nesta extração, NÃO corrigidas automaticamente (fariam a máquina INVENTAR um corte que o texto não delimita com segurança):

- **Rótulo de classe grudado no fim de `posologia_bruta`** do medicamento anterior (ex.: "...2 a 3 vezes Sulfonilureias" na posologia da metformina — "Sulfonilureias" pertence à PRÓXIMA classe, não à metformina).
- **Texto repetido entre `insulina regular` e `Insulina análoga de ação rápida`**: no PDF, os dois esquemas de dose prandial aparecem colados na mesma região da tabela; a fatia entre as duas âncoras saiu idêntica para as duas rows.

Curadoria humana (Camada 2) deve tratar `posologia_bruta` como matéria-prima a aparar, não como texto final.

### Nota sobre `linha` (achado desta rodada)

A extração popula `linha` com o RÓTULO DE CLASSE FARMACOLÓGICA que precede o princípio ativo no próprio Quadro 15 (ex.: "Sulfonilureias", "iSGLT2") — mecanicamente extraível do texto. O rascunho humano usa `linha` para o PAPEL TERAPÊUTICO ("1ª linha", "intensificação"), que vem de prosa nas p.21-22 do PDF, fora do escopo mecânico desta camada. **Divergência esperada e documentada, não falha de extração.**

---
*Gerado por script — reprodutível rodando de novo sobre o mesmo corpus estagiado.*