# MEDIÇÃO — o tamanho do retroativo TUSS

| Campo | Valor |
|---|---|
| **Pedido** | Arquiteto (Z), 28/09/2026: *"você PODE adiantar a outra medição que informa a decisão: quantos `pedido_exame_itens` já carregam um dos 38 (query de leitura — o tamanho do retroativo). Medir é seu; trocar código com consequência financeira é caneta."* |
| **Classe** | `docs` — medição de leitura. **Zero escrita, zero código de app** |
| **Irmão** | `RELATORIO-TUSS-RECONCILIACAO.md` (na #279) — este documento continua aquele |
| **Estado** | ✔️ Medição entregue e **caneta executada** (ENG-028, 28/09) — ver nota abaixo |

> ## ✔️ O que a caneta fez com esta medição — 28/09/2026
>
> Os **cinco** itens do §6 foram resolvidos, inclusive os dois que esta
> medição acrescentou:
>
> | # | item | destino |
> |---|---|---|
> | 1 | os 2 válidos-errados (hemograma **e PCR**) | corrigidos: `40304361` e `40308391` |
> | 2 | os 26 com candidato | 27 diretas, conferidas contra a fonte |
> | 3 | os 10 grupamentos | **todos tinham item oficial** — zero ficou sem código |
> | 4 | **o `seed_demo.py`** | as 3 ocorrências alinhadas aos mesmos códigos |
> | 5 | **fechar a torneira** | fechada **na fonte**: `_BASE_RAW` corrigido faz o caminho clínico escrever o código certo daqui em diante |
>
> **O retroativo continua intocado, e é decisão, não omissão.** O §4.4 do
> ENG-028 é explícito: *"histórico é imutável — itens já emitidos mantêm o
> código que faturaram"*. É a mesma régua do ledger desta casa (§1/§2 do
> CLAUDE.md): não se edita o que já foi emitido; registra-se. **Este
> documento é esse registro.** Guarda:
> `TestNenhumCodigoInventadoEmLugarNenhum::test_o_retroativo_nao_foi_tocado`,
> que reprova se um `UPDATE pedido_exame_itens` entrar por algum PR da caneta.

---

## §1 A resposta curta, e por que ela não é um número

> **O retroativo não é um estoque. É um fluxo — e ele está aberto agora.**

A pergunta *"quantos itens já carregam um dos 38"* pressupõe que os códigos
errados sejam resíduo histórico. Não são: **o caminho clínico continua
escrevendo-os**, a cada pedido de exame emitido. A cadeia está inteira e viva:

```
tuss_base._BASE_RAW        os 38 códigos curados
        ↓
ia_exames.py:133           "codigo_tuss": registro["codigo_tuss"]
        ↓                  (a IA de normalização devolve o código ao front)
prescritor.html:4804       const codigoTuss = data.codigo_tuss
        ↓                  (vai para o campo oculto do item)
prescritor.html:4941/5139  codigo_tuss: tussEl.value
        ↓                  (segue no payload do pedido)
pedidos_exame.py:339       INSERT INTO pedido_exame_itens (..., codigo_tuss, ...)
        ↓
clinicas.py:334            _faturamento_do_cnpj(conn, cnpj, coluna="codigo_tuss")
```

Corrigir só o passado deixaria a torneira aberta; fechar a torneira sem olhar
o passado deixaria o faturamento já emitido inconsistente. **As duas pontas
são o mesmo trabalho**, e é isso que a caneta precisa saber antes de decidir.

## §2 O que eu pude medir — e o que não pude

| Onde | Consigo medir? | Resultado |
|---|---|---|
| `data/pix_saude_demo.db` (demo local) | sim | **2 itens; 0 carregam um dos 38** — ver §3, o resultado surpreende |
| Vitrine / produção (PostgreSQL) | **não** — sem acesso desta vantage | query pronta no §5, para quem tiver |

Não estimei o número de produção. Extrapolar de 2 linhas seria inventar
grandeza — e o defeito que este arco inteiro persegue é exatamente inventar
número que a fonte não dá.

## §3 O achado da medição: existe uma TERCEIRA fonte de código TUSS

Os 2 itens do banco demo **não carregam nenhum dos 38**. Carregam outros dois:

| Exame | código no banco demo | consta na Tabela 22? |
|---|---|---|
| Hemograma completo | `40301107` | **não existe** |
| Glicemia de jejum | `40302055` | **não existe** |

Vêm de `backend/seed_demo.py` (linhas 559, 654 e 741), onde estão **cravados
à mão** — e são **diferentes** dos da curadoria. Ou seja:

> **O hemograma tem três códigos nesta casa, e dois são inventados:**
>
> | origem | código | o que é de verdade |
> |---|---|---|
> | `seed_demo.py` | `40301107` | não existe na Tabela 22 |
> | `tuss_base._BASE_RAW` | `40301079` | existe — é **"Ácido beta hidroxi butírico"** |
> | **Tabela 22 oficial** | **`40304361`** | **Hemograma com contagem de plaquetas** |
>
> O mesmo exame sai com um código pela semente e com outro pelo caminho
> clínico. Nenhum dos dois é o certo.

Isso amplia o escopo da caneta: **não basta corrigir `_BASE_RAW`**. O
`seed_demo.py` tem os seus próprios valores, e a vitrine é gerada por ele.

## §4 O segundo "válido-mas-errado" — agora com nome

O relatório anterior nomeou o hemograma. A medição fechou o par: **os DOIS
códigos que existem na Tabela 22 apontam para outro exame.**

| curado | curado como | **é, na Tabela 22** |
|---|---|---|
| `40301079` | Hemograma completo com contagem de plaquetas | **Ácido beta hidroxi butírico** — pesquisa e/ou dosagem |
| `40308030` | Proteína C Reativa (PCR) | **Fator reumatóide**, teste do látex (qualitativo) |

São os dois piores casos do conjunto, e pela mesma razão: **código válido é
aceito no faturamento**. Um código inexistente é rejeitado e o erro aparece;
estes dois passam, e faturam outro exame em silêncio. Os 36 inexistentes são
ruidosos — estes dois são mudos.

## §5 A query, pronta para rodar em produção

Leitura pura. Roda igual em SQLite e PostgreSQL.

```sql
-- Quantos itens de pedido de exame carregam um dos 38 códigos curados.
SELECT codigo_tuss,
       COUNT(*)                        AS itens,
       COUNT(DISTINCT pedido_id)       AS pedidos,
       MIN(criado_em)                  AS primeiro,
       MAX(criado_em)                  AS ultimo
  FROM pedido_exame_itens
 WHERE codigo_tuss IN (
   '40201030','40201048','40205020','40205128','40301079','40302019','40302027',
   '40302035','40302043','40302132','40302140','40302264','40302272','40302280',
   '40302388','40302434','40302450','40302485','40302523','40302590','40302663',
   '40302671','40306117','40306150','40308030','40311012','40311020','40311071',
   '40403082','40403090','40403104','40601078','40601086','40801019','40801027',
   '40801124','40901060','40901337')
 GROUP BY codigo_tuss
 ORDER BY itens DESC;
```

E a segunda, para os dois **válidos-mas-errados** — os que o faturamento
aceita e que por isso merecem contagem própria:

```sql
SELECT codigo_tuss, nome_exame, COUNT(*) AS itens
  FROM pedido_exame_itens
 WHERE codigo_tuss IN ('40301079', '40308030')
 GROUP BY codigo_tuss, nome_exame
 ORDER BY itens DESC;
```

E a terceira, para a fonte que a medição descobriu (os códigos da semente):

```sql
SELECT codigo_tuss, nome_exame, COUNT(*) AS itens
  FROM pedido_exame_itens
 WHERE codigo_tuss IN ('40301107', '40302055')
 GROUP BY codigo_tuss, nome_exame;
```

> **Cuidado de escopo institucional (§6b do CLAUDE.md):** `pedido_exame_itens`
> não tem `org_id` (herda contexto via o pedido). Para recortar por
> instituição, o JOIN é com `pedidos_exame`. As queries acima são de
> **diagnóstico agregado**, sem dado de paciente — não expõem CPF nem nome.

## §6 O que isto acrescenta à decisão do Fabiano

A caneta de correção ficou com **um item a mais** do que o relatório anterior
previa:

| # | O que decidir | Novidade desta medição |
|---|---|---|
| 1 | os 2 válidos-errados | agora são **dois nomeados**: hemograma **e PCR** |
| 2 | os 26 com candidato | inalterado |
| 3 | os 10 grupamentos | inalterado |
| 4 | **o `seed_demo.py`** | **NOVO** — tem códigos próprios, também inexistentes, diferentes dos curados |
| 5 | **fechar a torneira antes ou junto do retroativo** | **NOVO** — o caminho clínico segue escrevendo; corrigir só o passado não resolve |

**Nada foi corrigido nesta medição** — nem em `_BASE_RAW`, nem no
`seed_demo.py`, nem em linha de banco. Medição é leitura; a troca é caneta.

---

*Lavrado em 28/09/2026 pelo engenheiro, a pedido do arquiteto, enquanto a #279
aguarda o martelo. Nenhum arquivo da #279 foi tocado: a ratificação do
arquiteto foi dada contra aquele head, e mexer nele invalidaria a prova
própria que ele produziu.*
