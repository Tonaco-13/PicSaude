"""
posologia_sugerida.py — sugestão determinística de posologia usual.
====================================================================

Quando o prescritor escolhe o fármaco, o sistema **sugere a posologia usual**
para ele **AVALIAR e EDITAR**. NUNCA preenche de forma vinculante; é um rascunho
editável que pré-popula o campo de posologia. O prescritor é o responsável final.

PRINCÍPIOS (companheiro do semáforo — mesma família de apoio à decisão):
- DETERMINÍSTICO, baseado em lookup. SEM LLM, SEM ML.
- A inteligência mora no DADO CURADO; a engine só serve linhas
  `status_curadoria == 'validado'` (linha vermelha — conteúdo clínico assinado).
- Mesma canonicalização de princípio ativo do semáforo (remove sal/acento/caixa).

Ver docs/ARQUITETURA_DECISAO_CLINICA.md (3ª função: fármaco → posologia usual).
"""
from __future__ import annotations

import csv as _csv
import os as _os
from dataclasses import dataclass
from typing import Optional

from app.domain.semaforo_decisao import canon_ativo   # reuso da canonicalização

_STATUS_VALIDADO = "validado"


@dataclass(frozen=True)
class Posologia:
    """Sugestão de posologia + proveniência (auditável, como a ficha do semáforo)."""
    principio_ativo: str   # canônico (sem sal/acento)
    posologia: str         # texto que pré-popula o campo (editável)
    condicao: str
    fonte: str
    validado_por: str
    versao: str
    observacao: str


def _resolver_csv() -> str:
    """Caminho do CSV curado. Env `PICSAUDE_POSOLOGIA_CSV` tem prioridade
    (empacotamento Docker); senão, layout de dev (data/ na raiz do repo)."""
    override = _os.getenv("PICSAUDE_POSOLOGIA_CSV")
    if override:
        return override
    return _os.path.normpath(
        _os.path.join(_os.path.dirname(__file__), "..", "..", "..",
                      "data", "posologia_sugerida.csv")
    )


def carregar_posologias(caminho: str) -> dict[str, Posologia]:
    """Lê o CSV curado → índice {ativo_canônico: Posologia}. Só entram linhas
    `status_curadoria == 'validado'` (rascunhos ficam dormentes — linha vermelha)."""
    idx: dict[str, Posologia] = {}
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                if (row.get("status_curadoria") or "").strip() != _STATUS_VALIDADO:
                    continue
                ativo_k = canon_ativo(row.get("principio_ativo") or "")
                posologia = (row.get("posologia_usual") or "").strip()
                if not ativo_k or not posologia:
                    continue
                idx[ativo_k] = Posologia(
                    principio_ativo=ativo_k,
                    posologia=posologia,
                    condicao=(row.get("condicao_nome") or "").strip(),
                    fonte=(row.get("fonte") or "").strip(),
                    validado_por=(row.get("validado_por") or "").strip(),
                    versao=(row.get("versao") or "").strip(),
                    observacao=(row.get("observacao") or "").strip(),
                )
    except FileNotFoundError:
        pass   # sem CSV → sem sugestões (degrada seguro)
    return idx


_CACHE: Optional[dict[str, Posologia]] = None


def _idx() -> dict[str, Posologia]:
    global _CACHE
    if _CACHE is None:
        _CACHE = carregar_posologias(_resolver_csv())
    return _CACHE


def sugerir(principio_ativo: Optional[str]) -> Optional[Posologia]:
    """Sugestão para o princípio ativo (canonicalizado). None se não houver
    posologia validada — a UI então não oferece nada (silêncio honesto)."""
    ativo_k = canon_ativo(principio_ativo or "")
    if not ativo_k:
        return None
    return _idx().get(ativo_k)


def total_posologias() -> int:
    """Número de posologias validadas carregadas (health/diagnóstico)."""
    return len(_idx())
