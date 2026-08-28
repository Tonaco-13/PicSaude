/* ==========================================================================
 * cidadao-demo-fixo.js — trava o par nome+CPF do paciente no cidadão canônico.
 *
 * M-D (docs/tickets/DESENHO-VITRINE-HIGIENE-VISITANTE.md §8 — martelo do
 * Fabiano, 28/08, REVOGA M-B/M-C)
 * ------------------------------------------------------------------------
 * O texto livre nos quatro campos de paciente (receita/exame/encaminhamento/
 * atestado) deixava o visitante digitar QUALQUER nome — inclusive nomes
 * chulos, que ficavam visíveis para o PRÓXIMO visitante e em demos guiadas
 * (o problema original que abriu este ciclo, §0 do desenho). M-B (chips de
 * quick-pick) e M-C (preenchimento padrão) tentaram tornar o caminho
 * canônico mais preguiçoso que a chulice SEM fechar a porta do texto
 * livre — não bastou: *"As pessoas podem preencher com nomes chulos.
 * Aconteceu isso, por essa razão estamos fazendo esse ciclo."* (Fabiano,
 * 28/08). M-D fecha a porta: os campos de nome/CPF do paciente ficam
 * `readonly`, sempre com o cidadão canônico (`DEMO.cidadao`) — nenhuma
 * edição possível pela tela, e não há mais escolha entre cidadãos (o
 * conjunto de 3 cidadãos do M-B/M-C foi retirado — ver o desenho §8).
 *
 * LIMITE DECLARADO: isto é um lock de FRONTEND. Quem chama a API
 * diretamente (curl/Postman) ainda escreve o que quiser em
 * `nome_paciente`/`cpf_paciente` — o backend não valida conteúdo (nunca
 * validou; §1 do desenho continua valendo: validação de forma é
 * indecidível). Fechar essa porta também exigiria o backend recusar ou
 * normalizar em DEMO_MODE — decisão separada, fora deste PR.
 * ========================================================================== */

(function () {
  "use strict";

  function _disparar(el, tipo) {
    el.dispatchEvent(new Event(tipo, { bubbles: true }));
  }

  const CidadaoDemoFixo = {
    /**
     * Preenche e TRAVA (readonly) o par nome+CPF com o cidadão canônico.
     * Chamada no boot de cada formulário e de novo após qualquer limpeza
     * que o fluxo já faça (`novaReceita()` e afins) — um `.reset()` nativo
     * reverte um `<input readonly>` ao valor vazio do HTML (o valor nunca é
     * chumbado como literal no HTML — guard-rail de identidades, CLAUDE.md),
     * então o preenchimento precisa ser reaplicado; a trava em si persiste.
     *
     * @param {string} nomeInputId
     * @param {string} cpfInputId
     * @param {{cpf:string,nome:string}} [cidadao]  default: `DEMO.cidadao`
     */
    travar(nomeInputId, cpfInputId, cidadao) {
      const c = cidadao || (typeof DEMO !== "undefined" && DEMO.cidadao);
      if (!c) return;

      const nomeEl = document.getElementById(nomeInputId);
      const cpfEl = document.getElementById(cpfInputId);
      if (nomeEl) {
        nomeEl.value = c.nome;
        nomeEl.readOnly = true;
        _disparar(nomeEl, "input");
      }
      if (cpfEl) {
        // Dígitos crus: a máscara de config.js (aplicarMascaraCPF) escuta
        // 'input' e formata sozinha — mesmo caminho de quem digita.
        cpfEl.value = c.cpf;
        cpfEl.readOnly = true;
        _disparar(cpfEl, "input");
        // 'blur' — o onblur do encaminhamento (carregarSugestoesDestino)
        // dispara como se o visitante tivesse saído do campo; nos outros
        // campos, sem onblur, é no-op.
        _disparar(cpfEl, "blur");
      }
    },
  };

  window.CidadaoDemoFixo = CidadaoDemoFixo;
})();
