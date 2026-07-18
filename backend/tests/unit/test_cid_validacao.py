"""
tests/unit/test_cid_validacao.py — TICKET-CID-VALIDACAO, Frente B.

A régua que estes testes protegem:

    rejeitar o que é INEQUIVOCAMENTE INVÁLIDO   (formato)
    nunca rejeitar o que é apenas DESCONHECIDO  (catálogo)

O teste mais importante do arquivo é `TestCatalogoNuncaBloqueia` — ele fixa a
decisão de que a defasagem da NOSSA base não vira atrito para o prescritor.
"""
from __future__ import annotations

import pytest

from app.domain.cid import (
    ResultadoCID,
    consultar_catalogo_cid,
    normalizar_codigo_cid,
    validar_formato_codigo_cid,
)


class TestFormatoEstrito:
    """Camada 1 — o que não é código CID em nenhuma revisão é rejeitado."""

    @pytest.mark.parametrize(
        "invalido",
        [
            "XYZ123",   # nem parece
            "gripe",    # texto clínico no campo de código
            "I10.99",   # subcategoria com 2 dígitos — não existe no CID-10
            "I1",       # dígitos de menos
            "I100",     # sem o ponto
            "110",      # zero-vs-letra: erro de digitação clássico
            "I10.",     # ponto órfão
            "I10.1.2",  # dois níveis de subcategoria
            "I 10",     # espaço interno (o trim só tira das pontas)
        ],
    )
    def test_formato_invalido_levanta(self, invalido):
        with pytest.raises(ValueError, match="codigo_cid inválido"):
            validar_formato_codigo_cid(invalido)

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("I10", "I10"),
            ("i10", "I10"),        # minúscula normaliza, NÃO é 422
            (" i10 ", "I10"),      # espaço nas pontas normaliza
            ("U07.1", "U07.1"),
            ("u07.1", "U07.1"),
            ("A00.0", "A00.0"),
            ("Z99", "Z99"),        # última letra do alfabeto é válida
        ],
    )
    def test_formato_valido_normaliza(self, entrada, esperado):
        assert validar_formato_codigo_cid(entrada) == esperado

    @pytest.mark.parametrize("vazio", [None, "", "   "])
    def test_ausente_continua_ausente(self, vazio):
        """O campo é OPCIONAL — CFM art. 3º, CID só com anuência do paciente.

        Tornar obrigatório está explicitamente fora do escopo do ticket.
        """
        assert validar_formato_codigo_cid(vazio) is None

    def test_todas_as_letras_sao_aceitas(self):
        """A base usa as 26 letras — não restringir o conjunto.

        Uma regex `[A-TV-Z]` (excluindo U, como algumas implementações fazem)
        rejeitaria justamente a família U07 de emergência. Foi o que motivou
        este ticket.
        """
        for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert validar_formato_codigo_cid(f"{letra}50") == f"{letra}50"


class TestCatalogoNuncaBloqueia:
    """Camada 2 — SUAVE. O coração da decisão do ticket.

    Bloquear um código bem-formado porque a nossa base é de 2008 puniria o
    prescritor pelo NOSSO atraso. A base defasada é defeito nosso.
    """

    def test_codigo_conhecido_traz_descricao(self):
        r = consultar_catalogo_cid("I10")
        assert r is not None
        assert r.consta_na_base is True
        assert r.descricao and "ipertens" in r.descricao

    def test_bem_formado_fora_da_base_e_aceito_e_sinalizado(self):
        """NUNCA 422 — aceita e marca `consta_na_base=False`.

        `I10.0` é o exemplo escolhido de propósito: I10 (hipertensão essencial) é
        uma categoria de 3 caracteres SEM subcategorias no CID-10, então "I10.0"
        é sintaticamente impecável e ainda assim não é código nenhum. Continua
        válido depois da Frente A — que acrescenta a família U pós-2008, não
        subcategorias de I10.
        """
        r = consultar_catalogo_cid("I10.0")
        assert isinstance(r, ResultadoCID)
        assert r.codigo == "I10.0"
        assert r.consta_na_base is False
        assert r.descricao is None

    def test_consultar_catalogo_nunca_levanta(self):
        """Nenhuma entrada faz a camada suave explodir — nem lixo."""
        for entrada in ["I10", "Q99.9", "ZZZZZZ", "", "não é código"]:
            consultar_catalogo_cid(entrada)  # não levanta

    def test_sem_codigo_retorna_none(self):
        assert consultar_catalogo_cid(None) is None

    def test_usa_a_base_e_nao_uma_regex_de_catalogo_duplicada(self, monkeypatch):
        """A base é a fonte única — sem lista paralela de códigos no validador.

        Se alguém reintroduzir uma regex/lista de catálogo dentro de domain/cid.py,
        este teste falha: neutralizada a base, nada mais pode afirmar `consta`.
        """
        import app.ai.base_cid as base_cid

        monkeypatch.setattr(
            base_cid.BASE_CID, "buscar_por_codigo", lambda _codigo: None
        )
        r = consultar_catalogo_cid("I10")
        assert r is not None and r.consta_na_base is False


class TestNormalizacao:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [(" i10 ", "I10"), ("I10", "I10"), (None, None), ("", None), ("  ", None)],
    )
    def test_normalizar(self, entrada, esperado):
        assert normalizar_codigo_cid(entrada) == esperado

    def test_normalizacao_nao_valida(self):
        """`normalizar_` é deliberadamente separado de `validar_`.

        O caminho FÍSICO do atestado (fire-and-forget) normaliza sem rejeitar —
        um 422 lá não desimprime o papel, só descarta o registro central.
        """
        assert normalizar_codigo_cid("gripe") == "GRIPE"
