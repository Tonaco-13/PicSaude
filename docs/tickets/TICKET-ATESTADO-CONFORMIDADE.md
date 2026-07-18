# TICKET-ATESTADO-CONFORMIDADE — atestado pronto para imprimir e assinar (CFM/CFO)

**Classe:** `module` + migração · **Base:** `main` = `b8b1fca` · **Data:** 2026-07-18
**Análise do arquiteto ratificada por Fabiano.**

---

## O problema

O atestado já era um objeto sanitário íntegro — protocolo, ledger, custódia, hash,
assinatura PAdES. O que faltava não era integridade: era a **face do papel**. Impresso,
o documento não atendia ao que o CFM exige, e a tela tinha um caminho que produzia algo
parecido com um atestado sem ser um.

O cabeçalho do PDF (`domain/pdf_atestado.py`) **já estava correto** — "ATESTADO MÉDICO"
em caixa alta e negrito, blocos, assinatura, protocolo + hash, marca d'água de demo.
Não era ali o buraco.

---

## A — Local e data (CFM exige "local e data")

A data já existia (`data_documento`); o **local** não.

- Migração: `atestados.municipio_emissao` (String 120), **NULLABLE no schema**,
  **OBRIGATÓRIO no payload** `AtestadoIn` → sem município = **422**.
- PDF: fecho clássico `{Município}, {dd/mm/aaaa}` **acima** da área de assinatura.
- Frontend: campo "Município de Emissão *" no formulário.
- **Sem** estabelecimento/CNES — entra com o login (decisão do Fabiano).

**Por que nullable e obrigatório ao mesmo tempo:** atestados já emitidos não têm
município e **não podem ser reescritos** (CLAUDE.md §1). Backfill com município
inventado falsificaria o local de emissão de um documento assinado. NULL = "não
declarado à época", e o PDF omite o fecho.

Na emissão **física** o município é opcional: o POST é fire-and-forget (§6) e um 422 não
impediria a impressão — só perderia o registro central. A exigência mora na tela.

## B — Conselho (CFM + CFO; enfermagem NÃO agora)

- Migração: `atestados.conselho` (String 10: `CFM`|`CFO`) + `uf_registro` (String 2).
- `registro_profissional` passa a guardar o **NÚMERO**.
- **Fonte única:** `backend/app/domain/conselho_profissional.py`

  | Conselho | Sigla | Título | "sob cuidados …" | "a atendimento …" |
  |---|---|---|---|---|
  | CFM | CRM | ATESTADO MÉDICO | médicos | médico |
  | CFO | CRO | ATESTADO ODONTOLÓGICO | odontológicos | odontológico |

- PDF e HTML **nunca hardcodam** — perguntam ao domínio. Mesma régua do `grupo_por_id`
  do R4: o backend resolve, a tela exibe. A tela recebe o catálogo por
  `GET /config/public` → `conselhos_profissionais`.
- **LEGADO:** `conselho` NULL → `CONSELHO_PADRAO` (CFM) → "ATESTADO MÉDICO". Não quebra.
  Slug desconhecido degrada para o mesmo padrão em vez de levantar.

> **Desvio do enunciado (aprovar/rejeitar):** o ticket definia um adjetivo por conselho
> (`"médicos"`). Foram necessários **dois** — plural para "sob cuidados médicos" e
> singular para "compareceu a atendimento médico". Com um só campo, o PDF teria de
> flexionar a palavra: regra de gramática escondida no renderizador. O contrato do
> ticket está contido no que foi entregue.

## C — Ênfase: registro antes do CNS

Antes: `Nome — CNS {cns} · {registro}`. Agora: `Nome — CRM-PE 12345 · CNS {cns}`.
Quem identifica o profissional perante a norma é o CRM/CRO+UF; o CNS é identificador de
sistema, não de habilitação. Aplicado no bloco PROFISSIONAL **e** na área de assinatura.

## D — Hora (atestado de comparecimento)

- Migração: `hora_inicio` / `hora_fim` (String 5, `HH:MM`), nullable e **OPCIONAIS
  SEMPRE**. A obrigatoriedade **não** é condicionada à finalidade (que é praticamente
  texto livre — condicionar seria frágil).
- PDF: `no período das 08:00 às 12:00` / `a partir das 08:00` / `até as 12:00`.
- O período entra **nos dois ramos** (comparecimento e afastamento): hora digitada que
  não aparece no documento é perda silenciosa.

## E — Fim do rascunho-fantasma

`imprimirAtestado()` (`prescritor.html`) imprimia o rascunho da IA num `<pre>` serifado
que terminava em data + nome + registro — parecia atestado, mas não tinha protocolo,
hash nem assinatura. Estava a um clique de ser confundido com o documento real.

- Renomeada para `imprimirRascunhoAtestado()`: tarja **"RASCUNHO — SEM VALIDADE LEGAL"**,
  marca d'água, fonte não-serifada (diferente da do PDF), **sem** protocolo, **sem** área
  de assinatura, e rodapé apontando o caminho oficial.
- O preview **na tela** também deixou de imitar papel timbrado: tarja lateral vermelha,
  selo "sem validade legal" e marca d'água.
- Botão `🖨️ Imprimir / Usar` separado em dois: **"✓ Usar — ir para a emissão oficial"**
  (primária) e "🖨️ Imprimir rascunho" (secundária).
- **O documento oficial tem UM renderizador: o PDF do servidor.**

> **Desvio do enunciado (aprovar/rejeitar):** o ticket dizia que "Usar" *preenche o
> formulário*. Não há o que preencher — o rascunho é **gerado a partir** dos campos do
> formulário (`renderizar_atestado` só formata o que recebeu), então re-preencher seria
> no-op. "Usar" foi implementado como **adotar o rascunho e seguir para a emissão
> oficial**: rola até o botão de emitir e o destaca. Mantém a intenção (a ação primária
> leva ao documento de verdade) sem simular um preenchimento que não existe.

---

## Aceite — evidência

| Critério | Como foi verificado |
|---|---|
| Emitir sem município → 422 | `POST /atestados` sem o campo → **HTTP 422** (servidor real, banco demo) |
| PDF traz "Recife, 18/07/2026" acima da assinatura | texto extraído do PDF do servidor; índice do fecho **<** índice da régua de assinatura |
| CFO → ATESTADO ODONTOLÓGICO + "odontológico" + CRO-PE 1234 | PDF real: `ATESTADO ODONTOLÓGICO … CRO-PE 1234 · CNS … compareceu a atendimento odontológico … no período das 08:00 às 12:00. Recife, 18/07/2026.` |
| CFM → ATESTADO MÉDICO + CRM-PE 12345 | PDF real: `ATESTADO MÉDICO … CRM-PE 12345 · CNS … esteve sob cuidados médicos` |
| conselho NULL → comportamento atual | linha legada inserida direto no banco → PDF sai `ATESTADO MÉDICO`, registro livre `CRM-PE 99999` intacto, **sem** fecho |
| Registro antes do CNS | `CRM-PE 12345 · CNS 980001112223334` — índice do registro **<** índice de `CNS ` |
| Comparecimento com hora → período; sem hora → frase atual | ambos os ramos testados; sem hora, `no período` **ausente** |
| Migração dual-DB | SQLite: upgrade + downgrade + re-upgrade em cópia do dev DB (310 MB, dados preservados). PostgreSQL 15: cadeia completa do zero, tipos `VARCHAR(120/10/2/5/5)`, comentários de coluna, downgrade reversível |
| Gate verde | unit **251 passed, 0 failed**. Integração PG: **9 falhas idênticas** em `main` e na branch (`comm -23` vazio) → **zero regressão** |

**Testes:** `tests/unit/test_conselho_profissional.py` (novo, 20 casos) e 8 classes novas
em `tests/unit/test_atestados.py` (município, conselho, ênfase, hora, hash, física,
catálogo). O helper `_texto_pdf` desfaz ASCII85+Flate e extrai os operandos `Tj` — sem
isso, `b"ATESTADO ODONTOLÓGICO" in pdf` seria **sempre falso** e os testes passariam por
vacuidade. Controle negativo executado.

**Hash canônico:** `versao_esquema` sobe para `"2"`, incorporando município, conselho/UF/
registro e horário — conteúdo **material** do documento. Fora do hash, dois atestados com
locais diferentes teriam a mesma impressão digital. O hash é gravado **uma vez** na
emissão e nunca recalculado, então atestados v1 não mudam.

---

## Demo (dívida #98)

A migração **altera tabela existente** → o banco demo foi **reconstruído**, não
re-semeado: `rm data/pix_saude_demo.db` → `PICSAUDE_DEMO_MODE=true python init_tables.py`
→ `seed_demo.py`. **Não** usar `subir-local.sh` (roda alembic contra o dev DB e recria o
`.venv` arm64 quebrado).

Semeado `DEMO-ATESTADO-0001` — CFM/CRM-PE 12345, Recife, 3 dias, 08:00–09:30 — com
custódia prescritor→paciente e os dois eventos do ledger (objeto completo, não órfão).
Conselho CFM porque a prescritora da demo é médica; o caminho CFO se demonstra trocando o
seletor na tela.

---

## Fora de escopo

Estabelecimento/CNES · enfermagem/COFEN (registrado em `backend/docs/DIVIDA-TECNICA.md`
§7-A) · validação de CID (ticket próprio) · policiar escopo clínico.

## Sugerido, não feito (exige martelo — é `core`)

`CLAUDE.md` §7 lista as regras fundamentais do atestado e hoje não menciona município nem
conselho. Atualizar é mudança **`core`** (revisão central obrigatória), então ficou de
fora deste PR. Proposta de linha:

> - Município de emissão **obrigatório** no digital (CFM exige local e data); conselho
>   (CFM|CFO) decide título e adjetivos do documento — fonte única em
>   `domain/conselho_profissional.py`
