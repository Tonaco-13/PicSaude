# Prompt-delta-2 para Claude Code — TICKET 4D.2 (rodada 5)

> Cole o bloco abaixo no Claude Code (VS Code).
> Aplica 2 fixes finais identificados pelo CODEX na revisão estática
> rodada 5. Trabalho prévio: 13/13 + 165 verdes — após estes fixes,
> esperado **13/13 + 165 verdes** (sem regressão).

---

```
=== TICKET 4D.2 — RODADA 5: 2 fixes finais pré-commit ===

CONTEXTO

CODEX revisou a rodada 4 (após os 4 fixes pré-commit anteriores) e
detectou 2 itens antes de aprovar o commit:

  1. P1 — test_4d2:429 muta estado sanitário via SQL-direct
     (`UPDATE laudos SET status = 'ciencia_paciente'`) em vez de
     chamar o endpoint real. Viola o princípio "Backend é fonte de
     verdade" e contorna o próprio contrato do ledger que estamos
     testando.

  2. P2 — Imports mortos remanescentes:
     - circulacao_diagnostica.py:42 → `import json` (era usado pelo
       INSERT manual migrado para o helper)
     - test_4d2_instance_id_ledger.py → `import json`, `datetime`,
       possivelmente `pytest` (após remover @xfail na rodada 4)

DIRETÓRIO:
  /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

NÃO comitar antes da validação final do Arquiteto.

--------------------------------------------------
FIX 1 — Substituir UPDATE direto por POST /ciencia-paciente
--------------------------------------------------

Arquivo: tests/integration/test_4d2_instance_id_ledger.py
Local: dentro de test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id
       (linhas ~420-432 com o UPDATE)

Trecho atual problemático:

  # Validação alternativa via 2 eventos da rota /ciencia-prescritor
  # quando o laudo está em ciencia_paciente: forçar isso via outer_conn.
  with outer_conn.cursor() as cur:
      cur.execute(
          "UPDATE laudos SET status = 'ciencia_paciente' WHERE id = %s",
          (laudo_id,),
      )
  # Agora ciência-prescritor → encerra + 2 eventos compartilhados
  r = client.post(
      f"/laudos/{protocolo}/ciencia-prescritor", headers=_headers(token),
  )

Substituir por chamada ao endpoint real:

  # CODEX rodada 5 P1: usar endpoint real em vez de SQL-direct.
  # Manter o invariante de que o ledger é a fonte de verdade —
  # se mutarmos por SQL, contornamos o ledger que estamos testando.
  #
  # O endpoint /ciencia-paciente exige role paciente OU admin.
  # Reusamos o helper _override_role (já presente no arquivo).
  with _override_role("paciente", cpf=cpf_paciente):  # ou "admin"
      r = client.post(
          f"/laudos/{protocolo}/ciencia-paciente",
          headers=_headers(token_paciente),  # ou token_admin
      )
      assert r.status_code == 200, r.text

  # Agora ciência-prescritor → encerra + 2 eventos compartilhados
  with _override_role("prescritor"):  # voltar ao role original
      r = client.post(
          f"/laudos/{protocolo}/ciencia-prescritor", headers=_headers(token),
      )
      assert r.status_code == 200, r.text

NOTA: a implementação exata depende do padrão atual do arquivo
(como _override_role é usado em outros testes, qual token está
disponível, etc.). Adapte para usar o padrão idiomático que já
existe no arquivo de testes — NÃO inventar novo helper.

Se houver dificuldade (ex: o role 'paciente' não tem permissão para
o endpoint quando o laudo está no estado 'liberado'), verificar o
endpoint laudos.py:568+ para entender o contrato real e adaptar o
fluxo do teste de acordo (talvez precise emitir o laudo já no
estado correto, ou chamar outros endpoints intermediários).

OBJETIVO: zero SQL-direct para mutação de estado sanitário no teste.
Apenas SELECTs para verificação são aceitáveis.

--------------------------------------------------
FIX 2 — Remover imports mortos
--------------------------------------------------

Arquivo 1: app/routers/circulacao_diagnostica.py
Linha: 42

Diff:

     ...outros imports...
  -  import json
     ...próximos imports...

Verificar antes via grep:

  grep -n "json\\." app/routers/circulacao_diagnostica.py

Se zero matches no arquivo, remover. Se houver uso remanescente,
parar e escalar para o Arquiteto.

Arquivo 2: tests/integration/test_4d2_instance_id_ledger.py
Linhas: 26-29 (e possivelmente outras)

Para cada um dos imports candidatos a serem mortos:
  - `import json`
  - `from datetime import datetime`
  - `import pytest`

Rodar grep no arquivo:

  grep -n "json\\.\\|datetime(\\|datetime\\.\\|pytest\\." \
    tests/integration/test_4d2_instance_id_ledger.py

Remover apenas os que NÃO têm uso no arquivo. Se algum estiver em
uso (ex: `datetime.utcnow()`, `pytest.fixture`, `json.dumps`),
manter.

NOTA SOBRE pytest: após a remoção do @xfail na rodada 4, verificar
se `import pytest` ainda é usado por @pytest.fixture, pytest.mark.*
ou pytest.raises. Se não, remover.

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Aplicar FIX 1 (substituir UPDATE por endpoint /ciencia-paciente).
2. Rodar pytest apenas do teste afetado para confirmar verde:
     pytest tests/integration/test_4d2_instance_id_ledger.py::test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id -v
3. Aplicar FIX 2 (remover imports mortos em 2 arquivos).
4. Verificação automatizada — confirmar zero `INSERT INTO *_eventos`
   ainda:
     for tab in pedido_exame_eventos laudo_eventos \
                agendamento_eventos circulacao_diagnostica_eventos; do
       grep -RInI --include='*.py' --exclude-dir='__pycache__' \
         "INSERT INTO $tab" app/routers/
     done
   Esperado: zero matches
5. Rodar suíte completa 4D.2:
     pytest tests/integration/test_4d2_instance_id_ledger.py -v
   Esperado: 13/13 passed
6. Rodar regressão completa:
     pytest tests/test_ledger_helper.py \
            tests/test_migration_4b_instance_id.py \
            tests/test_eventos_publicacao.py \
            tests/test_agendamentos.py \
            tests/test_circulacao_diagnostica.py \
            tests/test_circulacao_ticket54.py \
            tests/integration/test_4d1_instance_id_ledger.py \
            tests/integration/test_4d2_instance_id_ledger.py
   Esperado: 165 passed, 0 failed
7. Reportar:
   - Output do passo 2, 5, 6
   - Confirmação dos imports removidos (lista com diff antes/depois)
   - Snippet final do trecho do teste após FIX 1 (para validação)
8. NÃO COMITAR. Aguardar validação final do Arquiteto.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- FIX 1: NÃO inventar novo helper. Usar o padrão idiomático já
  presente no arquivo (provavelmente `_override_role` + client.post).
- FIX 1: se o fluxo do endpoint exigir mudança no setup do teste
  (estado anterior, role, etc.), adapte SEM mudar a invariante
  testada (mesmo instance_id em 2 eventos da mesma transação).
- FIX 2: verificar uso via grep antes de remover. Se algum import
  está em uso, manter.
- Não tocar em outros arquivos.
- Verificar `.git/index.lock` antes de qualquer git (padrão
  recorrente).
```

---

## Notas para Fabiano

- **FIX 1 é o item de qualidade arquitetural.** Vai além de "limpeza" — é alinhamento com o princípio "Backend é fonte de verdade" (CLAUDE.md). Pequena mudança, ganho de coerência arquitetural significativo.
- Se o Code reportar que o endpoint `/ciencia-paciente` exige condições específicas que o teste não atende (ex: laudo precisa estar em estado X), pode haver pequena adaptação do setup do teste. **Não autorizar mudança de invariante** — só ajuste de pré-condições.
- Total previsto: **~10 linhas** de mudança (5 no FIX 1, 5 no FIX 2 espalhados).
- Esperado: **13/13 + 165 verdes** após os 2 fixes (mesmas contagens da rodada 4).
- Após Code reportar verde, eu valido e propomos os 2 commits canônicos.
