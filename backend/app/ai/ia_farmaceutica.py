"""
ia_farmaceutica.py
==================
Função principal da IA farmacêutica v1 do PicSaúde.

ARQUITETURA
-----------
  Stateless   — sem estado interno, sem escrita em DB.
  Pipeline    — Normalização → Lookup → Regras → Consolidação → Aviso
  Determinística — mesmo input → mesmo output, sempre.

PIPELINE
--------
  1. Normalização textual do nome informado.
  2. Lookup na base DEF (exato → alias → aproximado → nenhum).
  3. Regras determinísticas (sugestão de unidade, incoerências).
  4. Consolidação da resposta (lookup tem prioridade sobre regras).
  5. Aviso fixo — a IA é consultiva, nunca decisória.

CONTEXTO
--------
  contexto = "prescricao" | "dispensacao"

  Na v1 a lógica é idêntica nos dois contextos.
  O campo está presente para preparar evolução futura sem quebrar a interface.

RESPOSTA
--------
  {
    "nome_normalizado":             str,
    "forma_farmaceutica_sugerida":  str | None,
    "unidade_quantidade_sugerida":  str | None,
    "principio_ativo":              str | None,
    "concentracao_sugerida":        str | None,
    "via_administracao":            str | None,
    "match_tipo":                   "exato" | "alias" | "aproximado" | "regra" | "nenhum",
    "score":                        float,
    "fonte":                        str | None,
    "versao_base":                  str | None,
    "alertas":                      list[str],
    "aviso":                        str,
  }
"""

from __future__ import annotations

from typing import Optional

from app.ai.normalizacao_medicamento import normalizar_nome_medicamento
from app.ai.lookup_def import buscar_medicamento
from app.ai.regras_farmaceuticas import sugerir_unidade, verificar_incoerencias


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_AVISO_FIXO = (
    "Sugestão farmacológica auxiliar gerada automaticamente. "
    "A decisão clínica é responsabilidade exclusiva do profissional de saúde habilitado."
)

_CONTEXTOS_VALIDOS = frozenset({"prescricao", "dispensacao"})


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def sugerir_medicamento(
    nome_medicamento: str,
    forma_farmaceutica: Optional[str] = None,
    unidade_quantidade: Optional[str] = None,
    contexto: str = "prescricao",
) -> dict:
    """
    Ponto de entrada principal da IA farmacêutica v1.

    Parâmetros
    ----------
    nome_medicamento    : nome livre (obrigatório)
    forma_farmaceutica  : forma declarada pelo usuário (opcional)
    unidade_quantidade  : unidade declarada pelo usuário (opcional)
    contexto            : "prescricao" | "dispensacao"

    Retorno
    -------
    dict padronizado com sugestões, alertas e metadados de rastreabilidade.
    """
    # --- Normalização do input ---
    nome_norm = normalizar_nome_medicamento(nome_medicamento)
    forma_norm = normalizar_nome_medicamento(forma_farmaceutica) if forma_farmaceutica else None

    # --- Lookup DEF ---
    lookup = buscar_medicamento(
        nome_medicamento=nome_medicamento,
        forma_farmaceutica=forma_farmaceutica,
    )

    # --- Determinar forma e unidade sugeridas ---
    # Prioridade: lookup > regras baseadas na forma informada pelo usuário
    forma_sugerida = (
        lookup.get("forma_farmaceutica")
        or forma_farmaceutica
        or None
    )

    unidade_sugerida = None
    match_tipo       = lookup.get("match_tipo", "nenhum")
    score            = lookup.get("score", 0.0)
    fonte            = lookup.get("fonte")
    versao           = lookup.get("versao_base")

    if lookup["match_tipo"] != "nenhum":
        # Lookup encontrou algo — unidade vem da base
        unidade_sugerida = lookup.get("unidade_dispensavel")
    else:
        # Sem match no lookup — tentar derivar unidade por regra da forma
        unidade_por_regra = sugerir_unidade(forma_farmaceutica)
        if unidade_por_regra:
            unidade_sugerida = unidade_por_regra
            match_tipo       = "regra"
            score            = 0.0
            fonte            = "regras_locais"
            versao           = None

    # --- Regras de incoerência ---
    # Verificar contra: (nome original, forma final que será sugerida)
    alertas = verificar_incoerencias(
        nome_medicamento=nome_medicamento,
        forma_farmaceutica=forma_sugerida or forma_farmaceutica,
    )

    # --- Consolidar resposta ---
    return {
        "nome_normalizado":             nome_norm,
        "forma_farmaceutica_sugerida":  forma_sugerida or None,
        "unidade_quantidade_sugerida":  unidade_sugerida or None,
        "principio_ativo":              lookup.get("principio_ativo"),
        "concentracao_sugerida":        lookup.get("concentracao_texto"),
        "via_administracao":            lookup.get("via_administracao"),
        "match_tipo":                   match_tipo,
        "score":                        round(score, 4),
        "fonte":                        fonte,
        "versao_base":                  versao,
        "alertas":                      alertas,
        "aviso":                        _AVISO_FIXO,
    }
