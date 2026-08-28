# Desenho — typeahead unificado do encaminhamento + base CBO (saúde)

| Campo | Valor |
|---|---|
| **Origem** | Fabiano, 28/08: *"os motores de busca do encaminhamento se apresentarem como no atestado ou pedido de exames?"* → parecer do arquiteto → **dois martelos**: unificação visual + troca da base para CBO |
| **Autor** | Arquiteto (Z) — desenho, **não implementação** |
| **Classe** | PR 1 `module` (componente de tela, §4) · PR 2 `adapter` (importação de catálogo, snapshot versionado, §3) — ordem invertida pelo §6 |
| **Estado** | PR 1 (`module`) implementado — `typeahead-catalogo.js`, duas montagens no encaminhamento. PR 2 (`adapter`, base CBO) segue como próximo passo |
| **Relacionados** | `catalogos-encaminhamento.js` (ENG-016 §5 — o arquivo que se troca de base) · `DESENHO-ENCAMINHAMENTO-UX.md` · R4/§2a (identificador externo nunca ao vivo) |

---

## §1 O fato que molda o desenho: psicologia é saúde — mas NÃO está no grupo "saúde" do CBO

Pergunta do Fabiano: *"a psicologia está na saúde, certo?"* — resposta em duas camadas:

- **Em regulação sanitária: SIM.** Psicólogo é profissional de saúde de nível superior (CFP,
  SUS/NASF, e-CNS) — e o mini-CID do próprio encaminhamento carrega F32/F41, cujo destino
  natural é exatamente a psicologia.
- **No CBO: NÃO.** A família **2515 — Psicólogos e psicanalistas** (2515-05 educacional,
  2515-10 clínico, …) pertence ao **subgrupo principal 25** (ciências sociais/humanas
  aplicadas) — **fora** do subgrupo 22 ("ciências biológicas, da saúde e afins"), onde
  moram 2251 (médicos), 2252 (odontologia) e 2232 (enfermagem). Verificado na publicação
  do MTE (Portaria 397/2002, livro oficial do CBO).

**Conseqüência arquitetural, e é o guardião deste desenho:** a base CBO do encaminhamento
**não pode ser um filtro por prefixo "22 = saúde"** — isso excluiria silenciosamente a
psicologia do universo de destino, um defeito clínico disfarçado de precisão técnica. A
base é uma **whitelist EXPLÍCITA de famílias CBO**, versionada no snapshot, com 2515
dentro **por decisão declarada** — não por acidente de agrupamento do MTE.

> Guarda executável proposta: teste de regressão afirmando que a família 2515 está na
> base. É o teste que cai se alguém "simplificar" para prefixo 22.

## §2 Duas perguntas, dois conjuntos — não confundir

A casa já usa CBO para outra coisa, e os conjuntos são **diferentes de propósito**:

| Pergunta | Conjunto | Onde vive |
|---|---|---|
| **Quem pode prescrever?** | `CBO_PREFIXES = (2251, 2252, 2232)` — médicos, odontologia, enfermagem | `app/config.py:13`; filtra o snapshot CNES (`cnes_prescritor.py:109`) |
| **Para onde se encaminha?** | whitelist NOVA, mais ampla — o universo assistencial de destino | snapshot CBO deste desenho |

O universo de encaminhamento é mais largo que o de prescrição **por natureza** (receita
não sai de 2251/2252/2232; encaminhamento vai a psicologia, fisioterapia, fono,
nutrição…). **Proibido reutilizar `CBO_PREFIXES` como base do formulário** — são
perguntas diferentes com respostas diferentes.

**Whitelist inicial proposta** (a conferência fina das famílias é passo 1 da importação,
contra a publicação oficial do MTE — **nada entra por memória**):

- **2251** (médicos — as subfamílias SÃO as especialidades médicas: cardiologia,
  endocrinologia… a lista atual de 15 mapeia quase 1:1 aqui)
- **2252** (odontologia)
- **2232** (enfermagem)
- **2231 · 2236 · 2237** (fisioterapia · fonoaudiologia · nutrição — conferir códigos na
  importação)
- **2515** (psicólogos e psicanalistas) — o caso-guarda do §1

Extensões futuras (assistente social 2512, farmacêutico, serviço social NASF): uma linha
na whitelist, novo snapshot versionado — decisão do arquiteto quando houver caso real.

## §3 PR da base `adapter` — snapshot CBO versionado

O cabeçalho do próprio `catalogos-encaminhamento.js` já declara o caminho: *"completar a
lista é importação de catálogo (classe `adapter`, §10): entra por snapshot versionado,
nunca por consulta ao vivo"*.

- **Ferramenta offline** (script no repo) que produz o snapshot a partir da publicação
  oficial do CBO (MTE). Roda em máquina de desenvolvedor; **nunca em runtime, nunca em
  deploy, nunca com fetch ao vivo** (R4 aplicado à referência).
- **Arquivo versionado** (sucessor do bloco `especialidades` do
  `catalogos-encaminhamento.js`): cada entrada com `{codigo CBO, título, família}` +
  `versao_cbo` + `data_snapshot` + famílias incluídas declaradas no próprio arquivo.
- **Alias das personas demo**: o matching de destino (`carregarSugestoesDestino`) compara
  strings; o snapshot traz uma tabela de alias mínima (ex.: persona "CARDIOLOGIA" ↔
  CBO 2251-10 Cardiologista) para a demo continuar casando. **Não** se muda o
  comportamento do endpoint de destino nesta PR.
- **"OUTRA" permanece** — escape de texto livre, no mesmo espírito do "não listado" do
  mini-CID: snapshot é referência, não gaiola.

**ACs:**
1. Toda especialidade oferecida carrega código CBO e família; nenhuma entrada sem código.
2. **2515 presente** (a regressão do §1) — vermelho-antes-de-verde contra um snapshot
   sem psicologia.
3. O arquivo declara fonte (Portaria 397/MTE, versão CBO), data e famílias incluídas.
4. O script de importação não é invocado por nenhum caminho de runtime/deploy (guarda de
   import/referência).
5. `CBO_PREFIXES` intocado — o conjunto de prescritores não muda com esta PR.
6. **A PR do painel não é reaberta**: a troca de base é só o arquivo de dados — o
   rodapé passa a citar CBO/MTE porque o catálogo passou a declará-lo (AC 2 do painel),
   os chips ganham código porque as entradas passaram a tê-lo (AC 1 do painel), e o
   browser test "PSI → 2515" acende aqui.

## §4 PR do painel `module` — typeahead unificado, a língua dos painéis

O encaminhamento adota a **mesma língua visual** dos painéis assistidos que o Fabiano
apontou (padrão do print: painel do CID do atestado). **Um componente, duas montagens**
(precedente: `submodulos.js` #193, `chips-cidadaos-demo.js` #213 — mesma língua por
construção, não por disciplina):

1. **Especialidade** (na estréia, base = a lista atual de 15; a base CBO entra depois,
   pela PR adapter, e **só troca o arquivo de dados** — o componente não muda): hoje é
   `input` filtrando `<select>` nativo (`prescritor.html:990-991`).
2. **CID do encaminhamento** (base = mini-CID local, inalterado): mesma língua, para o
   formulário parar de ter dois pesos.

**O que o painel herda do padrão-ouro:** eco do termo digitado, lista com
**código + título** (o código CBO/CID entra como chip, como o CID-10 do print),
contagem honesta ("5 de 61"), escape explícito ("não listada / OUTRA"), rodapé de
**provenância verdadeira**.

**O que o painel NÃO herda, de propósito:** badge de confiança ("Aproximada · Alta")
— aquele selo existe porque há engine de casamento difuso atrás dele; aqui é substring
exato sobre snapshot. Selo sem engine é teatro. Idem: o rodapé cita **CBO/MTE** (com
versão e data do snapshot), não "DATASUS" — unificar a forma não fabrica fonte.

**Guardas:** teclado (setas + enter) e rótulos ARIA; guardas anti-cópia (nenhum HTML de
painel duplicado inline; componente único); o `<select>` nativo morre substituído, não
convive.

**ACs:**
1. Digitar no campo de especialidade abre o painel com eco, lista (título; código no
   chip **quando a entrada o tiver** — a lista atual não tem, e o chip sem código é a
   forma honesta dela) e contagem — sem clique em `<select>`.
2. Rodapé do painel declara a provenância **lida do catálogo** — na estréia: "lista
   local curada, 15 entradas, versão 2026-08-23.1"; após a troca de base, passa a
   declarar CBO/MTE **sem tocar no componente** (é o teste da agnosticidade).
3. Zero badge de confiança; zero promessa de fonte que não seja a real.
4. "OUTRA"/escape preservado e funcional; o que não está no catálogo continua
   emitível.
5. Mini-CID do encaminhamento na mesma língua (provenância: "parcial, 55 códigos
   verificáveis").
6. Browser test: digitar "CARDIO" lista CARDIOLOGIA na lista atual; escape funciona.

## §5 Fronteiras declaradas

- **Painéis IA existentes (receita/exames/atestado) não são tocados** — o pedido era o
  encaminhamento se apresentar como eles, não refatorá-los para o componente novo.
- **Mini-CID ≠ tabela CID-10**: os dois universos CID seguem separados; convergência é
  decisão futura de catálogo.
- **Endpoint de sugestão de destino intocado** (string match + alias do snapshot);
  enriquecer esse matching é escopo novo.
- **Nada de fetch CBO ao vivo** — em nenhum PR, em nenhum lugar.

## §6 Sequência e martelos

> **SUPERSSÃO (Fabiano, 28/08, pergunta "motor ou tabela primeiro?"): a ordem agora é
> PAVEL primeiro — painel na lista atual —, base CBO depois.** A ordem original deste
> desenho (adapter → module) tratava "o painel consome o snapshot" como dependência de
> construção; era só dependência de **conteúdo** (dois ACs, que migraram para a PR da
> base). A dependência real é a inversa: o contrato do componente precisa ser
> agnóstico de fonte, e a prova mais barata é construí-lo contra a lista pequena que
> já existe — se o componente assumir formato CBO por acidente, a fase de lista-local
> acusa na hora. Somam-se a isso: o ganho visível (a dor que originou o pedido) chega
> antes; e o isolamento de risco no bisect (painel vs. dados são PRs separadas).

1. **PR do painel (`module`, §4)** — typeahead na língua dos painéis, base = lista
   atual de 15 (+ `fonte`/`versão` declaradas no catálogo; mini-CID na mesma língua).
2. **PR da base (`adapter`, §3)** — snapshot CBO versionado substitui o arquivo de
   dados; o componente não muda (AC 6 do §3 é a guarda disso).

Depois do M-C (em voo).

**Martelos (Fabiano, 28/08):** unificação visual ✔ · troca da base para CBO ✔ ·
psicologia incluída por decisão declarada ✔ (§1) · **motor antes da tabela ✔** (§6).

---

*Desenho do arquiteto, 2026-08-28. Âncoras: `prescritor.html:990-991` (select nativo) ·
`catalogos-encaminhamento.js` (lista de 15, versão 2026-08-23.1) · `config.py:13`
(CBO_PREFIXES) · `cnes_prescritor.py:109`. Fonte do fato §1: publicação oficial do CBO
(MTE, Portaria 397/2002) — família 2515 no subgrupo 25, fora do 22. Implementação é do
engenheiro.*
