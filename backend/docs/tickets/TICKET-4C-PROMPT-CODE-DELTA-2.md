# Prompt-delta-2 para Claude Code — TICKET 4C (rodada 4)

> Cole o bloco abaixo no Claude Code (VS Code).
> Aplica 3 ajustes da rodada 4 do CODEX antes do commit final.
> **Trabalho prévio: 43/43 verdes** — não reverter, apenas adicionar/ajustar.

---

```
=== TICKET 4C — RODADA 4: 3 ajustes antes do commit ===

CONTEXTO

Você já implementou a 4C completa (helper + lifespan + P1+P2-A+P2-B da
rodada 3). 43/43 testes verdes na suíte-alvo. CODEX revisou e detectou
1 regressão FORA da suíte-alvo + 2 pontos menores.

REGRESSÃO REPRODUZIDA POR CODEX:
  pytest tests/test_eventos_publicacao.py::TestRegistrarOutbox::test_insere_evento_corretamente
  → falha porque registrar_outbox agora insere instance_id, mas o
    model EventoPublicacao não tem essa coluna; create_all() em
    fixtures legadas não cria a coluna; INSERT quebra silenciosamente.

CAUSA:
  4B adicionou instance_id via Alembic em 10 tabelas. Mas os models
  SQLAlchemy não foram alinhados. Em ambientes com Alembic (banco real,
  testes de migration), funciona. Em ambientes com create_all (fixtures
  de teste legadas), a coluna NÃO existe.

NÃO reverter o trabalho prévio. Apenas aplicar os 3 ajustes abaixo.

DIRETÓRIO:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

--------------------------------------------------
AJUSTE 1 (P1) — Alinhar 6 models com a coluna instance_id
--------------------------------------------------

Adicionar `instance_id = Column(String(36), nullable=True)` em cada
um dos 6 models abaixo (são os que registrar_evento_ledger + outbox
escrevem):

  app/models/evento_publicacao.py
  app/models/prescricao_evento.py
  app/models/pedido_exame_evento.py
  app/models/laudo_evento.py
  app/models/agendamento_evento.py
  app/models/circulacao_diagnostica_evento.py

Posição: ao final das colunas existentes, antes de quaisquer
relationships().

Exemplo (evento_publicacao.py — ajuste similar nos outros 5):

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
      # NOVO (4C): marca d'água da instância PicSaúde — preenchida pelo
      # helper registrar_evento_ledger / registrar_outbox via
      # get_instance_id_conn(). Nullable=True alinhado com a migration
      # 4B (4b1ce80a017d) — preserva registros pré-instance_id.
      instance_id  = Column(String(36), nullable=True)

NOTA SOBRE TIPO: use String(36) para alinhar com a migration 4B
(VARCHAR(36)). Se algum dos 6 models já usa Text/String com outro
tamanho em outras colunas, use o estilo dominante do arquivo MAS
mantenha 36 como tamanho. Em SQLite ambos colapsam para TEXT;
no PostgreSQL String(36) gera VARCHAR(36) idêntico ao Alembic.

NÃO atualizar os 4 models de objetos sanitários principais nesta
rodada (Prescricao, PedidoExame, Laudo, Agendamento). 4C não os
escreve — fica para 4D ou Etapa 8.

--------------------------------------------------
AJUSTE 2 (P2) — Env override no conftest raiz para isolar lifespan
--------------------------------------------------

Arquivo: backend/conftest.py (raiz, já existe)

Adicionar fixture autouse session-scope que seta
PICSAUDE_INSTANCE_ID + PICSAUDE_ENV=test. Lifespan então vê env
override em modo test → curto-circuita → não toca DB real.

Adicionar APÓS a fixture _disable_rate_limit_in_tests existente:

  _INSTANCE_ID_TESTE = "11111111-1111-4111-8111-111111111111"


  @pytest.fixture(autouse=True, scope="session")
  def _isolate_instance_id_in_tests():
      """
      Isola o lifespan do app durante testes:

      - PICSAUDE_INSTANCE_ID setado → lifespan + get_instance_id_conn
        vêem env override e curto-circuitam (não tocam DB).
      - PICSAUDE_ENV=test → desabilita o guard de prod (que rejeitaria
        env override).

      Sem isto, with TestClient(app): roda lifespan, que abre
      SessionLocal global e toca data/pix_saude_pe.db (não o tmp do
      teste). CODEX rodada 4 P2.
      """
      os.environ["PICSAUDE_INSTANCE_ID"] = _INSTANCE_ID_TESTE
      os.environ["PICSAUDE_ENV"] = "test"
      yield
      os.environ.pop("PICSAUDE_INSTANCE_ID", None)
      os.environ.pop("PICSAUDE_ENV", None)

NOTA: se algum teste existente já manipula PICSAUDE_INSTANCE_ID ou
PICSAUDE_ENV via monkeypatch, ele sobrescreve esta fixture
session-scope durante seu escopo (ordem normal do pytest). Os
testes test_env_override_* da 4A funcionam com monkeypatch
explícito — verifique que continuam verdes.

--------------------------------------------------
AJUSTE 3 (P3) — Atualizar docstring obsoleta de get_instance_id_conn
--------------------------------------------------

Arquivo: app/instance.py — função get_instance_id_conn

A docstring atual (linhas ~329-343) diz que env override e arquivo
.instance_id permanecem APENAS na variante get_instance_id(session).
Isso é falso desde a rodada 3 (P2-A): get_instance_id_conn agora
TAMBÉM respeita PICSAUDE_INSTANCE_ID em dev/test.

Também remover/ajustar menção a "INSERT idempotente com RETURNING
chave" se descrever genericamente — após rodada 3 P2-B, SQLite NÃO
usa mais RETURNING (só o caminho PG via wrapper).

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

1. Aplicar P1 nos 6 models.
2. Aplicar P2 no backend/conftest.py.
3. Aplicar P3 na docstring de instance.py.
4. Rodar a suíte-alvo da 4C (deve continuar 20/20 + 23/23 = 43 verdes):
     pytest tests/test_ledger_helper.py \
            tests/test_migration_4b_instance_id.py \
            tests/test_migration_regulariza_circulacao_diagnostica.py \
            tests/test_instance_id.py -v
5. Rodar a regressão original do CODEX:
     pytest tests/test_eventos_publicacao.py -v
   Esperado: 23/23 verdes (era 22/23 com 1 falha).
6. Rodar sanity em outros arquivos que usam TestClient (P2):
     pytest tests/test_assinatura_icp.py \
            tests/test_prestadores.py \
            tests/test_ia_documental.py \
            tests/test_ia_cid.py -v
   Esperado: continuam verdes (sem novas regressões introduzidas).
7. Reportar output completo dos passos 4, 5 e 6.
8. NÃO COMITAR. Engenheiro-Chefe valida e propõe commit final.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- Não tocar nos 4 models de objetos sanitários principais
  (Prescricao, PedidoExame, Laudo, Agendamento) — escopo 4D/Etapa 8.
- Não tocar nos routers (escopo 4D).
- Não modificar assinaturas públicas de registrar_evento_ledger,
  get_instance_id_conn, get_instance_id ou registrar_outbox.
- Não modificar testes existentes (apenas adicionar fixture nova
  no conftest raiz, sem mexer nos 20 + 23 testes da 4C).
```

---

## Notas para Fabiano

- **Escopo conservador no P1:** apenas 6 models (que `registrar_evento_ledger` + outbox escrevem). Os 4 principais (`Prescricao`, etc.) ficam pra 4D — o ticket é claro sobre isso. Não vamos reabrir 4C para resolver TODO o drift.
- **P2 elegante:** reutiliza o env override que **a própria rodada 3 P2-A já implementou**. Sem precisar criar mecanismo novo de "test mode" no lifespan.
- **Ganho colateral do P1:** uma vez alinhados, os 6 models permitem que `init_tables.py` (que ainda existe como ferramenta de bootstrap) crie tabelas com `instance_id` direto, alinhando dev/test/prod.
- Se algo do P2 quebrar (alguma fixture do projeto que assume sem env override), Code deve trazer pra mim antes de improvisar.

Espero **43 (4C) + 23 (eventos_publicacao) + N (TestClient samples) = ~80+ verdes** ao final.