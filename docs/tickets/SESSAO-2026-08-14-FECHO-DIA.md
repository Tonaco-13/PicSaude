# Sessão 2026-08-14 — Fecho do dia: demo laboratório na `main` + série J

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator |
| **Arquiteto** | Z AI — pareceres, despacho ENG-010 e adjudicação do J.4 |
| **Dono** | Fabiano Tonaco Borges — martelos e ordens de merge |
| **`main` ao fim do dia** | `e19e216` |
| **Estado** | 3 PRs mergeados · 1 aberto pronto para merge · série J encerrada do lado do código |

---

## §1 O dia em uma frase

A demo do laboratório entrou na `main` e, no mesmo dia, uma excursão pela vitrine
ao vivo devolveu três bugs `core` que os gates não podiam ver — todos corrigidos,
com o mais importante deles **recusado como estava escrito** e devolvido ao
arquiteto antes de virar código.

---

## §2 O que entrou na `main`

```
e19e216  fix(core): série J — estados do exame, hash canônico e ledger da coleta [core] (#161)
c85442f  feat(demo): módulo laboratório — laudo cidadão + bancada leve [module] (#160)
0dbd296  feat(laudo): dispensador produz/assina/libera laudo em nome do RT [core] (#159)
95f3536  docs: descritivos dos módulos demo (fast-forward, ver §4)
```

| PR | Classe | Conteúdo |
|---|---|---|
| **#159** | `core` | Ticket C — dispensador produz/assina/libera laudo **em nome do RT**; ownership por posse do pedido |
| **#160** | `module` | Demo laboratório: bancada (B), TUSS/SIGTAP (D), gesto na tela (F), UI de laudo (G), E2E (H), polimento (I) |
| **#161** | `core` | Série J: J.1 estados do exame · J.2 hash canônico · J.5 ledger da coleta |
| **#162** | `module` | Série J: J.3 login invisível · J.6.b mensagem do token · guia do selo (J.4 c) — **aberto, pronto** |

---

## §3 A excursão que pagou o dia

Três agentes do arquiteto circularam receita, atestado e pedido de exames na
vitrine **ao vivo**. O motor passou; o que caiu foram três coisas que nenhum gate
alcançava:

| Achado | Por que o gate não via |
|---|---|
| `resultado_disponivel` inalcançável no pedido; `/encerrar` em **422 circular**; `pedido_encerrado` nunca emitido | Nenhum teste percorria o ciclo **até o fim** — paravam antes do encerramento |
| Hash do documento canônico **nunca** casava; `/validacao` acusando adulteração inexistente | O `conftest` semeia o paciente **já em maiúsculas**: o hash casava por acidente. O seed da vitrine usa Title Case |
| Coleta via agendamento invisível no ledger do pedido | Os dois caminhos de coleta nunca foram comparados entre si |

> A lição comum, e ela repete a de ontem: **o gate cobre o caminho que o gate
> cria**. O dado de teste tinha forma diferente do dado real, e foi a forma —
> não o endpoint — que escondeu o defeito.

Fora isso, o J.2 rendeu um segundo achado durante a correção: **eram dois sítios**
de reconstrução do canônico, não um. O segundo (`validacao_documental.py`) é
justamente a superfície que o cidadão e o auditor veem.

---

## §4 Uma correção de rota no meio do caminho

O diff do #159 carregava dois commits de docs herdados da branch de partida —
ruído num PR que ia ao martelo. Opção B do Fabiano: levar os docs à `main` por
**fast-forward**, em vez de rebasear as branches de feature. Verificado antes
(`main` sem divergência, core fora da branch de docs), executado, e o **#158**
fechou como mergeado por consequência.

**Erro meu registrado ali:** afirmei que o GitHub reconciliou o cache do PR
sozinho. Não foi — o `close`/`reopen` foi do arquiteto, e eu li o disparo do meu
polling como causa. Corrigido em commit próprio. *Observar o efeito não é observar
a causa.*

---

## §5 A recusa do J.4 — o item que não virou código

O despacho pedia corrigir o path do CNES com AC **"score alto na vitrine"**.
Localizei a raiz do path (o `Dockerfile` faz `COPY backend/ .`, então `config.py`
vive em `/app/app/` e o default `../../data/` resolve para fora de `/app`) — mas
o AC era inalcançável, e a evidência estava no próprio seed:

> `# Tabelas de validação do prescritor (vazias): garantem que a consulta CNES`
> `# rode e retorne 'nao_encontrado' em vez de falhar por tabela ausente.`

`profissionais_cnes` nasce **vazia por desenho**, e o CNS da persona é sintético.
Corrigir o path troca `FileNotFoundError` por `nao_encontrado` — o score continua
baixo, **porque é verdade**.

Parei sem alterar código e devolvi com três opções. O arquiteto adjudicou (c)+(a)
e **assumiu a errata**: o AC conflava "sem erro" com "score alto".

> Forçar "score alto" numa demo de identidade sintética faria o indicador de
> confiança **mentir** — e é o único indicador que não pode.

Ficou uma linha no `guia.html` explicando que *baixo* é o selo funcionando. O
resto do J.4 é env no Render, fora do meu alcance.

---

## §6 Higiene acumulada no dia

- `-k` da integração: **263 → 368** testes ao longo dos dois dias, absorvendo a
  família de invariante/ledger e, desarmada a bomba-relógio de data,
  `regras_receituario`. O `test_4d2` estava **vermelho havia meses** sem ninguém
  ver. *Verde e não-gateado apodrece; vermelho e não-gateado mente.*
- `.gitignore` ganhou `.zcode/` e `inbox/`.
- Staging por caminho explícito em **todos** os commits do dia; `git add -A` não
  foi usado nenhuma vez. Os 8 arquivos de outras sessões seguem intocados.

Gates ao fim: **integração 466 · unit 436 · browser 68** (local) e verdes na
nuvem nos quatro PRs.

---

## §7 O que fica para amanhã

| # | Item | Dono |
|---|---|---|
| 1 | Merge do **#162** | Fabiano |
| 2 | Env no Render: `PIX_SAUDE_DEMO_DB`, `PICSAUDE_JWT_SECRET` fixo, `PICSAUDE_DEMO_ADMIN=true` | Fabiano |
| 3 | Reset da vitrine (`reset_demo_db.py --sim-eu-quero`) — sem ele o SIGTAP não aparece nas linhas pré-semeadas | Fabiano |
| 4 | **J.7** (transferir-laboratorio não agenda) — aguarda martelo | Arquiteto → Engenheiro |
| 5 | **J.8/J.9** (abas de UI) — ainda sem martelo | Arquiteto |
| 6 | **#157** (`wip/resgate-arvore`) obsoleto, conflita; conferir 2 commits de docs antes de fechar | Arquiteto |

---

*Registro emitido pelo Engenheiro em 2026-08-14. Dois arcos fechados no mesmo dia:
a demo laboratório do plano à `main`, e a série J da excursão ao PR — esta última
com um ticket recusado e devolvido, que era o que ele merecia.*
