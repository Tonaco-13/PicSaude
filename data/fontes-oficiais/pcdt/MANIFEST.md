# Manifesto — PCDT (commitado; binários ficam locais)

`data/fontes-oficiais/.gitignore` (idiom `*` + `!*/` + `!*/MANIFEST.md`,
corrigido na auditoria da #222) faz os PDFs/ZIPs desta pasta ficarem
locais, fora do git — só este manifesto commita: sha256 + URL oficial de
cada binário, para reprodutibilidade sem carregar o binário no repo.

## PCDT-diabete-melito-tipo-2-2026.pdf
- sha256: f90b782997a5f90842877c6526432cd382b596ad6cb7ad95da0a2fd776dfae09
- Fonte oficial: https://www.gov.br/conitec/pt-br/midias/protocolos/2026/pcdt-diabete-melito-tipo-2
- Edição: Portaria SCTIE/MS nº 13, de 21/02/2026 — 80 páginas
- Baixado pelo arquiteto (Z) em 28/08/2026; extração pypdf OK
- Sonda de conteúdo: {'metformina': 37, 'dapagliflozina': 26, 'glibenclamida': 16, 'insulina': 255, 'esquema terapêutico': 1, 'elenco': 0}

## Snapshot do dataset aberto — aberto-2025-08-13/ (baixado 29/08/2026)

Fonte: dataset "PCDT" do portal de dados abertos do MS (6 recursos em S3,
snapshot de 13/08/2025). O catálogo é ÍNDICE (nome;status;tipo — 83 condições,
sem CID/fármaco/portaria); o conteúdo canônico é o PDF de cada portaria.

### aberto-2025-08-13/pcdt.csv.zip
- sha256: 531648c7ec8e5e8b90b3b7b0373423d64cf046ff7d6e448679d8f5952e549f99
- URL: https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CONITEC/csv/pcdt.csv.zip
- Conteúdo (descompactado): 83 condições — Aprovado* 28 · Conitec 6 · Em atualização 36 · Em elaboração 13; tipos: PCDT 67 · DDT 7 · Prot. Uso 4 · Dir. Brasileiras 4 · Diretriz 1

### aberto-2025-08-13/pcdt.json.zip
- sha256: 0678655cddc53af1ea0298f5575f843576fdf367ee9991750e1f1c41a2f1e324
- URL: https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CONITEC/json/pcdt.json.zip
- Mesmo conteúdo do CSV, em JSON.

### aberto-2025-08-13/Metadados_PCDT.pdf
- sha256: 393e528b7f73e9904f1595b773c0951ecff1f9ad8a61394b2d2f410a5eb08ada
- URL: https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CONITEC/pdf/Metadados_PCDT.pdf
- Dicionário de dados do dataset (conferir aqui o significado do "Aprovado*").

Nota de frescor (arquiteto, 29/08): o catálogo lista DM2 como "Em atualização"
(snapshot 08/2025) quando a portaria vigente é SCTIE/MS 13/2026 — o canal
aberto ATRASA; portaria/PDF é o canônico. Ver DESENHO-ONDA-PCDT.md §0–§1.

## Corpus CONITEC — corpus-conitec-2026-08-30/ (baixado 30/08/2026 pelo arquiteto)

- **240 PDFs, 373 MB, zero falhas** — família `/conitec/pt-br/midias/protocolos/`
  (qualquer forma de URL, INCLUSIVE as sem extensão `.pdf`, onde moram os mais
  novos). Página-Fonte: https://www.gov.br/conitec/pt-br/assuntos/avaliacao-de-tecnologias-em-saude/protocolos-clinicos-e-diretrizes-terapeuticas/pcdt
- **`SHA256SUMS.txt`** no interior da pasta: 240 entradas `sha256 <arquivo>`.
  **Âncora** (sha256 do próprio SHA256SUMS.txt):
  `f358ea7d05d90f9c850044f9289130a1dddbc6768217230270316a2b95544f3d`
- Download com pausa de 2s, validação por magic bytes (`%PDF`) — lição do
  incidente da primeira passada: sem o sufixo `@@display-file/file` o Plone
  devolve a PÁGINA de visualização em HTML, não o arquivo.
- **Escopo declarado**: apenas a família `protocolos/`. As famílias
  `legislacao/`, `pdf/` e `consultas/` da mesma página NÃO foram colhidas
  (legislação avulsa e relatórios de consulta — decisão registrada, não lacuna).
- Reconciliação catálogo×corpus: `docs/tickets/RELATORIO-RECONCILIACAO-PCDT.md`

## Adendos pós-batch — adendos-pos-batch/

Fontes estagiadas DEPOIS do batch de 30/08, uma a uma, cada qual com despacho
próprio. Ficam em pasta separada **de propósito**: o `SHA256SUMS.txt` do
`corpus-conitec-2026-08-30/` é a **âncora daquele batch** e não é reescrito —
acrescentar um 241º arquivo lá dentro faria a pasta discordar do próprio
carimbo. Aqui a âncora é a entrada individual abaixo.

### adendos-pos-batch/pcdt_anemia_deficienciaferro_2014.pdf
- sha256: `94ead687bc36a6ece58f2369dd0c51c24d4f1ba1f8496a6e4e3847c165b824e1`
- Tamanho: 609.200 bytes (20 páginas) · Estagiado em 22/09/2026 (P-10, DESPACHO-ENG-021)
- URL: https://www.gov.br/conitec/pt-br/midias/consultas/relatorios/2014/pcdt_anemia_deficienciaferro_2014.pdf/@@display-file/file
- Página-fonte: a MESMA do batch (`.../protocolos-clinicos-e-diretrizes-terapeuticas/pcdt`)
- Edição: **Portaria SAS/MS nº 1.247, de 10 de novembro de 2014** — "Anemia por
  Deficiência de Ferro". CIDs declarados no texto: **D50.0** e **D50.8**.
- Validação: magic bytes `%PDF` conferidos (a lição do incidente da primeira
  passada — o sufixo `@@display-file/file` é obrigatório, senão o Plone devolve
  a página de visualização em HTML).
- Extração pypdf: **BOA** (70.722 caracteres). Sonda de conteúdo:
  `{ferro: 226, CID: 41, ferritina: 24, sulfato ferroso: 15, sacarato: 14, D50: 4}`.

**POR QUE FALTAVA — e não era acidente.** O catálogo aberto 08/2025 lista
"Anemia por deficiência de ferro" como *Aprovado\**, mas o PDF não está no
corpus porque ele mora na família **`consultas/relatorios/`**, e o batch de
30/08 declarou escopo `protocolos/` apenas (ver a seção acima: *"as famílias
`legislacao/`, `pdf/` e `consultas/` NÃO foram colhidas — decisão registrada,
não lacuna"*). A ausência tinha causa documentada; este adendo cruza aquela
linha de escopo **deliberadamente**, para uma condição só.

**IDADE DECLARADA (para a curadoria, antes da caneta):** é de **2014** — o PCDT
mais antigo da despensa, e a página oficial não oferece edição mais nova. Pela
régua da casa (a mesma da ITU 2003 e da AMB 2008), a idade entra declarada no
rascunho e no campo `fonte` de qualquer row que dele saia. O cruzamento com a
RENAME 2024 é o que dirá se o elenco ainda se sustenta.

### adendos-pos-batch/pcdt-da-doenca-pulmonar-obstrutiva-cronica-2021.pdf
- sha256: `86448b826799ad98ee5f05634fa3bbb25c9e94f5af8dd01627c8cd70ec60cc2c`
- Tamanho: 2.782.813 bytes (72 páginas) · Estagiado em 24/09/2026 (ENG-025 §B)
- URL de origem (a **oficial**, tal como servida à época):
  `https://www.gov.br/saude/pt-br/assuntos/pcdt/d/doenca-pulmonar-obstrutiva-cronica/@@download/file`
- **Recuperado pelo Internet Archive**, captura de **05/05/2025**:
  `https://web.archive.org/web/20250505102131id_/https://www.gov.br/saude/pt-br/assuntos/pcdt/d/doenca-pulmonar-obstrutiva-cronica/@@download/file`
- Edição: **Portaria Conjunta SAES/SCTIE nº 19, de 16 de novembro de 2021** —
  "Doença Pulmonar Obstrutiva Crônica". CID declarado: **J44**.
- Validação: magic bytes `%PDF` conferidos · extração pypdf **BOA**
  (154.034 caracteres). Sonda: `{formoterol: 21 pág, budesonida: 14 pág,
  LABA: 23 pág, ICS: 13 pág, "Esquemas de administração": p.16}`.

**POR QUE PELO ARQUIVO, e não do servidor vivo — declarado, não contornado.**
A edição de 2021 foi **revogada** pela Portaria Conjunta SAES/SCTIE nº 29, de
27/11/2025 (art. 4º do PDF de 2025, já no corpus). O canal oficial serve
**somente a edição vigente**: em 24/09/2026 tanto
`conitec/.../protocolos/pcdt-da-doenca-pulmonar-obstrutiva-cronica` quanto
`saude/.../pcdt/d/doenca-pulmonar-obstrutiva-cronica/@@download/file` devolvem
o PDF de 2025 — este último **byte-idêntico** ao `0cb3c41b…` do corpus de
30/08 (cross-check do corpus feito de carona). O repositório oficial de
legislação (`bvsms.saude.gov.br/.../poc0019_22_11_2021.html`) respondeu
**HTTP 503** em três tentativas (WAF F5). A captura do arquivo **é da própria
URL oficial**, feita antes da revogação — é o mais próximo do primário que
existe hoje para uma edição revogada.

**CORROBORAÇÃO INDEPENDENTE (porque procedência de arquivo exige prova).**
Uma segunda cópia, de origem não relacionada
(`static.poder360.com.br/2023/11/PCDT-DPOC-SUS-2021.pdf`, sha256
`7c875cf1…`), tem **bytes diferentes** (2.819.756 — outro empacotamento) e
**texto extraído byte-a-byte IDÊNTICO** nas 72 páginas
(`sha256(texto)=a2e4173c0b4ac23e…`, 148.758 caracteres nas duas). O conteúdo é
autêntico; só o invólucro difere. O sha256 registrado acima é o da cópia
estagiada — a que veio da URL oficial.

**A DIVERGÊNCIA DE DATA, resolvida PELO DOCUMENTO.** A casa vinha falando em
"nº 19, de 22/11/2021"; o PDF de 2025 revoga "nº 19, de **16** de novembro de
2021". As duas datas são verdadeiras sobre coisas diferentes, e o art. 4º do
2025 diz as duas na mesma frase, verbatim: *"Fica revogada a Portaria Conjunta
nº 19, de 16 de novembro de 2021, publicada no Diário Oficial da União (DOU)
nº 218, em 22 de novembro de 2021, seção 1, página 210."* A capa do PDF de
2021 agora estagiado confirma: **"PORTARIA CONJUNTA Nº 19, DE 16 DE NOVEMBRO
DE 2021"**. Portanto: **assinada em 16/11, publicada em 22/11** — cita-se
16/11/2021 para a portaria, 22/11/2021 para a publicação. Ninguém errou; a
casa citava a data de publicação.

**O QUE ESTE ADENDO RESPONDEU (ENG-025 §B) — e a resposta foi "não".** Foi
estagiado para buscar a posologia da associação **fumarato de formoterol +
budesonida em J44**, que o #269 deixou de fora honestamente. **Não existe, nem
em 2021 nem em 2025** — ver o registro completo em
`docs/tickets/REGISTRO-J44-NONA-ROW-SEM-DOSE.md`. O PDF fica estagiado de
qualquer forma: é a evidência de que a pergunta foi feita à fonte primária.
