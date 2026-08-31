# DESENHO-ONDA-PCDT — Montar as bases PCDT (corpus → extração → curadoria)

| Campo | Valor |
|---|---|
| **Origem** | Fabiano, 29/08: *"temos que ver como vamos montar as bases PCDTs"* + *"a gente importa o dataset ou cria ponte de consulta instantânea?"* |
| **Martelos que regem** | 28/08: *"PCDT + RENAME 100%!!!! Pode ir"* · 28/08 (onda das bases): *"importação offline versionada, nunca ao vivo"* |
| **Classe** | Camada 0 (corpus) e 1 (extração): `ops`/`adapter` · Camada 2 (curadoria): humano, assinatura Fabiano |
| **Estado** | 🟡 Desenho lavrado · camada 0 iniciada (catálogo estagiado 29/08) · corpus de PDFs: 30/08 |

---

## §0 A pergunta que abre o desenho: importar ou ponte viva?

**Importar. Sem ponte de consulta instantânea.** Não é preferência — é o martelo
da onda das bases (28/08: *"importação offline versionada, nunca ao vivo"*), e a
sonda de 29/08 deu três razões práticas a mais:

1. **O canal aberto é imaturo e defasado.** O dataset publicado
   (dadosabertos.saude.gov.br) expõe 6 recursos em S3 cujo snapshot data de
   **13/08/2025**; o catálogo lista DM2 como *"Em atualização"* quando a portaria
   vigente é de **21/02/2026** (a que o E11 já estagiou, sha256 no manifesto).
   Consulta viva a um índice defasado é consultar mentira com timestamp.
2. **Sem versionamento não há proveniência por row.** A curadoria é assinada
   **citando** portaria + quadro + página. Uma ponte viva muda por baixo e
   quebra a citação — o invariante do vagão.
3. **A API viva documentada é o mesmo catálogo.**
   `apidadosabertos.saude.gov.br/v1/…controle_pcdt` serve o índice
   (nome/status/tipo), não o conteúdo. Não há o que pontear.

A única ponta viva do produto continua sendo a **curadoria assinada**. O rio
lá fora entra pela comporta (snapshot versionado), não pela tomada.

## §1 Fatos medidos (sonda do arquiteto, 29/08, tudo estagiado em `data/fontes-oficiais/pcdt/aberto-2025-08-13/`)

**O dataset aberto é um CATÁLOGO, não uma tabela de fármacos.** 83 condições,
schema inteiro: `nome;status;tipo`. Nenhuma coluna de CID, princípio ativo,
portaria ou apresentação. O Ministério publica o **índice**; o **conteúdo**
canônico é **só PDF**.

| Recorte | Contagem |
|---|---|
| Total de condições no catálogo | 83 |
| por status | Aprovado\* 28 · Conitec 6 · Em atualização 36 · Em elaboração 13 |
| por tipo | PCDT 67 · DDT 7 · Protocolo de Uso 4 · Diretrizes Brasileiras 4 · Diretriz 1 |

Fatos que afinam o desenho:

- **O catálogo é corda de frescor, não fonte.** DM2 "Em atualização" no
  snapshot 08/2025 vs portaria 02/2026 vigente — cada reconciliação futuro
  catálogo×corpus denuncia o atraso do canal.
- **Asma (J45) tem PCDT no catálogo; F32 e ITU (N39.0) NÃO têm** — confirma a
  régua que o vagão já praticava: condição sem PCDT dedicado segue o padrão I10
  (diretrizes de especialidade + RENAME).
- O asterisco de "Aprovado\*" está no dicionário estagiado
  (`Metadados_PCDT.pdf`) — conferir lá antes de interpretar.

## §2 As três camadas

```
┌─ Camada 2 · CURADORIA ASSINADA (Fabiano) ──────────────────┐
│  decisao_semaforo.csv + posologia_sugerida.csv             │
│  unidade = levantura dupla E11 (uma passada, uma assinatura)│
└───────────────▲────────────────────────────────────────────┘
                │ rascunho com citação (portaria, quadro, pág.)
┌───────────────┴────────────────────────────────────────────┐
│  Camada 1 · EXTRAÇÃO ASSISTIDA (arquiteto + máquina)       │
│  pré-tabela rascunho pcdt×cid×princípio×posologia×linha    │
│  NUNCA SERVIDA — grau rascunho por construção              │
└───────────────▲────────────────────────────────────────────┘
                │ lê
┌───────────────┴────────────────────────────────────────────┐
│  Camada 0 · CORPUS ESTAGIADO (ops)                          │
│  PDFs oficiais (canônico) + catálogo (índice/checklist)     │
│  sha256 por arquivo, manifest versionado, NUNCA ao vivo     │
└─────────────────────────────────────────────────────────────┘
```

## §3 Camada 0 — o corpus (o que estagiar)

- **PDFs das portarias vigentes** (canônicos): página CONITEC de PCDT é o
  índice navegável com os links. Denominador inicial: as condições **com
  portaria publicada** (as 28 "Aprovado\*" + as 36 "Em atualização", que têm
  versão vigente enquanto a revisão corre). "Em elaboração" (13) entra quando
  publicar.
- **Catálogo aberto** (checklist + corda de frescor): já estagiado (29/08).
- **Convenção herdada do E11**: `data/fontes-oficiais/pcdt/<nome>-<ano>.pdf`,
  MANIFEST.md com sha256, fonte, edição e sonda de conteúdo.
- **PDFs NÃO entram no git** (dezenas de MB): `.gitignore` em
  `data/fontes-oficiais/`; o que commita é o **manifesto** (as chaves do
  corpus) e os relatórios de reconciliação. Repositório continua leve; o
  corpus é reconstruível pelos URLs + sha256 do manifesto.

## §4 Camada 1 — extração assistida (rascunho de máquina)

- Pré-tabela: `pcdt · condicao · cid · principio_ativo · posologia_bruta ·
  linha · citacao (portaria+quadro+pág) · status_curadoria=rascunho`.
- Fonte de extração: os **Quadros de esquemas terapêuticos** dos PDFs (o E11
  usou Quadros 15/18; cada PCDT tem os seus). Ferramenta: pypdf + leitura
  assistida — **permitido aqui** porque o produto desta camada é RASCUNHO
  verificável, nunca dado servido.
- A linha vermelha do vagão §8.1 estende-se à máquina: **extração nunca flipa
  `validado`/`exaustivo`**; toda row de extração nasce `rascunho` e morre
  rascunho até a assinatura.
- Catálogo como checklist de completude: corpus sem PDF de condição
  "Aprovado\*" = gap listado no relatório de reconciliação.

## §5 Camada 2 — curadoria (o gargalo é o produto)

- Unidade de trabalho: **levantura dupla** (rows do semáforo E rows de
  posologia, mesma passada, mesma assinatura) — o formato que o E11 provou.
- Ordem: a fila do vagão (E11 pronto para assinar → J45 → F32 → N39.0), depois
  crônicas de alto impacto, depois a cauda das 28+36.
- Ritmo sugerido: sessões de lote (3–5 condições pré-revisadas por sessão).
- A régua que faz "100%" ser programa honesto: o **portão da exaustividade**
  (CID sem curadoria → NEUTRO, nunca mentira). Cobertura parcial é feature.

## §6 Cronograma em curso (hoje–amanhã, arquiteto)

| Dia | Entrega |
|---|---|
| 29/08 (hoje) | ✔ Este desenho · ✔ catálogo + dicionário estagiados com sha256 · ✔ manifesto atualizado · ✔ agendamento |
| 30/08 (amanhã) | Corpus de PDFs (scrape CONITEC → download → sha256 → manifest) · relatório de reconciliação catálogo×corpus×portarias (gaps, defasagens, denominador real) |
| depois | Extrator da camada 1 (slot `ops` na fila do engenheiro, junto da onda das bases) · rascunhos assistidos condição a condição (arquiteto) · sessões de assinatura (Fabiano) |

## §7 Classes e guardrails

- Estagiagem e extrator: `ops`/`adapter` — **nunca** escrevem em tabela clínica
  nem nos CSVs de curadoria; saída é arquivo de dados + relatório.
- CSVs de curadoria só mudam por levantura assinada (vagão §1.1).
- Nenhum `core` em lugar algum desta onda.
- gov.br com rate limit ou bloqueio: registrar e parar com relatório parcial —
  nunca insistir contra o host oficial.

## §8 Em aberto (só o Fabiano decide)

1. **Escopo do "100%"**: 67 PCDTs primeiro e DDT/Protocolos de Uso depois
   (recomendo), ou tudo junto?
2. **PDFs fora do git** (manifest commitado) — conforme §3; martelar se quiser
   o contrário (repo engordaria ~100–200 MB).
3. **Sessão de assinatura E11**: rascunho pronto (`RASCUNHO-E11-DUPLO-PCDT-2026.md`);
   com o strip de dose mergeado (#220 martelada 29/08), o flip está destravado.

---

*Lavrado pelo arquiteto em 29/08/2026, com sonda própria: catálogo baixado,
descompactado e contado; URLs S3 extraídos da página do dataset; dicionário
estagiado. Tudo reproduzível pelos URLs e sha256 abaixo no MANIFEST.*
