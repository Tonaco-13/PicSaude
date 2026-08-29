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
