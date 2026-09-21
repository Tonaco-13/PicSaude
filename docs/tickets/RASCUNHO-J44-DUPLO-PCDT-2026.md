# RASCUNHO J44 DUPLO — semáforo da DPOC, do PCDT 2025 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Agenda de fim de semana R4 (05-06/09), autorizada 04/09 · vagão: expansão por escolha |
| **Rascunhista** | Arquiteto (Z) — nunca flipa `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Fonte canônica** | **PCDT da DPOC — Portaria Conjunta SAES/SCTIE nº 29, de 27/11/2025**, 68 págs., no corpus (`pcdt-da-doenca-pulmonar-obstrutiva-cronica.pdf`) |
| **Critério** | Padrão estrito da casa (sinal verde I10 v2, 04/09): 🟢 = reconhecido **e** disponível no SUS. Elenco = PCDT ∩ RENAME 2024 (estagiada, sha256 no MANIFEST) |
| **Estado** | ✅ **EXECUTADO 13/09** — autorização verbal do Fabiano |

## §1 Elenco proposto (7 chaves + 1 combinação)

| Chave | PCDT (págs.) | RENAME 2024 (págs.) |
|---|---|---|
| salbutamol | 15, 19-20, 23 | 111, 144 |
| ipratrópio | 15-16, 18-20 | 107, 127 |
| tiotrópio | 8-10, 16, 18 | 107, 173 |
| formoterol | 8, 15, 17-19 | 110, 192 |
| budesonida | 17, 19, 21-22 | 107-108 |
| **formoterol + budesonida** (combinação) | 17, 19 | ver apresentações RENAME na assinatura |
| prednisona (exacerbação) | 18-19, 22, 33, 35 | 56, 143 |
| **umeclidínio** (LAMA) | 8-10, 16-17, 19 | 107, 174 |

**Emenda do self-check (R5, 06/09):** a primeira passada perdeu os dois LAMAs
irmãos do tiotrópio, citados na mesma frase do PCDT (p. 16): **umeclidínio**
entra no elenco (presente na RENAME, p. 107/174); **glicopirrônio** fica fora
por ausência na RENAME (🟡 por disponibilidade, mesmo modelo do §2).

A combinação tem row própria pelo precedente J45 (`formoterol + budesonida`, a
estratégia terapêutica central da DPOC estável): `canon_ativo` não decompõe
combinações; sem row, amarelo falso sistemático.

## §2 Fora do elenco (com razão e página)

- **fluticasona**: recomendada no PCDT (p. 8, 17, 19, 22) em combinações, mas
  **AUSENTE da RENAME 2024**. Ponto de decisão no modelo fosfomicina: 🟢 com a
  ausência declarada na row, ou 🟡 por disponibilidade. Recomendo 🟡.
- **teofilina**: p. 18 (texto) e anexo (54, 59-60); não recomendada na DPOC
  estável pela linha GOLD do protocolo; AUSENTE da RENAME. Fora.
- **roflumilaste**: apenas anexo histórico (53-56). Fora.
- **glicopirrônio** (emenda do self-check R5): LAMA citado no PCDT junto ao
  tiotrópio e umeclidínio (p. 16), mas **AUSENTE da RENAME 2024** → 🟡 por
  disponibilidade. Se o Fabiano preferir o modelo fosfomicina (🟢 com ausência
  declarada), é acréscimo de uma row.
- **salmeterol**: anexo (53, 67-68) no PCDT da DPOC — embora CONSTE da RENAME
  (p. 111, 221). Fora do elenco por não recomendado no protocolo vigente.

## §3 Posologia

Pendente de levantura na assinatura, direto do PDF estagiado (as doses vivem nas
p. 15-22; mesmas páginas do elenco). Não se inventa row.

## §4 Pontos de decisão (só o Fabiano)

1. **Fluticasona** (recomendada no PCDT, ausente da RENAME): recomendo 🟡 com a
   causa, coerente com o estrito. Alternativa: 🟢 com ausência declarada (modelo
   fosfomicina).
2. **Combinação formoterol + budesonida**: recomendo INCLUIR (precedente J45).
3. Versão na assinatura: `semaforo_j44_exaustiva_v1_2026-09`.

## §5 Sequenciamento

Sessão de assinatura sugerida: **I50 junto** (mesma rodada) — duas condições
cardiorrespiratórias, uma sessão. O flip independe de código (canon já curado
para dose e concentração).

---

*Lavrado na R4 da agenda (dom 06/09), com extração mecânica das duas fontes
estagiadas e cruzamento PCDT×RENAME. Self-check de citações na R5.*

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

Três das quatro de J44 voltaram (salbutamol, budesonida, prednisona), do
**Quadro 6, p. 19-22** do PCDT DPOC 2025.

**A quarta NÃO voltou, e o motivo é de fonte:** `fumarato de formoterol +
budesonida` está na lista de medicamentos (p. 19), mas o Quadro 6 **não traz
esquema de administração para LABA+ICS** — o Protocolo afirma que a combinação
não é opção preferencial na DPOC (p. 9, p. 17). Sem dose na fonte, não se
escreve row: *"não se inventa row"* é a regra desta casa, e ela valeria pouco se
cedesse justamente para fechar uma contagem de nove. O que importa clinicamente
já está garantido — com a chave composta, a dose de ASMA não vaza para a DPOC
(guarda:
`test_formoterol_budesonida_nao_empresta_a_dose_da_asma_para_a_dpoc`). Escrever
a row exige uma caneta com dose de fonte, não este ticket.
