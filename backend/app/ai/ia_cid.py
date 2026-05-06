"""
ia_cid.py
=========
Função principal da IA CID v1 do PicSaúde — Ticket 33.

ARQUITETURA
-----------
  Stateless   — sem estado interno, sem escrita em DB.
  Pipeline    — Normalização → Busca → Consolidação → Aviso
  Determinística — mesmo input → mesmo output, sempre.

DIFERENÇA FUNDAMENTAL em relação à IA farmacêutica e IA exames:
  • TUSS/Exames: retorna UM único match (normalização de objeto operacional)
  • CID: retorna UMA LISTA de sugestões (busca em vocabulário de diagnóstico)
    Porque o médico não escolhe um "nome correto" — escolhe entre diagnósticos
    possíveis. A IA nunca decide qual CID aplica.

PIPELINE
--------
  1. Normalização do texto clínico livre.
  2. Busca na base CID local (exato → alias → fuzzy, score ≥ 0.75).
  3. Consolidação da lista de sugestões com metadados de rastreabilidade.
  4. Aviso fixo — a IA é consultiva, nunca diagnóstica.

RESPOSTA
--------
  {
    "texto_entrada":    str,
    "texto_normalizado": str,
    "cid_sugeridos": [
      {
        "codigo":    str,          # ex: "R10.4"
        "descricao": str,          # ex: "Outras dores abdominais..."
        "categoria": str,          # ex: "sintoma"
        "match_tipo": str,         # "exato" | "alias" | "aproximado"
        "score":     float,        # 0.75–1.0
      },
      ...                          # até 5 sugestões
    ],
    "fonte":       str,
    "versao_base": str,
    "alertas":     list[str],
    "aviso":       str,
  }
"""

from __future__ import annotations

from app.ai.normalizacao_cid import normalizar_texto_clinico
from app.ai.base_cid import BASE_CID


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_AVISO_FIXO = (
    "Sugestões de CID baseadas no texto informado. "
    "A escolha clínica permanece com o profissional."
)

_ALERTA_TEXTO_GENERICO = (
    "Termo genérico — múltiplas condições possíveis. "
    "Considere especificar local, tipo ou intensidade."
)

# Termos que sinalizam alta ambiguidade diagnóstica
_TERMOS_GENERICOS = frozenset({
    "dor", "infeccao", "inflamacao", "alteracao", "problema",
    "doenca", "sindrome", "lesao", "queixa", "sintoma",
})

_CONTEXTOS_VALIDOS = frozenset({"pedido_exame", "prescricao", "laudo", "geral"})

_MAX_SUGESTOES = 5


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def buscar_cid(
    texto_clinico: str,
    contexto: str = "geral",
) -> dict:
    """
    Pipeline IA CID v1: normalização → busca → consolidação.

    Parâmetros
    ----------
    texto_clinico : str
        Texto livre do campo indicacao_clinica ou similar.
    contexto : str
        Contexto de uso ("pedido_exame", "prescricao", "laudo", "geral").
        Na v1 não altera o comportamento; presente para evolução futura.

    Retorna
    -------
    dict com lista de sugestões CID e metadados de rastreabilidade.
    """
    texto_entrada = (texto_clinico or "").strip()

    # ── Normalização ─────────────────────────────────────────────────────────
    texto_norm = normalizar_texto_clinico(texto_entrada)

    # ── Busca na base ────────────────────────────────────────────────────────
    resultados = BASE_CID.buscar(texto_norm, max_resultados=_MAX_SUGESTOES)

    # ── Alertas ──────────────────────────────────────────────────────────────
    alertas: list[str] = []

    # Alerta se o texto normalizado é muito curto ou genérico
    tokens = set(texto_norm.split())
    if len(texto_norm) < 4:
        alertas.append(
            "Texto muito curto para busca confiável. Informe mais detalhes clínicos."
        )
    elif tokens and tokens.issubset(_TERMOS_GENERICOS):
        alertas.append(_ALERTA_TEXTO_GENERICO)
    elif not resultados:
        alertas.append(
            "Nenhum CID encontrado para o texto informado. "
            "Tente usar termos clínicos mais específicos."
        )

    # ── Consolidação da lista de sugestões ───────────────────────────────────
    cid_sugeridos = [
        {
            "codigo":    r["codigo_cid"],
            "descricao": r["descricao"],
            "categoria": r.get("categoria", ""),
            "match_tipo": match_tipo,
            "score":     score,
        }
        for r, score, match_tipo in resultados
    ]

    return {
        "texto_entrada":     texto_entrada,
        "texto_normalizado": texto_norm,
        "cid_sugeridos":     cid_sugeridos,
        "fonte":             BASE_CID._registros[0]["fonte"] if BASE_CID.total > 0 else "CID10/BASE_LOCAL",
        "versao_base":       BASE_CID.versao,
        "alertas":           alertas,
        "aviso":             _AVISO_FIXO,
    }
