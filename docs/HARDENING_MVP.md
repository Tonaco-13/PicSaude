# Checklist de Hardening — PicSaúde MVP Produção

> Define os ajustes mínimos para levar o backend do ambiente de desenvolvimento
> para um MVP operável em ambiente institucional (secretaria de saúde, hospital, piloto municipal).
>
> **Status de cada item:** ✅ implementado · 🔜 próximo · 🟡 parcial · ❌ pendente

---

## 1. Autenticação por perfis (RBAC) ❌

Perfis mínimos necessários:

| Perfil | Descrição |
|---|---|
| `prescritor` | Emite e cancela prescrições |
| `dispensador` | Dispensar itens, transferir custódia |
| `cidadao` | Consulta pública das próprias prescrições |
| `auditor` | Leitura de relatórios e ledger |
| `admin` | Acesso total |

Mapeamento de endpoints:

| Endpoint | Perfil permitido |
|---|---|
| `POST /prescricoes` | prescritor |
| `POST /prescricoes/fisica` | prescritor |
| `POST /prescricoes/{p}/custodia/transferir` | dispensador, paciente |
| `POST /prescricoes/{p}/itens/{i}/dispensar` | dispensador |
| `GET /dispensacoes/{id}/comprovante` | dispensador, prescritor |
| `GET /relatorios/dispensacoes.csv` | auditor, admin |
| `GET /public/prescricoes/{protocolo}` | público |
| `GET /prescricoes/{protocolo}/qr` | prescritor, dispensador |

**Implementação sugerida:**
```python
# FastAPI dependency
def require_role(*roles: str):
    def dep(token: str = Depends(oauth2_scheme)):
        payload = verify_jwt(token)
        if payload["role"] not in roles:
            raise HTTPException(403)
    return dep

@router.post("/prescricoes")
def criar(payload: PrescricaoIn, _=Depends(require_role("prescritor"))):
    ...
```

---

## 2. JWT com expiração ❌

| Token | TTL |
|---|---|
| Access Token | 15 minutos |
| Refresh Token | 24 horas |

Payload mínimo:
```json
{
  "sub": "id_do_usuario",
  "role": "prescritor",
  "cns": "980001112223336",
  "exp": 1234567890
}
```

---

## 3. HTTPS obrigatório em produção ❌

- Nginx com TLS 1.3
- HSTS habilitado

Cabeçalhos obrigatórios:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

---

## 4. Proteção de relatórios sensíveis 🟡

`GET /relatorios/dispensacoes.csv` expõe CPF e nome de pacientes.

- **Hoje:** disponível sem autenticação (CORS restrito a 127.0.0.1 — proteção local)
- **Produção:** exigir perfil `auditor` ou `admin`
- **Nunca** tornar público

> Ver `backend/app/routers/relatorios.py` — há comentário TODO registrado.

---

## 5. Auditoria de acesso ❌

Além do ledger sanitário (`prescricao_eventos`), registrar acesso ao sistema.

Tabela sugerida: `auditoria_acessos`

```sql
CREATE TABLE auditoria_acessos (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id  TEXT,
    perfil      TEXT,
    endpoint    TEXT NOT NULL,
    metodo      TEXT NOT NULL,
    ip          TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> O ledger `prescricao_eventos` já cobre a trilha sanitária.
> `auditoria_acessos` cobre a trilha de acesso ao sistema.

---

## 6. Rate limit na consulta pública ❌

`GET /public/prescricoes/{protocolo}` precisa proteção contra scraping.

Limite sugerido: **60 req/min por IP**

```python
# Com slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/public/prescricoes/{protocolo}")
@limiter.limit("60/minute")
def consulta_publica(request: Request, protocolo: str):
    ...
```

---

## 7. Proteção contra enumeração de protocolo ✅

Protocolo é UUID v4 — espaço de busca inviável para força bruta.

Resposta para protocolo inexistente: sempre **404**, sem detalhe adicional.

> Já implementado em `routers/publico.py`.

---

## 8. Sanitização de logs ❌

Logs nunca devem conter:

| ❌ Nunca logar | ✅ Permitido logar |
|---|---|
| CPF do paciente | protocolo (UUID) |
| CNS do prescritor | status da prescrição |
| Nome do paciente | endpoint chamado |
| Medicamentos | código HTTP da resposta |

Configurar filtro no logger do Python:
```python
class SanitizingFilter(logging.Filter):
    _CPF_RE = re.compile(r'\b\d{11}\b')
    def filter(self, record):
        record.msg = self._CPF_RE.sub('[CPF]', str(record.msg))
        return True
```

---

## 9. Backup automático do banco ❌

**SQLite (atual):**
```bash
# Cópia diária com timestamp
cp data/pix_saude_pe.db backups/pix_saude_$(date +%Y%m%d).db
```

**PostgreSQL (produção):**
```bash
pg_dump picsaude | gzip > backups/picsaude_$(date +%Y%m%d).sql.gz
```

Recomendações:
- Retenção de 30 dias
- Backup criptografado em armazenamento externo
- Teste de restore mensal

---

## 10. Monitoramento ❌

Métricas prioritárias:

| Métrica | Ferramenta sugerida |
|---|---|
| Erros 5xx | Sentry |
| Tempo de resposta p95 | Prometheus + Grafana |
| Volume de prescrições/dia | Prometheus custom counter |
| Volume de dispensações/dia | Prometheus custom counter |
| Disponibilidade | UptimeRobot |

---

## Decisões arquiteturais já implementadas

> Itens que protegem o sistema mesmo antes do hardening completo.

| Proteção | Onde | Status |
|---|---|---|
| CPF sentinela `00000000000` excluído de relatórios | `relatorios.py`, `prescricoes.py` | ✅ |
| Endpoint `/pacientes` retorna 403 | `routers/pacientes.py` | ✅ |
| OTP não retorna código na resposta HTTP | `routers/auth.py` | ✅ |
| CORS restrito a origens locais | `main.py` | ✅ |
| UUID v4 como protocolo público | `prescricoes.py` | ✅ |
| Endpoint público não expõe CPF/CNS/lote | `routers/publico.py` | ✅ |
| Ledger imutável (sem UPDATE/DELETE) | arquitetura | ✅ |
| `BASE_URL` via variável de ambiente | `config.py` | ✅ |

---

## Ordem de implementação recomendada para produção

```
1. JWT + RBAC básico          ← desbloqueia todos os outros
2. HTTPS + Nginx              ← infraestrutura
3. Rate limit consulta pública
4. Sanitização de logs
5. Auditoria de acessos
6. Backup automático
7. Monitoramento
```

---

*Documento gerado em 2026-03-13. Atualizar conforme evolução do sistema.*
