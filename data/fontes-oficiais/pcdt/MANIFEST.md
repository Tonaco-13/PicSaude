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
