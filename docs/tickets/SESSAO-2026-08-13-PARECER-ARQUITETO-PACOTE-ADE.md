# Sessão 2026-08-13 — Arquiteto: parecer sobre o pacote §6 (fix + A + D + E)

| Campo | Valor |
|---|---|
| **Arquiteto** | Z AI — redator |
| **Engenheiro** | Claude Code no terminal — executou o pacote §6 do `SESSAO-2026-08-13-PARECER-ARQUITETO-B-C.md` |
| **Escopo** | Verificação de código do fix do teste vermelho + Tickets A (`docs`), D (`module`), E (`docs`) |
| **Estado** | **Aprovado.** Dois itens de governança rastreados (time-bomb e política de `-k`). |

---

## §1 Veredito em uma frase

O pacote §6 foi executado na ordem despachada e está **aprovado após verificação no código**. O
Ticket D — ponto de risco (interpolação de coluna em SQL) — tem a injeção **fechada e provada por
teste**. Aceite 5/5; `-k` da CI em **326 passed** (era 279). Nada commitado.

---

## §2 Fix do teste vermelho + gate — ✅

- `test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` corrigido **sem tocar no
  `_PAYLOAD_LAUDO` compartilhado**: cria pedido antes e usa payload local
  `{**_PAYLOAD_LAUDO, "pedido_protocolo": ...}`. A invariante real (2 eventos, mesmo `instance_id`)
  voltou a ser exercitada. `test_4d2` → 13 passed.
- `-k` da CI (`gates.yml:101`) ampliado com `test_4d1 · test_4d2 · test_4e_e2e · integridade ·
  transferencia_exame` — suítes de invariante/ledger que estavam verde-e-não-gateadas. Decisão correta.

## §3 Ticket A — política de custódia clínica (`docs`) — ✅

`docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md`. Pontos verificados:
- `file:line` re-conferidos contra o código atual (o Ticket C deslocou `laudos.py`; o engenheiro
  corrigiu uma âncora própria `:800→:796`).
- Honesto sobre o que **não** promete: não é "zero dado" — cita RDC 302/2005, CFM 2.052/2013 e LGPD
  (art. 6º III minimização; art. 16º I ressalva de retenção legal).
- Declara-se `local-extension` com rodapé que cerca a exceção: mudança que altere
  estado/ledger/custódia deixa de ser local-extension e vira `core`.

## §4 Ticket D — faturamento TUSS + SIGTAP (`module`) — ✅ (risco de injeção fechado)

Verificado em `backend/app/routers/clinicas.py`. O ponto crítico — nome de coluna interpolado em SQL
— está **seguro e provado**:

- **Whitelist como gargalo único:** `_CRITERIOS_FATURAMENTO` (`:235`, só `codigo_tuss`/`codigo_sigtap`).
  `_resolver_criterio` (`:241`) é o único caminho; fora do mapa → 422 nomeado **antes do banco**.
- **Comentário honesto** (`:259`): "seguro pela whitelist, e por nenhum outro motivo".
- **Prova por teste:** `test_agrupar_por_invalido_422_nomeado` (`test_faturamento_exames_clinica.py:358`)
  mata em 422 três ataques — `"invalido"`, `"codigo_tuss"` (tentativa de usar o nome real da coluna) e
  `"tuss; DROP TABLE pedidos_exame"`. Mostra que a whitelist é sobre a **chave do critério**, não a
  coluna: nem saber o nome da coluna ajuda.
- **Reprodutibilidade preservada:** desempate `(-qtd, codigo)` (`:303`); chave neutra; rótulo só na
  borda (CSV/PDF); default `tuss` com teste byte-a-byte (`?agrupar_por=tuss` == sem parâmetro).

## §5 Ticket E — atualização da arquitetura (`docs`) — ✅

`ARQUITETURA_LAUDO.md` ganhou as seções "dispensador-produz-sob-RT" (com tabela de auditoria) e
"fluxo bancada" (com fronteira LIMS), + cross-link para a política. `/em-analise` entra em
`ARQUITETURA_EXAMES.md`. **Achado de drift corrigido:** a tabela de endpoints grafava
`/{proto}/coletar` mas a implementação é `/{proto}/itens/{item_id}/…` — corrigido com nota datada, e
`transferir-laboratorio` (que faltava) foi adicionado.

---

## §6 Governança — dois itens rastreados (decisões do arquiteto)

### 6.1 Time-bomb `test_validar_emissao_receituario_ok`
- Data hardcoded `data_validade = 2026-05-26` vencida vs `utcnow()`. Domínio receituário, **não** do
  laboratório; pré-existente. O engenheiro acertou em **não gatear** (gatear vermelho só move o
  apodrecimento) e em documentar a exclusão no `-k`.
- **Decisão:** corrigir como **housekeeping à parte** (tornar a data relativa via
  `calcular_data_validade`). Não bloqueia a demo. Pode entrar no PR de F/G/H se sobrar tempo; senão,
  vira ticket `ops`.

### 6.2 Política de `-k` (allowlist → denylist)
- 111 testes de integração fora do gate, quase todos verdes. Engenheiro sugere migrar para
  "tudo exceto exceções nomeadas".
- **Decisão:** **endossada, mas condicional e fora do escopo da demo**: (1) **primeiro** consertar o
  time-bomb (senão o CI fica vermelho no minuto da troca); (2) **depois** ticket `ops` deliberado
  para a migração, com exceções documentadas. Não fazer dentro do pacote da demo.

---

## §7 Agenda — delegação noturna do ENGENHEIRO (o arquiteto não se autoprograma)

O Fabiano autorizou cadência automática **para o engenheiro** (BRT, horário do host). Correção do
Fabiano: **o agendamento é do engenheiro, não do arquiteto** — o arquiteto (Z) pega a demo numa
sessão normal às 09:00, lendo a memória; **não há cron do arquiteto**.

| Quando (BRT) | Quem | O quê | Estado |
|---|---|---|---|
| 13/08 18:00 | Engenheiro | Ticket F — gesto bancada no `clinica.html` | ✅ agendado (`automation-54120389`) |
| 13/08 21:00 | Engenheiro | Ticket G — UI de laudo estruturado (pedra angular) | ⏳ chat novo* |
| 14/08 00:00 | Engenheiro | Ticket H — demo E2E + `web-gui-tester` | ⏳ chat novo* |
| 14/08 09:00 | **Arquiteto (Z) — manual, NÃO cron** | Revisar o overnight no código, confirmar gates, decidir commits (c/ Fabiano), seguir a demo | brief em `MEMORIA-ARQUITETO-2026-08-14.md` |

\* Limite do sistema: 1 automação por sessão de chat. F foi criado nesta sessão; G e H exigem
chats novos (prompts prontos já entregues ao Fabiano).

Cada rodada do engenheiro: implementa segundo o ticket, roda gates, **não commita**, e registra
relatório em `docs/tickets/SESSAO-2026-08-1{3,4}-TICKET-{F,G,H}-DEMO-LAB.md`. Em caso de ambiguidade
ou gate vermelho, **registra o bloqueio e espera o arquiteto** — não chuta.

## §8 Descritivos dos módulos (entrega Kimi)

Commit `95f3536` (nesta sessão): `Relatório Kimi Descritivo Módulos Demo/` — 5 descritivos factuais
(Prescritor, Cidadão, Farmácia, Laboratório, Portal) com jornada na tela, mapa frontend↔backend com
RBAC e endpoints sem tela. Documentação pura. São **referência de apoio** para F/G/H e para a
revisão das 09:00 — em especial `DESCRITIVO-MODULO-LABORATORIO-2026-08-13.md` espelha o
`clinica.html` que F e G vão tocar.

---

*Parecer emitido pelo Arquiteto (Z AI) em 2026-08-13. Pacote §6 aprovado. Descritivos Kimi
commitados (`95f3536`). Demo avança para o frontend (Dia 2) sob agenda do **engenheiro** (F/G/H);
retorno **manual** do arquiteto em 14/08 09:00 BRT.*
