#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# Pré-deploy do Render — migrações + seed de demonstração.
# ─────────────────────────────────────────────────────────────────────────────
# Por que um script (e não "alembic upgrade head && python3 seed_demo.py" direto
# no preDeployCommand): o Render executa o preDeployCommand como argv, SEM shell.
# Com o comando inline, o "&&" era passado como argumento do alembic e o deploy
# falhava com `unrecognized arguments: && python3 seed_demo.py`. Aqui o próprio
# `sh` interpreta o encadeamento. O CMD do Dockerfile já usa `sh -c`; o
# preDeployCommand não — daí a diferença.
#
# Roda com WORKDIR=/app (Dockerfile), onde ficam alembic.ini e seed_demo.py.
set -e

echo "[predeploy] alembic upgrade head"
alembic upgrade head

echo "[predeploy] seed_demo.py"
python3 seed_demo.py

echo "[predeploy] concluído"
