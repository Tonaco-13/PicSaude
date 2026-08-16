# Parecer do arquiteto (Z) — Revisão da entrega ENG-011 (CNES durável + J.8/J.9)

| Campo | Valor |
|---|---|
| **Data** | 2026-08-15 (tarde) |
| **Objeto** | `SESSAO-2026-08-15-TICKET-ENG-011-CNES-DURAVEL-ABAS.md` (engenheiro) |
| **Verificado** | Código na árvore (branch `fix/serie-j-demo-ux`, nada commitado) + relatório |
| **Veredito** | **APROVADO** (PR `ops` + PR `module`), com 2 determinações abaixo |

---

## §1 Micro-ticket `ops` — verificação §5 negativa: ACEITA

O despacho §5 exigia verificar se o arquivo do `preDeployCommand` persiste até o
container. A resposta é **não**, com três evidências independentes (docs do Render ×2 +
empírica: o arquivo de 14/08 morreu no redeploy, o que só acontece se `/data` é efêmero).
O despacho já nomeava a saída ("criar/verificar a base no boot, idempotente") — o engenheiro
aplicou o ramo condicional autorizado, não improvisou.

**Conferido no código (`app/cnes_demo.py` + `main.py`):**
- Hook no `_lifespan_bootstrap`; no-op fora de `PICSAUDE_DEMO_MODE`; no-op quando o banco da
  aplicação é o próprio SQLite (evita trocar erro claro por obscuro); `try/except` que nunca
  derruba o boot (a validação CNES é não-bloqueante por contrato).
- `DDL_CNES_DEMO` fonte única, importada pelo `seed_demo.py` (fim do DDL duplicado) — inclui
  `CO_UNIDADE`, que mata o bug dormente do `LEFT JOIN` em `identidade_prescritor` sem tocar no
  arquivo de domínio (correto: o defeito era do cinturão, não da query).
- Espelho lê `information_schema` e só pede as colunas existentes — a `estabelecimentos_cnes`
  da vitrine é antiga e sem `CO_UNIDADE`; SELECT fixo estouraria no ambiente-alvo.
- As 2 farmácias são **projeção** do seed (não redeclaradas); teste novo proíbe literal de
  identidade no módulo — respeita o guard-rail de identidades da casa.

## §2 J.8/J.9 — conferidos

- **Abas:** 4 no laboratório (Recepção/Agendamento/Realização/Bancada) com faixa "pedido em
  foco" e abertura na aba do próximo gesto; 3 na carteira (Receita/Exames/Atestado), pedido e
  laudo dividindo Exames (mesmo percurso). UI only confirmado — nenhum router/model tocado.
- **Anti-acoplamento ao J.7 cumprido ao pé da letra:** partição por percurso ("já foi
  coletado?"), Realização por negação; **duas guardas estáticas com prova por mutação** (as
  guardas mordem quando sabotadas). Quando o J.7 chegar, os itens chegam `pendente` e a tela
  não retrabalha.
- **403-posse × 403-sessão:** generalização correta do remédio que existia num sítio só;
  `tratarNaoAutorizado` escreve no painel do gesto com sessão intacta; guarda estática proíbe
  colapso em `handleUnauthorized`; J.3 preservado (guarda própria).
- **Aba Agendamento "explicando a lacuna"** (`GET …/agendamentos` recusa dispensador;
  `POST /agendamentos` aceita): honesto e sem tocar RBAC — correto para `module`.

## §3 Determinações

1. **Base dos PRs — superada pelo evento do dia.** O relatório recomenda empilhar o module
   sobre o #162 porque o J.3 vivia lá. **O #162 foi mergeado hoje** (`097534a`, squash) — a
   main ATUAL já contém o J.3. Abrir PR sobre `fix/serie-j-demo-ux` produziria base obsoleta.
   **Determinação:** ambos os PRs (`ops` e `module`) saem de branches novos a partir da main
   atual; o trabalho não commitado carrega limpo (conteúdo idêntico ao do branch antigo).
2. **F5-C3 — aceite a troca de critério.** A ordem Receita·Exames·Atestado é desenho
   explícito do Fabiano (14/08); a asserção posicional media fato de implementação antigo,
   não contrato. O critério novo (painel próprio + nenhum card de exame vazando) é mais
   forte que o posicional. Manter.

## §4 Itens rastreados (novos, fora deste despacho)

- **RBAC assimétrico de agendamentos:** dispensador CRIA mas não LISTA
  (`GET /pedidos-exame/{p}/agendamentos` recusa). Candidato a micro-ticket `module`;
  conversar com o J.10 quando este tocar a área.
- **`test_concorrencia.py` não coleta** (importa `DATABASE_URL_TEST` inexistente no
  conftest) — pré-existente na main; dívida de teste.

## §5 Observações de estado

- O relatório diz "J.7 martelo pendente" — **desatualizado**: o martelo FOI dado hoje
  (Adendo 2 §11a do despacho). J.7 liberado após a abertura destes dois PRs.
- Gates do relatório (unit 1650/52 pré-existentes sem diferença; integração 466 PG efêmero;
  browser 74 com 6 smokes novos) — aceitos; o CI confirma na abertura dos PRs.

---

*Parecer emitido pelo arquiteto (Z) em 2026-08-15. Aprovado com as determinações do §3.*
