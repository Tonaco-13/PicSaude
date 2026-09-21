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

  const MODOS = { RASCUNHO: "rascunho", CARIMBO: "carimbo" };

  /** Quanto tempo a tinta fica acesa na região que acabou de mudar. */
  const _TINTA_MS = 700;

  function esc(v) {
    return String(v === null || v === undefined ? "" : v).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function _vazio(v) {
    return String(v === null || v === undefined ? "" : v).trim() === "";
  }

  /** O espaço pontilhado — o branco do papel esperando a caneta. */
  function lacuna(texto) {
    return '<span class="rec-lacuna">' + esc(texto) + "</span>";
  }

  /** Valor escapado, ou a lacuna correspondente quando o campo está vazio. */
  function ou(valor, textoDaLacuna) {
    return _vazio(valor) ? lacuna(textoDaLacuna) : esc(String(valor).trim());
  }

  /** Como `ou`, mas caixa-alta — o nome do fármaco, na régua do receituário.
   *
   *  A caixa-alta é feita AQUI e não em CSS de propósito: `text-transform`
   *  pintaria a tela sem tocar o texto, e o W ≡ Y compara TEXTO. Dado passa
   *  pela função; só o cromo (rótulos, sombras) fica para a folha de estilo.
   *  Assim não há como um modo exibir uma coisa e o outro exibir outra. */
  function ouMaiusculo(valor, textoDaLacuna) {
    return _vazio(valor) ? lacuna(textoDaLacuna) : esc(String(valor).trim().toUpperCase());
  }

  /** Nota do documento sobre si mesmo (não é lacuna: é fato declarado). */
  function nota(texto) {
    return '<span class="rec-nota">' + esc(texto) + "</span>";
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
      " " + ou(m.unidade, "unidade") +
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
    const texto = fisica
      ? "🖨️ Impressa · sem custódia digital"
      : "✓ Transmitida · custódia ao paciente";
    // No carimbo o hash vai ABREVIADO: ele é a marca de que existe integridade,
    // não o lugar de conferi-la — o valor inteiro está no cabeçalho, onde se
    // copia e se compara. Carimbo de borracha não cabe 64 caracteres.
    const traco = _vazio(e.hash)
      ? ""
      : '<span class="rec-carimbo-hash">sha-256 ' + esc(String(e.hash).slice(0, 24)) + "…</span>";
    return (
      '<div class="rec-carimbo' + (fisica ? " rec-carimbo-fisica" : "") + '" data-bloco="carimbo">' +
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
      '<article class="rec-folha rec-modo-' + m + (e.emitido ? " rec-emitida" : "") + '">' +
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

  /**
   * Pinta um alvo com o documento — e acende a TINTA na região que mudou.
   *
   * A tinta é gesto de TELA: só no modo rascunho. No `#print-area` ela seria
   * ruído num documento que ninguém está vendo se formar.
   *
   * O invólucro (`#folha-viva`, `#print-area`) é preservado — trocamos só o
   * miolo. É o que permite ao AC4 exigir que o carimbo caia na MESMA folha
   * que estava à vista, e a uma guarda provar que a folha não foi substituída.
   */
  function montar(alvo, estado, modo) {
    const el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    if (!el) return;

    const antes = {};
    el.querySelectorAll("[data-bloco]").forEach((b) => {
      antes[b.getAttribute("data-bloco")] = b.innerHTML;
    });

    el.innerHTML = renderReceituario(estado, modo);

    if (modo === MODOS.CARIMBO) return;

    el.querySelectorAll("[data-bloco]").forEach((b) => {
      const chave = b.getAttribute("data-bloco");
      if (antes[chave] === undefined || antes[chave] === b.innerHTML) return;
      b.classList.add("rec-tinta");
      setTimeout(() => b.classList.remove("rec-tinta"), _TINTA_MS);
    });
  }

  /**
   * O texto do documento, normalizado — a definição ÚNICA de "equivalente".
   *
   * Existe aqui, e não copiada dentro de cada guarda, porque W ≡ Y só vale se
   * os dois lados forem lidos pela mesma régua (a lição do comentário que
   * promete fonte única: duplicação com assert ainda é duplicação).
   */
  function textoDoDocumento(alvo) {
    const el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    if (!el) return "";
    return String(el.textContent || "").replace(/\s+/g, " ").trim();
  }

  const Receituario = {
    MODOS: MODOS,
    render: renderReceituario,
    montar: montar,
    textoDoDocumento: textoDoDocumento,
  };

  window.Receituario = Receituario;
  // O nome que o despacho nomeia — uma função geradora, dois alvos.
  window.renderReceituario = renderReceituario;
})();
