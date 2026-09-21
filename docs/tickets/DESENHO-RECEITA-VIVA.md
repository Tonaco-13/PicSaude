# DESENHO — Receita Viva: a folha ao lado da pena (UI do prescritor)

| Campo | Valor |
|---|---|
| **Origem** | Conversa de design Fabiano + Kimi (13/09) → `conceitos-prescritor/MENSAGEM-ARQUITETO-RECEITA-VIVA.md` → **parecer do arquiteto (13/09): conceito certo, "é a Regra Zero dentro da tela"**, com correção de classe, uma sobreposição e 4 ACs novos |
| **Classe** | `module` — **corrigida pelo arquiteto**: não é `local-extension` (aquele quadrado é customização institucional). A Receita Viva é o **produto**: altera o `prescritor.html` para todo uso. Semântica clínica intacta — ledger, custódia, estados e API intocados |
| **Régua** | **REGRA ZERO** aplicada à tela que origina o objeto: no papel, a receita existe *durante* o ato; na tela atual, ela só nasce depois do ponto de não-retorno |
| **Martelos** | Arquiteto, 13/09 — ① CPF sobe para Identificação · ② **template ÚNICO, dois alvos** (sobrepõe a duplicação proposta) · ③ mobile: botão flutuante · ④ onda 1 **só receita** |
| **Estado** | 🟡 Desenho pronto, aguarda slot na fila do engenheiro |
| **Executor** | Engenheiro |

---

## §1 O defeito, com evidência

Kimi emitiu duas receitas reais no backend demo (`9a6d899e…` com CID I10 +
2 fármacos; `f21f292e…` sem CID + 1 fármaco) e mediu o túnel na leitura
estática do `prescritor.html`:

- **O formulário é um túnel de coluna única** — dados do paciente (linha 609),
  indicação/CID (634), prescrição terapêutica (645), modo de emissão (653):
  ~100 linhas de rolagem entre o primeiro campo e o botão de emitir.
- **A receita só existe depois do ponto de não-retorno.** O documento
  (`#print-area`, linha 1148) só é preenchido na `tela-sucesso` (1122),
  *após* a emissão.
- **CID e fármacos "somem" na interface** — o CID vira um chip roxo de 12px;
  cada fármaco vira um card de inputs. Nada se parece com o receituário que o
  paciente recebe.

## §2 O conserto: a folha ao lado da pena

- **Split pena/papel.** À esquerda, o formulário; à direita, o receituário se
  escrevendo a cada tecla — **no mesmo layout do PDF institucional**.
- **Lacunas.** Campo vazio aparece na folha como espaço pontilhado — o branco
  do papel esperando a caneta. O prescritor vê o que falta sem validação
  gritar.
- **Tinta.** Cada edição acende um brilho verde sutil na região
  correspondente da folha.
- **CID como selo** (`CID-10 I10`) sob a indicação clínica.
- **Fármacos numerados** na folha, com posologia em itálico.
- **O fecho do arco:** ao emitir, protocolo + hash **carimbam a mesma folha
  que estava à vista** — a tela não navega para um render novo da receita.
- **Mobile (< 980px):** botão flutuante "📄 Ver a receita".

Protótipo navegável verificado em navegador: `conceitos-prescritor/index.html`
(capturas em `conceitos-prescritor/capturas/`).

## §3 Template ÚNICO, dois alvos — a sobreposição do arquiteto

Kimi propôs duplicar deliberadamente o template (folha viva separada do
`#print-area`). **O arquiteto sobrepôs: uma função geradora do receituário,
dois alvos de render** — a folha viva em modo *rascunho* (lacunas pontilhadas)
e o print-area em modo *carimbo*.

> A razão é a lição mais repetida da casa: *mesma língua por construção, não
> por disciplina*. Dois templates do mesmo documento **vão** derivar, e quando
> derivarem o "zero surpresa" vira mentira gradual — a pior espécie. O WYSIWYG
> só é promessa se o W e o Y nascem da mesma função.

Consequência de implementação: extrair uma `renderReceituario(estado, modo)`
única que alimenta (a) a folha viva durante o preenchimento e (b) o
`#print-area`/PDF na emissão e na 2ª via. O `#print-area` deixa de ter marcação
própria divergente — vira alvo da mesma função.

## §4 As quatro marteladas

1. **CPF/CNI sobe para "Identificação do paciente" — CONFIRMADO.** O campo é o
   mesmo (`pac-chave`, chave de custódia do Ticket 63); a custódia mora no
   fluxo de emissão, não na seção onde o input senta. **Guardas que viram AC:**
   o lock M-D (em DEMO os campos do paciente são readonly no cidadão canônico
   — a folha se preenche sozinha, sem edição) e as máscaras/disciplina da A2
   seguem valendo.
2. **Template único — SOBREPOSIÇÃO** (ver §3).
3. **Mobile: botão flutuante — CONFIRMADO**, com AC de cuidado: o botão não
   pode cobrir o botão de emitir em viewport apertado.
4. **Escopo: onda 1 só receita — CONFIRMADO.** A receita tem o template
   institucional provado (print-area/PDF do documento canônico) — UM espelho
   para construir e validar. Exame e atestado, quando vierem, são
   **remontadas** do mesmo padrão, mais baratas por construção.

## §5 ACs

1. **A folha se escreve a cada tecla** — nome, idade, CPF/CNI, telefone,
   endereço, complemento, CEP, cidade/UF, indicação, CIDs e cada campo de cada
   fármaco refletem na folha no evento de input (delegação, robusta a
   limpar/remover/recriar cards, como `_initBuscaMedDelegada`).
2. **Lacuna pontilhada** para todo campo vazio que o documento final exibe;
   nenhum placeholder de formulário vaza para a folha como texto definitivo.
3. **Template único por construção:** folha viva e `#print-area` são renders
   da mesma função geradora — teste que falha se os dois alvos divergirem no
   mesmo estado (W ≡ Y).
4. **O carimbo não troca o layout** (AC do arquiteto): protocolo e hash são
   lacunas pontilhadas até a emissão; ao emitir, carimbam **a mesma folha à
   vista** — sem navegar para um render novo.
5. **A pena não é engolida pela folha** (AC do arquiteto): painéis de IA
   Farmacêutica, semáforo e sugestões seguem legíveis na coluna esquerda em
   desktop comum (1366px+).
6. **O selo de CID reflete o valor canônico escolhido** (AC do arquiteto) —
   o hidden input do typeahead (`prescricao-cid-escolhido`), não o texto
   digitado na indicação.
7. **M-D e A2 sobrevivem** (AC do arquiteto): lock readonly dos campos do
   paciente em DEMO (cidadão canônico) intocado; máscaras numéricas
   (`data-tipo`) seguem valendo nos campos movidos.
8. **Mobile:** o botão flutuante não cobre o botão de emitir em viewport
   apertado (AC do arquiteto).
9. **O fluxo físico não muda:** `imprimirDireto()` e a 2ª via continuam
   saindo pelo mesmo documento, agora gerado pela função única — suíte de
   browser da emissão verde sem adaptação de roteiro.

## §6 Fora de escopo (anotado pelo arquiteto para o futuro)

- **Número do talão na folha** quando houver fármaco controlado — a ponta
  visual do motor regulatório.
- **Posologia em itálico na folha como convite à sugestão editável** da
  `posologia_sugerida` — hoje chaveada por condição
  (`DESENHO-POSOLOGIA-POR-CONDICAO.md`, o ticket nascido do achado I50/J44).
- **Exame e atestado** como remontadas do padrão, em ondas próprias.

## §7 Referências

| Artefato | Caminho |
|---|---|
| Protótipo navegável | `conceitos-prescritor/index.html` |
| Capturas de verificação | `conceitos-prescritor/capturas/` |
| Mensagem original ao arquiteto | `conceitos-prescritor/MENSAGEM-ARQUITETO-RECEITA-VIVA.md` |
| Parecer do arquiteto (13/09) | `docs/tickets/PARECER-ARQ-RECEITA-VIVA-2026-09-13.md` — §3–§5 deste desenho o incorporam integralmente |

---

*Desenho redigido por Kimi a pedido do arquiteto ("manda o Kimi redigir o
ticket — classe `module`, template único, onda receita"), 13/09. O conceito é
a primeira UI que trata a receita como o objeto sanitário que ela é — não como
um formulário que por acaso a produz.*
