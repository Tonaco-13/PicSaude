# TICKET-5C-BIS-B.1 — Correção de laudo não deve cruzar paciente

| Campo | Valor |
|---|---|
| **Status** | Aberto (follow-up) — **não implementar sem revisão** |
| **Classe provável** | `module` (guard de domínio na criação de laudo) — confirmar |
| **Origem** | CODEX rodada 2 do PR #8 (5C-BIS-B), 2026-06-03 |
| **Não bloqueia** | O 5C-BIS-B (ownership) — gate verde; isto é coerência clínica, ortogonal |

## §1 Achado
O 5C-BIS-B passou a exigir que a **origem de uma correção** de laudo pertença ao
**mesmo autor** (`origem.autor.cns == cns_autor`, §8.3). Mas **não** valida que a
correção seja do **mesmo paciente** da origem. [VERIFICADO — `laudos.py`, bloco
`origem_laudo_id`]

Clinicamente, a cadeia de derivação `origem_laudo_id` (REC-001 ← REC-002 …) **não
deveria cruzar pacientes**: um laudo corrigido é o mesmo ato clínico reemitido, do
mesmo paciente. Hoje, um autor poderia emitir uma "correção" de um laudo seu de
outro paciente — sem barreira.

## §2 Ajuste proposto (a confirmar)
No guard de `origem_laudo_id` da criação, além de `origem.autor.cns == cns_autor`,
exigir `origem.paciente.cpf == cpf` (paciente do payload). 403 (ou 422) se divergir.

Espelha o guard de `pedido_protocolo` (§8.4), que já valida paciente — aqui a
mesma disciplina aplicada à cadeia de correção.

## §3 Teste
PG: autor cria correção cuja origem é laudo seu **de outro paciente** → bloqueado;
mesma autoria + mesmo paciente → 201.

## §4 Escopo
Fora do ownership mínimo (não é "quem acessa", é "coerência da cadeia clínica").
Guard de domínio pequeno na criação de laudo; sem tocar estados/ledger/custódia.

---

*Registrado em 2026-06-03 a partir da CODEX rodada 2 do PR #8.*
