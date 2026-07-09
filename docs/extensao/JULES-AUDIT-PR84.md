# Auditoria Jules - PR #84 (Correções)

## 1. T5 LGPD exposição
A rota `GET /dispensacoes/{id}/comprovante` **exige auth**, especificamente as roles de `dispensador`, `prescritor`, `auditor`, e `admin` via dependência de segurança. Não há endpoints públicos (sem auth) que retornem `comprador_nome` ou `comprador_documento`.
Atualmente, as colunas relacionadas a `comprador` só são acessadas e mapeadas para `paciente` na rota `GET /relatorios/*`, que também está restrita (disponível apenas em ambiente local no MVP).

## 2. T6 ORDER BY
A correção foi feita em `backend/app/routers/custodia.py:827`:
O campo originalmente utilizado na query isolado foi o `created_at`:
`ORDER BY created_at DESC LIMIT 1`
E foi alterado para incluir `id` como desempate (tiebreaker):
`ORDER BY created_at DESC, id DESC LIMIT 1`

## 3. T0.5b padrão arquitetural
O padrão arquitetural foi registrado em `CLAUDE.md`, na seção 10 (Taxonomia de contribuição), garantindo a regra como oficial: "estados computados não são persistidos; flag read-only deriva de fonte autoritativa".

## 4. Cross-cutting (Testes Reais na Composição #83+#84)
Para a composição, foram realizados os seguintes 3 checks reais na base de código:
1. Verificação de que operações de `estorno` (`POST /dispensacoes/{id}/estornar`) criam objetos derivados de forma determinística sem mutar a estrutura imutável de `dispensacoes`.
2. Validação dos limites de custódia e se as transições de estados (e.g. transferências, devoluções) cumprem os limites de posse de acordo com RBAC e regras de custódia sanitária.
3. Garantia de que a verificação de multi-role no endpoint `/comprovante` é efetuada corretamente (dispensadores são validados via CNPJ; prescritores via CNS; administradores e auditores têm bypass integral).
