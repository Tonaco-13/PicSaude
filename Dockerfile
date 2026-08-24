# ─────────────────────────────────────────────────────────────────────────────
# PicSaúde — Backend Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Dependências primeiro — melhor aproveitamento de cache de layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY backend/ .

# Telas do frontend servidas pela própria casa em modo DEMO (vitrine "uma casa só").
# Vivem na raiz do repo (fora de backend/); config.js usa window.location.origin,
# então same-origin "só funciona" sem CORS. PICSAUDE_FRONTEND_DIR aponta o main.py.
#
# ⚠️ GLOB, NÃO LISTA EXPLÍCITA — e isto é correção de INCIDENTE, não estilo.
#
# A lista era `*.html config.js logo-picsaude.png`. Todo asset novo entrava no
# repo, passava no gate (que serve o REPO) e sumia na imagem. Três já estavam
# 404 em produção quando o incidente estourou:
#
#   · `lente.js`                    (#167) — "ver rastreabilidade" NUNCA
#                                     funcionou na vitrine, e ninguém viu;
#   · `catalogos-encaminhamento.js` (#187) — o formulário de encaminhamento
#                                     subia com especialidade e CID vazios;
#   · `submodulos.js` / `.css`      (#193) — derrubaram o init do prescritor,
#                                     e aí o silêncio virou tela branca.
#
# Os dois primeiros eram falhas SILENCIOSAS: degradavam uma função e seguiam.
# Só o terceiro quebrou alto o bastante para ser notado — e é por isso que a
# guarda de paridade (`tests/test_paridade_deploy_assets.py` + o passo de CI que
# builda a imagem) vale mais que este glob: glob conserta hoje, guarda impede
# amanhã. Espécie registrada: **gate verde, deploy cego**.
COPY *.html *.js *.css logo-picsaude.png /app/frontend/
ENV PICSAUDE_FRONTEND_DIR=/app/frontend

# Bases de referência (medicamentos DEF + CID-10) lidas em runtime por app/ai/.
# Ficam FORA de /data (que é dir de volume) para não serem sombreadas por um mount.
COPY data/def_medicamentos.csv /app/reference/def_medicamentos.csv
ENV PICSAUDE_DEF_CSV=/app/reference/def_medicamentos.csv
COPY data/cid10.csv /app/reference/cid10.csv
ENV PICSAUDE_CID_CSV=/app/reference/cid10.csv
COPY data/cmed_apresentacoes.csv /app/reference/cmed_apresentacoes.csv
ENV PICSAUDE_CMED_APRES_CSV=/app/reference/cmed_apresentacoes.csv
COPY data/decisao_semaforo.csv /app/reference/decisao_semaforo.csv
ENV PICSAUDE_SEMAFORO_CSV=/app/reference/decisao_semaforo.csv
COPY data/posologia_sugerida.csv /app/reference/posologia_sugerida.csv
ENV PICSAUDE_POSOLOGIA_CSV=/app/reference/posologia_sugerida.csv

# Banco em volume externo — nunca dentro da imagem
ENV PIX_SAUDE_DB=/data/picsaude.db

# Cria o diretório de dados (o volume externo o sobrescreverá em runtime)
RUN mkdir -p /data

# Health check embutido — usa urllib stdlib (sem dependência de curl).
# Honra $PORT (PaaS como Render injeta a porta); default 8000 em runs locais.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c \
        "import os, urllib.request, sys; \
         p = os.environ.get('PORT', '8000'); \
         r = urllib.request.urlopen(f'http://localhost:{p}/health', timeout=4); \
         sys.exit(0 if r.status == 200 else 1)" \
    || exit 1

EXPOSE 8000

# Escuta em $PORT quando o PaaS o injeta (Render); senão 8000 (local).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
