"""
TICKET-UNIDADE-QUANTIDADE-VISIVEL — exibição honesta de unidade.

Cobre a regra sanitária: toda quantidade sai com a unidade junto; unidade
ausente/inválida → "não informada", NUNCA "unidade" (defaultar afirmaria
"30 unidades" onde o real pode ser "30 caixas"). Pluralização ingênua.

Também cobre o aceite do item LEGADO: comprovante de dispensação cuja
`unidade_quantidade` é NULL renderiza "não informada" (JSON e PDF), sem inventar.
"""
from __future__ import annotations

import zlib

from app.domain.medicamento import formatar_quantidade, formatar_unidade
from app.routers.dispensacoes import _gerar_pdf, _montar_json


# ---------------------------------------------------------------------------
# domain helper
# ---------------------------------------------------------------------------

def test_formatar_unidade_pluraliza_por_quantidade():
    assert formatar_unidade("comprimido", 30) == "comprimidos"
    assert formatar_unidade("comprimido", 1) == "comprimido"
    assert formatar_unidade("cápsula", 21) == "cápsulas"


def test_formatar_unidade_normaliza_sem_acento():
    # "capsula" (sem acento) é aceito pelo vocabulário e vira display canônico
    assert formatar_unidade("capsula", 21) == "cápsulas"


def test_formatar_unidade_ausente_ou_invalida_nao_informada():
    assert formatar_unidade(None, 30) == "não informada"
    assert formatar_unidade("", 30) == "não informada"
    assert formatar_unidade("caixa-de-fósforo", 30) == "não informada"
    # NUNCA defaultar para "unidade"
    assert "unidade" not in formatar_unidade(None, 30)


def test_formatar_quantidade_compoe_qtd_e_unidade():
    assert formatar_quantidade(30, "comprimido") == "30 comprimidos"
    assert formatar_quantidade(1, "cápsula") == "1 cápsula"
    assert formatar_quantidade(30, None) == "30 (unidade não informada)"


# ---------------------------------------------------------------------------
# comprovante — item legado com unidade_quantidade NULL
# ---------------------------------------------------------------------------

def _raw(unidade):
    """Linha bruta mínima (formato de _SQL_COMPROVANTE) para _montar_json."""
    return {
        "dispensacao_id": 1,
        "cnpj_estabelecimento": "12345678000195",
        "quantidade_dispensada": 30,
        "dispensado_por": "Farmacêutico X",
        "dispensado_em": "2026-07-16T10:00:00",
        "lote": "L1",
        "fabricante": "ACME",
        "observacao": None,
        "comprador_nome": None,
        "comprador_documento": None,
        "nome_medicamento": "LOSARTANA",
        "concentracao": "50mg",
        "quantidade_prescrita": 30,
        "unidade_quantidade": unidade,
        "posologia": "1x ao dia",
        "protocolo": "PROTO-XYZ",
        "data_emissao": "2026-07-10T09:00:00",
        "paciente_nome": "João",
        "paciente_cpf": "12345678909",
        "prescritor_nome": "Dra. Y",
        "prescritor_cns": "980001112223334",
        "estabelecimento_nome": "Farmácia Z",
        "estabelecimento_razao": "Farmácia Z LTDA",
        "_estornos": [],
    }


def test_json_unidade_valida_canonica():
    d = _montar_json(_raw("comprimido"))
    assert d["medicamento"]["unidade_quantidade"] == "comprimido"


def test_json_unidade_nula_expoe_none_para_ui():
    # NULL vira None no JSON — a UI renderiza "não informada" (nunca "unidade").
    d = _montar_json(_raw(None))
    assert d["medicamento"]["unidade_quantidade"] is None


def _pdf_texto(pdf: bytes) -> str:
    """Concatena o texto descomprimido dos streams do PDF (ReportLab: Flate)."""
    import base64
    import re
    out = []
    for m in re.finditer(rb"stream\n(.*?)endstream", pdf, re.DOTALL):
        raw = m.group(1).strip(b"\n")
        for dec in (
            lambda r: zlib.decompress(base64.a85decode(r, adobe=True)),
            lambda r: zlib.decompress(r),
            lambda r: r,
        ):
            try:
                out.append(dec(raw).decode("latin-1"))
                break
            except Exception:
                continue
    return "\n".join(out)


def test_pdf_legado_nulo_mostra_nao_informada():
    pdf = _gerar_pdf(_montar_json(_raw(None)))
    assert pdf[:5] == b"%PDF-"
    texto = _pdf_texto(pdf)
    assert "não informada" in texto or "informada" in texto, (
        "PDF de item legado (unidade NULL) deveria exibir 'não informada'"
    )


def test_pdf_unidade_valida_mostra_unidade_pluralizada():
    pdf = _gerar_pdf(_montar_json(_raw("comprimido")))
    texto = _pdf_texto(pdf)
    assert "comprimidos" in texto, "PDF deveria exibir '30 comprimidos'"
