# FILA-VIVA — o que não pode se perder

| Campo | Valor |
|---|---|
| **O que é** | Lista viva de pendências: bugs confirmados, decisões pendentes, backlog anotado |
| **Ordem geral** | Fases GP primeiro, bugs depois — martelo do Fabiano, 26/08 ("Vamos fazer as fases GP e depois voltamos aos bugs") |
| **Quem mantém** | Arquiteto (Z). Engenheiro retira daqui; item concluído ganha ✔️ e link do PR |
| **Criada** | 2026-08-27 |

> Regra da casa que este arquivo obedece: ticket descreve **sintoma**;
> hipótese de causa é marcada como hipótese até o diagnóstico fechar.

---

## A. Bugs confirmados na vitrine (executar pós-Go Public)

| # | Item | Classe | Status |
|---|---|---|---|
| A1 | "Enviar à bancada" morre em silêncio | `module` | ✔️ efeito-colateral (#207–#211) — não reproduz, ver abaixo |
| A2 | Disciplina de entrada numérica (ticket da Júlia) | `local-extension` | ✔️ PR #219 (`536b7fc`) |
| A3 | Pílula "Exames 0" na carteira com a aba cheia | `module` | ✔️ #221 (`e96b697`, 29/08) |

### A1 — "Enviar à bancada" morre em silêncio

**Sintoma** (walkthrough do arquiteto, 27/08, pedido `13f7f491`, item GLICEMIA):
na aba Bancada da clínica, item `coletado` com botão "Enviar à bancada"
habilitado; dois cliques sem efeito algum — sem diálogo, sem toast, sem mudança
de estado.

**Isolamento já feito:** o mesmo gesto pela API responde **200** e promove
`coletado → em_analise` corretamente. O backend está são; o defeito está no
caminho do clique na tela.

**Âncoras no código (27/08, HOJE MORTAS):** `clinica.html:452` / `:2799-2805` /
`:3324` — defasadas pela onda de circulação (#207–#211, que reorganizou as abas e
dissolveu a Realização).

**Diagnóstico FECHADO (arquiteto, 28/08, contra `origin/main` pós-#219):** o
caminho atual está **correto por leitura** — render do botão em `clinica.html:2931`
(`onclick="registrarBancada(${item.id})"` inline) e handler `registrarBancada`
(`:3597`) bem-formado: `prompt` de setor → fetch POST `/em-analise` → 401 tratado →
`!resp.ok` com alerta → sucesso atualiza UI e **recarrega do backend** → catch com
alerta de rede. **Nenhum caminho silencioso existe no código atual.** Hipótese
revisada: o sintoma de 27/08 morava no caminho **pré-redesenho** (a aba extinta);
a onda de circulação reescreveu render+handler — **provável conserto como efeito
colateral**.

**Fechado (fila 5-bis, engenheiro, 29/08) — NÃO REPRODUZ.** `test_bancada_
clinica.py` (TICKET-F, já existente, pré-datava esta rodada) cobre exatamente
o gesto do sintoma: item `coletado` → clique em "Enviar à bancada" → dialog
de setor aceito → `expect(item).to_contain_text("Em Análise")` (atualização
em tela SEM `page.reload()` explícito no teste — a promessa de "recarrega do
backend" do diagnóstico do arquiteto se confirma) → backend concorda
(`status_item == "em_analise"`, evento `pedido_em_analise` no ledger). 3/3
testes verdes (`test_enviar_a_bancada_muda_o_item_na_tela_e_no_ledger`,
`test_cancelar_o_prompt_de_setor_nao_envia_nada`,
`test_pedido_na_bancada_continua_na_fila_do_laboratorio`). Confirma a
hipótese: o sintoma de 27/08 morava no caminho pré-redesenho (aba extinta);
a onda de circulação (#207–#211) já resolveu de carona. Arquivado — nenhuma
PR necessária.

**Nota de higiene da vitrine:** no walkthrough, o item 23 foi movido a
`em_analise` por chamada API do arquiteto — estado legítimo; HEMOGRAMA segue
`pendente`. Não é defeito, é resíduo do teste.

### A2 — Disciplina de entrada numérica (ticket da Júlia)

**Sintoma** (nota de Júlia, estudante, 26/08): campos numéricos dos
formulários — Idade, CPF, CEP — aceitam letras; o erro só aparece no submit
(422). Backend é fail-closed (normaliza e rejeita): defeito de higiene de
entrada, não de integridade — nada sujo persiste.

**Solução cirúrgica, só frontend:** `inputmode="numeric"` + bloqueio de
não-dígitos + máscara ao digitar (CPF `000.000.000-00`, CEP `00000-000`) +
validação antes do submit. Zero mudança em API, estados, ledger.

**Guarda mínima:** um teste de browser digitando letras e afirmando que elas
não entram.

### A3 — Pílula "Exames 0" na carteira com a aba cheia

**Sintoma** (walkthrough, 27/08): a pílula de Exames da carteira exibe **0**
com a aba de exames cheia de pedidos.

**Hipótese original — DESCARTADA por leitura (29/08):** "contador lê bucket
diferente do que a aba lista". Falso: `_contagemCarteira.pedidos =
ativos.length` e `renderizarPedidosExame(ativos)` (`cidadao.html`) usam o
MESMO array `ativos`, na MESMA função (`carregarPedidosExame`) — não há dois
buckets para divergir.

**Diagnóstico real, provado (engenheiro, 29/08) — DOIS bugs empilhados:**

1. **Placeholder `0` indistinguível de "carregando".** `_SUBMODULOS_CARTEIRA`
   (config estática da barra) e `_contagemCarteira` (estado runtime)
   nasciam com `contador: 0` / `pedidos: 0` etc. — um valor que É um
   resultado válido real, não "ainda não sei". `_sincronizarContadoresCarteira()`
   repinta as SEIS pílulas toda vez que QUALQUER UM dos seis loaders
   (receita/exames/laudos/atestados/agendamentos/encaminhamentos, que correm
   em paralelo) termina — então o loader mais rápido pinta "0" nas pílulas
   dos loaders ainda em voo, inclusive Exames.
2. **Bug de especificidade CSS — mesma família do `.tac-painel[hidden]`
   (#216).** Corrigido o bug 1 (pílula nasce com `contador: null` →
   `submodulos.js` marca `hidden`), a pílula continuava VISUALMENTE visível:
   `.submod-contador { display: inline-flex; }` tem a MESMA especificidade
   que `[hidden] { display: none }` da UA stylesheet e carrega DEPOIS —
   vence, e o atributo `hidden` vira decoração morta no HTML.

**Prova, com rede deliberadamente atrasada** (`page.route`, sem race contra
localhost): a pílula nasce com o `<span>` presente e `hidden=""`, e só
aparece — com o valor real, nunca `0` — depois que o fetch (atrasado de
propósito) resolve. Vermelho-antes-do-verde confirmado nos dois bugs
isoladamente (removendo cada fix, o teste falha de forma diferente:
sem o 1, mostra `0` cedo; sem o 2, mostra `hidden=""` mas visualmente
visível).

**Fix:** `contador: 0` → `contador: null` em `_SUBMODULOS_CARTEIRA` e nos
seis campos de `_contagemCarteira` (`cidadao.html`); `submodulos.js::render()`
marca `hidden` quando `contador === null`; `submodulos.css` ganha
`.submod-contador[hidden] { display: none; }`. `Submodulos.contador()` já
sabia desesconder — não mudou. Zero mudança em API/estados/ledger.

Guarda: `backend/tests/browser/test_a3_pilula_exames_sem_flash_zero.py`.

---

## B. Decisões que travam o Go Public (só o Fabiano decide)

| # | Decisão | Recomendação do arquiteto |
|---|---|---|
| B1 | **§3 do GP-3** — CNS de aparência real no seed (único indistinguível de real) | Substituir por sintético |
| B2 | **§4 do GP-3** — histórico COMO × O QUE (o que vai a público no git) | Intermediário: técnico completo, menos docs de gestão |

Fonte: `GP3-AUDITORIA-SEGREDOS-PII-2026-08-26.md` (GP-3 entregue — zero
segredos reais em 85 refs / 507 commits / 3.105 blobs).

**Depois de B2:** GP-2 (curadoria da fachada) → **flip**. GP-1 já entregue (#199).

---

## C. Backlog anotado (sem data, sem dono)

- ✔️ **Remarcação de encaminhamento** — já entregue ANTES da criação deste arquivo:
  PR **#194** (`e3ea403`, 24/08) — re-ato de agendar, sem estado/aresta/evento novo,
  teste dedicado (entrada estava desatualizada; corrigida 28/08 a pedido do
  "fila 4" do Fabiano)

### C.0 Fila do engenheiro — o referente do "fila N" (criada 28/08 para matar a deriva)

> O Fabiano comanda o engenheiro por "fila N"; este bloco é onde o número ganha
> nome. Mantido pelo arquiteto; ordem pode ser trocada por martelo.

| Fila | Item | Estado |
|---|---|---|
| 3 | A2 — entrada numérica | ✔️ #219 (`536b7fc`) |
| 4 | **Strip de dose no `canon_ativo`** (`TICKET-CANON-ATIVO-DOSE-SUFFIX`) — slot reservado no vagão §8 ("logo após a PR 2 do typeahead" — momento chegou); destrava o flip E11 | ✔️ **#220** (`6dcbc19`, squash — martelo do Fabiano 29/08); errata do ticket commitada em `adad1ae` |
| 5 | A3 — pílula "Exames 0" na carteira (diagnosticar + corrigir) | ✔️ **#221** (`e96b697`, squash — martelo do Fabiano 29/08) |
| 5-bis | **Carona (10 min):** verificação browser do A1 (diagnóstico fechado acima) | ✔️ não reproduz — `test_bancada_clinica.py` 3/3 verde, efeito-colateral #207–#211 |
| 6 | CID-10 completo (onda das bases) — desenho 29/08 (`TICKET-FILA-6-CID10-COMPLETO.md`); execução achou beco real (§6): sem fonte oficial baixável pós-2008. **Martelo do Fabiano 29/08 ("martelado e despachado"): opção 1 refinada** — teto acessível (V2008+remendos declarados, manifest sha256, remendos re-citados no PDF oficial MS, gap medido por espelho sem importar), gatilhos de reabertura no §6 | ✔️ **#222** (`754b5ac`, squash — martelo do Fabiano 29/08). Ticket fecha como TETO ACESSÍVEL. Verificação própria (vigília R3, 29/08 15:01): header com `versao_snapshot` (`V2008+remendos-2026`); importador sem nenhuma chamada de rede; guardas "não importado por app / não chamado por predeploy-Dockerfile"; RELATORIO-DIFF honesto (nenhum novo/removido/alterado); RNDS reproduz 303→auth; DATASUS não reproduzível do posto (parcial, registrado). Auditoria pós-CI achou defeito no `.gitignore` de `data/fontes-oficiais/` (`*/` excluía os próprios diretórios) — corrigido (`*` + `!*/`) e os dois manifestos (cid10, pcdt) commitados no mesmo squash |
| 7 | SIGTAP-exames (onda das bases) — desenho 29/08 (`TICKET-FILA-7-SIGTAP-EXAMES.md`): tabela oficial mensal DATASUS por competência + `sigtap_exames.csv` + typeahead que sugere e nunca bloqueia. **Ratificação pós-merge do arquiteto (29/08, auditada em `e69a3ab`):** fonte honesta nos 3 estados (fusão/só-TUSS/só-SIGTAP — guarda `test_match_so_sigtap_nao_afirma_tuss_base_local`), Regra Zero guardada (`test_nome_inedito_nao_bloqueia`), faturamento intocado, 58 testes re-rodados por conta própria. Errata do §4 lançada (mapeamento TUSS↔SIGTAP TEM canal oficial, vazio nesta competência). Nota de rito: merge ocorreu antes da auditoria final (a condição era CI + auditoria) — sem dano neste caso, registrado para o rito | ✔️ **#223** (`e69a3ab`, squash — martelo do Fabiano 29/08) |
| 8 | G2 talão digital (peça `core` em PR própria) → G3 talões na vitrine | desenho pronto |
- **Posologia diabetes / saúde mental** — pré-digitação ampliada (anotação do Fabiano,
  25/08). **Precisão do arquiteto (28/08):** o bulário NÃO é fonte da tabela de
  posologia — ela é dado clínico **curado e assinado** (`posologia_sugerida.csv`, mesma
  família do semáforo; cresce pela curadoria por condição, ritmo do vagão). Bulário,
  quando pousar, faz **ponte**: apoio à curadoria + tela de bula + tripwire de
  divergência — nunca fonte
- **"Treinar a IA do sinal"** — 🅿️ parqueado por martelo do Fabiano (28/08: "anote
  somente; vamos ver depois das bases"). Nota de direção com 4 trilhas no §7 do
  `VAGAO-CURADORIA-SEMAFORO.md` — inclui o achado de que a camada 3 já grava no ledger,
  na emissão, os tuplas (sinal × item emitido × versão de regra): a fundação de dados
  para um futuro modelo nasce capturada por desenho
- **Onda das bases de referência** — martelada 28/08 ("desenrolamos agora", desdobrando
  o "depois das bases"): **CID-10 completo → SIGTAP-exames → listas RDC 1.000/2025 (G1
  do talão digital)**; bulário e TUSS com gatilho declarado. Disciplina única:
  importação offline versionada, nunca ao vivo. Ticket próprio da onda a desenhar;
  consumo plug-and-play no typeahead agnóstico (#216). **G1 andou por fora da onda**
  (mecânica entregue via Opção 2, ver linha abaixo) — CID-10 completo e SIGTAP-exames
  seguem sem ticket, não iniciados
- 🟡 **Talão Digital SNCR (motor regulatório)** — martelado 28/08
  (`DESENHO-TALAO-DIGITAL-SNCR.md`, G1–G4). **G1 (Opção 2, mecânica) entregue**:
  migração `2fb9182a0846` (versao/data_snapshot + `catalogo_regulatorio_carimbo`),
  `validar_classificacao` com modo completo gated, `aplicar_snapshot_carimbado`,
  `backend/scripts/importar_snapshot_rdc_substancias.py` — tudo contra as 56 atuais,
  **carimbo explicitamente pendente** (AC5 aguarda a fonte real, §1.1/§1.2). Pesquisa
  web se mostrou inviável para as ~500+ substâncias do Anexo I completo — mesmo
  limite já documentado; segue dependendo do gesto do Fabiano (Anvisa Legis, PDF).
  **Ratificação do arquiteto (28/08)**: #218 verificado MERGED (`8711896`); o gate é
  real, não decorativo — `buscar_carimbo_ativo` devolve `None` no estado pendente
  (versão NULL nasce da migração) e `afirmacao_nao_controlado` só nasce com carimbo
  E ausência; colunas nullable; comportamento byte-idêntico até a fonte chegar,
  como o desenho mandava.
  G2 (modo lote/talão no stub) tem **peça `core`-flaggada** — extensão da interface
  SNCR exige revisão central; G3 (talões na vitrine) `module`; G4 (escrituração
  externa) **parqueado até piloto**. A ponte já existe (contrato+stub+fábrica+fiação,
  §0); guardas de honestidade tripla intocáveis
- ✔️ **Reset diário da vitrine** — **entregue completo**: PR #212 mergeado 27/08 (`8202f5a`); Blueprint **aplicado** por Fabiano na noite de 27/08; primeiro run automático **28/08 04:00 BRT com sucesso** (dashboard: "Successful run" — verde que, com a sentinela pós-seed, agora é prova, não silêncio)
- ✔️ **Higiene do campo de paciente — M-B → M-C → M-D (28/08)**: M-B (chips, #213,
  `b0ef413`) e M-C (padrão + atestado, #214, `8b714fa`) **REVOGADOS** pelo M-D —
  martelo direto do Fabiano ao engenheiro ("fixar, sem possibilidade de edição";
  o problema original ainda acontecia). M-D trava (readonly) os 4 campos no
  cidadão canônico, retira o quick-pick e os 2 cidadãos extras. Adendo §8 do
  `DESENHO-VITRINE-HIGIENE-VISITANTE.md`. Limite declarado: lock é só de
  frontend, backend não valida `nome_paciente`/`cpf_paciente` em DEMO_MODE.
- ✔️ **Typeahead unificado no encaminhamento — PR 1 + PR 2 completos**. PR 1
  (painel, `module`) — PR **#216** mergeado 28/08 (`98c100d`), ratificada pelo
  arquiteto. **PR 2 (base CBO, `adapter`)** — `especialidades` cresce de 15
  para 21 (as médicas + odontologia/enfermagem/fisioterapia/nutrição/
  fonoaudiologia/psicologia), cada uma com código+família,
  `backend/scripts/importar_snapshot_cbo_encaminhamento.py` como fonte única
  verificada. **Guarda-chave confirmada**: psicologia = CBO 2515, fora do
  subgrupo 22, presente na base (browser test "PSI → 2515"). **Achado na
  conferência**: 4 erros no rascunho da whitelist do §2 do desenho (2252 não
  é odontologia — é cirúrgicas; 2232 não é enfermagem — é odontologia;
  fisioterapia não é 2231 — é 2236; fonoaudiologia não é 2236 — é 2238) —
  detalhado no §7 do `DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md`, junto com um
  achado fora de escopo (mesmo tipo de erro na glosa do `CBO_PREFIXES` de
  `config.py:13`, valores intocados, só a legenda estava errada).
  **Ratificação do arquiteto (28/08)**: #217 verificado MERGED (`36072a0`);
  2515 conferido de forma independente contra fontes externas (MTE/Fiocruz —
  2235=Enfermeiros, 2232=Cirurgiões-dentistas); provenância lida do dado;
  `typeahead-catalogo.js` com diff **zero** contra a #216 — o AC "a troca de
  base não reabre o painel" provado em diff
- **CBEB v11** — conferir pontos A/B quando o Kimi voltar com a revisão (CBEB
  v12/v13 + Response R2 já pousaram, untracked, na raiz do repo — conferência
  pendente)
- 🟡 **Onda PCDT (montagem das bases)** — martelo 29/08: **importar, nunca
  ponte viva** (régua da onda das bases reafirmada). Desenho lavrado
  (`DESENHO-ONDA-PCDT.md`: corpus estagiado → extração assistida → curadoria
  assinada). Catálogo aberto do MS já estagiado com sha256
  (`data/fontes-oficiais/pcdt/aberto-2025-08-13/` — é ÍNDICE de 83 condições,
  sem CID/fármaco/portaria, e defasado vs portarias 2026; PDF é o canônico).
- ✅ **Onda PCDT — camada 0 (corpus) ENTREGUE 30/08** pelo arquiteto em sessão
  (cron de 09:00 não disparou; assumido às 10:11): **240 PDFs, 373 MB, 0
  falhas** da família `/midias/protocolos/` da CONITEC (duas vagas: 191 + 49;
  âncora sha256 do `SHA256SUMS.txt` no MANIFEST). Reconciliação:
  `RELATORIO-RECONCILIACAO-PCDT.md` — catálogo×corpus 52/83 diretos (matcher
  grosseiro, limite inferior); **catálogo 08/2025 confirmado defasado**: Asma
  2026, DM2-2026 completo, resumidos 2026 (incl. HAS) e portarias ago/2026 já
  estão na página. **E11 e J45 podem assinar sobre fonte 2026.** Lições da
  execução no §4 do relatório (`@@display-file` obrigatório; URLs sem
  extensão escondem o mais novo)
- ✅ **Onda PCDT — camada 1 (extrator) ENTREGUE 30/08** — ✔️ **#224**
  (`8a33eed`, squash — martelo do Fabiano 30/08). `extrair_snapshot_pcdt.py`
  lê offline os PDFs estagiados (nunca a rede); E11 por âncora de dicionário
  (`decisao_semaforo.csv`, read-only) no Quadro 15; J45 por bullets de
  "7.4.1. Esquemas de administração" (primeira leitura pura de máquina, sem
  levantura humana anterior). `status_curadoria` nasce e fica `rascunho`
  sempre; falhas de extração listadas em `RELATORIO-EXTRACAO-PCDT.md`, nunca
  escondidas. Auditoria do arquiteto (30/08, verificação própria: CI, CSVs
  byte-idênticos a `origin/main`, idempotência re-rodada, citação J45
  conferida no PDF) — **duas precisões registradas**: (1) a divergência do 8º
  item do elenco E11 se **inverteu** — o PDF diz literalmente "Insulina
  Humana Regular" (p.37/Quadro 15 p.39); era a extração que perdera o
  qualificador "humana", não o rascunho humano propondo rename. Lição de
  processo: nomear divergência máquina×humano pelo PDF como juiz, não supor
  a direção. Rascunho E11 emendado pelo arquiteto com a adjudicação +
  recomendação de rows-alias (as duas grafias, incl. o par NPH). Nenhuma
  mudança de código — a máquina flagrou corretamente, a cura é da curadoria.
  (2) coluna `linha` do E11 está pior do que o relatório descreve — carrega
  também o rabo da posologia da linha anterior, não só rótulo de classe;
  precisão do relatório fica para commit `docs` futuro, opcional. Ver
  [[pcdt-camada1-extrator-fechado]]
- 🟡 **Abertura pública (conceito) — ENTREGUE 30/08, aguardando o flip.**
  `conceitos-landing/`: duas lentes completas (domínio pelo arquiteto,
  engenharia pelo engenheiro — ambos os pareceres aplicados 1:1; relógio único
  implementado com `chegadas` DERIVADA da tabela `quadros`; contraste 4.96:1;
  320px renderizado de verdade). Errata do docstring de `publico.py:19`
  lavrada pelo arquiteto (item que ficou com a casa). **Decisão pendente só do
  Fabiano**: convivência com a fachada de serviço (portal some? vira
  `/entrar`?) — ele anunciou "vou disparar a mudança"; quando o flip
  acontecer, aplica a disciplina de paridade de imagem (lição dos assets 404)
