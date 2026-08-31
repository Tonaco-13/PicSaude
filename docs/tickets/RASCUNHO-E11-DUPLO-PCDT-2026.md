# RASCUNHO E11 DUPLO — semáforo + posologia, do PCDT 2026 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Martelo do Fabiano 28/08: *"PCDT + RENAME 100%!!!! Pode ir"* (sem alunos — vagão §8.1) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão, estendida a agentes) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT Diabete Melito Tipo 2 — **Portaria SCTIE/MS nº 13, de 21/02/2026**, 80 págs., estagiado com sha256 (`data/fontes-oficiais/pcdt/`, ver `MANIFEST.md`) |
| **Estado** | ✅ **ASSINADO — Fabiano, 31/08/2026** ("E11 e J45 assinado"). Executado na **PR #233** (canal curadoria, arquiteto): elenco 15 rows (8 do Quadro + aliases aterradas no PDF: humana NPH, regular, AIAR asparte/lispro/glulisina, AIAP glargina/degludeca; **detemir fora** — anexo histórico, processo encerrado); rascunhos 2022 (21 rows) retirados; posologia 8 rows. Guarda: `test_semaforo_flip_e11_j45.py` |

---

## §1 O elenco oficial 2026 — 8 itens, triplamente citados

Enumerados no **Quadro 15** (esquemas, p. 39), no **Quadro 18 Recomendação 1** (cobertura,
p. 47) e no **Termo de Esclarecimento** (p. 62):

| # | Princípio ativo (chave) | Classe | Linha (contexto, p. 21-22/47) |
|---|---|---|---|
| 1 | metformina | biguanida | 1ª linha (monoterapia inicial) |
| 2 | glibenclamida | sulfonilureia | intensificação |
| 3 | gliclazida | sulfonilureia | intensificação |
| 4 | dapagliflozina | iSGLT2 | benefício cardio-renal |
| 5 | insulina NPH | insulina basal | intensificação |
| 6 | insulina humana regular | insulina | prandial |
| 7 | insulina análoga de ação rápida | insulina (AIAR) | prandial |
| 8 | insulina análoga de ação prolongada | insulina (AIAP) | basal |

**Exclusões explícitas (p. 22)** — insumo para o 🟡 honesto: *"acarbose, inibidores da
DPP-4, agonistas do GLP-1, meglitinidas e tiazolidinedionas **não estão incorporados ao
SUS**"*. E11×sitagliptina etc. = 🟡 "fora do protocolo SUS", com citação.

> **⚠️ Achado que pede sua decisão — GLIMEPIRIDA:** existe row rascunho antiga
> (`rascunho_e11_dm2_v1_2026-06`) citando o PCDT **2022**, com glimepirida. O elenco
> **2026 não a traz** (sulfonilureias = glibenclamida + gliclazida somente).
> Recomendação do rascunhista: **descartar** a row antiga (a edição vigente a removeu);
> se você discordar, manter com fonte 2022 declarada e nota.

## §2 Rows propostas — `data/decisao_semaforo.csv` (E11, ainda `exaustivo=false`)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`
Fonte proposta para todas: `PCDT DM2 2026 (Port. SCTIE/MS 13/2026, Quadros 15/18) + RENAME 2024`.
Versão proposta: `semaforo_e11_exaustiva_v1_2026-08`. As 5 seeds validadas
(metformina, glibenclamida, gliclazida, insulina NPH, dapagliflozina — fonte
`RENAME/PCDT (APS)`) **atualizam a fonte** para a citação 2026; as 3 insulinas novas
entram. `status_curadoria=validado` e `exaustivo=true` **só após sua assinatura e o
merge do strip de dose** (dependência do vagão §3).

| principio_ativo | Ação proposta |
|---|---|
| metformina | atualizar fonte/versão (seed validada) |
| glibenclamida | atualizar fonte/versão (seed validada) |
| gliclazida | atualizar fonte/versão (seed validada) |
| insulina NPH | atualizar fonte/versão (seed validada) |
| dapagliflozina | atualizar fonte/versão (seed validada) |
| **insulina humana regular** | **nova row** |
| **insulina análoga de ação rápida** | **nova row** — ver §4.1 (chave vs. aliases) |
| **insulina análoga de ação prolongada** | **nova row** — ver §4.1 |
| ~~glimepirida~~ | **descartar rascunho 2022** (ver §1) |

## §3 Rows propostas — `data/posologia_sugerida.csv` (do Quadro 15, p. 39)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte proposta para todas: `PCDT DM2 2026 (Port. SCTIE/MS 13/2026, Quadro 15, p. 39)`.
Versão proposta: `posologia_dm2_v1_2026-08`. Condição: `Diabete melito tipo 2` / `E11`.

| principio_ativo | posologia_usual (rascunho do Quadro 15) | observacao (rascunho) |
|---|---|---|
| metformina | Tomar 1 comprimido de 500 mg ou 850 mg, por via oral, 2 a 3 vezes ao dia, junto às refeições. Não exceder 2.550 mg/dia. | 1ª linha. XR 500 mg disponível via Farmácia Popular (p. 38). Atualiza row existente. |
| glibenclamida | Tomar 1 comprimido de 5 mg, por via oral, 1 a 2 vezes ao dia. Não exceder 20 mg/dia. | Não recomendada ≥60 anos; contraindicada se TFG<30 (p. 40). Atualiza row existente. |
| gliclazida | Tomar 1 comprimido de 30 mg ou 60 mg, por via oral, 1 vez ao dia. Não exceder 120 mg/dia. | Sulfonilureia; mesmas contraindicações de classe (p. 40). |
| dapagliflozina | Tomar 1 comprimido de 10 mg, por via oral, 1 vez ao dia. | Contraindicada se TFG estimada <25 mL/min persistente; gravidez/lactação (p. 40). |
| insulina NPH | Iniciar 0,1 a 0,2 U/kg/dia por via subcutânea (obesidade/resistência: 0,5–0,75), à noite antes da ceia; titular 2 U a cada 3 dias pela glicemia de jejum. | Máx. 0,5 U/kg/dia (0,75 se obesidade/RI). Notas a/b/c do Quadro 15. |
| insulina humana regular | Iniciar 3 a 4 U por via subcutânea antes das refeições principais, titulando pela glicemia pós-prandial. | Não exceder >50% da dose total diária de insulina. |
| insulina análoga de ação rápida | Iniciar 3 a 4 U por via subcutânea antes das refeições principais, titulando pela glicemia pós-prandial. | Mesmo esquema da regular (Quadro 15); ver §4.1 para aliases. |
| insulina análoga de ação prolongada | Iniciar 0,1 a 0,2 U/kg/dia por via subcutânea, 1 vez ao dia; titular 2 U a cada 3 dias pela glicemia de jejum. | Máx. 0,5 U/kg/dia (0,75 se obesidade/RI). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **AIAR/AIAP — chave de classe ou enumeração de análogos?** O PCDT elenca por
   **classe** ("análoga de ação rápida/prolongada"); prescrições nomeiam o análogo
   (aspart, lispro, glargina, degludeca). Opções: (a) rows de classe + rows alias por
   análogo citando a mesma portaria; (b) só classe (prescrições de análogo específico
   casariam só com strip/alias no `canon_ativo` — escopo novo). Rascunhista sugere (a).
2. **Glimepirida** — descartar (recomendado) ou manter com fonte 2022 (§1).
3. **Momento do flip** — regra do vagão: `exaustivo=true` só depois do merge do strip
   de dose (TICKET-CANON-ATIVO-DOSE-SUFFIX), senão "Metformina 500mg" dá amarelo-falso.
4. **RENAME 2024** — a citação entra como fonte coadjuvante (componente/apresentação);
   se quiser o cruzamento item-a-item (nº RENAME por fármaco), é um adendo que o
   rascunhista pode preparar na mesma sessão de assinatura.
5. **ADJUDICAÇÃO da divergência máquina×humano (arquiteto, 30/08, na auditoria
   da #224):** o PDF diz literalmente **"Insulina Humana Regular"** (p. 37 e
   Quadro 15 na p. 39) — o termo do rascunho humano está certo, e a extração
   mecânica (#224) derivou "insulina regular" pela mesma regra de variante que
   harmonizou "Insulina humana NPH" → "insulina NPH". Como `canon_ativo` NÃO
   normaliza o qualificador "humana", grafias distintas são chaves distintas —
   **recomendação: assinar com AMBAS as grafias como rows-alias** citando a
   mesma portaria (insulina humana regular + insulina regular; e o par simétrico
   para NPH: insulina NPH + insulina humana NPH), prevenindo amarelo-falso em
   qualquer digitação do prescritor. Custo: +2 rows honestas; alternativa
   (alias no `canon_ativo`) seria `core` e não se justifica agora.

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro (typeahead/CBO, scripts, telas). Até lá, **nenhum arquivo servido
muda**: este rascunho é documento de revisão. `FILA-VIVA.md` só é tocado no fecho
(item ✔). A vigília do fim de semana não é afetada (não há PR; é curadoria).

---

*Rascunho lavrado pelo arquiteto em 28/08/2026, do PDF oficial estagiado (sha256
`f90b7829…`). Toda dose transcrita do Quadro 15 (p. 39); contraindicações da p. 40;
linhas de tratamento das p. 21-22 e Quadro 18 (p. 47). Sua revisão contra o PDF é parte
do rito — a assinatura fecha.*
