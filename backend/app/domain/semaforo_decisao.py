"""
semaforo_decisao.py — motor do semáforo de apoio à decisão (VALIDADOR).
=====================================================================

Confere a ESCOLHA do prescritor (fármaco) contra a INDICAÇÃO (CID) e devolve um
sinal discreto e NÃO-BLOQUEANTE:

    🟢 verde    — fármaco é tratamento reconhecido para o CID (consta no PCDT)
    🟡 amarelo  — sem base para afirmar (CID sem PCDT, ou fármaco não-listado)
    🔴 vermelho — contraindicação/perigo real  (FASE 2 — ainda não nesta v1)

PRINCÍPIOS (ver docs/ARQUITETURA_DECISAO_CLINICA.md)
---------------------------------------------------
- DETERMINÍSTICO, baseado em lookup. SEM LLM, SEM ML. "Por que este sinal?" tem
  resposta exata e rastreável à fonte (o PCDT).
- O sistema VALIDA e SINALIZA — nunca recomenda fármaco, nunca bloqueia.
- A inteligência mora no DADO CURADO (regras do PCDT), não no algoritmo.
- Anti-fadiga-de-alerta: incerteza → 🟡 (honesto). 🔴 reservado a perigo real.

A v1 acende 🟢/🟡. O 🔴 (contraindicações) é a Fase 2.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

SINAL_VERDE = "verde"
SINAL_AMARELO = "amarelo"
SINAL_VERMELHO = "vermelho"   # reservado — Fase 2


@dataclass(frozen=True)
class Avaliacao:
    sinal: str                # verde | amarelo | vermelho
    motivo: str               # explicação curta e legível
    fonte: Optional[str]      # proveniência (ex.: "PCDT Hipertensão") ou None


# ---------------------------------------------------------------------------
# Canonicalização do princípio ativo (remove sal/acento/caixa)
# ---------------------------------------------------------------------------

# Prefixos de sal "X de <ativo>" (a parte antes do ativo). Conservador.
_SAIS_PREFIXO = (
    "cloridrato de", "bromidrato de", "oxalato de", "sulfato de", "fosfato de",
    "maleato de", "besilato de", "mesilato de", "succinato de", "tartarato de",
    "acetato de", "nitrato de", "citrato de", "fumarato de", "hemifumarato de",
    "pamoato de", "lactato de", "gluconato de", "carbonato de", "valerato de",
    "dipropionato de", "estearato de", "propionato de", "dicloridrato de",
)
# Sufixos de sal (adjetivos após o ativo).
_SAIS_SUFIXO = (
    "sodico", "potassico", "potassica", "calcico", "calcica", "magnesico",
    "de sodio", "de potassio", "de calcio", "dihidratado", "monoidratado",
    "anidro", "trihidratado",
)


def _strip_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canon_ativo(nome: str) -> str:
    """Chave canônica do princípio ativo (sem sal/acento/caixa/espaço extra).

    "Oxalato de Escitalopram" → "escitalopram"
    "Losartana Potássica"     → "losartana"
    """
    s = _strip_acentos((nome or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    for pref in _SAIS_PREFIXO:
        if s.startswith(pref + " "):
            s = s[len(pref) + 1:]
            break
    for suf in _SAIS_SUFIXO:
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)]
            break
    return s.strip()


# ---------------------------------------------------------------------------
# Canonicalização e hierarquia do CID-10
# ---------------------------------------------------------------------------

def canon_cid(codigo: str) -> str:
    """Normaliza o código CID (maiúsculo, sem espaço). 'i10.0' → 'I10.0'."""
    return re.sub(r"\s+", "", (codigo or "").upper())


def cadeia_cid(codigo: str) -> list[str]:
    """Cadeia do mais específico ao mais amplo, para casar regra indexada num
    CID mais geral. 'I10.0' → ['I10.0', 'I10'].

    (Blocos DATASUS, ex.: I10-I15, ficam para uma versão futura — aqui usamos a
    derivação por categoria, suficiente para a v1.)
    """
    c = canon_cid(codigo)
    cadeia = [c]
    if "." in c:
        categoria = c.split(".", 1)[0]
        if categoria and categoria != c:
            cadeia.append(categoria)
    return cadeia


# ---------------------------------------------------------------------------
# Avaliação (a decisão — cadeia de regras por prioridade)
# ---------------------------------------------------------------------------

def avaliar_semaforo(
    codigo_cid: Optional[str],
    principio_ativo: Optional[str],
    aprovados: dict[tuple[str, str], str],
    cids_com_pcdt: set[str],
) -> Avaliacao:
    """Avalia a coerência fármaco ↔ CID e devolve o sinal.

    Parâmetros
    ----------
    aprovados      : índice {(cid_canônico, ativo_canônico): fonte} — as regras 🟢
                     curadas/assinadas (derivadas do PCDT).
    cids_com_pcdt  : conjunto de CIDs (canônicos) que têm PCDT — para distinguir
                     "fármaco não consta" de "não há base".

    Regras (Fase 1 — sem 🔴):
      1. (CID, ativo) aprovado  → 🟢
      2. CID tem PCDT, ativo não consta → 🟡 (não consta como tratamento)
      3. caso contrário → 🟡 (sem base)
    """
    if not codigo_cid or not principio_ativo:
        return Avaliacao(SINAL_AMARELO, "indicação ou fármaco ausente", None)

    ativo_k = canon_ativo(principio_ativo)
    cadeia = cadeia_cid(codigo_cid)

    # 1) Aprovado (🟢) — busca subindo a hierarquia do CID.
    for cid_k in cadeia:
        fonte = aprovados.get((cid_k, ativo_k))
        if fonte:
            return Avaliacao(SINAL_VERDE, "tratamento reconhecido para a condição", fonte)

    # 2) Condição tem PCDT, mas este fármaco não consta (🟡 atenção).
    for cid_k in cadeia:
        if cid_k in cids_com_pcdt:
            return Avaliacao(
                SINAL_AMARELO,
                "fármaco não consta no protocolo desta condição — confira",
                None,
            )

    # 3) Sem base para afirmar (🟡 neutro — honesto).
    return Avaliacao(SINAL_AMARELO, "sem base para confirmar coerência", None)
