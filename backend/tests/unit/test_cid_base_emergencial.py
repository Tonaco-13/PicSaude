"""
test_cid_base_emergencial.py — TICKET-CID-VALIDACAO, Frente A.

A base local era completa para o CID-10 V2008 e MUDA para tudo depois disso.
Consequência concreta: um médico não achava COVID-19 na busca, porque U07.1 não
existia na base. Estes testes impedem a regressão e — mais importante — impedem
que a defasagem volte a ser INVISÍVEL.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.ai.base_cid import BASE_CID

_CSV = Path(__file__).resolve().parents[3] / "data" / "cid10.csv"

# Os sete códigos de uso emergencial verificados contra fonte primária.
# NÃO estão na tabela DATASUS CID-10 V2008 (conferido no arquivo oficial) —
# vêm da OMS (uso emergencial 2020/2021) com adoção operacional do MS.
_EMERGENCIAIS = [
    "U07.1",  # COVID-19, vírus identificado
    "U07.2",  # COVID-19, vírus não identificado
    "U08.9",  # História pessoal de COVID-19
    "U09.9",  # Condição pós-COVID
    "U10.9",  # Síndrome inflamatória multissistêmica
    "U11.9",  # Necessidade de imunização contra COVID-19
    "U12.9",  # Efeito adverso de vacina COVID-19
]


class TestFamiliaEmergencialPresente:
    @pytest.mark.parametrize("codigo", _EMERGENCIAIS)
    def test_codigo_existe_na_base(self, codigo):
        registro = BASE_CID.buscar_por_codigo(codigo)
        assert registro is not None, (
            f"{codigo} ausente da base. Era esta a defasagem que o ticket corrigiu."
        )
        assert registro["descricao"]

    def test_covid_e_encontravel_por_texto(self):
        """O critério de aceite literal: busca por "covid" retorna U07.1.

        Não basta o código existir — o prescritor procura por "covid", não por
        "vírus identificado". Sem alias, a descrição oficial não o entrega.
        """
        resultados = BASE_CID.buscar("covid", max_resultados=5)
        codigos = [reg["codigo_cid"] for reg, _score, _tipo in resultados]
        assert "U07.1" in codigos, f"'covid' não encontrou U07.1. Retornou: {codigos}"
        assert codigos[0] == "U07.1", (
            f"U07.1 deveria ser o primeiro resultado de 'covid'. Retornou: {codigos}"
        )

    @pytest.mark.parametrize(
        "termo,esperado",
        [
            ("covid-19", "U07.1"),
            ("coronavirus", "U07.1"),
            ("covid longa", "U09.9"),
            ("pos covid", "U09.9"),
        ],
    )
    def test_termos_clinicos_usuais(self, termo, esperado):
        resultados = BASE_CID.buscar(termo, max_resultados=5)
        codigos = [reg["codigo_cid"] for reg, _score, _tipo in resultados]
        assert esperado in codigos, f"{termo!r} não encontrou {esperado}. Retornou: {codigos}"


class TestProcedenciaHonesta:
    """A coluna `fonte` não pode mentir.

    Verificado no arquivo oficial do DATASUS (CID10CSV.zip, "Versão: 2008"): as
    únicas entradas U são U04, U04.9, U80, U81, U88, U89, U99. Rotular os códigos
    de emergência como "DATASUS/CID-10 V2008" seria falso — e é justamente o tipo
    de rótulo errado que faz uma base parecer mais atual do que é.
    """

    def _linhas_csv(self) -> dict[str, dict]:
        with _CSV.open(encoding="utf-8", newline="") as f:
            return {r["codigo_cid"]: r for r in csv.DictReader(f)}

    @pytest.mark.parametrize("codigo", _EMERGENCIAIS)
    def test_nao_se_declara_datasus_v2008(self, codigo):
        linha = self._linhas_csv().get(codigo)
        assert linha is not None, f"{codigo} ausente do CSV."
        fonte = linha["fonte"]
        assert "V2008" not in fonte, (
            f"{codigo} declarado como {fonte!r}, mas NÃO está na tabela DATASUS "
            "CID-10 V2008 — conferido no arquivo oficial."
        )
        assert "OMS" in fonte, f"{codigo}: fonte {fonte!r} não identifica a origem real."

    def test_datasus_v2008_continua_rotulando_o_corpo_da_base(self):
        """A correção não pode ter contaminado as ~14k linhas legítimas."""
        linhas = self._linhas_csv()
        v2008 = [c for c, r in linhas.items() if r["fonte"] == "DATASUS/CID-10 V2008"]
        assert len(v2008) > 14_000, (
            f"Só {len(v2008)} linhas com a fonte original — a base foi corrompida?"
        )


class TestManifestoNaoDeixaADefasagemInvisivel:
    """A causa-raiz do ticket não foi a base velha — foi não dar para SABER disso.

    `_VERSAO_BASE` já dizia "V2008" e ninguém releu. O manifesto é DERIVADO dos
    registros carregados, então não envelhece em silêncio: qualquer código que
    entre sem `fonte` declarada aparece contado sob outra origem.
    """

    def test_manifesto_expoe_as_fontes_reais(self):
        m = BASE_CID.manifesto()
        assert m["total_registros"] == BASE_CID.total
        fontes = m["por_fonte"]

        assert any("V2008" in f for f in fontes), "A base DATASUS sumiu do manifesto."
        assert any("OMS" in f for f in fontes), (
            "O manifesto não revela a origem OMS — a defasagem voltaria a ser invisível."
        )
        # Soma das contagens = total. Se não fechar, alguma fonte está sendo omitida.
        assert sum(fontes.values()) == m["total_registros"]

    def test_manifesto_e_derivado_e_nao_declarado(self, monkeypatch):
        """Trocar a string declarada NÃO muda as contagens — elas vêm dos dados."""
        import app.ai.base_cid as bc

        monkeypatch.setattr(bc, "_VERSAO_BASE", "mentira deslavada")
        m = BASE_CID.manifesto()
        assert m["versao_declarada"] == "mentira deslavada"   # a string obedece…
        assert sum(m["por_fonte"].values()) == BASE_CID.total  # …os dados, não.
