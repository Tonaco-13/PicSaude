# Ticket A — Política de Custódia Clínica do Laudo

| Campo | Valor |
|---|---|
| Classe | `docs` |
| Depende de | — |
| Esforço | Pequeno |

## Contexto

Decisão #2 da demo: formalizar como política que **a custódia clínica do laudo é do cidadão**, e o
laboratório retém **rastro forense + mínimo legal**. O backend **já implementa** isso
(`liberar` → `laudo_custodia prestador→paciente`); falta declarar.

## Tarefa

Criar **`docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md`** com:

1. **Princípio** (uma frase forte): a custódia clínica do laudo é do cidadão; o laboratório guarda
   o rastro forense (protocolo, hash SHA-256, ledger imutável, cadeia de custódia) + o mínimo legal
   do Responsável Técnico.
2. **Mapeamento ao backend existente** (prove que não é teoria):
   - `POST /laudos/{proto}/liberar` (`laudos.py:651`) cria `laudo_custodia (de=cnpj_prestador, para='paciente')` (`:682`) → custódia passa ao cidadão.
   - `laudo_eventos` é ledger imutável (INSERT only).
   - `assinatura_hash` = SHA-256 do documento canônico (`_calcular_hash`, `laudos.py:145`).
   - `GET /paciente/laudos` (`auth.py:512`) + `cidadao.html:693-756` = a carteira do cidadão.
3. **Base regulatória da retenção mínima** do RT (parágrafos curtos, citando):
   - RDC 302/2005 (Anvisa) — retenção de registros/lautos pelo laboratório.
   - Resolução CFM 2.052/2013 — responsabilidade técnica do laudo.
   - LGPD — minimização + direitos do titular; **não revoga** a retenção obrigatória do controlador.
4. **Exceção documentada ao NUCLEO_SANITARIO:** o RT reteém o mínimo legal; a custódia **clínica**
   (acesso/posse primária do conteúdo) é do cidadão. Marcar como exceção legítima, nos termos da
   seção "Refinamento" de `docs/ARQUITETURA_LAUDO.md`.
5. **Classificação:** `local-extension`/`docs` — **não altera semântica clínica** (estados, ledger,
   custódia). Apenas declara política e mapeia ao existente.

## Critérios de aceite

- [ ] Arquivo `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` criado.
- [ ] Referencia `file:line` do backend que materializa cada afirmação.
- [ ] Cita RDC 302/2005, CFM 2.052/2013 e LGPD.
- [ ] Declara-se explicitamente `local-extension` (sem impacto em semântica clínica).
- [ ] Cross-link: adiciona entrada em `docs/ARQUITETURA_LAUDO.md` apontando para a política.

## Notas

- Não há código neste ticket. É puramente declaração de política + mapeamento factual.
- Evite prometer "zero dado" — a regulação proíbe. A política é "custódia clínica do cidadão,
  rastro + mínimo legal do lab".
