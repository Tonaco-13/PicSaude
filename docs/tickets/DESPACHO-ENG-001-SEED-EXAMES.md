# DESPACHO ENG-001 — Seed de exames → Engenheiro (backend)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-001 |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) |
| **Data** | 2026-08-02 |
| **Martelo** | Fabiano homologou Q1/Q2/Q3 (2026-08-02) |
| **Documento-fonte** | `docs/tickets/TICKET-SEED-EXAMES-DEMO.md` |

---

## §1 O que fazer

Implementar o seed de exames em `backend/seed_demo.py`, seguindo a spec em `docs/tickets/TICKET-SEED-EXAMES-DEMO.md`.

**Resumo da entrega:**
- Criar `_garantir_pedido_exame_ativo(conn)` — `DEMO-EXAME-0001` (ativo, hemograma, aguardando agendamento).
- Criar `_garantir_laudo_demo(conn)` — `DEMO-EXAME-0002` (resultado disponível) + `DEMO-LAUDO-0001` (liberado, ciência pendente).
- Adicionar, no `main()` do seed, o **prestador laboratório** + os dois blocos best-effort (mesmo padrão da receita e do atestado).
- Importar `timedelta` do `datetime` (hoje só vem `date, datetime, timezone`).

## §2 Decisões já tomadas (não reabrir)

- **Q1=(a):** a clínica loga como role `dispensador` (compartilhada), com CNPJ próprio (`11222333000181`). Use `_garantir_usuario(conn, CLINICA["cnpj"], CLINICA["nome"], "dispensador")`. A role `prestador_exame` é ticket core separado (`TICKET-CORE-ROLE-PRESTADOR-EXAME`, agendado) — **não introduza a role nova aqui.**
- **Q2=(M):** o laudo entra **mockado no seed** (`liberado`), sem exigir UI de emissão. A UI de laudo na clínica é ticket seguinte do Kimi 3.
- A constante `CLINICA` já existe em `seed_demo.py:88` — use-a; remova o comentário "Ainda não gera prestador semeado".

## §3 Invariantes (não-negociáveis)

- **R1:** nenhuma mudança no backend de endpoints, ledger, estados, custódia. Só `seed_demo.py`.
- **Idempotente:** protocolos sentinela (`DEMO-EXAME-0001`, `DEMO-EXAME-0002`, `DEMO-LAUDO-0001`) protegem re-execução.
- **Best-effort:** cada bloco isolado em try/except + rollback próprio — uma falha não aborta o seed já commitado.
- **Estados válidos:** respeitar a máquina em `states_exame.py` / `states_laudo.py`. Snapshot, não replay.
- **Custódia + ledger consistentes:** objeto sem cadeia é órfão (AGENTS.md §2/§3). Cada objeto tem sua custódia + eventos.

## §4 Critérios de aceite (do ticket-fonte §6)

1. Após rodar `PICSAUDE_DEMO_MODE=true python3 seed_demo.py`, as tabelas de exame/laudo/custodia/eventos contêm os objetos sentinela.
2. Idempotente (re-executar = no-op).
3. Best-effort (falha isolada).
4. Cidadão vê `DEMO-EXAME-0001` em "Pedidos de Exame Ativos" e `DEMO-LAUDO-0001` em "Laudos / Resultados".
5. Clínica busca `DEMO-EXAME-0001` por protocolo e vê o pedido.
6. Estados + custódia + ledger consistentes.
7. Roda em PG (Render) e SQLite (local).

## §5 ⚠️ Validação obrigatória antes de fechar

O `TICKET-SEED-EXAMES-DEMO.md` §9 marca uma verificação que **você deve fazer**: confirmar os nomes exatos das colunas de `laudo_custodia` e `laudo_eventos` contra os modelos reais (`backend/app/models/laudo_custodia.py`, `laudo_evento.py`). O spec usou nomes análogos a `atestado_custodia`/`atestado_eventos`; se divergir, ajuste o INSERT. **Não adivinhe — confirme no modelo.**

## §6 Validação de execução

Antes de considerar pronto:
```bash
cd backend
PICSAUDE_DEMO_MODE=true python3 seed_demo.py          # SQLite local — deve criar os 3 objetos sem erro
PICSAUDE_DEMO_MODE=true python3 seed_demo.py          # segunda vez — deve ser no-op (idempotente)
python3 -m pytest tests/integration/test_pedidos_exame.py tests/integration/test_laudos_autorizacao.py -v   # sem regressão
```

## §7 Fluxo de aprovação

1. Você implementa + valida (§6).
2. Branch: `module/seed-exames-demo`.
3. Revisor (Claude Code/app) audita contra o ticket.
4. Conselheiro (Fable 5) — parecer leve.
5. Arquiteto ratifica.
6. Martelo do Fabiano + merge.
7. Deploy (reset_demo_db.py re-seed) → validar ao vivo na demo.

## §8 Não fazer

- Não introduzir a role `prestador_exame` aqui (é `core`, ticket separado).
- Não criar `GET /prescritor/pedidos-exame` (é Gap 4, ticket meu separado).
- Não mexer na UI da clínica (mock-sinalizado é Kimi 3 — `TICKET-UI-MOCK-SINALIZADO-CLINICA`).
- Não usar `git stash` (pasta compartilhada — KIMI3-002 §3).

## §9 Coordenadas

| Artefato | Caminho |
|---|---|
| Ticket-fonte | `docs/tickets/TICKET-SEED-EXAMES-DEMO.md` |
| Parecer Q1/Q2/Q3 | `docs/tickets/DIAGNOSTICO-FABLE5-EXAMES-DEMO.md` §6 |
| Código a modificar | `backend/seed_demo.py` (constantes + 2 funções + main) |
| Validação de colunas | `backend/app/models/laudo_custodia.py`, `laudo_evento.py` |
| Reset demo (PG) | `backend/scripts/reset_demo_db.py` |

---

*Despacho emitido pelo arquiteto de backend. Martelo homologado. Engenheiro pode iniciar.*
