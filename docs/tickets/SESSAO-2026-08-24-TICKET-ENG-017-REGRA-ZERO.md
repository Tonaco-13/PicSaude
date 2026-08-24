# SESSÃO 2026-08-24 — ENG-017: a última milha, sob a Regra Zero

| Campo | Valor |
|---|---|
| **Origem** | Atritos que o Fabiano reportou na vitrine → comissão de diagnóstico (#189) → onda ENG-017 |
| **Régua** | **REGRA ZERO** (Fabiano, 24/08): *a movimentação sem atrito do objeto sanitário, ancorada ao CPF (chave)* — entra na constituição neste PR |
| **Martelos** | Fabiano, 24/08 — onda autorizada ("pode mandar ver") · `core` do PDF do dono (martelo próprio) · a ciência do pedido **não** se deriva de abrir o laudo · **pílulas, não cartões** |
| **Executor** | Engenheiro |
| **Base** | `main` em `2ad0fb3` → **`e3ea403`** |

---

## §0 Entregue

| PR | Classe | Squash | O quê |
|---|---|---|---|
| **#189** | `docs` | `703623b` | comissão de diagnóstico da Regra Zero |
| **#190** | `module` | `2da74f6` | última milha: ciência do exame, elo do laudo, CPF na agenda |
| **#193** | `module` | `a31bbc4` | carteira e prescritor na **mesma** barra de submódulos |
| **#192** | `module` | `a3e63e5` | janela de relatório em UTC + o gate deixa de ser cego ao fuso |
| **#191** | `core` | `d2a7ec9` | o dono baixa o papel que carrega |
| **#194** | `module` | `e3ea403` | remarcação do encaminhamento como **re-ato** |

Gates finais: unit **592** · integração **629** · navegador **124**.

---

## §1 O que a comissão descobriu, e que reorganizou a própria lista

Sete dos nove itens eram **a mesma família**: *o fato aconteceu no banco e não
apareceu na tela*.

- o laudo chegou — e nada avisou;
- o resultado saiu — e o cartão não levava até ele;
- a ciência podia ser dada — e não havia botão;
- o recebimento foi registrado — e não era exibido;
- o CPF foi enviado — e não era desenhado.

**Nenhum deles era falha de núcleo.** Ledger, custódia e estados estavam certos
nos cinco. O atrito estava inteiro na **última milha** — que é exatamente o que
a Regra Zero prevê: peças corretas isoladamente, atrito percebido no todo.

Três achados mudaram a leitura da lista que os originou:

**S3 era o mais grave e não estava na lista como tal.** `POST
/pedidos-exame/{p}/encerrar` existia, aceitava `paciente`, tinha testes de
integração — e **nenhuma das três telas o chamava**. Todo pedido da vitrine
morria em `resultado_disponivel`. **Não era o repouso do J.1**: o J.1 desenhou
repouso *aguardando ciência*, e a ciência não tinha porta. Atrito **infinito**,
porque o gesto era inalcançável.

**S1 e S4 eram um defeito só.** S4 **não reproduziu** — a sonda mostrou o laudo
chegando na liberação, e a tela da clínica encadeia `criar → assinar → liberar`
sozinha. O sintoma nascia da carteira: dentro de `renderizarPedidosExame` a
palavra `laudo` aparecia **zero vezes** — o cartão **citava** a seção pelo nome
e não linkava. Tratá-los como dois itens teria gerado duas soluções que não se
encontram.

**S5 era a colisão mais direta com a régua.** O cidadão detinha a custódia da
receita e do pedido de exame e levava **403** no PDF de ambos.

---

## §2 As decisões que a execução exigiu

**A ciência do pedido não se deriva de abrir o laudo** (martelo). Ciência do
laudo é do laudo (ENG-014: abrir é dar ciência); ciência do pedido é do pedido.
Fundi-las faria **abrir um PDF encerrar um pedido de exame** — e ninguém desfaz
o que declarou sem querer. Há teste que cai se alguém "simplificar".

**Ownership por CPF do documento, não por custódia** (#191). A receita pode
estar na farmácia no momento do download e continua sendo o documento dele.
*Custódia responde "onde está"; ownership responde "de quem é".* Há teste
provando que entregar o pedido ao laboratório **não tira do cidadão o próprio
papel**.

**`dispensador` continua fora do PDF do pedido**, e não por esquecimento: o
pedido é artefato de quem emitiu. O comprovante da clínica é outro documento,
por posse (S5-bis). Há teste que cai se alguém "completar" a lista por simetria.

**O elo do laudo só existe depois de LIBERADO.** Em produção ou apenas
assinado, o laudo não é do cidadão — a custódia não passou —, e anunciá-lo
prometeria o que ele não pode abrir. Sem laudo ainda, o cartão **explica** que
falta um passo do laboratório, em vez de mostrar link morto.

---

## §3 O bug de fuso, e por que o gate era cego

```
local  2026-08-23 21:24 -03      UTC  2026-08-24 00:24
janela do relatório → até 2026-08-23 23:59:59   (date.today(), LOCAL)
registro gravado    →    2026-08-24 00:24       (utcnow(), UTC)
dentro da janela?   → False
```

Registros carimbados em UTC, janela fechando em meia-noite **local**. No fuso
−03, **tudo criado entre 21h e 24h caía fora** do relatório padrão. Alcance
medido: 10 arquivos de integração, 1 de unidade, 3 de navegador.

**Confirmação independente:** os mesmos arquivos passaram sozinhos depois da
meia-noite, sem mudança de código. **Só o relógio mudou.**

**O CI nunca viu** porque roda em UTC, onde local e UTC coincidem — segunda vez
desta família (a primeira foi o "500 do faturamento por fuso").

A correção nasceu com **fonte única** (havia duas cópias de `_janela_periodo`
com o mesmo defeito). E a guarda principal **não** é o job de TZ pinado: entre
00h e 21h UTC os dois dias coincidem e ele passaria de qualquer jeito. Um gate
que pega o defeito **3h em 24** é melhor que nada e pior que suficiente. A
guarda que vale é a **reprodução aritmética** do instante exato da comissão,
com `zoneinfo`, que independe de quando a suíte roda. O job de TZ entrou como
defesa em profundidade, **declarado como tal** no workflow.

---

## §4 A língua visual: pílulas, idênticas por construção

Decisão do Fabiano (24/08), após um primeiro corte em cartões: **sem cartões —
pílulas**, iguais às do prescritor.

**Um arquivo, duas telas.** `submodulos.js` + `submodulos.css` desenham as duas
barras. Não é "mesma aparência mantida por disciplina": é a mesma aparência
**porque é o mesmo código**, e não existe o estado intermediário em que uma
tela andou e a outra ficou.

O CSS **não foi redesenhado — foi promovido** de `prescritor.html` para o
arquivo compartilhado. Quem olhava aquela tela ontem vê a mesma barra hoje.

**O cuidado novo:** a barra do prescritor tinha 3–4 itens e cabia numa linha; a
carteira tem **seis**, e o `flex: 1` original não tinha piso — em tela estreita
as pílulas espremeriam até truncar. `flex: 1 1 120px` + `flex-wrap: wrap`: a
barra cresce em **altura**, nunca fica ilegível em largura.

**Achado corrigido de carona:** os painéis do prescritor eram `form-*`, e o
`aria-controls` das pílulas aponta para `submod-<chave>`. Adotar o componente
sem renomear deixaria o **ARIA apontando para o vazio** — acessibilidade de
fachada. Há teste que lê o `aria-controls` da pílula e confere que o alvo
**existe**.

**Guardas anti-cópia:** as duas telas carregam o componente, nenhuma reescreve
as pílulas à mão, nenhuma redefine o CSS localmente. *"Só ajustar uma coisa"*
não é desculpa para ressuscitar duas cópias.

---

## §5 A remarcação como re-ato (#194)

**A data da visita é atributo do compromisso, não identidade do
encaminhamento.** A regra da casa — *remarcação = novo objeto derivado* — vale
quando o objeto **É** o compromisso (Agendamento: AG-001 → AG-002). Aqui o
objeto é o encaminhamento clínico, e derivá-lo inteiro para trocar um horário
copiaria conteúdo clínico para mover uma marca de calendário.

**Três negativas, três testes** — porque *"não criei nada"* é a afirmação mais
fácil de fazer e a mais fácil de furar depois: nenhum estado novo; **nenhum
self-loop** em `agendado` (o ato não é transição — é aditivo no ledger e
idempotente no estado); nenhum evento novo (reusa `encaminhamento_agendado` com
`{data_anterior, data_nova}`).

---

## §6 Método que se repetiu, e vale guardar

**Teste testa REGRA, não acidente.** Quatro testes cederam nesta pré-temporada,
e em todos o que caiu foi acidente do momento em que foram escritos:

| Teste | Acidente que caiu | Regra que ficou |
|---|---|---|
| `test_403_de_posse_nao_derruba_a_sessao` | o 403 era fácil **porque era defeito** | 403 de posse não desloga |
| `test_j11_selo_e_lente` | a contagem de abas do momento | a data chega ao cartão **sem** navegação |
| `test_selo_le_o_campo_do_backend` | a **assinatura** literal da função | a **fonte** do dado |
| `test_a_carteira_le_a_marcacao_MAIS_RECENTE` | o **409** que era o buraco | a carteira mostra a data que vale |

**Supersessão escrita, com martelo citado** — o padrão para teste ou comentário
que cede: o arquivo diz o que mudou, quando, por ordem de quem, e o que
**continua** valendo.

**Guarda conferida por mutação**, sempre. E **vermelho antes de verde** em tudo
que corrige defeito.

**Prova mecânica de merge:** `sha256` do patch, não leitura da mensagem. Em PR
empilhado, base **declarada** e recálculo com `rebase --onto` ensaiado em
worktree descartável — a base entra por squash, e um rebase comum a reaplicaria.

---

## §7 Estado ao fechar a pré-temporada

- **Três circulações completas** — receita, exame/laudo, encaminhamento — sem
  atrito conhecido.
- **Uma língua visual única**, garantida por construção.
- **Núcleo provado por invariantes** de banco nos dois dialetos, não por
  convenção de código.
- **A Regra Zero na constituição**, primeira linha do §7 (este PR).
- **Fila de código vazia.** O que resta é **go-public**, parqueado para
  conversa do Fabiano — nada abre sem gatilho dele.

---

*Relatório do Engenheiro, 24/08. Desenhos do arquiteto versionados neste PR.*
