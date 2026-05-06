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

# Banco em volume externo — nunca dentro da imagem
ENV PIX_SAUDE_DB=/data/picsaude.db

# Cria o diretório de dados (o volume externo o sobrescreverá em runtime)
RUN mkdir -p /data

# Health check embutido — usa urllib stdlib (sem dependência de curl)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c \
        "import urllib.request, sys; \
         r = urllib.request.urlopen('http://localhost:8000/health', timeout=4); \
         sys.exit(0 if r.status == 200 else 1)" \
    || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
