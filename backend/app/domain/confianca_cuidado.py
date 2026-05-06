"""
confianca_cuidado.py
====================
Ticket 50 — Score Composto de Confiança do Cuidado.

Objetivo: sintetizar sinais dispersos de confiança em uma leitura
explicável e auditável da confiabilidade institucional e operacional
do cuidado.

Princípios
----------
- Score NUNCA bloqueia o fluxo
- Score é explicável: sempre acompanha `fatores` e `resumo`
- Sem caixa preta: cálculo baseado em regras determinísticas
- Sinais originais são preservados (score não os substitui)

Escala de pontuação (0–100, clamped)
-------------------------------------
  Base (prescrição em fluxo):           +30
  Prescritor forte (CNES):              +40
  Prescritor parcial (CNES):            +20
  Prescritor divergente (CNES):         -30
  Prescritor não encontrado (CNES):     -15
  Conselho de classe habilitado:        +10
  Vínculos institucionais ≥ 1:          + 5
  Por divergência CNES (cap: -15):      - 5
  Prestador com contexto CNES:          +25
  Prestador manual confirmado:          -10
  Prestador manual não confirmado:      -20

Níveis sintéticos
-----------------
  70–100  alto
  40–69   medio
  10–39   baixo
  <  10   critico
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Constantes de pontuação — documentadas e auditáveis
# ---------------------------------------------------------------------------

_BASE                         = 30

# Prescritor
_PRESCRITOR_FORTE             = 40
_PRESCRITOR_PARCIAL           = 20
_PRESCRITOR_DIVERGENTE        = -30
_PRESCRITOR_NAO_ENCONTRADO    = -15

# Sinais adicionais do CNES
_CONSELHO_HABILITADO          = 10
_VINCULOS_ATIVOS              = 5
_POR_DIVERGENCIA              = -5
_MAX_PENALIDADE_DIVERGENCIAS  = -15   # cap: penalidade nunca passa de 3 divergências

# Prestador / contexto operacional
_PRESTADOR_CNES_VERIFICADO    = 25
_PRESTADOR_MANUAL_CONFIRMADO  = -10
_PRESTADOR_MANUAL_NAO_CONF    = -20

# Limites da pontuação
_PONTUACAO_MIN = 0
_PONTUACAO_MAX = 100


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _nivel(pontuacao: int) -> str:
    if pontuacao >= 70:
        return "alto"
    if pontuacao >= 40:
        return "medio"
    if pontuacao >= 10:
        return "baixo"
    return "critico"


def _clampar(pontuacao: int) -> int:
    return max(_PONTUACAO_MIN, min(_PONTUACAO_MAX, pontuacao))


def _contribuicao_prescritor(
    cnes_validacao: Optional[dict],
) -> tuple[int, list[str]]:
    """Retorna (pontos, fatores) para o bloco prescritor."""
    if not cnes_validacao:
        return 0, []

    pontos = 0
    fatores: list[str] = []
    nivel = (cnes_validacao.get("nivel_validacao_cnes") or "").strip()

    if nivel == "forte":
        pontos += _PRESCRITOR_FORTE
        fatores.append("Prescritor com validação CNES forte")
    elif nivel == "parcial":
        pontos += _PRESCRITOR_PARCIAL
        fatores.append("Prescritor com validação CNES parcial")
    elif nivel == "divergente":
        pontos += _PRESCRITOR_DIVERGENTE
        fatores.append("Prescritor com divergência CNES — identidade ou CBO inconsistente")
    elif nivel == "nao_encontrado":
        pontos += _PRESCRITOR_NAO_ENCONTRADO
        fatores.append("Prescritor não encontrado no snapshot CNES")
    # else: sem dados → 0 pontos, sem fator

    # Sinais adicionais (apenas quando CNS foi encontrado)
    if cnes_validacao.get("cns_encontrado"):
        if cnes_validacao.get("conselho"):
            pontos += _CONSELHO_HABILITADO
            fatores.append("Conselho de classe prescritivo confirmado no CNES")
        vinculos = cnes_validacao.get("vinculos_ativos") or 0
        if vinculos >= 1:
            pontos += _VINCULOS_ATIVOS
            fatores.append(
                f"Prescritor com {vinculos} vínculo(s) institucional(is) ativo(s)"
            )

    # Penalidade por divergências (com cap)
    divergencias = cnes_validacao.get("divergencias") or []
    if divergencias:
        pen = max(_MAX_PENALIDADE_DIVERGENCIAS, _POR_DIVERGENCIA * len(divergencias))
        pontos += pen
        fatores.append(
            f"{len(divergencias)} divergência(s) CNES registrada(s) no prescritor"
        )

    return pontos, fatores


def _contribuicao_prestador(
    origem_contexto: Optional[str],
    contexto_confirmado_manual: Optional[bool],
) -> tuple[int, list[str]]:
    """Retorna (pontos, fatores) para o bloco prestador/contexto operacional."""
    if not origem_contexto:
        return 0, []

    pontos = 0
    fatores: list[str] = []

    if origem_contexto == "cnes_verificado":
        pontos += _PRESTADOR_CNES_VERIFICADO
        fatores.append("Estabelecimento dispensador com contexto verificado no CNES")
    elif origem_contexto == "manual":
        if contexto_confirmado_manual is True:
            pontos += _PRESTADOR_MANUAL_CONFIRMADO
            fatores.append("Estabelecimento operando com contexto manual confirmado pelo operador")
        else:
            pontos += _PRESTADOR_MANUAL_NAO_CONF
            fatores.append("Estabelecimento operando com contexto manual não confirmado")

    return pontos, fatores


def _gerar_resumo(nivel: str, fatores: list[str]) -> str:
    base = {
        "alto":    "Confiança operacional alta",
        "medio":   "Confiança operacional moderada",
        "baixo":   "Confiança operacional baixa",
        "critico": "Confiança operacional crítica",
    }.get(nivel, "Confiança operacional indeterminada")

    if not fatores:
        return f"{base} — sinais insuficientes para análise detalhada."

    fts = [f.lower() for f in fatores]

    if any("divergência" in f or "divergente" in f for f in fts):
        detail = "com divergências de identidade ou habilitação no CNES"
    elif any("forte" in f for f in fts):
        detail = "com prescritor plenamente validado no CNES"
    elif any("parcial" in f for f in fts):
        detail = "com prescrição parcialmente validada no CNES"
    elif any("não encontrado" in f for f in fts):
        detail = "com prescritor sem registro no snapshot CNES"
    elif any("manual não confirmado" in f for f in fts):
        detail = "com contexto institucional manual não confirmado"
    elif any("manual confirmado" in f for f in fts):
        detail = "com contexto institucional manual confirmado"
    else:
        detail = "com sinais operacionais verificados"

    return f"{base} — {detail}."


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def calcular_score_confianca_prescricao(
    cnes_validacao: Optional[dict],
) -> dict:
    """
    Calcula o score de confiança para o contexto de emissão de prescrição.

    Chamado em ``criar_prescricao`` após ``validar_cns_prescritor``.
    Resultado é enriquecido no evento ``prescricao_emitida`` e retornado
    na resposta da API.

    Parâmetros
    ----------
    cnes_validacao  Bloco gerado por ``validar_cns_prescritor()`` (pode ser None).

    Retorna
    -------
    dict com chaves: ``nivel``, ``pontuacao``, ``fatores``, ``resumo``
    """
    pontos = _BASE
    fatores: list[str] = []

    p_presc, f_presc = _contribuicao_prescritor(cnes_validacao)
    pontos += p_presc
    fatores.extend(f_presc)

    pontuacao = _clampar(pontos)
    nivel = _nivel(pontuacao)

    return {
        "nivel":     nivel,
        "pontuacao": pontuacao,
        "fatores":   fatores,
        "resumo":    _gerar_resumo(nivel, fatores),
    }


def calcular_score_confianca_dispensacao(
    cnes_validacao: Optional[dict],
    origem_contexto: Optional[str],
    contexto_confirmado_manual: Optional[bool] = None,
) -> dict:
    """
    Calcula o score de confiança para o contexto de dispensação.

    Chamado em ``dispensar_item`` com os dados do prescritor (recuperados
    do evento ``prescricao_emitida``) e do contexto do estabelecimento.

    Parâmetros
    ----------
    cnes_validacao              Bloco CNES do prescritor (pode ser None).
    origem_contexto             ``'cnes_verificado'`` | ``'manual'`` | None
    contexto_confirmado_manual  True | False | None (relevante quando manual)

    Retorna
    -------
    dict com chaves: ``nivel``, ``pontuacao``, ``fatores``, ``resumo``
    """
    pontos = _BASE
    fatores: list[str] = []

    p_presc, f_presc = _contribuicao_prescritor(cnes_validacao)
    pontos += p_presc
    fatores.extend(f_presc)

    p_prest, f_prest = _contribuicao_prestador(origem_contexto, contexto_confirmado_manual)
    pontos += p_prest
    fatores.extend(f_prest)

    pontuacao = _clampar(pontos)
    nivel = _nivel(pontuacao)

    return {
        "nivel":     nivel,
        "pontuacao": pontuacao,
        "fatores":   fatores,
        "resumo":    _gerar_resumo(nivel, fatores),
    }
