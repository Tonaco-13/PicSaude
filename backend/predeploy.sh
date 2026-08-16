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
#
# ⚠️ NÃO criar arquivo aqui esperando encontrá-lo no serviço (DESPACHO-ENG-011 §5).
# O pre-deploy do Render roda numa instância SEPARADA e efêmera: "Changes you make
# to the filesystem are not reflected in the deployed service" (render.com/docs/deploys),
# e "You can't access persistent disks during a service's build command or pre-deploy
# command" (render.com/docs/disks). Por isso o SQLite de referência CNES da demo é
# garantido no BOOT da aplicação — ver `app/cnes_demo.py`.
set -e

echo "[predeploy] alembic upgrade head"
alembic upgrade head

echo "[predeploy] seed_demo.py"
python3 seed_demo.py

echo "[predeploy] concluído"
