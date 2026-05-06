"""
ia_exames.py
============
Função principal da IA de exames v1 do PicSaúde — Ticket 31.

ARQUITETURA
-----------
  Stateless   — sem estado interno, sem escrita em DB.
  Pipeline    — Normalização → Lookup → Consolidação → Aviso
  Determinística — mesmo input → mesmo output, sempre.

PIPELINE
--------
  1. Normalização textual do nome informado.
  2. Lookup na base TUSS (exato → alias → fuzzy → nenhum).
  3. Consolidação da resposta com metadados de rastreabilidade.
  4. Aviso fixo — a IA é consultiva, nunca decisória.

CONTEXTO
--------
  contexto = "pedido_exame" | "laudo"

  Na v1 a lógica é idêntica nos dois contextos.
  O campo está presente para preparar evolução futura sem quebrar a interface.

RESPOSTA
--------
  {
    "nome_entrada":       str,
    "nome_normalizado":   str,
    "codigo_tuss":        str | None,
    "nome_padronizado":   str | None,
    "categoria":          str | None,
    "preparo_sugerido":   str | None,
    "match_tipo":         "exato" | "alias" | "aproximado" | "nenhum",
    "score":              float,
    "fonte":              str | None,
    "versao_base":        str | None,
    "alertas":            list[str],
    "aviso":              str,
  }
"""

from __future__ import annotations

from app.ai.normalizacao_exame import normalizar_nome_exame
from app.ai.tuss_base import BASE_TUSS


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_AVISO_FIXO = (
    "Sugestão de codificação diagnóstica gerada automaticamente. "
    "A validação clínica e a codificação definitiva são responsabilidade "
    "exclusiva do profissional de saúde habilitado."
)

_CONTEXTOS_VALIDOS = frozenset({"pedido_exame", "laudo"})


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def normalizar_exame(
    nome_exame: str,
    contexto: str = "pedido_exame",
) -> dict:
    """
    Ponto de entrada principal da IA de exames v1.

    Parâmetros
    ----------
    nome_exame  : nome livre do exame (obrigatório)
    contexto    : "pedido_exame" | "laudo"

    Retorno
    -------
    dict padronizado com código TUSS, preparo, alertas e metadados de rastreabilidade.
    """
    nome_norm = normalizar_nome_exame(nome_exame)

    # --- Lookup exato (nome_busca ou alias exato) ---
    registro = BASE_TUSS.buscar_exato(nome_norm)
    match_tipo = "nenhum"
    score = 0.0

    if registro:
        # Distinguir exato (nome_busca) de alias
        if nome_norm == registro["nome_busca"]:
            match_tipo = "exato"
            score = 1.0
        else:
            match_tipo = "alias"
            score = 1.0
    else:
        # --- Lookup fuzzy ---
        registro_fuzzy, score_fuzzy = BASE_TUSS.buscar_fuzzy(nome_norm)
        if registro_fuzzy:
            registro = registro_fuzzy
            match_tipo = "aproximado"
            score = score_fuzzy

    # --- Consolidar alertas ---
    alertas: list[str] = list(registro["alertas_base"]) if registro else []

    # Alerta de baixa confiança no match aproximado
    if match_tipo == "aproximado" and score < 0.90:
        alertas.append(
            f"Match aproximado com confiança {score:.0%}. Confirme o código TUSS antes de usar."
        )

    # --- Resposta ---
    return {
        "nome_entrada":     nome_exame,
        "nome_normalizado": nome_norm,
        "codigo_tuss":      registro["codigo_tuss"] if registro else None,
        "nome_padronizado": registro["nome_padrao"] if registro else None,
        "categoria":        registro["categoria"] if registro else None,
        "preparo_sugerido": registro["preparo"] if registro else None,
        "match_tipo":       match_tipo,
        "score":            round(score, 4),
        "fonte":            "TUSS/BASE_LOCAL" if registro else None,
        "versao_base":      BASE_TUSS.versao if registro else None,
        "alertas":          alertas,
        "aviso":            _AVISO_FIXO,
    }
