# Comissão de diagnóstico — Regra Zero (S1–S5-bis · R1–R3 · achados)

| Campo | Valor |
|---|---|
| **Régua** | *"a movimentação SEM ATRITO do objeto sanitário, ancorada ao CPF (chave)"* — Fabiano, 23/08 |
| **Origem** | Atritos reportados pelo Fabiano na vitrine + acréscimos do arquiteto (S5-bis) e achados do engenheiro |
| **Executor** | Engenheiro · **diagnóstico, sem correção** |
| **Base** | `main` em `2ad0fb3` (ENG-016 fechado) |
| **Método** | reproduzir (ou não) → causa **provada no código** → classificar `BUG · GAP · DECISÃO` → medir atrito (cliques; de quem é o próximo gesto) |

> **Nada foi corrigido.** Uma sonda de reprodução foi escrita, executada e
> **apagada**; a árvore está limpa. A análise sai daqui, com o Fabiano e o
> arquiteto.

---

## Quadro-resumo

| # | Sintoma | Reproduz? | Classe | Atrito |
|---|---|---|---|---|
| **S1** | exame não comunica pós-resultado | **sim** | `GAP` | cartão diz "Resultado disponível" e **não leva a lugar nenhum** |
| **S2** | agenda da clínica sem CPF | **sim** | **`BUG`** | dado já chega do backend e não é desenhado |
| **S3** | fluxo estático pós-resultado | **sim** | **`GAP` grave** | o próximo gesto é **inalcançável**: endpoint sem botão |
| **S4** | laudo não chega ao cidadão | **NÃO** (cadeia funciona) | `GAP` de percepção | chega, mas **sem aviso** e a 1 rolagem de distância |
| **S5** | PDF para o cidadão | parcial | `GAP` | receita e pedido de exame **sem PDF para o dono** |
| **S5-bis** | PDF do exame no Histórico | n/a | `DECISÃO` + `GAP` | custo baixo; padrão já existe |
| **R1** | aba Laudo na clínica | n/a | `DECISÃO` | médio |
| **R2** | Laudos na carteira com recebimento | n/a | `DECISÃO` | baixo-médio |
| **R3** | reversibilidade até o Histórico | n/a | `DECISÃO` | alto e **desigual entre objetos** |

---

## S1 — o exame não comunica com o cidadão depois do resultado

### O que o cartão mostra hoje, estado a estado (verificado)

`cidadao.html::renderizarPedidosExame` monta **duas coisas independentes**: a
etiqueta (`_rotuloStatusExame`) e a área de ação (`acaoHtml`).

| Estado do pedido | Etiqueta | Área de ação |
|---|---|---|
| `emitido`, em posse | "Com você" | formulário de transferência |
| `emitido`, entregue | "No laboratório" | "Custódia transferida" |
| `coletado` | "Coletado" | "Custódia transferida" |
| `em_analise` | "Em análise" | "Custódia transferida" |
| `resultado_disponivel` | "Resultado disponível" | **"Custódia transferida"** |

### A causa, no código

A área de ação tem **dois ramos e só dois** — `emPosse ? … : …`. Do
`coletado` em diante o texto é **literalmente o mesmo**:

> "Custódia transferida — O pedido está com o laboratório. Você acompanha o
> resultado aqui e em *Laudos / Resultados*."

E dentro de `renderizarPedidosExame` a palavra `laudo` aparece **zero vezes**
(conferido): o cartão **cita** a seção pelo nome e **não linka** para ela.

### O atrito

O momento de maior interesse do cidadão — "meu resultado saiu" — é o momento
em que a tela menos fala com ele. A etiqueta muda; a instrução, não. Para
chegar ao resultado ele tem de **ler a frase, memorizar o nome da seção,
rolar a página** e achar o laudo pelo nome do exame.

**Classe: `GAP`.** Nada está errado; falta a ponte. É exatamente o problema que
o ENG-015 §4 resolveu para o agendamento (selo → aba), e a solução é da mesma
família.

---

## S2 — a agenda da clínica não mostra o CPF

### Reprodução e causa — provadas

O backend **já manda o CPF**:

```python
# routers/dispensadores.py:385  (fila de exames)
"paciente": {"nome": p["paciente_nome"], "cpf": _cpf_display(p["paciente_cpf"])},
```

A tela **não o lê**. Em `clinica.html::renderizarAgendaDaUnidade` o único campo
de identidade desenhado é `p.paciente?.nome`. No cartão da fila, idem: `cpf`
aparece **zero vezes**. Em toda a `clinica.html`, `paciente.cpf` é usado **uma
única vez** — na linha 3152, para **montar o laudo**, nunca para exibir.

### O atrito

A Regra Zero diz que o objeto é ancorado **ao CPF**. A agenda identifica por
**nome**. Dois "João da Silva" no mesmo dia são indistinguíveis, e o operador
não tem como conferir a identidade de quem está na frente dele sem abrir o
pedido — **+2 cliques** (abrir → ler) por conferência, num gesto que deveria
ser de leitura.

**Classe: `BUG`.** O dado chega, tem função de chave, e é descartado na
renderização. É código meu (ENG-015 PR 2) — anoto como meu.

---

## S3 — o fluxo "estático" pós-resultado

### O achado principal desta comissão

`POST /pedidos-exame/{protocolo}/encerrar` **existe**, aceita
`prescritor · admin · paciente`, e a sua docstring diz:

> "resultado_disponivel" e "encerrado" NÃO são o mesmo estado:
> resultado_disponivel = laudo pronto, aguarda ciência;
> encerrado = ciência registrada, ciclo completo.

**Nenhuma das três telas o chama.** Busca ampla por `encerrar` em
`cidadao.html`, `clinica.html` e `prescritor.html`: as **únicas** ocorrências
são as do **encaminhamento**, que acabei de escrever no ENG-016. O pedido de
exame tem cobertura de integração (`test_pedidos_exame_encerramento.py`) e
**zero chamadores de produto**.

### Quem tem o próximo gesto, e onde ele aparece

| Estado | Próximo gesto | De quem | Onde aparece |
|---|---|---|---|
| `coletado` | enviar à bancada / registrar resultado | laboratório | aba Bancada ✅ |
| `em_analise` | registrar resultado | laboratório | aba Bancada ✅ |
| `resultado_disponivel` | produzir/liberar laudo | laboratório | rodapé da Bancada ✅ |
| `resultado_disponivel` (laudo liberado) | **dar ciência → `encerrado`** | **cidadão ou prescritor** | **EM LUGAR NENHUM** ❌ |

### O atrito

**Infinito — o gesto é inalcançável pela interface.** Não é repouso de desenho:
o J.1 desenhou o repouso em `resultado_disponivel` *aguardando ciência*, e a
ciência não tem porta. Todo pedido de exame da vitrine morre nesse estado.

O `resultado_disponivel` não *parece* morte: para efeito de tela, **é**.

**Classe: `GAP` grave.** Mais grave que S1, porque S1 é uma ponte que falta e
S3 é o **fim do percurso** que não existe.

> **Nota de coerência:** o encaminhamento tem ciência explícita (`encerrar`,
> §2 lei 7) e **ganhou botão** no ENG-016. O laudo tem ciência por abertura
> (ENG-014) e **tem botão**. O pedido de exame tem ciência explícita e **não
> tem**. É o único objeto da casa com o ciclo aberto na tela.

---

## S4 — o laudo produzido na bancada não chega ao cidadão

### NÃO REPRODUZ. A cadeia funciona.

Sonda executada contra o app de demo, ciclo completo com as personas do seed:

```
apos transferir           → laudos_disponiveis: 1   (o do seed)
apos COLETAR              → 1
apos BANCADA (em_analise) → 1
apos RESULTADO            → 1
criar laudo               → 201
laudo assinar             → 200 · laudos_disponiveis: 1
laudo liberar             → 200 · laudos_disponiveis: 2   ← CHEGOU
```

**`liberar` é o gesto que entrega** (cria a custódia `prestador → paciente`).
`assinar` sozinho não entrega — e está certo assim.

E a tela da clínica **não depende do operador lembrar**: o botão de laudo
executa `criar → assinar → liberar` **encadeados**, num gesto só
(`clinica.html`, §§1–3 do bloco de laudo).

### Então de onde vem o sintoma

Da carteira, não da produção. Depois de liberado, o laudo aparece **em
"Laudos / Resultados"**, uma seção **abaixo** de "Pedidos de Exame Ativos"
dentro da aba Exames — e:

- **nada avisa** que ele chegou (o contador da aba soma pedidos + laudos, então
  o número muda **sem dizer por quê**);
- **o cartão do exame não aponta para ele** (S1);
- é preciso **rolar** e reconhecer o laudo pelo nome do exame.

**Classe: `GAP` de percepção** — e é o mesmo `GAP` do S1 visto do outro lado.
S1 e S4 são **um defeito só**: falta o elo exame → laudo na carteira. Tratá-los
como dois pode gerar duas soluções que não se encontram.

---

## S5 — PDF por objeto: o que existe e o que falta ao cidadão

### Inventário verificado (`require_role` de cada endpoint)

| Objeto | Endpoint | Papéis | Cidadão baixa? | Tem botão na carteira? |
|---|---|---|---|---|
| Atestado | `/atestados/{p}/pdf` | prescritor · admin · **paciente** | ✅ | ✅ |
| Laudo | `/laudos/{p}/pdf` | prescritor · admin · **paciente** · dispensador | ✅ | ✅ |
| Encaminhamento | `/encaminhamentos/{p}/pdf` | prescritor · **paciente** · admin | ✅ | ❌ **sem botão** |
| **Receita** | `/prescricoes/{p}/pdf` | prescritor · dispensador · admin | ❌ **403** | ❌ |
| **Pedido de exame** | `/pedidos-exame/{p}/pdf` | prescritor · admin | ❌ **403** | ❌ |

### O atrito, medido pela Regra Zero

O cidadão **detém a custódia** da receita e do pedido de exame — são dele, estão
na carteira dele — e **não consegue obter o PDF do que carrega**. O papel
`paciente` não está no `require_role` dos dois.

É a contradição mais direta com a régua no relatório inteiro: o objeto está
ancorado ao CPF dele, a posse é dele, e o documento não é.

**Classe: `GAP`** nos dois casos. Não é bug — foi decisão de escopo de quando os
endpoints nasceram —, mas colide de frente com a Regra Zero.

**Encaminhamento é caso à parte:** o backend **já autoriza** o cidadão; falta só
o botão. Custo: uma função de download igual à do atestado.

---

## S5-bis — PDF do exame executado, no Histórico da clínica

### Delimitação do arquiteto, conferida no código

- **NÃO** abrir `GET /pedidos-exame/{p}/pdf` ao dispensador: hoje é
  `prescritor · admin`, e o pedido é artefato de **quem emitiu**. Abrir daria à
  clínica o documento do prescritor. ✅ a delimitação procede.
- **É** um comprovante do que a unidade **executou**, sob escopo de posse do
  CNPJ, pelo padrão já existente:

```python
# routers/clinicas.py::relatorio_exames_pdf
usuario=Depends(require_role("dispensador"))
cnpj = normalize_cnpj(usuario["sub"])     # escopo vem do JWT, não do payload
linhas = _linhas_do_cnpj(conn, cnpj)      # posse provada, não declarada
```

### Custo

**Baixo.** O padrão está pronto: dois PDFs da clínica já nascem assim
(`relatorio.pdf`, `faturamento.pdf`), com o CNPJ vindo do JWT e o escopo pela
custódia. O novo seria um terceiro no mesmo molde, por **exame executado** em
vez de por período.

**Classe: `DECISÃO`** (o que o comprovante mostra: só o item executado? o laudo
junto?) **+ `GAP`** (não existe).

**Prioridade pela Regra Zero: ABAIXO do S5.** O cidadão não conseguir o PDF do
que carrega é atrito na circulação; a clínica não ter comprovante é atrito na
retaguarda. A régua fala da movimentação do objeto.

---

## R1 · R2 · R3 — propostas de desenho

### R1 — aba Laudo na clínica · `DECISÃO`, custo médio

Hoje o laudo vive no **rodapé da aba Bancada**, atrelado ao pedido em foco
(`renderizarGatilhoLaudo`). A clínica não tem onde responder *"quais laudos eu
tenho em produção?"* — só o Histórico, que é read-only e do que já passou.

- **A favor:** simetria com a agenda da unidade (ENG-015 §3), que resolveu
  exatamente isto para o compromisso: pergunta própria, aba própria, **sem
  exigir pedido em foco**.
- **Custo:** uma 6ª aba na clínica + a lista agregada. Se seguir o padrão da
  agenda (agregar da fila, escopo por custódia), **não precisa de endpoint
  novo** — o laudo vigente já está ao alcance por pedido.
- **Contra:** seis abas é muita aba. Vale perguntar se o Histórico + o rodapé
  da Bancada não cobrem, com o laudo em produção **sinalizado na Bancada**.

### R2 — submódulo Laudos na carteira, com o RECEBIMENTO visível · `DECISÃO`, custo baixo-médio

**O recebimento já é um fato registrado** e não é mostrado: `liberar` cria a
custódia `prestador → paciente`. Existe o instante em que o laudo **chegou às
mãos do cidadão**, e a carteira não o exibe — mostra status e "Ciência
registrada", nunca "chegou em dd/mm".

- **A favor da Regra Zero:** é o **handoff** — o momento em que o objeto mudou
  de mãos, que é justamente o que a régua manda tornar visível. E resolve S1/S4
  de carona se o submódulo nascer **linkado ao cartão do exame**.
- **Custo:** baixo no backend (o dado existe na custódia do laudo); médio na
  tela (uma aba a mais na carteira, que já tem cinco).
- **Alternativa mais barata:** não criar aba; **mostrar o recebimento no cartão
  do laudo** e **linkar o cartão do exame ao laudo**. Fecha S1, S4 e o
  "recebimento invisível" **sem** sexta aba.

### R3 — reversibilidade total até o Histórico · `DECISÃO`, custo alto

Hoje a reversibilidade é **desigual entre objetos** (contagem de gestos de
reversão por router):

| Objeto | Gestos de reversão |
|---|---|
| pedido de exame | 10 (devolver, cancelar…) |
| laudo | 5 |
| encaminhamento | 2 (cancelar, negar) |
| **receita** | **0** |
| **atestado** | **0** |

- **A favor:** previsibilidade — o operador aprende **uma** regra em vez de
  cinco.
- **Contra, e é sério:** "reversibilidade total" colide com §1 (objeto emitido é
  imutável) e com a doutrina de **estorno como objeto derivado** (§2a). O que a
  casa chama de reverter é **criar um fato novo que compensa**, nunca desfazer.
  Uma proposta de reversibilidade uniforme precisa dizer, objeto a objeto, qual
  é o **fato compensatório** — e para atestado e receita hoje não há resposta.
- **Custo:** alto, e é `core` em cada objeto que tocar.
- **Recomendação:** **não tratar como um item só.** Quebrar por objeto e
  priorizar onde o atrito foi sentido de verdade na vitrine.

---

## Achados do engenheiro (fora da lista original)

### A1 — bug de fuso na janela dos relatórios · **`BUG`**, com prova numérica

```
local  2026-08-23 21:24 -03      UTC  2026-08-24 00:24
janela do relatório → até 2026-08-23 23:59:59   (date.today(), hora LOCAL)
registro gravado    →    2026-08-24 00:24       (datetime.utcnow())
dentro da janela?   → False
```

`dispensadores.py::_janela_periodo` fecha a janela em **meia-noite local**; os
registros são carimbados em **UTC**. No fuso −03, **tudo o que for criado entre
21h e 24h cai fora** do padrão de 30 dias.

**Alcance medido:** 10 arquivos de integração, 1 de unidade e 3 casos de
navegador — SNGPC, faturamento, histórico da clínica e o E2E do laboratório.

**Confirmação independente:** os mesmos arquivos passaram sozinhos depois da
meia-noite local, sem nenhuma mudança de código. **Só o relógio mudou.**

### A2 — CI cego a esta classe inteira · **`GAP` de processo**

O CI roda em **UTC**, onde local e UTC coincidem: **nunca viu**. Um defeito real
de produção ficou invisível ao gate por escolha de fuso do runner.

**Lição derivada (formulação do arquiteto, endossada):** teste que depende de
relógio de parede precisa de **TZ pinado** ou **relógio injetado**. Hoje não há
nem um nem outro — e é por isso que o mesmo defeito voltou (é a família do "500
do faturamento por fuso", já registrado em sessão anterior).

### A3 — o encaminhamento não tem remarcação · **`GAP`**

`TRANSICOES_ENCAMINHAMENTO` não admite `agendado → agendado`, e não existe
`/remarcar` como no objeto Agendamento. Descoberto escrevendo o teste: a máquina
devolveu **409**. Mudar a data hoje exige cancelar e emitir de novo — o que,
sendo objeto imutável (§1), é **derivação**, não edição.

Não é bug: nada quebra. É capacidade ausente, e o objeto Agendamento mostra qual
seria a forma.

---

## Leitura de conjunto — o que a Regra Zero mostra que a lista não mostrava

Sete dos nove itens são **a mesma família**: *o fato aconteceu no banco e não
apareceu na tela*.

- o laudo chegou (S4) — e nada avisou;
- o resultado saiu (S1) — e o cartão não levou até ele;
- a ciência pode ser dada (S3) — e não há botão;
- o recebimento foi registrado (R2) — e não é exibido;
- o CPF foi enviado (S2) — e não foi desenhado.

**Nenhum deles é falha de núcleo.** Ledger, custódia e estados estão certos em
todos os cinco. O atrito está inteiro na **última milha** — e é exatamente o que
a régua do Fabiano prevê: *peças certas isoladamente, atrito percebido no todo*.

Isso sugere que a análise trate S1+S4 como **um** item, e que S3 seja o
**primeiro** a ser resolvido: é o único em que o percurso não tem fim.

---

*Diagnóstico do Engenheiro, 24/08. Sonda de reprodução executada e apagada;
nenhuma correção aplicada. As classificações são propostas — a decisão é do
Fabiano com o arquiteto.*
