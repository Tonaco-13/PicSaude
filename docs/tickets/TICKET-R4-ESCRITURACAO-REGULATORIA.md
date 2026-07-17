# TICKET-R4-ESCRITURACAO-REGULATORIA — congelar a identidade regulatória na dispensação

| Campo | Valor |
|---|---|
| **Regra** | §2a **R4** — *"identificadores de vigilância externos são congelados no movimento por snapshot, no ato da DISPENSAÇÃO; nunca chamada externa ao vivo."* |
| **Alvo** | A **identidade regulatória do controlado** (classe de controle / retenção) — **não** o número de registro ANVISA do produto. |
| **Classe** | `module` (+ migração: duas colunas nullable em `dispensacoes`) |
| **Estado** | ✅ **Implementado** (esta fatia). Fundação: `motor_regulatorio.py` (Ticket 15). |

## Alvo: campo estruturado, não texto livre
A identidade regulatória é resolvida de **campos estruturados** do item —
`prescricao_itens.classe_controle` (A1, B1, C5…) e `tipo_retencao` — pelo motor
determinístico `grupo_regulatorio(...)`. **Sem fuzzy-match** com catálogo (o alvo
não é o registro ANVISA do produto). Isso torna o 2º par de olhos (Z AI) dispensável.

## O que congela (POR VALOR, no ato da dispensação)
No `POST /prescricoes/{proto}/itens/{item_id}/dispensar` (e no caminho hospitalar
`.../dispensar/hospitalar`), antes do `INSERT INTO dispensacoes`:

```python
grupo_regulatorio_id, motor_regulatorio_versao = escriturar_grupo_regulatorio(
    item["classe_controle"], item["tipo_retencao"],
)
```

- **`grupo_regulatorio_id`** — o `id_grupo` (slug estável): a identidade regulatória
  que escriturou o movimento.
- **`motor_regulatorio_versao`** — carimbo da versão do motor (`MOTOR_REGULATORIO_VERSAO`).
  Dá **R1 pleno**: se a RDC mudar a definição do grupo amanhã, o movimento passado
  guarda **sob qual versão de regra** foi escriturado.

> **Por valor, não FK/derivação ao vivo.** Re-resolver na leitura daria a resposta
> do motor de *hoje*; se a regra mudou, o período fechado mudaria (fere R1). O
> snapshot fixa o que valeu à saída do produto. Precedente: `lote`/`fabricante`.

## Decisões marteladas
- **NULL honesto para não-controlado.** `classe_controle` e `tipo_retencao` ambos
  vazios → grupo `receita_simples` → `(None, None)`. Relatório mostra vazio. **Nunca**
  inventa grupo.
- **`ValueError`/`RuntimeError` = falha alta, não NULL silencioso.** Item COM
  `classe_controle`/`tipo_retencao` preenchido que o motor não classifica → o helper
  propaga; o endpoint devolve **HTTP 422** (`codigo=classe_controle_inconsistente`).
  Nunca congela NULL para um controlado.
- **Snapshot na DISPENSAÇÃO, não na emissão** (regime vigente à saída do produto).
- **Nenhuma chamada externa** no caminho de escrita nem no relatório — motor local e puro.

## 🌉 Fronteira — só o NOSSO lado da ponte (sem API ANVISA/SNCR) — VINCULANTE
- As regras vivem em **código nosso** (`motor_regulatorio.py`), curadas das normas
  (Portaria 344/98, RDC 1.000/2025, RDC 471/2021) — nunca buscadas de sistema externo.
- **`requer_sncr` é FLAG derivada localmente**, não número obtido de sistema. Proibido
  gerar/obter/simular número SNCR real — adapter SNCR segue stub (§10 / G4A).
- Congelamos o que **nós** sabemos dizer do movimento (grupo + versão da regra), não
  o que dependeria de terceiro.

## Arquivos
| Arquivo | Mudança |
|---|---|
| `backend/app/domain/motor_regulatorio.py` | `MOTOR_REGULATORIO_VERSAO` + `escriturar_grupo_regulatorio()` |
| `backend/app/models/dispensacao.py` | colunas `grupo_regulatorio_id`, `motor_regulatorio_versao` |
| `backend/alembic/versions/e5f6a7b8c9d0_*.py` | migração dual-DB idempotente (nullable) |
| `backend/app/routers/custodia.py` | congela no `dispensar_item` |
| `backend/app/routers/hospitalares.py` | congela no `dispensar_hospitalar` |
| `backend/app/domain/relatorio_sngpc.py` | coluna `grupo_regulatorio_id` no CSV (bloco do medicamento) |
| `backend/app/routers/dispensadores.py` | projeta `d.grupo_regulatorio_id` (dispensação + estorno) |
| `backend/app/routers/dispensacoes.py` | bloco `escrituracao_regulatoria` no comprovante |
| `backend/seed_demo.py` | item controlado **B1** (CLONAZEPAM) na receita da fila |

## Aceite (verificado)
- Dispensar **B1** → `grupo_regulatorio_id='notificacao_receita_b'` + versão congelados;
  relatório SNGPC mostra o grupo. ✅
- Dispensar **não-controlado** → `grupo_regulatorio_id=NULL`; coluna vazia. ✅
- **R1:** congelar; alterar (em teste) a definição do grupo no motor; re-gerar o
  relatório → movimento passado **mantém** o grupo congelado. ✅
- Item com `classe_controle` inválida → dispensação **falha 422** (não congela NULL). ✅
- Gate verde: unit (`test_motor_regulatorio_escrituracao`, `test_relatorio_sngpc_r4`) +
  integração PG (`tests/integration/test_relatorio_sngpc_r4.py`). ✅

## ⚠️ Nota de ops — banco demo fora do controle de migração (dívida #98)
`data/pix_saude_demo.db` **não** pega a migração automática. Para a demo ver a coluna
e o item controlado, **reconstruir/re-semear** o banco demo após a migração:

```bash
cd backend
PICSAUDE_DEMO_MODE=true python3 seed_demo.py   # nasce já com o item B1
```
