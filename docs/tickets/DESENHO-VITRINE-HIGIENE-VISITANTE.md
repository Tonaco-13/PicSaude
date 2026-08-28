# Desenho — higiene da vitrine: o lixo do visitante (nomes chulos)

| Campo | Valor |
|---|---|
| **Origem** | Fabiano, 27/08: *"as pessoas prescrevem nomes chulos, como TEBATO NAKARA"* na vitrine pública |
| **Autor** | Arquiteto (Z) — desenho, **não implementação** |
| **Classe** | Resposta primária: **nenhum código** (martelos do OPS-002). Resposta opcional de fonte: `module` (um PR de tela) |
| **Estado** | M-A ✔ (OPS-002: #212 mergeado, Blueprint aplicado, primeiro run 28/08 04:00 BRT verde) · M-B ✔ implementado (#213, `b0ef413`) · M-C ✔ implementado (#214, `8b714fa`) · **M-D martelado (28/08, direto ao engenheiro) — REVOGA M-B/M-C**: campos travados (readonly), quick-pick removido — adendo §8 |
| **Relacionados** | `DESPACHO-OPS-002-RESET-DEMO-CRON.md` (a cadência que resolve a maior parte) · `DESPACHO-OPS-001` (o ritual manual pré-demo) |

---

## §0 O problema, com precisão

A vitrine é pública e sem barreira (decisão de design: o visitante percorre o loop
livremente). O nome do paciente entra por **texto livre** em três campos — uma por
circulação:

- receita: `pac-nome` (`prescritor.html:570`)
- pedido de exame: `exam-pac-nome` (`prescritor.html:685`)
- encaminhamento: `enc-pac-nome` (`prescritor.html:962`)

O backend não julga conteúdo: `normalize_nome` (`utils/helpers.py:10`) faz
trim → colapsa espaços → uppercase. Nada mais. Um visitante digita "TEBATO NAKARA", e o
nome passa a morar no banco compartilhado — e aparece para o **próximo** visitante (fila
da clínica, busca do dispensador) e para qualquer parceiro numa demo guiada, até alguém
rodar um reset manual.

## §1 O enquadramento: é problema de cadência, não de validação

Três fatos da casa fecham o enquadramento:

1. **Imutabilidade proíbe a limpeza seletiva.** O ledger é guardado por trigger — não
   existe "apagar a receita do TEBATO NAKARA" sem derrubar o schema inteiro. A única
   vassoura que existe é o reset total.
2. **Validação de conteúdo é indecidível.** "TEBATO NAKARA" passa por qualquer régua de
   *forma*: duas palavras, letras, vogais, plausível como nome próprio. Régua que pega
   esse pega também nome legítimo (falso positivo) — ou é blocklist, que é
   whack-a-mole. Nenhuma das duas vale o atrito que adiciona ao loop da vitrine,
   exatamente o que a Regra Zero manda não criar.
3. **A vitrine é um sandbox por decisão.** O estado compartilhado tem até valor cênico
   (a fila viva). O lixo do visitante é custo aceito do formato — o que falta é **limitar
   a janela de exposição**, não policiar a entrada.

Portanto: **limitar a janela de exposição** (cadência de reset) + **tornar o caminho
canônico o caminho preguiçoso** (quick-pick), e nada de polícia de nomes.

## §2 Resposta primária — cadência (nenhum código novo; são os martelos do OPS-002)

- **Reset diário 04:00 BRT** (OPS-002 §7, martelos M1/M2 pendentes): o lixo do visitante
  morre na madrugada — toda manhã de vitrine nasce limpa. Este problema é **mais um
  argumento para dar os dois martelos**, não um ticket novo.
- **Ritual pré-demo, já documentado**: antes de sessão com parceiro, o reset manual do
  OPS-001 (§3–§5) limpa a vitrine em < 2 min. Nada a construir — é operação que já
  existe, só precisa virar hábito.

Juntos, cobrem a dor real (parceiro ver "TEBATO NAKARA" na fila durante demo guiada)
sem tocar numa linha do loop.

## §3 Resposta opcional de fonte — quick-pick de cidadãos demo (`module`)

A chulice nasce da preguiça: digitar nome + inventar um CPF válido é o único trabalho do
form. Se o campo de paciente oferecer **chips de cidadãos canônicos do seed** — um
clique preenche nome + CPF válido — o caminho canônico fica **mais preguiçoso que a
chulice**, e esta perde a motivação.

- Hoje o seed tem **um** cidadão demo: "João Demo da Silva" (`123.456.789-09`,
  `seed_demo.py:11`). Acrescentar o 2º e o 3º é emenda de seed (mesma classe do PR).
- **Texto livre permanece** — a vitrine não ganha gate. Quem quer prescrever para si
  mesmo continua podendo (e essa é uma affordance boa da demo).
- Componente **único, três montagens** (receita, exame, encaminhamento) — o precedente é
  `submodulos.js` (#193): mesma língua por construção, não por disciplina.
- Classificação: `module` — só telas e seed. Nenhuma máquina de estados, ledger ou
  custódia.

## §4 O que este desenho rejeita DE PROPÓSITO

| Rejeição | Motivo |
|---|---|
| Validação de forma/conteúdo no nome | Indecidível para o caso nomeado; falsos positivos em nome legítimo |
| Blocklist de memes/palavrões | Whack-a-mole; evadível; i18n; falso senso de resolução |
| Ocultação/remoção seletiva de objetos chulos | Imutabilidade do ledger (trigger); nem existe gesto de "esconder" no modelo |
| Sandbox isolado por visitante | Horizonte distante se a vitrine virar alto tráfego — parqueado (§5), não escopo |

Registrado aqui para que nenhuma dessas volte à mesa sem reabrir este desenho.

## §5 Fronteira

Demo efêmera por sessão (banco por visitante) resolveria o problema na raiz — e mudaria
a natureza da vitrine (fila viva → cabines individuais). Fora de escopo; se o tráfego
um dia justificar, é desenho novo do arquiteto.

## §6 Martelos (Fabiano)

- **M-A** — os **mesmos** M1/M2 do OPS-002 (autorizar o cron; cadência 04:00 BRT).
  Resolvem a maior parte deste problema como efeito colateral. Sem código novo.
- **M-B** *(opcional)* — aprovar o PR dos chips de cidadãos demo (§3, `module`), para
  reduzir a chulice na fonte sem tocar no texto livre.

---

## §7 Adendo M-C — João fixado por padrão nos QUATRO objetos (Fabiano, 28/08)

**Martelo:** *"fixar João Demo da Silva nos quatro objetos sanitários"*.

**Precisão de leitura — o que "fixar" significa:** preenchimento **padrão** do par
nome+CPF quando o formulário carrega. **Não** é travar o campo: "texto livre
permanece" foi martelo do §3 e continua valendo — a vitrine não ganha gate. A
hierarquia do caminho canônico fica: **padrão (zero cliques) > chips (um clique) >
texto livre (digitar)**. O M-C zera o custo do caso mais comum.

**O quarto objeto.** O M-B (#213) cobriu três montagens — receita (`pac-nome`/
`pac-chave`), exame (`exam-pac-nome`/`exam-pac-cpf`), encaminhamento
(`enc-pac-nome`/`enc-pac-cpf`). O **atestado** (`atestado-paciente` +
`atestado-cpf`) ficou de fora — e é o único dos quatro com CPF **obrigatório**
para o documento digital. M-C fecha o conjunto.

**Spec:**

1. **Quarta montagem** do componente único (`chips-cidadaos-demo.js`) no atestado.
2. **Preenchimento padrão**: no boot (e após qualquer limpeza de formulário que o
   fluxo já faça), os **quatro pares** recebem `DEMO.cidadaos[0]` (João), pelo
   MESMO código interno de fill+dispatch que o clique do chip usa — máscara de
   CPF aplicada igual, eventos nativos idênticos. Uma função de preencher, cinco
   chamadas (4 default + clique): mesma língua por construção.
3. **Sem memória**: nada de localStorage de última escolha — todo render novo
   volta a João. "Vitrine nova de manhã" é o modelo mental; escolha sticky seria
   estado de UI sem dono.
4. **Convivência**: o botão "Preencher com dados da prescrição atual" do atestado
   continua podendo sobrescrever — ordem: default no boot, botão é gesto posterior.

**ACs** (classe `module` — só frontend + config):

- **AC1**: fresh load → os 4 pares mostram João (nome + CPF mascarado), sem clique.
- **AC2**: chips visíveis no atestado (quarta montagem do mesmo componente).
- **AC3**: limpar/editar continua funcionando; **nenhum** gate novo (§4 vale).
- **AC4**: chip continua trocando o par; recarregar a página volta ao padrão.
- **AC5**: guarda de ordem — teste declara `DEMO.cidadaos[0]` = João Demo da
  Silva (`12345678909`): a posição do "fixado" é contrato, não sorteio.
- **AC6**: browser test cobre AC1 e a digitação por cima (AC3).

---

## §8 Adendo M-D — campo travado, sem edição (Fabiano, 28/08, REVOGA M-B/M-C)

**Martelo, direto ao engenheiro (fora do fluxo Z→ticket, decisão do dono):**
*"o que eu quero é fixar, deixar preenchido sem possibilidade de edição. As
pessoas podem preencher com nomes chulos. Aconteceu isso, por essa razão
estamos fazendo esse ciclo."*

**O que muda de fato.** §1(2) e §3 apostavam que tornar o caminho canônico
mais preguiçoso que a chulice bastaria, sem fechar a porta do texto livre —
essa aposta é revogada aqui: **não bastou**. M-D fecha a porta:

1. Os quatro campos de nome/CPF do paciente (receita/exame/encaminhamento/
   atestado) ficam **`readonly`** — sem edição possível pela tela, em vez de
   apenas pré-preenchidos e editáveis (M-C).
2. **O quick-pick do M-B é RETIRADO por inteiro** — texto da fileira de
   chips ("Preencher com cidadão demo: João Demo da Silva / Ana Demo
   Ferreira / Pedro Demo Costa") some da tela. Sem escolha entre cidadãos:
   travado num só, o canônico (`DEMO.cidadao`).
3. Os dois cidadãos extras do M-B/M-C (Ana Demo Ferreira, Pedro Demo Costa)
   são retirados de `config.js` e `seed_demo.py` — existiam só para o
   quick-pick, que não existe mais.
4. §4 continua valendo no que diz respeito a VALIDAÇÃO DE CONTEÚDO — M-D
   não julga o que seria um nome chulo; trava o campo inteiro, o que é
   categoricamente diferente e não reabre a discussão de §1(2).

**Limite declarado — dito em voz alta, não escondido:** isto é um lock de
**FRONTEND**. Quem chama a API diretamente (curl/Postman) ainda escreve o
que quiser em `nome_paciente`/`cpf_paciente` — o backend nunca validou
conteúdo, e M-D não muda isso. Fechar essa porta também exigiria o backend
recusar ou normalizar em `DEMO_MODE` — decisão separada, ainda em aberto,
fora do PR do M-D.

**ACs** (classe `module` — só frontend, sem tocar backend):

- **AC1**: fresh load → os 4 pares mostram o cidadão canônico, sem ação do
  visitante (herdado do M-C, continua valendo).
- **AC2**: os 8 campos (nome+CPF × 4 objetos) não aceitam `.fill()`/digitação
  — verificável como "not editable".
- **AC3**: nenhum `.chip-cidadao-demo` na página — o quick-pick do M-B foi
  removido, não só ocultado.
- **AC4**: suíte de regressão que dependia de preencher esses campos
  (smokes/E2E) segue verde — o valor que ela tentava digitar já é o valor
  travado.

---

*Desenho do arquiteto, 2026-08-27; adendo M-C em 2026-08-28; adendo M-D em
2026-08-28 (martelo direto ao engenheiro, revoga M-B/M-C). Âncoras
conferidas: `prescritor.html` (campos de paciente dos 4 objetos) ·
`cidadao-demo-fixo.js` (API `travar`) · `config.js` (`DEMO.cidadao`) ·
`utils/helpers.py:10` · OPS-001 §3–§5 · OPS-002 §7. Implementação é do
engenheiro.*
