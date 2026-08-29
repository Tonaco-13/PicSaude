# Manifesto — CID-10 (commitado; binários ficam locais)

TICKET-FILA-6-CID10-COMPLETO.md, fechado como TETO ACESSÍVEL (martelo do
Fabiano, 29/08/2026, §6 do ticket). `data/fontes-oficiais/.gitignore`
(idiom `*` + `!*/` + `!*/MANIFEST.md`, corrigido na auditoria da #222) faz
os PDFs desta pasta ficarem locais, fora do git — só este manifesto
commita. É a proveniência reproduzível: sha256 + URL oficial de cada
binário, para qualquer um reconstruir o estado exato sem o repositório
carregar o binário em si.

## orientacoes-codificacao-demais-codigos-emergencia-covid19-ms-2025.pdf
- sha256: 13ecf3c2ce33dcc468f1728435975488906f9ebf419330bc42fd0d933c58753f
- Fonte oficial: https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/c/covid-19/publicacoes-tecnicas/guias-e-planos/orientacoes-para-a-codificacao-dos-demais-codigos-de-emergencia-relacionados-a-covid-19.pdf
- Título: "Orientações para a codificação dos demais códigos de emergência
  relacionados à covid-19" — Ministério da Saúde, Secretaria de Vigilância
  em Saúde e Ambiente (SVSA), Daent. Brasília, 2025. 1ª edição eletrônica,
  18 páginas. Título anterior (mesma obra, edição prévia): "Orientações
  sobre novos códigos de emergência para as causas de morte relacionadas a
  condições que ocorrem no contexto da Covid-19" (2021).
- Baixado pelo engenheiro em 29/08/2026 (`curl`, HTTP 200, `file` confirma
  PDF v1.4 válido — HEAD na mesma URL responde 403, GET funciona; WAF do
  gov.br trata os dois verbos de forma diferente).
- Cobertura confirmada por extração de texto (PyPDF2): U07.1, U07.2, U09.9
  (`MARCADOR: U09.9`), U10.9, U12.9 (`MARCADOR: U12.9`). NÃO cobre U08.9
  nem U11.9 — ver o outro PDF desta pasta para esses dois.
- Usado para recitar a coluna `fonte` de 5 rows em `data/cid10.csv`
  (via `backend/scripts/importar_snapshot_cid10.py`).

## covid-19-coding-updates-3-4-combined_pt_OMS.pdf
- sha256: b39041a96ed4bbc1957a4cc0502bdf09238536e7ab8ba09d26333caae6f2d8e0
- Fonte oficial: https://cdn.who.int/media/docs/default-source/classification/icd/covid-19/covid-19-coding-updates-3-4-combined_pt.pdf?sfvrsn=f8a2aed_3
- Título: "Atualizações 3 e 4 em relação à codificação da COVID-19 com a
  CID-10" — Organização Mundial da Saúde, tradução em português, 2 páginas.
- Baixado pelo engenheiro em 29/08/2026 (`curl`, HTTP 200, `file` confirma
  PDF v1.3 válido, 2 páginas).
- Cobertura confirmada por extração de texto: define formalmente U08
  ("História pessoal de COVID-19"), U08.9, U09, U09.9, U10, U10.9, U11
  ("Necessidade de imunização contra a COVID-19"), U11.9, U12, U12.9 — as
  descrições batem quase palavra por palavra com as já presentes em
  `data/cid10.csv` (confirma que a base local já usava esta fonte,
  só sem citação verificável por linha).
- Usado para recitar a coluna `fonte` de 2 rows (U08.9, U11.9) em
  `data/cid10.csv` — as únicas duas não cobertas pelo PDF do MS acima.

## data/cid10.csv (pós-transformação, referência de reprodutibilidade)
- sha256: 1d3e229520c05a0cdaf772f827ca0eb51a5d3ca18408331e69cec5164b484a6c
- 14.240 rows, coluna `versao_snapshot="V2008+remendos-2026"` em toda row.
- Reproduzível: `python3 backend/scripts/importar_snapshot_cid10.py` sobre
  o CSV committado antes desta PR produz este arquivo, byte a byte
  (script idempotente — ver docstring do script).

## Gap medido — espelho de terceiros, CONFERÊNCIA, NÃO FONTE

`tabelacid.com.br` (consultado 29/08/2026, `/sobre`) declara **14.736**
códigos, metodologia declarada "CID-10, versão 2019/2020 (CC-BR-FIC/DataSUS)
— publicada pelo Centro Colaborador Brasileiro para a Família de
Classificações Internacionais (CC-BR-FIC), Ministério da Saúde". Número
NÃO importado, NÃO verificado independentemente — citado só para calibrar
o gatilho de reabertura (a) do §6 do ticket. Ver
`docs/tickets/RELATORIO-DIFF-CID10.md` para o mesmo número em contexto.

## Fontes verificadas e descartadas (registro do beco, §6 do ticket)

Para não repetir a mesma varredura no futuro sem necessidade — todas
conferidas com `curl`, não artefato de ferramenta, em 29/08/2026:

- **SVS/MS** (portal + boletins epidemiológicos): nenhum canal publica a
  tabela CID-10 completa pós-2008 para download — boletins e painéis USAM
  códigos CID, não os publicam como tabela.
- **DATASUS** (`www2.datasus.gov.br/cid10/`): só `V2008/` existe
  (`Last-Modified: 2014`, mesma base já no repo); `V2019` a `V2023`
  retornam 404.
- **CBCD/USP** (`fsp.usp.br/cbcd`): 404 real — site parece reestruturado
  ou fora do ar.
- **FHIR RNDS oficial** (`terminologia.saude.gov.br/fhir/CodeSystem-BRCID10`,
  Ministério da Saúde, atualizado em 22/08/2026): `CodeSystem-BRCID10.json`
  público tem `"content": "not-present"` — só metadado; os códigos vivem
  no terminology server operacional, atrás de autenticação institucional
  que o PicSaúde não tem hoje (gatilho de reabertura (b) do §6).
