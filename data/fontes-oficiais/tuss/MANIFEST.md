# Manifesto — TUSS / Padrão TISS (commitado; binário fica local)

ENG-027 §2. `data/fontes-oficiais/.gitignore` (idiom `*` + `!*/` +
`!*/MANIFEST.md`) faz o ZIP desta pasta ficar local, fora do git — só este
manifesto commita: sha256 + URL oficial, para reprodutibilidade sem carregar
o binário no repo.

**Por que esta pasta existe:** até 28/09/2026 os códigos TUSS da casa eram
~38 valores digitados à mão em `backend/app/ai/tuss_base.py`, **sem fonte**.
Era a única das bases sem procedência — CID-10, SIGTAP, RENAME, CBO, RDC e
PCDT já tinham a sua. Esta pasta fecha a lacuna.

## padraotiss_mapeamento_tuss_sigtap.zip
- sha256: `b365e36dbace8fea6f2984e69a26c0fbfeed801bca1b6a13f0a8520e8c84662a`
- Tamanho: 1.128.658 bytes · Baixado pelo engenheiro em **28/09/2026**
- **Fonte OFICIAL** (não é espelho): `https://www.gov.br/ans/pt-br/arquivos/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-tiss/padrao-tiss-tabelas-relacionadas/padraotiss_mapeamento_tuss_sigtap.zip`
- Página-fonte: `https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss/padrao-tiss-tabelas-relacionadas`
  (seção "Padrão TISS – Tabelas Relacionadas", link *"Compatibilização entre
  TUSS x SIGTAP"*)
- Validação: `file` confirma "Zip archive data"; 1 arquivo interno,
  `MAPEAMENTO TUSS x SIGTAP  2017 04.xlsx` (1.235.965 bytes, 5 abas).

### O que veio dentro — e por que resolve DUAS coisas

| Aba | Linhas | Serve para |
|---|---|---|
| `TUSS 22 201606` | 5.786 | **a Tabela 22 inteira** — código, termo e vigências. É a base oficial que faltava |
| `Mapeamento ativos` | 6.920 | **mapeamento TUSS→SIGTAP oficial**, com grau de equivalência declarado |
| `Tabela_Equivalência` | 5 | legenda dos graus 1–5 |
| `Situação das tabelas` | 10.322 | situação de mapeamento por código |
| `Metodologia` | — | o método, pela própria ANS |

O ticket previa casar TUSS e SIGTAP **por nome normalizado**. Não foi preciso:
o mapeamento oficial existe, tem grau declarado e é de autoria da ANS com o
MS. Heurística de nome ficaria atrás de fonte primária — e correria o risco
que a sabotagem da guarda persegue ("biopsia" ≈ "biopsia").

Legenda dos graus, verbatim da aba `Tabela_Equivalência`:

| Grau | Significado |
|---|---|
| 1 | Equivalência de significado, tanto léxico quanto conceitual. |
| 2 | Equivalência de significado, mas com sinonímia |
| 3 | TUSS (conceito fonte) tem significado menos específico que a SIGTAP (conceito alvo) |
| 4 | TUSS (conceito fonte) tem significado mais específico que a SIGTAP (conceito alvo) |
| 5 | Não é possível mapeamento. |

### ⚠️ IDADE DECLARADA — a régua da ITU 2003 e da AMB 2008

O pacote é de **abril de 2017** e a Tabela 22 que ele carrega é da competência
**201606**. É a fonte oficial mais completa que esta vantage alcançou, e a
idade entra **declarada no campo `fonte` de toda row** que dela sai, para que
ninguém a leia como corrente.

**Pendência de frescor (escrita, sem drama):** a ANS mantém a TUSS viva e
publica uma consulta on-line (`consulta-ocl.apps.sa-1a.mendixcloud.com/rest/
oclservice/ANS/concepts/tuss-22`, link declarado na página "Códigos da TUSS").
A API **não respondeu** a esta vantage em 28/09 (timeout de conexão em duas
tentativas, com e sem parâmetros). O portal `dados.gov.br` tem o conjunto
"Terminologia Unificada da Saúde Suplementar (TUSS)" mas a página é renderizada
por JS e a API pública devolveu **HTTP 401**. Quando uma extração mais nova
pousar, `backend/scripts/importar_snapshot_tuss.py` roda de novo e o
`versao_snapshot` muda junto — o script lê a competência do arquivo, nunca a
declara à mão.

### Derivados commitados

- `data/tuss_procedimentos.csv` — **5.755** procedimentos (Tabela 22)
- `data/tuss_sigtap_mapeamento.csv` — **4.270** pares TUSS↔SIGTAP

Gerados por `backend/scripts/importar_snapshot_tuss.py`, que roda **offline,
à mão** — a aplicação nunca o chama, exatamente como o import do SIGTAP.

### O que a conferência contra esta fonte revelou

**36 dos 38 códigos TUSS curados em `tuss_base.py` não existem na Tabela 22.**
Não são variantes de dígito verificador: os códigos certos são outros
(hemograma completo é `40304361`, não `40301079`). Medido e nomeado em
`docs/tickets/RELATORIO-TUSS-RECONCILIACAO.md`; **não corrigido** — trocar
código que vai para faturamento é caneta do Fabiano.
