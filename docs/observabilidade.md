# Observabilidade — PicSaúde (Ticket 11)

> Implementação mínima de logging estruturado, métricas em memória e endpoint `/metrics`.
> Para observabilidade real em produção, é necessário integrar Prometheus + Grafana.

---

## 1. Estrutura de logs

Cada requisição HTTP gera uma linha JSON no stdout. Formato:

```json
{
  "timestamp": "2026-04-17T22:49:33.561224+00:00",
  "level": "INFO",
  "logger": "picsaude.request",
  "event": "request",
  "path": "/health",
  "method": "GET",
  "status": 200,
  "latency_ms": 8.78,
  "request_id": "90c90d29435f"
}
```

Erros não tratados adicionam o campo `"type"` com o nome da exception e `"exception"` com o traceback.

---

## 2. Campos disponíveis

| Campo | Tipo | Descrição |
|---|---|---|
| `timestamp` | ISO-8601 | Momento do final da requisição |
| `level` | `INFO` / `WARNING` / `ERROR` | `INFO` para 2xx, `WARNING` para 4xx, `ERROR` para 5xx |
| `logger` | string | `picsaude.request` (normal) ou `picsaude.error` (erro) |
| `event` | string | `"request"` ou `"unhandled_exception"` |
| `path` | string | Path da rota (sem query string) |
| `method` | string | Método HTTP (GET, POST, etc.) |
| `status` | int | HTTP status code |
| `latency_ms` | float | Latência total em milissegundos |
| `request_id` | string | UUID curto (12 hex chars) único por requisição |
| `type` | string | Tipo da exception (apenas em erros) |
| `exception` | string | Traceback completo (apenas em erros) |

**Privacidade (LGPD):** nenhum campo contém CPF, CNS, nome de paciente ou dados clínicos.

---

## 3. Endpoint /metrics

```
GET /metrics
```

**Restrição:** aceita apenas requisições originadas de `127.0.0.1` ou `::1` (loopback).
Requisições externas recebem `HTTP 403`.

A verificação é feita no **TCP source IP** (`request.client.host`) — não pode ser contornada por headers como `X-Forwarded-For`.

### Resposta de exemplo

```json
{
  "requests_total": 1500,
  "errors_total": 12,
  "errors_4xx": 10,
  "errors_5xx": 2,
  "latency_avg_ms": 18.4,
  "last_latency_ms": 3.2,
  "timestamp": "2026-04-17T22:49:33.593073+00:00",
  "aviso": "Métricas por processo/worker. Reiniciam em restart. Sem agregação entre múltiplos workers."
}
```

### Campos

| Campo | Descrição |
|---|---|
| `requests_total` | Total de requisições recebidas neste worker |
| `errors_total` | Total de erros (4xx + 5xx) |
| `errors_4xx` | Erros de cliente (404, 422, 403, etc.) |
| `errors_5xx` | Erros de servidor (500, 503, etc.) |
| `latency_avg_ms` | Média simples de latência desde o start do processo |
| `last_latency_ms` | Latência da última requisição processada |
| `timestamp` | Momento do snapshot |

---

## 4. Como interpretar erros

### Log de erro (level WARNING — 4xx)

```json
{"level": "WARNING", "logger": "picsaude.error", "event": "request",
 "path": "/rota-inexistente", "status": 404, "latency_ms": 0.63, "request_id": "..."}
```

→ Erro de cliente: rota não encontrada, payload inválido, autorização negada.

### Log de erro (level ERROR — 5xx)

```json
{"level": "ERROR", "logger": "picsaude.error", "event": "request",
 "path": "/prescricoes", "status": 500, "latency_ms": 12.5, "request_id": "..."}
```

→ Erro de servidor: banco de dados, lógica interna, dependência indisponível.

### Rastrear uma requisição pelo request_id

```bash
grep "abc123def456" /var/log/picsaude.log
```

---

## 5. Arquivos do módulo

| Arquivo | Papel |
|---|---|
| `app/observabilidade/__init__.py` | Exports: `metrics`, `get_logger`, `configure_logging` |
| `app/observabilidade/metrics.py` | Contadores `_Metrics` (sem lock — GIL protege) |
| `app/observabilidade/logging_config.py` | Formatter JSON + `configure_logging()` |
| `app/middleware/observabilidade.py` | Middleware ASGI puro: intercepta request/response |
| `app/routers/metrics.py` | Endpoint `GET /metrics` (localhost only) |

**Nota técnica:** O middleware é implementado como **ASGI puro** (não `BaseHTTPMiddleware`) para evitar o deadlock conhecido do Starlette ao empilhar múltiplos middlewares BaseHTTPMiddleware.

---

## 6. Limitações atuais (obrigatórias)

| Limitação | Detalhe |
|---|---|
| **Métricas em memória** | Armazenadas na RAM do processo — sem persistência |
| **Reset em restart** | Contadores vão a zero a cada reinicialização do processo |
| **Métricas per-worker** | Com múltiplos workers uvicorn (`--workers N`), cada processo tem seus próprios contadores não sincronizados |
| **Sem agregação global** | `/metrics` retorna apenas o estado do worker que atendeu a requisição |
| **Sem histórico temporal** | Apenas média acumulada e último valor — sem séries temporais |
| **Ausência de Prometheus/Grafana** | Para observabilidade real em produção, integrar com Prometheus scraper e Grafana dashboards |
| **Query strings não logadas** | Por segurança, a query string não é registrada nos logs (pode conter tokens ou dados sensíveis) |

---

## 7. Validação realizada em 2026-04-17

```
Middleware criado:                 SIM (ASGI puro)
Formato de log:                    JSON estruturado por linha
Endpoint /metrics funcionando:     SIM (HTTP 200)
/metrics restrito a localhost:     SIM (verifica TCP source IP)
Contadores funcionando:            SIM (requests_total, errors_4xx, errors_5xx, latency_avg_ms)
Limitações documentadas:           SIM (6 limitações acima)
Logs de erro capturados:           SIM (level WARNING para 4xx, ERROR para 5xx)
Documento criado:                  SIM (este arquivo)
```

**OBSERVABILIDADE ATIVA**
