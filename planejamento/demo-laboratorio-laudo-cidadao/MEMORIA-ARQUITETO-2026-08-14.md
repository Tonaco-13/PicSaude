# Memória do Arquiteto — PicSaúde — manhã de 14/08/2026 (09:00 BRT)

> Brief de continuidade lido pelo arquiteto (Z) no retorno de 14/08 09:00 BRT.
> Mantém o papel e o estado da demo para a sessão matinal não depender de contexto perdido.

---

## Meu papel aqui

- **Eu sou Z — arquiteto do PicSaúde.** Não escrevo código de produção nesta demo; **verifico no
  código** o que o engenheiro entrega (não só o relatório), dou parecer, seguro invariantes e
  classifico mudanças (`core`/`module`/`docs`/`ops` — AGENTS.md §10). O martelo final de mérito em
  mudanças `core` é do **Fabiano Tonaco** (líder/arquiteto-líder).
- **Engenheiro = Claude Code no Terminal do Mac Air.** Executa tickets, roda gates, **não commita**
  sem ordem, registra relatório em `docs/tickets/`.
- **Princípios invioláveis** (AGENTS.md): objetos sanitários imutáveis após emissão; ledger
  INSERT-only; `encerrado_fisico ≠ cancelado`; CPF sentinela `'00000000000'`; adapter/transmissão
  externa **só com G4A** (§10).

## Estado da demo "Laboratório — Laudo Cidadão + Bancada Leve"

Plano: `planejamento/demo-laboratorio-laudo-cidadao/` (README + 8 tickets + contexto).

| Ticket | Classe | Estado |
|---|---|---|
| B — endpoint bancada (`em_analise`) | module | ✅ aprovado (verificado) |
| C — RBAC laudo→dispensador | **core** | ✅ aprovado (martelo do Fabiano concedido; PR isolado ao commitar) |
| Fix teste vermelho `test_4d2` + gate | test/ops | ✅ aprovado |
| A — política de custódia clínica | docs | ✅ aprovado |
| D — faturamento TUSS+SIGTAP | module | ✅ aprovado (injeção fechada e provada) |
| E — atualiza ARQUITETURA_LAUDO/EXAMES | docs | ✅ aprovado |
| **F — gesto bancada no `clinica.html`** | module | ⏳ agendado 13/08 18:00 |
| **G — UI de laudo estruturado (pedra angular)** | module | ⏳ agendado 13/08 21:00 |
| **H — demo E2E + web-gui-tester** | ops/test | ⏳ agendado 14/08 00:00 |

**Nada commitado.** Tudo na árvore de `docs/sessoes-11-12-agosto`.

## O que faço às 09:00 BRT de 14/08 (em ordem)

1. **Ler os relatórios overnight** em `docs/tickets/`:
   `SESSAO-2026-08-13-TICKET-F-DEMO-LAB.md`, `...-TICKET-G-DEMO-LAB.md`,
   `SESSAO-2026-08-14-TICKET-H-DEMO-LAB.md` (datas conforme rodada).
2. **Verificar no código, não só no relatório** — em especial:
   - **G (keystone):** a orquestração `criar → assinar → liberar → /resultado por item` no
     `clinica.html`; o desabilitar de "Produzir laudo" após liberação (idempotência, evita laudo
     derivado duplicado); `esc()` anti-XSS; 403 não derruba sessão; **não mexeu no `cidadao.html`**.
   - **F:** gesto bancada espelha `registrarColeta`; `atualizarStatusUI` atualizado.
   - **H:** o roteiro E2E fecha o ciclo (clínica libera → cidadão vê + dá ciência → clínica vê encerrado).
3. **Confirmar gates verdes** (`-k` da CI em `gates.yml:101` + browser smokes, pois `clinica.html`
   está no path do `gates-browser`). Se algum gate vermelho → entender antes de anything.
4. **Decidir commits:** nada foi commitado. Posso autorizar PR isolado para o **C (`core`)** com os
   16 testes de autorização como prova; B/D/A/E/F/G/H no fluxo normal. **Confirmar com o Fabiano**
   antes de commitar (martelo dele em `core`).
5. **Rastrear os dois itens de governança** (não bloqueiam a demo):
   - Time-bomb `test_validar_emissao_receituario_ok` → housekeeping (data relativa).
   - Migração `-k` allowlist→denylist → `ops`, **condicional** ao fix do time-bomb.
6. **Fechar a demo** com o Fabiano: roteiro E2E clicável + a narrativa (custódia clínica do cidadão;
   particular/TUSS/SIGTAP; bancada leve sem virar LIMS; sem transmissão externa — G4A).

## Cuidados para a manhã

- Se o engenheiro **bloqueou** algo (registrou e esperou), resolver o bloqueio antes de avançar.
- Se ele **commitou** apesar da instrução, verificar o que entrou e alinhar.
- G é a peça de maior risco autônomo — revisar com atenção redobrada a ponte item↔laudo e a
  idempotência.
- Registar meu parecer de manhã em `docs/tickets/SESSAO-2026-08-14-PARECER-ARQUITETO-FGH.md`.
- **Descritivos do Kimi** (commit `95f3536`, pasta `Relatório Kimi Descritivo Módulos Demo/`) — o
  `DESCRITIVO-MODULO-LABORATORIO` espelha o `clinica.html` que F/G tocaram; consulte ao revisar a UI.
- **Agendamento é do engenheiro, não meu**: F/G/H rodam sozinhos (cron); eu NÃO tenho cron — pego a
  demo manualmente às 09:00 lendo esta memória.

---

*Memória criada pelo arquiteto (Z AI) em 2026-08-13 para a sessão de 14/08 09:00 BRT.*
