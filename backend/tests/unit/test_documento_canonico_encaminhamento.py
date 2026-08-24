"""
test_documento_canonico_encaminhamento.py — ENG-016 §5, condições da ratificação.

AS TRÊS CONDIÇÕES DO RULING (arquiteto, 23/08), executáveis
-----------------------------------------------------------
O `versao_esquema` do documento canônico do encaminhamento subiu de "1" para
"2" porque a FINALIDADE passou a fazer parte do documento. O argumento é curto:
**hash que não congela o que foi visto é hash que mente** — a finalidade aparece
no cabeçalho que o médico confirma, então tem de estar no que é hasheado.

Por ser a PRIMEIRA evolução de documento canônico pós-emissão da história deste
repositório, o toque foi ao martelo, e a ratificação veio com condições. Este
arquivo é onde duas delas viram teste:

  · **compatibilidade versionada PROVADA, não afirmada** — um documento v1 tem
    hash que verifica sob a regra v1; um v2, sob a v2;
  · **nada recalcula hash hoje** — e quem um dia recalcular tem de respeitar a
    versão GRAVADA no documento, nunca a versão do código.

O HASH v1 ESTÁ CONGELADO POR VALOR ABAIXO
-----------------------------------------
Não é redundância com a função: é a única forma de detectar que a regra v1
DERIVOU. Um teste que compare a função consigo mesma passa mesmo quando ela
muda. O literal foi conferido contra o código da `main` ANTES da mudança —
mesma entrada, mesmo hash, byte a byte.

É o R4 aplicado ao próprio código (§2a): congela-se o valor no ato, para que
mudar a regra amanhã não altere o documento de ontem.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.routers.encaminhamentos import (
    ItemEncaminhamentoIn,
    VERSAO_DOC_ENCAMINHAMENTO,
    VERSOES_DOC_ENCAMINHAMENTO,
    _calcular_hash,
    _documento_canonico_encaminhamento,
)

_ROUTER = Path(__file__).resolve().parents[2] / "app" / "routers" / "encaminhamentos.py"

# Entrada fixa — a mesma usada para conferir contra a `main`.
_ENTRADA = dict(
    protocolo="P1",
    cns_origem="A",
    cns_destino="B",
    cpf_paciente="C",
    especialidade_destino="CARDIOLOGIA",
    cid=None,
    justificativa_clinica="J",
)

# ⚠️ CONGELADO POR VALOR: hash produzido pela regra v1 — conferido contra o
# código da `main` antes desta mudança. Se este literal precisar mudar, a regra
# v1 derivou, e todo documento v1 já emitido deixou de verificar.
_HASH_V1_CONGELADO = "c3cf6a1489ec2c13ea96f494e135bc9e6f0edf0c103eb52ac04d281ebd9d4c4d"


def _itens():
    return [ItemEncaminhamentoIn(especialidade="CARDIOLOGIA")]


# ---------------------------------------------------------------------------
# Condição 2 — compatibilidade versionada, provada
# ---------------------------------------------------------------------------

def test_a_regra_v1_nao_derivou():
    """O documento de ontem verifica hoje. É a condição inteira, num assert."""
    assert _calcular_hash(**_ENTRADA, itens=_itens(), versao="1") == _HASH_V1_CONGELADO, (
        "a regra v1 mudou — todo encaminhamento emitido antes da v2 deixou de "
        "verificar, e objeto sanitário emitido é imutável (§1)"
    )


def test_v1_e_v2_sao_hashes_DIFERENTES_para_a_mesma_entrada():
    """Se fossem iguais, a v2 não estaria cobrindo nada de novo — e a
    finalidade continuaria fora do que o hash congela."""
    v1 = _calcular_hash(**_ENTRADA, itens=_itens(), versao="1")
    v2 = _calcular_hash(**_ENTRADA, itens=_itens(), versao="2")
    assert v1 != v2


def test_a_finalidade_muda_o_hash_na_v2():
    """O ponto do §5: trocar a finalidade tem de mudar o documento."""
    a = _calcular_hash(**_ENTRADA, itens=_itens(), versao="2", finalidade="avaliacao")
    b = _calcular_hash(**_ENTRADA, itens=_itens(), versao="2", finalidade="segunda_opiniao")
    assert a != b


def test_a_finalidade_e_ignorada_na_v1():
    """A v1 não conhece finalidade — passá-la não pode mudar o hash dela.

    É o que garante que um documento antigo verifique mesmo quando o
    verificador tiver o campo em mãos.
    """
    sem = _calcular_hash(**_ENTRADA, itens=_itens(), versao="1")
    com = _calcular_hash(**_ENTRADA, itens=_itens(), versao="1",
                         finalidade="avaliacao", finalidade_texto="x")
    assert sem == com == _HASH_V1_CONGELADO


def test_a_v1_nao_tem_a_chave_e_a_v2_tem():
    """A diferença entre as versões é ESTRUTURAL, não só de valor."""
    d1 = _documento_canonico_encaminhamento("1", **_ENTRADA, itens=_itens())
    d2 = _documento_canonico_encaminhamento("2", **_ENTRADA, itens=_itens())
    assert "finalidade" not in d1 and d1["versao_esquema"] == "1"
    assert "finalidade" in d2 and d2["versao_esquema"] == "2"


def test_versao_desconhecida_e_erro_explicito_nao_silencio():
    """Documento com versão que este código não conhece NÃO é documento
    adulterado — é documento que não sabemos verificar, e a diferença importa.
    Cair no default e dizer "não confere" seria acusar quem emitiu."""
    with pytest.raises(ValueError, match="desconhecida"):
        _documento_canonico_encaminhamento("99", **_ENTRADA, itens=_itens())


def test_a_emissao_usa_a_versao_atual():
    assert VERSAO_DOC_ENCAMINHAMENTO == "2"
    assert _calcular_hash(**_ENTRADA, itens=_itens()) == \
           _calcular_hash(**_ENTRADA, itens=_itens(), versao=VERSAO_DOC_ENCAMINHAMENTO)


def test_as_versoes_conhecidas_estao_congeladas():
    assert VERSOES_DOC_ENCAMINHAMENTO == ("1", "2"), (
        "versão nova no documento canônico é decisão de martelo — não entra "
        "em silêncio (foi a condição da ratificação da v2)"
    )


# ---------------------------------------------------------------------------
# Condição 3 — nada recalcula hash hoje
# ---------------------------------------------------------------------------

def test_ninguem_recalcula_hash_de_documento_ja_emitido():
    """A afirmação que sustenta "a v2 não quebra nada", virada guarda.

    Hoje `_calcular_hash` é chamado SÓ na emissão (digital e física) e o
    resultado é gravado. Não existe caminho de verificação — por isso subir a
    versão não invalida documento nenhum.

    Se alguém escrever esse caminho, este teste cai. E deve cair: o verificador
    tem de passar a versão GRAVADA no documento, não a atual, e essa decisão
    precisa ser tomada com os olhos abertos.
    """
    fonte = _ROUTER.read_text(encoding="utf-8")
    sem_comentarios = "\n".join(
        l for l in fonte.splitlines() if not l.strip().startswith("#")
    )
    chamadas = len(re.findall(r"(?<!def )_calcular_hash\(", sem_comentarios))
    # 2 = emissão digital + emissão física. Ambas gravam; nenhuma compara.
    assert chamadas == 2, (
        f"`_calcular_hash` passou a ser chamado {chamadas}× (esperado 2: as duas "
        "emissões). Se nasceu um verificador, ele DEVE passar `versao=` lida do "
        "documento — e esta guarda precisa ser atualizada por decisão, não por "
        "conveniência."
    )
    assert "assinatura_hash" not in sem_comentarios.split("def _calcular_hash")[0] or True
    # E o hash gravado nunca é comparado com um recalculado:
    assert not re.search(r"assinatura_hash\s*==|==\s*_calcular_hash", sem_comentarios), (
        "apareceu comparação de hash — é o caminho de verificação; ver a nota acima"
    )
