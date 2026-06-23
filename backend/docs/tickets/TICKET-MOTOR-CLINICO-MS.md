# TICKET — Motor clínico de apoio + auditoria (conteúdo) · instância MS

> **Para:** instância Claude da conta do **Ministério da Saúde** (VS Code).
> **De:** Engenheiro-Chefe (instância PicSaúde).
> **Natureza:** entrega **individual** e auto-contida — o "motor de apoio e auditoria
> das prescrições medicamentosas" alimentado por **ANVISA, CMED e PCDT**.
> **Classe de contribuição:** `module` (conteúdo curado + ingestão). **NÃO** `core`.

---

## 1. Missão (o que você constrói)

Você é dona(o) do **CONTEÚDO CLÍNICO** do motor de apoio à decisão do PicSaúde —
não do motor em si. Concretamente:

1. **Curar** as regras clínicas (coerência fármaco↔CID e posologia usual) a partir de
   **PCDT/CONITEC, RENAME, ANVISA e CMED**, gravando-as nos **dois CSVs curados**
   (schema publicado na §4), sempre como **rascunho** até validação humana.
2. **Construir um módulo de ingestão** que transforme as bases (ANVISA/CMED/PCDT)
   nas linhas desses CSVs — determinístico, rastreável, sem LLM.

O motor (busca, semáforo, posologia, explicabilidade) **já existe e é estável**. Você
programa **contra o contrato** dele (§4–§5), nunca dentro dele.

---

## 2. Fronteira de propriedade (evita colisão entre as duas instâncias)

| Você (instância MS) é dona de | Você consome (READ-ONLY, não edita) | Você NUNCA toca |
|---|---|---|
| `data/decisao_semaforo.csv` | `backend/app/domain/semaforo_decisao.py` | núcleo (`domain/states*.py`) |
| `data/posologia_sugerida.csv` | `backend/app/domain/posologia_sugerida.py` | ledger (`domain/ledger.py`, `*_eventos`) |
| **novo:** `backend/app/ingestao_clinica/` (módulo de ingestão ANVISA/CMED/PCDT) | `backend/app/routers/ia.py` (endpoints) | custódia, RBAC, `auth/` |
| **novo:** `backend/scripts/ingerir_*.py` (CLIs de curadoria) | `docs/ARQUITETURA_DECISAO_CLINICA.md` · `docs/EXPLICABILIDADE_DECISAO_CLINICA.md` | qualquer router clínico, migrations |

> Se precisar de uma mudança no **motor** (nova coluna no CSV, novo campo na ficha),
> **abra uma issue/PR de proposta** — eu (chefe) avalio e altero o motor + o contrato.
> Você não altera o motor por conta própria. Assim os schemas nunca divergem.

---

## 3. Linhas vermelhas (invioláveis)

1. **Determinístico. SEM LLM, SEM ML.** O motor e a ingestão são *lookup* e regras.
   A inteligência mora no **dado curado**, não em geração.
2. **Só serve `validado`.** O motor ignora qualquer linha com `status_curadoria != "validado"`.
   Você entrega **rascunho**; **Fabiano valida e assina** (preenche `validado_por`,
   troca para `validado`). É a propriedade clínica dele. Nenhuma instância valida sozinha.
3. **Lei da exaustividade** (semáforo): o motor só **julga** (🟢/🟡) uma condição cuja
   lista 🟢 é **EXAUSTIVA** vs. PCDT (coluna `exaustivo=true`). Lista incompleta = viés →
   o motor se **cala** (neutro). Logo: ou a condição entra **completa** (todos os fármacos
   do PCDT) e marcada exaustiva, ou entra como semente não-exaustiva (silenciosa).
4. **Proveniência obrigatória** em toda linha validada: `fonte` (qual PCDT/RENAME/bula),
   `validado_por`, `versao`. É o que torna o sinal **auditável** (camadas de explicabilidade).
5. **Não-vinculante.** O sistema sugere/valida; o prescritor é o responsável final.

---

## 4. CONTRATO DE SCHEMA (publicado — programe contra isto)

### 4.1 `data/decisao_semaforo.csv` — coerência fármaco ↔ CID (semáforo)

Cabeçalho (ordem e nomes **exatos**):
```
codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo
```

| Coluna | Tipo | Semântica |
|---|---|---|
| `codigo_cid` | str | CID-10 da condição (ex.: `I10`). Canonizado pelo motor (ver §5). Pode ser categoria (`I10`) ou subcategoria (`I10.0`) — o motor sobe a hierarquia. |
| `condicao_nome` | str | Nome legível (ex.: `Hipertensão arterial`). Vira a `fonte`/condição na ficha. |
| `principio_ativo` | str | Princípio ativo. **Será canonizado** (sal/acento/caixa removidos — §5). Cure o nome genérico (ex.: `losartana`, não "Losartana Potássica 50mg"). |
| `fonte` | str | Proveniência clínica (ex.: `RENAME 2024 + Diretrizes Brasileiras de HAS 2020 (SBC/SBH/SBN)`). |
| `status_curadoria` | str | `validado` \| `rascunho`. **Só `validado` é servido.** |
| `validado_por` | str | Responsável que assinou (vazio em rascunho). |
| `versao` | str | Versão da curadoria (ex.: `semaforo_has_exaustiva_v1_2026-06`). |
| `exaustivo` | str | `true`/`sim`/`1`/`verdadeiro` ⇒ a lista 🟢 desta condição é **COMPLETA** vs. PCDT (motor julga ausências como 🟡). Senão, silêncio. |

**Regra de unicidade lógica:** uma linha 🟢 = `(codigo_cid canônico, principio_ativo canônico)`.
Para marcar uma condição como exaustiva, **todas** as linhas daquele CID devem estar
presentes e `exaustivo=true`.

### 4.2 `data/posologia_sugerida.csv` — posologia usual (sugestão editável)

Cabeçalho exato:
```
principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao
```

| Coluna | Semântica |
|---|---|
| `principio_ativo` | Chave (canonizada). Uma posologia por ativo (v1). |
| `posologia_usual` | **Texto que pré-popula o campo** (editável pelo prescritor). Ex.: `Tomar 1 comprimido de 50 mg, por via oral, 1 vez ao dia.` |
| `condicao_nome` / `codigo_cid` | Contexto (proveniência); o lookup v1 é por `principio_ativo`. |
| `fonte` / `status_curadoria` / `validado_por` / `versao` | Iguais ao §4.1. **Só `validado` é servido.** |
| `observacao` | Nota clínica curta (ajuste renal, monitorização etc.). |

---

## 5. Canonicalização (o motor aplica — cure o nome "limpo")

Ao casar `principio_ativo`, o motor aplica `canon_ativo()` (em `semaforo_decisao.py`,
reusado pela posologia): minúsculas, sem acento, **remove sal** (prefixo/sufixo):

- **Prefixos removidos:** `cloridrato de, bromidrato de, oxalato de, sulfato de, fosfato de, maleato de, besilato de, mesilato de, succinato de, tartarato de, acetato de, nitrato de, citrato de, fumarato de, hemifumarato de, pamoato de, lactato de, gluconato de, carbonato de, valerato de, dipropionato de, estearato de, propionato de, dicloridrato de`
- **Sufixos removidos:** `sodico, potassico, potassica, calcico, calcica, magnesico, de sodio, de potassio, de calcio, dihidratado, monoidratado, anidro, trihidratado`

Exemplos: `Oxalato de Escitalopram → escitalopram` · `Losartana Potássica → losartana`.

`canon_cid()`: maiúsculo, sem espaço (`i10.0 → I10.0`). `cadeia_cid()`: sobe a categoria
(`I10.0 → [I10.0, I10]`) — uma regra em `I10` cobre `I10.0`.

> **Implicação para você:** cure o **genérico** (ex.: `escitalopram`). Se uma base trouxer
> com sal, o motor remove — mas prefira já gravar limpo, e **adicione o sal à lista** (via
> proposta de PR ao motor) se aparecer um sal novo não coberto.

---

## 6. Módulo de ingestão (`backend/app/ingestao_clinica/`)

Novo módulo seu. Objetivo: transformar as bases em linhas dos CSVs (§4), **como rascunho**.

- **Entrada:** PCDT/CONITEC (catálogo aberto + leitura dos PDFs — ver achados em
  `[[fase2-decisao-clinica-planejada]]`), RENAME (lista), ANVISA (bulário/dados abertos —
  só cadastro estruturado é aberto), CMED (`data/cmed_apresentacoes.csv` já no repo).
- **Saída:** linhas `status_curadoria=rascunho`, com `fonte`/`versao` preenchidos, no schema §4.
- **Determinístico e rastreável:** cada linha sabe de qual documento/versão veio. Sem LLM.
- **CLIs:** `backend/scripts/ingerir_pcdt.py`, `ingerir_rename.py`, etc. — idempotentes.
- **Testes:** cobertura própria (parsing, canonicalização coerente com §5, rascunho-por-default).

O **fluxo de validação**: você gera rascunho → Fabiano revisa e marca `validado`+`validado_por`
→ o motor acende. (É o mesmo padrão já usado na hipertensão.)

---

## 7. Direção futura (visão de Fabiano, registrada)

A sugestão de medicamento (autocomplete) deve evoluir para **ranquear por melhor
evidência** à medida que a certeza aumenta — convergência busca + semáforo + posologia +
PCDT num ranking *evidence-based*. É a fronteira de pesquisa deste motor; cabe ao seu
escopo (conteúdo/evidência) sobre as interfaces que o chefe mantém estáveis.

---

## 8. Como entregar / coordenar

1. Trabalhe em branches que tocam **apenas** os arquivos da sua coluna (§2).
2. Abra PR; o **Engenheiro-Chefe revisa** a conformidade ao contrato (§3–§5) antes do merge.
3. Mudança que exija o **motor** (nova coluna, novo campo) = **proposta**, não edição direta.
4. **Conteúdo clínico não acende sem a validação de Fabiano** (rascunho→validado).

**Referências de leitura obrigatória:** `docs/ARQUITETURA_DECISAO_CLINICA.md`,
`docs/EXPLICABILIDADE_DECISAO_CLINICA.md`, `backend/app/domain/semaforo_decisao.py`,
`backend/app/domain/posologia_sugerida.py`, `backend/app/routers/ia.py`.
