/* ==========================================================================
 * chips-cidadaos-demo.js — quick-pick de cidadãos demo, compartilhado.
 *
 * M-B (docs/tickets/DESENHO-VITRINE-HIGIENE-VISITANTE.md §3) +
 * M-C (idem, §7 — adendo)
 * ------------------------------------------------------------------------
 * A vitrine é pública e sem barreira: o nome do paciente entra por texto
 * livre em quatro campos (receita/exame/encaminhamento/atestado), e nada no
 * backend julga conteúdo (§1 do desenho — validação de forma é indecidível).
 * A resposta não é policiar a entrada; é tornar o caminho CANÔNICO mais
 * preguiçoso que a chulice — e o M-C zera o custo do caso mais comum:
 *
 *     padrão (zero cliques)  >  chips (um clique)  >  texto livre (digitar)
 *
 * TEXTO LIVRE PERMANECE — isto é um atalho sobre o <input>, não um <select>
 * que troca o campo. Quem quer prescrever para si mesmo continua podendo, e
 * o preenchimento padrão não é gate: é só o que já está lá quando o
 * formulário abre (ou volta a abrir, limpo, para o próximo).
 *
 * UM ARQUIVO, QUATRO MONTAGENS (precedente: submodulos.js, #193) — mesma
 * língua por construção, não por disciplina: mudou aqui, mudou nos quatro
 * lugares, e não existe o estado intermediário em que um andou e os outros
 * ficaram. `montar()` e `preencherPadrao()` chamam o MESMO `_preencher()`
 * interno que o clique do chip usa — uma função de preencher, cinco
 * chamadas (4 default + 1 clique), não cinco implementações do mesmo gesto.
 *
 * SEM MEMÓRIA — de propósito. Nenhum localStorage de "última escolha": todo
 * `montar()`/`preencherPadrao()` novo volta ao cidadão default
 * (`DEMO.cidadaos[0]`, contrato de posição — é sempre o cidadão canônico,
 * `DEMO.cidadao`). "Vitrine nova de manhã" é o modelo mental; escolha
 * sticky seria estado de UI sem dono.
 *
 * O QUE ESTE COMPONENTE FAZ, E O QUE NÃO FAZ
 * -------------------------------------------
 * Faz: desenha os chips, preenche o par default no boot/montagem, e no
 * clique preenche nome + CPF nos dois <input> indicados — disparando os
 * eventos nativos (`input`/`blur`) que os campos já escutam. A máscara de
 * CPF de `config.js` e o `onblur` de sugestões de destino do encaminhamento
 * continuam sendo o MESMO código que rodaria se o visitante tivesse digitado
 * e saído do campo.
 *
 * NÃO faz: decidir qual objeto sanitário está sendo emitido, validar o
 * formulário, nem conhecer `pac-chave` vs. `exam-pac-cpf` vs. `enc-pac-cpf`
 * vs. `atestado-cpf` por nome — os ids vêm de quem monta. Também não decide
 * QUANDO um formulário foi limpo — quem chama `preencherPadrao()` depois de
 * limpar é o dono daquele formulário (`novaReceita()` e afins).
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

  function _listaOuDefault(cidadaos) {
    return cidadaos || (typeof DEMO !== "undefined" && DEMO.cidadaos) || [];
  }

  /** O fill+dispatch ÚNICO — usado pelo default (montar/preencherPadrao) E
   *  pelo clique do chip. Mesma língua por construção. */
  function _preencher(nomeInputId, cpfInputId, cidadao) {
    if (!cidadao) return;
    const nomeEl = document.getElementById(nomeInputId);
    const cpfEl = document.getElementById(cpfInputId);
    if (nomeEl) {
      nomeEl.value = cidadao.nome;
      _disparar(nomeEl, "input");
    }
    if (cpfEl) {
      // Dígitos crus: a máscara de config.js (aplicarMascaraCPF) escuta
      // 'input' e formata sozinha — mesmo caminho de quem digita.
      cpfEl.value = cidadao.cpf;
      _disparar(cpfEl, "input");
      // 'blur' — o onblur do encaminhamento (carregarSugestoesDestino)
      // dispara como se o visitante tivesse saído do campo; nos outros
      // campos, sem onblur, é no-op.
      _disparar(cpfEl, "blur");
    }
  }

  const ChipsCidadaosDemo = {
    /**
     * Monta a fileira de chips de quick-pick dentro de `container` E aplica
     * o preenchimento PADRÃO (`cidadaos[0]`) — M-C: o caso mais comum custa
     * zero cliques.
     *
     * @param {HTMLElement|string} container   elemento ou id onde desenhar
     * @param {string} nomeInputId             id do <input> de nome
     * @param {string} cpfInputId              id do <input> de CPF
     * @param {Array<{cpf:string,nome:string}>} [cidadaos]
     *        default: `DEMO.cidadaos` (config.js) — lista vazia/ausente
     *        significa nada a montar nem preencher (sem quebrar a tela).
     */
    montar(container, nomeInputId, cpfInputId, cidadaos) {
      const el = typeof container === "string"
        ? document.getElementById(container) : container;
      if (!el) return;

      const lista = _listaOuDefault(cidadaos);
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
        _preencher(nomeInputId, cpfInputId, lista[Number(btn.dataset.idx)]);
      };

      // M-C — padrão no boot: zero cliques até aqui.
      _preencher(nomeInputId, cpfInputId, lista[0]);
    },

    /**
     * Reaplica o par PADRÃO (`cidadaos[0]`) sem remontar a fileira de chips —
     * para quem limpa um formulário depois do boot (`novaReceita()` e afins)
     * e quer o mesmo "volta a João" que um `montar()` novo daria. Sem
     * memória: sempre `cidadaos[0]`, nunca a última escolha do clique.
     *
     * @param {string} nomeInputId
     * @param {string} cpfInputId
     * @param {Array<{cpf:string,nome:string}>} [cidadaos]  default: `DEMO.cidadaos`
     */
    preencherPadrao(nomeInputId, cpfInputId, cidadaos) {
      const lista = _listaOuDefault(cidadaos);
      if (!lista.length) return;
      _preencher(nomeInputId, cpfInputId, lista[0]);
    },
  };

  window.ChipsCidadaosDemo = ChipsCidadaosDemo;
})();
