# RASCUNHO I50 DUPLO — semáforo da Insuficiência Cardíaca, do PCDT 2024 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Agenda de fim de semana R4 (05-06/09), autorizada 04/09 · vagão: expansão por escolha |
| **Rascunhista** | Arquiteto (Z) — nunca flipa `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Fonte canônica** | **PCDT da IC (FEr) — Portaria Conjunta SAES/SECTICS nº 10, de 13/09/2024**, 39 págs., no corpus (`pcdt-de-insuficiencia-cardiaca.pdf`) |
| **Critério** | Padrão estrito (sinal verde I10 v2): 🟢 = reconhecido e disponível no SUS. PCDT ∩ RENAME 2024 |
| **Estado** | ✅ **EXECUTADO 13/09** — autorização verbal do Fabiano |

## §1 Elenco proposto (13 chaves)

| Chave | PCDT (págs.) | RENAME 2024 (págs.) |
|---|---|---|
| **sacubitril + valsartana** | 2, 4, 8, 11, 13 (critérios p. 8: <75 anos, NYHA II, FE ≤35%, NT-proBNP >600) | 46, 212 (a combinação consta) |
| enalapril | 12, 15-16, 24-25 | 45, 140 |
| captopril | 12, 15-16, 24-25 | 42, 128 |
| losartana | 12, 15-16, 24-25 | 45, 140 |
| espironolactona | 8, 13-16 | 44, 135 |
| furosemida | 13, 15-16, 24-25 | 44, 137 |
| hidroclorotiazida | 13, 15-16, 24-25 | 45, 138 |
| carvedilol | 12, 15-16, 24-25 | 42, 128 |
| metoprolol | 12, 15-16, 24-25 | 46, 144 |
| digoxina | 15-16, 24-25, 32 | 43, 134 |
| hidralazina | 14-16, 24-25 | 43, 131 |
| isossorbida (nitrato) | 14-16, 24-25 | 44-45 |
| **dapagliflozina** | 2, 8, 11, 13-14 | 29, 187 |

Nota de época: o PCDT é de **set/2024**; se a CONITEC publicar atualização (a
família 2026 já mexeu em DM2 e asma), a fonte canônica muda antes da assinatura.
Dapagliflozina na IC é a interseção elegante com o E11: mesma moléculula, duas
indicações, dois protocolos.

## §2 Fora do elenco (com razão)

- **bisoprolol**: citado no PCDT (p. 12), **AUSENTE da RENAME 2024** → 🟡 por
  disponibilidade (redireciona a carvedilol/metoprolol, ambos renomeados).
- **ivabradina**: citada (p. 10, 22, 37), **AUSENTE da RENAME 2024** → idem.
- Ambos são ponto de decisão no modelo fosfomicina se preferir mantê-los 🟢 com
  ausência declarada; recomendo o estrito puro (🟡).

## §3 Posologia

Pendente de levantura na assinatura (doses nas p. 13-16 do PDF estagiado).
Não se inventa row.

## §4 Pontos de decisão (só o Fabiano)

1. **Bisoprolol e ivabradina** (recomendados no PCDT, ausentes da RENAME):
   recomendo 🟡 com causa. Alternativa: 🟢 com ausência declarada.
2. Versão na assinatura: `semaforo_i50_exaustiva_v1_2026-09`.

## §5 Sequenciamento

Sessão dupla com J44. Com I10 v2 mergeada e estas duas assinadas, o núcleo
cardiorrespiratório crônico da APS fica completo no semáforo: I10 · E11 · J45 ·
J44 · I50 · F32 · N39.0 — sete condições, todas estritas, todas com fonte
estagiada e página.

---

*Lavrado na R4 da agenda (dom 06/09), extração mecânica das duas fontes e
cruzamento PCDT×RENAME. Self-check de citações na R5.*

---

## ✅ EXECUTADO — 13/09/2026

Autorização verbal do Fabiano, verbatim: **"Merge e canetas autorizados"**
(13/09/2026). Mesmo precedente do sinal verde I10 estrito (#256): a palavra do
Fabiano é a assinatura.

Rows gravadas em `data/decisao_semaforo.csv` (`validado`, `exaustivo=true`,
`validado_por = Fabiano Tonaco Borges`) e posologia em
`data/posologia_sugerida.csv`, transcrita do PDF estagiado com página.
Guarda: `backend/tests/unit/test_semaforo_flip_j44_i50.py`.

**Pontos de decisão do §4 resolvidos pela recomendação do próprio rascunho**
(o despacho mandou executar dos rascunhos auto-checkados): o estrito puro —
ausente da RENAME 2024 fica 🟡 com causa, não 🟢 com ausência declarada.

**Limite encontrado na execução:** `carregar_posologias` indexa por princípio
ativo, não por (ativo, CID). As rows de posologia de fármacos compartilhados
com outro protocolo foram RETIRADAS para não sobrescrever em silêncio a dose
do protocolo vizinho. Detalhe e guarda no teste acima.

---

## ✅ EXILADAS DE VOLTA — ENG-019, 21/09/2026

O limite registrado acima está fechado. `carregar_posologias` passou a chavear
por **`(ativo, CID)`** (`DESPACHO-ENG-019-POSOLOGIA-POR-CONDICAO.md`), e as rows
de posologia retiradas nesta caneta por colidirem com outro protocolo voltaram
ao `data/posologia_sugerida.csv` sob a chave certa — transcritas do mesmo PDF
estagiado, com página.

A guarda `test_posologia_nao_tem_dois_cids_para_o_mesmo_ativo`, que proibia
colisão, **foi invertida** em
`test_posologia_com_dois_cids_para_o_mesmo_ativo_agora_convive`: colidir passou
a ser legítimo, e o que se exige agora é que a colisão RESOLVA — cada par vivo,
cada um com a sua dose.

As cinco de I50 (losartana, enalapril, captopril, hidroclorotiazida,
dapagliflozina) vieram do **Quadro 5, p. 16** do PCDT IC 2024 — o mesmo quadro
das oito que já estavam no CSV.
