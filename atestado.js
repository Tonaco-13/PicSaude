/* ==========================================================================
 * atestado.js — O ATESTADO: uma função geradora, dois alvos.
 *
 * ENG-024 · lei: `docs/tickets/DESENHO-ATESTADO-VIVO.md`.
 *
 * O DEGENERADO — e por que ele é a prova de verdade da família
 * -------------------------------------------------------------
 * A receita tem itens. O pedido de exame tem itens. O encaminhamento tem
 * itens. O atestado não tem NADA disso: é monolítico — 18 campos de
 * formulário que se fecham numa ÚNICA FRASE corrida que o CFM manda existir.
 * Não há lista onde esconder a costura; ou a frase fecha, ou ela não fecha.
 *
 * Por isso a lacuna aqui mora DENTRO da sentença ("Atesto, para fins ____,
 * que ____ esteve sob cuidados médicos…"), e não num campo. O modo inline
 * entrou no `documento-nucleo.js` no #273 pensando exatamente neste objeto,
 * estreou no encaminhamento (#274) e chega aqui pronto — que era o ponto de
 * pô-lo no contrato antes de existir quem o pedisse.
 *
 * ⚠️ O SEGUNDO CONSTRUTOR DA FRASE — a dívida, declarada
 * -------------------------------------------------------
 * `corpoAtestado()` abaixo é uma TRANSCRIÇÃO de
 * `backend/app/domain/texto_atestado.py::corpo_atestado`. São dois
 * construtores da mesma frase, e este repositório já pagou por isso uma vez:
 * o rascunho e o PDF divergiam, e o profissional conferia um texto e assinava
 * outro — *"um espelho que mostra outra pessoa é pior que nenhum espelho"*.
 * O `_registroAtestadoDisplay()` foi removido do `prescritor.html` pela mesma
 * razão.
 *
 * O que impede a divergência aqui NÃO é disciplina: é a guarda
 * `test_eng024_atestado_vivo.py::TestFolhaEquivaleAoDominio`, que compara o
 * corpo desta função com o `corpo_documento` que o servidor devolve, sobre
 * uma MATRIZ de estados (os dois ramos × as quatro cláusulas clínicas ×
 * conselho × horário × observação). A cadeia fica: PDF ≡ rascunho
 * (`test_atestado_espelho.py`) ≡ folha (esta guarda) — três renderizações,
 * duas guardas, uma fonte.
 *
 * Absorver a frase do servidor (e apagar este construtor) é outro ticket,
 * declarado no §4 do despacho. Enquanto não vier, a guarda é o que segura.
 *
 * O TÍTULO E OS ADJETIVOS MUDAM COM O CONSELHO
 * ---------------------------------------------
 * "ATESTADO MÉDICO"/"cuidados médicos" (CFM) viram "ATESTADO
 * ODONTOLÓGICO"/"cuidados odontológicos" (CFO). O documento inteiro muda —
 * título, frase e sigla do registro — porque quem assina muda.
 *
 * CONTRATO (espelho dos três irmãos, por construção)
 * ---------------------------------------------------
 *   renderAtestado(estado, modo)          → string (HTML do documento)
 *   Atestado.render                       → a MESMA função (alias)
 *   Atestado.montar(alvo, estado, modo)   → pinta um alvo (+ tinta)
 *   Atestado.textoDoDocumento(el)         → texto normalizado (W ≡ Y)
 *   Atestado.corpoAtestado(estado)        → só o corpo, sem marcação (guarda)
 *   Atestado.MODOS                        → { RASCUNHO, CARIMBO }
 * ========================================================================== */

(function () {
  "use strict";

  const N = window.DocumentoNucleo;

  const MODOS = N.MODOS;
  const esc = N.esc;
  const _vazio = N.vazio;

  const { lacuna, ou, ouMaiusculo, nota } = N.vocabulario("at");

  /** O conselho decide o documento inteiro — espelho de
   *  `domain/conselho_profissional.py`. */
  const CONSELHOS = {
    CFM: {
      sigla: "CRM",
      titulo: "ATESTADO MÉDICO",
      adjetivoCuidados: "médicos",
      adjetivoAtendimento: "médico",
    },
    CFO: {
      sigla: "CRO",
      titulo: "ATESTADO ODONTOLÓGICO",
      adjetivoCuidados: "odontológicos",
      adjetivoAtendimento: "odontológico",
    },
  };

  function conselhoDe(id) {
    return CONSELHOS[String(id || "").trim().toUpperCase()] || CONSELHOS.CFM;
  }

  // ── os trechos da frase — transcrição de `texto_atestado.py` ─────────────

  /** `periodo_horario` — nenhuma combinação inventa a hora que falta. */
  function periodoHorario(horaInicio, horaFim) {
    const ini = String(horaInicio || "").trim();
    const fim = String(horaFim || "").trim();
    if (ini && fim) return `, no período das ${ini} às ${fim}`;
    if (ini) return `, a partir das ${ini}`;
    if (fim) return `, até as ${fim}`;
    return "";
  }

  /** `clausula_clinica` — os QUATRO casos existem para que a pontuação feche
   *  em todos eles. O CFM admite atestado sem CID: o diagnóstico só entra com
   *  anuência do paciente. */
  function clausulaClinica(indicacao, cid) {
    const ind = String(indicacao || "").trim();
    const codigo = String(cid || "").trim();
    if (ind && codigo) return `, em razão de quadro clínico compatível com ${ind} (CID ${codigo})`;
    if (ind) return `, em razão de quadro clínico compatível com ${ind}`;
    if (codigo) return ` (CID ${codigo})`;
    return "";
  }

  /** Data ISO → dd/mm/aaaa. Entrada inválida volta como veio: um atestado não
   *  deve falhar de renderizar por causa de um campo de data. */
  function dataBr(iso) {
    const v = String(iso || "").trim();
    if (!v) return "";
    const m = v.slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : v;
  }

  /**
   * O CORPO — a frase que o CFM manda fechar.
   *
   * Devolve `{ texto, html }`: o texto puro é o que a guarda compara com o
   * domínio; o HTML carrega as ênfases e as lacunas INLINE. Os dois nascem da
   * mesma passagem, para não haver como um andar sem o outro.
   *
   * Quando `paraGuarda` é true, as lacunas somem e cada campo vazio vira
   * string vazia — é assim que o servidor monta a frase com campos ausentes, e
   * é essa a fatia comparável.
   */
  function corpoAtestado(estado, paraGuarda) {
    const e = estado || {};
    const c = conselhoDe(e.conselho);
    const inline = { inline: true };

    const dias = parseInt(String(e.dias_afastamento || "").trim(), 10);
    const temAfastamento = Number.isFinite(dias) && dias > 0;

    const clausula = clausulaClinica(e.indicacao_clinica, e.codigo_cid);
    const periodo = periodoHorario(e.hora_inicio, e.hora_fim);
    const dataFmt = dataBr(e.data_documento);

    // Cada peça variável tem um par (texto puro, html) — o html pode trazer
    // lacuna onde o texto puro traz vazio.
    const finalidade = {
      txt: String(e.finalidade || "").trim(),
      html: _vazio(e.finalidade)
        ? lacuna("finalidade", inline)
        : "<strong>" + esc(String(e.finalidade).trim()) + "</strong>",
    };
    const paciente = {
      txt: String(e.nome_paciente || "").trim(),
      html: _vazio(e.nome_paciente)
        ? lacuna("nome do paciente", inline)
        : "<strong>" + esc(String(e.nome_paciente).trim()) + "</strong>",
    };
    const data = {
      txt: dataFmt || "",
      html: dataFmt ? esc(dataFmt) : lacuna("data do documento", inline),
    };

    let txt, html;
    if (temAfastamento) {
      const meio =
        ` esteve sob cuidados ${c.adjetivoCuidados} na data de ` +
        `${data.txt}${periodo}${clausula}, devendo permanecer afastado(a) ` +
        "de suas atividades habituais por ";
      const meioHtml =
        ` esteve sob cuidados ${esc(c.adjetivoCuidados)} na data de ` +
        `${data.html}${esc(periodo)}${esc(clausula)}, devendo permanecer afastado(a) ` +
        "de suas atividades habituais por ";
      txt = "Atesto, para fins " + finalidade.txt + ", que " + paciente.txt +
            meio + `${dias} dia(s)` + " a partir desta data.";
      html = "Atesto, para fins " + finalidade.html + ", que " + paciente.html +
             meioHtml + "<strong>" + esc(`${dias} dia(s)`) + "</strong>" +
             " a partir desta data.";
    } else {
      const meio =
        ` compareceu a atendimento ${c.adjetivoAtendimento} na data de ` +
        `${data.txt}${periodo}${clausula}.`;
      const meioHtml =
        ` compareceu a atendimento ${esc(c.adjetivoAtendimento)} na data de ` +
        `${data.html}${esc(periodo)}${esc(clausula)}.`;
      txt = "Atesto, para fins " + finalidade.txt + ", que " + paciente.txt + meio;
      html = "Atesto, para fins " + finalidade.html + ", que " + paciente.html + meioHtml;

      // No ramo de comparecimento sem dias, o formulário manda `0`: o domínio
      // lê isso como "não afasta". A folha não anuncia afastamento nenhum.
    }

    // A OBSERVAÇÃO é parágrafo PRÓPRIO e nunca substitui o corpo: os campos
    // estruturados seguem sendo a autoridade sobre dias, datas e finalidade.
    const obs = String(e.observacao_complementar || "").trim();

    if (paraGuarda) {
      return { texto: obs ? txt + "\n\n" + obs : txt, html: "" };
    }
    return {
      texto: obs ? txt + "\n\n" + obs : txt,
      html: html,
      observacaoHtml: obs ? esc(obs) : "",
    };
  }

  // ── blocos ───────────────────────────────────────────────────────────────

  function _cabecalho(e) {
    const c = conselhoDe(e.conselho);
    return (
      '<header class="at-cabecalho" data-bloco="cabecalho">' +
      '<p class="at-marca">PicSaúde</p>' +
      '<p class="at-sub">Plataforma de custódia sanitária digital</p>' +
      '<h2 data-campo="titulo">' + esc(c.titulo) + "</h2>" +
      "</header>"
    );
  }

  function _profissional(e) {
    const p = e.profissional || {};
    const c = conselhoDe(e.conselho);
    // O registro sai formatado "CRM-PE 12345" — e a sigla vem do conselho,
    // como no `conselho_profissional.py`. É o mesmo dado que o PDF imprime.
    const partes = [];
    if (!_vazio(p.uf) || !_vazio(p.numero)) {
      partes.push(
        c.sigla + (_vazio(p.uf) ? "" : "-" + String(p.uf).trim()) +
        (_vazio(p.numero) ? "" : " " + String(p.numero).trim())
      );
    }
    const registro = partes.length
      ? esc(partes[0])
      : lacuna("registro profissional");

    return (
      '<section class="at-bloco" data-bloco="profissional">' +
      '<span class="at-rot">Profissional</span>' +
      '<p class="at-linha-forte" data-campo="profissional">' +
      ou(p.nome, "prescritor não identificado") +
      ' <span class="at-registro">— ' + registro + "</span></p>" +
      "</section>"
    );
  }

  function _paciente(e) {
    return (
      '<section class="at-bloco" data-bloco="paciente">' +
      '<span class="at-rot">Paciente</span>' +
      '<p class="at-linha-forte" data-campo="paciente">' +
      ou(e.nome_paciente, "nome do paciente") +
      ' <span class="at-cpf">— CPF ' +
      ou(e.cpf_mascarado, "obrigatório para o atestado digital") +
      "</span></p>" +
      "</section>"
    );
  }

  /** O corpo — a região onde este objeto vive ou morre. */
  function _corpo(e) {
    const corpo = corpoAtestado(e, false);
    const obs = corpo.observacaoHtml
      ? '<p class="at-frase at-observacao" data-campo="observacao">' +
        corpo.observacaoHtml + "</p>"
      : "";
    return (
      '<section class="at-corpo" data-bloco="corpo">' +
      '<p class="at-frase" data-campo="frase">' + corpo.html + "</p>" +
      obs +
      "</section>"
    );
  }

  function _rodape(e) {
    const a = e.assinatura || {};
    const local = _vazio(e.municipio)
      ? lacuna("município de emissão", { inline: true })
      : esc(String(e.municipio).trim());
    const data = _vazio(dataBr(e.data_documento))
      ? lacuna("data", { inline: true })
      : esc(dataBr(e.data_documento));

    let selo;
    if (a.tipo === "digital") {
      selo = '<p class="at-ass-nota">Documento assinado digitalmente (ICP-Brasil)</p>';
    } else if (a.tipo === "fisica") {
      selo = '<p class="at-ass-nota at-ass-fisica">⚠️ Emissão física — requer ' +
             "assinatura à caneta e carimbo; sem custódia digital.</p>";
    } else {
      selo = '<p class="at-ass-nota">' + lacuna("a assinatura entra na emissão") + "</p>";
    }

    return (
      '<footer class="at-rodape" data-bloco="rodape">' +
      '<p class="at-local" data-campo="local-data">' + local + ", " + data + ".</p>" +
      selo +
      "</footer>"
    );
  }

  function _identificacao(e) {
    const proto = _vazio(e.protocolo)
      ? lacuna("gerado na emissão")
      : '<b class="at-mono">' + esc(e.protocolo) + "</b>";

    let hash;
    if (!_vazio(e.hash)) {
      hash = '<span class="at-mono">' + esc(e.hash) + "</span>";
    } else if (e.emitido) {
      hash = nota("não gerado — emissão física, sem documento canônico");
    } else {
      hash = lacuna("gerado na emissão");
    }

    return (
      '<section class="at-ident" data-bloco="identificacao">' +
      '<p class="at-ident-linha" data-campo="protocolo">Protocolo: ' + proto +
      (_vazio(e.status) ? "" : ' <span class="at-status">· Status: ' +
        esc(String(e.status).trim()) + "</span>") + "</p>" +
      '<p class="at-ident-linha" data-campo="hash">Hash SHA-256: ' + hash + "</p>" +
      '<p class="at-ident-rodape">PicSaúde — Plataforma de Custódia Sanitária ' +
      "Digital. Verifique a autenticidade pelo protocolo.</p>" +
      "</section>"
    );
  }

  function _seloCustodia(e) {
    if (!e.emitido) return "";
    const fisica = (e.assinatura || {}).tipo === "fisica";
    // Caixa-alta na FUNÇÃO — o W ≡ Y compara texto.
    //
    // "CUSTÓDIA AO PACIENTE" é FATO, não promessa: `atestados.py` registra a
    // custódia prescritor → paciente na própria emissão (INSERT em
    // `atestado_custodia`, evento `custodia_transferida`).
    const texto = fisica
      ? "🖨️ IMPRESSO · EMISSÃO FÍSICA — SEM CUSTÓDIA DIGITAL"
      : "✓ EMITIDO · CUSTÓDIA AO PACIENTE";
    const traco = _vazio(e.hash)
      ? ""
      : '<span class="doc-selo-hash at-selo-hash">sha-256 · ' +
        esc(String(e.hash).slice(0, 24)) + "…</span>";
    return (
      '<div class="doc-selo-custodia at-carimbo' +
        (fisica ? " doc-selo-fisico at-carimbo-fisico" : "") +
        '" data-bloco="carimbo">' +
      "<span>" + esc(texto) + "</span>" + traco +
      "</div>"
    );
  }

  /**
   * A FUNÇÃO GERADORA do atestado.
   *
   * @param {object} estado  o documento, como dado
   * @param {string} modo    MODOS.RASCUNHO | MODOS.CARIMBO — só o MEIO
   */
  function renderAtestado(estado, modo) {
    const e = estado || {};
    const m = modo === MODOS.CARIMBO ? MODOS.CARIMBO : MODOS.RASCUNHO;
    return (
      '<article class="doc-folha at-folha doc-modo-' + m + " at-modo-" + m +
        (e.emitido ? " doc-emitida at-emitido" : "") + '">' +
      _cabecalho(e) +
      _profissional(e) +
      _paciente(e) +
      _corpo(e) +
      _rodape(e) +
      _identificacao(e) +
      _seloCustodia(e) +
      "</article>"
    );
  }

  function montar(alvo, estado, modo) {
    N.montar(alvo, renderAtestado(estado, modo), modo);
  }

  const Atestado = {
    MODOS: MODOS,
    render: renderAtestado,
    montar: montar,
    textoDoDocumento: N.textoDoDocumento,
    // Exposto para a guarda folha ≡ domínio: é este texto que se compara com
    // o `corpo_documento` do servidor.
    corpoAtestado: (estado) => corpoAtestado(estado, true).texto,
    conselhoDe: conselhoDe,
  };

  window.Atestado = Atestado;
  window.renderAtestado = renderAtestado;
})();
