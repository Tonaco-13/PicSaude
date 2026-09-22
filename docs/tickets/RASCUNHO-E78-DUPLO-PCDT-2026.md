# RASCUNHO E78 DUPLO — semáforo + posologia, do PCDT 2019 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09 (5 rodadas, 14–18/09/2026). R1 lavrou este rascunho em 14/09 |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão, estendida a agentes; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT Dislipidemia: prevenção de eventos cardiovasculares e pancreatite — **Portaria Conjunta SAES/SCTIE nº 8, de 30/07/2019** (29 págs., `pcdt_dislipidemia.pdf`), estagiada no corpus CONITEC com sha256. Versão-livro ISBN 2020 (38 págs.) confere o elenco — ver §4.1 |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256 `pcdt_dislipidemia.pdf`: `70224304f3a7bc95fb65c36f76ade4b5de181fc216ad9dfbe58439ea3e2945cc`
sha256 ISBN 2020: `d6af3b54701603d5ea33fd57097ea11133fb5f3975fd5677612c97552b54d19d`

> Nota de frescor: o catálogo aberto MS (snapshot 08/2025) lista a condição como
> **"Em atualização"** — a portaria vigente publicada continua sendo a Conjunta nº 8/2019.
> Se uma edição nova sair, este rascunho fica obsoleto (lição E11: rascunho 2022 foi
> descartado pela edição 2026).

---

## §1 O elenco oficial 2019 — 9 itens, duplamente citados

Enumerados no **item 7.3 FÁRMACOS (p. 9)** e na **Tabela 1 – Doses Iniciais e máximas
(p. 10)**. A declaração de intenção está na p. 7: *"os representantes da classe das
estatinas com evidência inequívoca de benefício em desfechos primordiais tanto em
homens quanto em mulheres e que serão considerados por este Protocolo são:
sinvastatina, pravastatina e atorvastatina"*.

| # | Princípio ativo (chave) | Classe | Apresentações (7.3, p. 9) | Dose inicial → máxima (Tabela 1, p. 10) |
|---|---|---|---|---|
| 1 | sinvastatina | estatina | comprimidos 10, 20 e 40 mg | 20 → 80 mg/dia |
| 2 | atorvastatina | estatina | comprimidos 10, 20, 40 e 80 mg | 10 → 80 mg/dia* |
| 3 | pravastatina | estatina | comprimidos 10, 20 e 40 mg | 20 → 40 mg/dia |
| 4 | bezafibrato | fibrato | comp./drágeas 200 mg; LIB 400 mg | 200 → 400 mg/dia |
| 5 | ciprofibrato | fibrato | comprimidos 100 mg | 100 → 100 mg/dia |
| 6 | etofibrato | fibrato | cápsulas 500 mg | 500 → 500 mg/dia |
| 7 | fenofibrato | fibrato | cápsulas 200 mg; LR 250 mg | 200 → 250 mg/dia |
| 8 | genfibrozila | fibrato | comprimidos 600 e 900 mg | 600 → 1.200 mg/dia |
| 9 | ácido nicotínico | outros | comprimidos 500 mg | 500 → 3.000 mg/dia** |

\* Tabela 1: *"Restrita a casos especiais, sendo 10 mg a dose usual"* (atorvastatina 80).
\** Divergência interna — ver §4.1 (Tabela 1 diz inicial 500; a narrativa 7.4 e o livro
ISBN 2020 dizem 250).

**Posição na terapia (p. 4, critérios de inclusão):** estatinas para risco
cardiovascular moderado-alto (Framingham >10%/10 anos, DM com fatores de risco, doença
aterosclerótica evidenciada, hiperlipidemia familiar); **genfibrozila** só para
intolerantes/refratários a estatina com TG >200 e HDL <40 ou TG >500; **demais fibratos**
(fenofibrato, ciprofibrato, etofibrato, bezafibrato) sem indicação de estatina e TG >500
(prevenção de pancreatite); **ácido nicotínico** só para intolerante/contraindicado a
estatina que não preencha critérios de fibrato.

## §1a Exclusões explícitas citadas (insumo para o 🟡 honesto)

1. **Ezetimiba** — p. 9: *"este Protocolo não preconiza a ezetimiba como terapia
   hipolipemiante"*, em conformidade com a não incorporação da CONITEC
   (Portaria SCTIE/MS nº 34, de 29/08/2018). E78×ezetimiba = 🟡 "fora do protocolo SUS".
2. **Inibidores de PCSK9 (evolocumabe, alirocumabe)** — p. 9: *"Sugere-se, desta forma,
   que se aguarde maior tempo de experiência de uso desses medicamentos antes que sejam
   avaliados para incorporação no SUS"*. 🟡 com citação.
3. **Rosuvastatina** — **ausente do elenco** (não consta em 7.3 nem na Tabela 1). A p. 7
   discute a evidência dela (JUPITER, controversa; associação com DM em meta-análise,
   +18%) e NÃO a inclui. Não há frase de exclusão formal — wording proposto para o 🟡:
   "ausente do elenco do PCDT 2019" (padrão `ausente_lista_exaustiva` do I10 v2).
4. **Genfibrozila + estatina é PROIBIDA** (não é exclusão do elenco, é incompatibilidade):
   p. 4, p. 8 e 7.4 (p. 10) — *"A genfibrozila nunca deve ser administrada
   concomitantemente ao uso de estatinas"* (rabdomiólise). Fibratos em associação:
   tomar pela manhã, afastado da estatina.

**Interrupção (7.5, p. 10):** mialgias, CPK >10× valor normal, AST/ALT >3×, ou
surgimento de contraindicação → suspender. **Monitorização (§8, p. 10):** estatina
contínua sem necessidade de repetir perfil lipídico; TG semestral quando o objetivo é
prevenir pancreatite; função hepática e CPK no início, após 6 meses e a cada mudança de
dose. **Interação antirretrovirais (p. 5):** pravastatina é a estatina de escolha
(menor custo, sem CYP450).

## §2 Rows propostas — `data/decisao_semaforo.csv` (E78, hoje `exaustivo=false`)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta para todas: `PCDT Dislipidemia 2019 (Port. Conjunta SAES/SCTIE 8/2019, itens 7.3 e Tabela 1) + RENAME 2024`.
Versão proposta: `semaforo_e78_exaustiva_v1_2026-09`. `status_curadoria=validado` e
`exaustivo=true` **só após sua assinatura** (e observando a regra do momento do flip, §4.4).

| principio_ativo | Ação proposta |
|---|---|
| sinvastatina | atualizar fonte/versão (seed validada `semaforo_seed_v1_2026-06`) |
| atorvastatina | atualizar fonte/versão (seed validada) |
| **pravastatina** | **nova row** |
| **bezafibrato** | **nova row** |
| **ciprofibrato** | **nova row** |
| **etofibrato** | **nova row** |
| **fenofibrato** | **nova row** |
| **genfibrozila** | **nova row** — grafia do PCDT/DCB (ver §4.3) |
| **ácido nicotínico** | **nova row** — chave sem acento? ver §4.3 |

## §3 Rows propostas — `data/posologia_sugerida.csv` (Tabela 1 p. 10 + 7.4 p. 10)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte proposta: `PCDT Dislipidemia 2019 (Port. Conjunta 8/2019, Tabela 1 e item 7.4, p. 10)`.
Versão proposta: `posologia_e78_v1_2026-09`. Condição: `Dislipidemia` / `E78`.
Redação no padrão das rows existentes ("Tomar…"):

| principio_ativo | posologia_usual (rascunho da Tabela 1 + 7.4) | observacao (rascunho) |
|---|---|---|
| sinvastatina | Tomar 1 comprimido (10–40 mg), por via oral, 1 vez ao dia, preferencialmente à noite. Iniciar 20 mg; não exceder 80 mg/dia. | 80 mg/dia associa-se a risco aumentado de toxicidade (nota ** da Tabela 1). |
| atorvastatina | Tomar 1 comprimido (10–80 mg), por via oral, 1 vez ao dia, preferencialmente à noite. Iniciar 10 mg; não exceder 80 mg/dia. | 80 mg restrita a casos especiais; 10 mg é a dose usual (nota * da Tabela 1). |
| pravastatina | Tomar 1 comprimido (10–40 mg), por via oral, 1 vez ao dia, preferencialmente à noite. Iniciar 20 mg; máximo 40 mg/dia. | Estatina de escolha em pacientes em antirretrovirais (p. 5). |
| bezafibrato | Tomar por via oral, 200 a 400 mg/dia (comp. 200 mg ou LIB 400 mg), pela manhã, afastado das estatinas. | Fibrato; horário afastado da estatina reduz toxicidade (7.4). |
| ciprofibrato | Tomar 1 comprimido de 100 mg, por via oral, 1 vez ao dia, pela manhã. | Fibrato de dose fixa (inicial = máxima). |
| etofibrato | Tomar 1 cápsula de 500 mg, por via oral, 1 vez ao dia, pela manhã. | Fibrato de dose fixa. Ver §4.5 (presença na RENAME). |
| fenofibrato | Tomar por via oral, 200 a 250 mg/dia (cáps. 200 mg ou LR 250 mg), pela manhã. | Pode combinar com estatina quando TG >500 (p. 8). |
| genfibrozila | Tomar por via oral, 600 a 1.200 mg/dia (comp. 600 ou 900 mg), pela manhã. | **Nunca com estatinas** (rabdomiólise — p. 4, 8, 10). Indicação restrita (p. 4). |
| ácido nicotínico | Iniciar 250 mg após o jantar, aumentando a cada 2–4 semanas até 2–3 g/dia conforme tolerância; máximo 3.000 mg/dia. | Dose inicial divergente na fonte — ver §4.1. Reserva a intolerantes a estatina sem critério de fibrato (p. 4). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Ácido nicotínico — dose inicial 250 ou 500 mg?** A Tabela 1 da portaria (p. 10)
   diz inicial 500 mg; a própria narrativa do 7.4 (p. 10) manda *"inicia-se o
   tratamento com doses baixas (250 mg em dose única após o jantar)"*; o livro ISBN 2020
   (Tabela, p. 19 do livro) registra 250 e apresentações de 250/500/750 mg (a portaria
   lista só 500 mg). Recomendação do rascunhista: **250 mg** (casar com a narrativa e o
   livro) + observação registrando a divergência.
2. **Rosuvastatina** — não há frase de exclusão; confirmar o wording do 🟡 como
   "ausente do elenco do PCDT" (padrão I10 v2) em vez de "fora do protocolo SUS"
   (que exige citação de exclusão que não existe).
3. **Chaves de grafia** — `genfibrozila` (DCB/PCDT) vs `gemfibrozila` (INN
   internacional, digitação comum de prescritor); `ácido nicotínico` com/sem acento.
   Mesma lição da adjudicação da insulina (#224/E11 §4.5): grafias distintas são chaves
   distintas. Opções: rows-alias citando a mesma portaria (recomendado, +2 rows) ou
   alias no `canon_ativo` (`core`, não se justifica agora).
4. **Momento do flip** — regra do vagão mantida: `exaustivo=true` só depois do merge
   do strip de dose (TICKET-CANON-ATIVO-DOSE-SUFFIX), senão "Sinvastatina 20mg" dá
   amarelo-falso. E78 tem MUITAS apresentações por fármaco — o risco é real.
5. **Cruzamento RENAME 2024** — o elenco 7.3 pode conter itens que a RENAME atual não
   lista mais (candidatos: etofibrato, genfibrozila, ácido nicotínico). Decidir: fonte
   "PCDT 2019 + RENAME 2024" coadjuvante (padrão E11) ou verificação item a item antes
   do flip (o rascunhista pode preparar na sessão de assinatura).

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 14/09/2026, R1 do INTENSIVO PCDT, do PDF oficial
estagiado (sha256 `70224304…`). Doses transcritas da Tabela 1 (p. 10) e do item 7.4;
critérios de inclusão da p. 4; exclusões citadas das p. 7 e 9; elenco conferido também
contra o livro ISBN 2020 (p. 18–19). Sua revisão contra o PDF é parte do rito — a
assinatura fecha.*

> **SELF-CHECK (R1, 14/09/2026):** 7 citações reabertas e conferidas contra o PDF —
> Tabela 1 atorvastatina 10→80 e genfibrozila 600→1.200 (p. 10), exclusão da ezetimiba
> + Portaria 34/2018 (p. 9), proibição genfibrozila+estatina (p. 10), elenco 7.3
> pravastatina (p. 9), declaração de elenco (p. 7) — **7/7 ✅**.
