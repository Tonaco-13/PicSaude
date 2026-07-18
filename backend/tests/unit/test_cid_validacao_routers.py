"""
test_cid_validacao_routers.py — TICKET-CID-VALIDACAO, Frente B nos caminhos de escrita.

`domain/cid.py` tem os testes de unidade da regra. AQUI provamos a bifurcação que
motivou o ticket: o validador existia e os caminhos de escrita não o chamavam.

Critérios de aceite do ticket, um teste por linha:

    "XYZ123"                     → 422 nos dois routers
    "i10"                        → normaliza p/ I10, aceito
    "U07.1"                      → aceito (achado na base após a Frente A)
    bem-formado fora da base     → aceito + sinalizado, NUNCA 422
"""
from __future__ import annotations

import pytest

_BASE_ATESTADO = {
    "cns_prescritor": "123456789012345",   # = token sub do RoleClient prescritor
    "nome_prescritor": "Dra. Atesta",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente CID",
    "finalidade": "Afastamento do trabalho",
    "municipio_emissao": "Recife",
    "dias_afastamento": 2,
    "data_documento": "2026-06-23",
}

_BASE_PRESCRICAO = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dra. Atesta",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente CID",
    "itens": [
        {
            "nome_medicamento": "Dipirona",
            "concentracao": "500mg",
            "quantidade": 10,
            "unidade_quantidade": "comprimido",
            "posologia": "1 comprimido de 6/6h",
        }
    ],
}


def _atestado(**ov):
    return {**_BASE_ATESTADO, **ov}


def _prescricao(**ov):
    return {**_BASE_PRESCRICAO, **ov}


# ---------------------------------------------------------------------------
# Formato — ESTRITO (422) nos dois routers
# ---------------------------------------------------------------------------

_MALFORMADOS = ["XYZ123", "gripe", "I10.99", "I100"]


class TestFormatoRejeitadoNaEscrita:
    @pytest.mark.parametrize("codigo", _MALFORMADOS)
    def test_atestado_rejeita_formato_invalido(self, prescritor, codigo):
        r = prescritor.post("/atestados", json=_atestado(codigo_cid=codigo))
        assert r.status_code == 422, r.text
        assert "codigo_cid" in r.text

    @pytest.mark.parametrize("codigo", _MALFORMADOS)
    def test_prescricao_rejeita_formato_invalido(self, prescritor, codigo):
        r = prescritor.post("/prescricoes", json=_prescricao(codigo_cid=codigo))
        assert r.status_code == 422, r.text
        assert "codigo_cid" in r.text


class TestNormalizacaoNaEscrita:
    """"i10" é o prescritor digitando em minúscula — não é erro dele."""

    def test_atestado_normaliza_minuscula(self, prescritor):
        r = prescritor.post("/atestados", json=_atestado(codigo_cid=" i10 "))
        assert r.status_code == 201, r.text
        assert r.json()["codigo_cid"] == "I10"

    def test_prescricao_normaliza_minuscula(self, prescritor):
        r = prescritor.post("/prescricoes", json=_prescricao(codigo_cid=" i10 "))
        assert r.status_code == 201, r.text
        assert r.json()["codigo_cid"] == "I10"


# ---------------------------------------------------------------------------
# Catálogo — SUAVE (aceita e sinaliza). NUNCA 422.
# ---------------------------------------------------------------------------

class TestCatalogoNaoBloqueiaAEscrita:
    """O teste que redesenhou o ticket.

    Antes da Frente A, U07.1 (COVID-19) NÃO constava da base. Validação estrita
    contra o catálogo bloquearia um atestado de COVID — punindo o médico pelo
    NOSSO atraso de importação. Este teste fixa que isso não acontece.
    """

    def test_atestado_aceita_codigo_fora_da_base_e_sinaliza(self, prescritor):
        # I10.0: sintaticamente impecável, inexistente no CID-10 (I10 não tem
        # subcategorias). Estável — a Frente A não o acrescenta.
        r = prescritor.post("/atestados", json=_atestado(codigo_cid="I10.0"))
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["codigo_cid"] == "I10.0"
        assert corpo["cid_consta_na_base"] is False   # sinalizado…
        assert corpo["cid_descricao"] is None
        # …e gravado. Sinalizar não é recusar.

    def test_prescricao_aceita_codigo_fora_da_base_e_sinaliza(self, prescritor):
        r = prescritor.post("/prescricoes", json=_prescricao(codigo_cid="I10.0"))
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["codigo_cid"] == "I10.0"
        assert corpo["cid_consta_na_base"] is False

    def test_codigo_conhecido_vem_com_descricao(self, prescritor):
        r = prescritor.post("/atestados", json=_atestado(codigo_cid="I10"))
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["cid_consta_na_base"] is True
        assert corpo["cid_descricao"]

    def test_covid_e_aceito(self, prescritor):
        """U07.1 — o caso concreto. Aceito independente da Frente A.

        Este teste passava ANTES da Frente A (aceito, sinalizado como fora da
        base) e continua passando DEPOIS (aceito, agora encontrado). É essa
        estabilidade que prova que a camada de catálogo é suave: o resultado
        clínico não muda com a versão do nosso CSV.
        """
        r = prescritor.post("/atestados", json=_atestado(codigo_cid="U07.1"))
        assert r.status_code == 201, r.text
        assert r.json()["codigo_cid"] == "U07.1"
        # Depois da Frente A, também é ENCONTRADO. A emissão já funcionava antes;
        # o que a Frente A acrescenta é o médico achar o código na busca.
        assert r.json()["cid_consta_na_base"] is True

    def test_sem_cid_continua_valido(self, prescritor):
        """CID segue OPCIONAL — CFM art. 3º (só com anuência do paciente).

        Torná-lo obrigatório está explicitamente fora do escopo do ticket.
        """
        r = prescritor.post("/atestados", json=_atestado())
        assert r.status_code == 201, r.text
        assert r.json()["codigo_cid"] is None
        assert r.json()["cid_consta_na_base"] is None


# ---------------------------------------------------------------------------
# Atestado FÍSICO — normaliza, mas não rejeita
# ---------------------------------------------------------------------------

class TestAtestadoFisicoNaoRejeita:
    """Exceção deliberada, na linha do que o próprio router já documenta.

    O POST físico é fire-and-forget (CLAUDE.md §6): o papel já saiu na impressora
    quando o backend valida. Um 422 não desimprime nada — só descarta o registro
    central. Atestado no mundo e nada no ledger é pior que um CID ruim gravado.
    """

    def test_fisico_aceita_cid_malformado(self, prescritor):
        r = prescritor.post(
            "/atestados/fisica",
            json={
                "cns_prescritor": "123456789012345",
                "nome_prescritor": "Dra. Atesta",
                "finalidade": "Comparecimento",
                "codigo_cid": "gripe",
            },
        )
        assert r.status_code == 201, r.text

    def test_fisico_normaliza_o_que_da(self, prescritor):
        r = prescritor.post(
            "/atestados/fisica",
            json={
                "cns_prescritor": "123456789012345",
                "nome_prescritor": "Dra. Atesta",
                "finalidade": "Comparecimento",
                "codigo_cid": " i10 ",
            },
        )
        assert r.status_code == 201, r.text
