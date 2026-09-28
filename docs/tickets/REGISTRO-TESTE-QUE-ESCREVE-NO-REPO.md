# REGISTRO — a execução das 12:34 tinha dono: fui eu, e a causa é um teste

| Campo | Valor |
|---|---|
| **Pergunta** | Arquiteto (Z), 28/09/2026: *"A execução das 12:34 ficou sem dono conhecido; se souber de onde veio, uma linha no registro resolve."* |
| **Resposta** | **Fui eu** — pela suíte completa, no ENG-027. Mas a causa não é minha: é um teste que escreve em arquivo versionado |
| **Classe** | `docs` — registro. Nada corrigido |

---

## §1 O dono

Os arquivos `data/fontes-oficiais/pcdt/extracao/pcdt_e11_rascunho.csv` e
`docs/tickets/RELATORIO-EXTRACAO-PCDT.md` foram reescritos às **12:34:16** e
**12:34:19** de 28/09.

Nesse intervalo eu rodava `pytest tests` na íntegra — parte da prova de
não-regressão do ENG-027 (a comparação 56 = 56 contra a worktree de
`origin/main`). Eu não rodei o extrator; a **suíte** rodou.

## §2 A causa — e ela é mais interessante que o dono

`backend/tests/test_extrair_snapshot_pcdt.py` chama `extrator.main()` **quatro
vezes** (linhas 272, 300, 303 e 314). E `main()`, em
`backend/scripts/extrair_snapshot_pcdt.py`, escreve nos **caminhos reais do
repositório**, não num `tmp_path`:

```python
_SAIDA_DIR = _RAIZ / "data" / "fontes-oficiais" / "pcdt" / "extracao"   # linha 86
_RELATORIO = _RAIZ / "docs" / "tickets" / "RELATORIO-EXTRACAO-PCDT.md"  # linha 87
...
_RELATORIO.write_text("\n".join(linhas), encoding="utf-8")              # linha 616
```

**Reproduzido do zero, para não afirmar por dedução:**

```
$ git checkout <os dois arquivos>     # árvore limpa: 0 modificados
$ pytest tests/test_extrair_snapshot_pcdt.py -q
  30 passed in 37.16s
$ git status --short
 M data/fontes-oficiais/pcdt/extracao/pcdt_e11_rascunho.csv
 M docs/tickets/RELATORIO-EXTRACAO-PCDT.md
```

Trinta testes verdes, e dois arquivos versionados reescritos como efeito
colateral.

## §3 Por que isso importa mais que a linha de registro

O veredito do arquiteto já classificou a mudança de conteúdo como **benigna**
(regeneração do extrator, o AC do relatório até melhorou de 7/8 para 8/8), e
esse veredito continua de pé. O que este registro acrescenta é o **mecanismo**,
porque ele tem três consequências que sobrevivem ao caso benigno:

1. **Qualquer um que rode a suíte suja a árvore.** Sem saber por quê, e sem
   nada a ver com o que estava mexendo. Foi exatamente o que aconteceu comigo:
   apareceram dois arquivos modificados no meio de uma PR de TUSS.

2. **O artefato commitado pode mudar sozinho, em silêncio.** Se uma rodada de
   testes gerar saída diferente e alguém fizer `git add -A`, a mudança entra
   sem PR, sem revisão e sem despacho. É a porta dos fundos para dado curado.

3. **A dúvida de autoria que o arquiteto levantou é o sintoma.** Custou uma
   pergunta no despacho e esta investigação. Com o teste escrevendo em
   `tmp_path`, a pergunta não existiria.

## §4 O que NÃO fiz

**Não consertei.** O arquivo é do território da curadoria PCDT — e o
super-intensivo PCDT está rodando em docs neste momento (K21 lavrado, R2 às
15:01). Mexer no teste agora é exatamente o cruzamento de território que o
despacho do ENG-027 mandou evitar.

Também **não commitei** a regeneração: restaurei os dois arquivos com
`git checkout`. O veredito diz que a próxima PR de docs da curadoria os
recolhe, e é lá que devem entrar — com dono e com revisão.

## §5 A correção, quando alguém a fizer

Uma linha de desenho: `main()` aceita diretório de saída como parâmetro
(`main(saida: Path = _SAIDA_DIR)`), e o teste passa o `tmp_path` do pytest. O
caminho de produção não muda; o teste deixa de escrever no repo. É o mesmo
padrão que `importar_snapshot_tuss.py` já usa — o script recebe o destino como
`sys.argv[2]`, com o default só para a mão humana.

> Guard-rail possível, se a casa quiser: um teste que roda `git status
> --porcelain` ao fim da suíte e reprova se a árvore ficou suja. Pega esta
> família inteira, não só este caso. Fica como sugestão — não é minha decisão.

---

*Lavrado em 28/09/2026 pelo engenheiro, respondendo à pergunta do arquiteto.
A execução tinha dono; o que não tinha dono era o mecanismo.*
