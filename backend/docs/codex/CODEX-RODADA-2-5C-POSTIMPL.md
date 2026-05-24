# CODEX rodada 2 — TICKET-5C (revisão pós-implementação)

> **Data:** 2026-05-24
> **Commit alvo:** `01c67fa feat(5c): autorização mínima em 11 endpoints clínicos centrais` (impl) + `b020770 docs(5c): ticket pré-impl V1-V11 com 3 ciclos CODEX integrados` (ticket)
> **Branch:** `main` (origin/main = `b020770`, em sincronia com local)
> **Pacto:** Regra 2 estrita — esta é a quarta e última rodada antes do encerramento da Etapa 5.
> **Critério de fechamento:** zero P1. P2/P3 aceitáveis (vão para §11 do ticket como dívida ou follow-up).
> **Path local do repo (CODEX):** `/Users/fabianotonacoborges/PicSaude_Dev/`

---

## §1 Contexto

Você (CODEX) já participou de três ciclos pré-impl deste ticket em 2026-05-23:

1. **Rodada 1** — revisou o esqueleto V1-V6 e retornou 2 P1 + 4 P2 + 2 P3. Achados centrais: V6 ainda tinha bypass para `de ≠ "prescritor"`, e o inventário de gap estava incompleto (V7/V8/V9 faltando).
2. **Varredura `_=Depends`** — 58 matches em `backend/app/routers/`, classificadas em A (V10 novo P1), B (5 tickets sucessores #47-51), C (admin/health/IA stateless — fora do escopo) e D (carteira do paciente — ambíguo, #51).
3. **Rodada 1.5** — promoveu **V11** (POST `/assinatura`) a P1 obrigatório porque o `usuario` já era capturado mas faltava owner check antes do upsert + evento de ledger. Adicionou 5 lapidações P2/P3 (testes baseline genéricos, custódia item-level vs global, normalize_cnpj cru, tabela de payloads expandida, grep flexibilizado).

**Todos esses 14 achados foram integrados no ticket** (§10, §10.1, §10.3, §10.5) e implementados pelo Code no commit `01c67fa`.

**Esta rodada 2 é pós-impl.** O ticket está fechado para escopo — não estamos rediscutindo design. Estamos validando que o código entregue:

(a) implementa fielmente cada um dos 11 fixes especificados em §4.1-§4.11;
(b) não introduziu regressão em outros endpoints (suite reporta 27→27 falhas pré-existentes inalteradas);
(c) não deixou bypass residual nas matrizes multi-role (V5, V6, V9) nem nos paths upsert/ledger (V10, V11);
(d) preserva o contrato de erro padronizado (`codigo` + `mensagem` em português, status 403/404 conforme §3.5).

---

## §2 Escopo de revisão — onde olhar no commit `01c67fa`

5 routers de produção tocados. Linhas pós-impl (linha do `def`):

| V | Endpoint | Arquivo:linha | Tipo | Resumo do fix entregue |
|---|---|---|---|---|
| V1 | `POST /prescricoes` | `prescricoes.py:214` | escrita+ledger | `normalize_cns(usuario["sub"]) != cns` antes de qualquer query/INSERT |
| V2 | `POST /prescricoes/fisica` | `prescricoes.py:691` | escrita+ledger | espelho de V1 |
| V3 | `GET /prescricoes/{p}/documento` | `prescricoes.py:851` | leitura | owner check inline (JOIN prescritor); 404 quando protocolo inexiste; admin passa |
| V4 | `GET /prescricoes/{p}/pdf` | `prescricoes.py:931` | leitura | owner check só p/ role `prescritor`; dispensador/admin passam direto |
| V5 | `GET /prescricoes/{p}/custodia` | `custodia.py:238` | leitura | matriz multi-role (prescritor/paciente/dispensador/admin/auditor); dispensador = histórico de participação ambulatorial |
| V6 | `POST /custodia/{p}/transferir` | `custodia.py:347` | escrita+ledger | 5 regras §3.4 (paciente rejeitado, role/payload match, ownership real, item_id IS NULL p/ dispensador, hospitalar fora) |
| V7 | `GET /prescricoes/{p}/validacao` | `validacao.py:27` | leitura | owner check só p/ role `prescritor` |
| V8 | `GET /prescricoes/{p}/assinatura` | `assinaturas.py:150` | leitura | owner check só p/ role `prescritor`; admin passa |
| V9 | `GET /dispensacoes/{id}/comprovante` | `dispensacoes.py:278` | leitura | multi-role (dispensador via CNPJ; prescritor via CNS; admin/auditor passam) |
| V10 | `POST /custodia/{p}/itens/{i}/dispensar` | `custodia.py:518` | escrita+ledger | `normalize_cnpj(usuario["sub"]) != cnpj` ANTES de qualquer SELECT/INSERT |
| V11 | `POST /prescricoes/{p}/assinatura` | `assinaturas.py:255` | escrita+ledger | owner check após `_get_meta_prescricao`, antes do INSERT/UPDATE em `prescricao_assinatura` e do evento `assinatura_registrada` |

**Outros arquivos relevantes:**

- `backend/tests/integration/test_prescricoes.py` — V1, V2, V3, V4 (122 linhas novas)
- `backend/tests/integration/test_custodia_autorizacao.py` — **NOVO** — V5, V6 (5 sub-testes), V10 (317 linhas)
- `backend/tests/integration/test_validacao.py` — **NOVO** — V7 (61 linhas)
- `backend/tests/integration/test_assinaturas.py` — **NOVO** — V8, V11 (167 linhas)
- `backend/tests/integration/test_dispensacoes.py` — **NOVO** — V9 (158 linhas)
- `backend/tests/conftest.py` — RoleClient com subs canônicos por role (16 linhas)
- `backend/tests/test_assinatura_icp.py`, `test_cnes_prescritor.py`, `test_eventos_publicacao.py`, `test_string_validacao.py` — fixtures locais realinhadas para que `usuario["sub"]` bata com `cns_prescritor` do payload (necessário porque V1 agora rejeita mismatch)

Total: 1.207 inserções, 31 deleções, 15 arquivos.

---

## §3 Perguntas direcionadas

Estas são as perguntas que esperamos que você ataque. Não precisa responder em ordem — priorize achados graves.

### §3.1 Fidelidade ao spec

- Cada um dos 11 fixes corresponde ao que §4.1-§4.11 do ticket especifica? (mesma SQL, mesma ordem de check, mesmo código de erro)
- O `codigo` e `mensagem` do payload de erro batem com a tabela §3.5 do ticket? (especial atenção a `ator_mismatch` em V6 — três mensagens diferentes possíveis)
- Os imports adicionados (`normalize_cns`, `normalize_cpf`, `normalize_cnpj` em arquivos novos) estão completos?

### §3.2 Bypass residual

- **V5:** algum role não previsto na matriz (paciente sem CPF no `sub`, dispensador hospitalar com `unidade_id` em vez de CNPJ) cai em path errado? Hospitalar é anti-escopo (§7), mas precisa retornar 403 limpo — não 500/200.
- **V6:** a regra 4 exige `item_id IS NULL AND encerrada_em IS NULL` na query do dispensador. Dispensador com custódia ATIVA da prescrição inteira mas em CNPJ diferente — rejeita? Custódia ENCERRADA da prescrição inteira no mesmo CNPJ — rejeita?
- **V9:** se a `dispensacao_id` não existir, retorna 404 — confirmar que esse 404 não vaza informação sensível e que admin/auditor não pegam o 404 cedo demais (já que pulam o check).
- **V10:** check é feito antes do `with get_tx()`. Há algum side-effect de leitura/log que ocorra antes do raise?
- **V11:** check é feito DEPOIS do `_get_meta_prescricao` (que abre tx). Se `_get_meta_prescricao` levanta 404 para protocolo inexistente, está OK — confirmar. Se levanta outra coisa (200 com `meta = None`?), há janela de escrita?

### §3.3 Rollback de escrita + ledger

Os endpoints V1, V2, V6, V10, V11 emitem evento no `prescricao_eventos` no caminho feliz. Os testes têm asserts de baseline pré/pós em:

- `prescricoes`, `prescritores`, `pacientes` (V1, V2)
- `prescricao_custodia`, `prescricao_eventos` (V6)
- `dispensacoes`, `prescricao_itens` (`status_item`), `prescricao_eventos`, `eventos_publicacao` (V10)
- `prescricao_assinatura` (COUNT + campos específicos), `prescricao_eventos`, `eventos_publicacao` (V11)

**Perguntas:**

- O 403 ocorre **antes** de qualquer INSERT que poderia escapar do rollback transacional? (V10 não está dentro do `with get_tx()` — confirmar que isso é OK e não há side-effect prévio)
- V11 está dentro do `with get_tx()` — confirmar que o rollback automático cobre tanto INSERT (cenário nova assinatura) quanto UPDATE (cenário upsert sobre assinatura existente)
- Algum evento de outbox / publicação assíncrona pode ser disparado antes do 403?

### §3.4 Regressão silenciosa em testes pré-existentes

O commit realinhou fixtures em 4 arquivos de teste (`test_assinatura_icp.py`, `test_cnes_prescritor.py`, `test_eventos_publicacao.py`, `test_string_validacao.py`) e 1 conftest (`backend/tests/conftest.py`) para que `RoleClient` carregue `sub` canônico por role (V1 agora exige match).

**Perguntas:**

- Esses realinhamentos preservam a intenção do teste original? (i.e., o `sub` antigo era genérico/sintético; o novo precisa ser CNS válido. O Code não silenciou um caso negativo por engano?)
- Há outros testes na suite que usavam o antigo `sub` sintético e agora passariam por motivo errado (false-green)?

### §3.5 Convenções (KISS / anti-escopo)

- Algum dos 11 fixes virou helper compartilhado? §3.2 do ticket diz "sem helper na primeira passada" — confirmar que ficou inline em todos.
- Algum endpoint fora dos 11 listados (especialmente nos 5 routers tocados) foi alterado por engano?
- Mudou algo em `app/auth/dependencies.py` (`require_role`)? Não deveria.

### §3.6 Higiene de schema (latente)

Durante a rodada 1.5 mencionamos que `prescricao_eventos.tipo_evento` para dispensação é `item_dispensado` (custodia.py:560). Confirmar que o code:

- Não introduziu evento novo (`dispensacao_rejeitada`?) por engano.
- O 403 não emite evento no ledger (só sucesso emite).

---

## §4 Anti-escopo (NÃO atacar nesta rodada)

- **Tickets sucessores #47-51** (exames, agendamentos, laudos, hospitalar, circulação diagnóstica, carteira paciente) — escopo fora do MVP ambulatorial, abertos como tarefas pendentes.
- **Cluster auth eventos #41**, **cluster catálogo #39**, **cluster /health/db #40**, **órfão auth_paciente #42**, **CPF-shift #35**, **Dívida B-Carteira #36**, **validator de CPF geral #44** — domínios separados, falhas pré-existentes.
- **Matriz de roles do V5** (além do mínimo §3.3) — qualquer proposta de restringir dispensador a `encerrada_em IS NULL` fica como achado P3, não mudança neste ticket.
- **Helper `require_owner_or_admin`** — só propor se duplicação for grave; ticket explicitamente escolheu inline (§3.2).
- **Refatoração de `_get_meta_prescricao`** ou `_get_prescricao_by_protocolo` — fora do escopo.
- **Refatoração de `RoleClient`** ou `require_role` — fora do escopo (mudanças em conftest são adaptação ao novo contrato V1, não refatoração).

---

## §5 Verificação automatizada (você pode rodar localmente)

Estes greps reproduzem §6 do ticket sobre o commit aplicado:

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Zero "_=Depends(require_role" nos 5 routers
grep -rn "_=Depends" backend/app/routers/prescricoes.py \
     backend/app/routers/custodia.py backend/app/routers/validacao.py \
     backend/app/routers/assinaturas.py backend/app/routers/dispensacoes.py
# Esperado: zero matches

# 2. Os 5 códigos de erro aparecem em pelo menos 1 ocorrência cada
grep -rn "prescritor_mismatch\|nao_e_dono_da_prescricao\|sem_vinculo_com_prescricao\|ator_mismatch\|nao_e_dono_da_dispensacao" backend/app/routers/
# Esperado: cada código pelo menos 1x; ator_mismatch múltiplas

# 3. Suite focal — 17/17 verdes
cd backend
pytest tests/integration/test_prescricoes.py \
       tests/integration/test_custodia_autorizacao.py \
       tests/integration/test_validacao.py \
       tests/integration/test_assinaturas.py \
       tests/integration/test_dispensacoes.py \
       -v -k "v1_ or v2_ or v3_ or v4_ or v5_ or v6_ or v7_ or v8_ or v9_ or v10_ or v11_"

# 4. Suite completa — 27 falhas pré-existentes (declaradas), nenhuma regressão
pytest -q
```

O Code já rodou (1) (2) (3) (4) e reportou: zero `_=Depends`, 5 códigos presentes, 17/17 verdes, 27→27 falhas (zero regressão) + 40 passes novos.

Sua função: **reproduzir e cruzar** com leitura estática do diff.

---

## §6 Formato esperado da sua resposta

Padrão dos ciclos anteriores: `P1 / P2 / P3` numerados, com:

```
N. [Severidade] <Vulnerabilidade ou arquivo:linha>
   <descrição do achado>
   Decisão sugerida: <fix | follow-up | aceitar como dívida>
```

Critério de fechamento da Etapa 5:

- **Zero P1** → fechamos 5C. Eu preencho §11 do ticket com o resumo dos achados P2/P3 (aceitos ou diferidos), atualizo `PLANO-PRODUCAO-V2.md`, `CLAUDE.md`, `PROMPT-OPUS-4.7-ARQUITETO.md`, e a Etapa 5 está formalmente encerrada.
- **≥ 1 P1** → Code abre follow-up commit antes de fechar. Volta para você uma rodada 2.5.

P2 aceitos viram §11; P2 diferidos viram task pendente com origem rastreada. P3 normalmente vai para §11 como lapidação ou viram backlog.

---

## §7 Histórico cumulativo de aceitação (até agora)

Para você calibrar o que é alto-sinal vs ruído:

| Rodada | P1 | P2 | P3 | Aceitos integralmente |
|---|---|---|---|---|
| 5C rodada 1 (pré-impl) | 2 | 4 | 2 | 7/7 |
| 5C varredura | 1 (V10) + 5 tickets | — | — | integral |
| 5C rodada 1.5 (pré-impl) | 1 (V11) | 3 | 2 | 6/6 |

Sua taxa de aceitação no 5C é 100%. Isso significa que (a) seus achados têm sido alto sinal, e (b) você pode ser exigente nesta rodada 2 — não há custo em apontar P2/P3 sutis.

---

*Aguardando seu retorno. Obrigado.*
— Arquiteto (Opus 4.7)
