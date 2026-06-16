# Carga do CNES nacional na produção (PostgreSQL)

> Popular as tabelas de **referência** do CNES na base de produção para que a
> verificação institucional (login da farmácia/dispensador, identidade do prescritor)
> deixe de degradar (`cnes_verificado: false`) e passe a conferir de verdade.
>
> **Quando rodar:** depois do deploy (Etapa 8), com a base PostgreSQL de produção no ar.
> As tabelas CNES são dados externos do DATASUS → criadas **fora do Alembic** (o
> Alembic é dono só do schema clínico). A ferramenta: `backend/scripts/importar_cnes_pg.py`.

## O que é carregado

| Tabela | Origem (CSV) | Tamanho aprox. | Para quê |
|---|---|---|---|
| `estabelecimentos_cnes` | `tbEstabelecimento202512.csv` | ~400 mil | **Login da farmácia** confere o CNPJ (a correção do gap C.1) |
| `profissionais_cnes` | `tbDadosProfissionalSus202512.csv` | milhões | Identidade do prescritor via CNES |
| `relacao_prof_estab` | `tbCargaHorariaSus202512.csv` | muitos milhões | Vínculo profissional × estabelecimento |

## Passo 1 — baixar e descompactar a base do DATASUS

A base nacional é distribuída pelo DATASUS (atualização mensal):

```bash
# baixar BASE_DE_DADOS_CNES_<AAAAMM>.ZIP do portal do DATASUS, então:
mkdir -p data/cnes_br_tmp
unzip BASE_DE_DADOS_CNES_202512.ZIP -d data/cnes_br_tmp/
ls data/cnes_br_tmp/tbEstabelecimento202512.csv   # confere que os 3 CSVs existem
```

> A referência do snapshot (mês) vai em `CNES_SNAPSHOT_REF` / `CNES_SNAPSHOT_MES`
> (config.py). Ao trocar de mês, ajustar os nomes dos CSVs em `importar_cnes_pg.py`
> (`ARQUIVOS_CSV`) ou renomear os arquivos para o padrão `...202512.csv`.

## Passo 2 (recomendado) — medir o tamanho ANTES de carregar na gaveta paga

Carregar primeiro num PostgreSQL **local** para medir quanto ocupa e decidir o plano
do Render (a parte "profissionais/vínculos" são milhões de linhas):

```bash
# PG local efêmero (Docker)
docker run -d --name cnes_medir -e POSTGRES_PASSWORD=x -e POSTGRES_USER=x \
  -e POSTGRES_DB=cnes -p 5440:5432 postgres:15
export DATABASE_URL="postgresql://x:x@localhost:5440/cnes"
python backend/scripts/importar_cnes_pg.py

# tamanho de cada tabela
psql "$DATABASE_URL" -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
  FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"
```

Com o número em mãos, confirmar se o plano `basic-256mb` do Render comporta, ou subir.

## Passo 3 — carregar na produção

```bash
# DATABASE_URL = a connection string do Postgres de produção (Render)
export DATABASE_URL="postgresql://<prod>"
python backend/scripts/importar_cnes_pg.py

# ou, para carregar só os estabelecimentos primeiro (suficiente p/ o login da farmácia):
python backend/scripts/importar_cnes_pg.py --apenas estabelecimentos_cnes
```

O loader é **idempotente** (`DROP TABLE` + recria a cada execução) e cria os índices,
incluindo um índice funcional que casa com a query do login (busca de CNPJ rápida).

> ⚠️ Carregar milhões de linhas num Postgres **remoto** pela internet é lento. Se for
> pesado, a alternativa é carregar localmente, fazer `pg_dump -t estabelecimentos_cnes
> -t profissionais_cnes -t relacao_prof_estab` e restaurar (`psql`) na produção.

## Passo 4 — verificar

```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM estabelecimentos_cnes;"   # ~400 mil
```

- [ ] Login de uma farmácia real (CNPJ que consta no CNES) → `cnes_verificado: true`.
- [ ] Login de CNPJ inexistente → segue degradando gracioso (sem 500).

## Notas

- A ferramenta SQLite equivalente (dev/demo) é `backend/scripts/importar_cnes_br.py`.
- Gate automatizado do loader PG: `backend/tests/integration/test_importar_cnes_pg.py`
  (carga sintética + query do login + índice funcional; limpa as tabelas no teardown).
