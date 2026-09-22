/* ==========================================================================
 * receituario.js — O RECEITUÁRIO: **uma função geradora, dois alvos**.
 *
 * ENG-018 / DESENHO-RECEITA-VIVA.md §3 — a sobreposição do arquiteto.
 *
 * POR QUE ESTE ARQUIVO EXISTE
 * ---------------------------
 * A proposta original era duplicar o template: uma folha viva ao lado do
 * formulário, separada do `#print-area`. O arquiteto sobrepôs, e a razão é a
 * lição mais repetida da casa — *mesma língua por construção, não por
 * disciplina*: dois templates do MESMO documento vão derivar, e quando
 * derivarem o "zero surpresa no pós-emissão" vira mentira gradual, que é a
 * pior espécie. O WYSIWYG só é promessa se o W e o Y nascem da mesma função.
 *
 * Então aqui mora UMA função — `renderReceituario(estado, modo)` — e ela
 * alimenta os DOIS alvos:
 *
 *   folha viva (`#folha-viva`)  → modo 'rascunho'  — a receita se escrevendo
 *   documento  (`#print-area`)  → modo 'carimbo'   — o que sai na impressão
 *
 * O QUE O `modo` GOVERNA — E O QUE ELE **NÃO** GOVERNA
 * ---------------------------------------------------
 * Governa apenas o MEIO: a classe do invólucro, e daí a tipografia e o
 * cromo de tela (sombra, papel, grude) contra a tipografia de impressão.
 *
 * NÃO governa conteúdo. Nenhum campo aparece num modo e some no outro. Quem
 * decide o que está escrito é o `estado`, e só ele — inclusive as lacunas
 * (campo vazio) e o carimbo (`estado.emitido`). É isso que torna o W ≡ Y um
 * invariante verificável, e não uma intenção: mesmo estado, mesmo documento,
 * nos dois alvos. Sabotar um alvo reprova a guarda.
 *
 * AS LACUNAS
 * ----------
 * Campo vazio não some da folha: vira **espaço pontilhado** — o branco do
 * papel esperando a caneta. O prescritor vê o que falta sem validação
 * gritando. O texto da lacuna é vocabulário do DOCUMENTO ("nome do
 * paciente"), nunca o placeholder do formulário ("Ex: 45"): placeholder de
 * formulário que vaza para a folha como texto definitivo seria a folha
 * mentindo sobre o que o cidadão vai receber.
 *
 * O QUE ESTE ARQUIVO **NÃO** FAZ
 * ------------------------------
 * Não lê o DOM do formulário, não fala com endpoint nenhum, não conhece
 * `medicoLogado` nem `localStorage`, não decide quando repintar. Recebe um
 * objeto e devolve HTML. Quem monta o estado é a página hospedeira — é o que
 * permite que exame e atestado, em ondas próprias, sejam REMONTAGENS deste
 * mesmo padrão em vez de cópias dele.
 *
 * CONTRATO
 * --------
 *   renderReceituario(estado, modo)          → string (HTML do documento)
 *   Receituario.render                       → a MESMA função (alias)
 *   Receituario.montar(alvo, estado, modo)   → pinta um alvo (+ tinta)
 *   Receituario.textoDoDocumento(el)         → texto normalizado (W ≡ Y)
 *   Receituario.MODOS                        → { RASCUNHO, CARIMBO }
 * ========================================================================== */

(function () {
  "use strict";

  // ENG-022 — a receita passa a CONSUMIR o núcleo. O que saiu daqui (lacuna,
  // esc, tinta por `data-bloco`, o contrato W ≡ Y, o FAB) não mudou de
  // semântica: mudou de casa, para que o pedido de exame use as MESMAS peças
  // em vez de peças parecidas. O que fica é a ANATOMIA do receituário — e ela
  // não sobe ao núcleo por decisão do arquiteto: "duas anatomias numa função
  // só é a dupla posse pela porta dos fundos".
  const N = window.DocumentoNucleo;

  const MODOS = N.MODOS;
  const esc = N.esc;

  // `rec` é o gancho nomeado deste documento: as lacunas saem como
  // `class="doc-lacuna rec-lacuna"` — estilo no núcleo, identidade aqui.
  const { lacuna, ou, ouMaiusculo, nota } = N.vocabulario("rec");

  // Os blocos anatômicos abaixo perguntam "este campo está vazio?" o tempo
  // todo — o apelido mantém a leitura deles, com a resposta vindo do núcleo.
  const _vazio = N.vazio;

  /** Plural da unidade — "30 comprimido" não é português (ENG-020 §1.1).
   *
   *  Achado em uso real. A correção mora AQUI, e é a martelada ② pagando o
   *  próprio custo: uma função consertada cura as três superfícies de uma vez
   *  — folha viva, documento impresso e 2ª via —, porque as três são a mesma
   *  função. Com dois templates, seriam dois consertos e uma data futura em
   *  que um deles voltaria a dizer "30 comprimido".
   *
   *  Regra do português: acrescenta-se -s (todas as unidades do formulário
   *  terminam em vogal ou -e). A exceção é o composto, em que quem flexiona é
   *  o primeiro núcleo: frasco-ampola → frascos-ampola.
   *
   *  Quantidade ausente ou não-numérica mantém o singular: a folha não
   *  adivinha o número para depois concordar com ele. */
  const _PLURAL_COMPOSTO = { "frasco-ampola": "frascos-ampola" };

  function pluralizarUnidade(unidade, quantidade) {
    const u = String(unidade === null || unidade === undefined ? "" : unidade).trim();
    if (!u) return "";
    const q = String(quantidade === null || quantidade === undefined ? "" : quantidade).trim();
    // `Number("")` é 0, e 0 pluralizaria — mas campo VAZIO não é quantidade
    // zero: é quantidade ainda não escrita. A folha não concorda com um
    // número que o prescritor não digitou.
    if (!q) return u;
    const n = Number(q.replace(",", "."));
    if (!Number.isFinite(n) || n === 1) return u;
    return _PLURAL_COMPOSTO[u.toLowerCase()] || u + "s";
  }

  // ── blocos ───────────────────────────────────────────────────────────────
  //
  // Cada região do documento é um `[data-bloco]`. É por eles que a TINTA sabe
  // o que mudou (ver `montar`), e é por eles que uma guarda consegue apontar
  // "esta região divergiu" em vez de "o documento divergiu".

  function _cabecalho(e) {
    const proto = _vazio(e.protocolo)
      ? lacuna("gerado na emissão")
      : '<b class="rec-mono">' + esc(e.protocolo) + "</b>";

    let hash;
    if (!_vazio(e.hash)) {
      hash = '<span class="rec-mono">' + esc(e.hash) + "</span>";
    } else if (e.emitido) {
      // Emissão física não tem documento canônico — logo não tem hash. Dizer
      // isso é honesto; deixar a lacuna seria prometer algo que não vem.
      hash = nota("não gerado — emissão física, sem documento canônico");
    } else {
      hash = lacuna("gerado na emissão");
    }

    const aviso = _vazio(e.protocolo_aviso)
      ? ""
      : '<p class="rec-proto-aviso">' + esc(e.protocolo_aviso) + "</p>";

    return (
      '<header class="rec-cabecalho" data-bloco="cabecalho">' +
      "<h2>Receituário Médico</h2>" +
      '<p class="rec-sub">PicSaúde · Transferência eletrônica de dados</p>' +
      '<p class="rec-proto" data-campo="protocolo">Protocolo: ' + proto + "</p>" +
      '<p class="rec-proto rec-proto-hash" data-campo="hash">Hash SHA-256: ' + hash + "</p>" +
      aviso +
      "</header>"
    );
  }

  function _emitente(e) {
    const m = e.emitente || {};
    return (
      '<section class="rec-box" data-bloco="emitente">' +
      '<span class="rec-rot">Identificação do emitente</span>' +
      '<p class="rec-linha-forte" data-campo="emitente-nome">' +
      ou(m.nome, "prescritor não identificado") +
      "</p>" +
      '<p class="rec-linha" data-campo="emitente-registros">' +
      ou(m.registros, "registro profissional") +
      "</p>" +
      '<p class="rec-linha" data-campo="emitente-contato">Endereço: ' +
      ou(m.endereco, "endereço do consultório") +
      " | CEP: " +
      ou(m.cep, "cep") +
      " | Tel: " +
      ou(m.telefone, "telefone") +
      "</p>" +
      "</section>"
    );
  }

  function _paciente(e) {
    const p = e.paciente || {};
    return (
      '<section class="rec-box" data-bloco="paciente">' +
      '<span class="rec-rot">Identificação do paciente</span>' +
      '<p class="rec-linha-forte" data-campo="paciente-nome">' +
      ou(p.nome, "nome do paciente") +
      ' <span class="rec-idade">· ' +
      ou(p.idade, "idade") +
      " anos</span></p>" +
      '<p class="rec-linha" data-campo="paciente-chave">CPF / CNI: ' +
      ou(p.chave, "obrigatório para a emissão digital") +
      "</p>" +
      '<p class="rec-linha" data-campo="paciente-telefone">Tel: ' +
      ou(p.telefone, "telefone") +
      "</p>" +
      '<p class="rec-linha" data-campo="paciente-endereco">Endereço: ' +
      ou(p.endereco, "logradouro, número e bairro") +
      " | CEP: " +
      ou(p.cep, "cep") +
      " | " +
      ou(p.cidade_uf, "cidade e UF") +
      "</p>" +
      "</section>"
    );
  }

  function _indicacao(e) {
    const cids = (e.cids || [])
      .map(
        (c) =>
          '<span class="rec-selo-cid" data-cid="' +
          esc(c.codigo) +
          '"><b>CID-10 ' +
          esc(c.codigo) +
          "</b>" +
          (_vazio(c.descricao) ? "" : "<span>" + esc(c.descricao) + "</span>") +
          "</span>"
      )
      .join("");

    return (
      '<section class="rec-indicacao" data-bloco="indicacao">' +
      '<span class="rec-rot rec-rot-clinica">Indicação clínica</span>' +
      '<p class="rec-linha" data-campo="indicacao">' +
      ou(e.indicacao, "opcional — aparece se o prescritor escrever") +
      "</p>" +
      '<div class="rec-selos" data-campo="cids">' +
      (cids || lacuna("nenhum CID escolhido")) +
      "</div>" +
      "</section>"
    );
  }

  function _item(m, i) {
    const apres = _vazio(m.apresentacao)
      ? ""
      : " &middot; " + esc(String(m.apresentacao).trim());

    return (
      '<div class="rec-item" data-item="' + (i + 1) + '">' +
      '<p class="rec-item-cabeca">' +
      '<span class="rec-item-n">' + (i + 1) + ".</span> " +
      '<b class="rec-item-nome">' + ouMaiusculo(m.nome, "princípio ativo") + "</b>" +
      " — " + ou(m.concentracao, "concentração") +
      " &middot; " + ou(m.quantidade, "quantidade") +
      " " + ou(pluralizarUnidade(m.unidade, m.quantidade), "unidade") +
      '<span class="rec-item-validade">Validade: ' + ou(m.validade, "prazo") + "</span>" +
      "</p>" +
      '<p class="rec-item-forma">Forma: ' + ou(m.forma, "forma farmacêutica") + apres + "</p>" +
      '<p class="rec-item-uso"><i>' + ou(m.posologia, "instruções de uso (posologia)") + "</i></p>" +
      "</div>"
    );
  }

  function _itens(e) {
    const itens = e.itens || [];
    const corpo = itens.length
      ? itens.map(_item).join("")
      : lacuna("os fármacos aparecem aqui, numerados, à medida que forem escritos");

    return (
      '<section class="rec-itens" data-bloco="itens">' +
      '<span class="rec-rot">Prescrição terapêutica</span>' +
      '<div class="rec-itens-corpo" data-campo="itens">' + corpo + "</div>" +
      "</section>"
    );
  }

  function _selo(e) {
    const a = e.assinatura || {};
    if (a.tipo === "digital") {
      return (
        '<div class="rec-selo rec-selo-digital" data-campo="assinatura">' +
        "<b>Documento emitido com assinatura digital</b>" +
        (_vazio(a.nivel) ? "" : "<span>" + esc(a.nivel) + "</span>") +
        (_vazio(a.modo) ? "" : "<span>Assinatura: " + esc(a.modo) + "</span>") +
        "</div>"
      );
    }
    if (a.tipo === "fisica") {
      return (
        '<div class="rec-selo rec-selo-fisica" data-campo="assinatura">' +
        "<b>⚠️ Emissão física — sem custódia digital</b>" +
        "<span>Requer assinatura à caneta e carimbo físico para ter validade. " +
        "Sem protocolo rastreável no PicSaúde.</span>" +
        "</div>"
      );
    }
    return (
      '<div class="rec-selo rec-selo-pendente" data-campo="assinatura">' +
      lacuna("a assinatura entra na emissão") +
      "</div>"
    );
  }

  function _rodape(e) {
    const a = e.assinatura || {};
    return (
      '<footer class="rec-rodape" data-bloco="rodape">' +
      '<div class="rec-local">' +
      '<span class="rec-rot">Local e data da emissão</span>' +
      '<p class="rec-linha" data-campo="local-data">' +
      ou(e.local_data, "município e data") +
      "</p>" +
      "</div>" +
      '<div class="rec-assinatura">' +
      '<div class="rec-risco"></div>' +
      '<p class="rec-linha-forte" data-campo="assinante-nome">' +
      ou(a.nome, "prescritor não identificado") +
      "</p>" +
      '<p class="rec-linha" data-campo="assinante-registro">' +
      ou(a.registro, "registro profissional") +
      "</p>" +
      _selo(e) +
      "</div>" +
      "</footer>"
    );
  }

  function _carimbo(e) {
    if (!e.emitido) return "";
    const fisica = (e.assinatura || {}).tipo === "fisica";
    // Caixa-alta escrita AQUI, nunca em `text-transform` (a lei do ENG-018,
    // reafirmada no §2 do ENG-020): CSS pinta a tela sem tocar o texto, e o
    // W ≡ Y compara TEXTO. O selo é conteúdo do estado emitido — precisa
    // nascer igual nos dois alvos, não parecer igual em um deles.
    const texto = fisica
      ? "🖨️ IMPRESSA · SEM CUSTÓDIA DIGITAL"
      : "✓ TRANSMITIDA · CUSTÓDIA AO PACIENTE";
    // No carimbo o hash vai ABREVIADO: ele é a marca de que existe integridade,
    // não o lugar de conferi-la — o valor inteiro está no cabeçalho, onde se
    // copia e se compara. Carimbo de borracha não cabe 64 caracteres.
    const traco = _vazio(e.hash)
      ? ""
      : '<span class="doc-selo-hash rec-carimbo-hash">sha-256 ' +
        esc(String(e.hash).slice(0, 24)) + "…</span>";
    return (
      '<div class="doc-selo-custodia rec-carimbo' +
        (fisica ? " doc-selo-fisico rec-carimbo-fisica" : "") + '" data-bloco="carimbo">' +
      "<span>" + esc(texto) + "</span>" + traco +
      "</div>"
    );
  }

  /**
   * A FUNÇÃO GERADORA — a peça central do ENG-018.
   *
   * @param {object} estado  o documento, como dado (ver o contrato no topo)
   * @param {string} modo    MODOS.RASCUNHO | MODOS.CARIMBO — só o MEIO
   * @returns {string} HTML do receituário
   */
  function renderReceituario(estado, modo) {
    const e = estado || {};
    const m = modo === MODOS.CARIMBO ? MODOS.CARIMBO : MODOS.RASCUNHO;
    return (
      '<article class="doc-folha rec-folha doc-modo-' + m + " rec-modo-" + m +
        (e.emitido ? " doc-emitida rec-emitida" : "") + '">' +
      _cabecalho(e) +
      _emitente(e) +
      _paciente(e) +
      _indicacao(e) +
      _itens(e) +
      _rodape(e) +
      _carimbo(e) +
      "</article>"
    );
  }

  /** Pinta um alvo — o núcleo cuida do invólucro e da tinta; a receita só
   *  diz o que desenhar. Assinatura pública INTOCADA. */
  function montar(alvo, estado, modo) {
    N.montar(alvo, renderReceituario(estado, modo), modo);
  }

  const Receituario = {
    MODOS: MODOS,
    render: renderReceituario,
    pluralizarUnidade: pluralizarUnidade,
    montar: montar,
    textoDoDocumento: N.textoDoDocumento,
  };

  window.Receituario = Receituario;
  // O nome que o despacho nomeia — uma função geradora, dois alvos.
  window.renderReceituario = renderReceituario;
})();
