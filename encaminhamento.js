/* ==========================================================================
 * encaminhamento.js — O ENCAMINHAMENTO: uma função geradora, dois alvos.
 *
 * ENG-023 · lei: `docs/tickets/DESENHO-ENCAMINHAMENTO-VIVO.md`.
 *
 * O DEFEITO QUE ESTE ARQUIVO FECHA
 * --------------------------------
 * O encaminhamento é o único dos quatro objetos cujo papel inteiro APONTA PARA
 * ALGUÉM — e esse alguém não aparecia em lugar nenhum da tela. O documento só
 * existia na REVISÃO (um passo antes do ponto de não-retorno) e sumia logo
 * depois de emitir, com o `form.reset()`, virando linha de lista. Sem
 * impressão própria: o objeto nunca teve um alvo de papel.
 *
 * O TERCEIRO CONSUMIDOR DO NÚCLEO
 * -------------------------------
 * A receita provou a mecânica, o exame provou que era família, e este é o
 * terceiro a consumir `documento-nucleo.js` sem que o núcleo precise conhecer
 * nenhum dos três. O que ele pediu ao núcleo — e cresceu lá, não aqui — foi o
 * flutuante vigiando DOIS gestos de emissão: este é o único objeto em que
 * "emitir" acontece em dois tempos (revisar → confirmar).
 *
 * A ANATOMIA: O DESTINATÁRIO É A ASSINATURA DESTE PAPEL
 * ------------------------------------------------------
 * A receita tem posologia; o exame tem prioridade e TUSS; o encaminhamento tem
 * DESTINO. Por isso a caixa do destinatário é o bloco enfatizado do documento
 * — especialidade em corpo maior, finalidade e CNS de destino — e por isso a
 * frase gerada ("Encaminho o(a) paciente X para <finalidade> em
 * <ESPECIALIDADE>") aparece por inteiro: é ela que define o documento, e é
 * dela que o hash v2 toma conta.
 *
 * A FOLHA ESPELHA O DOCUMENTO CANÔNICO v2
 * ----------------------------------------
 * Campo a campo, o que `_documento_canonico_encaminhamento()` congela no
 * SHA-256: protocolo, CNS de origem e destino, CPF do paciente, especialidade,
 * CID, justificativa, itens (especialidade/procedimento/motivo) e — na v2 — a
 * finalidade. *"Hash que não congela o que foi visto é hash que mente"*; esta
 * folha existe para que o que foi visto seja exatamente isso.
 *
 * CONTRATO (espelho de `Receituario` e `PedidoExame`, por construção)
 * -------------------------------------------------------------------
 *   renderEncaminhamento(estado, modo)          → string (HTML do documento)
 *   Encaminhamento.render                       → a MESMA função (alias)
 *   Encaminhamento.montar(alvo, estado, modo)   → pinta um alvo (+ tinta)
 *   Encaminhamento.textoDoDocumento(el)         → texto normalizado (W ≡ Y)
 *   Encaminhamento.MODOS                        → { RASCUNHO, CARIMBO }
 * ========================================================================== */

(function () {
  "use strict";

  const N = window.DocumentoNucleo;

  const MODOS = N.MODOS;
  const esc = N.esc;
  const _vazio = N.vazio;

  // `enc` é o gancho nomeado deste documento: as lacunas saem como
  // `class="doc-lacuna enc-lacuna"` — estilo no núcleo, identidade aqui.
  const { lacuna, ou, ouMaiusculo, nota } = N.vocabulario("enc");

  // ── blocos ───────────────────────────────────────────────────────────────
  //
  // cabecalho · emitente · paciente · destinatario · frase · clinico · itens ·
  // rodape. Regiões NOMEADAS: é por elas que a tinta sabe o que mudou e que
  // uma guarda aponta a região que divergiu.

  function _cabecalho(e) {
    const proto = _vazio(e.protocolo)
      ? lacuna("gerado na emissão")
      : '<b class="enc-mono">' + esc(e.protocolo) + "</b>";

    let hash;
    if (!_vazio(e.hash)) {
      hash = '<span class="enc-mono">' + esc(e.hash) + "</span>";
    } else {
      hash = lacuna("gerado na emissão");
    }

    return (
      '<header class="enc-cabecalho" data-bloco="cabecalho">' +
      "<h2>Encaminhamento Médico</h2>" +
      '<p class="enc-sub">PicSaúde · Transferência eletrônica de dados</p>' +
      '<p class="enc-proto" data-campo="protocolo">Protocolo: ' + proto + "</p>" +
      '<p class="enc-proto enc-proto-hash" data-campo="hash">Hash SHA-256: ' + hash + "</p>" +
      "</header>"
    );
  }

  function _emitente(e) {
    const m = e.emitente || {};
    return (
      '<section class="enc-box" data-bloco="emitente">' +
      '<span class="enc-rot">Identificação do emitente — origem</span>' +
      '<p class="enc-linha-forte" data-campo="emitente-nome">' +
      ou(m.nome, "prescritor não identificado") +
      ' <span class="enc-cns">· CNS ' + ou(m.cns, "cns de origem") + "</span></p>" +
      '<p class="enc-linha" data-campo="emitente-unidade">' +
      ou(m.unidade, "unidade de saúde") +
      "</p>" +
      "</section>"
    );
  }

  function _paciente(e) {
    const p = e.paciente || {};
    return (
      '<section class="enc-box" data-bloco="paciente">' +
      '<span class="enc-rot">Identificação do paciente</span>' +
      '<p class="enc-linha-forte" data-campo="paciente-nome">' +
      ou(p.nome, "nome do paciente") +
      ' <span class="enc-cpf">· CPF/CNI ' +
      ou(p.cpf, "obrigatório para a emissão") +
      "</span></p>" +
      "</section>"
    );
  }

  /** A caixa que faz deste papel o que ele é: para QUEM ele aponta. */
  function _destinatario(e) {
    const d = e.destinatario || {};
    const linha2 = [
      _vazio(d.finalidade) ? lacuna("finalidade") : esc(String(d.finalidade).trim()),
      "CNS do profissional de destino: " + ou(d.cns, "cns de destino"),
    ].join(" &middot; ");

    return (
      '<section class="enc-destinatario" data-bloco="destinatario">' +
      '<span class="enc-rot enc-rot-destino">Destinatário</span>' +
      '<p class="enc-especialidade" data-campo="especialidade">' +
      ouMaiusculo(d.especialidade, "especialidade de destino") +
      "</p>" +
      '<p class="enc-linha" data-campo="destino-detalhe">' + linha2 + "</p>" +
      "</section>"
    );
  }

  /**
   * A frase que DEFINE o documento — e a única lacuna INLINE dos quatro.
   *
   * Ela mora dentro de uma sentença corrida, não num campo: é o modo que o
   * núcleo já trazia no contrato desde o nascimento, pensado para o atestado,
   * e que o encaminhamento passou a usar primeiro. Em modo de bloco, a largura
   * mínima rasgaria a linha no meio da frase.
   */
  function _frase(e) {
    const p = e.paciente || {};
    const d = e.destinatario || {};
    const inline = { inline: true };
    return (
      '<section class="enc-frase" data-bloco="frase">' +
      '<span class="enc-rot">Encaminhamento</span>' +
      '<p class="enc-linha-frase" data-campo="frase">Encaminho o(a) paciente <b>' +
      ou(p.nome, "nome do paciente", inline) +
      "</b> para <b>" +
      ou(d.finalidade, "finalidade", inline) +
      "</b> em <b>" +
      ouMaiusculo(d.especialidade, "especialidade", inline) +
      "</b>.</p>" +
      "</section>"
    );
  }

  function _clinico(e) {
    const selo = _vazio(e.cid)
      ? lacuna("nenhum CID informado")
      : '<span class="enc-selo-cid" data-cid="' + esc(e.cid) + '"><b>CID-10 ' +
        esc(e.cid) + "</b>" +
        (_vazio(e.cid_descricao) ? "" : "<span>" + esc(e.cid_descricao) + "</span>") +
        "</span>";

    return (
      '<section class="enc-clinico" data-bloco="clinico">' +
      '<span class="enc-rot enc-rot-clinica">CID</span>' +
      '<div class="enc-selos" data-campo="cid">' + selo + "</div>" +
      '<span class="enc-rot enc-rot-clinica enc-rot-justificativa">Justificativa clínica</span>' +
      '<p class="enc-linha" data-campo="justificativa">' +
      ou(e.justificativa, "o coração do documento — mínimo de 20 caracteres") +
      "</p>" +
      "</section>"
    );
  }

  function _item(x, i, especialidadeDoDestino) {
    // A especialidade do item é a do destinatário (o formulário não a pede por
    // item); mostrá-la ao lado do procedimento é o que o documento canônico
    // grava em `itens[].especialidade`.
    const esp = _vazio(x.especialidade) ? especialidadeDoDestino : x.especialidade;
    return (
      '<div class="enc-item" data-item="' + (i + 1) + '">' +
      '<p class="enc-item-cabeca">' +
      '<span class="enc-item-n">' + (i + 1) + ".</span> " +
      '<b class="enc-item-nome">' + ouMaiusculo(x.procedimento, "procedimento") + "</b>" +
      (_vazio(esp) ? "" : ' <span class="enc-item-esp">— ' +
        esc(String(esp).trim().toUpperCase()) + "</span>") +
      "</p>" +
      '<p class="enc-item-motivo"><i>' + ou(x.motivo, "motivo do item") + "</i></p>" +
      "</div>"
    );
  }

  function _itens(e) {
    const itens = e.itens || [];
    const esp = (e.destinatario || {}).especialidade || "";
    const corpo = itens.length
      ? itens.map((x, i) => _item(x, i, esp)).join("")
      : lacuna("os itens aparecem aqui, numerados, à medida que forem escritos");

    return (
      '<section class="enc-itens" data-bloco="itens">' +
      '<span class="enc-rot">Itens do encaminhamento</span>' +
      '<div class="enc-itens-corpo" data-campo="itens">' + corpo + "</div>" +
      "</section>"
    );
  }

  function _rodape(e) {
    const a = e.assinatura || {};
    const selo = a.tipo === "digital"
      ? '<span class="enc-ass-nota">assinatura eletrônica do emitente</span>'
      : lacuna("a assinatura entra na emissão");

    return (
      '<footer class="enc-rodape" data-bloco="rodape">' +
      '<div class="enc-local">' +
      '<p class="enc-linha" data-campo="local-data">' +
      ou(e.local_data, "município e data") +
      "</p>" +
      // A posse é do cidadão, e o papel diz isso: é ele quem leva o documento
      // ao destinatário, e é o gesto dele que move a custódia (J.7 aplicado ao
      // terceiro objeto — agendar é compromisso, entregar é posse).
      '<p class="enc-nota-posse">O cidadão leva este documento ao destinatário ' +
      "— o gesto dele move a posse.</p>" +
      "</div>" +
      '<div class="enc-assinatura">' +
      '<div class="enc-risco"></div>' +
      '<p class="enc-linha-forte" data-campo="assinante-nome">' +
      ou(a.nome, "prescritor não identificado") +
      "</p>" +
      '<p class="enc-linha" data-campo="assinante-cns">CNS ' +
      ou(a.cns, "cns de origem") +
      "</p>" +
      selo +
      "</div></footer>"
    );
  }

  function _seloCustodia(e) {
    if (!e.emitido) return "";
    // Caixa-alta na FUNÇÃO, nunca em `text-transform`: o selo é conteúdo do
    // estado emitido e precisa nascer igual nos dois alvos.
    //
    // "CUSTÓDIA AO CIDADÃO" e não "COM O CIDADÃO": o selo nomeia o fato
    // jurídico que o ledger registra (`emissao_digital` abre a posse no
    // cidadão), não a etiqueta da lista.
    const texto = "✓ EMITIDO · CUSTÓDIA AO CIDADÃO";
    const traco = _vazio(e.hash)
      ? ""
      : '<span class="doc-selo-hash enc-selo-hash">sha-256 · ' +
        esc(String(e.hash).slice(0, 24)) + "…</span>";
    return (
      '<div class="doc-selo-custodia enc-carimbo" data-bloco="carimbo">' +
      "<span>" + esc(texto) + "</span>" + traco +
      "</div>"
    );
  }

  /**
   * A FUNÇÃO GERADORA do encaminhamento.
   *
   * @param {object} estado  o documento, como dado
   * @param {string} modo    MODOS.RASCUNHO | MODOS.CARIMBO — só o MEIO
   * @returns {string} HTML do encaminhamento
   */
  function renderEncaminhamento(estado, modo) {
    const e = estado || {};
    const m = modo === MODOS.CARIMBO ? MODOS.CARIMBO : MODOS.RASCUNHO;
    return (
      '<article class="doc-folha enc-folha doc-modo-' + m + " enc-modo-" + m +
        (e.emitido ? " doc-emitida enc-emitido" : "") + '">' +
      _cabecalho(e) +
      _emitente(e) +
      _paciente(e) +
      _destinatario(e) +
      _frase(e) +
      _clinico(e) +
      _itens(e) +
      _rodape(e) +
      _seloCustodia(e) +
      "</article>"
    );
  }

  /** Pinta um alvo — o núcleo cuida do invólucro e da tinta. */
  function montar(alvo, estado, modo) {
    N.montar(alvo, renderEncaminhamento(estado, modo), modo);
  }

  const Encaminhamento = {
    MODOS: MODOS,
    render: renderEncaminhamento,
    montar: montar,
    textoDoDocumento: N.textoDoDocumento,
  };

  window.Encaminhamento = Encaminhamento;
  window.renderEncaminhamento = renderEncaminhamento;
})();
