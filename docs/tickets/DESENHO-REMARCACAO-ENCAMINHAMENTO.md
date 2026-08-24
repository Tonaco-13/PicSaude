# Mini-desenho — remarcação do encaminhamento (`module`)

| Campo | Valor |
|---|---|
| **Origem** | Achado do #188 (máquina recusa `agendado → agendado`; não há /remarcar) + promessa do arquiteto na ENG-017 |
| **Ruling central** | **A data da visita é atributo do compromisso, não identidade do encaminhamento** |

## §1 A distinção doutrinária (por que NÃO derivar)

A regra da casa — *"remarcação = novo objeto derivado"* — vale quando **o objeto
É o compromisso** (agendamentos: AG-001 → AG-002 com `origem_agendamento_id`).
No encaminhamento, o objeto é o **encaminhamento clínico** (quem, por quê, para
qual especialidade); a data da visita é atributo dele. Derivar um objeto
inteiro para trocar um horário copia conteúdo clínico para mover uma marca de
calendário — desproporcional, e enche a cadeia de derivação de eventos sem
conteúdo clínico.

## §2 A mecânica

- **`agendar` torna-se re-chamável enquanto `status = agendado`**: cada
  chamada emite `encaminhamento_agendado` com `{data_anterior, data_nova}` no
  payload — **estado não muda** (sem aresta nova, sem self-loop: o ato é
  aditivo no ledger, idempotente no estado).
- **Nenhum evento novo no vocabulário** — reusa `encaminhamento_agendado`
  com o payload de/para (congelamento intacto).
- **Papéis**: destino (quem marcou, remarca — a lógica do #171) + admin.
  Cidadão remarcar: futuro registrado.
- **Guardas**: re-agendar só em `agendado` (em `atendido`/terminais → 422);
  primeira chamada em `emitido` segue sendo o agendar de hoje.

## §3 Testes

(i) re-agendar muda a data que a carteira lê **sem novo objeto** (a leitura já
pega o compromisso mais recente — provado no #188); (ii) ledger com dois
eventos encadeados por `data_anterior/data_nova`; (iii) guard de estado;
(iv) a carteira mostra a última, nunca a primeira.

---

*Mini-desenho do arquiteto (Z), 24/08. Classe `module`; nenhum estado novo,
nenhuma aresta nova, nenhum evento novo — a remarcação como re-ato.*
