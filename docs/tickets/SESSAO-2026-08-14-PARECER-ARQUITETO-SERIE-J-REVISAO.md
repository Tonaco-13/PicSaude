# Sessão 2026-08-14 — Arquiteto: revisão da entrega série J (ENG-010) + adjudicação do J.4

| Campo | Valor |
|---|---|
| **Arquiteto** | Z AI — redator |
| **Engenheiro** | entregou J.1 · J.2 · J.3 · J.5 · J.6.b; J.4 devolvido sob a regra §3 do ENG-010 |
| **Verificação** | diffs lidos arquivo por arquivo no working tree (nada commitado) + testes novos |
| **Estado** | 5 tickets **APROVADOS**. J.4 **adjudicado: opção (c)+(a)** — AC revisto (erro era meu). |

---

## §1 Veredito por ticket (verificado no código)

| Ticket | Veredito | Verificação do arquiteto |
|---|---|---|
| **J.1** (`core`) | ✅ | `derivar_status_pedido` corrigido: `resultado_disponivel` tem precedência sobre o ramo dos terminais; docstring explica os 3 sintomas da excursão. **Companheiro aprovado:** `resultado_disponivel` em `_ESTADOS_PEDIDO_FIM_FILA` (`dispensadores.py:229`) com justificativa correta — fila é trabalho pendente do lab; ciência é ato do cidadão. Efeito colateral positivo endossado: carteira mantém "em andamento" até a ciência (reforça a narrativa do laudo cidadão). |
| **J.2** (`core`) | ✅ | Dois sítios normalizados com comentário cruzado (`documento_canonico.py` + `validacao_documental.py:395`) — o achado do segundo sítio era a superfície que o cidadão vê; bom catch. Argumento de não-afrouxamento correto (`normalize_nome` idempotente; trocar nome por outro segue quebrando o hash; teste preserva acento). Round-trip análogo verificado: exame/laudo/atestado hasheiam CPF, não nome — imunes. Causa da cegueira do gate (conftest semeia maiúsculas) plausível e agora coberta com Title Case. |
| **J.5** (`core`) | ✅ | `pedido_coletado` + outbox na transação do `/agendamentos/{ag}/realizar`, `instance_id` compartilhado antes do laço. As duas vias de coleta contam a mesma história. |
| **J.3** (`module`) | ✅ | Interceptador único em `config.js::instalarReloginDemo` (ponto de estrangulamento dos fetches), idempotente, com mutex contra rajada de 401 (um `/demo/login` por rajada — detalhe bem pensado). Ligado nos 4 módulos. JWT/RBAC intocados, como exigido. |
| **J.6.b** (`module`) | ✅ | `tokens.py` distingue tipo de objeto do paciente antes de 404; implementação defensiva (tabela ausente não derruba emissão — "enfeite de mensagem, não caminho clínico"). |
| **J.4** (`ops`) | ⚠️ adjudicado | Ver §2. |

Gates reportados: integração completa 466 · unit 436 · browser 68 — verdes. No ambiente do
arquiteto rodei `tests/unit/test_states_exame_derivacao.py` (17 passed); integração requer
PostgreSQL e browser requer playwright, ausentes no sandbox do arquiteto — gates do engenheiro
aceitos (código verificado diretamente compensa).

## §2 Adjudicação do J.4 — a discordância procede, e o erro era meu

**O engenheiro está certo.** A raiz do path está correta (`COPY backend/ .` → `/app/app/config.py`
→ default `../../data/` usado sem resolução), mas o **AC que eu escrevi** — "score alto" — era
indevido: `profissionais_cnes` nasce vazia **por desenho** (`seed_demo.py:705`), a persona usa CNS
sintético e a validação CNES é não-bloqueante. Corrigir o path troca `FileNotFoundError` por
`nao_encontrado` — e o score "baixo" passa a ser **o indicador dizendo a verdade** sobre um CNS
que não existe. Forçar score alto faria o indicador de confiança mentir.

**Decisão do arquiteto (para ratificação do Fabiano, pois revierte AC de despacho):**

- **Opção (c) + (a) adotadas:** score "baixo" aceito como correto para persona sintética;
  path corrigido via env no Render (zera o erro de arquivo no log). **AC revisto:**
  "checagem CNES roda sem erro de path e retorna `nao_encontrado` graciosamente; score 'baixo'
  é comportamento correto na demo; o guia explica o que o score significa".
- **Opção (b) rejeitada** — trocar a persona por CNS real muda a identidade da demo e fere a
  fonte única.
- Errata do arquiteto: no parecer da excursão (§2.3), o achado CNES era real (erro de path), mas
  o AC conflate "sem erro" com "score alto". Correção registrada aqui.

## §3 Itens que ficam nas mãos do Fabiano (acesso Render)

| Env / ação | Efeito | Origem |
|---|---|---|
| `PIX_SAUDE_DEMO_DB=<path real do demo DB>` | fim do `FileNotFoundError` CNES | J.4 (a) |
| `PICSAUDE_JWT_SECRET=<hex fixo de 32 bytes>` | tokens sobrevivem a restart; mata a hipótese do 401 isolado | vigilância J.4 |
| `PICSAUDE_DEMO_ADMIN=true` | persona admin no `/demo/login` → ledger visível | J.6.a |
| Reset manual da vitrine (`reset_demo_db.py --sim-eu-quero`) | SIGTAP nas linhas pré-semeadas | pendência antiga |
| Guia: o que o score de confiança significa (baixo = CNS sintético) | narrativa honesta | J.4 (c) |

## §4 Próximos passos

1. Fabiano dá a ordem → engenheiro commita e abre **PR 1** (`fix/serie-j-core`: J.1+J.2+J.5 +
   3 suítes) e **PR 2** (`fix/serie-j-demo-ux`: J.3+J.6.b + 2 suítes).
2. Martelo do Fabiano no PR 1 (`core`) após review — parecer desta sessão serve de base.
3. J.7/J.8/J.9 (bloco `Fabiano.md`) entram na sequência: J.7 no mesmo PR core ou no próximo;
   J.8/J.9 no PR 2 ou PR 3 de UI. J.7 ainda precisa de martelo.

---

*Parecer redigido pelo arquiteto (Z AI) em 2026-08-14. Errata do AC do J.4 assumida pelo
arquiteto; ratificação do Fabiano registrada nesta sessão.*
