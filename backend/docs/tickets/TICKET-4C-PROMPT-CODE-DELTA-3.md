# Prompt-delta-3 para Claude Code — TICKET 4C (rodada 5)

> **Classe (CLAUDE.md §10): `core`** — toca ledger (models de eventos),
> bootstrap de identidade da instância e lifespan da aplicação. Por isso
> CODEX revisou e exigiu reescrita do delta-2.
>
> **Substitui** `TICKET-4C-PROMPT-CODE-DELTA-2.md`, que tinha bug no P2:
> setar `PICSAUDE_INSTANCE_ID` globalmente quebraria o teste 15 da 4C
> (`test_get_instance_id_conn_funciona_com_pgconnection_wrapper`). Esta
> versão usa **lifespan injetável** em vez de env override global.
>
> **Trabalho prévio: 43/43 verdes** — não reverter.

---

```
=== TICKET 4C — RODADA 5: 3 ajustes (P2 reescrito) ===

CONTEXTO

A rodada 4 do CODEX detectou regressão fora da suíte-alvo
(test_eventos_publicacao.py — outbox quebra porque models não têm
instance_id) + 2 pontos menores. O delta-2 propôs correção, mas a
rodada 5 do CODEX detectou que a fixture autouse com
PICSAUDE_INSTANCE_ID global quebraria o teste 15 da 4C.

Este delta-3 mantém P1 (alinhar 6 models) e P3 (docstring) e
REESCREVE P2 com lifespan injetável.

CLASSIFICAÇÃO (CLAUDE.md §10): core. Toca ledger + identidade
de instância + bootstrap do lifespan.

NÃO reverter o trabalho prévio. Apenas aplicar os 3 ajustes abaixo.

DIRETÓRIO:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

--------------------------------------------------
AJUSTE 1 (P1) — Alinhar 6 models com a coluna instance_id
--------------------------------------------------

Causa: a 4B adicionou instance_id via Alembic em 10 tabelas. Models
SQLAlchemy não foram alinhados. Em ambientes com create_all (fixtures
de teste legadas), a coluna NÃO existe → INSERT do outbox quebra
silenciosamente.

Adicionar `instance_id = Column(String(36), nullable=True)` em CADA
um dos 6 models abaixo (são os que registrar_evento_ledger + outbox
escrevem). NÃO atualizar os 4 models de objetos sanitários
principais (Prescricao, PedidoExame, Laudo, Agendamento) — escopo 4D.

Os 6 models alvo:

  1. app/models/evento_publicacao.py
  2. app/models/prescricao_evento.py
  3. app/models/pedido_exame_evento.py
  4. app/models/laudo_evento.py
  5. app/models/agendamento_evento.py
  6. app/models/circulacao_diagnostica_evento.py

ATENÇÃO 1.A — Imports faltando String em 3 arquivos.

Os arquivos abaixo hoje NÃO importam String. Atualizar o import
ANTES de adicionar a coluna:

  - app/models/evento_publicacao.py
    Atual: from sqlalchemy import Column, Integer, Text
    Novo:  from sqlalchemy import Column, Integer, String, Text

  - app/models/agendamento_evento.py
    Atual: from sqlalchemy import Column, ForeignKey, Integer, Text
    Novo:  from sqlalchemy import Column, ForeignKey, Integer, String, Text

  - app/models/circulacao_diagnostica_evento.py
    Atual: from sqlalchemy import Column, ForeignKey, Integer, Text
    Novo:  from sqlalchemy import Column, ForeignKey, Integer, String, Text

Os outros 3 (prescricao_evento.py, pedido_exame_evento.py,
laudo_evento.py) já importam String — verificar antes de tocar.

ATENÇÃO 1.B — Posição da nova coluna em EventoPublicacao.

O modelo real tem `publicado_em` DEPOIS de `criado_em`. Adicionar
`instance_id` AO FINAL DAS COLUNAS — depois de publicado_em. Não
inserir entre criado_em e publicado_em.

Exemplo correto (evento_publicacao.py):

  class EventoPublicacao(Base):
      __tablename__ = "eventos_publicacao"

      id           = Column(Text, primary_key=True)
      tipo_evento  = Column(Text, nullable=False)
      objeto_tipo  = Column(Text, nullable=False)
      objeto_id    = Column(Text, nullable=False)
      payload      = Column(Text, nullable=False)
      org_id       = Column(Text, nullable=True)
      unidade_id   = Column(Text, nullable=True)
      publicado    = Column(Integer, nullable=False, default=0)
      tentativas   = Column(Integer, nullable=False, default=0)
      criado_em    = Column(Text, nullable=False)
      publicado_em = Column(Text, nullable=True)
      # NOVO (4C): marca d'água da instância PicSaúde — preenchida pelo
      # helper registrar_evento_ledger / registrar_outbox via
      # get_instance_id_conn(). Nullable=True alinhado com a migration
      # 4B (4b1ce80a017d) — preserva registros pré-instance_id.
      instance_id  = Column(String(36), nullable=True)

Para os outros 5 models, adicionar instance_id ao final das colunas
existentes, antes de quaisquer relationships().

NOTA SOBRE TIPO: use String(36) para alinhar com a migration 4B
(VARCHAR(36)). Em SQLite ambos colapsam para TEXT; no PostgreSQL
String(36) gera VARCHAR(36) idêntico.

--------------------------------------------------
AJUSTE 2 (P2 — REESCRITO) — Lifespan injetável + conftest top-level
--------------------------------------------------

Problema do delta-2 (descoberto pela rodada 5 do CODEX):

  Setar PICSAUDE_INSTANCE_ID globalmente em fixture autouse faz
  get_instance_id_conn curto-circuitar SEMPRE. Teste 15 da 4C
  (test_get_instance_id_conn_funciona_com_pgconnection_wrapper)
  espera capturar INSERT ... RETURNING chave no fake PG. Sem
  INSERT (porque curto-circuitou no env override), o assert
  `len(insert_sqls) == 1` falha.

Solução: lifespan injetável. Hook do startup vira função
module-level patchável; conftest patcha o hook para no-op em testes,
sem tocar PICSAUDE_INSTANCE_ID globalmente.

PASSO 2.A — Refatorar app/main.py para extrair _lifespan_bootstrap.

Atual (delta-1, rodada 3):

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      session = SessionLocal()
      try:
          get_instance_id(session)
      finally:
          session.close()
      yield

Novo:

  def _lifespan_bootstrap() -> None:
      """
      Hook do startup — bootstrap idempotente do instance_id.

      Função module-level para ser patchável em testes via
      unittest.mock.patch (CODEX rodada 5 P1). Em produção/dev, abre
      SessionLocal global e chama get_instance_id(session) — garante
      DB↔arquivo↔env coerentes antes do primeiro request.
      """
      session = SessionLocal()
      try:
          get_instance_id(session)
      finally:
          session.close()


  @asynccontextmanager
  async def lifespan(app: FastAPI):
      _lifespan_bootstrap()
      yield

Manter `app = FastAPI(..., lifespan=lifespan)` como está.

PASSO 2.B — Atualizar backend/conftest.py (raiz).

Adicionar duas coisas:

(i) No TOP-LEVEL do módulo (antes de qualquer import de app.*),
    setar PICSAUDE_ENV=test para evitar o guard de prod em
    main.py:32 (importtime: raise RuntimeError se PICSAUDE_ENV=prod
    + SQLite). Fixtures autouse rodam DEPOIS dos imports — não
    pegam isso. Setar via environ.setdefault para não pisar em
    PICSAUDE_ENV explícita do operador.

(ii) Fixture autouse session-scope que patcha _lifespan_bootstrap
     para no-op. NÃO setar PICSAUDE_INSTANCE_ID global aqui — isso
     quebraria teste 15 da 4C.

Conteúdo final esperado de backend/conftest.py:

  # conftest.py raiz (backend/) — configura sys.path e ambiente de
  # testes ANTES de qualquer importação de app.*
  import os
  import sys

  # ----------------------------------------------------------------
  # Top-level (executado antes de coleta) — evita o guard de prod
  # em app/main.py:32 que dispara em import-time se PICSAUDE_ENV=prod.
  # ----------------------------------------------------------------
  os.environ.setdefault("PICSAUDE_ENV", "test")

  import pytest

  _root = os.path.dirname(os.path.abspath(__file__))
  if _root not in sys.path:
      sys.path.insert(0, _root)


  @pytest.fixture(autouse=True, scope="session")
  def _disable_rate_limit_in_tests():
      """Desativa rate limiting globalmente durante testes."""
      os.environ["RATE_LIMIT_DISABLED"] = "1"
      yield
      del os.environ["RATE_LIMIT_DISABLED"]


  @pytest.fixture(autouse=True, scope="session")
  def _disable_lifespan_bootstrap():
      """
      Neutraliza _lifespan_bootstrap em testes — evita que
      with TestClient(app) toque o DB real (data/pix_saude_pe.db).

      NÃO usa PICSAUDE_INSTANCE_ID global porque isso faria
      get_instance_id_conn curto-circuitar SEMPRE, quebrando o
      teste 15 da 4C (CODEX rodada 5 P1).

      Testes que precisam exercitar o lifespan real (ex.: futuros
      testes do startup hook) devem usar monkeypatch.undo() ou
      fixture local que stop o patch.
      """
      from unittest.mock import patch
      with patch("app.main._lifespan_bootstrap", lambda: None):
          yield

NOTA: o `os.environ.setdefault` permite que um operador setando
PICSAUDE_ENV=prod externamente (ex.: rodando pytest em ambiente
de produção, o que não deveria acontecer) ainda dispare o guard.
Isso é proposital — defesa em profundidade.

--------------------------------------------------
AJUSTE 3 (P3) — Atualizar docstring obsoleta de get_instance_id_conn
--------------------------------------------------

(Sem mudança em relação ao delta-2 — copiar a mesma orientação.)

Arquivo: app/instance.py — função get_instance_id_conn

A docstring atual (linhas ~329-343) diz que env override e arquivo
.instance_id permanecem APENAS na variante get_instance_id(session).
Isso é falso desde a rodada 3 (P2-A): get_instance_id_conn agora
TAMBÉM respeita PICSAUDE_INSTANCE_ID em dev/test.

Atualizar para algo como:

    Padrão (CODEX rodadas 2-3):

      0. Env override em dev/test: se PICSAUDE_INSTANCE_ID setada e
         PICSAUDE_ENV != "prod", retorna o valor da env sem tocar DB.
         Em prod, env override → RuntimeError.
      a. SELECT primeiro (caso comum: instance_id já existe no DB).
      b. Se vazio (first boot): INSERT idempotente.
         - SQLite: INSERT OR IGNORE (sem RETURNING)
         - PG via wrapper: INSERT ... ON CONFLICT DO NOTHING
                             RETURNING chave (RETURNING serve apenas
                             para evitar a auto-adição de RETURNING id
                             pelo wrapper _PgConnection)
      c. SELECT autoritativo após o INSERT — race-safe.

    Sincronização com o arquivo .instance_id permanece APENAS na
    variante get_instance_id(session): aquela roda no boot da
    aplicação (lifespan); esta variante roda dentro de transações
    clínicas, onde I/O em arquivo seria contraproducente.

Manter o resto do docstring intacto.

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Aplicar P1 — atualizar 3 imports + adicionar coluna em 6 models.
2. Aplicar P2 — refatorar lifespan em main.py + atualizar conftest.
3. Aplicar P3 — atualizar docstring em instance.py.
4. Rodar a suíte-alvo da 4C (deve continuar 20 + 23 = 43 verdes):
     pytest tests/test_ledger_helper.py \
            tests/test_migration_4b_instance_id.py \
            tests/test_migration_regulariza_circulacao_diagnostica.py \
            tests/test_instance_id.py -v
5. Rodar a regressão original do CODEX rodada 4:
     pytest tests/test_eventos_publicacao.py -v
   Esperado: 23/23 verdes (era 22/23 com 1 falha por instance_id).
6. Rodar sanity em outros arquivos que usam TestClient:
     pytest tests/test_assinatura_icp.py \
            tests/test_prestadores.py \
            tests/test_ia_documental.py \
            tests/test_ia_cid.py -v
   Esperado: continuam verdes (sem novas regressões).
7. Reportar output completo dos passos 4, 5 e 6.
8. NÃO COMITAR. Engenheiro-Chefe valida e propõe commit final.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- Não tocar nos 4 models de objetos sanitários principais
  (Prescricao, PedidoExame, Laudo, Agendamento) — escopo 4D.
- Não tocar nos routers (escopo 4D).
- Não modificar assinaturas públicas de registrar_evento_ledger,
  get_instance_id_conn, get_instance_id ou registrar_outbox.
- Não modificar testes existentes (apenas adicionar fixture nova
  no conftest raiz, sem mexer nos 20 + 23 testes da 4C).
- Não setar PICSAUDE_INSTANCE_ID globalmente — quebraria teste 15.
```

---

## Notas para Fabiano

- **O P2 reescrito resolve dois problemas de uma vez:**
  - `os.environ.setdefault("PICSAUDE_ENV", "test")` em top-level → evita guard de prod em import-time
  - `patch("app.main._lifespan_bootstrap", lambda: None)` em fixture autouse → neutraliza só o startup, sem tocar `PICSAUDE_INSTANCE_ID` global
- **Vantagem da abordagem injetável:** se algum dia precisarmos de teste que exercite o lifespan real (ex: integração que verifica que `instance_id` foi gerado no startup), basta usar `mock.patch.stopall()` ou fixture local que para o patch — sem ter que reverter env vars.
- **Espero 43 (4C) + 23 (eventos_publicacao) + ~50-80 (TestClient samples) = ~120+ verdes** ao final.
- Se algum dos 4 testes de TestClient sample (assinatura_icp, prestadores, ia_documental, ia_cid) quebrar com o patch do lifespan, é porque algum deles já assumia que lifespan rodou. Code deve trazer pra mim antes de improvisar.