# TICKET-CID-VALIDACAO — validar CID na escrita, sem punir o prescritor

**Classe:** Frente A `ops`/dados · Frente B `module`
**Origem:** o validador `buscar_por_codigo()` existia (`app/ai/base_cid.py:499`) e
**nenhum caminho de escrita o chamava** — era código morto. Mesma bifurcação do
`formatar_quantidade`.

---

## 1. O teste que redesenhou o ticket

A base do CID **não** estava "completa e atual". Verificado no arquivo:

```
U07.1 (COVID-19)  AUSENTE      U07.2 · U08.9 · U09.9 · U10.9  AUSENTES
Códigos U existentes: U04 (SARS 2003) · U80–U89 · U99 — todos pré-2008
```

Consequências concretas: um médico **não achava COVID na busca**; e validação
estrita contra essa base **bloquearia um atestado de COVID**.

É disso que sai a régua do ticket:

> **Rejeitar o que é INEQUIVOCAMENTE INVÁLIDO (formato).
> Nunca rejeitar o que é apenas DESCONHECIDO PARA NÓS (catálogo).**

---

## 2. Frente A — a base (`ops`/dados)

### Verificação na fonte, não de memória

Baixado e inspecionado o arquivo **oficial do DATASUS** (`CID10CSV.zip`, "Tabelas
da CID-10 — **Versão: 2008**", `www2.datasus.gov.br/cid10/V2008/download.htm`).
Todas as entradas `U`:

```
CATEGORIAS:    U04, U80, U81, U88, U89, U99
SUBCATEGORIAS: U04.9   (única)
```

**Nenhum dos sete códigos candidatos está lá.** A tabela nunca foi reeditada.
Eles chegam ao Brasil pela **OMS** (uso emergencial) e por instruções
operacionais do MS — **não** pela distribuição CID-10 do DATASUS.

### O que a lista do despacho errou

1. **Proveniência falsa para os sete.** `DATASUS/CID-10 V2008` seria mentira em
   todos. (Era exatamente o alerta do "coluna `fonte` honesta".)
2. **Os sete não têm a mesma data.** U07.1/U07.2 = fev/2020 · U08–U10 = set/2020
   · U11–U12 = jan/2021. Uma `fonte` única para todos seria factualmente errada.
3. **U09.9 não é autônomo no Brasil.** O MS (Nota Técnica nº 57/2023) instrui
   `B94.8` + `U09.9` **na mesma linha** — U09.9 é marcador, não diagnóstico
   principal isolado.
4. **`U92.1` "reincidência de COVID"** aparece em fonte secundária (blog) **sem**
   respaldo na OMS ou no MS. **Não incluído.**

### Linhas acrescentadas a `data/cid10.csv`

| Código | `fonte` gravada |
|---|---|
| U07.1 · U07.2 | `OMS/CID-10 uso emergencial 2020` |
| U08.9 · U09.9 · U10.9 | `OMS/CID-10 uso emergencial 2020 (set/2020)` |
| U11.9 · U12.9 | `OMS/CID-10 uso emergencial 2021 (jan/2021)` |

### Buscabilidade

Não basta o código existir — o prescritor digita **"covid"**, não "vírus
identificado". Aliases curados para U07.1/U07.2/U09.9/U10.9 em `_BASE_CID_RAW`
(`covid`, `coronavirus`, `sars-cov-2`, `covid longa`, `pos covid`, `sim-p`…).

Resultado: `"covid"` → **U07.1 em primeiro lugar**, score 0.98, `match_tipo=alias`.

### Versão em lugar consultável

A causa-raiz não foi a base velha — foi **não dar para saber disso**.
`_VERSAO_BASE` **já dizia "V2008"** e ninguém releu. Uma string escrita à mão
envelhece em silêncio.

Por isso a proveniência auditável agora é **derivada dos dados**,
`BASE_CID.manifesto()`:

```json
{
  "versao_declarada": "DATASUS CID-10 V2008 (base) + uso emergencial OMS 2020/2021 …",
  "total_registros": 14243,
  "por_fonte": {
    "CID10/BASE_LOCAL": 3,
    "DATASUS/CID-10 V2008": 14233,
    "OMS/CID-10 uso emergencial 2020": 2,
    "OMS/CID-10 uso emergencial 2020 (set/2020)": 3,
    "OMS/CID-10 uso emergencial 2021 (jan/2021)": 2
  }
}
```

Conta por `fonte` a partir do que foi **de fato carregado** — não tem como mentir.
Código que entre sem origem declarada aparece contado sob outro rótulo.

---

## 3. Frente B — validar na escrita (`module`)

Fonte única: **`app/domain/cid.py`**. Sem regex de catálogo duplicada — a base é
uma só (`buscar_por_codigo()`).

### Camada 1 — FORMATO, estrito (422)

```
^[A-Z]\d{2}(\.\d)?$      normalizado antes (trim + maiúscula)
```

Verificado empiricamente contra o CSV: **14.233/14.233** códigos casam, e as **26
letras** são usadas (não restringir o conjunto — uma regex `[A-TV-Z]` rejeitaria
justamente a família U07).

### Camada 2 — CATÁLOGO, suave (aceita e sinaliza)

Bem-formado e fora da base → **aceita**, grava e devolve
`cid_consta_na_base: false`; a UI avisa. **Nunca** bloqueia.

> A defasagem é defeito **nosso**, não do prescritor. Bloquear U07.1 porque o
> nosso CSV é de 2008 seria punir o médico pelo nosso atraso — e
> `backend/CLAUDE.md` é explícito: "não adiciona atrito ao fluxo do prescritor sem
> justificativa regulatória".

### Onde o sinal NÃO entra — e por quê

`cid_consta_na_base` fica **fora do hash canônico e fora do ledger**, de propósito.

"Consta na nossa base" é propriedade do **nosso catálogo naquele instante**, não
do documento clínico. Dentro do hash, quebraria a **reprodutibilidade (CLAUDE.md
§2a R1)**: o mesmo atestado passaria a ter hash diferente só porque atualizamos o
CSV. A consulta ao catálogo roda **depois** da escrita/commit — não pode
influenciar se o objeto é gravado.

### Exceção documentada — atestado FÍSICO normaliza, mas não rejeita

`POST /atestados/fisica` é fire-and-forget (CLAUDE.md §6): **o papel já saiu na
impressora** quando o backend valida. Um 422 não desimprime nada — só descarta o
registro central. Atestado no mundo e nada no ledger é pior que um CID ruim
gravado e depois audível.

É a mesma razão que o próprio router já documenta para `municipio_emissao`.

### A decisão anterior que **não** foi revertida

`prescricoes.py` dizia: *"a validação semântica do CID é responsabilidade da IA
CID, não do backend"*. **Segue valendo.** Este ticket acrescenta só a camada
**sintática** ("I10" é código, "gripe" não é) e a consulta não-bloqueante.
Se o código é clinicamente adequado à indicação, o backend continua não julgando.

---

## 4. Aceite

| Critério | Resultado |
|---|---|
| `"XYZ123"` → 422 nos dois routers | ✅ (também `gripe`, `I10.99`, `I100`, `110`, `I 10`) |
| `"i10"` → normaliza p/ `I10`, aceito | ✅ (e `" i10 "`) |
| `"U07.1"` → aceito, achado na base após Frente A | ✅ `cid_consta_na_base: true` |
| bem-formado fora da base → aceito + sinalizado, **nunca** 422 | ✅ via `I10.0` |
| busca por `"covid"` retorna U07.1 | ✅ 1º lugar, 0.98, alias |
| usa `buscar_por_codigo()`, sem regex de catálogo duplicada | ✅ teste neutraliza a base e exige que nada mais afirme "consta" |

**Testes:** 31 (`test_cid_validacao.py`) + 17 (`test_cid_validacao_routers.py`)
+ 22 (`test_cid_base_emergencial.py`). Suíte unitária completa: **334 verdes**.

`I10.0` foi escolhido como o "fora da base" porque I10 é categoria de 3 caracteres
**sem subcategorias** — sintaticamente impecável e estavelmente inexistente. (A
primeira tentativa usou `Q99.9`, que **existe**; o teste pegou o erro.)

---

## 5. Fora de escopo

- Migrar para CID-11 (os sistemas do MS seguem em CID-10)
- Tornar `codigo_cid` obrigatório (segue opcional — CFM art. 3º, só com anuência
  do paciente)
- `ia.py` (leitura)

---

## 6. Aberto para o martelo do Fabiano

1. **Redação PT-BR de U07.1/U07.2.** Gravei a tradução literal da OMS ("COVID-19,
   vírus identificado / não identificado") por coerência com a `fonte` declarada.
   Circula também a redação operacional do MS ("Diagnóstico de COVID-19 confirmado
   por exames laboratoriais"). Se a string exata importar para conformidade, a
   fonte a consultar é o **SIGTAP** ou a tabela CID do e-SUS APS — **não** o
   arquivo V2008, que comprovadamente não os contém. A busca não depende disso
   (os aliases cobrem).
2. **Categorias de 3 caracteres (U08, U09, U10, U11, U12).** A OMS as emitiu para
   países que não reportam em 4 dígitos. **Não incluídas**: não obtive redação
   PT-BR verificada, e inventá-la contrariaria a regra da Frente A. O Brasil
   reporta em 4 dígitos.
3. **`cid_consta_na_base` no ledger?** Hoje só na resposta. Há valor de auditoria
   em registrar "no ato da emissão, este código não constava do nosso catálogo" —
   mas mexer em payload de evento é `core`, e mantê-lo fora preserva a
   classificação `module` desta frente.
