# PARECER DO CONSELHEIRO — PR #76 (T0.5 + T1, classe core/custódia)

> Conselheiro (cowork/MS), 2026-07-05. Portão de core conforme CLAUDE.md §10.
> Diff revisado: `e72ff74`, `cc00b50`, `7ec4be4` (origin/feat/circulacao-t1-devolucao).

## SIGN-OFF FINAL (3ª rodada): CONDIÇÃO VINCULANTE CUMPRIDA — commit autorizado

Verificado no working tree: helper com `(item_id IS NULL OR item_id = ?)`
espelhando o idioma de `_dispensador_detem_custodia`; cenários (d) e (d2),
este com seed próprio de custódia por prescrição inteira e verificação por
ablação relatada pelo autor. O portão de código está fechado. Restam os
portões de processo: CI Postgres verde no PR #76 e auditoria Jules antes do
merge. Ratificações da Fase 0 seguem pendentes com Fabiano (bloqueiam T2,
não este PR).

## Veredito (1ª rodada): APROVADO COM 1 CONDIÇÃO VINCULANTE

O T1 em `devolver_item` está correto: reabertura de custódia ao paciente na
mesma transação, CPF normalizado, ramo `prescritor` preservado, teste que
falha sem o fix. T0.5 idem (booleans `True`, DVs do CNPJ conferidos duas
vezes — por mim e pelo code/MS, independentemente). A inclusão de
`test_custodia_devolucao` no gate de CI corrige um furo real (suíte existia
e nunca rodava).

## Condição vinculante — ajuste em `dispensar_item` (antes do merge)

O novo auto-fechamento fecha **qualquer** custódia que não seja do
dispensador atual. Combinado com dois fatos pré-existentes — guard de status
em blocklist (`em_custodia` alheio é dispensável) e ausência de
`_dispensador_detem_custodia` no dispensar — isso **legitima a tomada
silenciosa de custódia entre CNPJs**: Farmácia B, com protocolo + item_id e
JWT válido, dispensa item retido pela Farmácia A e assume a custódia dela.
Antes do PR o buraco existia mas deixava trilha inconsistente; com o PR, a
tomada vira rastro "legítimo". É pior que o problema que corrige.

**Exigência (pequena, mesmo PR):**

```
custódia ativa do PACIENTE      → fechar e abrir para o dispensador (caso T1 ✓)
custódia ativa INEXISTENTE      → abrir para o dispensador (comportamento atual ✓)
custódia ativa de OUTRO         → HTTP 409
  dispensador                     {"codigo": "item_retido_por_outro_estabelecimento"}
```

**Teste adicional obrigatório (cenário d):** Farmácia A retém (custódia ativa
de A, sem dispensar) → Farmácia B tenta dispensar → 409. Usa a Farmácia Norte
do T0.5.

## Observações não-bloqueantes

1. **Consistência de ledger:** `transferir_custodia` emite `custodia_transferida`
   (custodia.py:~530); os dois caminhos implícitos novos (reabertura na
   devolução; assunção no dispensar parcial) registram só em
   `prescricao_custodia`. Recomendo emitir `custodia_transferida` também
   nesses caminhos — o evento já existe no vocabulário §2 (não é evento novo),
   e o T6 (histórico) vai renderizar a trilha incompleta sem isso. Pode ser
   follow-up imediato se o autor preferir não crescer este PR.
2. **Defensivo:** `paciente_row` ausente em `devolver_item` → `AttributeError`
   500. Trocar por 422/409 explícito. Menor.
3. **Achado do code/MS confirmado e elevado:** dispensação sem detenção de
   custódia (e sem token) é possível hoje — inclusive para itens `pendente`
   (nunca apresentados). Isso contradiz o invariante "posse não brota na
   farmácia" na própria dispensação. **Proposta T1.5** para ratificação de
   Fabiano: `dispensar_item` passa a exigir detenção prévia (retenção
   explícita ou token de apresentação). Muda comportamento de produto e UX
   do balcão — decisão de produto, não de código. Registrar antes da Fase 2.
4. A falha pré-existente de `test_posologia_sugerida` (herdada de `23ca07d`)
   não é objeto deste parecer; segue como pendência de `main` a tratar em
   ticket próprio — não usar este PR para corrigi-la.

## Adendo (2026-07-05, 2ª rodada) — granularidade da condição vinculante

A implementação da condição (helper `_custodia_item_de_outro_dispensador`)
cobre apenas custódia **por item** (`item_id = ?`). Porém a retenção padrão
do balcão grava custódia da **prescrição inteira** (`item_id IS NULL`) —
confirmado na própria regra de autorização nº 4 de `transferir_custodia`.
Com isso, a tomada silenciosa continua possível no fluxo mais comum:
A retém a prescrição inteira → B dispensa item e assume custódia do item.

**Complemento exigido (1 linha de SQL + 1 teste):**

```sql
WHERE prescricao_id = ? AND (item_id = ? OR item_id IS NULL)
  AND detentor_tipo = 'dispensador' AND detentor_id != ? AND encerrada_em IS NULL
```

**Teste (d2):** custódia ativa da prescrição INTEIRA em nome da Farmácia A
(sem custódia por item) → Farmácia B tenta dispensar item → 409; custódia de
A intacta; zero linhas em `dispensacoes`.

**Observação não-bloqueante (registrar, não corrigir aqui):** quando o
próprio dispensador detém a prescrição inteira e dispensa parcialmente, o
código abre custódia por item própria coexistindo com a de prescrição
inteira — duplicidade pré-existente ao T1; candidata a nota no
TICKET-COERENCIA-DEVOLUCOES.md.

Com o complemento + (d2) verdes, o commit no branch do PR está autorizado
(não é push direto em main; o merge continua condicionado ao CI verde e à
auditoria Jules).

## Pendências de processo antes do merge

- [ ] Condição vinculante implementada + cenário (d) verde
- [ ] CI do PR #76 verde (gate de integração com Postgres)
- [ ] Auditoria Jules (checklist do próprio PR)
- [ ] Ratificações da Fase 0 (Fabiano) — não bloqueiam este PR, mas T2 espera por elas
