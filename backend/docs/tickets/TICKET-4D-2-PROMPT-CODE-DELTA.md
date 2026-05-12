# Prompt-delta para Claude Code — TICKET 4D.2 (3 fixes pré-commit)

> Cole o bloco abaixo no Claude Code (VS Code).
> Aplica 3 ajustes pequenos identificados pelo Arquiteto+Fabiano na
> validação pós-implementação. Trabalho prévio: 12 passed + 1 xfailed
> + 164 verdes regressão — após estes fixes, esperado **13 passed**
> + regressão verde.

---

```
=== TICKET 4D.2 — 3 fixes pré-commit ===

CONTEXTO

A 4D.2 está pronta para commit, exceto 3 itens identificados na
validação:

  1. Fix incidental: data_validade NULL em pedido_exame.py:421
     (bug latente — mesma classe de fix da 4D.1 P1.2)
  2. Limpeza: import json órfão em agendamentos.py:24
  3. Limpeza: variável rem_eventos não-utilizada em
     test_4d2_instance_id_ledger.py:564-568

Após os 3 fixes, o xfail do test_pedido_fisico_dois_eventos pode
ser removido.

DIRETÓRIO:
  /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

NÃO comitar antes da validação do Arquiteto.

--------------------------------------------------
FIX 1 — data_validade NULL em /pedidos-exame/fisica
--------------------------------------------------

Arquivo: app/routers/pedidos_exame.py
Bug: linha ~421 passa data_validade=NULL no INSERT, mas o schema
do model (app/models/pedido_exame.py:28) declara
  data_validade = Column(String(10), nullable=False)

Em PostgreSQL: NotNullViolation. Em produção, o endpoint /fisica
está quebrado. Mesma classe dos bugs latentes corrigidos como fix
incidental na 4D.1 (auth.py iniciada_em + created_at).

Aplicar fix mínimo de schema (sem mudar lógica clínica):

1. No topo do arquivo, garantir import:
     from datetime import date, timedelta
   (verificar se date e timedelta já estão importados; se sim,
   não duplicar; se não, adicionar)

2. Em criar_pedido_exame_fisico, ANTES do INSERT em pedidos_exame
   (linha ~415), calcular data_validade igual o endpoint digital
   faz — usar o mesmo prazo (verificar criar_pedido_exame digital
   para confirmar o cálculo; provavelmente hoje + 30 dias):

     data_validade = (date.today() + timedelta(days=30)).isoformat()

   IMPORTANTE: confirme o prazo usado pelo endpoint digital antes
   de hardcodar. Se for outro valor (ex: 60 dias), use o mesmo.
   Se houver uma constante ou função utilitária para isso, prefira.

3. Substituir no INSERT:
     # antes:
     VALUES (..., 'encerrado_fisico', 'fisico', ?, ?, ?, NULL, ?)
     # depois:
     VALUES (..., 'encerrado_fisico', 'fisico', ?, ?, ?, ?, ?)
   E adicionar `data_validade` na tupla de params, na posição
   correspondente.

4. Adicionar comentário inline citando o fix:
     # Ticket 4D.2 (rodada 4): fix incidental — data_validade era
     # NULL mas schema é NOT NULL. Mesma classe do fix da 4D.1 §4.7
     # P1.2 (auth.py prescricao_custodia).

--------------------------------------------------
FIX 2 — Import json órfão em agendamentos.py
--------------------------------------------------

Arquivo: app/routers/agendamentos.py
Linha: 24

Diff:

     from __future__ import annotations

  -  import json
     import uuid
     from datetime import datetime

Razão: o uso de json estava no INSERT INTO agendamento_eventos
manual (linha 119 antes da 4D.2), que foi substituído pelo helper.
Verificação automatizada confirmou que não há mais uso de json. no
arquivo.

--------------------------------------------------
FIX 3 — Variável rem_eventos não-utilizada
--------------------------------------------------

Arquivo: tests/integration/test_4d2_instance_id_ledger.py
Linhas: 564-568

Trecho atual:

  # Filtrar a transação de remarcação (últimos 3 eventos)
  rem_eventos = [e for e in eventos if e[0] in (
      "agendamento_remarcado", "agendamento_cancelado",
  )] + [e for e in eventos if e[0] == "agendamento_criado"
        and e == eventos[-1]]
  # Os 3 da remarcação devem ter mesmo iid
  eventos_remarcacao = eventos[-3:]

A variável `rem_eventos` é calculada mas nunca usada — o que é
usado para a asserção é `eventos_remarcacao = eventos[-3:]`.

Remover o bloco morto:

  -  # Filtrar a transação de remarcação (últimos 3 eventos)
  -  rem_eventos = [e for e in eventos if e[0] in (
  -      "agendamento_remarcado", "agendamento_cancelado",
  -  )] + [e for e in eventos if e[0] == "agendamento_criado"
  -        and e == eventos[-1]]
     # Os 3 da remarcação devem ter mesmo iid
     eventos_remarcacao = eventos[-3:]

--------------------------------------------------
FIX 4 — Remover xfail do test_pedido_fisico_dois_eventos
--------------------------------------------------

Arquivo: tests/integration/test_4d2_instance_id_ledger.py
Local: decorator @pytest.mark.xfail(strict=True) acima de
test_pedido_fisico_dois_eventos_mesmo_instance_id

Após o FIX 1 acima, o teste deve passar. Remover o decorator
@pytest.mark.xfail completo (junto com o comentário/motivo).

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Aplicar FIX 1 em pedido_exame.py (data_validade)
2. Aplicar FIX 2 em agendamentos.py (remover import json)
3. Aplicar FIX 3 em test_4d2 (remover rem_eventos)
4. Aplicar FIX 4 em test_4d2 (remover @xfail do teste 5)
5. Rodar suíte 4D.2:
     pytest tests/integration/test_4d2_instance_id_ledger.py -v
   Esperado: 13/13 passed (sem xfail)
6. Rodar regressão (mesma lista do reporting anterior):
     pytest tests/test_ledger_helper.py \
            tests/test_migration_4b_instance_id.py \
            tests/test_eventos_publicacao.py \
            tests/test_agendamentos.py \
            tests/test_circulacao_diagnostica.py \
            tests/test_circulacao_ticket54.py \
            tests/integration/test_4d1_instance_id_ledger.py \
            tests/integration/test_4d2_instance_id_ledger.py
   Esperado: todos verdes (sem xfailed agora)
7. Rodar verificação automatizada novamente (não-regressão):
     for tab in pedido_exame_eventos laudo_eventos \
                agendamento_eventos circulacao_diagnostica_eventos; do
       grep -RInI --include='*.py' --exclude-dir='__pycache__' \
         "INSERT INTO $tab" app/routers/
     done
   Esperado: zero matches
8. Reportar:
   - Output dos passos 5, 6, 7
   - Lista de arquivos modificados nesta rodada
9. NÃO COMITAR. Aguardar validação final do Arquiteto.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- FIX 1 deve usar a MESMA fórmula/constante de data_validade que o
  endpoint digital (criar_pedido_exame). Não inventar prazo.
- Não tocar em outros arquivos além dos 3 listados.
- Não mudar assinaturas públicas.
- Verificar `.git/index.lock` antes de qualquer git (padrão
  recorrente das últimas sessões).
```

---

## Notas para Fabiano

- **Fix 1 é o coração desta rodada.** Os outros 2 são limpeza.
- Antes de aplicar o fix do `data_validade`, peça pro Code **confirmar o prazo** usado pelo endpoint digital — se for `today() + 30`, ótimo; se for outro valor (60 dias, 90 dias, ou uma constante `VALIDADE_PADRAO_DIAS`), usar o mesmo. **Não inventar prazo arbitrário.**
- Tamanho previsto: **< 15 linhas** total de mudança nos 3 arquivos.
- Espera-se **13/13 testes verdes** na 4D.2 (sem xfail) + regressão limpa.
- Após Code reportar verde, eu valido e proponho os 2 commits canônicos da 4D.2.
