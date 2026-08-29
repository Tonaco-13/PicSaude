# TICKET-FILA-6 — CID-10 completo: revisão vigente, import offline versionado

| Campo | Valor |
|---|---|
| **Origem** | Fila 6 da FILA-VIVA · onda das bases (martelo 28/08: "CID-10 completo → SIGTAP-exames → listas RDC"; disciplina: *"importação offline versionada, nunca ao vivo"*) |
| **Classe** | `ops` (estagiagem + import) com toque `module` (proveniência por linha). **Zero `core`** — ver §5 |
| **Para** | Engenheiro |
| **Estado** | 🟡 Desenho pronto, aguardando execução |

---

## §1 O que existe HOJE (verificado pelo arquiteto em 29/08, `main` pós-#221)

- **`data/cid10.csv` — 14.240 rows, e é a fonte única viva**: carregada por
  `base_cid.py` (`_carregar_csv`, `base_cid.py:649`), servida por
  `routers/ia.py:37` (`BASE_CID`), consultada por `domain/cid.py` (catálogo suave).
- **Conteúdo defasado**: bulk "DATASUS/CID-10 **V2008**" + remendos ad-hoc
  pós-2008 (U07.1 pela Frente A do TICKET-CID-VALIDACAO; U11.9/U12.9 no rabo do
  arquivo com fonte "OMS 2021"). A revisão brasileira vigente (2ª edição, com
  atualizações MS posteriores — BES/suplementos) NÃO está aqui.
- **Sem proveniência versionada**: a coluna `fonte` é texto livre misto; não há
  manifest, sha256 nem versão de snapshot.
- Docstring do `base_cid.py` ainda se autochama "subset MVP ~240" — lenda
  velha (o loader lê o CSV completo); corrigir a legenda no mesmo PR.

## §2 O que fazer

### Passo 1 — Estagiar a fonte (camada 0, padrão `DESENHO-ONDA-PCDT` §3)

Baixar a **tabela CID-10 brasileira vigente** (2ª edição, revisão/ATUALIZAÇÃO
mais recente publicada pelo MS/SVS — a de 2023 e incrementos, conferir a
versão corrente na execução) para `data/fontes-oficiais/cid10/` com sha256 em
`MANIFEST.md` (mesma convenção do PCDT). Candidatos de fonte, em ordem:

1. Portal SVS/MS / BES — "Atualização da Classificação de Estatísticas de
   Mortalidade / CID-10" (suplementos publicam a tabela completa em XLSX/PDF);
2. DATASUS (tabnet/ftp — "CID-10 Subcategorias, adaptação brasileira");
3. ecos/terceiros SÓ como espelho de conferência — nunca como fonte primária.

Regra da onda: se o host oficial bloquear/rate-limitar, registrar e parar com
relatório parcial. Nunca insistir contra gov.br.

### Passo 2 — Import offline versionado (camada 1)

`backend/scripts/importar_snapshot_cid10.py` (padrão dos
`importar_snapshot_*.py` já existentes — CBO, RDC):

- lê o arquivo estagiado, **não a rede**;
- escreve `data/cid10.csv` com colunas `codigo_cid,descricao,fonte,versao_snapshot`
  (`versao_snapshot` = identificador da revisão oficial, igual em todas as rows);
- idempotente (re-rodar não duplica; reposição por código);
- **produz `RELATORIO-DIFF-CID10.md`**: códigos novos, descrições alteradas,
  códigos ausentes na nova revisão.

### Passo 3 — Consumo (só o que a troca de dados exige)

- `domain/cid.py`: **zero mudança** (a régua formato-estrito/catálogo-suave
  continua; a defasagem deixa de ser nossa).
- `base_cid.py`: atualizar o docstring-MVP e, se preciso, o loader para a
  coluna nova. Nenhum hardcode de catálogo duplicado — a base é uma só.
- Typeahead do prescritor: já consome via `BASE_CID`; a completude nova chega
  de graça (o painel #216 é agnóstico — nada a reabrir).

## §3 Criterios de aceite

1. **Diff report existe e é honesto**: lista novos/alterados/removidos. Nenhum
   código da base atual é REMOVIDO silenciosamente — remoção é decisão do
   arquiteto com o report na mão.
2. **Regressão de formato**: o regex `_RE_FORMATO_CID` casa 100% dos códigos
   da nova base (hoje: 14.233/14.233, 26 letras) — recontar e registrar.
3. **Proveniência**: toda row com `versao_snapshot`; manifest da fonte com
   sha256; reprodutível do manifest.
4. **Testes existentes verdes**: guardas do TICKET-CID-VALIDACAO (formato 422,
   catálogo suave, U07.1) + suite de browser que usa CID.
5. **Nenhuma API muda** — este ticket é DADO, não contrato.

## §4 Fora do escopo (cercas explícitas)

- **`cadeia_cid` com blocos DATASUS (ex.: I10–I15) no semáforo** — o próprio
  `canon_cid` declara blocos como "versão futura". Isso é aresta de decisão
  clínica (`semaforo_decisao.py`): **`core`**, PR própria, martelo do Fabiano.
- **Mini-CID do encaminhamento** (`catalogos-encaminhamento.js`, 55 códigos) —
  catálogo curado de outro módulo; não é consumidor desta base.
- **CID-11** — não existe no SUS; nem conversor, nem esboço.

## §5 Classes e guardrails

`ops` a maior parte (download estagiado, script de import, report). O toque
`module` é só o loader/docstring do `base_cid.py`. **Não escreve em tabela
clínica, não emite evento, não altera estados** — e o semáforo fica intocado.

---

## §6 ACHADO DA EXECUÇÃO (29/08) — o beco é real; decisão devolvida ao Fabiano

O engenheiro varreu os três candidatos na ordem do ticket e parou onde o
ticket mandava parar. Constatações (todas com curl, não artefato de ferramenta):

1. **SVS/MS**: nenhum canal oficial publica a tabela completa pós-2008 para
   baixar — boletins e painéis USAM códigos CID, não os publicam como tabela.
2. **DATASUS**: `cid10/V2008/` vivo porém é a MESMA base (Last-Modified 2014);
   `V2019…V2023` não existem como pastas.
3. **CBCD/USP** (mantenedor histórico citado no `base_cid.py`): 404 real.
4. **Extra — FHIR RNDS** (`terminologia.saude.gov.br`, atualizado 22/08/2026):
   o `CodeSystem-BRCID10.json` público é só metadado (`"content":
   "not-present"`); os códigos vivem no terminology server operacional, atrás
   de autenticação institucional que o PicSaúde não tem.

**Verificação independente do arquiteto (29/08)** confirma o beco — e acrescenta
dois fatos:

- **Deltas oficiais EXISTEM**: o MS publica documentos técnicos de atualização
  (ex.: "Orientações para a codificação dos códigos de emergência COVID" —
  cobre U07–U12); listas de códigos novos 2019/2020 circulam em canal oficial
  estadual (DIVE/SES-SC). Servem para CITAR remendos, não como tabela completa.
- **CID-11 tem cronograma MS de transição com conclusão prevista ~2027** — a
  CID-10 segue classificação operante por anos; investir em caça à tabela
  pós-2008 tem retorno decrescente.

### Recomendação do arquiteto: opção 1 (fechar no teto acessível), com três refinamentos

1. **Proveniência honesta do que já existe**: corrigir docstring lendário do
   `base_cid.py`, coluna `versao_snapshot="V2008+remendos-2026"`, manifest
   sha256 do CSV atual.
2. **Remendos re-citados**: estagiar o PDF oficial MS dos códigos de emergência
   (sha256) e trocar a coluna `fonte` das rows remendadas pela citação oficial
   — mesmo dado, proveniência de verdade.
3. **Lacuna medida, não importada**: usar espelho de terceiros SÓ para medir o
   gap no relatório (números rotulados como conferência), jamais como fonte.

**Gatilhos de reabertura (registrados):** (a) o MS publicar a tabela completa
em canal aberto; (b) o PicSaúde conseguir acesso institucional RNDS
(realístico na era pós-G4A — integração RNDS é horizonte do produto);
(c) marcos da transição CID-11 (base nova, projeto novo — não update).

Opção 2 (credencial RNDS) descartada: não existe hoje. Opção 3 (terceiro como
fonte primária) descartada: contraria a cerca do §2 do ticket — mantém-se
"espelho só para conferência".

> **MARTELO do Fabiano (29/08, na sessão com o arquiteto): "martelado e
> despachado"** — opção 1 refinada APROVADA, despacho ao engenheiro no mesmo
> dia. O ticket fecha como TETO ACESSÍVEL; os gatilhos de reabertura do §6
> ficam vigentes.

---

*Lavrado pelo arquiteto em 29/08/2026, depois de verificar in-loco: contagem
do CSV (14.240), loader (`base_cid.py:649`), consumidor (`ia.py:37`), régua de
validação (`domain/cid.py`) e o estado V2008+remendos das linhas de fonte.
§6 acrescentado no mesmo dia, sobre o registro de bloqueio do engenheiro.*
