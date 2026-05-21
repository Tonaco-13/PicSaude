# Relatório CODEX — Revisão estática consolidada da Etapa 4 (4E.2)

> **Data:** 2026-05-21
> **Revisor:** CODEX (OpenAI)
> **Material:** `git diff d8abf7e^..6b5dbed -- backend/` (14.325 linhas, 64 arquivos, +12.416 −510)
> **Briefing:** §4.3 do `backend/docs/tickets/TICKET-4E-BRIEFING-PARA-CODEX.md` (revisão de diff, não redação de ticket)
> **Modo:** revisão estática apenas, sem executar testes
> **Status:** recebido e arquivado pelo Arquiteto, aguardando relatório Jules para integração

---

## §1 Resumo de achados

| Severidade | Quantidade |
|---|---|
| **P1** (bloqueador) | 0 |
| **P2** (relevante, não bloqueador) | 5 |
| **P3** (lapidação textual/sugestão) | 3 |
| **Total** | 8 |

Zero P1: a Etapa 4 entrega o que se propôs. Os achados são pontuais e tratáveis sem reabrir a arquitetura.

---

## §2 P1 — Bloqueadores

Nenhum P1 encontrado.

Nos arquivos revisados, os callers de `registrar_evento_ledger(...)` passam `instance_id=...`, e os wrappers locais de `laudos`, `agendamentos`, `circulacao`, `custodia` e `hospitalares` recebem/propagam `instance_id` corretamente.

---

## §3 P2 — Achados relevantes

### §3.1 P2-A — `custodia.py:616` — evento genérico `item_devolvido`

`devolver_item` grava evento genérico `item_devolvido`, mas `CLAUDE.md §2` define eventos separados: `item_devolvido_paciente` e `item_devolvido_prescritor`. Além disso, o ator fica hardcoded como `dispensador` / `sistema`, apesar do endpoint aceitar `dispensador` e `prescritor`.

**Sugestão CODEX:** escolher `tipo_evento` conforme `payload.para` e usar o usuário real do `Depends(require_role(...))` para `ator_tipo/ator_id`. Se a intenção for manter `item_devolvido`, atualizar formalmente o vocabulário em `CLAUDE.md`.

### §3.2 P2-B — `assinaturas.py:323` — `ator_id` armazena modo de assinatura

`assinatura_registrada` preserva `ator_tipo="prescritor"`, mas usa `ator_id=meta.get("assinatura_modo") or "sem_modo"`. Isso transforma modo de assinatura em identidade do ator, enfraquecendo a trilha auditável.

**Sugestão CODEX:** alterar a assinatura do endpoint para capturar `usuario=Depends(require_role(...))` e gravar `ator_id=usuario["sub"]` quando disponível.

### §3.3 P2-C — `auth.py:320` — `devolver_prescritor` deixa estado incoerente

`devolver_prescritor` marca itens `pendente` como `devolvido_prescritor`, mas mantém `prescricoes.status='pendente'`. Como `devolvido_prescritor` é terminal em `CLAUDE.md §5b`, isso deixa objeto ativo com itens terminais.

**Sugestão CODEX:** validar com o Arquiteto se esse fluxo deve recalcular status pelo helper de domínio, ou se `pendente` aqui representa "em posse do prescritor". Hoje o teste cobre só persistência do evento, não a coerência de estados.

### §3.4 P2-D — `outbox.py:33` — `instance_id` opcional permite regressão silenciosa

`registrar_outbox` aceita `instance_id=None` silenciosamente. Os callers atuais revisados passam `instance_id`, mas o helper permite regressão futura: ledger correto, outbox com `NULL`.

**Sugestão CODEX:** sem refatorar core agora, adicionar verificação estática/teste que falhe se algum `registrar_outbox(` em `app/routers` não passar `instance_id=`.

### §3.5 P2-E — Superfície migrada sem cobertura explícita 4D/4E.1

Há superfície real migrada que não aparece explicitamente na cobertura 4D.1/4D.2/4E.1 por endpoint:
- `receituarios.py:398` — `receituarios_gerados`, `receituarios_numerados`, `receituario_emitido`
- `hospitalares.py:351` — `dispensacao_hospitalar_registrada`
- `assinaturas.py:324` — `pdf_assinado_pades`, `assinatura_registrada`

**Sugestão CODEX:** acrescentar testes focados pequenos ou uma checagem estática de regressão para esses callers, sem ampliar o E2E consolidado.

---

## §4 P3 — Lapidações textuais

### §4.1 P3-A — `outbox.py:6` — docstring contradiz decisão 4D

Docstring diz que todo router que inserir em `*_eventos` deve chamar `registrar_outbox()`. Isso contradiz a decisão da 4D de não criar outbox novo para eventos sem publicação prevista.

**Sugestão CODEX:** trocar para "quando houver evento publicável / outbox previsto".

**Nota Arquiteto:** este achado já estava pré-identificado em §4.6 do `TICKET-4E-BRIEFING-PARA-CODEX.md`. Confirmação do CODEX.

### §4.2 P3-B — `ledger.py:19` — docstring desatualizada

Docstring ainda diz "4D — ainda não implementado", mas 4D.1/4D.2 já foram implementadas.

**Sugestão CODEX:** atualizar para "Contrato aplicado pelos routers desde 4D".

### §4.3 P3-C — `test_4e_e2e_consolidado.py:480` — C5 frágil com rows pré-backfill

C5 verifica `instance_id IS NULL` nos ledgers inteiros. É bom como smoke de higiene, mas fica frágil se o banco de teste carregar rows históricos pré-backfill.

**Sugestão CODEX:** documentar explicitamente que é checagem global de higiene, ou filtrar pelos objetos/protocolos criados no próprio teste.

**Nota Arquiteto:** confirma o drift de 210 rows `instance_id IS NULL` em `eventos_publicacao` já registrado em §4.6 do briefing.

---

## §5 Observação técnica

Os links de arquivo no relatório original do CODEX apontam para `~/Desktop/PicSaude_Dev.broken.20260521/...` porque CODEX rodou contra o clone local do Mac mini antes da movimentação do repo para `~/PicSaude_Dev/`. O conteúdo dos arquivos é idêntico (clone fresh do mesmo HEAD `6b5dbed`), então os achados são válidos — apenas os paths nos relatórios precisam ser normalizados para `backend/app/routers/...` ao serem operacionalizados pelo Code.

---

## §6 Próximo passo

Aguardar relatório Jules sobre o mesmo material para integrar ambos em `TICKET-4E-2-RELATORIO-INTEGRADO.md` com classificação cruzada (✅ aceito / 🔄 adaptado / ❌ rejeitado) e spec de fix por achado.
