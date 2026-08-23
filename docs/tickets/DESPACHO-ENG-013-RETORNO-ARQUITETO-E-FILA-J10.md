# DESPACHO ENG-013 — retorno da sessão do arquiteto (19/08) + fila J.10/migração

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Fabiano (martelos) |
| **Emitido** | 2026-08-19, via chat do arquiteto |
| **Registro** | Transcrito do chat pelo próprio autor em 23/08 — conteúdo íntegro, sem revisão de mérito |
| **Execução** | Fila executada por inteiro em 20/08; vereditos e martelos registrados nos relatórios de sessão |

---

## RETORNO — o que a sessão do ARQUITETO produziu em 19/08

Fabiano ordenou diretamente ao arquiteto: *"começa o J.10 empilhado na branch da
migração"*. O arquiteto executou (exceção de papel registrada — a revisão do
código é do engenheiro, inversão do padrão). Entregue:

- **PR #170 [module]** — J.10 completo (`DESENHO-J10` §3.3–§3.6): `itens:[...]`
  opcional com explosão de granularidade; `POST /pedidos-exame/{p}/itens/{id}/devolver`
  (item permanece `pendente`); fila e GET anti-vazamento (AC vi); guards
  item-scoped; carteira com posse por item; telas (checkboxes por exame +
  "Não realizamos este exame"). Commit único `a30630c`, empilhado no #168, CI verde.
- Veredito do arquiteto sobre o desvio J.7 (#165→#166): **ACEITO, sem revert**.
- Parecer do arquiteto sobre o #168: **APROVADO** (§4.1a/b, §4.3) — martelo do Fabiano.

## FASE 1 (gatilho: martelo+merge do #168) — dança da pilha (lição do #165)

1. merge squash do #168 **SEM `--delete-branch`** (deletar a base fecha PR
   empilhado em vez de retargetá-lo — foi assim que o #165 morreu);
2. retarget do #170 → main, rebase (replay de 1 commit, mensagem preservada),
   `push --force-with-lease`;
3. conferir diff do PR == `a30630c` (nenhum hun a mais/menos), CI verde, MERGEABLE;
   só então deletar a branch da migração;
4. merge do #170 (module, ordem geral). **Stop-condition:** qualquer divergência.

## FASE 2 — revisão retroativa do #170 (do ENGENHEIRO, como revisor do código
do arquiteto). Achados já deixados: laudo sob custódia parcial (laudos.py lê
nível-pedido — desenho laudo×item é do arquiteto) e motivo
`devolucao_pos_resultado` reservado.

## FASE 3 — micro-ticket `core` do RBAC (remarcar/nao-compareceu aceitarem
dispensador). Core: martelo PRÓPRIO do Fabiano.

**Regras permanentes:** core não se auto-mergeia · docs sem ordem não se
commitam · discordância técnica = para e devolve (§3 do ENG-012).

---

*Despacho emitido pelo arquiteto (Z) em 19/08; registro durável em 23/08.*
