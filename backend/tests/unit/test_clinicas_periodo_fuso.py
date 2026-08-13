"""Guarda do fuso misto nos relatórios da clínica — achado do TICKET-H.

O DEFEITO QUE ESTE ARQUIVO TRAVA
--------------------------------
O banco guarda `resultado_em` em DOIS formatos, dependendo de quem escreveu:

    seed_demo.py    → datetime.now(timezone.utc).isoformat()   → "...+00:00"  (aware)
    routers/*.py    → datetime.utcnow().isoformat()            → "..."        (naive)

A janela de período de `clinicas.py` é naive. Comparar um lado aware com um lado
naive estoura `TypeError: can't compare offset-naive and offset-aware datetimes`
— e o endpoint devolve **500**, não uma lista vazia.

POR QUE PASSOU DESPERCEBIDO
---------------------------
Os testes de integração rodam contra PostgreSQL e criam os dados PELA API, então
nunca viram uma linha do seed. O defeito só aparece onde o seed está: no banco de
demo — isto é, **na vitrine**. Os botões "Relatório de exames" e "Faturamento" do
`clinica.html` quebravam com 500 lá, e nenhum gate acusava.

A correção fica no funil único (`_como_datetime`), porque as DUAS rotas passam
por ele: `_filtrar_periodo` (relatório) e `_linhas_faturamento` (faturamento).
Estes testes cobrem as duas, para a próxima regressão morrer aqui e não na demo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.routers.clinicas import (
    _como_datetime,
    _filtrar_periodo,
    _janela_periodo,
)


# ---------------------------------------------------------------------------
# O normalizador
# ---------------------------------------------------------------------------

def test_como_datetime_devolve_sempre_naive():
    """Aware ou naive na entrada, naive na saída — é o que torna a comparação
    possível. Sem isto, metade das linhas do banco derruba o endpoint."""
    aware = _como_datetime("2026-08-13T10:00:00+00:00")
    naive = _como_datetime("2026-08-13T10:00:00")
    objeto_aware = _como_datetime(datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc))

    for dt in (aware, naive, objeto_aware):
        assert dt is not None
        assert dt.tzinfo is None, f"{dt!r} saiu com fuso — a comparação vai estourar"


def test_como_datetime_converte_para_utc_antes_de_descartar_o_fuso():
    """Descartar o fuso sem converter deslocaria o instante em 3 horas — um exame
    das 23h entraria no dia seguinte, e o relatório do período mentiria."""
    assert _como_datetime("2026-08-13T07:00:00-03:00") == datetime(2026, 8, 13, 10, 0)


def test_como_datetime_tolera_lixo_e_nulo():
    assert _como_datetime(None) is None
    assert _como_datetime("nem data nem nada") is None


# ---------------------------------------------------------------------------
# As duas rotas que consomem o normalizador
# ---------------------------------------------------------------------------

def _linha(chave: str, valor: str) -> dict:
    return {"protocolo": "p", "item_id": 1, chave: valor}


def test_filtrar_periodo_nao_estoura_com_fusos_misturados():
    """Rota do RELATÓRIO. Uma linha do seed (aware) ao lado de uma da API
    (naive) — o caso exato do banco de demo."""
    hoje = datetime.utcnow()
    dt_inicio, dt_fim, _ = _janela_periodo(
        (hoje - timedelta(days=1)).date().isoformat(),
        (hoje + timedelta(days=1)).date().isoformat(),
    )

    linhas = [
        _linha("data_resultado", hoje.replace(tzinfo=timezone.utc).isoformat()),  # seed
        _linha("data_resultado", hoje.isoformat()),                              # API
    ]

    dentro = _filtrar_periodo(linhas, dt_inicio, dt_fim)
    assert len(dentro) == 2, "linha com fuso foi descartada ou derrubou o filtro"


def test_filtrar_periodo_ainda_exclui_o_que_esta_fora_da_janela():
    """A tolerância ao fuso não pode ter virado 'aceita tudo'."""
    hoje = datetime.utcnow()
    dt_inicio, dt_fim, _ = _janela_periodo(
        (hoje - timedelta(days=1)).date().isoformat(),
        (hoje + timedelta(days=1)).date().isoformat(),
    )
    antiga = (hoje - timedelta(days=400)).replace(tzinfo=timezone.utc).isoformat()

    assert _filtrar_periodo([_linha("data_resultado", antiga)], dt_inicio, dt_fim) == []
