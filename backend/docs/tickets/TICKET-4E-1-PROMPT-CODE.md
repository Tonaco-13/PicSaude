# Prompt para Claude Code — TICKET 4E.1

> Cole o bloco abaixo no Claude Code (VS Code).
> Ticket aprovado pelo Arquiteto após 3 rodadas (0, 0.5 Code, 1 CODEX).
> 18 pontos aceitos + 1 adaptado + 0 rejeitados.
> **Predecessoras commitadas no main:** 4D.1 (`60382d2` + `0056c93`), 4D.2 (`3db4060` + `79f2f4f`), Task #8 (`d2f016b`), OTP fix (`5fa6902` + `a44582b`).

---

```
=== TICKET 4E.1 — Testes E2E consolidados da Etapa 4 (instance_id canônico) ===

CONTEXTO

Sub-tarefa 4E.1 da Etapa 4 do plano de produção. Fecha a etapa com
cobertura E2E transversal entre os 5 subdomínios já tocados (prescrição,
pedido_exame, laudo, agendamento, circulação diagnóstica).

Ticket completo (aprovado pelo Arquiteto após rodada 1 CODEX):
  backend/docs/tickets/TICKET-4E-1-E2E-CONSOLIDADO.md

LEIA O TICKET INTEIRO ANTES DE COMEÇAR. Este prompt é só o resumo
operacional — todas as decisões arquiteturais (contrato semântico
do instance_id, estratégia de captura do canônico, mapas de cenários)
estão lá.

CLASSE (CLAUDE.md §10): module — adiciona testes E2E novos; NÃO altera
código de produção.

DIRETÓRIO:
  /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

AMBIENTE:
  source ../.venv/bin/activate
  # Migrations da 4B já aplicadas; tests/integration/ usa PostgreSQL
  # picsaude_test real com SAVEPOINT por request.

--------------------------------------------------
ESCOPO — 5 cenários obrigatórios + 1 opcional
--------------------------------------------------

OBRIGATÓRIOS:
  C1   Cadeia clínica completa em uma sessão de paciente
       (prescrição → pedido → agendamento → coleta → laudo + atomização)
  C3   Cadeia diagnóstica (pedido → agendamento → coleta → laudo)
  C4   Remarcação derivada preserva invariantes
  C5   Smoke test agregado nos 5 ledgers (pedido_A e pedido_B separados)
  C5b  Override PICSAUDE_INSTANCE_ID em dev (NOVO obrigatório rodada 1)

OPCIONAL (só se sobrar tempo após os 5 verdes):
  C6   Coerência ledger+outbox em cadeia multi-objeto (sem circulação)

NOVO ARQUIVO:
  backend/tests/integration/test_4e_e2e_consolidado.py

Estimativa: 260–310 linhas (sem C6); até 340 linhas com C6.

--------------------------------------------------
CONTRATOS CRÍTICOS (não improvisar — vêm da rodada 1 CODEX)
--------------------------------------------------

1. instance_id é marca d'água da INSTALAÇÃO, não da transação.
   Em uma única instância PicSaúde, TODOS os eventos têm o MESMO
   instance_id. Ver §3 do ticket completo.

2. meta_instalacao NÃO está populado antes da 1ª transação clínica
   nos testes de integração: conftest.py:37 desliga o
   _lifespan_bootstrap. A linha só aparece quando a primeira chamada
   a registrar_evento_ledger executa get_instance_id_conn(conn).

   Por isso C1/C3/C4/C5/C6 capturam instance_id_canonico DEPOIS do
   1º POST que grava ledger:

     # 1. POST que grava em algum *_eventos
     proto = client.post(...).json()["protocolo"]

     # 2. AGORA sim ler o canônico
     instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(outer_conn)

   Ou ler direto de qualquer *_eventos recém-criado — ambos dão
   o mesmo valor por I2.

3. C5b é EXCEÇÃO: usa monkeypatch.setenv("PICSAUDE_INSTANCE_ID", ...)
   e compara contra UUID forçado conhecido pelo teste, SEM ler
   meta_instalacao (override por env não toca o DB — contrato testado
   em test_ledger_helper.py:674).

4. eventos_publicacao NÃO tem coluna `protocolo`. O outbox usa
   objeto_id. Queries no outbox usam:

     SELECT instance_id FROM eventos_publicacao
      WHERE objeto_tipo = %s AND objeto_id = %s

   NUNCA usar WHERE protocolo = %s em eventos_publicacao.

5. C5 precisa de DOIS pedidos de exame:
   - pedido_A: vira agendamento (itens transitam pendente → agendado)
   - pedido_B: item permanece pendente, usado para circulação
     (POST /pedidos-exame/{proto}/circulacao exige item pendente)

6. C1/C3: laudo deve usar `pedido_protocolo` apontando ao pedido
   anterior — garante cadeia clínica real (router laudos.py:100 grava
   pedido_id quando informado).

7. C4: usar evento esperado + origem_agendamento_id como asserção
   primária. NÃO usar `criado_em < 1s` (frágil, P3.2 CODEX).
   Endpoint: POST /agendamentos/{protocolo}/remarcar com
   payload {"data_hora": "2026-05-25T14:00:00"} (padrão idêntico ao
   já exercitado em test_4d2:465).

8. Atomização no C1 (cobre "múltiplas transações no mesmo protocolo"):
   POST /prescricoes/{proto_prescricao}/tokens/atomizar com
   _override_role("paciente") e payload {"validade_minutos": 60}.
   NÃO precisa fazer fluxo completo de dispensação atomizada
   (4D.1 já cobre).

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

PASSO 0 — VERIFICAÇÃO INICIAL OBRIGATÓRIA

Antes de tocar qualquer arquivo:

  cd backend

  # (a) Confirmar guardrail da 4D — nenhum INSERT manual reintroduzido
  for tab in prescricao_eventos pedido_exame_eventos laudo_eventos \
             agendamento_eventos circulacao_diagnostica_eventos; do
    grep -RInI --include='*.py' --exclude-dir='__pycache__' \
      "INSERT INTO $tab" app/routers/
  done
  # Esperado: zero matches

  # (b) Confirmar que o arquivo novo ainda não existe
  test ! -f tests/integration/test_4e_e2e_consolidado.py && echo OK

Se qualquer um falhar, parar e escalar para o Arquiteto.

PASSO 1 — CRIAR ARQUIVO + HELPERS LOCAIS

Criar tests/integration/test_4e_e2e_consolidado.py com:

  a) Docstring de módulo conforme §5.1 do ticket, citando:
     - app/instance.py (contrato semântico)
     - app/domain/ledger.py (helper)
     - DATA-PROTECTION.md §4.2 (marca d'água da instalação)
     - este ticket
     - Estratégia "ler instance_id após 1ª transação"

  b) Imports:
     from __future__ import annotations
     import uuid
     from contextlib import contextmanager
     from tests.integration.conftest import (
         SEED_PACIENTE_CPF, SEED_PACIENTE_NOME,
         SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME,
         obter_token_prescritor,
     )

  c) Helpers locais (cópia de test_4d2_instance_id_ledger.py — NÃO
     fazer import cruzado entre arquivos de teste):
     - _headers(token: str) -> dict
     - _eh_uuid_v4(s) -> bool
     - _override_role(role: str, sub: str = "test") (context manager)
     - _instance_id_canonico_apos_primeira_transacao(outer_conn) -> str
       (conforme §5.3 do ticket — lê de meta_instalacao após a 1ª
       transação ter populado a linha)

  d) Payloads canônicos (cópia ou consolidação local):
     - _PAYLOAD_PRESCRICAO (mesmo padrão de test_4d1)
     - _PAYLOAD_PEDIDO_A, _PAYLOAD_PEDIDO_B (diferenciar pacientes
       ou itens para clareza)
     - _PAYLOAD_LAUDO (com pedido_protocolo passado dinamicamente)
     - _PAYLOAD_AGENDAMENTO

PASSO 2 — IMPLEMENTAR C1 (cadeia clínica completa + atomização)

def test_cadeia_clinica_completa_preserva_instance_id(
    client, outer_conn, seed_usuario, seed_paciente, ...
):
    token = obter_token_prescritor(client, seed_usuario)

    # 1) POST /prescricoes (1ª transação — popula meta_instalacao)
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO,
                    headers=_headers(token))
    assert r.status_code == 201
    proto_prescricao = r.json()["protocolo"]

    # 2) Capturar canônico AGORA
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )
    assert _eh_uuid_v4(instance_id_canonico)

    # 3) POST /pedidos-exame
    # 4) POST /agendamentos vinculado ao pedido
    # 5) Realizar agendamento (verificar endpoint exato contra
    #    agendamentos.py — pode ser PATCH /agendamentos/{proto}/realizar
    #    ou outro path)
    # 6) POST /laudos com pedido_protocolo apontando ao pedido criado em (3)
    # 7) POST /prescricoes/{proto_prescricao}/tokens/atomizar
    #    com _override_role("paciente") e {"validade_minutos": 60}

    # Asserções:
    #   I1+I2 nos 4 ledgers (prescricao_, pedido_exame_, agendamento_,
    #     laudo_eventos): SELECT DISTINCT = 1 linha = instance_id_canonico
    #   I3 no outbox usando objeto_tipo + objeto_id (NUNCA protocolo!)
    #   Coerência clínica: laudo.pedido_id aponta ao pedido criado em (3)

Rodar:
  pytest tests/integration/test_4e_e2e_consolidado.py::test_cadeia_clinica_completa_preserva_instance_id -v

Só avançar para C3 quando C1 estiver verde.

PASSO 3 — IMPLEMENTAR C3 (cadeia diagnóstica)

def test_cadeia_diagnostica_preserva_instance_id(...)

  1) POST /pedidos-exame (1ª transação)
  2) Capturar instance_id_canonico
  3) POST /agendamentos vinculado
  4) Realizar agendamento
  5) POST /laudos com pedido_protocolo apontando ao pedido (1)

  Asserções:
    I1+I2 nos 3 ledgers
    I5 explícito: SELECT evento, instance_id FROM agendamento_eventos
       (outlier — coluna `evento`, não `tipo_evento`)
    Coerência: laudo.pedido_id = pedido_id

PASSO 4 — IMPLEMENTAR C5 (smoke agregado, com pedido_A + pedido_B)

def test_smoke_agregado_5_ledgers_um_instance_id(...)

  1) POST /prescricoes (1ª transação)
  2) Capturar instance_id_canonico
  3) POST /pedidos-exame (pedido_A — para agendamento)
  4) POST /pedidos-exame (pedido_B — item permanece pendente)
  5) POST /agendamentos vinculado ao pedido_A
  6) POST /laudos
  7) POST /pedidos-exame/{proto_pedido_B}/circulacao
     (cria circulação sobre pedido_B com item pendente — CRÍTICO)

  Asserção crítica:
    SELECT COUNT(DISTINCT instance_id) FROM (
        SELECT instance_id FROM prescricao_eventos
        UNION ALL SELECT instance_id FROM pedido_exame_eventos
        UNION ALL SELECT instance_id FROM laudo_eventos
        UNION ALL SELECT instance_id FROM agendamento_eventos
        UNION ALL SELECT instance_id FROM circulacao_diagnostica_eventos
    ) AS uniao
    → Esperado: 1
    → Valor único == instance_id_canonico
    → UUID v4 válido

  Validar adicionalmente:
    COUNT(*) WHERE instance_id IS NULL = 0 em cada ledger

PASSO 5 — IMPLEMENTAR C4 (remarcação)

def test_remarcacao_derivada_preserva_instance_id(...)

  1) POST /agendamentos (1ª transação)
  2) Capturar instance_id_canonico
  3) POST /agendamentos/{protocolo}/remarcar com
     {"data_hora": "2026-05-25T14:00:00"}
     → resposta retorna protocolo_novo

  Asserções (robustas — P3.2 CODEX):
    SELECT DISTINCT instance_id FROM agendamento_eventos
     WHERE agendamento_id IN (original, derivado)
    → 1 linha = instance_id_canonico, UUID v4 válido

    SELECT origem_agendamento_id FROM agendamentos
     WHERE id = agendamento_derivado_id
    → igual ao id do original

    Vocabulário de eventos esperado:
      'agendamento_criado' presente
      'agendamento_remarcado' OU 'agendamento_cancelado' presente
      (vocabulário exato em agendamentos.py:506-537)

    NÃO usar `criado_em < 1s` como asserção primária.

PASSO 6 — IMPLEMENTAR C5b (override PICSAUDE_INSTANCE_ID — OBRIGATÓRIO)

def test_override_instance_id_env_var(
    client, outer_conn, seed_usuario, seed_paciente, monkeypatch
):
    INSTANCE_ID_FORCADO = "deadbeef-dead-4eef-beef-deadbeefcafe"

    monkeypatch.setenv("PICSAUDE_ENV", "dev")
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", INSTANCE_ID_FORCADO)

    token = obter_token_prescritor(client, seed_usuario)

    # Executar 3-5 fluxos curtos que toquem ledgers distintos
    client.post("/prescricoes", json=..., headers=_headers(token))
    client.post("/pedidos-exame", json=..., headers=_headers(token))
    client.post("/laudos", json=..., headers=_headers(token))

    # Comparar DIRETO contra UUID forçado — NÃO ler meta_instalacao
    for tabela in [
        "prescricao_eventos", "pedido_exame_eventos", "laudo_eventos",
    ]:
        cur = outer_conn.cursor()
        cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
        rows = cur.fetchall()
        if rows:
            assert rows[0][0] == INSTANCE_ID_FORCADO
            assert _eh_uuid_v4(rows[0][0])

PASSO 7 (OPCIONAL) — IMPLEMENTAR C6 (ledger+outbox em cadeia)

Só se C1-C5b estiverem todos verdes e sobrar tempo.

def test_ledger_outbox_multiobjeto_compartilham_instance_id(...)

  Cadeia transversal: prescrição + pedido_exame + laudo + agendamento
  (NÃO incluir circulação — sem outbox adjacente)

  Para cada row em eventos_publicacao com objeto_tipo IN
    ('prescricao', 'pedido_exame', 'laudo', 'agendamento'):
      Buscar instance_id correspondente no *_eventos do mesmo
      objeto_tipo, comparando objeto_id (outbox) com protocolo (ledger).
      Asserir igualdade ao instance_id_canonico.

PASSO 8 — VERIFICAÇÃO AUTOMATIZADA FINAL

  # (a) Confirmar nenhum INSERT manual reintroduzido (idem passo 0)
  for tab in prescricao_eventos pedido_exame_eventos laudo_eventos \
             agendamento_eventos circulacao_diagnostica_eventos; do
    grep -RInI --include='*.py' --exclude-dir='__pycache__' \
      "INSERT INTO $tab" app/routers/
  done
  # Esperado: zero matches

  # (b) Confirmar nomes dos cenários
  grep -E "^def test_(cadeia_clinica|cadeia_diagnostica|remarcacao|smoke_agregado|override_instance_id_env|ledger_outbox_multiobjeto)" \
       tests/integration/test_4e_e2e_consolidado.py
  # Esperado: C1, C3, C4, C5, C5b (e opcional C6) presentes

  # (c) Confirmar que nenhuma query usa coluna errada do outbox
  grep -E "FROM eventos_publicacao.*WHERE.*protocolo" \
       tests/integration/test_4e_e2e_consolidado.py
  # Esperado: zero matches

PASSO 9 — REGRESSÃO CONSOLIDADA

  cd backend

  # Testes da Etapa 4 (5 + 1 da 4E.1)
  pytest tests/test_instance_id.py
  pytest tests/test_migration_4b_instance_id.py
  pytest tests/test_ledger_helper.py
  pytest tests/integration/test_4d1_instance_id_ledger.py
  pytest tests/integration/test_4d2_instance_id_ledger.py
  pytest tests/integration/test_4e_e2e_consolidado.py

  # Regressões em routers tocados pela Etapa 4
  pytest tests/test_eventos_publicacao.py
  pytest tests/test_agendamentos.py
  pytest tests/test_circulacao_diagnostica.py
  pytest tests/test_circulacao_ticket54.py
  pytest tests/integration/test_prescricoes.py
  pytest tests/test_atomizacao.py
  pytest tests/test_dispensacao_atomizada.py
  pytest tests/test_dispensacao_hospitalar.py

  # Smoke geral
  pytest

Esperado: TODOS verdes.

--------------------------------------------------
REGRAS INVIOLÁVEIS (§2.3 e §6.1 do ticket)
--------------------------------------------------

- NUNCA alterar arquivos em backend/app/, backend/alembic/, frontend/
- NUNCA refatorar tests/integration/conftest.py
- NUNCA criar fixtures globais novas (extensão de fixture local OK)
- NUNCA importar entre arquivos de teste (cópia local de helpers)
- NUNCA usar coluna `protocolo` em queries de eventos_publicacao
  (não existe — usar objeto_tipo + objeto_id)
- NUNCA ler meta_instalacao em C5b (override não toca DB)
- NUNCA capturar instance_id_canonico antes da 1ª transação clínica
  em C1/C3/C4/C5/C6 (meta_instalacao está vazia até esse momento)
- NUNCA testar instance_id em rows de objetos principais
  (prescricoes, pedidos_exame, laudos, agendamentos) — Etapa 8
- NUNCA alterar payloads, schemas, vocabulário de eventos

--------------------------------------------------
REPORTING
--------------------------------------------------

Ao terminar, devolva:

1. Output do PASSO 0 (verificação inicial — guardrail + arquivo ausente)
2. Output incremental de cada cenário (passos 2-7) — pytest verde
3. Output do PASSO 8 (verificação automatizada final — 3 sub-checks)
4. Output do PASSO 9 (regressão consolidada)
5. Lista de arquivos modificados (caminho + número de linhas)
6. Estimativa final de linhas adicionadas (esperado: 260-310 sem C6)
7. Qualquer desvio do ticket com justificativa
8. Qualquer drift latente ou bug descoberto durante a implementação
   (padrão das sub-tarefas anteriores — registrar mesmo se fora de escopo)
9. Se C6 foi implementado, indicar explicitamente

NÃO COMITAR. Aguardar validação do Arquiteto.

--------------------------------------------------
CONVENÇÕES
--------------------------------------------------

- Type hints em todas as assinaturas das funções de teste
- Docstrings em português (português é a língua do projeto)
- Sem dependências novas (tudo já está em requirements.txt)
- Compatibilidade Python 3.10+
- Antes de qualquer `git commit`, verificar `.git/index.lock` e
  `.git/HEAD.lock` — se existirem sem processo git ativo, são
  órfãos e devem ser removidos (`rm -f .git/index.lock`). Padrão
  recorrente das últimas 4 sessões.

--------------------------------------------------
FORA DO ESCOPO (NÃO FAZER — §2.3 do ticket)
--------------------------------------------------

- Alterar arquivos em backend/app/, backend/alembic/, frontend/
- Adicionar migration
- Cobrir Etapa 5+ (Fix B1, DEMO_MODE, Docker, deploy)
- Cobrir tokens de apresentação além da atomização mínima do C1
- Cobrir dispensação atomizada completa (4D.1 já cobre)
- Cobrir remarcação de circulação diagnóstica (4D.2 já cobre)
- Testar instance_id em objetos principais (Etapa 8)
- Alterar vocabulário de eventos, payloads, estados, custódia
- Refatorar conftest, helpers, ou tests já existentes
- Lapidar docstring de outbox.py (registrado para 4E.2 — onda de
  lapidações pós-Regra 5)
```

---

## Notas para Fabiano

- Ticket passou por 3 rodadas (0, 0.5 Code, 1 CODEX) antes deste prompt — 18 pontos integrados, 1 adaptado, 0 rejeitados. Está maduro.
- **Tamanho previsto**: 260–310 linhas de testes novos (sem C6); até 340 com C6. Sem alteração em código de produção.
- **Risco mais provável**: C5 (smoke agregado com pedido_A + pedido_B). Se Code reportar dúvida sobre o endpoint exato de "realizar agendamento" ou sobre a transição de itens do pedido (pendente → agendado → coletado), me traz antes de improvisar — pode ser issue real do contrato do router que precisa de atenção.
- **C5b é onde o `monkeypatch.setenv` pode pegar Code de surpresa**: o `monkeypatch` tem escopo de função (pytest), mas se Code colocar o `setenv` no lugar errado (depois do TestClient já ter cacheado a env), o override não funciona. Padrão correto: setenv ANTES de qualquer request.
- **Reminder sobre lock**: padrão recorrente nas últimas 4 sessões. Code deve usar `rm -f .git/index.lock` antes de cada `git commit` se houver suspeita.
- **Próximo passo do pacto após Code reportar verde**: revisão CODEX pós-implementação → commit canônico + push → 4E.1 fechada → você dispara 4E.2 (Regra 5).
