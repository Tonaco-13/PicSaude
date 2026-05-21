# Relatório Jules — Revisão estática consolidada da Etapa 4 (4E.2)

> **Data:** 2026-05-21
> **Revisor:** Jules (Google Gemini) via `jules.google.com`
> **Material:** Repo `Tonaco-13/PicSaude` lido direto via GitHub, range `d8abf7e^..main -- backend/`
> **Briefing:** §4.4 do `backend/docs/tickets/TICKET-4E-BRIEFING-PARA-CODEX.md` (lente: simplicidade, legibilidade, pragmatismo, onboarding)
> **Sessão:** `https://jules.google.com/session/6289227329369843205`
> **Status:** recebido e arquivado pelo Arquiteto, aguardando integração com CODEX

---

## §1 Resumo de achados

| Severidade declarada | Quantidade |
|---|---|
| **P1** (bloqueador) | 1 |
| **P2** (relevante, não bloqueador) | 2 |
| **P3** (lapidação textual/sugestão) | 1 |
| **Total** | 4 |

**Observação Arquiteto:** A classificação de severidade do Jules é mais agressiva que a do CODEX. A leitura cruzada mostra que o "P1" do Jules é, na escala real de produção do PicSaúde, um P2 (overhead técnico não-bloqueador). Reclassificação no relatório integrado.

---

## §2 P1 Jules — Overhead de query por transação

### Achado
- **Arquivo/Linha:** `app/instance.py:382` — em `get_instance_id_conn`, no bloco "SELECT primeiro"
- **Problema:** A função executa `SELECT` em `meta_instalacao` a cada invocação. Como os routers a chamam em cada transação clínica (para propagar para ledger e outbox), há overhead de I/O em todas as transações.
- **Argumento:** `instance_id` é imutável (UUID v4 da instalação), então o I/O recorrente é injustificado.

### Sugestão Jules
Cache em memória no nível do módulo (variável `_CACHED_INSTANCE_ID = None` preenchida na primeira leitura, ou `@functools.lru_cache`). Leitura ao DB apenas uma vez por worker.

### Avaliação preliminar Arquiteto
- **Severidade real:** P2, não P1. Escala atual do PicSaúde MVP: <10 transações/s × <1ms por SELECT em PK single-row = overhead negligenciável.
- **Mérito da sugestão:** real. `lru_cache(maxsize=1)` ou variável de módulo é mudança de < 5 linhas, sem reabertura de API.
- **Caveat:** o cache precisa funcionar PER-WORKER (cada worker uvicorn tem sua memória), o que é natural com `lru_cache`. Verificar interação com testes (que rodam em processo único e podem precisar de fixture de reset entre testes — provavelmente já coberto pelo SAVEPOINT do conftest).

---

## §3 P2 Jules — Achados relevantes

### §3.1 P2-J #1 — Propagação manual nos routers (boilerplate)

- **Arquivo/Linha:** `app/domain/ledger.py:143` (assinatura) + ~34 callers em `app/routers/*.py`
- **Problema (Jules):** Routers buscam `instance_id` via `get_instance_id_conn(conn)` e passam manualmente em cada chamada de ledger/outbox. Polui camada de roteamento com preocupações de auditoria de infraestrutura. Fragilidade: dev novo esquece de passar.
- **Sugestão Jules:** Helpers `registrar_evento_ledger` e `registrar_outbox` leem variável/cache global diretamente. **Router não sabe o que é `instance_id`.**

### Avaliação preliminar Arquiteto — ⚠️ CONFLITO COM CODEX

Este achado conflita **diretamente** com o **P2-D do CODEX** (outbox.py:33 — `instance_id` opcional permite regressão silenciosa). CODEX quer tornar `instance_id` **mais explícito** (parâmetro obrigatório). Jules quer torná-lo **menos explícito** (lido do contexto).

**Posição preliminar do Arquiteto: rejeitar a sugestão Jules.**

Argumento:
1. A Etapa 4 inteira foi DESIGN de "`instance_id` é propagado explicitamente do caller". Não é boilerplate acidental — é decisão arquitetural ligada ao Princípio 2 do CLAUDE.md ("Auditoria é arquitetura"). Ler o caller fonte mostra exatamente qual `instance_id` está sendo gravado em cada evento.
2. Aceitar a sugestão Jules reabriria os 34 sites das 4D.1 + 4D.2, reverteria 4C, e exigiria nova auditoria CODEX. Custo desproporcional ao benefício.
3. O argumento de "dev novo esquece" é mitigado pelo parâmetro `keyword-only`: a chamada `registrar_evento_ledger(...)` sem `instance_id=...` levanta TypeError no import-time. Não há regressão silenciosa possível desde a 4C — exceto no `outbox.py` que o CODEX justamente apontou.

**Conclusão:** Aceitar CODEX P2-D (hardening de `outbox.registrar_outbox` para também exigir `instance_id` keyword-only) **resolve** a preocupação do Jules sobre fragilidade, sem reverter a explicitez do design.

Pendência: registrar essa decisão como **ADR (Architecture Decision Record)** futuro — explicar publicamente por que a propagação manual é design e não dívida técnica.

### §3.2 P2-J #2 — Lógica de first-boot acoplada a fluxos transacionais

- **Arquivo/Linha:** `app/instance.py:393` (lógica de INSERT e tratamento de UUID v4 no bloco "2. First boot")
- **Problema (Jules):** Função `_conn` feita para rodar em transações clínicas contém responsabilidade de "inicialização do banco no first-boot" (com concorrência + dialect-specific RETURNING vs INSERT OR IGNORE). Risco: chamada paralela nos primeiros instantes mescla transação clínica com setup global.
- **Sugestão Jules:** Ciclo de vida da app (lifespan/startup) é o único responsável por garantir first-boot via `get_instance_id(session)`. Em runtime, routers só leem da memória.

### Avaliação preliminar Arquiteto
- **Severidade real:** P3 (não P2). Em produção, `lifespan` é executado antes de qualquer request — o first-boot acontece no startup, não em runtime. O bloco no `get_instance_id_conn` é **fallback defensivo** caso o lifespan tenha sido bypassado (teste, demo).
- **Mérito da sugestão:** documentar claramente que esse INSERT é fallback, não caminho principal. Idealmente adicionar uma asserção/log que avise se o fallback for executado em prod.
- **Decisão preliminar:** aceitar como **lapidação textual + log**, não como refatoração. Em conftest.py:37 o lifespan é desabilitado intencionalmente — o fallback existe para isso.

---

## §4 P3 Jules — Lapidações

### §4.1 P3-J — Onboarding: risco de confusão semântica

- **Arquivo/Linha:** `app/domain/ledger.py` (docstring inicial) + `app/instance.py`
- **Problema:** Dev novo pode confundir `instance_id` com Request/Transaction ID porque ele aparece como parâmetro junto de variáveis transacionais.
- **Sugestão Jules:** Reforçar em caixa alta nas docstrings que `instance_id` representa Servidor/Instalação física e nunca muda na vida do banco.

### Avaliação preliminar Arquiteto
**Aceitar.** Consolidar com o CODEX P3-B (ledger.py:19 docstring "4D — ainda não implementado") em uma rodada única de lapidação textual nas docstrings de:
- `app/instance.py`
- `app/domain/ledger.py`
- `app/domain/outbox.py`

---

## §5 O que o Jules NÃO viu (zona cega da lente "pragmatismo")

Cinco achados do CODEX **não aparecem** no Jules:
- `custodia.py:616` evento genérico (P2-A CODEX)
- `assinaturas.py:323` ator_id armazena modo (P2-B CODEX)
- `auth.py:320` estado incoerente (P2-C CODEX)
- `outbox.py:33` instance_id opcional (P2-D CODEX)
- Cobertura faltante de `receituarios/hospitalares/assinaturas` (P2-E CODEX)

Isso é esperado: Jules foi instruído a olhar "complexidade desnecessária / propagação / fragilidade / performance / onboarding", não conformidade com CLAUDE.md ou cobertura de testes. **As lentes funcionaram como pares complementares** — esse é o resultado positivo do pacto Regra 5.

---

## §6 O que o CODEX NÃO viu (zona cega da lente "conformidade")

Quatro achados do Jules **não aparecem** no CODEX:
- Overhead de SELECT por transação (P1-J)
- Sugestão de cache em memória
- Acoplamento first-boot vs runtime
- Risco semântico de onboarding (parcial — CODEX viu docstring outdated, mas não a confusão Request/Transaction vs Instalação)

Isso valida o segundo revisor: CODEX está calibrado em "tem bug? cumpre CLAUDE.md?" — não em "como dói para alguém entender isso?".

---

## §7 Próximo passo

Arquiteto consolida CODEX + Jules em `TICKET-4E-2-RELATORIO-INTEGRADO.md` com:
- Classificação cruzada (✅ aceito / 🔄 adaptado / ❌ rejeitado com justificativa)
- Spec de fix por achado aceito (passada ao Code via Regra 2 ou Regra 3 dependendo do tamanho)
- ADR sobre propagação manual de `instance_id` (resposta pública à sugestão Jules P2-J #1)
