/* ==========================================================================
 * chips-cidadaos-demo.js — quick-pick de cidadãos demo, compartilhado.
 *
 * M-B (docs/tickets/DESENHO-VITRINE-HIGIENE-VISITANTE.md §3)
 * ------------------------------------------------------------------------
 * A vitrine é pública e sem barreira: o nome do paciente entra por texto
 * livre em três campos (receita/exame/encaminhamento), e nada no backend
 * julga conteúdo (§1 do desenho — validação de forma é indecidível). A
 * resposta não é policiar a entrada; é tornar o caminho CANÔNICO mais
 * preguiçoso que a chulice: um clique preenche nome + CPF válido de um
 * cidadão demo real (`DEMO.cidadaos`, config.js).
 *
 * TEXTO LIVRE PERMANECE — isto é um atalho sobre o <input>, não um <select>
 * que troca o campo. Quem quer prescrever para si mesmo continua podendo.
 *
 * UM ARQUIVO, TRÊS MONTAGENS (precedente: submodulos.js, #193) — mesma
 * língua por construção, não por disciplina: mudou aqui, mudou nos três
 * lugares, e não existe o estado intermediário em que um andou e os outros
 * ficaram.
 *
 * O QUE ESTE COMPONENTE FAZ, E O QUE NÃO FAZ
 * -------------------------------------------
 * Faz: desenha os chips e, no clique, preenche nome + CPF nos dois <input>
 * indicados, disparando os eventos nativos (`input`/`blur`) que os campos já
 * escutam — a máscara de CPF de `config.js` e o `onblur` de sugestões de
 * destino do encaminhamento continuam sendo o MESMO código que rodaria se o
 * visitante tivesse digitado e saído do campo.
 *
 * NÃO faz: decidir qual objeto sanitário está sendo emitido, validar o
 * formulário, nem conhecer `pac-chave` vs. `exam-pac-cpf` vs. `enc-pac-cpf`
 * por nome — os ids vêm de quem monta.
 * ========================================================================== */

(function () {
  "use strict";

  function _esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function _garantirCss() {
    if (document.getElementById("chips-cidadaos-demo-css")) return;
    const css = document.createElement("style");
    css.id = "chips-cidadaos-demo-css";
    css.textContent =
      ".chips-cidadaos-demo{display:flex;flex-wrap:wrap;align-items:center;" +
      "gap:6px;margin-top:8px;}" +
      ".chips-cidadaos-demo .rotulo{font-size:11px;color:#64748b;" +
      "font-weight:600;margin-right:2px;}" +
      ".chip-cidadao-demo{border:1px solid #cbd5e1;background:#f8fafc;" +
      "color:#1e3a8a;font-size:12px;font-weight:600;padding:4px 12px;" +
      "border-radius:999px;cursor:pointer;font-family:inherit;}" +
      ".chip-cidadao-demo:hover{background:#e0f2fe;border-color:#93c5fd;}" +
      ".chip-cidadao-demo:focus-visible{outline:2px solid #1e3a8a;" +
      "outline-offset:1px;}";
    document.head.appendChild(css);
  }

  function _disparar(el, tipo) {
    el.dispatchEvent(new Event(tipo, { bubbles: true }));
  }

  const ChipsCidadaosDemo = {
    /**
     * Monta a fileira de chips de quick-pick dentro de `container`.
     *
     * @param {HTMLElement|string} container   elemento ou id onde desenhar
     * @param {string} nomeInputId             id do <input> de nome
     * @param {string} cpfInputId              id do <input> de CPF
     * @param {Array<{cpf:string,nome:string}>} [cidadaos]
     *        default: `DEMO.cidadaos` (config.js) — lista vazia/ausente
     *        significa nada a montar (sem quebrar a tela).
     */
    montar(container, nomeInputId, cpfInputId, cidadaos) {
      const el = typeof container === "string"
        ? document.getElementById(container) : container;
      if (!el) return;

      const lista = cidadaos || (typeof DEMO !== "undefined" && DEMO.cidadaos) || [];
      if (!lista.length) { el.innerHTML = ""; return; }

      _garantirCss();
      el.className = "chips-cidadaos-demo";
      el.innerHTML = '<span class="rotulo">Preencher com cidadão demo:</span>' +
        lista.map((c, i) => `
          <button type="button" class="chip-cidadao-demo" data-idx="${i}">${_esc(c.nome)}</button>
        `).join("");

      // Delegação: um listener na fileira, não N nos chips (mesma disciplina
      // de submodulos.js — re-montar não acumula handler).
      el.onclick = (ev) => {
        const btn = ev.target.closest("[data-idx]");
        if (!btn) return;
        const c = lista[Number(btn.dataset.idx)];
        if (!c) return;

        const nomeEl = document.getElementById(nomeInputId);
        const cpfEl = document.getElementById(cpfInputId);
        if (nomeEl) {
          nomeEl.value = c.nome;
          _disparar(nomeEl, "input");
        }
        if (cpfEl) {
          // Dígitos crus: a máscara de config.js (aplicarMascaraCPF) escuta
          // 'input' e formata sozinha — mesmo caminho de quem digita.
          cpfEl.value = c.cpf;
          _disparar(cpfEl, "input");
          // 'blur' — o onblur do encaminhamento (carregarSugestoesDestino)
          // dispara como se o visitante tivesse saído do campo; nos outros
          // dois campos, sem onblur, é no-op.
          _disparar(cpfEl, "blur");
        }
      };
    },
  };

  window.ChipsCidadaosDemo = ChipsCidadaosDemo;
})();
