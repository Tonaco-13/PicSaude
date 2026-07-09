# Handoff — Cowork como ARQUITETO · rumo à paridade v27 da demo

> Documento de passagem de bastão. Cole/aponte isto para o **Cowork** (máquina Air,
> ativa durante a viagem). Escrito pelo engenheiro (code/MS, Mac mini) em 2026-07-09,
> logo após publicar o ciclo mínimo do dispensador.

---

## 1. Seu papel a partir de agora

**Você (Cowork) é o ARQUITETO.** Não implementa — **desenha**: escreve specs, tickets,
contratos de estado, ordem de execução, define o gap e as fatias. Você segura o
**norte do produto** (paridade v27) e o **portão dos invariantes** (CLAUDE.md).

| Papel | Quem | Faz |
|---|---|---|
| **Arquiteto** | **Cowork (você)** | specs, tickets, ordem, gap v27, guarda de invariantes |
| **Conselheiro** | **Z AI** | revisa cada spec/ticket contra invariantes e UX; parecer verde/nota/bloqueio |
| **Engenheiro** | code/MS | implementa, testa contra PG, abre PR, roda o gate |
| **Auditor** | Jules | audita cada PR core/module de forma independente (pós-commit) |
| **Dono** | Fabiano | decide produto, dispara ultra-review, testa manual, autoriza merge |

Regra de ouro herdada: **backend antes de frontend, sempre.** Nada de UI de feature
que não tenha endpoint real. O v27 (`cidadao.txt` / `dispensador.txt` /
`prescritor.txt`) é a **spec de UX/fluxo**, não o alvo de implementação — o alvo é o
**ciclo rodando sobre o backend real** (ledger, custódia, estados), **nunca** voltando
ao localStorage nem mockando feature ausente.

---

## 2. Realidade das duas máquinas (viagem)

- **Air = máquina ATIVA** durante a viagem. **Mac mini = CONGELADO** até a volta.
- **Código resolve-se por git.** No Air, antes de tudo: `git fetch && git checkout main && git pull`. A cópia veio em `feat/circulacao-fase4-frontend @ efa583f`, que está **ATRÁS** — o `main` já está em **`fc7417d`** (Fase 4 mergeada) com o fix da data. Trabalhe a partir do `main` atualizado.
- **Banco SQLite NÃO faz merge.** Se você escrever dados no Air e no mini, não há reconciliação. Air é a fonte da verdade dos dados durante a viagem; o `.venv` precisa ser recriado no Air (caminhos do mini). O banco clínico da demo se regenera com `seed_demo.py` — prefira **reseed** a copiar `.db`.
- Como arquiteto você escreve **docs/tickets** (texto) — isso flui limpo por git, sem conflito de banco.

---

## 3. Onde estamos (o que JÁ está publicado)

Ciclo mínimo do dispensador **no ar** (`main` + vitrine Render):

**login demo → entra na farmácia com CNES verificado → dispensar parcial → estornar (saldo reposto) → comprovante COMPRADOR × PACIENTE → histórico de retenções.**

Cravado no backend (não reabrir — são invariantes ratificados):
- **Estorno é objeto sanitário DERIVADO e imutável** (`estornos`, `origem_dispensacao_id`, evento `estorno_registrado`) — **nunca** transição `dispensado→estornado`. Saldo efetivo = Σ dispensado − Σ estornado. Ver `docs/tickets/TICKET-ESTORNO-OBJETO-DERIVADO.md` + CLAUDE.md §2.
- **Auto-retenção (T1.5)**: em demo, dispensar item não-retido auto-retém E emite `custodia_transferida` (auto-retenção sem o evento = bug, CLAUDE.md §2). Em produção → 409 `item_nao_retido`. Transferência é atômica (fecha antes de abrir).
- **Comprador ≠ paciente**: `dispensacoes.comprador_nome/comprador_documento` (nullable), comprovante mostra COMPRADOR × PACIENTE. PII minimizada (só nome+documento, nunca endereço). Todas as 4 rotas que tocam comprador exigem role.

PRs mergeados: #83 (Fase 1), #84 (Fase 2 backend), #87 (hotfix deploy), #85 (audit), #86 (Fase 4 frontend). Plano vivo: `docs/PLANO_DEMO_CIRCULACAO.md` (bloco STATUS no topo).

---

## 4. O ALVO — paridade v27 completa (o gap)

A demo v27 tem **3 módulos** wired ao backend real. Hoje só o núcleo do dispensador
está no ar. O gap, por módulo:

### 4a. Dispensador — completar o v27
- **Campo comprador na UI da fila.** Hoje o modal de lote NÃO coleta comprador → no fluxo da fila comprador cai como paciente. O backend já aceita; falta a UI coletar (nome + documento) e passar no dispensar.
- **Devolução ao prescritor** — **decisão de produto pendente** (Fabiano). Hoje só devolução ao paciente. O endpoint `dispensador→prescritor` existe no backend; a UI foi removida por decisão de escopo. **Não reabrir sem despacho.** Se voltar: resolver antes o gotcha do painel do prescritor (§4c).
- **Relatório consolidado (print) + SNGPC CSV** (era o T8, cortado). Backend de relatório existe (`/relatorios/dispensacoes.{csv,pdf}` travado ao CNPJ do JWT); falta a fatia consolidada/SNGPC e o botão.
- Devolução integral sem baixa; re-apresentação fracionada A→B fina na UI.

### 4b. Cidadão (`cidadao.txt`) — trazer ao backend real
Carteira de receitas, **token de apresentação** (já existe `tokens_apresentacao`),
transferência de custódia à farmácia, devolução ao médico, **solicitação de estorno**.
Nível v27, wired — nada de localStorage.

### 4c. Prescritor (`prescritor.txt`) — trazer ao backend real
Emissão, **caixa de correções/devoluções** e histórico. **Gotcha conhecido a resolver:**
`prescritor.html` não faz polling e cai em **fallback silencioso ao localStorage** se a
chamada ao backend falhar → devolução "não chega" ao médico. Foi a raiz do "devolvi ao
prescritor mas não chegou". Qualquer trabalho aqui precisa resolver polling + fallback.

---

## 5. Sua primeira entrega como arquiteto

1. **Escolher a próxima fatia** (recomendo: **fechar o dispensador v27** antes de abrir cidadão/prescritor — menor risco, completa um módulo inteiro). Fatia sugerida de arranque: **campo comprador na UI da fila** (backend pronto, é frontend puro, fecha uma lacuna real de UX). Confirmar com Fabiano.
2. **Escrever o(s) ticket(s)** no padrão do `docs/tickets/` — cada um: classe da taxonomia (CLAUDE.md §10), invariantes tocados, contrato de estado, critério de aceite, checklist NUCLEO_SANITARIO se for module/core.
3. **Passar pelo Z AI (conselheiro)** antes de mandar implementar — parecer verde/nota/bloqueio.
4. **Despachar ao engenheiro (code/MS)** com ordem e escopo fechados. Backend antes de frontend.

Se a fatia for **cidadão** ou **prescritor**, ela é **module/core** → checklist
NUCLEO_SANITARIO + portão obrigatório. Não deixe virar "clonar o .txt": o alvo é o
contrato de estados + custódia + ledger por trás de cada tela.

---

## 6. Réguas de processo (aprendidas neste arco — não repetir os erros)

- **Reproduza o deploy, não confie no gate sozinho.** O gate rodava migrations mas nunca o `seed_demo.py` que o `predeploy.sh` roda contra a PG de prod — um INSERT quebrou em produção (#84). Fix + **agora o gate roda o predeploy (seed) contra PG**. Todo caminho que a prod executa tem que estar no gate.
- **`database.py` na PG anexa `RETURNING id`** a todo INSERT sem RETURNING → quebra em tabela sem `id` (ex.: `estabelecimentos_cnes`). Use RETURNING explícito.
- **[PII-EXAUSTIVIDADE]** (`docs/LEARNINGS.md`): toda mudança que toca coluna PII lista TODAS as rotas + auth de cada; nenhuma pública. CPF/documento em rota pública é problema regulatório, não técnico.
- **PG ≠ SQLite**: datetime volta como objeto (não ISO string); Boolean com literal inteiro passa em SQLite e quebra na PG. Testar o caminho 2xx contra PG.
- **Auditoria ≠ self-check**: para interpretação arquitetural, Jules (independente) é obrigatório; para fato factual ("rota X é pública?"), code+grep basta.
- **`prescricao_custodia` NÃO está deprecated** — o histórico (T6) lê de `dispensacoes`/`estornos` por dívida técnica registrada (`backend/docs/DIVIDA-TECNICA.md`, custodia.py:766: reabertura na dispensação parcial não emite `custodia_transferida`). Ao mexer em custódia, ler essa dívida antes.

---

## 7. Ponteiros

- Norte + gap: **este arquivo** + `docs/PLANO_DEMO_CIRCULACAO.md` (STATUS no topo).
- Invariantes: `CLAUDE.md` (§1–10), `docs/NUCLEO_SANITARIO.md`, `backend/app/domain/states.py`.
- Spec de UX v27: `cidadao.txt` / `dispensador.txt` / `prescritor.txt` (protótipo — fluxo, não implementação).
- Dívida: `backend/docs/DIVIDA-TECNICA.md`. Aprendizados: `docs/LEARNINGS.md`.
- Frontend atual: `dispensador.html` (ciclo mínimo wired). Backend: `backend/app/routers/{dispensacoes,custodia,dispensadores}.py`.

**Rodar a demo local** (para de-riscar antes de despachar):
```bash
cd backend
docker run -d --name pg -e POSTGRES_USER=picsaude -e POSTGRES_PASSWORD=picsaude \
  -e POSTGRES_DB=picsaude -p 5434:5432 postgres:15
export DATABASE_URL=postgresql://picsaude:picsaude@localhost:5434/picsaude
export PICSAUDE_ENV=stg PICSAUDE_DEMO_MODE=true \
  PICSAUDE_JWT_SECRET=demo-secret-local-suficientemente-longo
alembic upgrade head && python3 seed_demo.py
uvicorn app.main:app --host 127.0.0.1 --port 8099
# http://127.0.0.1:8099/dispensador.html  (entra sozinho como Farmácia Demo)
```

---

**Primeira ação esperada de você (Cowork):** confirmar a fatia de arranque com Fabiano
e escrever o primeiro ticket da Fase 5. Nada a re-decidir sobre o que já está publicado.
