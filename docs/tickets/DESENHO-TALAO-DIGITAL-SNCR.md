# Desenho — Talão Digital SNCR: nosso lado da ponte com a ANVISA

| Campo | Valor |
|---|---|
| **Origem** | Fabiano, 28/08: *"criar o nosso lado da ponte para API com ANVISA — pensei em termos um simulador da máquina deles para numerar as receitas, como era com os talões de receita azul e amarela"*. Parecer do arquiteto → martelo *"desenrolamos isso agora"* |
| **Autor** | Arquiteto (Z) — desenho, **não implementação** |
| **Classes** | G1 `adapter` (importação de base) · G2 `module` **+ uma peça `core`-flaggada** (extensão de interface SNCR) · G3 `module` (telas/PDF) · G4 🅿️ parqueado (piloto) |
| **Estado** | G1 Opção 2 (mecânica) implementada — migração + carimbo gated + importador, contra as 56 atuais, carimbo PENDENTE por design (AC1-4 ✅, AC5 aguarda a fonte real — §1.1). G2/G3/G4 seguem não iniciados |
| **Relacionados** | `app/adapters/sncr_interface.py` · `sncr_stub.py` · `sncr_factory.py` (Ticket 16A) · `TICKET-R4-ESCRITURACAO-REGULATORIA` (✅ implementado) · `DESPACHO-OPS-SEED-CATALOGO-DCB` · `TICKET-G4A` · fila "Simulador RDC 1.000" no `FILA-VIVA.md` |

---

## §0 O que JÁ existe — a ponte está em pé do nosso lado

Verificado no código (28/08). A descoberta que reframa o pedido: **não é greenfield**.

| Peça | Onde | Estado |
|---|---|---|
| Contrato SNCR (requisitar/verificar/registrar/health) | `sncr_interface.py` (Ticket 16A) | ✅ ABC + DTOs + vocabulário de erros |
| A metáfora do talão, já codificada | `NumeracaoSNCR`: `prescritor_cpf` + **`lote_id`** + `valida_ate`; docstring: RDC 1.000/2025 exige *"numeração individualizada previamente concedida"* | ✅ o lote É o talonário |
| Simulador | `sncr_stub.py` — numeração `STUB-` prefixada; status `numerado_stub`; log `[SNCR-STUB]` | ✅ operacional |
| Fábrica sem fallback silencioso | `sncr_factory.py` (`SNCR_ADAPTER`; produção = `real`, sem queda para stub) | ✅ |
| Fiação | `receituarios.py:36,110,322-363` — `requer_sncr`, `numeracao_sncr`, caminhos `nao_requer_sncr` / `requer_sncr_retencao_provisorio` | ✅ |
| Motor + escrituração versionada | `motor_regulatorio.py` (`GRUPOS_REGULATORIOS`, `MOTOR_REGULATORIO_VERSAO`) + R4: snapshot do grupo na dispensação | ✅ |
| Base de classificação | `catalogo_substancias` — **56 DCBs curadas à mão** | ⚠️ **parcial — a lacuna real (G1)** |

**Guarda de honestidade tripla do stub (intocável):** prefixo `STUB-`, status
`numerado_stub` (nunca "numerado"), sem fallback silencioso da fábrica. O simulador
**nunca finge ser oficial** — é o que permite demonstrar a ponte sem mentir.

## §1 G1 — a base regulatória completa (`adapter`)

**O problema:** com catálogo parcial, `validar_classificacao` segue o **princípio da
cautela** — substância ausente devolve silêncio (`coerente=True`, sem alerta; documentado
no DESPACHO-OPS-SEED-CATALOGO-DCB §1). A classificação **automática** só é confiável
quando a base é completa.

**O movimento:** importar as **listas de substâncias controladas da RDC 1.000/2025**
(anexos da norma, publicação oficial) como **snapshot versionado** — a mesma disciplina
da onda das bases (CID/SIGTAP/CBO): ferramenta offline, nunca consulta ao vivo,
`fonte`/`versão`/`data` declarados no próprio dado.

**A inversão semântica (o coração do G1):** base completa + carimbada **inverte o
princípio da cautela** — ausência deixa de ser silêncio e vira **afirmação negativa
confiável**: *"não-controlado, sob a versão V da lista"*. A afirmação negativa só vale
enquanto carimbada; sem o carimbo de versão, volta a valer o silêncio.

### §1.1 Estado da fonte (28/08 — caça do arquiteto + muro do engenheiro)

**Errata de proveniência deste desenho:** a RDC 1.000/2025 (de 11/12/2025, vigor
13/02/2026) é a norma do **receituário eletrônico/SNCR** — ela NÃO contém as listas de
substâncias. As listas são o **Anexo I da Portaria SVS/MS 344/1998**, mantidas por
cadeia de ~90 RDCs de emenda até a **RDC 1.036/2026** (última, jul/2026); a RDC
970/2025 foi atualização ampla recente. O carimbo deve citar esta cadeia, não
"anexos da RDC 1.000".

**O muro do engenheiro é real e confirmado:** (a) ferramenta de busca resume em vez de
enumerar — inútil para lista carimbável; (b) a página oficial
(`lista-substancias`, gov.br) é o **histórico de emendas**, não uma lista consolidada
baixável; (c) o **Anvisa Legis** tem o texto consolidado com notas de alteração, mas a
rota de impressão (`acao=imprimirAto`) exige sessão interativa de navegador — curl
sem sessão devolve vazio (testado).

**Artefatos oficiais já garantidos (staging, não commitados):**
`data/fontes-oficiais/anvisa-controlados-2026-08-28/`
— 22 PDFs oficiais do histórico de emendas + índice HTML da página + `MANIFEST.md`
com sha256 e identificação de cada arquivo.

**Despacho do arquiteto sobre as opções do engenheiro:**
1. **Opção 2 (mecânica agora) — APROVADA, incondicional.** Migração com
   `versão`/`data_snapshot`, modo completo do `validar_classificacao`, importador,
   testes — contra as 56 atuais, com o **carimbo explicitamente pendente**. O desenho
   já prevê exatamente isto: sem carimbo, silêncio (a inversão é gated by design).
2. **Opção 1 (você traz a fonte) — É O CAMINHO DO DADO, com pedido preciso:**
   abrir no navegador a Portaria 344/98 no Anvisa Legis (link na
   `indice-lista-substancias.html`), usar **IMPRIMIR → salvar PDF** (é o texto
   consolidado com o Anexo I vigente) e depositar em
   `data/fontes-oficiais/anvisa-controlados-2026-08-28/`. Gesto de minutos, único
   passo que exige humano — a rota programática está fechada por sessão.
3. **Opção 3 (fatiar buscas pequenas) — REJEITADA.** Lista parcial montada por busca
   é exatamente o "close enough" que o carimbo proíbe; e sem carimbo ela não adiciona
   nada às 56 curadas que já existem.

**ACs:**
1. ✅ Importador offline versionado (classe `adapter`; nada em runtime/deploy consulta
   externo — R4).
2. ✅ Toda entrada com classe/retenção + `fonte` + `versão` + `data_snapshot`.
3. ✅ `validar_classificacao` ganha o modo completo: com base carimbada, ausência =
   `"não_controlado"` **informado com versão**; sem carimbo, silêncio como hoje.
4. ✅ Vermelho-antes-de-verde: base sem carimbo NÃO afirma não-controlado.
5. ⏳ **PENDENTE** — as 56 curadas atuais migram/reconciliam contra a lista oficial
   (divergências relatadas, não silenciosas). Não há o que reconciliar contra uma
   fonte que ainda não chegou (§1.1); fica para a primeira vez que o importador
   rodar com dado real.

### §1.2 Implementação da Opção 2 (28/08 — mecânica, carimbo pendente)

- **Migração `2fb9182a0846`**: `catalogo_substancias` ganha `versao`/`data_snapshot`
  (nullable — as 56 curadas ficam NULL, honestas sobre não terem citação pontual).
  Tabela nova `catalogo_regulatorio_carimbo`, linha única (id=1), nasce com tudo
  NULL. Testada nos dois dialetos (SQLite + PostgreSQL efêmero), upgrade e
  downgrade limpos.
- **`CarimboRegulatorio` + `buscar_carimbo_ativo(conn)`** (`catalogo_regulatorio.py`)
  — lê a linha única; `versao IS NULL` devolve `None` (nunca um carimbo com campos
  vazios).
- **`validar_classificacao` ganha `carimbo: Optional[CarimboRegulatorio] = None`** —
  parâmetro opcional, backward-compatible (o único caller de produção,
  `validar_itens_prescricao`, já busca o carimbo uma vez por lote e passa adiante;
  hoje é sempre `None`, então o comportamento não mudou uma linha). Substância
  ausente + carimbo presente → `ResultadoValidacaoCatalogo.afirmacao_nao_controlado`
  populado, citando fonte/versão/data. Sem carimbo, campo fica `None` — o
  princípio da cautela de sempre.
- **`aplicar_snapshot_carimbado`/`aplicar_carimbo`/`limpar_carimbo`**
  (`catalogo_seed.py`) — o caminho de escrita, reusa o `_upsert` do seed curado
  (agora aceita `versao`/`data_snapshot` opcionais) em vez de duplicá-lo.
- **`backend/scripts/importar_snapshot_rdc_substancias.py`** — importador real,
  ainda SEM dado: lê um JSON (formato documentado no próprio script), valida
  (fonte/versão/data obrigatórios, toda entrada com classe OU retenção, DCB não
  duplicada) e aplica. Roda com `--arquivo <path>`; sem o arquivo, aborta
  claramente — não há fallback silencioso.
- **Vermelho-antes-de-verde, ao vivo**: gate de `validar_classificacao` sabotado
  (ignorando o parâmetro `carimbo`) → o teste que prova "sem carimbo, silêncio"
  quebra imediatamente (crash ao acessar `carimbo.fonte` com `carimbo=None`).
  Restaurado, verde.
- **Por que a fonte real não chegou nesta PR**: pesquisa web se mostrou inviável
  para enumerar ~500+ substâncias com a fidelidade que um carimbo exige — a
  ferramenta de busca RESUME listas grandes em vez de enumerar (mesmo limite já
  documentado no §1.1). O caminho segue sendo o gesto do Fabiano (Anvisa Legis,
  IMPRIMIR → salvar) + transcrição para o formato do importador.

## §2 G2 — o talão como modo de uso (`module` + peça `core`-flaggada)

Hoje o stub numera **por emissão** (pede na hora). O modelo do talão é o da norma e o
mais resiliente: o prescritor **adquire um lote** (talonário digital, por tipo —
`notificacao_receita_a` amarelo / `notificacao_receita_b` azul), e a emissão **consome o
próximo número do lote dele** — zero dependência externa no caminho clínico (a lição do
fire-and-forget do fluxo físico, aplicada à numeração; Regra Zero preservada).

- **Adquirir lote**: por prescritor × tipo, com série `[início..fim]` e `valida_ate`
  (o DTO já nasceu com `lote_id` opcional — a norma prevê concessão prévia).
- **Consumir**: `requisitar` passa a sacar do lote ativo do par (prescritor, tipo);
  sem lote, mantém o comportamento atual (numeração sob demanda) — retrocompatível.
- **Store próprio do adapter**: tabela própria (lotes + consumo), **sem FK clínica**,
  migração própria — o adapter nunca escreve em tabela clínica (§10).
- **Emissão nunca bloqueia**: stub é local; no modo `real` futuro (Ticket 16B), a
  política de bloqueio é decisão daquele ticket, não desta.

> ⚠️ **Peça `core`-flaggada:** a operação `adquirir_lote` é **extensão da interface
> SNCR** — e o próprio `sncr_interface.py` declara: *"a interface deve permanecer
> ESTÁVEL: mudanças aqui são `core` e exigem revisão central"*. Esta peça passa pela
> revisão central antes de mergear. O resto do G2 (stub, store, consumo) é `module`.

**ACs (além dos do store e da retrocompat):**
1. Prescritor com lote ativo emite controlado → número sai do lote, sequencial,
   `STUB-` prefixado, status `numerado_stub`.
2. Lote esgotado → repor é gesto explícito (novo lote); emissão sem lote segue o
   caminho atual — nada quebra no meio.
3. Guarda de concorrência: dois receituários simultâneos não sacam o mesmo número.
4. `valida_ate` vencido → lote não saca mais (afirma, não silencia).

## §3 G3 — a cara do talão na vitrine (`module`)

O que o Fabiano quer **ver**:
- Painel "Talões" no prescritor: amarelo (A) e azul (B), lotes ativos com
  próximo número e consumo (o suficiente para a demo contar a história).
- A numeração impressa na receita (PDF/canônico) com o **selo honesto de stub**.
- Leitura apenas — nenhum gesto clínico novo aqui.

**ACs:** browser test cobrindo a vista dos talões e a presença do número na receita
emitida de controlado.

## §4 G4 — o retorno (escrituração externa) — 🅿️ PARQUEADO

`RegistroUtilizacao` (o DTO já existe na interface) na dispensação, publicação via
G4A/outbox no formato que o SNCR/SNGCR um dia pedir. **Gatilho: piloto real com a
ANVISA.** Nada abre antes.

## §5 Fronteiras e guardas (resumo executável)

- Interface SNCR intocada **exceto** pela peça `core`-flaggada do §2 (revisão central).
- Honestidade tripla do stub intocável (prefixo, status, sem fallback).
- Adapter com store próprio; nunca escreve em tabela clínica; observável (health).
- Emissão nunca bloqueia por numeração.
- Demo ≠ piloto: numeração de vitrine é cenário; integração real é Ticket 16B
  (especificação SNCR seguir não-publicada quando do 16A — reconfirmar ao abrir).

## §6 Sequência

1. PR 2 do typeahead (base CBO) — **em voo**.
2. **Onda das bases**: CID-10 completo → SIGTAP-exames → **listas RDC 1.000 (este G1)**
   — mesma disciplina, fontes distintas; ticket próprio da onda ainda a desenhar.
3. G2 (com a peça `core` isolada em PR própria para a revisão central).
4. G3 na sequência. G4 parqueado.

**Martelos (Fabiano):** 28/08 — desenho aprovado ("desenrolamos isso agora") · G1 dobra
para a onda das bases · **sem segunda automação**: a vigília existente vigia os PRs
contra este desenho.

---

*Desenho do arquiteto, 2026-08-28; §1.2 (implementação da Opção 2) em 2026-08-28.
Âncoras verificadas: `sncr_interface.py` (docstring RDC 1.000/2025 + DTOs) ·
`sncr_stub.py` (guardas) · `sncr_factory.py` · `receituarios.py:36,110,322-363` ·
`motor_regulatorio.py` · TICKET-R4 (✅) · DESPACHO-OPS-SEED-CATALOGO-DCB §1
(princípio da cautela) · migração `2fb9182a0846` · `catalogo_regulatorio.py`
(`CarimboRegulatorio`, `buscar_carimbo_ativo`) · `catalogo_seed.py`
(`aplicar_snapshot_carimbado`) · `backend/scripts/importar_snapshot_rdc_substancias.py`.
Implementação é do engenheiro; a peça `core` do §2 passa por revisão central.*
