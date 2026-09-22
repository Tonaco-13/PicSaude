# DESPACHO-ENG-021 — Registro no repo (PR docs) + staging do PCDT de anemia ferropriva (P-10)

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 22/09/2026 — martelos do Fabiano: *"mergeados. Morte ao Zumbi. Docs aprovados. P-10 aprovado. Mensagem ao engenheiro."* |
| **Entrega** | **2 PRs pequenas** (uma `docs`, uma `ops`), sem código de app |
| **Contexto** | #269 (`d2f3803`) e #270 (`b18b176`) MERGEADOS e verificados 22/09 13:00Z; zumbi `automation-b49a5414` deletado; deploy do #270 verificado ao vivo pelo arquiteto (palco creme, serif na folha, papel com borda/sombra, gov.br fora — 13 ocorrências restantes são comentários, renderizador de dado emitido e URLs do ITI; plural no ar) |

---

## PR 1 — `docs`: o registro da curadoria entra no repo (aprovado pelo Fabiano)

**21 arquivos não rastreados em `docs/tickets/` + o `FILA-VIVA.md` modificado.**
Lista exata (verifique com `git status docs/tickets/`):

- **12 rascunhos da pilha**: `RASCUNHO-{E78,F17,R52,M81,G40,L20,A30,G30,IST,L40,G20,E28}-DUPLO-PCDT-2026.md`
- **Manuais das sessões**: `SESSAO-2026-09-14-18-INTENSIVO-PCDT.md` (com o diário da
  sessão-hospedeira de 21/09) · `SESSAO-2026-09-21-25-INTENSIVO-PCDT.md` (semana em
  curso) · `SESSAO-2026-09-05-06-AGENDA-WEEKEND.md` (straggler de 05–06/09)
- **Plano-mestre**: `PLANO-CURADORIA-PCDT-AUTOMATICA.md`
- **Pareceres**: `PARECER-KIMI-RECEITA-VIVA-USO-REAL-2026-09-21.md` (o dela) ·
  `PARECER-ARQ-RECEITA-VIVA-POS-KIMI-2026-09-21.md` (o meu)
- **Despacho**: `DESPACHO-KIMI3-008-AVALIACAO-RECEITA-VIVA.md`
- **Stragglers antigos, de propósito** (registro viaja em PR — a lição das 5 perdas):
  `DESENHO-TESTE-EXTENSAO-PJ324.md` (parqueado, entra como está) ·
  `DESPACHO-COPY-ATRIBUICAO-INSTITUCIONAL.md` (da era #255)
- **`FILA-VIVA.md`** com as seções reconstituídas de 20–22/09

**Fora do commit (decisão em pé da #270):** `conceitos-prescritor/` inteiro —
referência visual local com fontes e imagem próprias (as evidências
`capturas-producao/0{1,2}-*.png` citadas nos pareceres moram lá; permanecem
referência local).

**Nota de limpeza:** depois que esta PR pousar e o FILA-VIVA do repo for conferido,
o stash `eng018-autostash` (cópia pré-#268 do FILA-VIVA) está supersedido — pode ser
dropado com registro no corpo da PR.

## PR 2 — `ops`: staging do PCDT de anemia ferropriva (P-10 aprovado)

**O que:** o catálogo aberto 08/2025 lista *"Anemia por deficiência de ferro" —
Aprovado\**, mas o PDF **não está no corpus** (varredura da R2 do intensivo — só há
ferro-na-IRC, hemolítica e sobrecarga). Baixar da página oficial de PCDTs do MS
(gov.br/saude, família `/midias/protocolos/` se disponível) e estagiar.

**Rito (a régua da onda das bases):**
1. **Importação offline versionada, nunca ao vivo** — o PDF entra em disco, o repo
   registra a âncora.
2. **`data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/SHA256SUMS.txt` NÃO é
   reescrito** (é a âncora do batch 30/08); o novo PDF ganha **entrada individual
   no `MANIFEST.md`** com sha256, data de staging e procedência (seção nova tipo
   "adendos pós-batch" — mesmo padrão do MANIFEST de diretrizes).
3. O PDF em si **não é versionado** (deny-by-default do `.gitignore` de
   `fontes-oficiais` — o `git add` de um `.pdf` deve FALHAR; essa falha é a guarda).
4. PR pequena `ops`/curadoria-infra: só o MANIFEST (+ relato de uma linha no corpo:
   fonte, data, tamanho, sha256).

**Por que importa:** com o PDF estagiado, a condição vira rascunhável — o
intensivo (R3 qui ou R4) lavra o RASCUNHO-D50 no padrão E11/J45, e a anemia
ferropriva (prevalência APS altíssima) entra na pilha da caneta.

## Rito geral

2 PRs, classes separadas (`docs` e `ops`), nenhum código de app, CI
`gates`+`smokes` verde por tabela (nada executa). Corpo de cada PR com o martelo
do Fabiano citado (verbatim acima). Merge com RATIFICADO do arquiteto + martelo —
nestas duas, sendo registro puro, o RATIFICADO pode vir da conferência do diff
(quick review).

---

*Lavrado em 22/09/2026. O registro da semana inteira — 12 rascunhos, dois manuais,
um plano, dois pareceres — para de morar em árvore não commitada (ritual #2, nunca
mais). E a despensa ganha o ferro que faltava.*
