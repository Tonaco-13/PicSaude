"""
auditoria_decisao.py — trilha de auditoria da decisão clínica (camada 3).
=========================================================================

No momento da EMISSÃO de uma prescrição digital, registra qual sinal do semáforo
(🟢/🟡/neutro) foi atribuído a cada item e SOB QUAL VERSÃO de regra. É o
complemento *persistente* da ficha de explicabilidade (camada 2):

    camada 2 (ficha)   → recomputável sob demanda (determinística)
    camada 3 (trilha)  → registro do que foi efetivamente apresentado, no tempo

A trilha vive no **ledger imutável** (evento `decisao_clinica_avaliada` em
`prescricao_eventos`) — não é tabela nova; é um novo tipo de evento no append-only
que já é a coluna vertebral de auditoria do PicSaúde.

Determinístico, sem LLM. O registro é **não-bloqueante**: a camada de chamada
(router de emissão) envolve esta montagem e o INSERT em try/except — a trilha
NUNCA pode quebrar a emissão de uma prescrição.

Ver docs/EXPLICABILIDADE_DECISAO_CLINICA.md §11.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

from app.domain.semaforo_decisao import avaliar, total_regras

# Tipo de evento no ledger (vocabulário em CLAUDE.md §2).
TIPO_EVENTO_DECISAO = "decisao_clinica_avaliada"


def montar_trilha_decisao(
    codigo_cid: Optional[str],
    itens: Sequence[Tuple[int, str]],
) -> dict:
    """Constrói o payload da trilha a partir do CID da prescrição e da lista de
    itens emitidos `(item_id, nome_medicamento)`.

    Avalia cada item no semáforo e captura o que torna a decisão auditável no
    futuro: sinal, causa, exaustividade, a regra e a **versão da curadoria** que
    a produziu. Função PURA — sem I/O de banco; o router faz o INSERT no ledger.

    Mesma entrada + mesma versão de curadoria → mesmo payload (determinismo).
    """
    avaliacoes = []
    for item_id, nome in itens:
        a = avaliar(codigo_cid, nome)
        prov = a.proveniencia
        avaliacoes.append(
            {
                "item_id": item_id,
                "nome_medicamento": nome,
                "principio_ativo_canonico": a.ativo_canonico,
                "sinal": a.sinal,
                "causa": a.causa,
                "exaustiva": a.exaustiva,
                "regra": a.regra,
                "versao_regra": prov.versao if prov else None,
                "fonte": prov.fonte if prov else None,
            }
        )
    return {
        "codigo_cid": codigo_cid,
        "total_regras_carregadas": total_regras(),
        "avaliacoes": avaliacoes,
    }
