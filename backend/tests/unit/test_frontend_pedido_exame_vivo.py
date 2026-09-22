"""
test_frontend_pedido_exame_vivo.py — guardas ESTÁTICAS da família (ENG-022).

POR QUE ESTÁTICAS, SE O W ≡ Y DO EXAME JÁ TEM TESTE DE NAVEGADOR
-----------------------------------------------------------------
Porque respondem perguntas diferentes, e só estas rodam em TODO PR.

O smoke responde *"os dois alvos do exame renderizam igual?"*. Este arquivo
responde *"a família continua sendo família?"* — o núcleo tem dois
consumidores, cada documento tem o seu gerador, cada objeto tem o seu alvo de
carimbo. É a estrutura que o parecer adjudicou, e ela pode ser desfeita por um
PR que deixe o W ≡ Y verde no caminho: basta alguém fundir as duas anatomias
numa função com bandeiras, e os dois alvos continuariam batendo — batendo num
documento que finge ser dois.

Mesma disciplina de `test_frontend_receita_viva.py`.
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
_EXAME_CSS = _RAIZ / "pedidoexame.css"


@pytest.fixture(scope="module")
def html() -> str:
    return _HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def exame() -> str:
    return _EXAME.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nucleo() -> str:
    return _NUCLEO.read_text(encoding="utf-8")


class TestUmGeradorPorDocumento:
    """A adjudicação que este PR não pode desfazer no futuro."""

    def test_o_exame_tem_gerador_proprio(self, exame):
        assert "function renderPedidoExame(estado, modo)" in exame
        assert "window.renderPedidoExame = renderPedidoExame;" in exame
        assert _EXAME_CSS.exists()

    def test_o_receituario_nao_virou_documento_parametrizado(self):
        """*"Duas anatomias numa função só é a dupla posse pela porta dos
        fundos"*. O receituário segue gerando receituário, e só."""
        receita = _RECEITA.read_text(encoding="utf-8")
        for estranho in ("Pedido de Exames", "TUSS", "SIGTAP", "prioridade"):
            assert estranho not in receita, (
                f"{estranho!r} apareceu no gerador da RECEITA — as duas "
                "anatomias estão se misturando"
            )

    def test_o_gerador_do_exame_nao_conhece_receita(self, exame):
        # Fora dos comentários: o cabeçalho do arquivo EXPLICA a fronteira
        # citando a receita ("o receituário tem posologia e via"), e uma
        # guarda que se deixa enganar pela própria justificativa não guarda
        # nada — nem no sentido de acusar, nem no de absolver.
        codigo = re.sub(r"/\*.*?\*/", "", exame, flags=re.S)
        codigo = re.sub(r"//[^\n]*", "", codigo)
        for estranho in ("Receituário", "posologia", "med-card", "fármaco"):
            assert estranho not in codigo, (
                f"{estranho!r} apareceu no CÓDIGO do gerador do EXAME"
            )


class TestONucleoTemDoisConsumidores:
    """Núcleo órfão vira parametrização de conveniência — e, adiante, a
    desculpa para fundir anatomias. Por isso ele nasceu com dois."""

    def test_os_dois_geradores_consomem_o_nucleo(self, exame):
        receita = _RECEITA.read_text(encoding="utf-8")
        for nome, js in (("receituario.js", receita), ("pedidoexame.js", exame)):
            assert "window.DocumentoNucleo" in js, f"{nome} não consome o núcleo"
            assert "N.vocabulario(" in js, f"{nome} não usa o vocabulário do núcleo"
            assert "N.montar(" in js, f"{nome} não usa o `montar` do núcleo"

    def test_a_regua_do_w_equiv_y_e_uma_so(self, exame):
        """Três documentos com três réguas seriam três promessas diferentes
        com o mesmo nome."""
        receita = _RECEITA.read_text(encoding="utf-8")
        for nome, js in (("receituario.js", receita), ("pedidoexame.js", exame)):
            assert "textoDoDocumento: N.textoDoDocumento," in js, (
                f"{nome} trouxe a própria régua de texto em vez de usar a do núcleo"
            )

    def test_as_licoes_do_degenerado_estao_no_contrato(self, nucleo):
        """Modo inline e região nomeada entram ANTES de existir quem as peça:
        reforma de núcleo com três clientes vivos é onde se quebram os outros
        dois."""
        assert "function lacuna(texto, opcoes)" in nucleo
        assert "opcoes.inline" in nucleo
        assert "doc-lacuna-inline" in nucleo
        assert 'querySelectorAll("[data-bloco]")' in nucleo, (
            "a tinta deixou de trabalhar por região nomeada"
        )

    def test_o_nucleo_nao_conhece_documento_nenhum(self, nucleo):
        for estranho in ("Receituário", "Pedido de Exames", "posologia", "TUSS"):
            assert estranho not in nucleo, (
                f"{estranho!r} vazou para o núcleo — ele não pode ganhar o "
                "direito de escolher anatomia"
            )


class TestUmAlvoPorObjeto:
    """Adjudicação 1: nada de alvo multi-objeto chaveado pela aba ativa —
    imprimir é momento de verdade, e a chave de submódulo seria uma variável
    a mais e falível no caminho."""

    def test_o_exame_tem_print_area_propria_e_vazia(self, html):
        area = re.search(r'<div id="print-area-exame"[^>]*>(.*?)</div>', html, re.S)
        assert area, "#print-area-exame não existe"
        assert area.group(1).strip() == "", (
            "#print-area-exame ganhou marcação própria — ele é ALVO da função "
            "geradora do exame, não um segundo template"
        )

    def test_o_print_area_da_receita_segue_da_receita(self, html):
        area = re.search(r'<div id="print-area"[^>]*>(.*?)</div>', html, re.S)
        assert area and area.group(1).strip() == ""

    def test_os_dois_alvos_do_exame_saem_da_mesma_chamada(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarPedidoExame()")
        assert "const estado" in corpo, "os alvos precisam partir do MESMO objeto"
        assert corpo.count("PedidoExame.montar(") == 2
        assert "'folha-viva-exame'" in corpo and "'print-area-exame'" in corpo


class TestOFluxoFisicoDoExameNaoMuda:
    """AC9 — o papel oficial continua nascendo no servidor."""

    def test_o_print_area_do_exame_nao_entra_na_impressao(self, html):
        """Só o `#print-area` da receita é revelado no `@media print`. O do
        exame é alvo de W ≡ Y e conferência: imprimir o pedido continua
        baixando o PDF do backend."""
        bloco = html[html.index("@media print {"):]
        bloco = bloco[:bloco.index("}\n\n")]
        assert "#print-area, #print-area *" in bloco
        assert "print-area-exame" not in bloco, (
            "o alvo do exame entrou no @media print — isso MUDARIA o fluxo "
            "físico, que esta onda declarou intocado"
        )

    def test_a_impressao_fisica_continua_pedindo_o_pdf_ao_servidor(self, html):
        corpo = _corpo_da_funcao(html, "async function imprimirPedidoFisico()")
        assert "/pedidos-exame/fisica" in corpo
        assert "'/pdf'" in corpo, "o PDF oficial deixou de vir do backend"


class TestSeloDeCidCanonicoDoExame:
    """AC6 — o selo reflete o hidden do typeahead, nunca o texto digitado."""

    def test_o_selo_le_o_hidden_e_nao_a_indicacao(self, html):
        corpo = _corpo_da_funcao(html, "function _cidsEscolhidosExame()")
        assert "exam-cid-escolhido" in corpo
        assert "exam-indicacao" not in corpo, (
            "o selo de CID do exame passou a olhar o texto da indicação"
        )


class TestGuardasQueViajamComOExame:
    """AC7 — M-D e A2 no formulário do exame."""

    def test_o_cpf_do_exame_mantem_mascara_e_lock(self, html):
        campo = re.search(r'<input[^>]*id="exam-pac-cpf"[^>]*>', html, re.S)
        assert campo and 'data-tipo="cpf"' in campo.group(0)
        assert "cpf-input" in campo.group(0)
        assert "_retravarCidadaoDemo('exam-pac-nome', 'exam-pac-cpf');" in html


class TestAFolhaDoExameEscutaTudo:
    """AC1 — delegação + observação de estrutura, como na receita."""

    def test_a_folha_escuta_por_delegacao_na_raiz_do_submodulo(self, html):
        corpo = _corpo_da_funcao(html, "function _initFolhaExame()")
        assert "getElementById('submod-exames')" in corpo
        assert "raiz.addEventListener('input',  _repintarPedidoExame);" in corpo
        assert "MutationObserver" in corpo
        assert "'lista-exames'" in corpo and "'ia-cid-exame-chips'" in corpo
        assert "ligarFabAoEmitir('exame-fab', 'btn-emitir-exame')" in corpo

    def test_a_normalizacao_grava_dado_e_nao_so_pixel(self, html):
        """A folha lê categoria e preparo de campos, não do HTML do bloco azul
        — depender da aparência de outro componente é acoplamento frágil."""
        assert 'class="exame-categoria"' in html
        assert 'class="exame-preparo"' in html
        corpo = _corpo_da_funcao(html, "function _renderizarNormalizacaoExame(n, data)")
        assert "querySelector('.exame-categoria')" in corpo
        assert "querySelector('.exame-preparo')" in corpo


class TestOPedidoEmitidoCongela:
    """AC4 — e aqui importa MAIS que na receita: o fluxo do exame limpa o
    formulário logo depois de emitir."""

    def test_o_carimbo_congela_antes_da_limpeza(self, html):
        corpo = _corpo_da_funcao(html, "async function emitirPedidoExame(e)")
        assert "_carimbarPedidoExame(data, true);" in corpo
        assert corpo.index("_carimbarPedidoExame(data, true);") < corpo.index(
            "document.getElementById('lista-exames').innerHTML = '';"
        ), (
            "o carimbo acontece DEPOIS da limpeza do formulário — a folha "
            "carimbada se esvaziaria diante de quem acabou de emitir"
        )

    def test_o_estado_emitido_congela_a_repintura(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarPedidoExame()")
        assert "_pedidoExameEmitido ||" in corpo


def _corpo_da_funcao(html: str, assinatura: str) -> str:
    """Recorta o corpo de uma função pelo balanço de chaves.

    Mesma cópia deliberada de `test_frontend_receita_viva.py`: helper de
    leitura estática, sem dono próprio. Promovê-lo a módulo com dois
    chamadores seria inventar biblioteca.
    """
    ini = html.index(assinatura)
    abriu = html.index("{", ini)
    prof = 0
    for i in range(abriu, len(html)):
        if html[i] == "{":
            prof += 1
        elif html[i] == "}":
            prof -= 1
            if prof == 0:
                return html[abriu : i + 1]
    raise AssertionError(f"função não fecha: {assinatura!r}")
