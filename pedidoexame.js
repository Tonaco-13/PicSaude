/* ==========================================================================
 * pedidoexame.js — O PEDIDO DE EXAMES: uma função geradora, dois alvos.
 *
 * ENG-022, commit 2 · lei: `docs/tickets/DESENHO-PEDIDO-EXAME-VIVO.md`.
 *
 * O DEFEITO QUE ESTE ARQUIVO FECHA — pior que o da receita
 * --------------------------------------------------------
 * A receita, antes da onda 1, ao menos tinha um `#print-area` preenchido
 * tarde. O pedido de exame **não tinha documento nenhum na tela** — nem
 * depois de emitir. O próprio comentário do `imprimirPedidoFisico` confessava:
 * *"como #print-area só contém o template do RECEITUÁRIO, a impressão do
 * pedido saía sem documento"*. O papel oficial só existia como PDF do
 * servidor, atrás de um botão, depois do ponto de não-retorno.
 *
 * POR QUE ESTE ARQUIVO EXISTE, E NÃO UM `documento.js` PARAMETRIZADO
 * ------------------------------------------------------------------
 * Adjudicação do arquiteto: *"duas anatomias numa função só é a dupla posse
 * pela porta dos fundos"*. O receituário e o pedido de exame compartilham o
 * MEIO (papel, lacuna, tinta, W ≡ Y) — e é isso, e só isso, que mora no
 * `documento-nucleo.js`. A ANATOMIA de cada um é dele: o pedido tem selo de
 * prioridade, códigos TUSS/SIGTAP, preparo e prazo de validade; o receituário
 * tem posologia e via. Fundi-los numa função com bandeiras seria trocar dois
 * documentos honestos por um que finge ser os dois.
 *
 * A ANATOMIA AQUI É A DO PDF OFICIAL
 * -----------------------------------
 * Não é a do receituário: é a do `documento-referencia.pdf` — cabeçalho com
 * selo de prioridade, PRESCRITOR, PACIENTE, INDICAÇÃO com CID como selo,
 * EXAMES SOLICITADOS numerados com TUSS/SIGTAP e preparo, IDENTIFICAÇÃO DO
 * DOCUMENTO (datas, prioridade, hash), aviso de validade e assinatura.
 *
 * O SELO DE CUSTÓDIA DIZ O FATO, NÃO O DESTINO
 * ---------------------------------------------
 * "✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE" — a emissão digital abre custódia
 * `prescritor → paciente` (ARQUITETURA_EXAMES: quem nasce detendo é o
 * cidadão, que depois leva o pedido ao prestador). "RUMO AO PRESTADOR" foi
 * considerado e REJEITADO: anteciparia um fato que ainda não ocorreu — a
 * lição do `pedido_agendado` fantasma.
 *
 * CONTRATO (espelho do `Receituario`, por construção)
 * ---------------------------------------------------
 *   renderPedidoExame(estado, modo)          → string (HTML do documento)
 *   PedidoExame.render                       → a MESMA função (alias)
 *   PedidoExame.montar(alvo, estado, modo)   → pinta um alvo (+ tinta)
 *   PedidoExame.textoDoDocumento(el)         → texto normalizado (W ≡ Y)
 *   PedidoExame.MODOS                        → { RASCUNHO, CARIMBO }
 * ========================================================================== */

(function () {
  "use strict";

  const N = window.DocumentoNucleo;

  const MODOS = N.MODOS;
  const esc = N.esc;
  const _vazio = N.vazio;

  // `exame` é o gancho nomeado deste documento: as lacunas saem como
  // `class="doc-lacuna exame-lacuna"` — estilo no núcleo, identidade aqui.
  const { lacuna, ou, ouMaiusculo, nota } = N.vocabulario("exame");

  /** As três prioridades do pedido, como o documento oficial as escreve.
   *
   *  Caixa-alta AQUI e não em `text-transform`: o selo é conteúdo do
   *  documento, e o W ≡ Y compara texto. */
  const _PRIORIDADES = {
    rotina: "ROTINA",
    urgente: "URGENTE",
    urgentissimo: "URGENTÍSSIMO",
  };

  function _rotuloPrioridade(v) {
    const k = String(v || "").trim().toLowerCase();
    return _PRIORIDADES[k] || "";
  }

  // ── blocos ───────────────────────────────────────────────────────────────
  //
  // Cada região é um `[data-bloco]`: cabecalho · prescritor · paciente ·
  // indicacao · exames · identificacao · rodape. É por eles que a tinta sabe o
  // que mudou, e é por eles que uma guarda aponta a REGIÃO que divergiu.

  function _cabecalho(e) {
    const proto = _vazio(e.protocolo)
      ? lacuna("gerado na emissão")
      : '<b class="exame-mono">' + esc(e.protocolo) + "</b>";

    const prioridade = _rotuloPrioridade(e.prioridade);
    const selo = prioridade
      ? '<span class="exame-selo-prioridade exame-prioridade-' +
        esc(String(e.prioridade).toLowerCase()) + '" data-campo="prioridade">' +
        esc(prioridade) + "</span>"
      : "";

    return (
      '<header class="exame-cabecalho" data-bloco="cabecalho">' +
      selo +
      "<h2>Pedido de Exames</h2>" +
      '<p class="exame-sub">PicSaúde · Plataforma de custódia sanitária digital</p>' +
      '<p class="exame-proto" data-campo="protocolo">Protocolo: ' + proto + "</p>" +
      "</header>"
    );
  }

  function _prescritor(e) {
    const p = e.prescritor || {};
    return (
      '<section class="exame-box" data-bloco="prescritor">' +
      '<span class="exame-rot">Prescritor</span>' +
      '<p class="exame-linha-forte" data-campo="prescritor-nome">' +
      ou(p.nome, "prescritor não identificado") +
      ' <span class="exame-registro">· ' + ou(p.registros, "registro profissional") +
      "</span></p>" +
      '<p class="exame-linha" data-campo="prescritor-unidade">' +
      ou(p.unidade, "unidade de saúde") +
      "</p>" +
      "</section>"
    );
  }

  function _paciente(e) {
    const p = e.paciente || {};
    return (
      '<section class="exame-box" data-bloco="paciente">' +
      '<span class="exame-rot">Paciente</span>' +
      '<p class="exame-linha-forte" data-campo="paciente-nome">' +
      ou(p.nome, "nome do paciente") +
      ' <span class="exame-chave">· CPF/CNI ' +
      ou(p.chave, "obrigatório para a emissão digital") +
      "</span></p>" +
      "</section>"
    );
  }

  function _indicacao(e) {
    const cids = (e.cids || [])
      .map(
        (c) =>
          '<span class="exame-selo-cid" data-cid="' + esc(c.codigo) +
          '"><b>CID-10 ' + esc(c.codigo) + "</b>" +
          (_vazio(c.descricao) ? "" : "<span>" + esc(c.descricao) + "</span>") +
          "</span>"
      )
      .join("");

    return (
      '<section class="exame-indicacao" data-bloco="indicacao">' +
      '<span class="exame-rot exame-rot-clinica">Indicação clínica</span>' +
      '<p class="exame-linha" data-campo="indicacao">' +
      ou(e.indicacao, "hipótese diagnóstica ou motivo") +
      "</p>" +
      '<div class="exame-selos" data-campo="cids">' +
      (cids || lacuna("nenhum CID escolhido")) +
      "</div>" +
      "</section>"
    );
  }

  function _exame(x, i) {
    // TUSS, SIGTAP e categoria são o que a normalização assistida devolveu;
    // sem ela, a linha inteira some — não é lacuna porque o documento oficial
    // também não a mostra quando não há código.
    const codigos = [
      _vazio(x.tuss) ? "" : "TUSS " + esc(String(x.tuss).trim()),
      _vazio(x.sigtap) ? "" : "SIGTAP " + esc(String(x.sigtap).trim()),
      _vazio(x.categoria) ? "" : esc(String(x.categoria).trim()),
    ].filter(Boolean).join(" &middot; ");

    const qtd = _vazio(x.quantidade) || String(x.quantidade).trim() === "1"
      ? ""
      : '<span class="exame-item-qtd">' + esc(String(x.quantidade).trim()) + "×</span>";

    return (
      '<div class="exame-item" data-item="' + (i + 1) + '">' +
      '<p class="exame-item-cabeca">' +
      '<span class="exame-item-n">' + (i + 1) + ".</span> " +
      '<b class="exame-item-nome">' + ouMaiusculo(x.nome, "nome do exame") + "</b>" +
      qtd +
      "</p>" +
      (codigos ? '<p class="exame-item-codigos">' + codigos + "</p>" : "") +
      (_vazio(x.preparo)
        ? ""
        : '<p class="exame-item-preparo"><i>Preparo: ' + esc(String(x.preparo).trim()) + "</i></p>") +
      "</div>"
    );
  }

  function _exames(e) {
    const itens = e.exames || [];
    const corpo = itens.length
      ? itens.map(_exame).join("")
      : lacuna("os exames aparecem aqui, numerados, à medida que forem escritos");

    return (
      '<section class="exame-itens" data-bloco="exames">' +
      '<span class="exame-rot">Exames solicitados</span>' +
      '<div class="exame-itens-corpo" data-campo="exames">' + corpo + "</div>" +
      "</section>"
    );
  }

  function _linhaIdent(rotulo, valor, campo, textoLacuna) {
    return (
      '<p class="exame-ident-linha" data-campo="' + campo + '">' +
      '<span class="exame-ident-rot">' + esc(rotulo) + "</span>" +
      '<span class="exame-ident-val">' + valor + "</span></p>"
    );
  }

  function _identificacao(e) {
    let hash;
    if (!_vazio(e.hash)) {
      hash = '<span class="exame-mono">' + esc(e.hash) + "</span>";
    } else if (e.emitido) {
      // Emissão física não tem documento canônico — logo não tem hash. Dizer
      // isso é honesto; deixar a lacuna seria prometer algo que não vem.
      hash = nota("não gerado — emissão física, sem documento canônico");
    } else {
      hash = lacuna("gerado na emissão");
    }

    const prioridade = _rotuloPrioridade(e.prioridade);

    return (
      '<section class="exame-box exame-ident" data-bloco="identificacao">' +
      '<span class="exame-rot">Identificação do documento</span>' +
      _linhaIdent("Data de emissão", ou(e.data_emissao, "gerada na emissão"), "data-emissao") +
      _linhaIdent("Validade", ou(e.data_validade, "gerada na emissão"), "validade") +
      _linhaIdent("Prioridade", prioridade ? esc(prioridade) : lacuna("a definir"), "ident-prioridade") +
      _linhaIdent("Hash SHA-256", hash, "hash") +
      "</section>"
    );
  }

  function _aviso(e) {
    if (_vazio(e.data_validade)) {
      return (
        '<p class="exame-aviso" data-campo="aviso-validade">' +
        "Pedido válido até " + lacuna("data gerada na emissão") +
        ". Apresentar ao prestador de exames dentro do prazo de validade.</p>"
      );
    }
    return (
      '<p class="exame-aviso" data-campo="aviso-validade">Pedido válido até <b>' +
      esc(e.data_validade) +
      "</b>. Apresentar ao prestador de exames dentro do prazo de validade.</p>"
    );
  }

  function _rodape(e) {
    const a = e.assinatura || {};
    const selo = a.tipo === "digital"
      ? '<span class="exame-ass-nota">assinatura registrada na emissão</span>'
      : a.tipo === "fisica"
        ? '<span class="exame-ass-nota exame-ass-fisica">⚠️ requer assinatura à caneta — sem custódia digital</span>'
        : lacuna("a assinatura entra na emissão");

    return (
      '<footer class="exame-rodape" data-bloco="rodape">' +
      '<div class="exame-local">' +
      '<p class="exame-linha" data-campo="local-data">' +
      ou(e.local_data, "município e data") +
      "</p></div>" +
      '<div class="exame-assinatura">' +
      '<div class="exame-risco"></div>' +
      '<p class="exame-linha-forte" data-campo="assinante-nome">' +
      ou(a.nome, "prescritor não identificado") +
      "</p>" +
      '<p class="exame-linha" data-campo="assinante-registro">' +
      ou(a.registro, "registro profissional") +
      "</p>" +
      selo +
      "</div></footer>"
    );
  }

  function _seloCustodia(e) {
    if (!e.emitido) return "";
    const fisica = (e.assinatura || {}).tipo === "fisica";
    // Caixa-alta escrita AQUI, nunca em `text-transform`: o selo é conteúdo do
    // estado emitido e precisa nascer igual nos dois alvos, não parecer igual
    // em um deles.
    const texto = fisica
      ? "🖨️ IMPRESSO · SEM CUSTÓDIA DIGITAL"
      : "✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE";
    const traco = _vazio(e.hash)
      ? ""
      : '<span class="doc-selo-hash exame-selo-hash">sha-256 · ' +
        esc(String(e.hash).slice(0, 24)) + "…</span>";
    return (
      '<div class="doc-selo-custodia exame-carimbo' +
        (fisica ? " doc-selo-fisico exame-carimbo-fisico" : "") +
        '" data-bloco="carimbo">' +
      "<span>" + esc(texto) + "</span>" + traco +
      "</div>"
    );
  }

  /**
   * A FUNÇÃO GERADORA do pedido de exame.
   *
   * @param {object} estado  o documento, como dado
   * @param {string} modo    MODOS.RASCUNHO | MODOS.CARIMBO — só o MEIO
   * @returns {string} HTML do pedido
   */
  function renderPedidoExame(estado, modo) {
    const e = estado || {};
    const m = modo === MODOS.CARIMBO ? MODOS.CARIMBO : MODOS.RASCUNHO;
    return (
      '<article class="doc-folha exame-folha doc-modo-' + m + " exame-modo-" + m +
        (e.emitido ? " doc-emitida exame-emitido" : "") + '">' +
      _cabecalho(e) +
      _prescritor(e) +
      _paciente(e) +
      _indicacao(e) +
      _exames(e) +
      _identificacao(e) +
      _aviso(e) +
      _rodape(e) +
      _seloCustodia(e) +
      "</article>"
    );
  }

  /** Pinta um alvo — o núcleo cuida do invólucro e da tinta; o pedido só diz
   *  o que desenhar. Espelho exato do `Receituario.montar`. */
  function montar(alvo, estado, modo) {
    N.montar(alvo, renderPedidoExame(estado, modo), modo);
  }

  const PedidoExame = {
    MODOS: MODOS,
    render: renderPedidoExame,
    montar: montar,
    textoDoDocumento: N.textoDoDocumento,
    rotuloPrioridade: _rotuloPrioridade,
  };

  window.PedidoExame = PedidoExame;
  window.renderPedidoExame = renderPedidoExame;
})();
