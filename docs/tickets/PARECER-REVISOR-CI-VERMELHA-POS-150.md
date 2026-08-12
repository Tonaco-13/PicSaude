# PARECER-REVISOR — CI vermelha pós-#150 (2 gates)

| Campo | Valor |
|---|---|
| **Revisa** | Mensagem do Kimi 3 (arq. frontend) — CI `gates` vermelha após merge do **PR #150** na main |
| **PR em jogo** | #151 (`local-extension/kimi3-guard-silencio-cpf`, commit `e4e40c9`) — fecha gate 1; gate 2 pendente de martelo |
| **Papel** | Revisor de tickets (parecer **consultivo** — endossa/opina, não bloqueia) |
| **Data** | 2026-08-10 |
| **Veredito** | Gate 1: fix **honesto ✅**. Gate 2: **Opção A correta ✅** (1 condição inegociável). **Opção B rejeitada ❌**. Não destoa — endosso. |
| **Base do parecer** | Código real: `git show e4e40c9`, `main:prescritor.html`, `test_frontend_acao_sem_silencio.py`, `test_frontend_atestado.py` — não a descrição de terceiros |

> Contexto: o #150 migrou `imprimirPedidoFisico()` de `window.print()` (imprimia o
> `#print-area`, que só tem o template do Receituário — bug real) para o padrão PDF-do-servidor,
> espelho de `imprimirAtestadoFisico` (LEARNINGS 2026-07-22). Isso derrubou 2 guardas de teste.

---

## Q1 — O fix do gate 1 (#151) é suficiente e honesto?

**Sim — verificado em `git show e4e40c9`, não na descrição.**

O #150 inseriu o bloco `scrollIntoView/focus` **entre** a notificação (`errCpfEl.textContent`)
e o `return;`. A guarda `test_frontend_acao_sem_silencio` só olha `_JANELA = 3` linhas atrás
(`test_frontend_acao_sem_silencio.py:117`), então o feedback caiu fora da janela → falso "return
mudo". O fix move a **mesma** notificação (texto verbatim) para imediatamente antes do `return;`.

Honesto, não jogo com o teste:
- **Feedback real preservado** — mensagem acionável ("O CPF é obrigatório… campo em Dados do
  Paciente, no topo"). Diz *o que fazer*.
- **UX idêntica** — scroll/focus e `textContent` são síncronos antes do `return`; a ordem entre
  eles é invisível ao usuário.
- Satisfaz a **intenção** da guarda (feedback perto do return), não a contorna. Comentário novo
  documenta o porquê da posição.

Caveat menor (não bloqueia): a guarda é heurística **posicional** (3 linhas), não semântica. O
#150 tropeçou nela com uma inserção legítima (scroll/focus é boa UX), não com falha silenciosa
real. O fix é a resposta pragmática correta; não vale endurecer a guarda agora.

Bônus no mesmo commit: rename `_fisMsg → _mostrar` em `imprimirPedidoFisico`. `_mostrar(` é token
de `_FEEDBACK` (`:108`); `_fisMsg(` não era. Inerte hoje, mas **pré-requisito da Opção A** — sem
mudar comportamento.

> Escopo: o #151 **como commitado fecha só o gate 1**. Gate 2 fica vermelho até o commit 2.

---

## Q2 — A Opção A é a leitura correta da governança?

**Sim.** Três fatos confirmados no código real:

1. **O medo fundador não se aplica.** `imprimirPedidoFisico` na main (pós-#150) é server-PDF
   puro: `POST /pedidos-exame/fisica` → `GET /…/pdf` → `_baixarBlobExame(...)`. **Sem
   `window.open`, sem `window.print()`** (comentário "nunca window.open mudo" em
   `prescritor.html:3517`). O guard `TestImpressaoDaPaginaPrincipal`
   (`test_frontend_atestado.py:164-179`) falha **só** no `assert "window.print()" in corpo`; o
   `assert "window.open" not in corpo` continua passando. O guard trava um **proxy obsoleto**
   (window.print) — o pop-up bloqueado, que é o medo real, não existe em download de blob.

2. **O precedente do atestado é real e fielmente espelhado.** `imprimirAtestadoFisico` é
   server-PDF idêntico (`POST /atestados/fisica` → `/pdf` → `_baixarBlob`), está em `_ACOES`
   (`test_frontend_acao_sem_silencio.py:67`, datado 2026-07-22) e **não** está sob
   `TestImpressaoDaPaginaPrincipal`. A Opção A replica exatamente esse movimento para o exame.

3. **A Opção A EXCEDE o precedente — a favor.** O atestado físico **não tem** guard executável
   contra `window.open` — só um comentário. O `test_pedido_fisico_nao_abre_janela` proposto pelo
   Kimi 3 **trava a proibição em teste**, coisa que o precedente nunca fez. É o R2 (invariante
   executável, não memória) bem aplicado.

**Condição inegociável:** migrar o guard ≠ apagar o guard. A Opção A pode largar o `window.print()`
(proxy obsoleto), mas **tem de manter a proibição de `window.open`** (invariante real). O rascunho
do Kimi 3 faz isso (teste novo + `_sem_comentarios`). Sem esse teste no commit 2, **não passa** —
seria remover a proteção de pop-up junto com o proxy.

**Por que a Opção B está errada:** repopular `#print-area` com template de exame montado no cliente
é o "falso-espelho no nível do DOCUMENTO" que o LEARNINGS 2026-07-22 condena — o impresso deixa de
ser o PDF canônico do servidor (cheiro regulatório: divergência entre impresso e registrado) e
reintroduz o bug do #150. Rejeitada.

---

## Notas de governança

- **O rótulo `local-extension` da branch subestima.** Migrar um guard-rail que codifica decisão de
  segurança de UX é mais pesado que `local-extension` (§10). Não é `core` (não toca
  ledger/estados/custódia/RBAC/doc canônico) — é `module`/frontend com toque de governança. A
  **postura do Kimi 3 de escalar** está certa, independente do rótulo.
- **Lição de processo (não relitigar):** o #150 devia ter migrado o guard **no mesmo PR**. A
  defasagem é o que deixou a main vermelha. Corrige-se adiante com a Opção A.
- **Transparência de escopo:** o diff da Opção A está "aplicado e não commitado" no worktree
  `gap4`, que aparece **`prunable`** (diretório sumido) — **não consegui inspecioná-lo**. Endosso a
  **abordagem** pela descrição + pela realidade do código que verifiquei direto. Antes do merge, o
  Conselheiro/Engenheiro confere o diff real contra estas **4 condições**:
  1. `window.print` sai só de `imprimirPedidoFisico`; `imprimirDireto` permanece na parametrização.
  2. `test_pedido_fisico_nao_abre_janela` trava `window.open` com `_sem_comentarios`.
  3. `imprimirPedidoFisico` entra em `_ACOES` (silence guard).
  4. Literal `17 → 18` mudado com a contagem documentada no docstring de
     `test_registro_nao_encolhe_em_silencio`.

## Bônus (opcional, baixo custo)

Estender o `test_pedido_fisico_nao_abre_janela` para cobrir também `imprimirAtestadoFisico` — o
precedente deixou a proibição de `window.open` do atestado só em comentário. Fecha um gap latente
com uma linha de parametrização.

---

## Encaminhamento

- **Gate 1:** endosso o #151 para merge.
- **Gate 2:** endosso a Opção A sob as 4 condições acima; rejeito a Opção B. Como toca guard
  codificado, o **martelo é do Fabiano** para o Kimi 3 commitar o commit 2. Não precisa voltar ao
  Revisor — o Conselheiro confere o diff real no portão de `core`/governança.
