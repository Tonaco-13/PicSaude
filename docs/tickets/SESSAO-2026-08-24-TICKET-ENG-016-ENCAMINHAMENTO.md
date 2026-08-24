# SESSÃO 2026-08-23/24 — ENG-016: a terceira circulação

| Campo | Valor |
|---|---|
| **Despacho** | ENG-016 (encaminhamento/contrarreferência), sobre o `DESENHO-ENCAMINHAMENTO-UX.md` |
| **Martelos** | Fabiano, 23/08 — justificativa obrigatória (mantida) · finalidade estruturada (entra) · sugestão de destino auditável (entra) · adendo §1a: o gesto `entregar` do cidadão · 24/08 — o `core` do vocabulário e o `versao_esquema` 2 |
| **Executor** | Engenheiro |
| **Base** | `main` em `e85180b` → **`2ad0fb3`** |

---

## §0 Entregue

| PR | Classe | Squash | O quê |
|---|---|---|---|
| **#185** | `core` | `b68506c` | unicidade de posse ativa no encaminhamento **e** na contrarreferência |
| **#186** | `core-doc` | `c86ab27` | o bloco do Encaminhamento no CLAUDE.md **e** no AGENTS.md |
| **#187** | `module` +2 flags `core` | `e5b5cf6` | tela do prescritor, §1a e §5 |
| **#188** | `module` | `2ad0fb3` | carteira do cidadão e o gesto de entregar |

Todos com **igualdade de patch** conferida (`sha256` do diff == patch auditado).

---

## §1 O que a onda mudou de doutrina

**Posse é do cidadão; agenda é compromisso — no terceiro objeto também.** O
`agendar` do destino movia a posse de carona, porque era o único gesto que
existia. Nasceu o **`entregar` do cidadão** (§1a), espelho exato do
`transferir-farmacia` e do `transferir-laboratorio`, e o `agendar` deixou de
escrever custódia. É o J.7 aplicado à terceira circulação.

**O corolário é o ponto, não efeito colateral:** um encaminhamento `agendado`
tanto pode estar com o cidadão (marcou e ainda não foi) quanto com o destino
(já entregou). Quem responde "onde está" é `encaminhamento_custodia`.

**O invariante veio ANTES da escrita nova.** O #185 (índice único de posse
ativa, espelho do #168) foi o PR 1 exatamente por isso: o guarda precede as
telas que passam a escrever custódia. E o teste
`test_cada_gesto_deixa_exatamente_uma_posse_ativa`, criado ali, **passou antes
e depois** de a escrita mudar de gesto — que é a prova de que mover não
afrouxou.

---

## §2 Os dois toques `core` sinalizados, e como foram tratados

**1. `contrarreferencia_registrada` no vocabulário.** Achado da comissão do
bloco §7: o evento era emitido nos dois ledgers — e no `motivo` da custódia da
CR — sem estar declarado. Ninguém errou ao emitir; a lista é que não
acompanhou. Entrou com **guarda executável**: um teste varre os dois ledgers
(helpers e INSERT cru) e afirma que todo evento emitido está declarado.

A guarda distingue as duas direções, e a distinção importa: *emitido ⊄
declarado* é falha dura; *declarado sem emissor* **não é** —
`encaminhamento_em_regulacao` fica travado como **reserva**. Migrações têm
lista de exceção **congelada**, para que uma migração nova que grave outro
evento **acuse** em vez de entrar calada.

**2. `versao_esquema` do documento canônico: 1 → 2.** A finalidade entra no
documento porque o §5 manda a confirmação mostrar o documento montado e o hash
congelar o que se vê — e **hash que não congela o que foi visto é hash que
mente**.

Foi a **primeira evolução de documento canônico pós-emissão** da história do
repositório. Ratificado sob três condições, todas cumpridas e executáveis:

- a regra **v1 continua no código** e reproduz **byte a byte** o hash da `main`
  anterior (congelado por valor no teste — comparar a função consigo mesma
  passaria mesmo quando ela derivasse);
- **compatibilidade versionada provada**: um documento emitido confere sob a
  própria versão, e um v1 confere sob a v1 e **não** sob a v2 — a segunda
  metade é o que prova que a versão é **consultada**, e não ignorada;
- **nada recalcula hash hoje**: guarda estática conta os *call sites* (2, as
  duas emissões) e proíbe comparação de hash. Se nascer um verificador, ela
  cai — e deve cair.

Versão desconhecida levanta **erro explícito**, não cai em default: documento
com versão que este código não conhece **não é documento adulterado** — é
documento que não sabemos verificar, e dizer "não confere" acusaria quem
emitiu.

---

## §3 Decisões de tela que valem registro

**Lista por DEVER, selo por POSSE** (§2 lei 1) — dois campos por linha porque
são duas perguntas. `atendido` é dever do destino com posse no cidadão: uma
lista por custódia faria o item **sumir da tela no exato momento em que vira
obrigação**. É o teste central da entrega.

**A confirmação mostra o documento montado**, não o formulário — a última coisa
que o médico vê é o documento como o destino vai lê-lo, e é isso que o hash
congela.

**Sugestão de destino auditável**: razão declarada, nunca pré-selecionada, e o
que a tela **apresentou** entra no payload de `encaminhamento_emitido`.
`escolheu_sugerido` é **tri-state** — `None` = não houve sugestão, `False` =
houve e não pegou. Colapsar os dois em `False` faria a auditoria contar como
recusa o que nunca foi oferecido.

---

## §4 Erros meus, e onde cada um foi pego

**1. O PR `core` saiu empilhado na branch dos docs.** Os commits estavam
separados, mas a superfície de auditoria do #185 carregava dois arquivos de
docs. Corrigido com `rebase --onto` — obrigatório, porque a base entrou por
**squash** e um rebase comum tentaria reaplicá-la. Ensaiado em worktree
descartável antes de tocar na branch real.

**2. O mini-CID saiu menor que o pedido.** O §5 falava em "~300"; entreguei
**55 códigos verificáveis**. Encher a lista até o número alvo com códigos
plausíveis seria pior: **CID errado entra no hash** e viaja como declaração
clínica de quem emitiu. O escape "não listado" cobre o resto.

**3. `minlength` nativo engolia a mensagem.** A validação do navegador recusa o
submit **antes** do `onsubmit`, então a frase que explica por que a
justificativa é obrigatória nunca aparecia — só a bolha genérica. Validação
migrou para JS.

**4. Escrevi um teste supondo que dava para remarcar.** A máquina devolveu
**409**. Virou o achado A3 da comissão, e foi fechado no ticket da remarcação.

---

*Relatório do Engenheiro. Desenho do arquiteto versionado neste PR.*
