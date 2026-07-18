"""
test_conselho_profissional.py — fonte única do conselho emissor do atestado.

Lógica pura (sem banco, sem FastAPI). O que se protege aqui é a régua: título,
adjetivos e sigla do registro saem de UM lugar, e atestado legado (sem conselho
declarado) continua renderizando como sempre renderizou.
"""
from __future__ import annotations

import pytest

from app.domain.conselho_profissional import (
    CONSELHOS,
    CONSELHO_CFM,
    CONSELHO_CFO,
    CONSELHO_PADRAO,
    IDS_CONSELHO_VALIDOS,
    catalogo_publico,
    conselho_ou_padrao,
    conselho_por_id,
    conselho_por_sigla,
    formatar_registro,
)


class TestCatalogo:

    def test_cfm_e_cfo_declarados(self):
        assert conselho_por_id("CFM") is CONSELHO_CFM
        assert conselho_por_id("CFO") is CONSELHO_CFO

    def test_titulos_e_adjetivos_distintos(self):
        assert CONSELHO_CFM.titulo_documento == "ATESTADO MÉDICO"
        assert CONSELHO_CFO.titulo_documento == "ATESTADO ODONTOLÓGICO"
        assert CONSELHO_CFM.adjetivo_cuidados == "médicos"
        assert CONSELHO_CFO.adjetivo_cuidados == "odontológicos"
        assert CONSELHO_CFM.adjetivo_atendimento == "médico"
        assert CONSELHO_CFO.adjetivo_atendimento == "odontológico"

    def test_siglas_de_registro(self):
        assert CONSELHO_CFM.sigla_registro == "CRM"
        assert CONSELHO_CFO.sigla_registro == "CRO"

    def test_enfermagem_fora_de_escopo(self):
        # COFEN não entra enquanto a norma do atestado de enfermagem estiver
        # pendente (decisão do Fabiano; ver docs/DIVIDA-TECNICA.md).
        assert "COFEN" not in IDS_CONSELHO_VALIDOS
        assert IDS_CONSELHO_VALIDOS == {"CFM", "CFO"}

    def test_ids_unicos(self):
        ids = [c.id_conselho for c in CONSELHOS]
        assert len(ids) == len(set(ids))

    def test_case_insensitive(self):
        assert conselho_por_id("cfo") is CONSELHO_CFO
        assert conselho_por_id("  CfO  ") is CONSELHO_CFO


class TestLookupPorSigla:

    def test_sigla_para_conselho(self):
        # O cadastro do profissional fala CRM/CRO; o atestado grava CFM/CFO.
        assert conselho_por_sigla("CRM") is CONSELHO_CFM
        assert conselho_por_sigla("CRO") is CONSELHO_CFO

    def test_sigla_desconhecida_e_none(self):
        assert conselho_por_sigla("COREN") is None
        assert conselho_por_sigla(None) is None
        assert conselho_por_sigla("") is None


class TestLegado:

    def test_conselho_nulo_cai_no_padrao_medico(self):
        # Atestado emitido antes da migração: renderiza "ATESTADO MÉDICO".
        assert conselho_por_id(None) is None
        assert conselho_ou_padrao(None) is CONSELHO_PADRAO
        assert conselho_ou_padrao(None).titulo_documento == "ATESTADO MÉDICO"

    def test_slug_desconhecido_degrada_sem_levantar(self):
        # Um rótulo desconhecido nunca pode derrubar a geração de um PDF.
        assert conselho_por_id("CFX") is None
        assert conselho_ou_padrao("CFX") is CONSELHO_PADRAO


class TestFormatarRegistro:

    def test_forma_canonica(self):
        assert formatar_registro("CFM", "PE", "12345") == "CRM-PE 12345"
        assert formatar_registro("CFO", "PE", "1234") == "CRO-PE 1234"

    def test_uf_normalizada(self):
        assert formatar_registro("CFM", "pe", "12345") == "CRM-PE 12345"

    def test_legado_texto_livre_preservado(self):
        # Antes da migração o campo guardava o registro inteiro. Reformatar
        # inventaria uma UF que o dado histórico não tem.
        assert formatar_registro(None, None, "CRM-PE 12345") == "CRM-PE 12345"
        assert formatar_registro(None, None, "CRM 999") == "CRM 999"

    def test_sem_uf_devolve_numero_cru(self):
        assert formatar_registro("CFM", None, "12345") == "12345"

    def test_nada_declarado_e_none(self):
        assert formatar_registro(None, None, None) is None
        assert formatar_registro("CFM", "PE", "   ") is None


class TestCatalogoPublico:

    def test_shape_para_a_tela(self):
        cat = catalogo_publico()
        assert [c["id_conselho"] for c in cat] == ["CFM", "CFO"]
        assert all({"id_conselho", "nome", "sigla_registro", "titulo_documento"} == set(c)
                   for c in cat)

    def test_serializavel(self):
        import json
        json.dumps(catalogo_publico())   # não levanta
