# TICKET-FILA-7 — SIGTAP-exames: a tabela oficial como base, o catálogo vira projeção

| Campo | Valor |
|---|---|
| **Origem** | Fila 7 da FILA-VIVA · onda das bases (martelo 28/08). CID-10 fechou como teto acessível (#222, 29/08); SIGTAP é o próximo elo |
| **Classe** | `ops` (estagiagem + import) · `module` (loader/typeahead). **Zero `core`** |
| **Para** | Engenheiro |
| **Estado** | 🟡 Desenho pronto, aguardando execução |

---

## §1 O que existe HOJE (verificado pelo arquiteto em 29/08, `main` pós-#222)

- **Os campos já existem e são populados**: `pedido_exame_itens.codigo_tuss` e
  `codigo_sigtap` (`models/pedido_exame_item.py:25-26`); faturamento já agrega
  pelos dois (Ticket D executado — seletor TUSS/SIGTAP na clínica); as telas
  exibem os códigos.
- **A fonte é curadoria hardcoded**: `app/ai/tuss_base.py` (Ticket 31) —
  `_BASE_RAW` com ~35 procedimentos frequentes, aliases clínicos, preparo,
  alertas. O próprio docstring promete a v2: *"CSV/tabela local com
  versionamento explícito… mapeamento TUSS ↔ SIGTAP"*.
- **Zero SIGTAP oficial em todo o backend**: os códigos SUS atuais nasceram de
  curadoria manual, sem fonte estagiada nem sha256 — a mesma dívida de
  proveniência que a #222 acabou de pagar na CID-10.

## §2 A fonte — o contrário do CID-10: ABERTA e MENSAL

SIGTAP (DATASUS) publica a **Tabela Unificada** para download: ZIP mensal com
tabelas de largura fixa (`tb_procedimento`, `tb_grupo`, `tb_subgrupo`,
`tb_forma_organizacao`, …), versionada por **competência YYYYMM**.

- **Estagiamento**: `data/fontes-oficiais/sigtap/` — ZIP + `MANIFEST.md` com
  sha256 e competência (a competência É a versão). Binário fora do git,
  manifesto commitado (idiom do `.gitignore` corrigido na #222).
- **O corte de exames usa a taxonomia do próprio dump** — whitelist de
  grupos/subgrupos/forma_organizacao diagnósticos (listagem LITERAL no report),
  nunca matching de nome. As tabelas auxiliares vêm no ZIP; o corte é JOIN delas.
- **Competência-alvo**: a corrente no momento do import, pinada no manifest.
  Refresh é gesto manual (re-rodar o script), nunca cron ao vivo — régua da onda.

## §3 O que construir

1. **Camada 0** — estagiar o ZIP mensal + manifest (padrão PCDT/CID-10).
2. **Camada 1** — `backend/scripts/importar_snapshot_sigtap.py`: lê o ZIP
   estagiado, corta os grupos de exame, escreve `data/sigtap_exames.csv`
   (`codigo_sigtap, nome, grupo, subgrupo, forma_organizacao, competencia`).
   Idempotente; report de contagens + whitelist aplicada.
3. **Camada 2** — `tuss_base.py` v2: a camada curada (aliases, preparo,
   alertas) **sobrevive** como curadoria sobreposta — só a FONTE de
   códigos/nomes passa a ser o CSV oficial. Docstring-MVP morre (como o do
   `base_cid.py`). Código não encontrado no CSV oficial: continua válido —
   régua do catálogo suave (desconhecido ≠ inválido; a lição do CID).
4. **Typeahead de exames no prescritor** — sugestão sobre o CSV oficial
   (código + nome), **nunca bloqueio**: nome livre permanece 100% aceito
   (Regra Zero — atrito é defeito). Código SIGTAP é chave de organização
   operacional; **nunca substitui protocolo** (§6b do AGENTS.md).

## §4 Cercas explícitas

- **Valores (R$) NÃO entram no MVP** — dado financeiro; o faturamento
  PicSaúde é contagem+classificação read-only, não precificação SUS. Se um dia
  o contrário for decidido, é martelo.
- **TUSS oficial (ANS) não entra aqui** — outra base, outro órgão; a camada
  TUSS curada segue como está. ~~O mapeamento TUSS↔SIGTAP ponto-a-ponto não
  está publicado de forma simples~~ **ERRATA (arquiteto, 29/08, na pré-auditoria
  da execução):** o mapeamento TEM canal oficial — o dump contém a relação
  `rl_procedimento_tuss.txt` (vazia, 0 bytes, na competência 06/2026) e o
  portal lista `Mapeamento_TUSS_SIGTAP.zip` como download próprio (não
  baixado nesta rodada; ver MANIFEST do sigtap). A conclusão da cerca não muda
  — fica fora do escopo desta PR — mas a futura onda TUSS oficial tem por
  onde começar: avaliar o ZIP dedicado e a relação em competências vindouras.
- **Sem schema change** (campos já existem), **sem evento novo**, **sem
  transmissão TISS/APAC** (adapter → era G4A).
- **CID-10 teto acessível** é o precedente honesto: se o dump mensal mudar de
  formato/URL, registrar e parar com report parcial — nunca insistir contra
  gov.br.

## §5 Critérios de aceite

1. ZIP da competência estagiado com sha256; import reprodutível do manifest.
2. Whitelist de corte LITERAL no report (grupos/subgrupos/formas); contagem
   final ≥ dezenas× a curadoria atual (35) — número real no report.
3. **Regressão da emissão demo**: os ~35 nomes curados continuam resolvendo
   (aliases preservados); testes de emissão de exame verdes.
4. **Typeahead sugere e não bloqueia** (browser test: "glicemia" → sugestão com
   código; nome inédito é aceito sem atrito).
5. Docstring do `tuss_base.py` reescrito sem a lenda MVP.
6. Faturamento byte-idêntico (read-only intocado).

## §6 Em aberto (só o Fabiano decide)

1. **Valores SIGTAP no futuro?** (recomendo não por ora — §4).
2. **Cobertura do corte**: só laboratorial+imagem, ou métodos diagnósticos
   amplos? (recomendo: diagnósticos amplos no CSV; a UI filra por busca).

---

*Lavrado pelo arquiteto em 29/08/2026, com verificação in-loco: modelo
(`pedido_exame_item.py:25-26`), faturamento por TUSS/SIGTAP (Ticket D,
`clinicas.py`), catálogo curado (`tuss_base.py` — ~35 itens, promessa de v2 no
próprio docstring) e ausência de fonte SIGTAP oficial no backend.*
