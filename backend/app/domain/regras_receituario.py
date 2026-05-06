"""
regras_receituario.py
=====================
Regras de validade e emissão por tipo de receituário — Ticket 19.

Cada tipo_receituario tem regras operacionais específicas:
- validade_dias: prazo em dias a partir da emissão
- vias: número de vias do receituário
- retencao_farmacia: se a farmácia retém cópia
- requer_sncr: se exige numeração SNCR
- assinatura_minima: nível mínimo de assinatura
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping, Optional


@dataclass(frozen=True)
class RegraReceituario:
    tipo_receituario: str
    validade_dias: int | None       # None = sem validade definida
    vias: int
    retencao_farmacia: bool
    requer_sncr: bool
    assinatura_minima: str          # "qualificada" | "avancada" | "nenhuma"
    permite_reemissao_pdf: bool = True
    observacao: str | None = None


# ── Mapa de regras por tipo_receituario ─────────────────────
REGRAS_RECEITUARIO: Mapping[str, RegraReceituario] = {
    "notificacao_receita_a": RegraReceituario(
        tipo_receituario="notificacao_receita_a",
        validade_dias=30,
        vias=3,
        retencao_farmacia=True,
        requer_sncr=True,
        assinatura_minima="qualificada",
    ),
    "notificacao_receita_b": RegraReceituario(
        tipo_receituario="notificacao_receita_b",
        validade_dias=30,
        vias=2,
        retencao_farmacia=True,
        requer_sncr=True,
        assinatura_minima="qualificada",
    ),
    "receita_controle_especial": RegraReceituario(
        tipo_receituario="receita_controle_especial",
        validade_dias=30,
        vias=2,
        retencao_farmacia=True,
        requer_sncr=True,
        assinatura_minima="qualificada",
    ),
    "notificacao_receita_especial": RegraReceituario(
        tipo_receituario="notificacao_receita_especial",
        validade_dias=30,
        vias=2,
        retencao_farmacia=True,
        requer_sncr=True,
        assinatura_minima="qualificada",
        observacao="Talidomida (D1) pode ter prazo diferenciado. "
                   "TODO_REGULATORIO: confirmar prazo específico para "
                   "Notificação Especial com Anvisa.",
    ),
    "receita_retencao": RegraReceituario(
        tipo_receituario="receita_retencao",
        validade_dias=10,          # fallback; ver VALIDADE_POR_TIPO_RETENCAO
        vias=2,
        retencao_farmacia=True,
        requer_sncr=False,
        assinatura_minima="avancada",
        observacao="Validade condicional por tipo_retencao: "
                   "antimicrobiano=10 dias (RDC 471/2021), "
                   "glp1_agonista=90 dias (IN 360/2025). "
                   "requer_sncr=False é provisório (Ticket 18).",
    ),
    "receita_simples": RegraReceituario(
        tipo_receituario="receita_simples",
        validade_dias=None,
        vias=1,
        retencao_farmacia=False,
        requer_sncr=False,
        assinatura_minima="nenhuma",
    ),
}


# ── Validade condicional para receita_retencao ────────────
# Dentro do grupo RETENCAO, a validade depende do tipo_retencao
# do item (antimicrobiano vs glp1_agonista). O campo validade_dias
# da regra acima (10) é o fallback conservador (antimicrobiano).
VALIDADE_POR_TIPO_RETENCAO: Mapping[str, int] = {
    "antimicrobiano": 10,     # RDC 471/2021
    "glp1_agonista":  90,     # IN 360/2025
}


def obter_regra_receituario(tipo_receituario: str) -> RegraReceituario:
    """Retorna regra ou levanta ValueError se tipo desconhecido."""
    regra = REGRAS_RECEITUARIO.get(tipo_receituario)
    if regra is None:
        raise ValueError(
            f"Tipo de receituário desconhecido: {tipo_receituario!r}. "
            f"Tipos válidos: {sorted(REGRAS_RECEITUARIO.keys())}"
        )
    return regra


def calcular_data_validade(
    data_emissao: datetime,
    tipo_receituario: str,
    tipo_retencao: str | None = None,
) -> datetime | None:
    """Calcula data_validade = data_emissao + validade_dias.

    Para receita_retencao, a validade depende do tipo_retencao:
    - antimicrobiano: 10 dias (RDC 471/2021)
    - glp1_agonista:  90 dias (IN 360/2025)

    Retorna None se o tipo não tem validade definida.
    """
    regra = obter_regra_receituario(tipo_receituario)
    if regra.validade_dias is None:
        return None

    dias = regra.validade_dias  # fallback
    if tipo_receituario == "receita_retencao" and tipo_retencao:
        dias = VALIDADE_POR_TIPO_RETENCAO.get(tipo_retencao, dias)

    return data_emissao + timedelta(days=dias)


def receituario_expirado(
    data_validade: datetime | None,
    agora: datetime | None = None,
) -> bool:
    """Retorna True se data_validade < agora.
    None (sem validade) retorna False."""
    if data_validade is None:
        return False
    if agora is None:
        agora = datetime.utcnow()
    return data_validade < agora


# ── Níveis de assinatura (hierarquia) ───────────────────────

_HIERARQUIA_ASSINATURA = {
    "nenhuma": 0,
    "avancada": 1,
    "qualificada": 2,
}


def assinatura_atende_minimo(
    nivel_presente: str | None,
    nivel_exigido: str,
) -> bool:
    """True se o nível presente atende ou supera o exigido."""
    if nivel_exigido == "nenhuma":
        return True
    if nivel_presente is None:
        return nivel_exigido == "nenhuma"
    return _HIERARQUIA_ASSINATURA.get(nivel_presente, -1) >= \
           _HIERARQUIA_ASSINATURA.get(nivel_exigido, 99)


# ── Status que permitem geração de PDF ──────────────────────

_STATUS_PERMITE_PDF = frozenset({
    "numerado_stub",
    "numerado",
    "nao_requer_sncr",
    "emitido",      # re-download
})


def status_permite_pdf(status: str) -> bool:
    """Retorna True se o status permite geração/download de PDF."""
    return status in _STATUS_PERMITE_PDF


def validar_emissao_receituario(
    *,
    tipo_receituario: str,
    status: str,
    data_validade: datetime | None = None,
    assinatura_modo: str | None = None,
    numeracao_sncr: str | None = None,
    adapter_usado: str | None = None,
) -> tuple[bool, list[str]]:
    """
    Valida se receituário pode ser emitido (PDF gerado).
    Retorna (valido, lista_de_motivos_de_bloqueio).
    Lista vazia = válido.
    """
    motivos: list[str] = []
    regra = obter_regra_receituario(tipo_receituario)

    # 1. Status deve permitir PDF
    if not status_permite_pdf(status):
        motivos.append(
            f"Status '{status}' não permite geração de PDF. "
            f"Permitidos: {sorted(_STATUS_PERMITE_PDF)}"
        )

    # 2. Se expirado, bloqueia (exceto re-download de emitido)
    if status != "emitido" and receituario_expirado(data_validade):
        motivos.append(
            f"Receituário expirado (validade: {data_validade}). "
            "Não é possível emitir PDF de receituário vencido."
        )

    # 3. Se requer SNCR, deve ter numeração (exceto re-download)
    if regra.requer_sncr and not numeracao_sncr and status != "emitido":
        if status not in ("numerado_stub", "numerado"):
            motivos.append(
                "Receituário requer numeração SNCR mas não foi numerado."
            )

    return (len(motivos) == 0, motivos)
