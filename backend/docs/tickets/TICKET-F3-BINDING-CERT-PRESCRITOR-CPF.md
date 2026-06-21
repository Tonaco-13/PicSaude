# TICKET F3 — Binding verificável certificado ↔ prescritor (CPF)

> Origem: achado **F3** da auditoria de segurança (Jules, 2026-06-19).
> Classe: **`core`** (cadastro/identidade do prescritor) — exige revisão central.
> Bloqueia: NO-GO para expor a assinatura A1 na UI (junto com F2).

---

## Problema

Em `backend/app/routers/prescritor.py: upload_certificado`, ao cadastrar o
`.pfx`, o sistema **confia** que o CPF contido no certificado pertence ao
prescritor logado, sem cruzamento (linhas 159-162):

```
# Hoje o model `prescritores` não tem CPF (apenas CNS).
# Confiamos na identidade do certificado e marcamos no log.
```

Consequência: um prescritor autenticado (por CNS) poderia associar à sua conta o
certificado de um **terceiro** (de posse do `.pfx` + senha), assinando com uma
identidade que não é a dele — ou vinculando identidade alheia à sua sessão.

## Objetivo (invariante)

> O certificado só é aceito se o **CPF do certificado == CPF do prescritor** no
> cadastro. Sem CPF de referência, não há cadastro de certificado.

## Abordagem — faseada

### Fase A — CPF no cadastro + igualdade no upload (mínimo para o portão)
- Adicionar **`cpf`** ao registro do prescritor (`prescritores`), migração com
  coluna *nullable* (objetos legados permanecem `NULL`).
- Capturar/validar o CPF do prescritor no **onboarding** (antes do 1º upload de
  certificado). Fonte do CPF: decisão de implementação — autodeclarado no
  onboarding (interino) vs. derivado de base confiável.
- No `upload_certificado`: comparar `icp.cpf_certificado` com o CPF do prescritor
  no cadastro; **mismatch → 422/403**, sem persistir.
- Se o prescritor ainda não tem CPF no cadastro → exigir captura antes (não
  cadastrar certificado "confiando" no CPF do próprio certificado).

### Fase B — verificação forte do CPF (depois)
- Validar o CPF do prescritor contra base confiável (CADSUS / integração T65),
  elevando o binding de "autodeclarado" para "verificado".

## Escopo

**Inclui:** migração `prescritores.cpf` (nullable), captura no onboarding,
comparação no upload, testes (match aceita / mismatch rejeita / sem CPF exige).
**Não inclui:** integração CADSUS completa (T65 — fica para a Fase B).

## Critérios de aceite
- [ ] Certificado com CPF ≠ CPF do prescritor no cadastro → rejeitado (sem persistir).
- [ ] Certificado com CPF == CPF do prescritor → aceito.
- [ ] Prescritor sem CPF no cadastro → upload exige captura/validação antes.
- [ ] Migração não quebra objetos legados (CPF `NULL` permitido).
- [ ] Testes cobrindo cada caso.

## Esforço / riscos
- Fase A: **médio** (migração + campo no onboarding + comparação + testes).
- Risco: definir a **fonte de verdade** do CPF do prescritor. Para o portão,
  "CPF declarado no onboarding + igualdade com o cert (cuja identidade é
  confiável após F2)" é interino aceitável; a verificação forte é a Fase B.

## Relação com F2
F2 garante que o CPF **dentro do certificado** é confiável (cadeia ICP-Brasil).
F3 garante que esse CPF é o **do prescritor certo**. Os dois juntos fecham o
binding identidade↔conta. Implementar F3 sem F2 deixa o CPF do cert ainda
forjável; por isso ambos são pré-requisito da exposição na UI.
