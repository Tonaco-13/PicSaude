# RASCUNHO F32 DUPLO — semáforo da Depressão, padrão I10 (diretrizes + RENAME 2024)

| Campo | Valor |
|---|---|
| **Origem** | Vagão §2 (fila: E11 ✔ → J45 ✔ → **F32** → N39.0) · "Vai", Fabiano 02/09 |
| **Rascunhista** | Arquiteto (Z) — nunca flipa `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Fontes estagiadas (sha256 no MANIFEST)** | **RENAME 2024** (`fontes-oficiais/rename/rename-2024.pdf`, 254p) · **AMB/ABP Depressão 2009 integral** (`diretrizes/amb-abp-depressao-2009.pdf`, 11p, SciELO) · **Guia Fiocruz APS 2022** (`diretrizes/fiocruz-depressao-aps.pdf`, 40p) |
| **Estado** | ✅ **ASSINADO — Fabiano, 02/09/2026** ("Estou de acordo … com suas recomendações"): elenco ESTRITO RENAME 2024. Executado na **PR #249** (5 rows 🟢, sertralina/escitalopram 🟡 com causa; bupropiona confirmada N06AX12/p.95, componente Estratégico — p.147 era índice). Posologia F32 segue PENDENTE (fonte de dose a estagiar). Guarda: `test_semaforo_flip_f32_n39.py` |

---

## §1 O achado principal: as sementes citam RENAME que não as contém

Varredura do RENAME 2024 inteiro (254p): **sertralina e escitalopram NÃO CONSTAM
— nenhuma página**. As seeds 93-94 trazem `fonte=RENAME/PCDT (APS)` — **citação
falsa**, herdada da semeadura de junho. Elenco antidepressivo REAL da RENAME 2024:

| Princípio ativo | RENAME 2024 (págs.) |
|---|---|
| fluoxetina | 95, 131 |
| clomipramina | 95, 130 |
| amitriptilina | 94, 130 |
| nortriptilina | 97, 132 |
| bupropiona | 95, 147 ⚠️ (checar seção da p.147 — pode ser indicação distinta) |

Diretrizes: AMB/ABP 2009 nomeia fluoxetina (p.4), venlafaxina (p.5,7), mirtazapina
(p.7) — discute classes, não elenco fechado. Fiocruz APS 2022: **ISRs como
primeira linha** (p.5, 29); nomes de fármaco não extraíveis mecanicamente
(tabelas) — declarado.

## §2 Ponto de decisão ÚNICO (só o Fabiano decide)

**(a) Elenco estrito RENAME 2024 — RECOMENDADO:** 🟢 = fluoxetina, clomipramina,
amitriptilina, nortriptilina (+bupropiona, se a p.147 confirmar depressão).
**Sertralina e escitalopram migram para 🟡 com causa e citação** ("não constam
da RENAME 2024 — disponibilidade fora do componente básico") — o mesmo modelo do
E11 ("não incorporado ao SUS" = 🟡 honesto). O 🟢 significa *tratamento
reconhecido E disponível no SUS*; quebrar isso quebra a semântica do semáforo.

**(b) Elenco RENAME ∪ diretrizes** (mantém sertralina/escitalopram 🟢 citando
diretriz): NÃO recomendado — `fonte` voltaria a prometer o que a RENAME não dá,
o defeito que este rascunho acaba de expor.

Em qualquer cenário: **as 4 seeds trocam `fonte`** (a atual é falsa) e a versão
vira `semaforo_f32_exaustiva_v1_2026-09` na assinatura.

## §3 Posologia — pendência declarada

RENAME não traz posologia; AMB/ABP 2009 discute estratégia, não dose-padrão.
**Rows de posologia F32 ficam PENDENTES de levantura por fármaco** (bula ANVISA
ou guia com doses) — não se inventa dose para acompanhar o flip. O flip do
semáforo NÃO depende da posologia (o vagão §8 pediu brief duplo "a partir do
E11", mas a honestidade manda: sem fonte de dose, sem row).

## §4 Sequenciamento

Rascunho N39.0 lavrado junto (mesma sessão). Assinatura sugerida: sessão dupla
F32+N39.0, após decisão do §2 (F32) e §2 do N39.0.

---

*Lavrado em 02/09/2026 com varredura mecânica das três fontes estagiadas;
divergências verificadas por ausência no texto integral, não por memória.*
