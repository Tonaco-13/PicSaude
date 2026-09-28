# Manifesto — SIGTAP (commitado; binário fica local)

TICKET-FILA-7-SIGTAP-EXAMES.md, fila 7. `data/fontes-oficiais/.gitignore`
(idiom `*` + `!*/` + `!*/MANIFEST.md`, corrigido na auditoria da #222) faz
o ZIP desta pasta ficar local, fora do git — só este manifesto commita:
sha256 + URL oficial, para reprodutibilidade sem carregar o binário no repo.

Ao contrário do CID-10 (teto acessível, sem fonte aberta pós-2008), o
SIGTAP é **aberto e mensal** — Tabela Unificada do DATASUS, publicada por
competência (mês de vigência).

## TabelaUnificada_202606_v2606091427.zip
- sha256: c573e01806da0a491bbd68f50acbebf30c8b9be7043877a4a24e96e3b99160d1
- Fonte oficial: ftp://ftp2.datasus.gov.br/pub/sistemas/tup/downloads/TabelaUnificada_202606_v2606091427.zip
- Portal de download (lista de competências): http://tabela-unificada.datasus.gov.br/tabela-unificada/app/download.jsp
- Competência: **06/2026** (`DT_COMPETENCIA=202606` em toda row de
  `tb_procedimento.txt`) — a mais recente disponível no portal em
  29/08/2026 (gerada 09/06/2026 14:28, confirmada pelo próprio portal;
  nenhuma competência 07/2026 ou 08/2026 publicada ainda nesta data).
- Baixado pelo engenheiro em 29/08/2026 (`curl ftp://...`, 2.141.359
  bytes, `file` confirma "Zip archive data, at least v2.0 to extract").
- Conteúdo relevante: `tb_procedimento.txt` (4.994 procedimentos, layout
  fixo — `CO_PROCEDIMENTO` 10 dígitos = GG(grupo) SS(subgrupo) FF(forma
  organização) PPP(sequencial) D(dígito verificador)), `tb_grupo.txt`
  (9 grupos), `tb_sub_grupo.txt`, `tb_forma_organizacao.txt` — as tabelas
  de taxonomia que fazem o corte por whitelist (ver
  `backend/scripts/importar_snapshot_sigtap.py` e
  `docs/tickets/RELATORIO-DIFF-SIGTAP.md`).
- **Achado fora do escopo desta rodada**: o ZIP também contém
  `Mapeamento_TUSS_SIGTAP.zip` (mencionado na lista de downloads do
  portal, não baixado) e `rl_procedimento_tuss.txt` (relação
  procedimento↔TUSS ponto-a-ponto — presente no ZIP mas **vazio, 0 bytes,
  nesta competência**). O §4 do ticket explicitamente tira o mapeamento
  TUSS↔SIGTAP do escopo ("não está publicado de forma simples; quando
  houver caso real, onda própria") — registrado aqui como achado, não
  perseguido.

---

## Teto de competência — conferido em 28/09/2026 (ENG-027 §1)

**202606 é a competência mais nova PUBLICADA no canal oficial.** Conferido na
página de download do DATASUS
(`http://tabela-unificada.datasus.gov.br/tabela-unificada/app/download.jsp`)
pelo arquiteto em 28/09/2026 por volta das 12:00 BRT: o portal lista
`TabelaUnificada_202606_v2606091427.zip` como a mais recente, e **202607,
202608 e 202609 não existem** ali.

**O veredito anterior estava errado, e a correção entra como ato.** Em rodada
anterior o SIGTAP foi chamado de *"3 competências atrás"* — o cálculo assumia
que 202609 deveria existir porque estamos em setembro. Não deveria: quem
atrasa é o **canal publicador**, não a casa. É a mesma lição do DM2 (o canal
aberto atrasa; a portaria/PDF é o canônico) e o mesmo músculo de conferir
merge antes de anunciar: **conferir a fonte antes de chamá-la de defasada**.

Portanto **não houve refresh nesta rodada**: `data/sigtap_exames.csv` fica na
202606, e é o correto. Fabricar competência que não existe seria o erro que
este registro existe para não cometer.

**Gatilho de reabertura, declarado:** quando **202607 ou posterior** pousar no
portal, roda-se `backend/scripts/importar_snapshot_sigtap.py` com o ZIP novo,
o sha256 entra aqui como entrada própria, e o `RELATORIO-DIFF-SIGTAP.md`
ganha a rodada. Antes disso, não há o que atualizar.

### Pendência escrita — a nota técnica da competência

A página de download declara a nota técnica oficial em
`ftp2.datasus.gov.br/pub/sistemas/tup/downloads/notastecnicas/nota_tecnica_cgsi_sigtap_2026_06.pdf`.
O FTP **recusou a vantage do arquiteto** em 28/09 e **também a do engenheiro**
(`curl: (28) Connection timed out after 60003 ms`, uma tentativa, conforme o
despacho). Fica registrado com a URL, sem drama e sem espelho: nota técnica é
documento de apoio, não a fonte dos dados — o ZIP com sha256 acima é que é.
