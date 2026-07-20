"""
test_atestado_espelho.py
========================
TICKET-ATESTADO-RASCUNHO-ESPELHO — o rascunho é espelho do documento oficial.

O DEFEITO QUE ESTES TESTES FECHAM
---------------------------------
Existiam dois construtores do texto do atestado, e eles divergiam: o profissional
conferia uma frase no rascunho da tela e assinava outra no PDF. Não era um
documento falso — era um FALSO ESPELHO, que é pior, porque o profissional confia
nele para conferir.

O teste central é `TestEspelho::test_corpo_do_rascunho_igual_ao_do_pdf`: ele
captura o texto que o ReportLab de fato recebe (espionando `Paragraph`) e compara
com o corpo do rascunho, ignorando só a marcação de ênfase. É esse teste que fecha
a CLASSE do defeito — qualquer futura divergência entre os dois renderizadores
falha aqui, mesmo que ninguém se lembre deste ticket.
"""
from __future__ import annotations

import re

import pytest

from app.ai_documental.ia_documental import validar_atestado
from app.ai_documental.templates_atestado import TITULO_RASCUNHO, renderizar_atestado
from app.domain import pdf_atestado as mod_pdf
from app.domain.pdf_atestado import gerar_pdf_atestado
from app.domain.texto_atestado import Paragrafo, Trecho, corpo_atestado


# ---------------------------------------------------------------------------
# Fixtures — o MESMO atestado, alimentando os dois caminhos
# ---------------------------------------------------------------------------

_ATESTADO = {
    "nome_paciente":     "João da Silva",
    "finalidade":        "trabalhistas",
    "dias_afastamento":  3,
    "data_documento":    "2026-07-19",
    "indicacao_clinica": "quadro gripal agudo",
    "codigo_cid":        "J11",
    "municipio_emissao": "Recife",
    "conselho":          "CFM",
    "uf_registro":       "PE",
    "registro_profissional": "12345",
    "nome_profissional": "Dra. Ana Ribeiro",
    "hora_inicio":       "08:30",
    "hora_fim":          "10:00",
}


def _rascunho(**overrides):
    """Rascunho renderizado pelo caminho da IA Documental."""
    dados = {**_ATESTADO, **overrides}
    return renderizar_atestado(
        paciente_nome=dados["nome_paciente"],
        finalidade=dados["finalidade"],
        dias_afastamento=dados["dias_afastamento"],
        data_documento=dados["data_documento"],
        nome_profissional=dados["nome_profissional"],
        registro_profissional=dados["registro_profissional"],
        indicacao_clinica=dados["indicacao_clinica"],
        codigo_cid=dados["codigo_cid"],
        municipio_emissao=dados["municipio_emissao"],
        conselho=dados["conselho"],
        uf_registro=dados["uf_registro"],
        hora_inicio=dados["hora_inicio"],
        hora_fim=dados["hora_fim"],
        observacao_complementar=dados.get("observacao_complementar"),
    )


def _paragrafos_do_pdf(monkeypatch, **overrides) -> list[str]:
    """Textos que o PDF oficial REALMENTE entrega ao ReportLab.

    Espiona `Paragraph` em vez de reimplementar a montagem: se alguém voltar a
    escrever a frase dentro do `gerar_pdf_atestado`, o espião vê o texto novo e o
    espelho quebra — que é exatamente o alarme que queremos.
    """
    capturados: list[str] = []
    original = mod_pdf.Paragraph

    def _espiao(texto, *args, **kwargs):
        capturados.append(texto)
        return original(texto, *args, **kwargs)

    monkeypatch.setattr(mod_pdf, "Paragraph", _espiao)

    dados = {**_ATESTADO, **overrides}
    gerar_pdf_atestado(
        protocolo="00000000-0000-0000-0000-000000000001",
        status="emitido",
        tipo_emissao="nova",
        finalidade=dados["finalidade"],
        indicacao_clinica=dados["indicacao_clinica"],
        codigo_cid=dados["codigo_cid"],
        dias_afastamento=dados["dias_afastamento"],
        data_documento=dados["data_documento"],
        data_validade=None,
        assinatura_modo=None,
        assinatura_hash=None,
        nome_prescritor=dados["nome_profissional"],
        cns_prescritor="123456789012345",
        registro_profissional=dados["registro_profissional"],
        nome_paciente=dados["nome_paciente"],
        cpf_paciente="52998224725",
        conselho=dados["conselho"],
        uf_registro=dados["uf_registro"],
        municipio_emissao=dados["municipio_emissao"],
        hora_inicio=dados["hora_inicio"],
        hora_fim=dados["hora_fim"],
        observacao_complementar=dados.get("observacao_complementar"),
    )
    return capturados


def _sem_markup(texto: str) -> str:
    """Remove a marcação de ênfase e desfaz o escape — sobra só o conteúdo."""
    sem_tags = re.sub(r"</?(b|strong)>", "", texto)
    return (
        sem_tags.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    )


def _corpo_do_pdf(paragrafos_pdf: list[str], corpo_rascunho: str) -> str:
    """Recorta, do que o PDF renderizou, os parágrafos que formam o corpo.

    O PDF diagrama muita coisa em volta (cabeçalho, seções, rodapé); o corpo é a
    fatia que corresponde, em ordem, aos parágrafos do rascunho.
    """
    n = len(corpo_rascunho.split("\n\n"))
    inicio = next(
        i for i, p in enumerate(paragrafos_pdf) if "Atesto, para fins" in _sem_markup(p)
    )
    return "\n\n".join(_sem_markup(p) for p in paragrafos_pdf[inicio:inicio + n])


# ---------------------------------------------------------------------------
# 1. O ESPELHO — o teste que fecha a classe do defeito
# ---------------------------------------------------------------------------

class TestEspelho:
    def test_corpo_do_rascunho_igual_ao_do_pdf(self, monkeypatch):
        """Para o MESMO atestado, o corpo do rascunho é o corpo do PDF.

        Ignorada apenas a marcação de ênfase (`<b>` vs. `<strong>`) — que é a
        única diferença legítima entre os dois renderizadores.
        """
        rascunho = _rascunho()
        do_pdf = _corpo_do_pdf(_paragrafos_do_pdf(monkeypatch), rascunho.corpo)
        assert rascunho.corpo == do_pdf

    def test_espelho_vale_com_observacao_complementar(self, monkeypatch):
        obs = "Reavaliação agendada para o dia 26/07/2026."
        rascunho = _rascunho(observacao_complementar=obs)
        do_pdf = _corpo_do_pdf(
            _paragrafos_do_pdf(monkeypatch, observacao_complementar=obs), rascunho.corpo
        )
        assert rascunho.corpo == do_pdf
        assert obs in rascunho.corpo

    def test_espelho_vale_no_ramo_de_comparecimento(self, monkeypatch):
        """Sem dias de afastamento o texto muda de ramo — o espelho acompanha."""
        rascunho = _rascunho(dias_afastamento=None)
        do_pdf = _corpo_do_pdf(
            _paragrafos_do_pdf(monkeypatch, dias_afastamento=None), rascunho.corpo
        )
        assert rascunho.corpo == do_pdf
        assert "compareceu a atendimento" in rascunho.corpo

    def test_espelho_vale_para_o_cfo(self, monkeypatch):
        rascunho = _rascunho(conselho="CFO")
        do_pdf = _corpo_do_pdf(
            _paragrafos_do_pdf(monkeypatch, conselho="CFO"), rascunho.corpo
        )
        assert rascunho.corpo == do_pdf


# ---------------------------------------------------------------------------
# 2. Redação unificada
# ---------------------------------------------------------------------------

class TestRedacao:
    def test_adota_para_fins_e_abandona_a_forma_agramatical(self):
        corpo = _rascunho().corpo
        assert "para fins trabalhistas" in corpo
        assert "para os devidos fins de" not in corpo

    def test_rascunho_usa_data_br_e_nao_iso(self):
        texto = _rascunho().texto
        assert "19/07/2026" in texto
        assert "2026-07-19" not in texto

    def test_rascunho_traz_o_municipio_de_emissao(self):
        assert "Recife, 19/07/2026." in _rascunho().texto

    def test_rascunho_formata_o_registro_como_o_pdf(self):
        texto = _rascunho().texto
        assert "CRM-PE 12345" in texto

    def test_horario_de_comparecimento_entra_no_corpo(self):
        assert "no período das 08:30 às 10:00" in _rascunho().corpo


# ---------------------------------------------------------------------------
# 3. Conselho emissor refletido — o rascunho ignorava o conselho
# ---------------------------------------------------------------------------

class TestConselho:
    def test_cfo_diz_odontologicos_no_rascunho(self):
        assert "cuidados odontológicos" in _rascunho(conselho="CFO").corpo

    def test_cfo_diz_odontologico_no_comparecimento(self):
        rascunho = _rascunho(conselho="CFO", dias_afastamento=None)
        assert "atendimento odontológico" in rascunho.corpo

    def test_cfo_formata_registro_como_cro(self):
        assert "CRO-PE 12345" in _rascunho(conselho="CFO").texto

    def test_cfm_permanece_medico(self):
        assert "cuidados médicos" in _rascunho(conselho="CFM").corpo

    def test_legado_sem_conselho_cai_no_padrao_cfm(self):
        assert "cuidados médicos" in _rascunho(conselho=None).corpo


# ---------------------------------------------------------------------------
# 4. Título — o rascunho não se veste de documento oficial
# ---------------------------------------------------------------------------

class TestTitulo:
    def test_rascunho_traz_o_titulo_generico(self):
        assert _rascunho().texto.startswith(TITULO_RASCUNHO)
        assert TITULO_RASCUNHO == "Atestado"

    @pytest.mark.parametrize("marca", ["ATESTADO MÉDICO", "ATESTADO ODONTOLÓGICO"])
    def test_rascunho_nunca_usa_o_titulo_do_documento_oficial(self, marca):
        """O título completo é marca do documento OFICIAL.

        Reproduzi-lo no papel de trabalho aproximaria o rascunho justamente
        daquilo que ele não é — decisão explícita do Fabiano. O corpo tem de ser
        idêntico (é o que se confere); a capa, não (é o que distingue).
        """
        for conselho in ("CFM", "CFO", None):
            assert marca not in _rascunho(conselho=conselho).texto


# ---------------------------------------------------------------------------
# 5. Observação complementar — acrescenta, nunca substitui
# ---------------------------------------------------------------------------

class TestObservacaoComplementar:
    def test_ausente_nao_gera_paragrafo_em_nenhum_dos_dois(self, monkeypatch):
        """Sem observação, o corpo é UM parágrafo — na tela e no PDF."""
        assert len(corpo_atestado(
            nome_paciente="X", finalidade="trabalhistas", dias_afastamento=1,
            data_documento="2026-07-19")) == 1

        rascunho = _rascunho(observacao_complementar=None)
        assert rascunho.corpo.count("\n\n") == 0
        do_pdf = _corpo_do_pdf(_paragrafos_do_pdf(monkeypatch), rascunho.corpo)
        assert do_pdf.count("\n\n") == 0

    def test_vazia_ou_so_espacos_nao_cria_paragrafo(self):
        assert _rascunho(observacao_complementar="   ").corpo.count("\n\n") == 0

    def test_preenchida_vira_paragrafo_proprio_depois_do_corpo(self):
        obs = "Paciente orientado a retornar em caso de febre."
        corpo = _rascunho(observacao_complementar=obs).corpo
        assert corpo.endswith(obs)
        assert corpo.count("\n\n") == 1

    def test_nao_substitui_o_corpo_gerado(self):
        """A frase gerada continua inteira mesmo com observação declarada."""
        obs = "Observação livre do profissional."
        corpo = _rascunho(observacao_complementar=obs).corpo
        assert "Atesto, para fins" in corpo
        assert "3 dia(s)" in corpo


# ---------------------------------------------------------------------------
# 6. Ênfase — um texto, dois markups
# ---------------------------------------------------------------------------

class TestEnfase:
    def test_reportlab_usa_b_e_html_usa_strong(self):
        p = Paragrafo((Trecho("normal "), Trecho("forte", enfase=True)))
        assert p.para_reportlab() == "normal <b>forte</b>"
        assert p.para_html() == "normal <strong>forte</strong>"
        assert p.texto_puro() == "normal forte"

    def test_conteudo_do_profissional_e_escapado_nos_dois(self):
        """Nome com `<` não injeta tag — nem no PDF, nem na tela."""
        p = Paragrafo((Trecho("a < b & c", enfase=True),))
        assert p.para_reportlab() == "<b>a &lt; b &amp; c</b>"
        assert p.para_html() == "<strong>a &lt; b &amp; c</strong>"

    def test_rascunho_html_traz_strong_e_nunca_b_cru(self):
        html = _rascunho().html
        assert "<strong>João da Silva</strong>" in html
        assert "<b>" not in html


# ---------------------------------------------------------------------------
# 7. O caminho completo da IA Documental devolve as três formas
# ---------------------------------------------------------------------------

class TestRespostaDaIaDocumental:
    def _resposta(self, **extra):
        return validar_atestado(
            paciente_nome=_ATESTADO["nome_paciente"],
            finalidade=_ATESTADO["finalidade"],
            indicacao_clinica=_ATESTADO["indicacao_clinica"],
            codigo_cid=_ATESTADO["codigo_cid"],
            dias_afastamento=_ATESTADO["dias_afastamento"],
            data_documento=_ATESTADO["data_documento"],
            nome_profissional=_ATESTADO["nome_profissional"],
            registro_profissional=_ATESTADO["registro_profissional"],
            municipio_emissao=_ATESTADO["municipio_emissao"],
            conselho=_ATESTADO["conselho"],
            uf_registro=_ATESTADO["uf_registro"],
            **extra,
        )

    def test_devolve_texto_html_e_corpo(self):
        r = self._resposta()
        assert r["ok"] is True
        assert "Recife, 19/07/2026." in r["documento_base"]
        assert "<strong>" in r["documento_base_html"]
        assert r["corpo_documento"].startswith("Atesto, para fins")

    def test_observacao_chega_ao_corpo_pelo_endpoint_de_dominio(self):
        obs = "Retorno em sete dias."
        r = self._resposta(observacao_complementar=obs)
        assert obs in r["corpo_documento"]
        assert obs in r["documento_base"]

    def test_sem_observacao_nada_aparece(self):
        r = self._resposta()
        assert r["corpo_documento"].count("\n\n") == 0

    def test_faltantes_zeram_as_tres_formas(self):
        r = validar_atestado(paciente_nome="João")
        assert r["documento_base"] is None
        assert r["documento_base_html"] is None
        assert r["corpo_documento"] is None
