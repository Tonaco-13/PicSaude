# Prompt para Claude Code — TICKET 4D.2

> Cole o bloco abaixo no Claude Code (VS Code).
> Ticket aprovado pelo CODEX em 3 rodadas (7 aceitos + 1 adaptado + 0 rejeitados).
> **Predecessoras commitadas no main:** 4D.1 (`60382d2` + `0056c93`), Task #8 (`d2f016b`).

---

```
=== TICKET 4D.2 — Integrar instance_id nos ledgers de exame, laudo, agendamento e circulação diagnóstica ===

CONTEXTO

Sub-tarefa 4D.2 da Etapa 4 do plano de produção. Fecha os 4 subdomínios
restantes (após a 4D.1 ter feito o subdomínio prescrição) — substitui
INSERTs raw em *_eventos pelo helper registrar_evento_ledger,
preenchendo instance_id em todo evento novo.

Ticket completo (aprovado pelo CODEX em 3 rodadas):
  backend/docs/tickets/TICKET-4D-2-LEDGER-INSTANCE-ID-SUBDOMINIOS.md

LEIA O TICKET INTEIRO ANTES DE COMEÇAR. Este prompt é só o resumo
operacional — todas as decisões arquiteturais, mapas detalhados e
critérios estão lá.

CLASSE (CLAUDE.md §10): core (toca ledger imutável).

DIRETÓRIO:
  /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

AMBIENTE:
  source ../.venv/bin/activate
  # Migrations da 4B já aplicadas no picsaude_test após Task #8

--------------------------------------------------
ESCOPO (13 sites SQL em 4 routers, ~36 eventos de negócio)
--------------------------------------------------

| Router | Sites SQL | Eventos via helper | Helper local |
|---|---:|---:|---|
| pedidos_exame.py | 10 | 10 (1:1) | NÃO tem helper |
| laudos.py | 1 | 11 | _evento (linha 205) |
| agendamentos.py | 1 | 8 | _gravar_evento_agendamento (linha 109) |
| circulacao_diagnostica.py | 1 | 7 | _gravar_evento (linha 163) |
| TOTAL | 13 | 36 | — |

Mapa exato de cada site (linha + tipo_evento + outbox adjacente) está
no §4 do ticket. Não improvisar — usar exatamente o que está mapeado.

--------------------------------------------------
PROCEDIMENTO (numerado conforme §9 do ticket)
--------------------------------------------------

PASSO 0 — VERIFICAÇÃO INICIAL OBRIGATÓRIA (adição §10.A)

Antes de tocar qualquer arquivo, rodar:

  for tab in pedido_exame_eventos laudo_eventos agendamento_eventos circulacao_diagnostica_eventos; do
    grep -RInI --include='*.py' --exclude-dir='__pycache__' \
      "INSERT INTO $tab" backend/app/routers/
  done

ESPERADO: 13 matches no total
  - 10 em pedidos_exame.py (linhas 304, 344, 445, 460, 633, 708, 773, 849, 883, 955)
  - 1 em laudos.py (linha 213)
  - 1 em agendamentos.py (linha 119)
  - 1 em circulacao_diagnostica.py (linha 168)

Se aparecer:
  - Contagem diferente de 13
  - Match em router fora dos 4 alvo
  - Linha diferente do mapa em §4 do ticket
→ PARAR e escalar para o Arquiteto. NÃO improvisar.

PASSO 1 — IMPLEMENTAÇÃO (ordem por router, conforme §10.C)

Para cada um dos 4 routers (sugestão de ordem: pedidos_exame →
agendamentos → circulacao_diagnostica → laudos):

  1.a  Adicionar imports:
       from app.domain.ledger import registrar_evento_ledger
       from app.instance import get_instance_id_conn

  1.b  (Se tem helper local) Migrar o HELPER PRIMEIRO:
       - Adicionar parâmetro `instance_id: str` keyword-only obrigatório
       - Substituir INSERT SQL bruto por registrar_evento_ledger(...)
       - Manter assinatura mínima (não adicionar lógica nova)

  1.c  Atualizar TODOS os callers do helper para passar instance_id:
       - get_instance_id_conn(conn) uma vez por transação clínica
       - Passar o mesmo instance_id para registrar_outbox adjacente

  1.d  Rodar pytest do router (rápido) para detectar callers órfãos:
       pytest tests/test_<router>.py -v --tb=short
       Ou se for router sem teste dedicado, rodar suíte ampla:
       pytest tests/integration/ -v --tb=short -k <router-name>

  1.e  Só avançar para o próximo router após pytest verde do atual.

REGRAS INVIOLÁVEIS (§3 do ticket):

  - get_instance_id_conn(conn) uma vez por transação clínica.
  - Mesmo instance_id em todos os eventos da transação.
  - Mesmo instance_id em registrar_outbox adjacente.
  - NÃO passar ator_tipo/ator_id nos 4 subdomínios da 4D.2
    (apenas "prescricao" tem ator no schema; helper levanta ValueError
    se outros subdomínios passarem ator).
  - NÃO adicionar outbox novo.
  - NÃO renomear eventos.
  - NÃO mudar payloads (manter exatamente o que está hoje).
  - Falha no ledger NÃO é silenciada (raise propaga e aborta a transação).

PARTICULARIDADE — agendamento_eventos é outlier:

  A tabela física usa coluna `evento` (não `tipo_evento`) e `payload`
  (não `dados_json`). O helper _LEDGER_SCHEMA da 4C já encapsula isso —
  você passa `tipo_evento=...` para o helper e ele cuida do mapping.

  Em _gravar_evento_agendamento, hoje o parâmetro local se chama
  `evento`. Passar literalmente: tipo_evento=evento ao helper central.

PARTICULARIDADE — criar_pedido_exame usa with get_tx() (CODEX rodada 3):

  Diferente da 4D.1 onde criar_prescricao usava get_conn() manual,
  criar_pedido_exame usa `with get_tx()`. Não precisa snippet especial:
  basta obter instance_id dentro do `with`, antes do primeiro evento.

PASSO 2 — VERIFICAÇÃO AUTOMATIZADA FINAL

Repetir o grep do passo 0:

  for tab in pedido_exame_eventos laudo_eventos agendamento_eventos circulacao_diagnostica_eventos; do
    grep -RInI --include='*.py' --exclude-dir='__pycache__' \
      "INSERT INTO $tab" backend/app/routers/
  done

ESPERADO: zero matches.

Se aparecer match: site esquecido. Voltar e migrar.

PASSO 3 — TESTES OBRIGATÓRIOS

NOVO ARQUIVO: backend/tests/integration/test_4d2_instance_id_ledger.py

Setup CRÍTICO (igual padrão da 4D.1): usar SQLite tmp_path + alembic
upgrade head para garantir coluna instance_id nos modelos.

13 testes mínimos (5 happy + 5 multi-evento + 3 ledger+outbox):

Happy-path por endpoint (5):
  1. test_pedido_emitido_tem_instance_id
       POST /pedidos-exame → pedido_emitido com instance_id UUID v4

  2. test_laudo_criado_tem_instance_id
       POST /laudos → laudo_criado com instance_id

  3. test_agendamento_criado_tem_instance_id
       POST /agendamentos → agendamento_criado no outlier
       agendamento_eventos.evento, com instance_id

  4. test_circulacao_criada_tem_instance_id
       POST /pedidos-exame/{proto}/circulacao → circulacao_criada
       com instance_id

  5. test_pedido_fisico_dois_eventos_mesmo_instance_id
       POST /pedidos-exame/fisica → pedido_impresso +
       encerrado_localmente com mesmo instance_id

Multi-evento (invariantes transacionais — 5):
  6. test_pedido_resultado_dois_eventos_mesmo_instance_id
       Registrar resultado gera pedido_em_analise +
       resultado_registrado com mesmo instance_id

  7. test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id
       ciencia_paciente + laudo_encerrado (condicional) com mesmo
       instance_id

  8. test_laudo_fisico_dois_eventos_mesmo_instance_id
       POST /laudos/fisica → laudo_impresso + encerrado_localmente
       com mesmo instance_id

  9. test_agendamento_remarcar_tres_eventos_mesmo_instance_id
       remarcar gera agendamento_remarcado + agendamento_cancelado +
       agendamento_criado (derivado) — todos com mesmo instance_id

 10. test_circulacao_remarcar_dois_eventos_mesmo_instance_id
       circulacao_desmarcada_laboratorio + nova circulacao_criada
       com mesmo instance_id

Ledger+outbox (adição §10.B — 3):
 11. test_pedido_exame_ledger_e_outbox_compartilham_instance_id
       pedido_emitido tem mesmo instance_id no ledger e no outbox
       eventos_publicacao com objeto_tipo='pedido_exame'

 12. test_laudo_ledger_e_outbox_compartilham_instance_id
       laudo_criado tem mesmo instance_id no ledger e no outbox

 13. test_agendamento_ledger_e_outbox_compartilham_instance_id
       agendamento_criado tem mesmo instance_id no ledger e no
       outbox — IMPORTANTE: valida que o mapping do _LEDGER_SCHEMA
       preserva coerência forense para o outlier do schema

NOTA: circulação diagnóstica NÃO tem outbox adjacente, então não
precisa de teste ledger+outbox para esse subdomínio.

PASSO 4 — REGRESSÃO

Rodar:

  cd backend
  pytest tests/test_ledger_helper.py
  pytest tests/test_migration_4b_instance_id.py
  pytest tests/test_eventos_publicacao.py
  pytest tests/test_agendamentos.py
  pytest tests/test_circulacao_diagnostica.py
  pytest tests/test_circulacao_ticket54.py
  pytest tests/integration/test_4d1_instance_id_ledger.py
  pytest tests/integration/test_4d2_instance_id_ledger.py

Esperado: TODOS verdes (sem novas regressões).

Se algum teste legado falhar por causa de instance_id agora
preenchido (em vez de NULL), ajustar a expectativa: comportamento
correto pós-4D.2 é instance_id válido. Documentar essa adaptação
no reporting.

--------------------------------------------------
REPORTING
--------------------------------------------------

Ao terminar, devolva:

1. Output do passo 0 (verificação inicial — 13 matches confirmados)
2. Output do passo 2 (verificação final — zero matches)
3. Output do pytest do passo 3 (13 testes novos)
4. Output do pytest do passo 4 (regressão)
5. Lista dos arquivos modificados (caminho + número de linhas)
6. Qualquer desvio do ticket com justificativa
7. Qualquer drift latente ou bug descoberto durante a implementação
   (similar à 4D.1 onde apareceu o iniciada_em → transferida_em em
   auth.py — registrar mesmo se for fora de escopo)

NÃO COMITAR. Aguardar validação do Arquiteto.

--------------------------------------------------
CONVENÇÕES
--------------------------------------------------

- Type hints em todas as assinaturas alteradas
- Docstrings em português (português é a língua do projeto)
- Sem dependências novas (tudo já está em requirements.txt)
- Compatibilidade Python 3.10+
- Antes de qualquer `git commit`, verificar `.git/index.lock` e
  `.git/HEAD.lock` — se existirem sem processo git ativo, são
  órfãos e devem ser removidos (`rm -f .git/index.lock`). Padrão
  recorrente das últimas 3 sessões.

--------------------------------------------------
FORA DO ESCOPO (NÃO FAZER — §5 do ticket)
--------------------------------------------------

- Backfill de instance_id em eventos antigos
- Alterar os 4 models principais (Prescricao, PedidoExame, Laudo,
  Agendamento) — fica para Etapa 8 / Task #5
- Padronizar nomes físicos de colunas (evento → tipo_evento, etc.)
- Adicionar outbox novo
- Renomear eventos
- Mudar regras de estado, custódia ou semântica clínica
- Tocar nos 4 routers da 4D.1 (já estão migrados)
- Tocar em routers fora dos 4 alvo (auth.py, custodia.py, etc.)
```

---

## Notas para Fabiano

- Ticket passou por 3 rodadas CODEX antes deste prompt — está maduro. Pouco provável que apareça surpresa nova durante implementação, mas a 4D.1 ensinou que vale manter o passo 0 (verificação inicial obrigatória).
- **Tamanho previsto**: ~250 linhas de código alteradas + ~450 linhas de testes novos (13 testes E2E). Comparável à 4D.1 (~820 inserções).
- **Se Code travar em algum dos 13 testes invariantes** (especialmente o do agendamento que valida o outlier), traga pra mim antes de improvisar — pode ser issue real do `_LEDGER_SCHEMA` que precisa de atenção.
- **Reminder sobre lock:** padrão recorrente. Code deve usar `rm -f .git/index.lock` antes de cada `git commit` se houver suspeita.
