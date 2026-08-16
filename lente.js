/**
 * lente.js — Lente de Auditoria, componente compartilhado
 * =======================================================
 * TICKET-J.11 (`module`) · Adendo §11b do DESPACHO-ENG-011.
 *
 * O QUE É
 * -------
 * A visão NEUTRA de um objeto sanitário: existência e estado, nunca conteúdo
 * clínico nem identificação das partes. Nasceu no rodapé do `index.html` como
 * busca anônima por protocolo/chave — a prova da tese para quem chega ao
 * portal sem login. O J.11 extrai o render para cá para que a mesma lente
 * possa ser aberta a partir de um cartão da carteira do cidadão
 * ("ver rastreabilidade"), sem duplicar o desenho nem a leitura.
 *
 * O QUE ESTE ARQUIVO **NÃO** FAZ
 * ------------------------------
 * Não fala com nenhum endpoint autenticado de conteúdo, não escreve nada e não
 * emite evento. Só lê `/public/*` (neutros por construção, classe `core`,
 * intocados por este ticket) e, quando há sessão, `/circulacao/{chave}` — deste
 * último exibe apenas estado, validade e QUANTOS exames, jamais quem ou quais.
 * Auditoria vê que o objeto existe e em que estado está; operação fica no
 * módulo de origem.
 *
 * CONTRATO
 * --------
 *   LenteAuditoria.consultar(termo, {token})  → Promise<resultado>
 *   LenteAuditoria.cartaoHtml(resultado)      → string (HTML do cartão)
 *   LenteAuditoria.mensagemDeVazio(termo, {token}) → string (por que não achou)
 *   LenteAuditoria.injetarEstilos()           → idempotente; chamado sozinho
 *   LenteAuditoria.esc / .badge / .tonoDoStatus  → utilitários do render
 *
 * `consultar` devolve `{ achou:false }` ou
 * `{ achou:true, familia:'publico'|'circulacao', tipo, dados }`.
 * Quem chama decide onde pendurar o HTML — o componente não conhece o DOM da
 * página hospedeira, só o seu próprio cartão.
 */
(function () {
  'use strict';

  // Tipos de objeto sanitário consultáveis nos endpoints públicos neutros.
  var LENTE_TIPOS = [
    { path: 'prescricoes',        nome: 'Receita (prescrição)', icone: '📄', statusKey: 'status_prescricao' },
    { path: 'exames',             nome: 'Pedido de exame',      icone: '🧪', statusKey: 'status_pedido' },
    { path: 'atestados',          nome: 'Atestado',             icone: '🩺', statusKey: 'status' },
    { path: 'laudos',             nome: 'Laudo',                icone: '📋', statusKey: 'status_laudo' },
    { path: 'encaminhamentos',    nome: 'Encaminhamento',       icone: '↗️', statusKey: 'status_encaminhamento' },
    { path: 'contrarreferencias', nome: 'Contrarreferência',    icone: '↩️', statusKey: 'status_contrarreferencia' },
  ];

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Tom do badge por família de estado (contrato de estados, CLAUDE.md §5a/§5b).
  function tonoDoStatus(status) {
    var s = String(status || '').toLowerCase();
    if (/cancel|desmarc|expira|recusad|revogad|indefer/.test(s)) return 'tono-vermelho';
    if (/aguard|pendente|proposta|rascunho|selecionado/.test(s)) return 'tono-amarelo';
    if (/confirm|dispens|realizad|assinado|entregue|conclu|vigente|transfer/.test(s)) return 'tono-verde';
    if (/emit|enviado|custodia|registrado|ativo/.test(s)) return 'tono-azul';
    return '';
  }

  function badge(status) {
    return '<span class="lente-badge ' + tonoDoStatus(status) + '">' + esc(status || '—') + '</span>';
  }

  // ── Estilos ───────────────────────────────────────────────────────────────
  // Viajam com o componente: uma tela que inclui `lente.js` ganha o cartão já
  // desenhado, sem copiar CSS. Idempotente — a segunda chamada não faz nada.
  var _ESTILOS = ''
    + '.lente-card { background:#fff; border:1.5px solid #bfdbfe; border-radius:10px; padding:16px 20px; margin-top:12px; }'
    + '.lente-card-head { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }'
    + '.lente-tipo { font-size:14px; font-weight:700; color:#0f172a; }'
    + '.lente-badge { display:inline-block; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; padding:3px 10px; border-radius:999px; background:#f1f5f9; color:#475569; }'
    + '.lente-badge.tono-azul    { background:#dbeafe; color:#1e40af; }'
    + '.lente-badge.tono-verde   { background:#d1fae5; color:#065f46; }'
    + '.lente-badge.tono-amarelo { background:#fef9c3; color:#854d0e; }'
    + '.lente-badge.tono-vermelho{ background:#fee2e2; color:#991b1b; }'
    + '.lente-chave-display { font-family:\'Courier New\',monospace; font-size:15px; font-weight:700; letter-spacing:2px; color:#1e3a8a; padding:8px 10px; background:#eff6ff; border:1px dashed #93c5fd; border-radius:6px; margin:10px 0; word-break:break-all; }'
    + '.lente-meta { font-size:12px; color:#64748b; line-height:1.7; }'
    + '.lente-itens { margin-top:10px; font-size:13px; color:#334155; }'
    + '.lente-item-row { display:flex; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid #f1f5f9; }'
    + '.lente-item-row:last-child { border-bottom:none; }'
    + '.lente-nota { font-size:11px; color:#1e40af; background:#dbeafe; border-radius:4px; padding:6px 10px; margin-top:12px; }'
    + '.lente-nota a { color:#1e3a8a; font-weight:700; text-decoration:none; }'
    + '.lente-nota a:hover { text-decoration:underline; }';

  function injetarEstilos() {
    if (document.getElementById('lente-estilos-compartilhados')) return;
    var st = document.createElement('style');
    st.id = 'lente-estilos-compartilhados';
    st.textContent = _ESTILOS;
    (document.head || document.documentElement).appendChild(st);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  // Cartão neutro para os endpoints /public/* — o payload já nasce neutro no
  // backend (sem clínica, sem identidade); aqui só apresentamos.
  function _cartaoPublico(tipo, dados) {
    var html = '<div class="lente-card">'
      + '<div class="lente-card-head">'
      +   '<span class="lente-tipo">' + tipo.icone + ' ' + esc(tipo.nome) + '</span>'
      +   badge(dados[tipo.statusKey])
      + '</div>'
      + '<div class="lente-chave-display">' + esc(dados.protocolo) + '</div>'
      + '<div class="lente-meta">Tipo de emissão: <strong>' + esc(dados.tipo_emissao || '—') + '</strong></div>';

    if (tipo.path === 'atestados') {
      html += '<div class="lente-meta">Assinado: <strong>' + (dados.assinado ? 'sim' : 'não') + '</strong>'
        + (dados.vigente === null || dados.vigente === undefined
           ? ''
           : ' · Vigente: <strong>' + (dados.vigente ? 'sim' : 'não') + '</strong>')
        + '</div>';
    }

    if (Array.isArray(dados.itens) && dados.itens.length) {
      html += '<div class="lente-itens">';
      dados.itens.forEach(function (it) {
        html += '<div class="lente-item-row"><span>Item ' + esc(it.ordem) + '</span>'
          + badge(it.status_item) + '</div>';
      });
      html += '</div>';
    }

    html += '<div class="lente-nota">Visão neutra de auditoria — existência e estado do objeto, '
      + 'sem conteúdo clínico nem identificação das partes.</div></div>';
    return html;
  }

  // Cartão neutro para circulação diagnóstica. O endpoint autenticado retorna
  // paciente/prescritor/exames — a lente NÃO os exibe: auditoria vê estado,
  // validade e tamanho do conjunto; o restante é operação, e operação fica no
  // módulo Clínica/Laboratório.
  function _cartaoCirculacao(circ) {
    var nItens = Array.isArray(circ.itens) ? circ.itens.length : 0;
    var validade = circ.validade ? String(circ.validade).slice(0, 10) : '—';
    return '<div class="lente-card">'
      + '<div class="lente-card-head">'
      +   '<span class="lente-tipo">🔬 Circulação diagnóstica</span>'
      +   badge(circ.status)
      + '</div>'
      + '<div class="lente-chave-display">' + esc(circ.chave_circulacao) + '</div>'
      + '<div class="lente-meta">Validade da chave: <strong>' + esc(validade) + '</strong>'
      + ' · Exames nesta circulação: <strong>' + nItens + '</strong></div>'
      + '<div class="lente-nota">Visão neutra de auditoria. Detalhes clínicos e operação '
      + '(proposta, confirmação, realização) no módulo '
      + '<a href="clinica.html">Clínica/Laboratório →</a></div></div>';
  }

  function cartaoHtml(resultado) {
    if (!resultado || !resultado.achou) return '';
    injetarEstilos();
    return resultado.familia === 'circulacao'
      ? _cartaoCirculacao(resultado.dados)
      : _cartaoPublico(resultado.tipo, resultado.dados);
  }

  // ── Leitura ───────────────────────────────────────────────────────────────

  // Chave de circulação diagnóstica: hex curto, sem hífen (ex: A3F1C2B4E5D6).
  // Protocolos (UUID com hífen) caem direto nos endpoints públicos.
  function _pareceCirculacao(termo) {
    return /^[0-9A-F]{8,16}$/.test(String(termo).toUpperCase()) && String(termo).indexOf('-') === -1;
  }

  function _base() {
    return (typeof BACKEND_URL !== 'undefined') ? BACKEND_URL : '';
  }

  async function consultar(termo, opcoes) {
    var t = String(termo || '').trim();
    var token = (opcoes && opcoes.token) || null;

    // 1) Circulação diagnóstica (autenticada) — só com sessão ativa.
    if (_pareceCirculacao(t) && token) {
      try {
        var rc = await fetch(_base() + '/circulacao/' + encodeURIComponent(t.toUpperCase()), {
          headers: { 'Authorization': 'Bearer ' + token },
        });
        if (rc.ok) return { achou: true, familia: 'circulacao', dados: await rc.json() };
      } catch (_) { /* rede — segue para os públicos */ }
    }

    // 2) Objetos sanitários via endpoints públicos neutros, na ordem.
    for (var i = 0; i < LENTE_TIPOS.length; i++) {
      var tipo = LENTE_TIPOS[i];
      try {
        var rp = await fetch(_base() + '/public/' + tipo.path + '/' + encodeURIComponent(t));
        if (rp.ok) return { achou: true, familia: 'publico', tipo: tipo, dados: await rp.json() };
      } catch (_) { /* rede — tenta o próximo tipo */ }
    }

    return { achou: false };
  }

  // Nada encontrado — feedback com o próximo passo (R4: nunca calar).
  function mensagemDeVazio(termo, opcoes) {
    var t = String(termo || '').trim();
    var token = (opcoes && opcoes.token) || null;
    if (_pareceCirculacao(t) && !token) {
      return 'Formato de chave de circulação diagnóstica, mas nenhum objeto público '
        + 'respondeu por ela. A circulação diagnóstica detalhada exige um perfil ativo — '
        + 'entre pelo card da Clínica/Laboratório e consulte lá.';
    }
    if (_pareceCirculacao(t)) {
      return 'Nenhuma circulação ou objeto sanitário encontrado com "' + t.toUpperCase() + '". '
        + 'Confira a digitação ou consulte no módulo de origem.';
    }
    return 'Nenhum objeto sanitário encontrado com este protocolo. '
      + 'Confira a digitação — o protocolo é o identificador completo do documento.';
  }

  window.LenteAuditoria = {
    TIPOS:           LENTE_TIPOS,
    consultar:       consultar,
    cartaoHtml:      cartaoHtml,
    mensagemDeVazio: mensagemDeVazio,
    injetarEstilos:  injetarEstilos,
    esc:             esc,
    badge:           badge,
    tonoDoStatus:    tonoDoStatus,
  };
})();
