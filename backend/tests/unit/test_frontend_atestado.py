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
    """O documento oficial tem UM renderizador: o PDF do servidor."""

    def test_impressao_do_rascunho_tem_tarja_e_marca_dagua(self, html):
        corpo = _corpo_da_funcao(html, "function imprimirRascunhoAtestado")
        assert "RASCUNHO — SEM VALIDADE LEGAL" in corpo
        assert 'class="marca"' in corpo

    def test_impressao_do_rascunho_sem_assinatura_nem_protocolo(self, html):
        corpo = _corpo_da_funcao(html, "function imprimirRascunhoAtestado")
        assert "____" not in corpo, "rascunho não pode ter régua de assinatura"
        assert not re.search(r"Protocolo:\s*\$\{", corpo), "rascunho não pode exibir protocolo"

    def test_acao_primaria_leva_a_emissao_oficial(self, html):
        assert "usarRascunhoAtestado()" in html
        assert "btn-emitir-atestado" in html


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
