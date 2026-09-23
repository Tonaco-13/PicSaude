"""
test_frontend_encaminhamento_vivo.py — guardas ESTÁTICAS da terceira onda.

POR QUE ESTÁTICAS
-----------------
O smoke responde *"os dois alvos do encaminhamento renderizam igual?"* e roda
no gate de navegador. Estas rodam em TODO PR e respondem *"a família continua
com três geradores, um núcleo e um alvo por objeto?"* — a estrutura que um PR
futuro pode desfazer deixando o W ≡ Y verde no caminho.

Mesma disciplina de `test_frontend_receita_viva.py` e
`test_frontend_pedido_exame_vivo.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_HTML = _RAIZ / "prescritor.html"
_NUCLEO = _RAIZ / "documento-nucleo.js"
_RECEITA = _RAIZ / "receituario.js"
_EXAME = _RAIZ / "pedidoexame.js"
_ENC = _RAIZ / "encaminhamento.js"
_ENC_CSS = _RAIZ / "encaminhamento.css"
_CONFIG = _RAIZ / "config.js"


@pytest.fixture(scope="module")
def html() -> str:
    return _HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def enc() -> str:
    return _ENC.read_text(encoding="utf-8")


class TestTerceiroGeradorTerceiroAlvo:

    def test_o_encaminhamento_tem_gerador_proprio(self, enc):
        assert "function renderEncaminhamento(estado, modo)" in enc
        assert "window.renderEncaminhamento = renderEncaminhamento;" in enc
        assert _ENC_CSS.exists()

    def test_o_encaminhamento_tem_alvo_proprio_e_vazio(self, html):
        area = re.search(
            r'<div id="print-area-encaminhamento"[^>]*>(.*?)</div>', html, re.S
        )
        assert area, "#print-area-encaminhamento não existe"
        assert area.group(1).strip() == "", (
            "o alvo do encaminhamento ganhou marcação própria — ele é ALVO da "
            "função geradora, não um segundo template"
        )

    def test_os_tres_alvos_convivem(self, html):
        for alvo in ("print-area", "print-area-exame", "print-area-encaminhamento"):
            assert f'id="{alvo}"' in html, f"o alvo {alvo} sumiu"

    def test_os_dois_alvos_do_encaminhamento_saem_da_mesma_chamada(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarEncaminhamento()")
        assert "const estado" in corpo
        assert corpo.count("Encaminhamento.montar(") == 2
        assert "'folha-viva-encaminhamento'" in corpo
        assert "'print-area-encaminhamento'" in corpo

    def test_o_gerador_nao_conhece_os_irmaos(self, enc):
        codigo = re.sub(r"/\*.*?\*/", "", enc, flags=re.S)
        codigo = re.sub(r"//[^\n]*", "", codigo)
        for estranho in ("Receituário", "posologia", "TUSS", "prioridade", "Pedido de Exames"):
            assert estranho not in codigo, (
                f"{estranho!r} apareceu no CÓDIGO do gerador do ENCAMINHAMENTO"
            )


class TestONucleoTemTresConsumidores:

    def test_os_tres_geradores_consomem_o_nucleo(self, enc):
        for nome, arq in (("receituario.js", _RECEITA), ("pedidoexame.js", _EXAME)):
            js = arq.read_text(encoding="utf-8")
            assert "window.DocumentoNucleo" in js, f"{nome} não consome o núcleo"
        assert "window.DocumentoNucleo" in enc
        assert 'N.vocabulario("enc")' in enc
        assert "N.montar(" in enc
        assert "textoDoDocumento: N.textoDoDocumento," in enc

    def test_o_nucleo_segue_sem_conhecer_documento_nenhum(self):
        nucleo = _NUCLEO.read_text(encoding="utf-8")
        for estranho in ("Receituário", "Pedido de Exames", "Encaminhamento Médico",
                         "posologia", "TUSS", "especialidade"):
            assert estranho not in nucleo, (
                f"{estranho!r} vazou para o núcleo na terceira onda — é "
                "exatamente aqui que um núcleo começa a escolher anatomia"
            )

    def test_o_fab_do_nucleo_cresceu_para_varios_gestos(self):
        """A única peça que subiu nesta onda, e o objeto que a pediu explica o
        porquê: o encaminhamento é o único em que emitir acontece em dois
        tempos (revisar → confirmar)."""
        nucleo = _NUCLEO.read_text(encoding="utf-8")
        assert "function ligarFabAoEmitir(fab, ...alvos)" in nucleo
        assert "aVista" in nucleo, (
            "o núcleo voltou a decidir pelo último evento em vez do conjunto "
            "de gestos à vista — com dois alvos, um desmancharia a decisão do "
            "outro"
        )

    def test_a_licao_do_degenerado_estreou_aqui(self, html):
        """O modo inline entrou no núcleo no ENG-022 pensando no atestado, e
        foi o encaminhamento que o usou primeiro — na frase corrida."""
        enc = _ENC.read_text(encoding="utf-8")
        corpo = _corpo_da_funcao(enc, "function _frase(e)")
        assert "inline: true" in corpo or "inline" in corpo


class TestMascaraDeCNS:
    """AC7 — a máscara nova, e a grafia única do CNS no documento."""

    def test_a_mascara_mora_com_as_irmas(self):
        config = _CONFIG.read_text(encoding="utf-8")
        assert "function aplicarMascaraCNS(input)" in config
        assert "aplicarMascarasCNSGlobais();" in config, (
            "a máscara existe mas não é aplicada no boot"
        )

    def test_o_agrupamento_do_cns_tem_fonte_unica(self):
        """A máscara de digitação e o DOCUMENTO usam a mesma função. Sem isso,
        a folha saía com dois CNS em grafias diferentes — o do emitente com
        pontos, o do destino com espaços."""
        config = _CONFIG.read_text(encoding="utf-8")
        assert "function agruparCNS(valor)" in config
        corpo = _corpo_da_funcao(config, "function aplicarMascaraCNS(input)")
        assert "agruparCNS(" in corpo, "a máscara reimplementou o agrupamento"

        html = _HTML.read_text(encoding="utf-8")
        estado = _corpo_da_funcao(html, "function _estadoDoFormularioEnc()")
        assert "agruparCNS(" in estado
        assert "formatarCNS(" not in estado, (
            "o documento voltou a usar a grafia com pontos do painel de chaves"
        )

    def test_o_campo_de_cns_declara_a_mascara(self, html):
        campo = re.search(r'<input[^>]*id="enc-cns-destino"[^>]*>', html, re.S)
        assert campo and 'data-tipo="cns"' in campo.group(0)


class TestOFluxoDeEmissaoNaoMuda:
    """AC9 — revisão → confirmar → POST, e a aba Encaminhados no fim."""

    def test_o_carimbo_acontece_antes_do_reset(self, html):
        corpo = _corpo_da_funcao(html, "async function emitirEncaminhamento()")
        assert "_carimbarEncaminhamento(dados);" in corpo
        assert corpo.index("_carimbarEncaminhamento(dados);") < corpo.index(
            "document.getElementById('form-enc-main').reset();"
        ), (
            "o carimbo acontece DEPOIS do reset — era justamente esse reset "
            "que fazia o documento sumir sem deixar rastro"
        )

    def test_a_troca_de_aba_pos_emissao_permanece(self, html):
        corpo = _corpo_da_funcao(html, "async function emitirEncaminhamento()")
        assert "abrirAbaEnc('encaminhados')" in corpo, (
            "a troca de aba sumiu — as suítes do ENG-016 dependem dela, e o "
            "AC9 manda não mexer no fluxo"
        )

    def test_os_itens_do_formulario_viajam(self, html):
        corpo = _corpo_da_funcao(html, "async function emitirEncaminhamento()")
        assert "_encItensDoFormulario()" in corpo, (
            "a tela voltou a mandar um item sintético e a jogar fora o "
            "procedimento e o motivo que o backend sabe guardar"
        )
        assert "procedimento:" in corpo and "motivo:" in corpo

    def test_o_alvo_do_encaminhamento_nao_entra_na_impressao(self, html):
        """PDF e QR públicos seguem fora de escopo: o alvo é de W ≡ Y e
        conferência, não de impressão."""
        bloco = html[html.index("@media print {"):]
        bloco = bloco[:bloco.index("}\n\n")]
        assert "print-area-encaminhamento" not in bloco


class TestSaidaDoCongelamento:
    """AC4 — folha congelada precisa de gesto de saída, ou vira beco."""

    def test_existe_o_gesto_e_ele_limpa_os_canonicos(self, html):
        corpo = _corpo_da_funcao(html, "function novoEncaminhamento()")
        assert "_liberarFolhaEnc();" in corpo
        assert "'enc-especialidade'" in corpo and "'enc-cid'" in corpo, (
            "o gesto de recomeçar não limpa os hidden dos typeaheads — a "
            "especialidade e o CID do encaminhamento ANTERIOR sobreviveriam "
            "ao 'novo', que é pior que campo sujo"
        )
        assert corpo.index("form.reset();") < corpo.index("_liberarFolhaEnc();"), (
            "a folha é liberada ANTES da limpeza — repintaria com o que "
            "acabou de ser apagado"
        )
        assert 'id="btn-enc-novo"' in html


class TestAFolhaDoEncaminhamentoEscutaTudo:

    def test_delegacao_e_observacao_de_estrutura(self, html):
        corpo = _corpo_da_funcao(html, "function _initFolhaEnc()")
        assert "getElementById('enc-aba-emitir')" in corpo
        assert "raiz.addEventListener('input',  _repintarEncaminhamento);" in corpo
        assert "MutationObserver" in corpo
        assert "'enc-lista-itens'" in corpo
        assert "ligarFabAoEmitir('enc-fab', 'btn-enc-revisar', 'btn-enc-confirmar')" in corpo, (
            "o flutuante voltou a vigiar um gesto só — o outro botão de "
            "emissão ficaria descoberto"
        )


def _corpo_da_funcao(texto: str, assinatura: str) -> str:
    """Recorta o corpo de uma função pelo balanço de chaves.

    Terceira cópia deliberada (receita, exame, encaminhamento). Ao contrário
    do que a regra de duplicação diria, promover a helper de leitura estática
    a módulo compartilhado acoplaria três arquivos de guarda que hoje são
    independentes — e o valor deles é justamente poder ser lidos sozinhos.
    Se um quarto aparecer, a conta muda.
    """
    ini = texto.index(assinatura)
    abriu = texto.index("{", ini)
    prof = 0
    for i in range(abriu, len(texto)):
        if texto[i] == "{":
            prof += 1
        elif texto[i] == "}":
            prof -= 1
            if prof == 0:
                return texto[abriu : i + 1]
    raise AssertionError(f"função não fecha: {assinatura!r}")
