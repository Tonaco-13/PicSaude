# RASCUNHO L40 DUPLO — semáforo + posologia, do PCDT da Psoríase 2021 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Intensivo PCDT 21–25/09/2026, R1 (seg 21/09), regra (b) — prevalência APS (dermatologia que a UBS carrega; o próprio PCDT: §2/p. 4, encaminhamento ágil à Atenção Especializada quando indicado) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Psoríase — **Portaria Conjunta SAES/SCTIE nº 18, de 14/10/2021**, 78 págs., estagiado em `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/20211021_portaria_conjunta_pcdt_psoriase.pdf` — **com as alterações pós-publicação embutidas no próprio PDF** (Apêndice 2: risanquizumabe 150 mg/mL na Rename, deliberação 139ª Conitec, abr/2025; monitoramento ILTB, mai–jun/2025) |
| **Estado** | 🟡 Rascunho — aguardando caneta do Fabiano. SEM FLIP |

---

## §1 O elenco oficial — 13 substâncias, triplamente citadas

**TECI – Termo de Esclarecimento (p. 42):** *"ÁCIDO SALICÍLICO, ACITRETINA, ADALIMUMABE,
ALCATRÃO MINERAL, CALCIPOTRIOL, CICLOSPORINA, CLOBETASOL, DEXAMETASONA, ETANERCEPTE,
METOTREXATO, RISANQUIZUMABE, SECUQUINUMABE E USTEQUINUMABE"*.

**"Disponíveis" históricos (Apêndice 2, p. 47):** ácido salicílico pomada, alcatrão mineral
pomada, clobetasol creme e solução capilar, dexametasona creme, calcipotriol pomada,
acitretina, metotrexato e ciclosporina (herança da Portaria SAS/MS 1.229/2013).

**Biológicos incorporados (Apêndice 2, p. 47–48):** adalimumabe, etanercepte, secuquinumabe
e ustequinumabe (Relatório 625/2021); **risanquizumabe** incorporado pela Portaria
SCTIE/MS nº 40/2020 (Rel. 534), com a apresentação 150 mg/mL incluída na Rename em 2025.
**Exclusão explícita com relatoria: infliximabe — NÃO incorporado** (p. 47: *"A
recomendação foi pela não incorporação do infliximabe e pela incorporação do adalimumabe,
etanercepte, secuquinumabe e ustequinumabe"*, plenária Conitec 30/08/2018).

**Outras ausências do protocolo (insumo 🟡 honesto):** a associação calcipotriol +
betametasona foi pedida na enquete pública (p. 47) e **não foi incorporada** — o esteroide
do protocolo para pele fina/pregas é a **dexametasona creme** (§7.4, p. 17), e clobetasol
para placas (a associação fixa e a betametasona isolada não constam do TECI). Apremilast
e dimetilfumarato não aparecem no elenco.

**CID-10 do protocolo (§2, p. 4):** L40.0 Psoríase vulgar · L40.1 Pustulosa generalizada ·
L40.4 Gutata · L40.8 Outras formas. (Artrite psoriásica — L40.5 — **não é deste PCDT**;
tem protocolo próprio no corpus.)

## §2 Rows propostas — `data/decisao_semaforo.csv`

Fonte proposta para todas: `PCDT Psoríase (Port. Conjunta SAES/SCTIE 18/2021, TECI p. 42 + §7.4 p. 17–22)`.
Versão proposta: `semaforo_l40_v1_2026-09`. 13 rows, chave **L40**:

| # | Princípio ativo (chave) | Linha (contexto) |
|---|---|---|
| 1 | ácido salicílico | queratolítico tópico (lesões hiperceratóticas) |
| 2 | alcatrão mineral | tópico (pomada 1%) |
| 3 | calcipotriol | tópico (análogo vitamina D) |
| 4 | clobetasol | corticosteroide tópico de alta potência (placas) |
| 5 | dexametasona | corticosteroide tópico (pele fina/pregas — creme 0,1%) |
| 6 | acitretina | sistêmico — 1ª linha na pustulosa, 2ª na em placas (p. 15) |
| 7 | metotrexato | sistêmico — **1ª linha na em placas** (p. 15) ⚠️ P-9, ver §4.4 |
| 8 | ciclosporina | sistêmico — indução em curso intermitente (p. 20) |
| 9 | adalimumabe | biológico (componente especializado) |
| 10 | etanercepte | biológico (componente especializado) |
| 11 | secuquinumabe | biológico (componente especializado) |
| 12 | ustequinumabe | biológico (componente especializado) |
| 13 | risanquizumabe | biológico (componente especializado; 150 mg/mL desde 2025) |

> 🟡 honesto gerado pelo portão: L40 × infliximabe = **"não incorporado"** (com
> relatoria, p. 47); L40 × betametasona/apremilast/dimeti lfumarato = fora do protocolo.

## §3 Rows propostas — `data/posologia_sugerida.csv` (§7.4, p. 17–22)

| Princípio ativo | posologia_usual (rascunho do §7.4) |
|---|---|
| clobetasol | Creme/solução capilar 0,05%, 1–3x/dia por <30 dias; manutenção 2x/semana; máx 50 g/semana (p. 17) |
| dexametasona | Creme 0,1%, 1–3x/dia por <30 dias; mesma disciplina do clobetasol (p. 17) |
| calcipotriol | Pomada 2x/dia (manutenção 1x/dia); máx 100 g/semana (p. 17) |
| ácido salicílico | Pomada 5%, 1x/dia nas lesões hiperceratóticas (p. 17) |
| alcatrão mineral | Pomada 1%, uso diário (p. 17) |
| acitretina | 25 mg/dia inicial, aumento gradual até máx 75 mg/dia (0,5–1 mg/kg/dia); usual 25 mg dias alternados a 50 mg/dia (p. 19) |
| metotrexato | 15 mg/semana inicial (VO/SC/IM, dose única semanal ou 3 tomadas de 12/12h); range 7,5–25 mg/semana; ácido fólico 5 mg/semana 24–48h após (p. 19–20) |
| ciclosporina | 2,5 mg/kg/dia inicial, +0,5 mg/kg a cada 2–4 sem até máx 5 mg/kg/dia, 2 tomadas; cursos de até 12 sem; máx 2 anos (p. 20) |
| adalimumabe | SC: 80 mg inicial (2 injeções), depois 40 mg; escalável 40 mg/7d ou 80 mg/14d (p. 21–22) |
| etanercepte | SC 25 mg ou 50 mg, semanal (p. 22) |
| secuquinumabe | SC 300 mg (2×150 mg) sem 0,1,2,3,4 e depois a cada 4 semanas (p. 22) |
| ustequinumabe | SC 45 mg sem 0 e 4, depois a cada 12 semanas (90 mg em >100 kg) (p. 22) |
| risanquizumabe | SC 150 mg (1×150 ou 2×75) sem 0, 4 e depois a cada 12 semanas (p. 22) |

*(Fototerapia UVB/PUVA — Quadros 4–7, p. 17–19 — é procedimento, não row de receita;
psoraleno e ciclosporina injetável amarrados a procedimentos SIGTAP, p. 17.)*

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave: L40 guarda-chuva ou L40.0 puro?** O protocolo lista L40.0/.1/.4/.8 (p. 4).
   Recomendo **L40** — a cadeia do semáforo casa subcategoria na categoria e o elenco é
   o mesmo nas formas (mesmo padrão proposto para M81). L40.5 (artrite psoriásica) fica
   FORA — protocolo próprio.
2. **Biológicos no semáforo do prescritor?** São dispensados pelo componente especializado
   com solicitação e dispensação própria (a dispensação não se condiciona a exames — p. 8),
   e o PCDT os destina a moderado/grave com falha de sistêmico (fluxograma p. 49+).
   Recomendo: **manter as 13 rows** (elenco completo é a lei da exaustividade) com
   observação de canal; a 🟢/🟡 da tela não proíbe — informa. Alternativa: flipar só as
   8 não-biológicas e listar biológicos como nota.
3. **Dexametasona creme é o esteroide "de face"** — escolha incomum vs. mercado
   (betametasona). É o que o protocolo traz (p. 17); a associação calcipotriol+
   betametasona pedida na enquete NÃO entrou (p. 47). Decisão: manter fiel (dexametasona)
   — o 🟡 para betametasona é honesto e citado.
4. **⚠️ P-9 (dependência dura):** **metotrexato é compartilhado com L20** (dermatite
   atópica, ranges próximos) — o flip de L40 (e o de L20) só sai com a PR da posologia
   por `(ativo, CID)` (`DESENHO-POSOLOGIA-POR-CONDICAO.md`). As 12 rows restantes não
   colidem com nada no CSV atual.
5. **Ciclosporina/MTX injetáveis e psoraleno** — amarrados a código SIGTAP de
   procedimento (p. 17); a row é do fármaco, a apresentação injetável segue o canal
   de procedimento.

## §5 Self-check

**Executado na mesma rodada (R1, seg 21/09/2026):** 11 citações reabertas contra o PDF
(extração fresca pypdf, independente da primeira passada) — **11/11 ✅ de primeira**.
Âncoras confirmadas: CID-10 §2 (p. 4) · §7.4 completo (p. 17) · acitretina e MTX doses
(p. 19) · ciclosporina (p. 20) · secuquinumabe 2×150 (p. 21) · TECI 13 substâncias
(p. 42) · elenco disponível e **não-incorporação do infliximabe** (p. 47). **Uma
precisão de página aplicada:** a alteração pós-publicação do risanquizumabe 150 mg/mL
(Rename/2025) mora na **p. 46** (abertura do Apêndice 2), não p. 47 como o cabeçalho
poderia sugerir — citado corretamente aqui.

---

*Rascunho lavrado na R1 do intensivo 21–25/09 (seg 21/09/2026, 09:01 BRT). SEM FLIP,
SEM PR, SEM código — só docs. A caneta é do Fabiano.*
