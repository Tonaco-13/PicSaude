# RASCUNHO R52 DUPLO — semáforo + posologia, do PCDT 2024 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09. R2 lavrou este rascunho em 15/09 (regra (b): prevalência APS — seeds esgotadas no canal (a)) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Dor Crônica — **Portaria Conjunta SAES/SAPS/SECTICS nº 1, de 22/08/2024** (298 págs., `dorcronica-1.pdf`), estagiada no corpus CONITEC com sha256. Co-assinada pela **Secretaria de Atenção Primária à Saúde** — o PCDT da dor pensado para a APS |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256 `dorcronica-1.pdf`: `927f96a4969d4d62d37047d7457998db963f21e1adb0763bf951d833ed31609d`

> **Convenção de página:** página do PDF (pypdf). O corpo do protocolo tem offset pequeno
> (o texto impresso na p. 33 corresponde ao PDF p. 33 — conferido no self-check).

> **Escopo CID (p. 3):** o PCDT nomeia **R52.1 Dor crônica intratável** e
> **R52.2 Outra dor crônica**. O naproxeno tem escopo PRÓPRIO e restrito (ver §1a).

---

## §1 O elenco oficial 2024 — 16 itens, duplamente citados

Enumerados no **item 6.2.6 FÁRMACOS (p. 16–17)** e no **Quadro 2 – Esquemas
terapêuticos dos medicamentos preconizados (p. 17–19)**. A escada analgésica adaptada
da OMS está na Figura 1 (p. 16); a apresentação por tipo de dor (nociceptiva,
neuropática, nociplástica, mista, oncológica) está no 6.2 (p. 14–16).

| # | Princípio ativo (chave) | Classe / papel | Posologia essencial (Quadro 2) |
|---|---|---|---|
| 1 | paracetamol | analgésico não opioide | 1–2 comp. 500 mg 3–4×/dia; máx. 4.000 mg/dia |
| 2 | dipirona | analgésico não opioide | 1–2 comp. 500 mg até 4×/dia (ou 10–20 mL) |
| 3 | ácido acetilsalicílico | analgésico/anti-inflamatório | 1–2 comp. 500 mg, repetir 4–8h; máx. 8 comp./dia |
| 4 | ibuprofeno | AINE | 200–600 mg 3–4×/dia; máx. 3.200 mg/dia |
| 5 | naproxeno | AINE — **escopo restrito M16/M17, ver §1a** | 250 mg 1–2×/dia ou 500 mg 1×/dia; máx. 500 mg/dia |
| 6 | omeprazol | gastroproteção do AINE | 10 ou 20 mg antes do café da manhã |
| 7 | gabapentina | anticonvulsivante (dor neuropática) | 900 mg 3×/dia; máx. 3.600 mg/dia |
| 8 | carbamazepina | anticonvulsivante (trigêmeo) | 200–400 mg/dia → 200 mg 3–4×/dia; máx. 1.200 mg/dia |
| 9 | amitriptilina | ADT (nociplástica/neuropática) | 25–100 mg/dia; máx. 150 mg/dia; idosos 10–50 mg ao dormir |
| 10 | nortriptilina | ADT | 25 mg 3–4×/dia; máx. 150 mg/dia |
| 11 | clomipramina | ADT | 10–150 mg/dia |
| 12 | fenitoína | anticonvulsivante | 100 mg 3×/dia; manutenção 300–400 mg/dia; máx. 600 mg/dia |
| 13 | ácido valproico / valproato de sódio | anticonvulsivante | 250–750 mg/dia; máx. 60 mg/kg/dia |
| 14 | codeína (fosfato) | opioide fraco — **ver §4.2** | 30–60 mg 3–4×/dia; máx. 360 mg/dia |
| 15 | morfina (sulfato) | opioide forte — **ver §4.2** | 5–30 mg 4/4h (ação curta); LP 30–100 mg 12/12h |
| 16 | metadona (cloridrato) | opioide forte — **ver §4.2** | 2,5–10 mg 6/6–12h; máx. 40 mg/dia |

Linhas por tipo de dor (p. 14–16): **nociceptiva/musculoesquelética** → paracetamol,
dipirona, AINEs (+omeprazol); **neuropática** → gabapentina (pós-herpética, neuropatia
diabética, mista, hanseníase), carbamazepina (trigêmeo), ADT; **nociplástica**
(fibromialgia) → **ADT em primeiro lugar** (amitriptilina/nortriptilina); **oncológica**
→ escada OMS (não opioide → codeína → morfina/metadona; naloxona em alto risco de
sobredose; rotação de opioides com cálculo de equivalência — conversão morfina:metadona
1:5 a 1:12 só por profissionais experientes, p. 16).

## §1a Exclusões e limites explícitos citados (insumo para o 🟡 honesto)

1. **Parágrafo de não-incorporações (p. 14, com portarias):** *"não são recomendados o
   uso de medicamentos avaliados pela CONITEC e cuja decisão do Ministério da Saúde foi
   pela sua não incorporação:*
   - *diclofenaco (uso oral) para a dor crônica musculoesquelética (**Portaria SCTIE/MS nº 45, de 20/07/2021**);
   - *opioides fortes — fentanila, oxicodona e buprenorfina — para a dor crônica (**Portaria nº 46, de 20/07/2021**);
   - *opioides fracos (codeína e tramadol) e morfina em baixa dose para a dor crônica (**Portaria nº 59, de 2021** — ver §4.2);
   - *AINEs tópicos para dor musculoesquelética/OA (**Portaria nº 48, de 20/07/2021**);
   - *lidocaína para dor neuropática localizada (**Portaria nº 50, de 02/08/2021**);
   - *pregabalina para dor neuropática e fibromialgia (**Portaria nº 51, de 02/08/2021**);
   - *duloxetina para dor neuropática e fibromialgia (**Portaria nº 52, de 02/08/2021**)".
   → **🟡 com portaria**: diclofenaco oral, fentanila, oxicodona, buprenorfina, tramadol,
   AINE tópico, lidocaína, pregabalina, duloxetina.
2. **Relaxantes musculares** — p. 15: *"Não há clareza sobre o uso de relaxantes
   musculares para o tratamento da dor crônica, assim, seu uso não está recomendado
   neste PCDT"*. 🟡 ciclobenzaprina etc.
3. **Condroitina/glucosamina e infiltrações** — p. 15 (OA de joelho/quadril): *"O uso de
   sulfato de condroitina, glucosamina ou sua associação não é recomendado"*; *"injeções
   intra-articulares de corticosteroides ou ácido hialurônico não são recomendadas"*.
4. **Naproxeno com escopo PRÓPRIO (p. 3 e 14):** conforme a **Portaria SCTIE/MS nº 53,
   de 23/11/2017**, o naproxeno foi ampliado apenas para **osteoartrites de quadril e
   joelho**, CIDs **M16 (coxartrose)** e **M17 (gonartrose)** do Relatório 298/2017 —
   *"este Protocolo preconiza o uso desse medicamento apenas para estas condições"*.
   → Proposta: rows de naproxeno sob **M16/M17**, não R52 (ver §4.1).
5. **Opioides na dor nociplástica desencorajados** (p. 15) e na neuropática só com
   cautela, menor dose efetiva (p. 15) — reforça o §4.2.

## §2 Rows propostas — `data/decisao_semaforo.csv` (R52, novo CID no semáforo)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta: `PCDT Dor Crônica 2024 (Port. Conjunta SAES/SAPS/SECTICS 1/2024, item 6.2.6 e Quadro 2) + RENAME 2024`.
Versão proposta: `semaforo_r52_exaustiva_v1_2026-09`. Chave proposta: **R52.2** (ver §4.1
para R52.1/M16/M17). `exaustivo=true` **só após sua assinatura**.

| principio_ativo | Ação proposta (R52.2) |
|---|---|
| paracetamol · dipirona · ácido acetilsalicílico · ibuprofeno · omeprazol | novas rows — degrau 1 (não opioides) + gastroproteção |
| gabapentina · carbamazepina · fenitoína · ácido valproico/valproato de sódio | novas rows — adjuvantes anticonvulsivantes |
| amitriptilina · nortriptilina · clomipramina | novas rows — ADT (1ª linha na nociplástica) |
| codeína · morfina · metadona | novas rows — **com a tensão do §4.2 estampada na observação** |
| naproxeno | **rows sob M16 e M17** (escopo da Portaria 53/2017), não R52 |

## §3 Rows propostas — `data/posologia_sugerida.csv` (Quadro 2, p. 17–19)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte proposta: `PCDT Dor Crônica 2024 (Port. Conjunta 1/2024, Quadro 2 p. 17–19)`.
Versão: `posologia_r52_v1_2026-09`. Condição: `Dor crônica` / `R52.2`. Redação adulta
(pediatria/idoso citadas no Quadro 2 e propostas como observação):

| principio_ativo | posologia_usual (rascunho do Quadro 2) | observacao (rascunho) |
|---|---|---|
| paracetamol | Tomar 1 a 2 comprimidos de 500 mg, por via oral, 3 a 4 vezes ao dia. Não exceder 4.000 mg/dia. | Crianças <12a: 10–15 mg/kg 4/4–6/6h; máx. 75 mg/kg/dia. |
| dipirona | Tomar 1 a 2 comprimidos de 500 mg, por via oral, até 4 vezes ao dia (ou 10 a 20 mL da solução). | ≥15 anos. <3 meses ou <5 kg: não usar. |
| ácido acetilsalicílico | Tomar 1 a 2 comprimidos de 500 mg, por via oral, se necessário repetir a cada 4–8 h. Máximo de 8 comprimidos/dia, após as refeições. | Crianças ≥12a: até 3×/dia. |
| ibuprofeno | Tomar 200 a 600 mg, por via oral, 3 a 4 vezes ao dia. Não exceder 3.200 mg/dia. | Crianças ≥6m: 1–2 gotas/kg 3–4×/dia (máx. 160 gotas/dia). |
| naproxeno | Tomar 250 mg 1 a 2 vezes ao dia, ou 500 mg 1 vez ao dia, por via oral. Não exceder 500 mg/dia. | **M16/M17 (OA de quadril e joelho) — Portaria SCTIE 53/2017 (p. 3, 14).** Idosos: doses menores. |
| omeprazol | Tomar 10 ou 20 mg, por via oral, antes do café da manhã. | Profilaxia de úlcera/esofagite durante AINE (Quadro 2). |
| gabapentina | Tomar até 900 mg, 3 vezes ao dia (titulação conforme resposta). Máximo de 3.600 mg/dia. | Reduzir se depuração <79 mL/min; esquema de hemodiálise no Quadro 2. |
| carbamazepina | Iniciar 200 a 400 mg/dia, elevando gradualmente até 200 mg 3 a 4 vezes ao dia. Máximo 1.200 mg/dia. | Neuralgia do trigêmeo; idosos iniciar 100 mg 2×/dia. |
| amitriptilina | Tomar 25 a 100 mg/dia, preferencialmente ao dormir. Máximo 150 mg/dia. | Idosos: 10–50 mg/dia. 1ª linha na dor nociplástica (p. 15). |
| nortriptilina | Tomar 25 mg, 3 a 4 vezes ao dia. Máximo 150 mg/dia. | Idosos: 30–50 mg/dia; manter a menor dose eficaz. |
| clomipramina | Tomar 10 a 150 mg/dia. | Idosos: iniciar 10 mg/dia, ideal 30–50 mg/dia. |
| fenitoína | Tomar 100 mg, 3 vezes ao dia; manutenção usual 300–400 mg/dia. Máximo 600 mg/dia. | Ajustar por concentração sérica. |
| ácido valproico / valproato de sódio | Tomar 250 a 750 mg/dia; acima de 250 mg/dia fracionar em até 3 doses. Máximo 60 mg/kg/dia. | Idosos: iniciar mais baixo. |
| codeína (fosfato) | Tomar 30 a 60 mg, 3 a 4 vezes ao dia. Máximo 360 mg/dia. | **Ver §4.2.** Idosos: iniciar 15 mg 4/4h. |
| morfina (sulfato) | Ação curta: iniciar 5 a 30 mg a cada 4 h; LP: 30 a 100 mg a cada 12 h após dose ideal estabelecida. | **Ver §4.2.** Sem dose máxima fixa (titulação); maioria ~180 mg/dia. |
| metadona (cloridrato) | Tomar 2,5 a 10 mg a cada 6, 8 ou 12 h. Máximo 40 mg/dia. | **Ver §4.2.** Rotação morfina:metadona 1:5–1:12 só por experientes (p. 16). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave CID** — o PCDT nomeia R52.1 e R52.2 (p. 3). Proposta: rows sob **R52.2**
   ("Outra dor crônica" — o cenário APS comum); replicar sob R52.1 dobra as rows
   (16→32). Alternativa: manter só R52.2 e deixar R52.1 não-exaustivo. **O naproxeno
   foge do R52**: escopo M16/M17 pela Portaria 53/2017 (p. 3) — proposta: 2 rows
   extras (M16 e M17). Confirmar contra os CIDs que o seletor de condição do
   prescritor realmente oferece.
2. **A tensão codeína/morfina/metadona (a decisão mais fina desta levantura):** o
   elenco 6.2.6 e o Quadro 2 **incluem** os três opioides com posologia (e a seção
   oncológica p. 16 os preconiza pela escada OMS); MAS o p. 14 lista a Portaria nº
   59/2021 (não incorporação de "opioides fracos (codeína e tramadol) e morfina em
   baixa dose para o tratamento da dor crônica") entre os "não recomendados". O
   tramadol e os opioides fortes (fentanila/oxicodona/buprenorfina) estão coerentemente
   FORA do elenco — 🟡 limpo. Para codeína/morfina/metadona, opções:
   (a) rows no elenco com observação citando a tensão e o contexto oncológico
   (recomendação do rascunhista — o Quadro 2 é a letra do protocolo);
   (b) não incluir, tratando como 🟡 "não incorporados p/ dor crônica" pela Portaria 59.
   Nota técnica: o corpo do texto (p. 14) data a Portaria 59 de "20 de julho de 2021";
   a lista de referências (p. 30) diz **"7 de setembro de 2021"** — divergência interna
   do próprio PCDT, registrada aqui (o rito da adjudicação da insulina: o PDF é o juiz,
   e aqui o PDF diverge de si).
3. **Momento do flip** — regra do vagão: `exaustivo=true` só depois do merge do strip
   de dose. Atenção redobrada: ácido acetilsalicílico 500, ibuprofeno em 4
   apresentações, morfina em 5.
4. **Cruzamento RENAME 2024** — confirmar presença dos 16 na RENAME (suspeitas de
   ausência: fenitoína solução, clomipramina); o rascunhista pode preparar o
   cruzamento na sessão de assinatura.
5. **Dupla grafia valproato** — "ácido valproico" e "valproato de sódio" são itens
   separados no 6.2.6 com o MESMO esquema; proposta: uma row por grafia (2 rows) ou
   row única "valproato" — mesma lição das rows-alias da insulina (E11 §4.5).

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 15/09/2026, R2 do INTENSIVO PCDT, do PDF oficial
estagiado (sha256 `927f96a4…`). Elenco do item 6.2.6 (p. 16–17); esquemas do Quadro 2
(p. 17–19); linhas por tipo de dor (p. 14–16); não-incorporações com portarias (p. 14);
escopo CID (p. 3); eventos adversos no Quadro 3 (p. 19–21). Sua revisão contra o PDF é
parte do rito — a assinatura fecha.*

> **SELF-CHECK (R2, 15/09/2026):** 7 citações reabertas e conferidas contra o PDF —
> gabapentina no Quadro 2 (p. 18), parágrafo de não-incorporações + âncora Portaria
> 51/2021 (p. 14), elenco 6.2.6 (p. 17), escopos CID R52.1/R52.2 (p. 3), escopo
> restrito do naproxeno (p. 14) — **7/7 ✅**. Nota registrada: divergência interna do
> PCDT sobre a DATA da Portaria 59 (corpo p. 14 diz 20/07/2021; referência p. 30 diz
> 07/09/2021) — §4.2.
