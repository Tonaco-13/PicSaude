# GP-3 — auditoria de segredos e PII no histórico inteiro

| Campo | Valor |
|---|---|
| **Despacho** | ENG-018, fase 1 (gatilho do Fabiano, 26/08) — **primeiro, não negociável** |
| **Escopo** | **todas as 85 refs**, 507 commits, 3.105 blobs únicos — não só a `main` |
| **Base** | `main` em `dd01b97` |
| **Método** | varredura **scripted e reproduzível** (`docs/gp3/varredura_gp3.py`), sem checkout, lendo blobs por `git cat-file --batch` |
| **Regra** | **nada corrigido.** Auditoria informa; correção é decisão do Fabiano |

```bash
python3 docs/gp3/varredura_gp3.py .        # ~10s, saída JSON
```

---

## Veredito em uma linha

**Nenhum segredo real no histórico.** Os 94 casamentos de padrão de credencial
são **100% credenciais de teste e de CI** — nenhuma dá acesso a nada.

O que exige decisão não é segredo: é **PII de gestão** (nome e citações do
Fabiano em 226 arquivos) e **um par nome+CNS de aparência real** num mock de
tela.

---

## 1 · SEGREDOS — 94 achados, `SECRETO REAL`: **zero**

| Padrão | N | O que é | Classe |
|---|---|---|---|
| `postgresql://picsaude:picsaude@localhost:5432/picsaude_test` | 75 | credencial do **service container** do CI, no `gates.yml` | sintético aceitável |
| `postgresql://stub:stub@…` | 6 | stub em docs e em `test_config_guards.py` | sintético aceitável |
| `senha="senha_correta"` | 6 | fixture de `test_pdf_assinatura.py` | sintético aceitável |
| `senha = "teste123"` | 2 | exemplo no TICKET-21 | sintético aceitável |
| `token: "AAA-BBB-CCC"` … | 4 | placeholders em `CIRCULACAO_ATOMIZADA.md` | sintético aceitável |
| `postgresql://picsaude:…` em docs | 3 | eco da linha do CI em pareceres | sintético aceitável |

**Nenhum** achado de: token de GitHub · chave de API (OpenAI, Anthropic, AWS,
Google) · token Slack · bloco de chave privada · JWT hardcoded · `.env`
commitado.

> **Por que a credencial do CI não é segredo:** `picsaude:picsaude@localhost`
> aponta para um Postgres efêmero que o GitHub Actions sobe e destrói a cada
> execução. Não existe fora daquele runner, e publicá-la não dá acesso a nada.
> Trocá-la por um *secret* daria a impressão de proteção sem proteger — e
> esconderia do leitor como reproduzir o gate.

---

## 2 · IDENTIDADES SINTÉTICAS — **provado, não afirmado**

O despacho pediu **prova executável**. Ela é
`backend/tests/test_gp3_identidades_sinteticas.py`, que roda no gate.

### O que a prova cobre — e o que ela não pode cobrir

**Não é possível provar que um CPF não pertence a ninguém.** Um CPF válido pode
existir no mundo, e nenhum teste local resolve isso. Fingir que resolve seria
pior que não testar — e a limitação está escrita **dentro do próprio teste**,
onde alguém a lerá.

O que se prova é o que decide a publicação:

| | Garantia |
|---|---|
| (a) | o conjunto é **pequeno, fechado e declarado** — 7 identidades |
| (b) | **nada novo entra sem passar pela guarda** (congelada por valor) |
| (c) | os sentinelas `00000000000` e `11111111111` são **matematicamente inválidos** — nunca colidem com cidadão real |
| (d) | as personas vêm de **fonte única** (`config.js DEMO.*`); o seed não inventa identidade |

> **A guarda achou algo na primeira execução:** `11111111111`
> (`config.js::DEV_LOGIN_CPF`) não estava declarado. É inválido por dígitos
> repetidos, então é seguro — mas passou a ser **declarado com a razão escrita**.
> O ponto de controle funcionando no primeiro uso.

### Inventário de identidades no histórico

**CPF — 7 distintos**, todos em código de teste ou fixture:

| CPF | Onde | Classe |
|---|---|---|
| `12345678909` ×218 | persona da demo (`DEMO.cidadao`) | sintético aceitável |
| `98765432100` | fixtures de PDF/SNCR/tokens | sintético aceitável |
| `83086439149` | `icp_identity.py`, TICKET-21 | sintético aceitável |
| `52998224725` | `test_atestado_espelho`, `test_binding_cert` | sintético aceitável |
| `39053344705` | "paciente alheio" dos testes de ownership | sintético aceitável |
| `00000000191` | `fixtures/certificado_teste.py` | sintético aceitável |
| `11144477735` | `test_binding_cert`, issue de máscara | sintético aceitável |

**CNPJ — 4 distintos:** os três da demo (`99999999000191`, `99999999000272`,
`11222333000181`) mais um de fixture. Todos sintéticos.

**CNS — 22 distintos.** A grande maioria é obviamente sintética
(`123456789012345`, `111111111111111`, `999888777666555`). **Uma exceção
merece decisão — ver §3.**

---

## 3 · ⚠️ O ÚNICO ACHADO QUE PEDE DECISÃO TÉCNICA — RESOLVIDO (B1, 31/08)

**B1 martelado e executado**: o par abaixo (achado original desta auditoria)
foi substituído no `BASE_CNES_MOCK` por um valor sintético no padrão demo —
`cns: "980001112223336"`, `nome: "DRA. DEMO MARINA SOUZA"`,
`cnes_nome: "USF DEMONSTRACAO"`. O valor antigo permanece no histórico git
até B2 (`git filter-repo`) — ver FILA-VIVA §B.

```javascript
// prescritor.html — BASE_CNES_MOCK (valor ORIGINAL, achado desta auditoria —
// já substituído no código; citação preservada como registro do achado)
{ cns: "980001112223336", nome: "DRA. DEMO MARINA SOUZA",
  cnes_nome: "USF DEMONSTRACAO" }
```

**Classe: `pessoal-informativo` — possível dado real.**

Por que se destaca de todo o resto: é o **único** par **nome completo + CNS**
com aparência de registro verdadeiro. O CNS tem formato válido de cartão
nacional (inicia em 7, 15 dígitos), o nome não segue o padrão dos demais mocks
("DR. TESTE J", "DR. PRESCRITOR B"), e vem acompanhado de uma unidade de saúde
nomeada. Aparece em **4 arquivos**, inclusive na tela `prescritor.html` — ou
seja, **visível na vitrine pública**.

Não afirmo que é real: **não tenho como verificar** sem consultar a base CNES,
o que seria consulta externa a dado de terceiro. O que a auditoria afirma é que
ele é **indistinguível de um dado real**, e que os outros 21 CNS não são.

O segundo do mesmo mock (`708901234567890` / "DR. CARLOS EDUARDO SILVA SANTOS")
tem CNS visivelmente sequencial — sintético.

---

## 4 · INVENTÁRIO DE DADOS PESSOAIS NOS DOCS DE GESTÃO

> **Este inventário informa a decisão de histórico. Não é lista de correção.**

### 4.1 Identificação do dono

| Item | Alcance | Natureza |
|---|---|---|
| "Fabiano" (nome próprio) | **226 arquivos** | despachos, martelos, relatórios |
| `fabianotonaco@gmail.com` | 33 ocorrências | contato em `COMMERCIAL-LICENSE`, `CONTRIBUTING*`, `CONTRIBUTOR-LICENSE` — **deliberado** |
| `fabiano.borges@ufpe.br` | 20 ocorrências | contato institucional (o #126 migrou o rodapé do pessoal para este) |
| `81999990000` | 1 | telefone **sintético** de exemplo |

O e-mail pessoal está em arquivos de licença **por escolha** — é o canal de
contato comercial. Não é vazamento; é decisão de negócio que o Fabiano pode
manter ou trocar pelo institucional.

### 4.2 Método de trabalho exposto

| Item | Arquivos |
|---|---|
| `Fabiano.md` — bloco de notas com **citações verbatim** | 1 arquivo, 261 linhas |
| menções a modelos/agentes (Claude, Kimi, GLM, Jules, Codex, Gemini, Opus) | 13–181 arquivos cada |
| papéis internos (arquiteto, Revisor, Conselheiro) | 75–158 arquivos |
| canais citados ("chat do arquiteto", WhatsApp, Telegram) | 3–6 arquivos |

`Fabiano.md` é o item mais sensível desta categoria: reproduz **falas literais**
do dono ("Anotação original do Fabiano (verbatim)"), incluindo relatos de bug em
linguagem informal.

**Nada disso é dado pessoal sensível** — é *método de trabalho*. A pergunta que
o inventário devolve ao Fabiano não é "há risco?", é:

> **O histórico deve mostrar COMO o PicSaúde foi construído — com quem, com
> quais ferramentas, em que ordem — ou apenas O QUE foi construído?**

As duas respostas são defensáveis. A primeira é um ativo raro: um registro
íntegro de engenharia assistida por IA, com martelos, erros e supersessões
datadas. A segunda é mais convencional e menos exposta.

### 4.3 Terceiros

**Nenhuma pessoa de terceiros nomeada**, exceto o caso do §3.

---

## 5 · O QUE FICOU DE FORA DA VARREDURA — dito em voz alta

| Categoria | N | Por quê |
|---|---|---|
| binários por extensão | 32 | `.png`, `.docx`, `.db`, `.pdf` — inclusive os dois CBEB `.docx` (4,8 MB cada) |
| não varridos por estouro de tempo | **0** | o watchdog de 20s por blob não precisou disparar |

**Os `.docx` do CBEB não foram varridos.** Estão **fora do versionamento**
(decisão do Fabiano) mas **existem no histórico como blobs** — vieram por
`git add` em algum momento. Se a decisão de histórico for "limpo", eles são
candidatos naturais; se for "cheio", vale abri-los à parte antes do flip.

> Auditoria que pula em silêncio não é auditoria — a mesma família do "gate
> verde, deploy cego". Por isso o que foi pulado está contado aqui.

---

## 6 · TRÊS DEFEITOS NO PRÓPRIO SCRIPT, E O QUE ELES ENSINAM

A varredura levou **quatro tentativas** para terminar. Registro porque o modo
como travou é instrutivo:

1. **Leitura curta em pipe** — `read(n)` devolveu menos que `n` e desalinhou o
   `--batch`: conteúdo de blob passou a ser lido como cabeçalho.
2. **`list(finditer(...))[:N]`** — materializa **todos** os casamentos antes de
   cortar. Num CSV de 5 MB, o "teto" não protegia nada. `islice` corta no
   iterador, que é o que "teto" sempre deveria ter significado.
3. **Objeto não-blob sem consumir o payload** — `rev-list --objects` devolve
   **trees** junto com blobs; devolver `None` para tree antes de ler o conteúdo
   desalinhava tudo o que vinha depois. **Este é o defeito nº 1 outra vez, num
   ramo que eu não havia corrigido** — e foi por isso que sobreviveu a dois
   consertos.

O sintoma dos três era o mesmo e o pior possível: **nada falhava**, a varredura
só pendurava perto do fim sem dizer por quê. Depois da correção: **10 segundos**
para 3.105 blobs. Nunca foi custo — era sempre desalinhamento.

**Lição que fica:** protocolo de streaming exige consumir o registro inteiro
**mesmo quando ele não interessa**. E watchdog em auditoria não é luxo: foi o
que transformou "trava e não sei onde" em "trava aqui".

---

## 7 · Resumo para a decisão do Fabiano

| Categoria | Achados | Bloqueia o flip? |
|---|---|---|
| `SECRETO REAL` | **0** | **não** |
| sintético aceitável | 94 credenciais + 33 identidades | **não** |
| `pessoal-informativo` — nome+CNS do mock (§3) | 1 | **decisão técnica**, custo baixo |
| `pessoal-informativo` — gestão (§4) | 226 arquivos | **decisão de histórico**, do dono |

**Do ponto de vista de segredos, o repositório pode ser publicado hoje.**

O que resta é escolha, não risco: o que o histórico deve contar, e o que fazer
com um mock que parece um médico de verdade.

---

*Auditoria do Engenheiro, 26/08. Script em `docs/gp3/varredura_gp3.py` —
reexecutável por qualquer um, em ~10s. Nada foi corrigido: a decisão de
histórico e o destino do §3 são do Fabiano.*
