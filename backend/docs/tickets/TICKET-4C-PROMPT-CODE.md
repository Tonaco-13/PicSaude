# Prompt para Claude Code — TICKET 4C

> Cole o bloco abaixo no Claude Code (VS Code).
> O Claude Code roda localmente, faz as edições, executa pytest e reporta.

---

```
=== TICKET 4C — Helper de inserção no ledger com instance_id ===

CONTEXTO

Sub-tarefa 4C da Etapa 4 do plano de produção PicSaúde. Cria helper
centralizado de inserção no ledger imutável que recusa eventos sem
instance_id (marca d'água de rastreabilidade — DATA-PROTECTION.md §4.2).

Predecessoras commitadas no main:
  - 4A (d8abf7e): app/instance.py — get_instance_id(session)
  - 4B-prequel (2dce4f8): regulariza 3 tabelas órfãs do subdomínio
    circulação diagnóstica (revision a3f5c8d9e1b2)
  - 4B (89f064a): coluna instance_id VARCHAR(36) NULL em 10 tabelas
    (revision 4b1ce80a017d)

Ticket completo (743 linhas, aprovado pelo CODEX em 2 rodadas):
  backend/docs/tickets/TICKET-4C-HELPER-LEDGER-INSTANCE-ID.md

LEIA O TICKET INTEIRO ANTES DE COMEÇAR. Este prompt é só o resumo
operacional — as decisões arquiteturais e justificativas estão lá.

CLASSE DA MUDANÇA (CLAUDE.md §10): core (toca o ledger imutável).

DIRETÓRIO DO PROJETO:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

AMBIENTE:
  source ../.venv/bin/activate
  # SQLite local: data/pix_saude_pe.db (já populado)
  # Para testes: pytest usa SQLite em tmp_path

--------------------------------------------------
ENTREGÁVEIS (3 arquivos)
--------------------------------------------------

1. NOVO: app/domain/ledger.py
   - Constante: ObjetoSanitario = Literal["prescricao", "pedido_exame",
     "laudo", "agendamento", "circulacao_diagnostica"]
   - Constante privada: _LEDGER_SCHEMA — mapping com 5 entradas
     (ver §4.1 do ticket para o dicionário completo, incluindo o
     outlier 'agendamento' que usa 'evento' em vez de 'tipo_evento')
   - Função pública: registrar_evento_ledger(conn, *, objeto_tipo,
     objeto_id, tipo_evento, instance_id, payload=None,
     ator_tipo=None, ator_id=None) -> None

   IMPORTANTE:
   - Todos os parâmetros após `conn` são keyword-only (*)
   - instance_id é OBRIGATÓRIO (sem default — TypeError se faltar)
   - ValueError em runtime se objeto_tipo inválido
   - ValueError se ator_tipo/ator_id inconsistente com schema
     (apenas 'prescricao' aceita ator)
   - Falha em INSERT levanta exceção (NÃO silenciar — ledger é fonte
     de verdade)
   - Compatível com SQLite e wrapper _PgConnection (PostgreSQL)

2. EDIT: app/instance.py
   - Adicionar função: get_instance_id_conn(conn) -> str
   - Padrão "INSERT idempotente + SELECT autoritativo" (CODEX rodada 2):
     a) SELECT primeiro
     b) Se vazio: INSERT idempotente com RETURNING chave EXPLÍCITO
        (RETURNING só para satisfazer o wrapper _PgConnection — não
        confiar no valor retornado)
     c) SELECT autoritativo (race-safe, fonte de verdade)
   - Helper privado: _is_sqlite_conn(conn) — detecta dialeto
   - NÃO comita (caller controla a transação)
   - Ver §4.1-bis do ticket para o código completo

3. EDIT: app/domain/outbox.py
   - Adicionar parâmetro instance_id: str | None = None ao final da
     assinatura de registrar_outbox()
   - Adicionar coluna instance_id no INSERT
   - Manter retrocompatibilidade (default None)
   - Manter best-effort (try/except — não levantar)

--------------------------------------------------
TESTES OBRIGATÓRIOS (15 testes)
--------------------------------------------------

NOVO: tests/test_ledger_helper.py

Setup CRÍTICO (CODEX P2-3): NÃO usar Base.metadata.create_all().
A coluna instance_id vem só por Alembic (4B). Use:

  @pytest.fixture
  def alembic_setup(tmp_path, monkeypatch):
      db_path = tmp_path / "test_ledger.db"
      monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
      backend_root = Path(__file__).resolve().parent.parent
      cfg = Config(str(backend_root / "alembic.ini"))
      monkeypatch.chdir(backend_root)
      command.upgrade(cfg, "head")  # aplica TODA a cadeia, incluindo 4B
      return db_path

  (Padrão idêntico ao usado em test_migration_4b_instance_id.py)

Os 15 testes (ver §4.5 do ticket para descrições detalhadas):

Cobertura por subdomínio (5 — happy path):
  1. test_registrar_evento_prescricao_preenche_instance_id
  2. test_registrar_evento_pedido_exame_preenche_instance_id
  3. test_registrar_evento_laudo_preenche_instance_id
  4. test_registrar_evento_agendamento_preenche_instance_id  # outlier 'evento'
  5. test_registrar_evento_circulacao_diagnostica_preenche_instance_id

Validação de entrada (3 — negative path):
  6. test_objeto_tipo_invalido_raise_value_error
  7. test_prescricao_sem_ator_raise_value_error
  8. test_outros_subdominios_com_ator_raise_value_error

Outbox e retrocompatibilidade (2):
  9. test_outbox_aceita_instance_id_opcional
 10. test_outbox_sem_instance_id_continua_funcionando_silencioso

Invariantes transacionais (4 — adicionados pelo CODEX):
 11. test_rollback_da_transacao_remove_ledger_e_outbox
 12. test_ledger_e_outbox_recebem_o_mesmo_instance_id
 13. test_payload_none_inserido_como_dict_vazio
 14. test_first_boot_nao_antecipa_commit_de_dados_clinicos
     # Teste de regressão crítico — ver §4.5 para cenário detalhado

Compatibilidade DB (1):
 15. test_get_instance_id_conn_funciona_com_pgconnection_wrapper
     # Mock do wrapper _PgConnection — confirma que SELECT/INSERT com
     # RETURNING chave NÃO é interceptado pela auto-adição de
     # RETURNING id (linha 173 de database.py)

--------------------------------------------------
RESTRIÇÕES CRÍTICAS (NÃO VIOLAR)
--------------------------------------------------

1. Não tocar nos routers (app/routers/*.py). A integração nos endpoints
   é escopo da 4D, não da 4C. Esta sub-tarefa cria APENAS o helper.

2. Não usar Session (SQLAlchemy) na API pública do helper. O backend
   usa conn raw (get_conn() / get_tx()). Refatorar para Session
   aumentaria muito o blast radius.

3. Não tentar resolver o drift de nomenclatura entre as 6 tabelas de
   eventos (prescricao_eventos vs agendamento_eventos etc.). Encapsular
   no _LEDGER_SCHEMA. Padronização é ticket separado.

4. instance_id é parâmetro OBRIGATÓRIO do helper (sem default).
   Caller chama get_instance_id_conn(conn) UMA VEZ por transação e
   passa para ledger + outbox.

5. Falha em INSERT no ledger levanta exceção. Não silenciar (diferente
   do outbox, que segue best-effort).

6. RETURNING chave no get_instance_id_conn é só para passar pelo
   wrapper _PgConnection. NÃO confiar no valor retornado — usar SELECT
   subsequente como fonte de verdade.

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Ler o ticket inteiro:
     backend/docs/tickets/TICKET-4C-HELPER-LEDGER-INSTANCE-ID.md

2. Implementar os 3 arquivos (entregáveis acima) seguindo o ticket.

3. Rodar os 15 testes:
     pytest tests/test_ledger_helper.py -v

4. Se algum falhar, depurar e corrigir ANTES de reportar.

5. Quando todos passarem, rodar também:
     pytest tests/test_migration_4b_instance_id.py \
            tests/test_migration_regulariza_circulacao_diagnostica.py \
            tests/test_instance_id.py -v

   (Esses 28 testes existentes precisam continuar verdes — sanity
   check de não-regressão.)

6. Reportar o output completo do pytest dos passos 3 e 5
   (PASSED/FAILED por teste, contagem final, tempo).

7. NÃO COMITAR. O Engenheiro-Chefe valida o output e propõe os
   commits canônicos depois.

--------------------------------------------------
CONVENÇÕES
--------------------------------------------------

- Type hints em todas as funções públicas
- Docstrings em português, explicando o "porquê" (não só "o quê")
- Logging via logging.getLogger(__name__) — sem print()
- Sem dependências novas (usar apenas stdlib + libs já em
  requirements.txt)
- Compatibilidade Python 3.10+

--------------------------------------------------
REPORTING
--------------------------------------------------

Ao terminar, devolva:

1. Output do pytest dos 15 testes novos
2. Output do pytest dos 28 testes de não-regressão
3. Lista dos arquivos criados/modificados (caminho + número de linhas)
4. Qualquer desvio do ticket com justificativa
5. Quaisquer dúvidas que surgiram durante implementação

NÃO comite, NÃO faça push. O Engenheiro-Chefe valida primeiro.
```

---

## Notas para Fabiano

- **Não edite o prompt** antes de colar — todas as decisões já foram revisadas pelo CODEX em 2 rodadas.
- Se o Claude Code pedir esclarecimento sobre algum ponto, **pause e me traga a pergunta**. Não autorize desvios — isso protege a coerência do ticket.
- Se algum teste falhar e o Code não conseguir resolver em 2 tentativas, **traga o output para mim** antes que ele tente "consertar criativamente".
- Quando o Code reportar verde nos 15 + 28 testes, eu valido e proponho os commits canônicos (provavelmente 1 commit só — `feat(core): registrar_evento_ledger + get_instance_id_conn (4C)`).
