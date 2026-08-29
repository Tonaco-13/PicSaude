/* ==========================================================================
 * submodulos.js — a BARRA DE PÍLULAS de submódulos, compartilhada.
 *
 * UM ARQUIVO, DUAS TELAS (decisão do Fabiano, 24/08)
 * --------------------------------------------------
 * A carteira do cidadão e a tela do prescritor navegam pela MESMA barra,
 * desenhada pela MESMA função. Não é "mesma aparência mantida por disciplina"
 * — é a mesma aparência porque é o mesmo código. Consistência por construção:
 * mudou aqui, mudou nas duas, e não existe o estado intermediário em que uma
 * andou e a outra ficou.
 *
 * A fórmula é a do prescritor: texto em maiúsculas, compacto, pílula clara
 * sobre trilho cinza. Sem ícone e sem subtítulo — é o "design limpo" que a
 * decisão nomeia, e é o que faz as duas barras serem literalmente iguais.
 *
 * O QUE ESTE COMPONENTE FAZ, E O QUE NÃO FAZ
 * ------------------------------------------
 * Faz: desenha as pílulas, marca a ativa, mostra e atualiza contadores, e
 * chama de volta quem a montou.
 *
 * NÃO faz: decidir o que cada painel mostra, buscar dado, conhecer objeto
 * sanitário. Ele troca a PORTA; o que há dentro da casa é de quem o usa — foi
 * a instrução literal do ticket, e é o que o mantém utilizável nas duas telas
 * sem virar um arquivo que sabe de tudo.
 *
 * ACESSIBILIDADE: as pílulas são `role="tab"` num `role="tablist"`, como as
 * abas que substituem. Mudou a aparência, não a semântica — leitor de tela
 * continua anunciando "aba N de 6, selecionada".
 * ========================================================================== */

(function () {
  "use strict";

  function _esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  const Submodulos = {
    /**
     * Desenha a barra dentro de `container`.
     *
     * @param {HTMLElement|string} container  elemento ou id
     * @param {Array<{chave,titulo,contador?}>} itens
     *        `contador` ausente (undefined) = pílula sem número (a barra do
     *        prescritor, que numera nada) — nem o `<span>` nasce. `null` =
     *        pílula existe mas SEM DADO AINDA (nasce `hidden`; A3/FILA-VIVA —
     *        pintar `0` de saída é indistinguível de "de fato zero", e o
     *        fetch assíncrono que preenche o valor real ainda não voltou).
     *        Número = valor real, visível desde o início.
     * @param {(chave:string)=>void} aoEscolher
     * @param {string} ativo  chave inicial
     * @param {string} rotulo rótulo ARIA da barra
     */
    render(container, itens, aoEscolher, ativo, rotulo) {
      const el = typeof container === "string"
        ? document.getElementById(container) : container;
      if (!el) return;

      el.className = "submod-nav";
      el.setAttribute("role", "tablist");
      el.setAttribute("aria-label", rotulo || "Submódulos");
      el.innerHTML = itens.map((it) => `
        <button type="button" role="tab" class="submod-btn${it.chave === ativo ? " ativo" : ""}"
                id="submod-btn-${_esc(it.chave)}"
                aria-controls="submod-${_esc(it.chave)}"
                aria-selected="${it.chave === ativo}"
                data-submod="${_esc(it.chave)}">
          <span class="submod-titulo">${_esc(it.titulo)}</span>
          ${it.contador === undefined ? "" :
            `<span class="submod-contador" id="submod-count-${_esc(it.chave)}"${it.contador === null ? " hidden" : ""}>${it.contador ?? 0}</span>`}
        </button>`).join("");

      // Delegação: um listener na barra, não N nas pílulas. Re-render não
      // acumula handler — e re-render acontece a cada carga da carteira.
      el.onclick = (ev) => {
        const alvo = ev.target.closest("[data-submod]");
        if (alvo && aoEscolher) aoEscolher(alvo.dataset.submod);
      };
    },

    /** Marca a pílula ativa e sincroniza o ARIA dos painéis. */
    marcarAtivo(chaves, ativo) {
      chaves.forEach((c) => {
        const btn = document.getElementById("submod-btn-" + c);
        const painel = document.getElementById("submod-" + c);
        if (btn) {
          btn.classList.toggle("ativo", c === ativo);
          btn.setAttribute("aria-selected", String(c === ativo));
        }
        if (painel) painel.classList.toggle("hidden", c !== ativo);
      });
    },

    /** Contador da pílula. `null`/`undefined` esconde — zero não é "sem
     *  informação", e um "0" permanente vira ruído que ninguém mais lê. */
    contador(chave, valor) {
      const el = document.getElementById("submod-count-" + chave);
      if (!el) return;
      if (valor === null || valor === undefined) { el.hidden = true; return; }
      el.hidden = false;
      el.textContent = String(valor);
    },
  };

  window.Submodulos = Submodulos;
})();
