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
SINAL_NEUTRO = "neutro"       # sem julgamento — o semáforo se cala (sem ponto na UI)


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
    cids_exaustivos: set[str],
) -> Avaliacao:
    """Avalia a coerência fármaco ↔ CID e devolve o sinal.

    LEI DA EXAUSTIVIDADE (decisão Fabiano 2026-06-21): o semáforo só JULGA uma
    condição cuja lista 🟢 é EXAUSTIVA em relação ao PCDT. Numa condição não
    exaustiva, o sinal seria viés — então o semáforo se CALA (neutro). Assim ele
    é autoritativo quando fala e honesto quando se cala.

    Parâmetros
    ----------
    aprovados        : índice {(cid_canônico, ativo_canônico): fonte} — regras 🟢
                       curadas/assinadas (do PCDT).
    cids_exaustivos  : CIDs (canônicos) cuja curadoria é COMPLETA. Só nesses a
                       ausência de um fármaco tem significado (🟡).

    Regras (Fase 1 — sem 🔴):
      1. (CID, ativo) aprovado            → 🟢
      2. CID exaustivo, ativo não consta  → 🟡 (fora do protocolo — confira)
      3. caso contrário (não exaustivo)   → neutro (sem julgamento, sem ponto)
    """
    if not codigo_cid or not principio_ativo:
        return Avaliacao(SINAL_NEUTRO, "indicação ou fármaco ausente", None)

    ativo_k = canon_ativo(principio_ativo)
    cadeia = cadeia_cid(codigo_cid)

    # PORTÃO DA EXAUSTIVIDADE (primeiro!). Se a condição não tem lista COMPLETA,
    # o semáforo não julga NADA — nem 🟢. Mostrar 🟢 só para os fármacos que
    # curamos privilegiaria-os sobre os válidos que faltam (o viés que Fabiano
    # apontou). Então: condição não-exaustiva → neutro (silêncio).
    if not any(cid_k in cids_exaustivos for cid_k in cadeia):
        return Avaliacao(SINAL_NEUTRO, "sem curadoria exaustiva para esta condição", None)

    # Condição EXAUSTIVA → o semáforo pode julgar.
    # 1) Aprovado (🟢) — busca subindo a hierarquia do CID.
    for cid_k in cadeia:
        fonte = aprovados.get((cid_k, ativo_k))
        if fonte:
            return Avaliacao(SINAL_VERDE, "tratamento reconhecido para a condição", fonte)

    # 2) Fármaco fora da lista completa do protocolo → 🟡 (informação honesta).
    return Avaliacao(
        SINAL_AMARELO,
        "fármaco fora do protocolo desta condição — confira",
        None,
    )


# ---------------------------------------------------------------------------
# Carregamento das regras curadas (só serve o que está `validado`)
# ---------------------------------------------------------------------------

import csv as _csv          # noqa: E402  (import local ao bloco de loading)
import os as _os            # noqa: E402

_STATUS_VALIDADO = "validado"


def _resolver_csv() -> str:
    """Caminho do CSV curado. Env `PICSAUDE_SEMAFORO_CSV` tem prioridade
    (empacotamento Docker); senão, layout de dev (data/ na raiz do repo)."""
    override = _os.getenv("PICSAUDE_SEMAFORO_CSV")
    if override:
        return override
    return _os.path.normpath(
        _os.path.join(
            _os.path.dirname(__file__), "..", "..", "..",
            "data", "decisao_semaforo.csv",
        )
    )


_VALORES_VERDADE = ("true", "sim", "1", "verdadeiro")


def carregar_regras(caminho: str) -> tuple[dict[tuple[str, str], str], set[str]]:
    """Lê o CSV curado → (aprovados, cids_exaustivos).

    INVARIANTES:
    - só entram regras com `status_curadoria == 'validado'` (linha vermelha);
    - `cids_exaustivos` = CIDs marcados `exaustivo` (lista 🟢 COMPLETA). Só nesses
      o semáforo julga a ausência (🟡); senão se cala (lei da exaustividade).
    """
    aprovados: dict[tuple[str, str], str] = {}
    cids_exaustivos: set[str] = set()
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                if (row.get("status_curadoria") or "").strip() != _STATUS_VALIDADO:
                    continue
                cid_k = canon_cid(row.get("codigo_cid") or "")
                ativo_k = canon_ativo(row.get("principio_ativo") or "")
                if not cid_k or not ativo_k:
                    continue
                fonte = (row.get("condicao_nome") or "").strip() or cid_k
                aprovados[(cid_k, ativo_k)] = fonte
                if (row.get("exaustivo") or "").strip().lower() in _VALORES_VERDADE:
                    cids_exaustivos.add(cid_k)
    except FileNotFoundError:
        pass   # sem CSV → sem regras → tudo neutro (degrada seguro)
    return aprovados, cids_exaustivos


_REGRAS_CACHE: Optional[tuple[dict, set]] = None


def _regras() -> tuple[dict, set]:
    global _REGRAS_CACHE
    if _REGRAS_CACHE is None:
        _REGRAS_CACHE = carregar_regras(_resolver_csv())
    return _REGRAS_CACHE


def avaliar(codigo_cid: Optional[str], principio_ativo: Optional[str]) -> Avaliacao:
    """Avalia usando as regras curadas carregadas (cacheadas)."""
    aprovados, cids = _regras()
    return avaliar_semaforo(codigo_cid, principio_ativo, aprovados, cids)


def total_regras() -> int:
    """Número de regras 🟢 validadas carregadas (para health/diagnóstico)."""
    return len(_regras()[0])
