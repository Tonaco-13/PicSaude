# PARECER-ARQ — Receita Viva onda 1, pós-Kimi: ratificada pelo uso; a alma visual segue na estação

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Objeto** | `PARECER-KIMI-RECEITA-VIVA-ONDA-1` (21/09, uso real) + auditoria visual ao vivo do arquiteto (21/09, 1440px) |
| **Data** | 21/09/2026 |
| **Leitura** | **Endosso integral do veredito dela — onda 1 RATIFICADA PELO USO** — com uma reconciliação que o parecer dela não podia fazer (o método dela não cobriu a camada visual, §4.3 dela) e duas adjudicações para a onda 2 |

---

## §1 O endosso

O método da Kimi é o mais forte que esta casa já viu numa onda de UI: emissão real
(losartana 50 mg × 30, protocolo `9ba9429f…`), o **W≡Y verificado EM RUNTIME no
estado emitido** (chamada viva a `textoDoDocumento` nos dois alvos → true), e a
suíte unitária re-rodada por ela, independente de mim (15/15) e independente do CI.
Três provas independentes do mesmo invariante — a martelada ② é fato, não intenção.

O achado dela sobre `test_o_hash_de_integridade_nao_e_mais_descartado` nomeia um
débito que ninguém tinha visto: **o hash antes ia ao limbo no print**. A onda 1
quitou sem anunciar. Registrado.

## §2 As duas almas — reconciliação honesta

O parecer dela diz *"o conceito virou produto sem perder a alma"*; a minha auditoria
visual disse o contrário. **Os dois estão certos — são duas almas diferentes:**

- **A alma funcional** (a promessa: zero surpresa, a folha É o documento) — **sã**,
  provada em runtime pela Kimi.
- **A alma visual** (o papel sobre a mesa: creme, serif, borda quente, selo) — **fica
  na estação**, provado pela minha captura ao vivo contra a captura do protótipo
  (`conceitos-prescritor/capturas-producao/01-desktop-estado-vazio-2026-09-21.png`).

O parecer dela é silente sobre a visual porque o método dela não a cobriu (§4.3:
painel fechado no meio da sessão, sem capturas) — não porque a aprovasse.

**Uma correção à MINHA auditoria** (fonte vence briefing, inclusive o meu): a Kimi
viu as **lacunas pontilhadas em runtime** (AC2 dela, "CEP: cep", "Tel: telefone"
pontilhados). Minha leitura estática da captura disse "sem pontilhado visível" —
o runtime dela é a evidência melhor. O ponto rebaixa de "ausente" para
**"sutil demais"**: o pontilhado existe, mas não conversa — e o conceito pedia "o
branco do papel esperando a caneta". Entra no polimento como legibilidade, não como
construção.

## §3 Adjudicações para a onda 2

1. **Um gerador por documento + núcleo compartilhado — ENDORSO.** A leitura dela é
   a lição da casa dita de novo: *"duas anatomias diferentes numa função só é a
   dupla posse pela porta dos fundos"*. O que generaliza é o NÚCLEO
   (lacuna, tinta por `data-bloco`, W≡Y, `montar`/`textoDoDocumento`, `MODOS`) —
   que o `receituario.js` já entregou **host-agnostic** (não lê DOM, não fala com
   endpoint: recebe estado, devolve HTML). A anatomia fica por documento:
   `pedidoexame.js`, `encaminhamento.js`, `atestado.js`.
2. **Ordem das ondas — RECOMENDO AO FABIANO (martelo dele, mexe no ladder de
   15/09):** **Receita → Exame → Encaminhamento → Atestado.** A lógica da Kimi
   inverte a intuição com razão: o exame é quase isomorfo à receita (remontagem
   barata, valida o padrão no caso favorável); o atestado é o degenerado monolítico
   (a prova de verdade da generalização) e fecha a série. O encaminhamento fica no
   meio — anatomia própria (destino, especialidade), mas com itens, e se beneficia
   do núcleo já amadurecido.
3. **O gancho da posologia (§5 dela) — registrado como débito declarado:** quando a
   ENG-019 pousar, a posologia em itálico da folha viva é onde a `posologia_sugerida`
   (chave `(ativo, CID)`) deve poder ser **editada, não só exibida**. Item da onda
   do exame ou de polimento futuro — nunca esquecido, nunca agora.

## §4 Gestos que saem deste parecer

- **Plural da unidade** (§4.1 dela): adotado como o gesto de demonstração da
  martelada ② — uma correção no `_item` do `receituario.js`, folha + print + 2ª via
  curadas de uma vez. Vai no polimento.
- **DESPACHO-ENG-020 (polimento da onda 1)**: lavrado junto deste parecer, na mão
  do Fabiano — estética NORMATIVA (o adendo que faltou no ENG-018) + plural + DDD
  truncado + flag do conselho da Dra. Demo. Colar **após a ENG-019 pousar** (a
  árvore está com o engenheiro vivo agora).

— Arquiteto (Z), 21/09/2026
