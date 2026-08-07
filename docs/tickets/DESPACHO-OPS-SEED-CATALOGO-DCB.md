# DESPACHO-OPS-SEED-CATALOGO-DCB — ligar o seeder do catálogo DCB ao pipeline

> **Classe:** `ops` (infra de seed + gate; não altera semântica clínica, não toca o conteúdo curado do catálogo).
> **Origem:** levantamento de bases 07/08 + parecer do Conselheiro.
> **Branch:** `ops/seed-catalogo-dcb` · **Implementação:** Engenheiro-chefe · **Revisão do PR:** Claude Code do terminal (inversão de chapéus — o app implementou).

---

## 1. Problema — o seeder órfão

`catalogo_substancias` nascia **vazia** em todo ambiente. Não por falta de dado: o
dado existia desde o Ticket 20 —

| Peça | Estado |
|---|---|
| `backend/app/domain/catalogo_seed.py` | 56 DCBs curadas (5 GLP-1 · 30 antimicrobianos · 20 Portaria 344 · 1 inativa) |
| `backend/scripts/seed_catalogo_substancias.py` | script executável, idempotente |
| `alembic/versions/0c8654f77baf` | tabela criada em todo ambiente |

— faltava **a chamada**. Nenhum caminho do pipeline invocava
`aplicar_seed_catalogo`: nem o `predeploy.sh` (Render/vitrine), nem o
`scripts/reset_demo_db.py`, nem o conftest do gate de navegador. O script era um
ato manual que ninguém lembrava de executar.

**Por que dói:** vazio, o catálogo não é inofensivo — é **silencioso**. Pelo
princípio de cautela do catálogo parcial
(`catalogo_regulatorio.validar_classificacao`, cenário 1), substância ausente
devolve `coerente=True, alertas=[]`. O motor RDC 1.000/2025 chamado por
`routers/receituarios.py:220` (`validar_itens_prescricao`) ficava **cego sem
emitir um único sinal**, e `GET /catalogo/substancias` respondia vazio. A jornada
do controlado da demo (B1 CLONAZEPAM) rodava sem oráculo.

---

## 2. O ponto canônico — um funil, não quatro chamadas

Investigação dos caminhos que semeiam a demo:

```
predeploy.sh (Render/vitrine) ──→ python3 seed_demo.py ──┐
scripts/reset_demo_db.py ────────→ seed_demo.main() ─────┼──→ seed_demo.main()
tests/browser/conftest.py ───────→ _rodar("seed_demo.py")┘
```

Os três desembocam em `seed_demo.main()`. **Ligar ali liga tudo** — vitrine e
local ficam iguais por construção, sem quatro chamadas para manter em sincronia.

`scripts/seed_catalogo_substancias.py` permanece como está: continua útil para
atualizar só o catálogo sem reprocessar o seed inteiro, e já chama a mesma função
de domínio (zero duplicação de dado).

### Decisões de implementação

1. **Dado de referência, antes das personas.** O catálogo não depende de nenhuma
   persona (nenhuma FK aponta para ele), como `estabelecimentos_cnes`. Entra
   primeiro, com `commit` próprio — a jornada do controlado fica servida mesmo se
   um bloco *best-effort* adiante falhar.
2. **NÃO é best-effort.** Os blocos de artefato da demo (receita na fila,
   atestado, exame, laudo) são isolados em `try/except` para nunca derrubar o
   deploy. O catálogo **não**: catálogo vazio é exatamente o defeito que este
   seed existe para impedir. Falha aqui aborta o seed (e o deploy, via `set -e`
   do `predeploy.sh`) — sinal honesto, melhor que uma demo silenciosamente sem
   classificação de controle.
3. **Idempotência já era do seeder** — `_upsert` por `dcb_normalizada`
   (atualiza, não duplica). Conferida nos dois dialetos (§4).

---

## 3. A guarda — o que impede o órfão de renascer

`backend/tests/test_seed_catalogo_dcb.py` monta um banco demo efêmero com a
**receita do predeploy** (`alembic upgrade head` + `seed_demo.py`) e prova:

| Teste | O que trava |
|---|---|
| `test_seed_da_demo_popula_catalogo_substancias` | tabela não-vazia **e** completa (56 = nº de DCBs distintas, derivado do próprio seed) |
| `test_seed_reexecutado_nao_duplica` | 2ª rodada inerte, zero DCB duplicada (o deploy re-roda o seed a cada push) |
| `test_motor_enxerga_classificacao_do_clonazepam` | evidência pela função que `receituarios.py` chama, não por `print` |
| `test_catalogo_vazio_deixa_o_motor_cego` | vermelho-antes-de-verde: com a tabela esvaziada, o mesmo motor emudece |

**No gate** (`.github/workflows/gates.yml`), em duas camadas:

- passo próprio `Gate do seed do catálogo DCB` — a suíte acima (SQLite);
- uma linha no `Predeploy smoke` — `SELECT COUNT(*)` na **PG que o predeploy
  acabou de semear**, o dialeto e o caminho onde o vazio doeu.

---

## 4. Verificação executada

**SQLite efêmero** (`alembic upgrade head` → `init_tables.py` → `seed_demo.py`):

```
✅ catálogo regulatório: 56 substâncias (GLP-1 5 · antimicrobianos 30 · Portaria 344 20 · inativas 1)

SELECT ... WHERE dcb_normalizada = 'clonazepam'
  {'dcb_display': 'Clonazepam', 'classe_controle': 'B1', 'tipo_retencao': None, 'fonte': 'portaria_344', 'ativo': 1}

validar_itens_prescricao(...)   ← o que routers/receituarios.py:220 chama
  item 1 · warning · sugestao_classe=B1 · 'Clonazepam 2mg' consta no catálogo como classe B1
           (Portaria 344/1998) mas classe_controle não foi informada.
  item 2 · warning · sugestao_classe=B1 · 'Clonazepam 2mg' foi declarado como classe C1,
           mas catálogo indica classe B1 (Portaria 344/1998).
```

**PostgreSQL efêmero**, `sh predeploy.sh` + re-seed (o que o Render faz):

```
 total | ativas          dcb_display | classe_controle | fonte        | ativo
-------+--------             --------+-----------------+--------------+-------
    56 |     55            Clonazepam | B1              | portaria_344 | t

SELECT dcb_normalizada, COUNT(*) ... HAVING COUNT(*) > 1  →  0 linhas   (idempotente)
```

Regressão: `tests/unit` 410 passed · suíte de integração (PG) sem alteração
atribuível — ver §5.

---

## 5. Achado fora de escopo (não implementado neste PR)

`tests/integration/test_catalogo_regulatorio.py` tem **7 testes vermelhos há
tempo**, pela mesma raiz: o conftest de integração nunca semeou o catálogo. Como
não estão no filtro `-k` do gate, ninguém via.

Medição (PG efêmero, suíte de integração completa):

| Estado do catálogo | Resultado |
|---|---|
| vazio (hoje) | **9 failed** / 355 passed |
| semeado | **2 failed** / 362 passed |

Exatamente os 7 testes do catálogo mudam de cor; **zero colateral** — as 2
falhas restantes (`test_4d2_instance_id_ledger`, `test_regras_receituario`) são
pré-existentes e sem relação.

Correção sugerida (follow-up, ~5 linhas): fixture de sessão em
`tests/integration/conftest.py` chamando `aplicar_seed_catalogo(conn)`. Fora do
escopo deste despacho ("só ligar o que existe + guarda") — fica para martelo do
Fabiano.

---

## 6. Nota de fato

O despacho estimava "~120 DCBs". O catálogo curado tem **56** (5 + 30 + 20 + 1
inativa) — número confirmado no seed e nos dois dialetos. A guarda deriva o
esperado das próprias tuplas de `catalogo_seed.py`, então acompanha sem edição
quando o arquiteto acrescentar substâncias (TICKET-MOTOR-REGULATORIO-AUDITORIA-CATALOGO).

---

## 7. Arquivos

| Arquivo | Mudança |
|---|---|
| `backend/seed_demo.py` | `_garantir_catalogo_regulatorio()` + chamada em `main()` |
| `backend/tests/test_seed_catalogo_dcb.py` | novo — a guarda (4 testes) |
| `.github/workflows/gates.yml` | passo do gate + conferência na PG do predeploy smoke |

Não tocados (fora de escopo por despacho): conteúdo de `catalogo_seed.py`, TUSS,
qualquer outra base.
