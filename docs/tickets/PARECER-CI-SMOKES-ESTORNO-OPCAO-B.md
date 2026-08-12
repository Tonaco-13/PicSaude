# PARECER — `gates-browser` vermelha: os smokes ficaram atrás da Opção B (não há código faltando)

| Campo | Valor |
|---|---|
| **De** | Engenheiro-chefe (terminal) |
| **Para** | Fabiano · Kimi (autor do despacho) · Revisor |
| **Data** | 2026-08-12 |
| **Responde a** | `DESPACHO — CI gates-browser vermelha: commitar o fix do estorno (já implementado e auditado)` |
| **Classe** | `core` (guardas executáveis de custódia/estado) — **nenhuma linha de produção alterada** |
| **Veredito** | O despacho parte de duas premissas incorretas. A CI vermelha não é código ausente: são 3 smokes escritos para o desenho **anterior** ao roteamento por motivo. |

---

## §1 Premissa 1 — "o fix nunca foi commitado" ❌

Os seis arquivos apontados como WIP solto têm **zero linhas de diferença** contra `origin/main`:

```
0 linhas de diff — backend/app/domain/states.py
0 linhas de diff — backend/app/routers/dispensacoes.py
0 linhas de diff — backend/tests/integration/test_estorno.py
0 linhas de diff — backend/tests/test_states.py
0 linhas de diff — backend/tests/integration/test_custodia_devolucao.py
0 linhas de diff — CLAUDE.md
```

O fix **foi** commitado: é o `c872b55` — *feat(estorno): devolve custódia ao cidadão no
estorno total [core] (#152)* —, mergeado em 2026-08-11 11:38.

**Por que pareceu não-commitado:** o checkout principal está na branch
`docs/handoff-2026-08-09`, **anterior** ao #152. Nessa branch o `git status` marca como
"modificado" exatamente aquilo que já entrou na `main`. É artefato de branch desatualizada,
não trabalho perdido. Antes de concluir "não commitado" a partir do `git status`, o teste é
`git diff origin/main -- <arquivo>`.

## §2 Premissa 2 — "commitar a Frente A conserta a CI" ❌

O core do estorno está **verde** no commit vermelho (`b773f10`):

| Suíte | Resultado |
|---|---|
| `test_estorno.py` + `test_custodia_devolucao.py` (PostgreSQL) | **45 passed** |
| `test_states.py` | **104 passed** |

Não há o que commitar, e commitar não mudaria os smokes.

## §3 Causa real — o teste executa à mão um passo que o #152 automatizou

Os três smokes estornam com **`desistencia_paciente`**, que pela Opção B devolve a posse ao
cidadão **dentro do próprio estorno**. Daí:

| Teste | O que fazia depois do estorno | Por que quebrou |
|---|---|---|
| `test_coer2_e2e` (fixture) | dispensador chama `/devolver {"para":"paciente"}` | `403 nao_detem_custodia` — **correto**: a posse já saiu da farmácia um passo antes |
| `test_coer2_fix` | idem | idem |
| `test_f5_b2::..._reentrada_por_estorno` | espera a receita **reaparecer na fila** | com "cidadão recupera" ela sai da fila; a reentrada do B0 §6.2 agora vale para `erro_dispensacao` / `outro` / parcial |

O 403 e a ausência na fila **são o comportamento ratificado**. Nada a corrigir em produção.

## §4 O que foi feito

Só testes — nenhuma linha de `states.py`, `dispensacoes.py` ou `CLAUDE.md` tocada.

1. **`test_coer2_e2e.py`** — o `/devolver` sai do fixture e é **substituído pela asserção do
   efeito que ele produzia**: a receita voltou à posse do cidadão. Sem isso os 4 testes
   passariam sem ninguém provar que a posse voltou. As 4 asserções finais não mudaram.
2. **`test_coer2_fix.py`** — mesma troca; a pré-condição (item em `devolvido_paciente`) passa a
   ser **conferida** via carteira, em vez de reproduzida pelo passo antigo.
3. **`test_f5_b2_ciclo_pos_dispensacao.py`** — `_estornar()` ganha o parâmetro `motivo`, e o
   cenário `reentrada` passa a usar `erro_dispensacao` — o ramo em que o B0 §6.2 vale. O
   cenário `estornada` (Escopos B/C) segue em `desistencia_paciente`, então o arquivo passa a
   exercitar **os dois ramos** do roteamento.

**Resultado:** `tests/browser` → **54 passed** (antes 48 passed, 2 failed, 4 errors).

## §5 Divergência de spec a resolver na origem

O §2 do despacho reafirma a spec v2 §3.2 com **`outro` → cidadão**. O implementado e o
`CLAUDE.md` da `main` são a **Opção B pós-CI #152**: `outro` fica no grupo que **retém**
(`dispensacoes.py:622`, `_MOTIVOS_CIDADAO_RECUPERA = {desistencia_paciente,
pagamento_nao_concluido}`).

**Fabiano ratificou a Opção B (12/08):** `outro` retém. O despacho citou a versão anterior —
vale corrigi-lo na origem para não recontaminar a próxima frente.

## §6 Dois reparos operacionais

- **O comando do §4.3 do despacho produz 28 erros espúrios.** Ele mistura `tests/test_states.py`
  (fora de `tests/integration/`) com testes de integração numa só invocação; os conftests
  colidem. Separados, tudo passa. Forma correta:
  ```bash
  pytest tests/integration/test_estorno.py tests/integration/test_custodia_devolucao.py   # PG
  pytest tests/test_states.py                                                             # unit
  ```
- **`backend/.venv` está quebrado neste Mac** (wheels arm64 num host x86_64): use `.venv-x86`.

## §7 O que este episódio ensina

O `gates-browser` só roda **no nightly e em PR que toca `.html`**. O #152 mudou
comportamento de custódia sem tocar em `.html`, entrou entre dois nightlies e ficou **6 horas
invisível** — o vermelho apareceu num PR de frontend alheio (#154) e foi lido como culpa dele.
Um `core` que muda custódia deveria disparar os smokes; vale avaliar acrescentar
`backend/app/routers/**` e `backend/app/domain/states*.py` aos paths do `gates-browser.yml`.
