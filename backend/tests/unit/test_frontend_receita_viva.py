"""
test_frontend_receita_viva.py — guardas ESTÁTICAS do template único (ENG-018).

POR QUE ESTE ARQUIVO EXISTE, SE O W ≡ Y JÁ TEM TESTE DE NAVEGADOR
-----------------------------------------------------------------
Porque os dois respondem perguntas diferentes, e só um deles roda em TODO PR.

`tests/browser/test_eng018_receita_viva.py` responde *"os dois alvos renderizam
igual?"* — e roda no gate de navegador (PR que toca `**.html` + nightly).

Este arquivo responde *"ainda existe UM template?"* — e roda no gate de sempre.
A diferença importa: alguém pode reintroduzir marcação própria no `#print-area`
e mantê-la, por um tempo, idêntica à da função geradora. O W ≡ Y passaria
verde, e a duplicação só apareceria no dia em que derivasse — que é exatamente
o "mentira gradual" que o §3 do desenho nomeia como a pior espécie. A guarda
estrutural pega no ato, não no dia da divergência.

Mesma disciplina de `test_frontend_atestado.py`: leitura estática, barata, da
CLASSE do defeito.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._leitura_estatica import corpo_da_funcao as _corpo_da_funcao

_RAIZ = Path(__file__).resolve().parents[3]
_HTML = _RAIZ / "prescritor.html"
_JS = _RAIZ / "receituario.js"
_NUCLEO = _RAIZ / "documento-nucleo.js"
_CSS = _RAIZ / "receituario.css"


@pytest.fixture(scope="module")
def html() -> str:
    return _HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js() -> str:
    return _JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nucleo() -> str:
    return _NUCLEO.read_text(encoding="utf-8")


class TestOComponenteExiste:

    def test_a_funcao_geradora_mora_em_arquivo_proprio(self, js):
        assert "function renderReceituario(estado, modo)" in js
        assert "window.renderReceituario = renderReceituario;" in js

    def test_a_folha_carrega_o_componente_e_o_seu_desenho(self, html):
        assert '<script src="receituario.js"></script>' in html
        assert '<link rel="stylesheet" href="receituario.css">' in html
        assert _CSS.exists()

    def test_o_nucleo_carrega_antes_dos_geradores(self, html):
        """ENG-022 — quem desenha um papel específico depende do vocabulário
        comum; carregar na ordem inversa deixaria `DocumentoNucleo` indefinido
        no instante em que o gerador o consome."""
        assert '<script src="documento-nucleo.js"></script>' in html
        assert _NUCLEO.exists()
        assert html.index("documento-nucleo.js") < html.index('src="receituario.js"')

    def test_os_dois_modos_sao_declarados(self, js, nucleo):
        """Os modos mudaram de casa na ENG-022 — e esta guarda mudou junto.

        Até o ENG-020 os dois literais eram declarados no `receituario.js`, e
        era lá que esta asserção olhava. A extração do núcleo os levou para
        `documento-nucleo.js`, onde passaram a ser o contrato W ≡ Y de TODOS
        os documentos — receita, pedido de exame e os que vierem.

        Esta é a ÚNICA adaptação que a extração exigiu em toda a suíte da
        Receita Viva, e ela não afrouxa nada: o que se exigia era "os dois
        modos são declarados", não "são declarados neste arquivo". Agora a
        guarda exige as duas metades — que o núcleo os declare, e que a
        receita os CONSUMA em vez de redeclarar (duplicar o par seria a porta
        para um documento rodar num modo que o outro não conhece).
        """
        assert 'RASCUNHO: "rascunho"' in nucleo
        assert 'CARIMBO: "carimbo"' in nucleo
        assert "const MODOS = N.MODOS;" in js, (
            "a receita voltou a declarar os modos por conta própria"
        )


class TestTemplateUnico:
    """A peça central: UMA função geradora, DOIS alvos."""

    def test_print_area_nao_tem_marcacao_propria(self, html):
        area = re.search(r'<div id="print-area"[^>]*>(.*?)</div>', html, re.S)
        assert area, "#print-area sumiu do prescritor.html"
        assert area.group(1).strip() == "", (
            "#print-area voltou a ter marcação própria. Ele é ALVO da função "
            "geradora (receituario.js) — dois templates do mesmo documento vão "
            "derivar, e o 'zero surpresa' vira mentira gradual "
            "(DESENHO-RECEITA-VIVA.md §3)."
        )

    def test_nenhum_campo_do_documento_e_preenchido_por_id(self, html):
        """Os `getElementById('print-…')` eram a porta por onde o segundo
        template entrava, campo a campo. Ela está fechada."""
        vazados = re.findall(r"getElementById\(\s*['\"]print-[a-z-]+['\"]", html)
        assert not vazados, (
            f"o documento voltou a ser preenchido campo a campo por id: {vazados}"
        )

    def test_a_pagina_nao_monta_receituario_por_conta_propria(self, html):
        """Nenhum 'Receituário Médico' escrito à mão na tela: o cabeçalho do
        documento tem UM dono."""
        assert html.count("Receituário Médico") == 0, (
            "o cabeçalho do receituário reapareceu no prescritor.html — ele "
            "pertence à função geradora, não à página"
        )

    def test_os_dois_alvos_saem_da_mesma_chamada(self, html):
        corpo = _corpo_da_funcao(html, "function _repintarReceituario()")
        assert "const estado" in corpo, "os alvos precisam partir do MESMO objeto"
        assert corpo.count("Receituario.montar(") == 2, (
            "esperado exatamente dois alvos (folha viva + print-area) a partir "
            "de um único estado"
        )
        assert "'folha-viva'" in corpo and "'print-area'" in corpo


class TestOCarimboNaoNavega:
    """AC4 — emitir carimba a folha à vista; não troca de tela."""

    def test_a_confirmacao_nao_e_mais_uma_tela(self, html):
        assert 'id="tela-sucesso"' not in html, (
            "a `tela-sucesso` voltou: emitir passaria a NAVEGAR, e a folha que "
            "o prescritor tinha diante dos olhos sumiria no ato da emissão"
        )
        assert 'id="painel-emissao"' in html

    def test_o_carimbo_congela_o_estado_emitido(self, html):
        corpo = _corpo_da_funcao(html, "function _carimbarEmissao(rec, isDigital, nivelFormal)")
        assert "_receituarioEmitido = _estadoDaReceitaEmitida(" in corpo
        assert "_repintarReceituario();" in corpo
        assert "esconderTudo()" not in corpo, (
            "o carimbo voltou a esconder a tela — AC4: a folha não sai de vista"
        )

    def test_o_hash_de_integridade_nao_e_mais_descartado(self, html):
        assert "novaReceitaObj.documento_hash" in html, (
            "o `documento_hash` da resposta de emissão voltou a ser jogado fora "
            "— é metade do carimbo (AC4)"
        )


class TestPapelEmBrancoDeVerdade:
    """Limpar o formulário tem de limpar a folha — e a ORDEM é o invariante.

    POR QUE ESTA GUARDA É ESTÁTICA, E NÃO DE NAVEGADOR
    --------------------------------------------------
    Inverter a ordem (`_liberarFolhaViva()` antes do `.reset()`) deixa na folha
    os dados do paciente ANTERIOR: o repintar lê o formulário, e nesse instante
    o formulário ainda está cheio. `.reset()` não dispara evento nenhum, então
    nada repinta depois.

    O smoke de navegador NÃO vê esse defeito: em DEMO, o lock M-D reaplica o
    cidadão canônico logo em seguida e dispara um `input` de verdade — que
    repinta por acidente e limpa a folha. Fora da vitrine esse evento não
    existe, e o defeito apareceria no consultório. É a mesma lição do gate que
    não enxerga o que só o seed produz: quando o ambiente de teste mascara o
    defeito, a guarda muda de camada em vez de desistir.
    """

    def test_liberar_a_folha_vem_depois_da_limpeza(self, html):
        for assinatura in ("function novaReceita()", "function irParaDashboard()"):
            corpo = _corpo_da_funcao(html, assinatura)
            assert "_liberarFolhaViva();" in corpo, (
                f"{assinatura} não devolve o papel em branco"
            )
            assert corpo.index(".reset();") < corpo.index("_liberarFolhaViva();"), (
                f"em {assinatura}, a folha é liberada ANTES da limpeza do "
                "formulário — ela repintaria com os dados que acabaram de ser "
                "apagados, e nada dispara um novo repintar depois do `.reset()`"
            )


class TestSeloDeCidCanonico:
    """AC6 — o selo reflete o hidden do typeahead, nunca o texto digitado."""

    def test_o_selo_le_o_hidden_e_nao_a_indicacao(self, html):
        corpo = _corpo_da_funcao(html, "function _cidsEscolhidosPrescricao()")
        assert "prescricao-cid-escolhido" in corpo
        assert "prescricao-indicacao" not in corpo, (
            "o selo de CID passou a olhar o texto da indicação — a folha não "
            "adivinha diagnóstico (AC6)"
        )


class TestGuardasQueViajamComOCampo:
    """AC7 — o CPF/CNI subiu de seção (martelada ①) levando as duas guardas."""

    def test_o_cpf_mantem_mascara_e_esta_na_identificacao(self, html):
        campo = re.search(r'<input[^>]*id="pac-chave"[^>]*>', html, re.S)
        assert campo, "campo `pac-chave` sumiu"
        assert 'data-tipo="cpf"' in campo.group(0), "máscara A2 caiu no transporte"
        assert "cpf-input" in campo.group(0)

        # Ancorado nos TÍTULOS das seções (`<h4>`), não no texto solto: o nome
        # das seções aparece também em comentário, e uma guarda que se deixa
        # enganar por comentário não guarda nada.
        bloco_paciente = html.index(">Identificação do Paciente</h4>")
        bloco_modo = html.index(">Modo de Emissão</h4>")
        assert bloco_paciente < html.index('id="pac-chave"') < bloco_modo, (
            "`pac-chave` não está entre o título da identificação do paciente e "
            "o bloco de modo de emissão (martelada ①)"
        )

    def test_o_lock_md_continua_travando_o_par(self, html):
        assert "CidadaoDemoFixo.travar('pac-nome', 'pac-chave');" in html
        assert "_retravarCidadaoDemo('pac-nome', 'pac-chave');" in html


class TestFolhaRobustaATeclaEAEstrutura:
    """AC1 — delegação + observação de estrutura."""

    def test_a_folha_escuta_por_delegacao_na_raiz_do_submodulo(self, html):
        corpo = _corpo_da_funcao(html, "function _initFolhaViva()")
        assert "getElementById('submod-receita')" in corpo
        assert "raiz.addEventListener('input',  _repintarReceituario);" in corpo
        assert "MutationObserver" in corpo, (
            "sem observar a estrutura, remover/recriar/limpar card de fármaco "
            "deixaria a folha desatualizada"
        )
        assert "'lista-medicamentos'" in corpo and "'ia-cid-prescricao-chips'" in corpo


class TestVitrineSemPromessaVazia:
    """ENG-020 §1.3 — a vitrine para de oferecer o que não existe.

    Martelo do Fabiano, 21/09: o cartão "Emissão Digital — Assinatura gov.br
    (Nuvem)", com botão ☁️ e a promessa "disponível em breve", saiu — não há
    despacho que sustente a data, e vitrine que promete o que não faz gasta a
    credibilidade do que ela de fato faz.

    ESTÁTICA, e não só de navegador, porque o gate de tela roda em PR de HTML
    e no nightly: a promessa pode voltar por um PR de backend que reponha o
    bloco de carona. Aqui ela é pega em todo PR.

    O QUE A GUARDA NÃO PROÍBE — e a distinção é o ponto: `labelAssinaturaModo`
    e `labelNivelFormal` continuam sabendo renderizar `gov_br_nuvem`, porque um
    documento JÁ EMITIDO naquele modo precisa seguir sendo lido corretamente.
    O que saiu foi a OFERTA, não o suporte (o domínio, os endpoints e o ledger
    estão intocados). Por isso a guarda mira em elementos de oferta, não na
    string solta.
    """

    _OFERTAS_PROIBIDAS = (
        "Entrar com gov.br",          # botão MORTO da tela de acesso (sem onclick)
        "Assinar em Nuvem",
        "Em Implantação",
        "disponível em breve",
        "assinaturaModo = 'gov_br_nuvem'",   # nenhum elemento seleciona o modo
    )

    def test_nenhuma_oferta_govbr_no_html_servido(self, html):
        sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        for oferta in self._OFERTAS_PROIBIDAS:
            assert oferta not in sem_comentarios, (
                f"a promessa {oferta!r} voltou ao prescritor.html. O bloco gov.br "
                "só retorna no dia do Ticket 21 (assinatura digital real)."
            )

    def test_o_que_funciona_permanece(self, html):
        """A retirada é cirúrgica: o ICP-Brasil, que tem modal e fluxo, fica."""
        assert "abrirModalCertificado(event)" in html
        assert "Meu certificado ICP-Brasil" in html
        assert 'id="btn-emitir"' in html

    def test_o_suporte_ao_modo_emitido_nao_foi_removido(self, html):
        """Um documento emitido em gov_br_nuvem continua legível — tirar a
        oferta não pode apagar a capacidade de LER o que já foi emitido."""
        assert "if (modo === 'gov_br_nuvem')" in html
        assert "'cfm_gov_br_pendente'" in html
