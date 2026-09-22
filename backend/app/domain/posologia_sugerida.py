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

A CHAVE É COMPOSTA — `(ativo, CID)` (ENG-019)
---------------------------------------------
Até 13/09/2026 o índice era `dict[ativo → Posologia]`, e **a última row do CSV
vencia em silêncio**. Não doía enquanto nenhuma condição coberta compartilhava
substância com outra; I50 (insuficiência cardíaca) e J44 (DPOC) trouxeram o
primeiro choque real — nove colisões com HAS, asma e DM2. Carvedilol começa em
3,125 mg 2x/dia na IC; sobrescrever com isso a dose de hipertensão é **erro
clínico calado** — o pior tipo, porque não deixa rastro nem pergunta.

As nove rows foram retiradas na hora e voltaram aqui, sob a chave certa. A
substância que trata duas condições passa a ter **uma dose viva por condição**,
e quem escolhe entre elas é o CID da prescrição em curso — não a ordem das
linhas no arquivo.

A BUSCA DEGRADA PARA O SILÊNCIO, NUNCA PARA O PALPITE
-----------------------------------------------------
Com CID: sobe a mesma cadeia do semáforo (`I50.0` → `I50`) e, se nada casar,
**não sugere**. Servir a dose de outra condição porque "é o mesmo fármaco" é
exatamente o defeito que este módulo passou a impedir.

Sem CID: só responde quando a substância é **unívoca** (uma row só no CSV
inteiro) — aí não há o que confundir. Havendo colisão, silêncio + log: nunca
"a última vence".

Ver docs/tickets/DESENHO-POSOLOGIA-POR-CONDICAO.md e
docs/ARQUITETURA_DECISAO_CLINICA.md (3ª função: fármaco → posologia usual).
"""
from __future__ import annotations

import csv as _csv
import logging as _logging
import os as _os
from dataclasses import dataclass
from typing import Optional

from app.domain.semaforo_decisao import (  # reuso: canonicalização E cadeia do CID
    cadeia_cid,
    canon_ativo,
    canon_cid,
)

_STATUS_VALIDADO = "validado"

_logger = _logging.getLogger(__name__)

# Chave do índice: `(ativo canônico, CID canônico)`.
ChavePosologia = tuple[str, str]


@dataclass(frozen=True)
class Posologia:
    """Sugestão de posologia + proveniência (auditável, como a ficha do semáforo)."""
    principio_ativo: str   # canônico (sem sal/acento)
    codigo_cid: str        # a CONDIÇÃO que fundamentou esta dose (ENG-019)
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


def carregar_posologias(caminho: str) -> dict[ChavePosologia, Posologia]:
    """Lê o CSV curado → índice `{(ativo_canônico, cid_canônico): Posologia}`.

    Só entram linhas `status_curadoria == 'validado'` (rascunhos ficam
    dormentes — linha vermelha).

    Row sem `codigo_cid` entra com CID vazio: é posologia **sem condição
    declarada**, alcançável apenas pelo caminho do ativo unívoco (ver
    `sugerir`). Descartá-la seria sumir com dado curado sem avisar; dar-lhe um
    CID inventado seria pior.
    """
    idx: dict[ChavePosologia, Posologia] = {}
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                if (row.get("status_curadoria") or "").strip() != _STATUS_VALIDADO:
                    continue
                ativo_k = canon_ativo(row.get("principio_ativo") or "")
                posologia = (row.get("posologia_usual") or "").strip()
                if not ativo_k or not posologia:
                    continue
                cid_k = canon_cid(row.get("codigo_cid") or "")
                idx[(ativo_k, cid_k)] = Posologia(
                    principio_ativo=ativo_k,
                    codigo_cid=cid_k,
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


def agrupar_por_ativo(
    idx: dict[ChavePosologia, Posologia],
) -> dict[str, tuple[Posologia, ...]]:
    """Vista por princípio ativo — é ela que responde *"esta substância é
    unívoca?"*, a pergunta de que depende o fallback sem CID.

    Função pura e exportada de propósito: a regra "unívoco → pode servir sem
    CID" é clínica, não detalhe de cache, e precisa ser testável sozinha.
    """
    por_ativo: dict[str, list[Posologia]] = {}
    for (ativo_k, _cid), p in idx.items():
        por_ativo.setdefault(ativo_k, []).append(p)
    return {a: tuple(ps) for a, ps in por_ativo.items()}


_CACHE: Optional[dict[ChavePosologia, Posologia]] = None
_CACHE_POR_ATIVO: Optional[dict[str, tuple[Posologia, ...]]] = None
_ULTIMO_IDX: Optional[dict[ChavePosologia, Posologia]] = None


def _idx() -> dict[ChavePosologia, Posologia]:
    global _CACHE
    if _CACHE is None:
        _CACHE = carregar_posologias(_resolver_csv())
    return _CACHE


def _por_ativo() -> dict[str, tuple[Posologia, ...]]:
    """A vista por ativo, derivada do índice vigente.

    Recalculada quando o índice não é o mesmo objeto de antes — os testes (e o
    reload de CSV) trocam `_CACHE` direto, e uma vista velha responderia
    "unívoco" sobre um CSV que já mudou.
    """
    global _CACHE_POR_ATIVO, _ULTIMO_IDX
    idx = _idx()
    if _CACHE_POR_ATIVO is None or _ULTIMO_IDX is not idx:
        _CACHE_POR_ATIVO = agrupar_por_ativo(idx)
        _ULTIMO_IDX = idx
    return _CACHE_POR_ATIVO


def sugerir(
    principio_ativo: Optional[str],
    codigo_cid: Optional[str] = None,
) -> Optional[Posologia]:
    """Sugestão para `(princípio ativo, CID)`. `None` = silêncio honesto.

    Com CID: casa pela cadeia do semáforo — `I50.0` antes de `I50` — e, sem
    casar, **não sugere**. Emprestar a dose de outra condição porque a
    substância é a mesma é o erro que esta função existe para não cometer.

    Sem CID (`None`/vazio): só serve quando a substância tem **uma única**
    posologia curada no CSV inteiro. Com mais de uma, silêncio + log: quem
    escolheria seria a ordem das linhas no arquivo, e ordem de arquivo não é
    critério clínico.
    """
    ativo_k = canon_ativo(principio_ativo or "")
    if not ativo_k:
        return None

    candidatas = _por_ativo().get(ativo_k, ())
    if not candidatas:
        return None

    cid_k = canon_cid(codigo_cid or "")
    if cid_k:
        idx = _idx()
        for elo in cadeia_cid(cid_k):
            achou = idx.get((ativo_k, elo))
            if achou is not None:
                return achou
        return None   # degrada seguro: nenhuma condição casou

    if len(candidatas) == 1:
        return candidatas[0]   # substância unívoca → retrocompat preservada

    _logger.info(
        "posologia sem sugestão: '%s' tem %d posologias curadas (%s) e a "
        "requisição não informou CID. Silêncio por segurança — servir uma "
        "delas seria deixar a ordem do CSV escolher a dose.",
        ativo_k,
        len(candidatas),
        ", ".join(sorted(p.codigo_cid or "(sem CID)" for p in candidatas)),
    )
    return None


def total_posologias() -> int:
    """Número de posologias validadas carregadas (health/diagnóstico)."""
    return len(_idx())
