/* ==========================================================================
 * typeahead-catalogo.js — typeahead unificado sobre catálogo local.
 *
 * DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §4/§6 (PR 1 `module` — painel
 * primeiro, base depois, martelo "motor ou tabela?" de 28/08).
 * ------------------------------------------------------------------------
 * O encaminhamento adota a MESMA língua visual dos painéis assistidos
 * (padrão-ouro: o painel de CID do atestado/exame/prescrição —
 * `_renderizarSugestoesCid`). UM COMPONENTE, DUAS MONTAGENS no
 * encaminhamento (especialidade + mini-CID) — precedente: `submodulos.js`
 * (#193), `chips-cidadaos-demo.js`/`cidadao-demo-fixo.js` (#213/#215):
 * mesma língua por construção, não por disciplina.
 *
 * O QUE ESTE COMPONENTE HERDA DO PADRÃO-OURO
 * --------------------------------------------
 * Eco do termo digitado, lista com **código + título** (o código entra como
 * chip — só quando a entrada TEM um, nunca inventado), contagem honesta
 * ("N de TOTAL"), escape explícito ("OUTRA"/"não listado"), rodapé de
 * **provenância verdadeira** — lida do catálogo a cada render, nunca fixa
 * aqui. É essa leitura ao vivo que prova a agnosticidade: quando a base
 * virar CBO (PR `adapter` seguinte), o catálogo passa a declarar outra
 * `fonte`/`versao` e este arquivo não muda uma linha.
 *
 * O QUE ESTE COMPONENTE NÃO HERDA, DE PROPÓSITO
 * -------------------------------------------------
 * Badge de confiança ("Aproximada · Alta") — aquele selo do padrão-ouro
 * existe porque há uma IA de casamento difuso atrás dele (`/ia/cid/buscar`).
 * Aqui é substring EXATO sobre um array local, sem rede, sem score. Selo
 * sem engine é teatro — não replicado.
 *
 * O QUE ESTE COMPONENTE FAZ, E O QUE NÃO FAZ
 * ---------------------------------------------
 * Faz: filtra por substring (`buscar`), desenha o painel, navega por
 * teclado (setas/Enter/Esc), escreve o valor escolhido no <input hidden>
 * indicado e dispara 'change' — os `onchange="..."` já cabeados no HTML
 * (ex.: `carregarSugestoesDestino()`) continuam sendo o MESMO caminho de
 * quem escolhia no <select> nativo.
 *
 * NÃO faz: decidir o que é "código" ou "título" num item bruto do catálogo
 * (os accessors `rotulo`/`chip`/`exibir`/`valor` vêm de quem monta — a
 * especialidade e o CID têm semânticas diferentes de "o que vira o valor
 * salvo", e o componente não deveria adivinhar isso), nem validar o
 * formulário, nem conhecer o objeto sanitário.
 * ========================================================================== */

(function () {
  "use strict";

  function _esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function _garantirCss() {
    if (document.getElementById("typeahead-catalogo-css")) return;
    const css = document.createElement("style");
    css.id = "typeahead-catalogo-css";
    css.textContent =
      ".tac-painel{margin-top:6px;border:1px solid #cbd5e1;border-radius:8px;" +
      "background:#fff;box-shadow:0 4px 12px rgba(15,23,42,.08);" +
      "max-height:320px;display:flex;flex-direction:column;overflow:hidden;}" +
      // [hidden] precisa de MAIS especificidade que a classe acima, senão
      // `display:flex` do seletor de classe vence `[hidden]{display:none}`
      // da UA stylesheet (mesma especificidade, cascata decide — e a nossa
      // <style> injetada é sempre mais recente). Achado ao vivo: o painel
      // ficava visualmente aberto mesmo com o atributo `hidden` presente.
      ".tac-painel[hidden]{display:none;}" +
      ".tac-eco{padding:8px 12px;font-size:11px;color:#64748b;" +
      "border-bottom:1px solid #eef2f7;background:#f8fafc;}" +
      ".tac-lista{overflow-y:auto;max-height:240px;}" +
      ".tac-item{display:flex;align-items:center;gap:8px;padding:8px 12px;" +
      "cursor:pointer;font-size:13px;color:#0f172a;}" +
      ".tac-item:hover,.tac-item.tac-ativo{background:#eff6ff;}" +
      ".tac-item-codigo{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;" +
      "font-size:11px;font-weight:700;color:#1e3a8a;background:#e0f2fe;" +
      "border-radius:4px;padding:2px 6px;white-space:nowrap;}" +
      ".tac-item-titulo{flex:1;}" +
      ".tac-escape{border-top:1px solid #eef2f7;color:#475569;font-style:italic;}" +
      ".tac-vazio{padding:10px 12px;font-size:12px;color:#94a3b8;font-style:italic;}" +
      ".tac-rodape{padding:6px 12px;font-size:11px;color:#94a3b8;" +
      "border-top:1px solid #eef2f7;background:#f8fafc;}";
    document.head.appendChild(css);
  }

  const TypeaheadCatalogo = {
    /**
     * Monta o typeahead: busca em `buscaInputId`, valor escolhido gravado em
     * `valorInputId` (<input type=hidden>), painel desenhado em `painelId`.
     *
     * @param {object} opcoes
     * @param {string}   opcoes.buscaInputId
     * @param {string}   opcoes.valorInputId
     * @param {string}   opcoes.painelId
     * @param {()=>Array} opcoes.itens        lê o catálogo NA HORA (permite
     *                                        trocar a base sem remontar)
     * @param {(item,termoMaiusculo:string)=>boolean} opcoes.buscar
     * @param {(item)=>string}      opcoes.rotulo   texto principal da linha
     * @param {(item)=>?string}     opcoes.chip     código pro chip (null = sem chip)
     * @param {(item)=>string}      opcoes.exibir   texto que fica no campo após escolher
     * @param {(item)=>string}      opcoes.valor    o que grava no hidden
     * @param {()=>{fonte:string,versao?:string,unidade:string}} opcoes.provenancia
     * @param {{rotulo:string,valor:string}} opcoes.escape  linha de escape ("OUTRA" etc.)
     */
    montar(opcoes) {
      const {
        buscaInputId, valorInputId, painelId,
        itens, buscar, rotulo, chip, exibir, valor, provenancia, escape,
      } = opcoes;

      const buscaEl = document.getElementById(buscaInputId);
      const valorEl = document.getElementById(valorInputId);
      const painelEl = document.getElementById(painelId);
      if (!buscaEl || !valorEl || !painelEl) return;

      _garantirCss();
      painelEl.className = "tac-painel";
      painelEl.hidden = true;
      painelEl.setAttribute("role", "listbox");

      buscaEl.setAttribute("role", "combobox");
      buscaEl.setAttribute("aria-expanded", "false");
      buscaEl.setAttribute("aria-controls", painelId);
      buscaEl.setAttribute("aria-autocomplete", "list");
      buscaEl.setAttribute("autocomplete", "off");

      let linhas = [];       // itens filtrados + a linha de escape, na ordem renderizada
      let ativo = -1;        // índice destacado (teclado), -1 = nenhum

      function _dispararChange(el) {
        el.dispatchEvent(new Event("change", { bubbles: true }));
      }

      function _fechar() {
        painelEl.hidden = true;
        painelEl.innerHTML = "";
        buscaEl.setAttribute("aria-expanded", "false");
        buscaEl.removeAttribute("aria-activedescendant");
        linhas = [];
        ativo = -1;
      }

      function _escolher(entrada) {
        const v = entrada.__escape ? escape.valor : valor(entrada.item);
        const texto = entrada.__escape ? escape.rotulo : exibir(entrada.item);
        valorEl.value = v;
        buscaEl.value = texto;
        _dispararChange(valorEl);
        _fechar();
      }

      function _marcarAtivo(i) {
        ativo = i;
        Array.from(painelEl.querySelectorAll(".tac-item")).forEach((el, idx) => {
          el.classList.toggle("tac-ativo", idx === i);
        });
        if (i >= 0 && linhas[i]) {
          buscaEl.setAttribute("aria-activedescendant", `${painelId}-opt-${i}`);
        } else {
          buscaEl.removeAttribute("aria-activedescendant");
        }
      }

      function _renderizar() {
        const termo = buscaEl.value.trim().toUpperCase();
        const todos = itens();
        const filtrados = termo ? todos.filter((it) => buscar(it, termo)) : todos;

        linhas = filtrados.map((item) => ({ item, __escape: false }));
        linhas.push({ __escape: true });

        const prov = provenancia();
        const versaoTxt = prov.versao ? `, versão ${_esc(prov.versao)}` : "";
        const rodape = `${_esc(prov.fonte)}, ${filtrados.length} ${_esc(prov.unidade)}${versaoTxt}`;

        let html = `<div class="tac-eco">` +
          (termo ? `Buscando &ldquo;${_esc(termo)}&rdquo; — ${filtrados.length} de ${todos.length}`
                 : `${todos.length} no catálogo — digite para refinar`) +
          `</div><div class="tac-lista">`;

        if (!filtrados.length) {
          html += `<div class="tac-vazio">Nenhuma entrada encontrada.</div>`;
        } else {
          filtrados.forEach((item, i) => {
            const cod = chip(item);
            html += `<div class="tac-item" role="option" id="${painelId}-opt-${i}" data-idx="${i}">` +
              (cod ? `<span class="tac-item-codigo">${_esc(cod)}</span>` : "") +
              `<span class="tac-item-titulo">${_esc(rotulo(item))}</span></div>`;
          });
        }

        const iEscape = linhas.length - 1;
        html += `</div>` +
          `<div class="tac-item tac-escape" role="option" id="${painelId}-opt-${iEscape}" data-idx="${iEscape}">` +
          `<span class="tac-item-titulo">${_esc(escape.rotulo)}</span></div>` +
          `<div class="tac-rodape">${rodape}</div>`;

        painelEl.innerHTML = html;
        painelEl.hidden = false;
        buscaEl.setAttribute("aria-expanded", "true");
        _marcarAtivo(-1);
      }

      // Não perder foco ao clicar dentro do painel (senão 'blur' fecha antes
      // do 'click' da linha registrar a escolha — o problema clássico do
      // combobox). mousedown, não click: dispara ANTES do blur.
      painelEl.addEventListener("mousedown", (ev) => ev.preventDefault());

      painelEl.addEventListener("click", (ev) => {
        const linha = ev.target.closest("[data-idx]");
        if (!linha) return;
        const entrada = linhas[Number(linha.dataset.idx)];
        if (entrada) _escolher(entrada);
      });

      buscaEl.addEventListener("focus", _renderizar);
      buscaEl.addEventListener("input", _renderizar);

      buscaEl.addEventListener("blur", _fechar);

      buscaEl.addEventListener("keydown", (ev) => {
        if (painelEl.hidden && (ev.key === "ArrowDown" || ev.key === "ArrowUp")) {
          _renderizar();
          return;
        }
        if (!linhas.length) return;

        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          _marcarAtivo(Math.min(ativo + 1, linhas.length - 1));
        } else if (ev.key === "ArrowUp") {
          ev.preventDefault();
          _marcarAtivo(Math.max(ativo - 1, 0));
        } else if (ev.key === "Enter") {
          // Impede o submit implícito do <form> — Enter aqui é "escolher da
          // lista", não "enviar o formulário".
          ev.preventDefault();
          if (ativo >= 0 && linhas[ativo]) _escolher(linhas[ativo]);
        } else if (ev.key === "Escape") {
          _fechar();
        }
      });
    },
  };

  window.TypeaheadCatalogo = TypeaheadCatalogo;
})();
