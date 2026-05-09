# Prompt-delta para Claude Code — TICKET 4C (rodada 3)

> Cole o bloco abaixo no Claude Code (VS Code).
> Aplica 3 ajustes pós-implementação (P1 + P2-A + P2-B) que CODEX pediu
> antes de aprovar o commit. **Trabalho prévio: 38/38 verdes** — não
> reverter, apenas adicionar/ajustar.

---

```
=== TICKET 4C — RODADA 3: 3 ajustes antes do commit ===

CONTEXTO

Você implementou a 4C (helper de inserção no ledger). 38/38 testes
verdes. Antes do commit, CODEX revisou o código em disco e levantou
3 ajustes. Todos aceitos pelo Engenheiro-Chefe e pelo Fabiano.

Ticket completo (atualizado com §5.5 desta rodada):
  backend/docs/tickets/TICKET-4C-HELPER-LEDGER-INSTANCE-ID.md

NÃO reverter o trabalho prévio. Apenas aplicar os 3 ajustes abaixo.

DIRETÓRIO:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

--------------------------------------------------
AJUSTE 1 (P1) — Validar instance_id em runtime
--------------------------------------------------

Arquivo: app/domain/ledger.py

Adicionar validação no INÍCIO de registrar_evento_ledger (antes de
qualquer outra checagem):

  from app.instance import _validar_uuid_v4   # já existe nesse módulo

  def registrar_evento_ledger(conn, *, ...):
      # 0. Validação de instance_id em runtime — defesa em camadas.
      #    Keyword-only sem default só pega ausência (TypeError);
      #    aqui pegamos invalidez (None explícito, "", string lixo, UUID v1).
      _validar_uuid_v4(instance_id)

      # 1. Validação de objeto_tipo (já existe — manter)
      ...

Razão: o contrato é "ledger não aceita evento sem instance_id válido".
Hoje só pegamos ausência. CODEX P1 (rodada 3) apontou que None/""/lixo
passariam silenciosamente.

NOTA: _validar_uuid_v4 é função privada de instance.py — está OK
importá-la em ledger.py (não é cross-domain, é mesmo domain helper).

--------------------------------------------------
AJUSTE 2 (P2-A) — Lifespan + nuance env override
--------------------------------------------------

Arquivo: app/main.py

Adicionar lifespan (asynccontextmanager) que chama get_instance_id
no startup. Mínimo possível:

  from contextlib import asynccontextmanager
  from app.database import SessionLocal
  from app.instance import get_instance_id

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      """
      Startup hook (sub-tarefa 4C): garante que instance_id está
      sincronizado entre DB (meta_instalacao), arquivo (.instance_id)
      e env override ANTES de qualquer request.

      Sem isso, get_instance_id_conn(conn) no primeiro request pode
      criar valor no DB sem propagar para o arquivo, gerando
      divergência forense que get_instance_id(session) rejeitaria
      depois com RuntimeError.
      """
      session = SessionLocal()
      try:
          get_instance_id(session)  # bootstrap idempotente
      finally:
          session.close()
      yield  # aplicação roda aqui

  app = FastAPI(title="PIX da Saúde", version="0.2.0", lifespan=lifespan)

NÃO rodar get_instance_id no import (apenas dentro do lifespan).

Verificar se SessionLocal está exportado em app/database.py. Se não
estiver, importar como `from app.database import engine` + criar
sessão local com `Session(engine)`. Use o jeito mais idiomático ao
que o repo já tem.

Arquivo: app/instance.py

Adicionar verificação de env override no INÍCIO de
get_instance_id_conn (ANTES do SELECT no DB), espelhando a regra
linhas 226-238 da função get_instance_id:

  def get_instance_id_conn(conn) -> str:
      # 0. Env override em dev/test (CODEX rodada 3 — coerência com
      #    get_instance_id(session)).
      env_id = os.environ.get("PICSAUDE_INSTANCE_ID")
      if env_id:
          env_modo = os.environ.get("PICSAUDE_ENV", "dev")
          if env_modo == "prod":
              raise RuntimeError(
                  "PICSAUDE_INSTANCE_ID env var não pode ser usada em "
                  "PICSAUDE_ENV=prod."
              )
          return _validar_uuid_v4(env_id)

      # 1. SELECT primeiro (caso comum) — código atual continua aqui
      ...

Razão: get_instance_id(session) retorna cedo quando env override
existe em dev/test, sem persistir DB/arquivo. Sem este passo no
_conn, dev com PICSAUDE_INSTANCE_ID=X + transação clínica pode
persistir valor diferente de X no DB.

--------------------------------------------------
AJUSTE 3 (P2-B) — Split SQLite/PG sem RETURNING em SQLite
--------------------------------------------------

Arquivo: app/instance.py — função get_instance_id_conn

Substituir o INSERT idempotente atual por branches sem RETURNING
em SQLite:

  if _is_sqlite_conn(conn):
      # SQLite nativo NÃO precisa de RETURNING (sem wrapper interceptando).
      # Compatível com SQLite < 3.35.
      sql_insert = (
          "INSERT OR IGNORE INTO meta_instalacao (chave, valor, criado_em) "
          "VALUES (?, ?, ?)"
      )
  else:
      # PG via wrapper _PgConnection: RETURNING chave evita auto-RETURNING id
      sql_insert = (
          "INSERT INTO meta_instalacao (chave, valor, criado_em) "
          "VALUES (?, ?, ?) ON CONFLICT (chave) DO NOTHING RETURNING chave"
      )
  conn.execute(sql_insert, (_CHAVE_DB, novo, agora))

Razão: RETURNING chave no caminho SQLite só existia como
defensividade contra wrapper PG. SQLite nativo não tem o wrapper —
não precisa do workaround. Reduz exigência de SQLite ≥ 3.35.

--------------------------------------------------
TESTES NOVOS (5 testes — total passa de 15 → 20)
--------------------------------------------------

Arquivo: tests/test_ledger_helper.py

Adicionar 3 testes negativos para o P1:

  def test_registrar_evento_recusa_instance_id_none(conn):
      """instance_id=None deve falhar com ValueError (não TypeError)."""
      from app.domain.ledger import registrar_evento_ledger
      with pytest.raises((ValueError, RuntimeError)):
          registrar_evento_ledger(
              conn,
              objeto_tipo="laudo",
              objeto_id=1,
              tipo_evento="laudo_arquivado",
              instance_id=None,  # type: ignore[arg-type]
          )

  def test_registrar_evento_recusa_instance_id_vazio(conn):
      """instance_id='' deve falhar."""
      from app.domain.ledger import registrar_evento_ledger
      with pytest.raises((ValueError, RuntimeError)):
          registrar_evento_ledger(
              conn,
              objeto_tipo="laudo",
              objeto_id=1,
              tipo_evento="laudo_arquivado",
              instance_id="",
          )

  def test_registrar_evento_recusa_instance_id_nao_uuid(conn):
      """String não-UUID deve falhar."""
      from app.domain.ledger import registrar_evento_ledger
      with pytest.raises((ValueError, RuntimeError)):
          registrar_evento_ledger(
              conn,
              objeto_tipo="laudo",
              objeto_id=1,
              tipo_evento="laudo_arquivado",
              instance_id="not-a-uuid",
          )

Adicionar 1 teste para P2-A (env override no _conn):

  def test_get_instance_id_conn_respeita_env_override_em_dev(
      conn, monkeypatch
  ):
      """
      Em dev/test, PICSAUDE_INSTANCE_ID curto-circuita — não toca DB.
      """
      from app.instance import get_instance_id_conn
      uuid_fixo = "11111111-1111-4111-8111-111111111111"
      monkeypatch.setenv("PICSAUDE_INSTANCE_ID", uuid_fixo)
      monkeypatch.setenv("PICSAUDE_ENV", "dev")

      iid = get_instance_id_conn(conn)
      assert iid == uuid_fixo

      # DB NÃO foi tocado
      row = conn.execute(
          "SELECT valor FROM meta_instalacao WHERE chave = ?",
          ("instance_id",),
      ).fetchone()
      assert row is None

  def test_get_instance_id_conn_recusa_env_override_em_prod(
      conn, monkeypatch
  ):
      """Em prod, PICSAUDE_INSTANCE_ID setado deve raise."""
      from app.instance import get_instance_id_conn
      monkeypatch.setenv("PICSAUDE_INSTANCE_ID", "11111111-1111-4111-8111-111111111111")
      monkeypatch.setenv("PICSAUDE_ENV", "prod")

      with pytest.raises(RuntimeError):
          get_instance_id_conn(conn)

NOTA SOBRE O TESTE 15 (compat wrapper PG): o ajuste P2-B muda o SQL
SQLite (não tem mais RETURNING). O teste 15 mocka o wrapper PG —
deve continuar verde. Se quebrar, ver se a assertiva ainda diz
"RETURNING chave em INSERT no caminho PG" (sim, mantido). Não
deve precisar de ajuste.

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Aplicar os 3 ajustes nos arquivos indicados.
2. Adicionar os 5 testes novos em tests/test_ledger_helper.py.
3. Rodar:
     pytest tests/test_ledger_helper.py -v
   Esperado: 20/20 verdes (15 antigos + 5 novos).
4. Rodar não-regressão:
     pytest tests/test_migration_4b_instance_id.py \
            tests/test_migration_regulariza_circulacao_diagnostica.py \
            tests/test_instance_id.py -v
   Esperado: 23/23 verdes.
5. Reportar output completo dos passos 3 e 4.
6. NÃO COMITAR. Engenheiro-Chefe valida e propõe commit.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- Não tocar nos routers (escopo 4D).
- Não modificar a assinatura pública de registrar_evento_ledger,
  get_instance_id_conn, get_instance_id ou registrar_outbox.
- Lifespan em main.py é a ÚNICA mudança nova fora dos arquivos
  já tocados.
- Manter os 15 testes existentes intactos (apenas adicionar 5
  novos).
```

---

## Notas para Fabiano

- O Code já implementou a 4C. Estes são **ajustes incrementais**, não nova implementação. Esperado: 5-10 minutos de trabalho.
- O **lifespan em `main.py`** é o único arquivo novo no escopo. Se o Code tiver dúvida sobre a estrutura do `main.py` (já que não é trivial), peça pra ele me trazer antes de improvisar.
- Espero **20/20 + 23/23 = 43 testes verdes**.
- Se algum dos 5 novos testes falhar, traga pra mim — pode ser detalhe de implementação do `_validar_uuid_v4` (raise pode ser `RuntimeError` ou `ValueError` dependendo do caminho).
