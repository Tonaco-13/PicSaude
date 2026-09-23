"""
test_frontend_atestado_vivo.py — guardas ESTÁTICAS do degenerado (ENG-024).

O smoke responde *"a folha do atestado bate com o domínio?"* e roda no gate de
navegador. Estas rodam em TODO PR e respondem *"a família fechou com quatro, e
o núcleo continua sem conhecer documento nenhum?"*.

A guarda que mais importa aqui é `TestASegundaFraseEstaDeclarada`: o
`atestado.js` constrói a frase pela segunda vez (a primeira é
`texto_atestado.py`), e este repositório já pagou por essa duplicação. O que a
torna aceitável é (a) estar DECLARADA no código, e (b) ter a guarda de
navegador que compara os dois. Se a declaração sumir, some também o aviso de
que existe uma dívida ali.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._leitura_estatica import corpo_da_funcao as _corpo_da_funcao

_RAIZ = Path(__file__).resolve().parents[3]
_HTML = _RAIZ / "prescritor.html"
_NUCLEO = _RAIZ / "documento-nucleo.js"
_AT = _RAIZ / "atestado.js"
_AT_CSS = _RAIZ / "atestado.css"
_TEXTO_DOMINIO = _RAIZ / "backend" / "app" / "domain" / "texto_atestado.py"

_GERADORES = {
    "receituario.js": _RAIZ / "receituario.js",
    "pedidoexame.js": _RAIZ / "pedidoexame.js",
    "encaminhamento.js": _RAIZ / "encaminhamento.js",
    "atestado.js": _AT,
}


@pytest.fixture(scope="module")
def html() -> str:
    return _HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def atestado() -> str:
    return _AT.read_text(encoding="utf-8")


class TestQuartoGeradorQuartoAlvo:

    def test_o_atestado_tem_gerador_proprio(self, atestado):
        assert "function renderAtestado(estado, modo)" in atestado
        assert "window.renderAtestado = renderAtestado;" in atestado
        assert _AT_CSS.exists()

    def test_o_atestado_tem_alvo_proprio_e_vazio(self, html):
        area = re.search(r'<div id="print-area-atestado"[^>]*>(.*?)</div>', html, re.S)
        assert area, "#print-area-atestado não existe"
        assert area.group(1).strip() == ""

    def test_os_quatro_alvos_convivem(self, html):
        for alvo in ("print-area", "print-area-exame",
                     "print-area-encaminhamento", "print-area-atestado"):
            assert f'id="{alvo}"' in html, f"o alvo {alvo} sumiu"

    def test_os_dois_alvos_do_atestado_saem_da_mesma_chamada(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarAtestado()")
        assert "const estado" in corpo
        assert corpo.count("Atestado.montar(") == 2
        assert "'folha-viva-atestado'" in corpo and "'print-area-atestado'" in corpo


class TestONucleoTemQuatroConsumidores:

    def test_os_quatro_geradores_consomem_o_nucleo(self):
        for nome, arq in _GERADORES.items():
            js = arq.read_text(encoding="utf-8")
            assert "window.DocumentoNucleo" in js, f"{nome} não consome o núcleo"
            assert "N.montar(" in js, f"{nome} não usa o `montar` do núcleo"
            assert "textoDoDocumento: N.textoDoDocumento," in js, (
                f"{nome} trouxe a própria régua de texto"
            )

    def test_cada_gerador_tem_o_seu_gancho_nomeado(self):
        esperado = {
            "receituario.js": '"rec"',
            "pedidoexame.js": '"exame"',
            "encaminhamento.js": '"enc"',
            "atestado.js": '"at"',
        }
        for nome, arq in _GERADORES.items():
            js = arq.read_text(encoding="utf-8")
            assert f"N.vocabulario({esperado[nome]})" in js, (
                f"{nome} perdeu o prefixo próprio — dois documentos com o "
                "mesmo gancho seriam duas guardas apontando para o mesmo lugar"
            )

    def test_o_nucleo_segue_sem_conhecer_documento_nenhum(self):
        """Quatro consumidores é onde um núcleo começa a ser tentado a
        'ajudar' um deles. A lista cresceu com os quatro títulos."""
        nucleo = _NUCLEO.read_text(encoding="utf-8")
        for estranho in ("Receituário", "Pedido de Exames", "Encaminhamento Médico",
                         "Atesto", "ATESTADO", "posologia", "TUSS", "finalidade"):
            assert estranho not in nucleo, (
                f"{estranho!r} vazou para o núcleo na quarta onda"
            )

    def test_o_atestado_nao_conhece_os_irmaos(self, atestado):
        codigo = re.sub(r"/\*.*?\*/", "", atestado, flags=re.S)
        codigo = re.sub(r"//[^\n]*", "", codigo)
        for estranho in ("Receituário", "posologia", "TUSS", "prioridade",
                         "Pedido de Exames", "destinatario"):
            assert estranho not in codigo, (
                f"{estranho!r} apareceu no CÓDIGO do gerador do ATESTADO"
            )


class TestASegundaFraseEstaDeclarada:
    """A dívida que este PR contrai, e o que a torna aceitável.

    `atestado.js` constrói a frase pela segunda vez — a primeira é
    `texto_atestado.py`. O repositório já pagou por essa duplicação: o rascunho
    e o PDF divergiam, e o profissional conferia um texto e assinava outro.
    O que impede a recaída não é disciplina, é a guarda de navegador — e o que
    impede alguém de esquecer que a dívida existe é a declaração no código.
    """

    def test_o_codigo_declara_que_e_uma_transcricao(self, atestado):
        assert "texto_atestado.py" in atestado, (
            "o gerador do atestado não diz de onde a frase vem — sem isso, a "
            "próxima pessoa a mexer nela não sabe que existe um par no servidor"
        )
        assert "TestFolhaEquivaleAoDominio" in atestado, (
            "o gerador não aponta para a guarda que o segura"
        )

    def test_a_fonte_do_dominio_segue_intocada(self):
        """§4: `texto_atestado.py` é intocado. Se este PR o tivesse alterado, a
        guarda folha ≡ domínio estaria comparando a folha com algo que a
        própria PR mudou — e provaria nada."""
        assert _TEXTO_DOMINIO.exists()
        fonte = _TEXTO_DOMINIO.read_text(encoding="utf-8")
        assert "def corpo_atestado(" in fonte
        assert "FONTE ÚNICA do texto" in fonte

    def test_a_transcricao_cobre_os_dois_ramos_e_as_quatro_clausulas(self, atestado):
        corpo = _corpo_da_funcao(atestado, "function clausulaClinica(indicacao, cid)")
        assert "em razão de quadro clínico compatível com" in corpo
        assert "(CID " in corpo
        principal = _corpo_da_funcao(atestado, "function corpoAtestado(estado, paraGuarda)")
        assert "esteve sob cuidados" in principal, "o ramo de afastamento sumiu"
        assert "compareceu a atendimento" in principal, "o ramo de comparecimento sumiu"

    def test_o_corpo_e_exposto_para_a_guarda(self, atestado):
        assert "corpoAtestado: (estado) => corpoAtestado(estado, true).texto," in atestado, (
            "sem expor o corpo puro, a guarda folha ≡ domínio não tem o que "
            "comparar"
        )


class TestOConselhoMudaODocumento:
    """AC7 — espelho de `domain/conselho_profissional.py`."""

    def test_os_dois_conselhos_estao_declarados(self, atestado):
        corpo = atestado[atestado.index("const CONSELHOS = {"):]
        corpo = corpo[:corpo.index("\n  };") + 4]
        for esperado in ('sigla: "CRM"', 'sigla: "CRO"',
                         '"ATESTADO MÉDICO"', '"ATESTADO ODONTOLÓGICO"',
                         '"médicos"', '"odontológicos"',
                         '"médico"', '"odontológico"'):
            assert esperado in corpo, f"{esperado} sumiu do mapa de conselhos"

    def test_conselho_desconhecido_cai_no_padrao(self, atestado):
        corpo = _corpo_da_funcao(atestado, "function conselhoDe(id)")
        assert "CONSELHOS.CFM" in corpo, (
            "conselho não reconhecido precisa cair no padrão (CFM), como o "
            "`CONSELHO_PADRAO` do domínio — não em `undefined`"
        )


class TestOFluxoDoAtestadoNaoMuda:
    """§4 — `pdf_atestado.py` e o endpoint de PDF intocados."""

    def test_o_carimbo_acontece_nos_dois_fluxos(self, html):
        digital = _corpo_da_funcao(html, "async function emitirAtestado()")
        assert "_carimbarAtestado(d, true);" in digital
        fisico = _corpo_da_funcao(html, "async function imprimirAtestadoFisico()")
        assert "_carimbarAtestado(d, false);" in fisico

    def test_o_fisico_continua_pedindo_o_pdf_ao_servidor(self, html):
        corpo = _corpo_da_funcao(html, "async function imprimirAtestadoFisico()")
        assert "/atestados/fisica" in corpo
        assert "'/pdf'" in corpo, "o PDF oficial deixou de vir do backend"

    def test_o_alvo_do_atestado_nao_entra_na_impressao(self, html):
        bloco = html[html.index("@media print {"):]
        bloco = bloco[:bloco.index("}\n\n")]
        assert "print-area-atestado" not in bloco


class TestAFolhaDoAtestadoEscutaTudo:

    def test_delegacao_e_o_fab_variadico(self, html):
        corpo = _corpo_da_funcao(html, "function _initFolhaAtestado()")
        assert "getElementById('submod-atestado')" in corpo
        assert "raiz.addEventListener('input',  _repintarAtestado);" in corpo
        assert "MutationObserver" in corpo
        assert (
            "ligarFabAoEmitir(\n                'at-fab', 'btn-emitir-atestado', "
            "'btn-imprimir-atestado-fisico')" in corpo
            or "'at-fab', 'btn-emitir-atestado', 'btn-imprimir-atestado-fisico'" in corpo
        ), (
            "o flutuante do atestado precisa vigiar os DOIS gestos (emitir "
            "digital e imprimir físico) — a versão variádica que o "
            "encaminhamento pediu ao núcleo serve aqui sem mudança"
        )

    def test_o_cpf_da_folha_e_mascarado(self, html):
        corpo = _corpo_da_funcao(html, "function _cpfMascaradoAtestado(valor)")
        assert ".***.***." in corpo, (
            "a folha voltaria a expor o CPF inteiro — o PDF oficial mascara"
        )


class TestPapelEmBrancoDeVerdade:
    """A lição da receita, na ordem inversa — e por isso fácil de repetir.

    Na receita o defeito era `_liberarFolhaViva()` ANTES do `.reset()`: a
    folha era repintada com dados que o `.reset()` ainda ia apagar. O
    `limparAtestado()` não usa `.reset()` — apaga campo a campo —, mas a
    armadilha é a mesma: enquanto `_atestadoEmitidoEstado` existir, o repinte
    é congelado; liberá-lo no meio da limpeza repinta a folha com o formulário
    ainda meio cheio.

    ESTÁTICA, e não de navegador, pelo mesmo motivo que na receita: em DEMO o
    lock M-D dispara um `input` real que repinta por acidente e faria o teste
    de tela passar com o defeito presente.
    """

    def test_a_folha_e_liberada_e_e_a_ultima_coisa(self, html):
        corpo = _corpo_da_funcao(html, "function limparAtestado()")
        assert "_liberarFolhaAtestado();" in corpo, (
            "limpar o formulário deixaria a folha exibindo o atestado "
            "anterior — e um atestado novo nasceria debaixo do papel velho"
        )
        for antes in ("_retravarCidadaoDemo(", "_aoMudarTipoAtestado();",
                      "ia-atestado-container"):
            assert corpo.index(antes) < corpo.index("_liberarFolhaAtestado();"), (
                f"{antes} roda DEPOIS de liberar a folha — o repinte pegaria "
                "o formulário no meio da limpeza"
            )

    def test_o_estado_emitido_congela_a_repintura(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarAtestado()")
        assert "_atestadoEmitidoEstado ||" in corpo, (
            "sem o congelamento, digitar depois de emitir reescreveria o "
            "documento emitido (§1)"
        )
