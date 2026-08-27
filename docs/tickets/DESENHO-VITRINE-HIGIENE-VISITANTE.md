# Desenho — higiene da vitrine: o lixo do visitante (nomes chulos)

| Campo | Valor |
|---|---|
| **Origem** | Fabiano, 27/08: *"as pessoas prescrevem nomes chulos, como TEBATO NAKARA"* na vitrine pública |
| **Autor** | Arquiteto (Z) — desenho, **não implementação** |
| **Classe** | Resposta primária: **nenhum código** (martelos do OPS-002). Resposta opcional de fonte: `module` (um PR de tela) |
| **Estado** | 🟢 **Martelado (Fabiano, 27/08)**: M-A coberto pelos M1/M2 do OPS-002; **M-B aprovado** — PR `module` dos chips liberado |
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

*Desenho do arquiteto, 2026-08-27. Âncoras conferidas: `prescritor.html:570/685/962` ·
`utils/helpers.py:10` · `seed_demo.py:11` · OPS-001 §3–§5 · OPS-002 §7. Implementação,
se M-B for aprovado, é do engenheiro.*
