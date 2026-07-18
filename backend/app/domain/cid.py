"""
domain/cid.py — validação de código CID-10 nos caminhos de escrita.

TICKET-CID-VALIDACAO, Frente B.

DUAS CAMADAS COM PROPÓSITOS DIFERENTES
--------------------------------------

    1. FORMATO  → ESTRITO (422).  Rejeita o que é INEQUIVOCAMENTE inválido.
    2. CATÁLOGO → SUAVE.          Aceita e sinaliza o que é apenas
                                  DESCONHECIDO PARA NÓS.

A régua: rejeitar o inválido, nunca rejeitar o desconhecido.

Por que o catálogo NÃO bloqueia
-------------------------------
A base local (`data/cid10.csv`) é completa para o CID-10 V2008 e defasada para
tudo que veio depois. Até a Frente A deste ticket ela não continha U07.1
(COVID-19). Bloquear uma emissão porque o nosso CSV é de 2008 puniria o
prescritor pelo NOSSO atraso — e `backend/CLAUDE.md` é explícito: "não adiciona
atrito ao fluxo do prescritor sem justificativa regulatória". A defasagem do
catálogo é defeito nosso; o código clinicamente correto não deixa de ser correto
porque não o importamos ainda.

O formato, ao contrário, é conhecimento nosso e não depende de versão: "gripe" e
"XYZ123" não são código CID em nenhuma revisão. Esses o backend rejeita.

Relação com a decisão anterior ("validação semântica é da IA CID")
------------------------------------------------------------------
`prescricoes.py` documentava que a validação SEMÂNTICA do CID é responsabilidade
da IA CID, não do backend. Isso permanece verdadeiro e intocado: este módulo não
julga se o código é clinicamente adequado à indicação — só se ele é
sintaticamente um código CID, e informa se consta da nossa base. Semântica
clínica segue com a IA.

Fonte de verdade do catálogo: `app.ai.base_cid.BASE_CID.buscar_por_codigo()`.
Não duplicar regex de catálogo aqui — a base é uma só.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
# A base tem exatamente dois padrões — categoria (LDD) e subcategoria (LDD.D).
# Verificado empiricamente contra data/cid10.csv: 14.233/14.233 códigos casam,
# e as 26 letras (A–Z) são usadas. Não restringir o conjunto de letras.
_RE_FORMATO_CID = re.compile(r"^[A-Z]\d{2}(\.\d)?$")

# Mensagem única — usada pelo validador de schema (vira detail do 422).
_ERRO_FORMATO = (
    "codigo_cid inválido: {valor!r}. "
    "Esperado o formato CID-10 — letra + 2 dígitos, com subcategoria opcional "
    '(ex.: "I10", "U07.1").'
)


@dataclass(frozen=True)
class ResultadoCID:
    """Resultado da validação de um código CID já normalizado.

    `consta_na_base` é uma propriedade do NOSSO catálogo no instante da escrita,
    não do documento clínico. Ver nota sobre hash canônico em `atestados.py`.
    """

    codigo: str                      # normalizado (maiúscula, sem espaços)
    consta_na_base: bool
    descricao: Optional[str] = None  # descrição oficial, quando consta


def normalizar_codigo_cid(valor: Optional[str]) -> Optional[str]:
    """Normaliza sem validar: trim + maiúscula. Vazio vira None.

    `" i10 "` → `"I10"`. Normalizar ANTES de validar é o que faz "i10" ser
    aceito em vez de virar 422 por capitalização.
    """
    if valor is None:
        return None
    normalizado = valor.strip().upper()
    return normalizado or None


def validar_formato_codigo_cid(valor: Optional[str]) -> Optional[str]:
    """Camada 1 — ESTRITA. Normaliza e exige o formato CID-10.

    Retorna o código normalizado, ou None quando ausente (o campo é opcional —
    CFM art. 3º: CID só com anuência do paciente).

    Levanta ValueError quando malformado. Em contexto Pydantic isso vira 422.
    """
    normalizado = normalizar_codigo_cid(valor)
    if normalizado is None:
        return None
    if not _RE_FORMATO_CID.match(normalizado):
        raise ValueError(_ERRO_FORMATO.format(valor=valor))
    return normalizado


def consultar_catalogo_cid(codigo: Optional[str]) -> Optional[ResultadoCID]:
    """Camada 2 — SUAVE. Consulta a base local. NUNCA levanta, NUNCA bloqueia.

    Retorna None se não há código. Caso contrário devolve um `ResultadoCID` com
    `consta_na_base` — que o chamador usa para SINALIZAR ao prescritor, jamais
    para recusar a escrita.

    Import local e `except Exception`: `BASE_CID` carrega ~14k registros no
    import e resolve um CSV do disco. Se essa base estiver indisponível, a
    emissão clínica NÃO pode cair junto — degrada para "não consta", que é
    exatamente o comportamento suave já previsto.
    """
    if codigo is None:
        return None
    try:
        from app.ai.base_cid import BASE_CID

        registro = BASE_CID.buscar_por_codigo(codigo)
    except Exception:
        registro = None

    if registro is None:
        return ResultadoCID(codigo=codigo, consta_na_base=False)
    return ResultadoCID(
        codigo=codigo,
        consta_na_base=True,
        descricao=registro.get("descricao"),
    )


# ---------------------------------------------------------------------------
# Validador reutilizável de schema (Pydantic v2)
# ---------------------------------------------------------------------------
# Uso, no padrão já adotado por atestados.py (_validar_conselho etc.):
#
#     _normalizar_cid = field_validator("codigo_cid")(validar_codigo_cid_schema)
#
# Um único ponto de verdade para os dois routers — sem regex duplicada.
def validar_codigo_cid_schema(cls, v: Optional[str]) -> Optional[str]:  # noqa: N805
    return validar_formato_codigo_cid(v)
