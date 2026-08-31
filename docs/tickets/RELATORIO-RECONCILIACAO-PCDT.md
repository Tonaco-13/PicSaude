# RELATORIO-RECONCILIACAO-PCDT — catálogo × corpus × portarias (30/08/2026)

| Campo | Valor |
|---|---|
| **Executor** | Arquiteto (Z), em sessão — o cron de 09:00 não materializou; assumido às 10:11 |
| **Corpus** | `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/` — 240 PDFs, 373 MB, 0 falhas |
| **Âncora** | sha256 do `SHA256SUMS.txt` (240 entradas): `f358ea7d05d90f9c…95544f3d` (completo no MANIFEST) |
| **Fonte** | Página oficial CONITEC de PCDT (raspada em 30/08; HTML de 703 KB estagiado em `/tmp` da sessão) |

---

## §1 O corpus

240 PDFs da família `/midias/protocolos/` — livros completos, versões
resumidas e portarias. Duas vagas de download (191 + 49), pausa de 2s,
validação por magic bytes (`%PDF`), zero falhas, host cooperativo do início ao
fim (nunca houve rate limit).

## §2 Reconciliação catálogo (13/08/2025) × corpus (30/08/2026)

Matching por nome normalizado (sem acentos/pontuação), substring dos 10
primeiros caracteres do nome da condição contra o nome de arquivo. Método
**grosseiro por declaração** — os números abaixo são limite INFERIOR de
cobertura (falso-negativo existe; falso-positivo não).

| Status no catálogo | Condições | c/ PDF no corpus |
|---|---|---|
| Aprovado\* | 28 | **19** |
| Conitec | 6 | **6** |
| Em atualização | 36 | **22** |
| Em elaboração | 13 | **5** |
| **Total** | **83** | **52** |

**Dos 31 "sem PDF":** pelo menos um é artefato de grafia, não lacuna —
"Diabetes Insípido" está no corpus como `pcdt-diabete-insipido` (a CONITEC
grafia "diabete", o catálogo "diabetes"). O matcher por nome de arquivo é a
ferramenta errada para os casos-limite; **a extração da camada 1 (leitura dos
próprios PDFs) resolve a reconciliação de verdade** — nomes de arquivo são
display, conteúdo é que é fato (a mesma lição do `pedido_item_id` do laudo).

## §3 A corda de frescor acendeu: o catálogo está OFICIALMENTE atrás da página

O catálogo aberto (snapshot 08/2025) diz "Em atualização" para condições cujos
**documentos 2026 já estão publicados** na página. Achados do delta (49 PDFs
que só existem sob URLs **sem extensão `.pdf`** — onde a CONITEC publica o
mais novo):

- **PCDT da Asma 2026** (`pcdt-da-asma`) — J45, o nº 2 da fila do vagão
- **DM2 tipo 2 completo 2026** (`pcdt-diabete-melito-tipo-2`) — o canônico do
  rascunho E11 (já estagiado individualmente em 28/08; agora no corpus)
- **Resumidos 2026**: HAS (`pcdt-resumido-da-hipertensao-arterial-sistemica`),
  cólon/reto, dermatite atópica, artrite reumatoide, artrite psoriásica,
  acidentes ofídicos, miopatias inflamatórias, sobrecarga de ferro
- **Portarias ago/2026**: Crohn (no 51, de 19/08), endometriose (conjunta no
  54, 19/08), trombocitopenia (conjunta no 41)

Consequência prática: **a fila do vagão pode assinar E11 e J45 sobre fontes
2026** — não é preciso esperar atualização do catálogo para nada.

## §4 Lições da execução (registro honesto)

1. **`@@display-file/file` é obrigatório.** Sem o sufixo, o Plone devolve a
   página-visualização em HTML com HTTP 200 — minha primeira extração colheu
   191 "PDFs" de mentira (40 MB de HTML). A validação por magic bytes era
   CORRETA e foi o que denunciou o defeito; o bug era a extração, não o check.
2. **URLs sem extensão escondem o mais novo.** O regex que exigia `.pdf`
   perdia exatamente a safra 2026 (49 arquivos, incluindo Asma e DM2-2026).
3. **Uma URL do delta colidiu em nome de arquivo** (49 baixados de 50
   listados) — dedupe por `basename`, sem perda de conteúdo distinto.
4. **O cron de 09:00 não disparou** (runCount 0 às 10:11, sem artefatos);
   trabalho assumido em sessão e cron removido para não colidir.
5. **Escopo**: só a família `protocolos/`. As famílias `legislacao/`, `pdf/` e
   `consultas/` ficaram de fora por decisão (legislação avulsa e relatórios de
   consulta) — registrada como decisão, não como lacuna.

## §5 Próximos passos

- **Camada 1 (extrator, slot `ops` do engenheiro)**: ler os Quadros dos PDFs
  do corpus → pré-tabela rascunho `pcdt×cid×princípio×posologia×linha×citação`.
  A reconciliação fina (§2) nasce daí, não de nomes de arquivo.
- **Curadoria E11**: rascunho pronto (`RASCUNHO-E11-DUPLO-PCDT-2026.md`),
  aguardando assinatura do Fabiano. J45 (Asma) tem agora fonte 2026 no corpus.

---

*Lavrado pelo arquiteto em 30/08/2026, com download, hashes e reconciliação
executados por conta própria. Reproduzível pelos URLs do MANIFEST + âncora
sha256 do SHA256SUMS.txt.*
