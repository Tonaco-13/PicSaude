# DIAGNÓSTICO solicitado ao Conselheiro (Fable 5) — Módulo de Exames na demo

| Campo | Valor |
|---|---|
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Conselheiro (Claude Fable 5) |
| **Data** | 2026-08-02 |
| **Assunto** | Colocar o módulo de Pedido de Exame "de pé" na demo (prescritor + laboratório) |
| **Tipo** | Pedido de diagnóstico estratégico (3 questões) |
| **Parecer técnico arquitetural** | Já emitido abaixo (§2) — Fable 5 opina sobre o §3 |

---

## §1 Resumo executivo pro Conselheiro

O módulo de exames do PicSaúde está **arquiteturalmente completo no backend** (estados, custódia, ledger imutável, ownership, PDF/QR, validação pública — 53 testes de integração), e **maduro no frontend do prescritor e do cidadão**. O que falta pra demo é **cirúrgico**: (1) a clínica não emite laudo nem registra resultado (UI interrompe o fluxo no meio), (2) não há persona demo de laboratório, (3) não há seed de exames na demo, (4) faltam endpoints de listagem pra prescritor/prestador.

**O fluxo quebra em um ponto só:** prescritor emite ✓ → cidadão recebe ✓ → clínica coleta ✓ → **clínica NÃO emite laudo ✗** → cidadão nunca recebe o resultado.

---

## §2 Diagnóstico técnico do arquiteto (factual — pra Fable 5 basear o parecer)

### 2.1 O que JÁ ESTÁ pronto (não precisa tocar)

- **Backend pedidos de exame** (`pedidos_exame.py`): emissão digital/física, agendamento, coleta, resultado, encerramento, cancelamento, PDF, QR. Custódia completa (prescritor→paciente→prestador→paciente). Ledger imutável (triggers PG). Ownership validado.
- **Backend laudos** (`laudos.py`): criar, assinar, liberar, ciência paciente/prescritor, encerrar, cancelar, PDF, QR. Custódia do laudo.
- **Backend agendamentos** (`agendamentos.py`): criar, confirmar, realizar, cancelar, não-compareceu, remarcar.
- **`prescritor.html`**: formulário de pedido completo (campos do paciente, indicação clínica com IA CID, lista de exames com IA normalização, emissão digital + física, PDF, assinatura ICP).
- **`cidadao.html`**: pedidos ativos, laudos/resultados, agendamento próprio, dar ciência, baixar PDF, circulação diagnóstica.

### 2.2 O que FALTA (os 4 gaps)

**Gap 1 — `clinica.html` não emite laudo nem registra resultado (gargalo).**
- `renderizarItens` (`clinica.html:1433`) mostra só `<span class="laudo-aguardo">Aguardando laudo</span>` estático quando item está `coletado`.
- Os endpoints existem no backend (`POST /pedidos-exame/{proto}/itens/{id}/resultado` em `pedidos_exame.py:974`; `POST /laudos` em `laudos.py:317`; `POST /laudos/{proto}/liberar` em `laudos.py:651`) — **a UI não os chama**.
- **Magnitude:** médio. É trabalho de frontend (Kimi 3).

**Gap 2 — Sem persona demo de laboratório.**
- `_PERSONAS` (`demo.py:39`) só tem prescritor/dispensador/dispensador_norte/paciente/admin.
- `_papeis_demo_disponiveis` (`config_publico.py:27`) retorna `["prescritor","dispensador","paciente"]`.
- `clinica.html` hoje loga como `dispensador` (`clinica.html:881`); banner diz "esta tela não tem persona demo" (`clinica.html:458`).
- `seed_demo.py:88` tem a constante `CLINICA = {cnpj: '11222333000181', nome: 'Clínica Demo'}` mas com comentário "Ainda não gera prestador semeado".
- **Magnitude:** pequeno. **Decisão pendente: (a) reusar `dispensador` ou (b) introduzir `prestador_exame` — ver §3.Q1.**

**Gap 3 — Sem seed de exames na demo.**
- `seed_demo.py` não cria nenhum pedido de exame, laudo ou agendamento. As tabelas existem mas nascem vazias.
- Pra demonstrar o fluxo, é preciso emitir pedidos manualmente via API.
- **Magnitude:** médio. É trabalho de backend (meu). Inclui decidir estados iniciais (1 pedido `emitido`, 1 `agendado`, 1 `resultado_disponivel`, 1 laudo `liberado`).

**Gap 4 — Sem endpoints de listagem pra prescritor e prestador.**
- Só existe `GET /paciente/pedidos-exame` (`auth.py:446`). Não há `GET /prescritor/pedidos-exame` nem fila pra laboratório.
- Consequência: prescritor não vê histórico de pedidos que emitiu (o painel hoje só lista receitas); laboratório só vê pedido se digitar o protocolo manualmente.
- **Magnitude:** médio. É trabalho de backend (meu).

### 2.3 Achado adjacente (fora de escopo, registro)

- O `docs/picsaude_ddl_postgres_v1.sql` está **desatualizado** — não contém as tabelas de exame (só 8 tabelas pré-Ticket 15). Fonte de verdade atual é a migration Alembic `037d38d98806_baseline_schema_manual.py`. **Não usar o DDL legado como referência de schema.**

---

## §3 Questões ao Conselheiro (Fable 5)

### Q1 — Papel da clínica na demo: reusar `dispensador` ou introduzir `prestador_exame`?

**Contexto:** A clínica hoje loga como `dispensador`. O `seed_dev.py:19` documenta `laboratório` como "role futuro". Pra por a clínica de pé:

- **(a) Reusar `dispensador`:** a persona demo de clínica usa a role `dispensador` existente. **Pró:** zero `core`, funciona hoje. **Contra:** sobrecarrega semanticamente o papel (dispensador de farmácia vs. laboratório); pode confundir auditabilidade; futura separação vira migração.
- **(b) Introduzir `prestador_exame`:** nova role. **Pró:** semântica correta, alinha com a arquitetura documentada (AGENTS.md §7: "Custódia: prescritor → paciente → prestador_exame → paciente"). **Contra:** toca RBAC (`core`), exige revisão central, ajustar gates de role em todos os endpoints de exame, mais trabalho.

**Pergunta ao Conselheiro:** qual opção você recomenda pra **esta fase da demo**, considerando o trade-off "velocidade agora vs. dívida depois"? Há uma terceira via que estou perdendo?

### Q2 — Escopo da demo de exames: mínimo viável ou fluxo completo?

**Contexto:** O fluxo completo é: prescritor emite → cidadão recebe → clínica agenda → clínica coleta → **clínica emite laudo** → cidadão dá ciência. O Gap 1 (UI de laudo na clínica) é o gargalo.

**Duas estratégias:**

- **(M) Mínimo viável:** a demo mostra prescritor emitindo + cidadão recebendo + clínica agendando/coletando. O laudo fica **mockado no seed** (um laudo `liberado` pronto, sem a clínica emitir pela UI). A UI de emissão de laudo fica pra fase seguinte. **Pró:** demo no ar mais rápido; a clínica mostra valor (receber/agendar/coletar) sem o trabalho mais pesado.
- **(C) Completo:** implementa a UI de laudo na clínica agora. Fluxo ponta-a-ponta real. **Pró:** demonstração honesta do ciclo sanitário completo. **Contra:** mais trabalho de frontend (Kimi 3), pode atrasar a demo.

**Pergunta ao Conselheiro:** qual estratégia (M ou C) você recomenda? Vale a pena mostrar ciclo completo, ou mínimo viável com laudo mockado no seed é suficiente pra desta fase?

### Q3 — Risco arquitetural: introduzir exames na demo sem limpar o `ddl_postgres_v1.sql` desatualizado?

**Contexto:** Descobri que o `docs/picsaude_ddl_postgres_v1.sql` está desatualizado (só tem 8 tabelas, não inclui as 10+ de exame/laudo/agendamento). A fonte de verdade é a migration Alembic. Esse desalinhamento é uma dívida latente: alguém pode usar o DDL legado como referência e achar que exames não existem.

**Pergunta ao Conselheiro:** isso é um risco que deve ser tratado **agora** (atualizar/remover o DDL legado como parte deste trabalho) ou é dívida separada que não bloqueia a demo de exames?

---

## §4 O que o Conselheiro NÃO precisa decidir (já é decisão do arquiteto ou de produto)

- Implementação técnica dos endpoints de listagem (Gap 4) — minha.
- Estrutura do seed de exames (Gap 3) — minha, depois da estratégia (Q2).
- UI de laudo na clínica (Gap 1) — Kimi 3, depois da estratégia (Q2).
- Decisão final sobre Q1/Q2/Q3 — **Fabiano** (martelo), após parecer do Conselheiro.

---

## §5 Fluxo esperado

1. **Fable 5** emite parecer sobre Q1, Q2, Q3 (este documento).
2. **GLM-5.2** (arquiteto) ratifica ou pede ajuste; redige specs/tickets de backend (Gap 3 + Gap 4 + possível role).
3. **Fabiano** dá o martelo final sobre Q1/Q2/Q3.
4. **Kimi 3** recebe handoff de frontend (Gap 1 + persona demo + index.html).
5. Implementação em paralelo (backend + frontend) onde independente.

---

## §6 Resolução — parecer recebido e ratificado (2026-08-02)

**Veredito do Conselheiro:** VERDE com condições.

| Questão | Resposta Fable 5 | Ratificação arquiteto | Tickets gerados |
|---|---|---|---|
| **Q1** | (a) reusar `dispensador` com CNPJ próprio + contrato de saída | ✅ Ratificado. Terceira via elegante — separa auditoria por estabelecimento sem custo de migração de dado resetável. | `TICKET-CORE-ROLE-PRESTADOR-EXAME` (agendado, gatilho = piloto real) |
| **Q2** | (M) mínimo viável, com 3 condições | ✅ Ratificado. Especialmente condição 2 (mock sinalizado) — alunos viram bug-reporters se mock silencioso. | `TICKET-SEED-EXAMES-DEMO` (spec completa, aguarda martelo) · `TICKET-UI-MOCK-SINALIZADO-CLINICA` (condição 2) |
| **Q3** | Tratar agora — lápide no DDL legado | ✅ Ratificado, com ajuste: **header tombstone** em vez de esvaziar (prescrição ainda é referência válida; só exames faltam). | Aplicado em `docs/picsaude_ddl_postgres_v1.sql` (header de obsolescência parcial) |

**Condições incorporadas:**
1. Seed com laudo `liberado` → já estava na spec (`DEMO-LAUDO-0001`). ✅
2. Mock sinalizado na UI → `TICKET-UI-MOCK-SINALIZADO-CLINICA` (Kimi 3).
3. (C) como ticket seguinte do Kimi 3 → formalizado como fase seguinte (UI de emissão de laudo), não futuro indefinido.
4. Persona clínica com CNPJ próprio → incorporada ao seed (`_garantir_usuario` + `_garantir_prestador`).

**Aguarda:** martelo do Fabiano sobre Q1/Q2/Q3.

---

*Diagnóstico preparado pelo arquiteto de backend. Parecer do Conselheiro recebido e ratificado (§6). Aguarda martelo do Fabiano.*
