/* ==========================================================================
 * documento-nucleo.js — o que TODO documento sanitário em tela tem em comum.
 *
 * ENG-022, commit 1 · adjudicação 3 do PARECER-ARQ-ENXAME-DEMAIS-OBJETOS.
 *
 * POR QUE ESTE ARQUIVO NASCE AGORA — E NÃO ANTES NEM DEPOIS
 * ---------------------------------------------------------
 * Ele nasce por EXTRAÇÃO do `receituario.js`, na onda do exame, e nasce
 * **consumido por dois geradores no mesmo PR**. A ordem é deliberada: núcleo
 * extraído de um cliente só é palpite sobre o que será comum; extraído com o
 * segundo cliente à vista, é fato. Núcleo órfão vira parametrização de
 * conveniência — e, mais adiante, a desculpa para fundir anatomias.
 *
 * O QUE ESTE ARQUIVO **NÃO** FAZ — a fronteira que o parecer cravou
 * -----------------------------------------------------------------
 * Não gera documento nenhum. Não conhece receituário, pedido de exame,
 * encaminhamento nem atestado. Cada documento tem o SEU gerador, com a SUA
 * anatomia: *"duas anatomias numa função só é a dupla posse pela porta dos
 * fundos"*. Aqui moram só os gestos que não dependem de qual papel é:
 *
 *   - o vocabulário da lacuna (o branco do papel esperando a caneta)
 *   - a TINTA por `data-bloco` — a região NOMEADA, para uma guarda poder
 *     apontar "esta região divergiu" em vez de "o documento divergiu"
 *   - o contrato W ≡ Y: `montar` / `textoDoDocumento` / `MODOS`
 *   - o botão flutuante que se recolhe diante do gesto de emitir
 *
 * AS DUAS LIÇÕES DO DEGENERADO, NO CONTRATO DESDE O NASCIMENTO
 * ------------------------------------------------------------
 * O atestado é um documento de FRASE CORRIDA: a lacuna dele mora no meio de
 * uma sentença ("atesto que o(a) Sr(a) ____ necessita de ____ dias"), não num
 * campo de bloco. Se o modo inline só aparecesse quando o atestado chegasse,
 * ele chegaria como REFORMA do núcleo — e reforma de núcleo com três clientes
 * vivos é onde se quebram os outros dois. Por isso `lacuna(texto, {inline})`
 * já está aqui, e a região nomeada também, antes de existir quem as peça.
 *
 * O VOCABULÁRIO É PREFIXADO POR OBJETO — e o porquê importa
 * ----------------------------------------------------------
 * `vocabulario('rec')` devolve funções que emitem `class="doc-lacuna
 * rec-lacuna"`. A classe `doc-*` carrega o ESTILO (um lugar só, compartilhado);
 * a `<prefixo>-*` é o GANCHO nomeado do objeto — é por ela que a guarda daquele
 * documento aponta, e é nela que uma exceção daquele papel se pendura sem
 * respingar nos outros. Estilo compartilhado por construção, identidade
 * preservada por construção.
 *
 * CONTRATO
 * --------
 *   DocumentoNucleo.MODOS                          → { RASCUNHO, CARIMBO }
 *   DocumentoNucleo.esc(v) / .vazio(v)
 *   DocumentoNucleo.vocabulario(prefixo)           → { lacuna, ou, ouMaiusculo, nota }
 *   DocumentoNucleo.montar(alvo, html, modo)       → pinta um alvo (+ tinta)
 *   DocumentoNucleo.textoDoDocumento(alvo)         → texto normalizado (W ≡ Y)
 *   DocumentoNucleo.ligarFabAoEmitir(fab, emitir)  → o flutuante que sai de cena
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

  function vazio(v) {
    return String(v === null || v === undefined ? "" : v).trim() === "";
  }

  /**
   * O vocabulário do documento, com o gancho nomeado do objeto.
   *
   * @param {string} prefixo  'rec' | 'exame' | … — nomeia o gancho do objeto
   * @returns {{lacuna,ou,ouMaiusculo,nota}}
   */
  function vocabulario(prefixo) {
    const p = String(prefixo || "doc");

    /**
     * O espaço pontilhado — o branco do papel esperando a caneta.
     *
     * `{inline: true}` para a lacuna que mora DENTRO de uma frase: ela abre
     * mão da largura mínima e do respiro, para não rasgar a linha de texto.
     * O documento de frase corrida (o atestado) depende disso; o de campos
     * (receita, pedido de exame) usa o modo de bloco, que é o default.
     */
    function lacuna(texto, opcoes) {
      const inline = !!(opcoes && opcoes.inline);
      return '<span class="doc-lacuna ' + p + "-lacuna" +
             (inline ? " doc-lacuna-inline" : "") + '">' + esc(texto) + "</span>";
    }

    /** Valor escapado, ou a lacuna correspondente quando o campo está vazio. */
    function ou(valor, textoDaLacuna, opcoes) {
      return vazio(valor) ? lacuna(textoDaLacuna, opcoes) : esc(String(valor).trim());
    }

    /**
     * Como `ou`, mas caixa-alta.
     *
     * A caixa-alta é feita AQUI e não em CSS de propósito: `text-transform`
     * pintaria a tela sem tocar o texto, e o W ≡ Y compara TEXTO. Dado passa
     * pela função; só o cromo (rótulos, sombras) fica para a folha de estilo.
     */
    function ouMaiusculo(valor, textoDaLacuna, opcoes) {
      return vazio(valor)
        ? lacuna(textoDaLacuna, opcoes)
        : esc(String(valor).trim().toUpperCase());
    }

    /** Nota do documento sobre si mesmo (não é lacuna: é fato declarado). */
    function nota(texto) {
      return '<span class="doc-nota ' + p + '-nota">' + esc(texto) + "</span>";
    }

    return { lacuna: lacuna, ou: ou, ouMaiusculo: ouMaiusculo, nota: nota };
  }

  /**
   * Pinta um alvo com o documento já renderizado — e acende a TINTA na região
   * que mudou.
   *
   * Recebe HTML PRONTO, não um estado: quem sabe desenhar o papel é o gerador
   * do objeto, e o núcleo não pode ganhar o direito de escolher anatomia.
   *
   * A tinta é gesto de TELA: só no modo rascunho. No alvo de carimbo ela seria
   * ruído num documento que ninguém está vendo se formar.
   *
   * O invólucro é preservado — trocamos só o miolo. É o que permite exigir que
   * o carimbo caia na MESMA folha que estava à vista, e a uma guarda provar
   * que a folha não foi substituída.
   */
  function montar(alvo, html, modo) {
    const el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    if (!el) return;

    const antes = {};
    el.querySelectorAll("[data-bloco]").forEach((b) => {
      antes[b.getAttribute("data-bloco")] = b.innerHTML;
    });

    el.innerHTML = html;

    if (modo === MODOS.CARIMBO) return;

    el.querySelectorAll("[data-bloco]").forEach((b) => {
      const chave = b.getAttribute("data-bloco");
      if (antes[chave] === undefined || antes[chave] === b.innerHTML) return;
      b.classList.add("doc-tinta");
      setTimeout(() => b.classList.remove("doc-tinta"), _TINTA_MS);
    });
  }

  /**
   * O texto do documento, normalizado — a definição ÚNICA de "equivalente".
   *
   * Existe aqui, e não copiada dentro de cada guarda nem de cada gerador,
   * porque W ≡ Y só vale se os dois lados forem lidos pela mesma régua. Três
   * documentos com três réguas seriam três promessas diferentes com o mesmo
   * nome.
   */
  function textoDoDocumento(alvo) {
    const el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    if (!el) return "";
    return String(el.textContent || "").replace(/\s+/g, " ").trim();
  }

  /**
   * O botão flutuante NUNCA cobre o gesto de emitir.
   *
   * Resolvido por construção, não por medida de pixel: quando o botão de
   * emitir entra na viewport, o flutuante se recolhe. Em telas apertadas os
   * dois nunca dividem o mesmo canto.
   *
   * A classe (e não `[hidden]`) é deliberada: `display:block` de media query
   * venceria o atributo, e a casa já pagou essa lição duas vezes.
   */
  function ligarFabAoEmitir(fab, emitir) {
    const b = typeof fab === "string" ? document.getElementById(fab) : fab;
    const e = typeof emitir === "string" ? document.getElementById(emitir) : emitir;
    if (!b || !e || typeof IntersectionObserver === "undefined") return;
    new IntersectionObserver((entradas) => {
      entradas.forEach((x) => b.classList.toggle("doc-fab-recolhido", x.isIntersecting));
    }, { threshold: 0 }).observe(e);
  }

  window.DocumentoNucleo = {
    MODOS: MODOS,
    esc: esc,
    vazio: vazio,
    vocabulario: vocabulario,
    montar: montar,
    textoDoDocumento: textoDoDocumento,
    ligarFabAoEmitir: ligarFabAoEmitir,
  };
})();
