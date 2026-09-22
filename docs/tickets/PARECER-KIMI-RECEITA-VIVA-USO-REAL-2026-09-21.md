# PARECER-KIMI — Receita Viva onda 1, USO REAL: a promessa se sustenta — e a primeira prova de fogo do template único já apareceu

| Campo | Valor |
|---|---|
| **De** | Kimi 3 — análise de uso real |
| **Para** | Arquiteto (Z) |
| **Data** | 21/09/2026 — a pedido do martelo do Fabiano: *"vamos pedir a opinião do Kimi antes de passarmos aos outros objetos"* |
| **Objeto** | PR #268, merge `45a7dae`, no ar desde 21/09 ~15:02 BRT |
| **Método** | Leitura estática do diff + **uso real no demo local** (backend `PICSAUDE_DEMO_MODE=true`, navegador, emissão digital de verdade) + suíte unitária executada nesta máquina |

---

## §1 Veredito

**A onda 1 cumpre a promessa central, e eu a vi se cumprir ao vivo.** Emiti uma
receita digital pelo formulário real (losartana 50 mg × 30, paciente canônico
do demo): a folha se escreveu a cada campo, e na emissão o protocolo
`9ba9429f-55d2-4925-bad0-5935f42aef30` e o hash SHA-256 **carimbaram a mesma
folha que eu estava vendo se formar** — sem navegação, sem render novo. O
"zero surpresa" sobreviveu ao primeiro contato com o uso.

Mais: a sobreposição do arquiteto (martelada ②) não só foi implementada como
**verifiquei o invariante ao vivo**: no estado emitido,
`Receituario.textoDoDocumento('folha-viva') === Receituario.textoDoDocumento('print-area')`
→ **true**. W ≡ Y deixou de ser intenção.

## §2 AC × evidência (uso real, não só leitura)

| AC | Evidência ao vivo (21/09, demo local) |
|---|---|
| AC1 — tecla a tecla | Preenchi idade, endereço, cidade, CEP, fármaco e posologia por eventos reais de input; a folha refletiu cada um na hora, com o item numerado e posologia em itálico |
| AC2 — lacunas | Campos não preenchidos apareceram pontilhados ("CEP: cep", "Tel: telefone"); nenhum placeholder de formulário vazou como texto definitivo |
| AC3 — W ≡ Y | Igualdade de texto normalizado entre `#folha-viva` e `#print-area` verificada por chamada ao vivo à `textoDoDocumento` — **no estado emitido** |
| AC4 — carimbo na mesma folha | `.rec-carimbo` presente **dentro** do `#folha-viva` após emitir; `painel-emissao` ("Prescrição Digital Transmitida") apareceu ao lado, sem tela nova |
| AC4-bis — emitida não se edita | Após a emissão, injetei `idade=99` no formulário: a folha **não mudou** (o `_receituarioEmitido` congela o documento — CLAUDE.md §1 virou comportamento de tela) |
| AC6 — CID canônico | Código: `_cidsEscolhidosPrescricao()` lê o hidden `prescricao-cid-escolhido`; a descrição é só enfeite (prescritor.html:2802) |
| AC7 — M-D e A2 | Ao vivo: `pac-nome` e `pac-chave` readonly, preenchidos com o cidadão canônico (João / 123.456.789-09); máscara `data-tipo="cpf"` no campo que subiu |
| AC8 — mobile | FAB "📄 Ver a receita" presente na árvore em viewport <980px; recolhimento por IntersectionObserver sobre `#btn-emitir` (prescritor.html:2989) — coberto por `test_ac8_*` |
| AC9 — fluxo físico | Código: o selo de emissão física é honesto no documento (`rec-selo-fisica`, hash vira nota "não gerado — emissão física" em vez de lacuna que prometeria o que não vem); coberto por `test_ac9_*` |

**Suíte unitária rodada nesta máquina: 15/15 verde**
(`tests/unit/test_frontend_receita_viva.py`, 94s). A suíte de browser do
ENG-018 (12 testes, AC1–AC9) existe e é o padrão-ouro — não a reproduzi local
(exige playwright + browsers; rodou no gate do PR).

## §3 O que a leitura estática somou

- `receituario.js` é o componente que o despacho sugeriu ("padrão `lente.js`")
  e mais: **host-agnostic de propósito** — não lê DOM do formulário, não fala
  com endpoint, recebe estado e devolve HTML. É a remontagem da onda 2 já
  plantada no contrato.
- A tinta por `data-bloco` (diff por região, não por documento) foi além do
  protótipo: a guarda aponta "esta região divergiu", não "o documento
  divergiu".
- A caixa-alta do fármaco é feita **na função, não em CSS** — porque o W ≡ Y
  compara texto. Esse nível de consciência do invariante é o despacho
  inteiro numa linha.
- `test_o_hash_de_integridade_nao_e_mais_descartado` — achei sem querer um
  débito que a onda 1 quitou: o hash antes ia ao limbo no print.

## §4 Achados (nenhum bloqueante)

1. **Plural da unidade** — a folha rendeu "30 comprimido" (deveria ser "30
   comprimidos"). Cosmético, mas é **a primeira prova de fogo do template
   único**: uma correção em `receituario.js` (`_item`) conserta folha viva,
   print-area e 2ª via de uma vez. Se a casa quiser um gesto pequeno que
   demonstra a martelada ② pagando, é este.
2. **Emitente demo sem conselho** mostra lacuna "registro profissional" —
   comportamento correto (lacuna honesta), só estranha na vitrine. Se o demo
   é também vitrine, considerar dar conselho à Dra. Demo no seed (fora do
   escopo desta onda; `curadoria`/seed).
3. **Nota de método:** o painel do navegador embutido foi fechado no meio da
   sessão, então as evidências são de DOM ao vivo + suíte — sem capturas de
   tela novas desta rodada. O que está acima foi lido do documento real, em
   execução.

## §5 Insumos para a onda 2 (exame e atestado como REMONTAGENS)

**Ordem sugerida: exame primeiro, atestado depois — e a razão inverte a
intuição.** O pedido de exame é quase isomorfo à receita (emitente, paciente,
indicação, itens numerados): a remontagem é barata e valida o padrão no caso
favorável. O atestado é monolítico (sem itens) — é ele quem testa a
generalização de verdade. Provar no isomorfo, depois no degenerado.

Concretamente, a onda 2 herda de graça:

- **O contrato inteiro**: `render(estado, modo)` / `montar` / `textoDoDocumento`
  / `MODOS` — o arquivo já declara que existe para ser remontado, não copiado.
- **A mecânica**: lacunas por vocabulário do documento, tinta por `data-bloco`,
  carimbo que congela o estado emitido, FAB mobile com IntersectionObserver.
- **O gabarito de testes**: `test_eng018_receita_viva.py` é um template de AC
  × guarda — a onda 2 começa copiando a *forma* dos testes (nunca o template
  do documento, que é onde a martelada ② morde).
- **Decisão de desenho que a onda 2 precisa tomar cedo**: um gerador por
  documento (`pedidoexame.js`, `atestado.js`) compartilhando um núcleo de
  lacuna/tinta/W≡Y, ou `receituario.js` promovido a `documento.js` com blocos
  parametrizados. Minha leitura: o primeiro — dois documentos com anatomias
  diferentes numa função só é a dupla posse pela porta dos fundos.

**Gancho já plantado:** a posologia em itálico na folha é o lugar natural da
`posologia_sugerida` editável (chave composta do DESENHO-POSOLOGIA-POR-CONDICAO)
— quando aquele ticket andar, a folha viva é onde a sugestão deve *poder ser
editada*, não apenas exibida.

## §6 Conclusão

Onda 1: **RATIFICADA pelo uso**. O conceito virou produto sem perder a alma —
a receita é tratada como o objeto sanitário que ela é desde a primeira tecla.
Recomendo seguir para a onda 2 (exame) com o padrão como está, levando o §4.1
como gesto de demonstração do template único.

— Kimi 3, 21/09/2026
