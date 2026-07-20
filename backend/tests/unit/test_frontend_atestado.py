"""
test_frontend_atestado.py — guardas estáticas do formulário de atestado.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O seletor de conselho não populava em produção e **o gate inteiro passou verde**:
a migração estava certa, o backend servia o catálogo certo, os contratos batiam.
O que quebrava era ORDEM DE EXECUÇÃO no `prescritor.html` — a chamada de bootstrap
vinha ~500 linhas ANTES da declaração `let _catalogoConselhos`, e o ReferenceError
da temporal dead zone estourava fora do try/catch. Sintoma: seletor vazio e MUDO,
com o caminho odontológico inalcançável. Um dentista emitiria ATESTADO MÉDICO sem
saber.

Nenhum teste pegou porque nenhum teste **abre a página e olha o `<select>`**.

O ideal seria um teste de navegador no gate. Como o projeto é Python e não tem
runner de browser, estas guardas cobrem a CLASSE do defeito de forma estática e
barata. Elas não substituem a verificação em navegador — só impedem a regressão
exata voltar despercebida.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_HTML = Path(__file__).resolve().parents[3] / "prescritor.html"


@pytest.fixture(scope="module")
def html() -> str:
    return _HTML.read_text(encoding="utf-8")


class TestOrdemDeInicializacao:
    """A regressão real: bootstrap antes da declaração `let` → TDZ."""

    def test_catalogo_declarado_antes_de_qualquer_uso(self, html):
        decl = html.index("let _catalogoConselhos")
        primeiro_uso = html.index("_montarSeletoresRegistroAtestado")
        assert decl < primeiro_uso, (
            "Bootstrap do seletor de conselho aparece ANTES de "
            "`let _catalogoConselhos` — temporal dead zone. O seletor fica vazio "
            "e silencioso, e o caminho odontológico some da tela."
        )

    def test_bootstrap_espera_o_dom(self, html):
        # O <select> precisa existir quando a função roda.
        assert "DOMContentLoaded', _montarSeletoresRegistroAtestado" in html


class TestFalhaVisivel:
    """Qualquer falha tem de virar aviso — nunca seletor vazio e mudo."""

    def test_montagem_do_seletor_tem_try_catch(self, html):
        corpo = _corpo_da_funcao(html, "async function _montarSeletoresRegistroAtestado")
        assert "try {" in corpo and "catch" in corpo, (
            "Sem try/catch, um erro inesperado deixa o seletor vazio SEM aviso — "
            "mesma classe do 'NULL silencioso' que o R4 combateu."
        )
        assert "_degradarSeletorConselho" in corpo

    def test_degradacao_avisa_que_sairia_como_medico(self, html):
        corpo = _corpo_da_funcao(html, "function _degradarSeletorConselho")
        assert "indisponível" in corpo and "médico" in corpo


class TestCamposObrigatorios:

    def test_municipio_marcado_required(self, html):
        campo = re.search(r'<input[^>]*id="atestado-municipio"[^>]*>', html, re.S)
        assert campo and "required" in campo.group(0), (
            "Município é exigido pelo CFM e o backend devolve 422 — marcar required "
            "evita o profissional descobrir só no submit."
        )


class TestRascunhoNaoPareceDocumento:
    """O documento oficial tem UM renderizador: o PDF do servidor.

    O HTML impresso saiu de dentro de `imprimirRascunhoAtestado` para
    `_htmlRascunhoAtestado` quando a impressão trocou de veículo (pop-up →
    iframe). As guardas seguiram o conteúdo: o que importa é que o papel de
    trabalho continue parecendo papel de trabalho, não em que função ele mora.
    """

    def test_impressao_do_rascunho_tem_tarja_e_marca_dagua(self, html):
        corpo = _corpo_da_funcao(html, "function _htmlRascunhoAtestado")
        assert "RASCUNHO — SEM VALIDADE LEGAL" in corpo
        assert 'class="marca"' in corpo

    def test_impressao_do_rascunho_sem_assinatura_nem_protocolo(self, html):
        corpo = _corpo_da_funcao(html, "function _htmlRascunhoAtestado")
        assert "____" not in corpo, "rascunho não pode ter régua de assinatura"
        assert not re.search(r"Protocolo:\s*\$\{", corpo), "rascunho não pode exibir protocolo"

    def test_acao_primaria_leva_a_emissao_oficial(self, html):
        assert "usarRascunhoAtestado()" in html
        assert "btn-emitir-atestado" in html


class TestImpressaoNuncaFalhaCalada:
    """O defeito que Fabiano encontrou: clicar em "Imprimir rascunho" e NADA.

    `window.open('', '_blank', …)` devolve `null` quando o bloqueador de pop-up
    age — o padrão em domínio não confiável, como o 127.0.0.1 do teste local. O
    código saía por `if (!win) return;`: sem impressão, sem erro, sem pista.
    Funcionava em picsaude.com.br (domínio confiável) e não na máquina dele.

    Mesma classe do seletor de conselho vazio (#103) e a mesma doutrina do R4:
    falha alta, nunca silêncio. A correção tem duas camadas — o iframe, que não
    é bloqueável, e o aviso visível, para o que ainda assim escapar.

    A PROVA de que funciona com o bloqueador ativo é o smoke de navegador
    (`tests/browser/test_smokes.py::TestImpressaoDoRascunho`), que estas guardas
    estáticas não substituem.
    """

    def test_nenhuma_impressao_depende_de_window_open(self, html):
        assert "window.open" not in _sem_comentarios(html), (
            "window.open volta a ser o veículo de impressão. Com bloqueador de "
            "pop-up ele devolve null e o clique não faz nada. Use o iframe "
            "oculto (_imprimirDocumentoAuxiliar)."
        )

    def test_veiculo_e_iframe_no_proprio_documento(self, html):
        corpo = _corpo_da_funcao(html, "function _imprimirDocumentoAuxiliar")
        assert "createElement('iframe')" in corpo
        assert "picsaude-print-frame" in corpo

    def test_iframe_e_renderizado_e_nao_display_none(self, html):
        """`display:none` imprime página em branco em vários navegadores."""
        corpo = _sem_comentarios(_corpo_da_funcao(html, "function _imprimirDocumentoAuxiliar"))
        assert "display:none" not in corpo.replace(" ", "")

    def test_todo_caminho_de_falha_avisa(self, html):
        """Nenhum `return` do fluxo de impressão sai calado.

        O chamador é quem avisa: a função-veículo devolve false e
        `imprimirRascunhoAtestado` transforma isso em texto na tela.
        """
        corpo = _corpo_da_funcao(html, "function imprimirRascunhoAtestado")
        assert "_avisarFalhaDeImpressao" in corpo
        assert "bloqueou a impressão" in corpo, (
            "O aviso precisa dizer o que aconteceu E o que fazer (Ctrl+P)."
        )

    def test_aviso_tem_slot_no_dom_e_e_anunciado(self, html):
        assert 'id="atestado-print-aviso"' in html
        slot = re.search(r'<div id="atestado-print-aviso"[^>]*>', html)
        assert slot and 'role="alert"' in slot.group(0), (
            "O aviso precisa ser anunciado por leitor de tela — quem não vê a "
            "tela também precisa saber que a impressão falhou."
        )

    def test_preview_ausente_tambem_avisa(self, html):
        """Antes: `if (!el) return;` — o segundo return mudo da mesma função."""
        corpo = _corpo_da_funcao(html, "function imprimirRascunhoAtestado")
        trecho = corpo[:corpo.index("const texto")]
        assert "_avisarFalhaDeImpressao" in trecho


class TestImpressaoDaPaginaPrincipal:
    """`imprimirDireto` e `imprimirPedidoFisico` NÃO têm o mesmo defeito.

    Verificado: as duas chamam `window.print()` na própria página, sem abrir
    janela nenhuma — não há o que um bloqueador de pop-up intercepte. Esta
    guarda existe para que continuem assim: se alguém as migrar para janela
    nova, cai no mesmo buraco.
    """

    @pytest.mark.parametrize(
        "funcao", ["async function imprimirDireto", "function imprimirPedidoFisico"]
    )
    def test_imprimem_a_propria_pagina(self, html, funcao):
        corpo = _corpo_da_funcao(html, funcao)
        assert "window.print()" in corpo
        assert "window.open" not in corpo


def _sem_comentarios(fonte: str) -> str:
    """Remove comentários `/* */` e `//` — guarda de código não lê prosa.

    Sem isto, uma guarda como "não use window.open" quebra ao explicar NO
    COMENTÁRIO por que window.open foi abandonado. O teste passaria a punir a
    documentação da própria correção, que é o contrário do que se quer.

    Heurística, não parser: basta para asserções de presença/ausência.
    """
    fonte = re.sub(r"/\*.*?\*/", "", fonte, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", fonte)


def _corpo_da_funcao(html: str, assinatura: str) -> str:
    """Trecho do fonte a partir da assinatura da função até a próxima declaração.

    Heurística deliberadamente simples: estas guardas são de presença/ausência de
    texto, não análise sintática. Um parser de JS aqui seria mais frágil que o
    problema que resolve.
    """
    i = html.index(assinatura)
    j = html.find("\n        function ", i + len(assinatura))
    k = html.find("\n        async function ", i + len(assinatura))
    fim = min(x for x in (j, k, len(html)) if x > 0)
    return html[i:fim]
