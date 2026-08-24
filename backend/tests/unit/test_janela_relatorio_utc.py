"""
test_janela_relatorio_utc.py — ENG-017 PR C (achado A1 da comissão #189).

A REGRA QUE ESTE ARQUIVO TRAVA
------------------------------
**A janela dos relatórios usa o mesmo relógio que carimba os registros: UTC.**

O defeito, com a prova numérica que a comissão colheu:

    local  2026-08-23 21:24 -03      UTC  2026-08-24 00:24
    janela do relatório → até 2026-08-23 23:59:59   (date.today(), LOCAL)
    registro gravado    →    2026-08-24 00:24       (utcnow(), UTC)
    dentro da janela?   → False

No fuso −03, entre 21h e 24h, **tudo o que fosse criado caía fora** da janela
padrão de 30 dias. Atingiu SNGPC, faturamento, histórico da clínica e o E2E do
laboratório.

POR QUE O GATE ERA CEGO — E POR QUE ESTE ARQUIVO NÃO BASTA SOZINHO
-------------------------------------------------------------------
O CI roda em **UTC**, onde local e UTC coincidem: nunca viu. Estes testes
comparam a janela com o relógio UTC e valem em qualquer fuso — mas o que
realmente fecha a classe é o **job de gate com `TZ` pinado** (variante
`America/Recife`, ver `.github/workflows/gates.yml`). Um prova a REGRA; o outro
roda a suíte inteira no fuso onde o defeito aparece.

Teste dependente de relógio de parede precisa de TZ pinado ou relógio injetado.
Antes deste PR não havia nem um nem outro — e é por isso que a família voltou
(a primeira vez foi o "500 do faturamento por fuso").
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.routers.clinicas import _janela_periodo as janela_clinica
from app.routers.dispensadores import _janela_periodo as janela_dispensador
from app.utils.relogio import agora_utc, hoje_utc

_ROUTERS = Path(__file__).resolve().parents[2] / "app" / "routers"

_JANELAS = [
    pytest.param(janela_dispensador, id="dispensador"),
    pytest.param(janela_clinica, id="clinica"),
]


# ---------------------------------------------------------------------------
# 1 — o relógio
# ---------------------------------------------------------------------------

def test_hoje_utc_e_o_dia_em_utc():
    assert hoje_utc() == datetime.now(timezone.utc).date()


def test_agora_utc_e_ciente_de_fuso():
    """Ingênuo (`utcnow()`) comparado com ciente estoura em runtime — e um
    `TypeError` no meio de um relatório é pior que a janela errada."""
    assert agora_utc().tzinfo is not None


# ---------------------------------------------------------------------------
# 2 — a janela, nas DUAS cópias
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("janela", _JANELAS)
def test_a_janela_padrao_fecha_no_dia_UTC(janela):
    """O assert que teria pego o A1 em qualquer fuso.

    Em UTC este teste passa dos dois jeitos (é por isso que o CI era cego); no
    fuso −03, entre 21h e 24h, ele SÓ passa com a correção. O job de TZ pinado
    é o que garante que essa faixa seja exercida.
    """
    _di, dt_fim, _f = janela(None, None)
    assert dt_fim.date() == hoje_utc(), (
        f"a janela fecha em {dt_fim.date()} e o dia UTC é {hoje_utc()} — "
        "voltou a usar a hora local do processo (A1)"
    )


@pytest.mark.parametrize("janela", _JANELAS)
def test_o_registro_carimbado_AGORA_cai_dentro_da_janela(janela):
    """O sintoma, virado teste: um registro criado neste instante — em UTC,
    como o código carimba — tem de aparecer no relatório padrão. Era
    exatamente isto que falhava."""
    dt_inicio, dt_fim, _f = janela(None, None)
    agora_ingenuo = agora_utc().replace(tzinfo=None)
    assert dt_inicio <= agora_ingenuo <= dt_fim, (
        f"registro de agora ({agora_ingenuo}) fora da janela "
        f"[{dt_inicio}, {dt_fim}] — é o A1, de volta"
    )


@pytest.mark.parametrize("janela", _JANELAS)
def test_a_janela_padrao_cobre_30_dias(janela):
    dt_inicio, dt_fim, _f = janela(None, None)
    assert (dt_fim.date() - dt_inicio.date()).days == 30


@pytest.mark.parametrize("janela", _JANELAS)
def test_filtros_explicitos_continuam_mandando(janela):
    """A correção é do DEFAULT. Data pedida pelo operador é dele — e é local
    do ponto de vista dele, porque ele a digitou."""
    dt_inicio, dt_fim, filtros = janela("2026-01-01", "2026-01-31")
    assert dt_inicio.date().isoformat() == "2026-01-01"
    assert dt_fim.date().isoformat() == "2026-01-31"
    assert filtros["data_inicio"] == "2026-01-01"


# ---------------------------------------------------------------------------
# 2b — o defeito REPRODUZIDO, sem depender da hora em que a suíte roda
# ---------------------------------------------------------------------------
# O job de TZ pinado só exercita a faixa 21h–24h — três horas em vinte e
# quatro. Um gate que pega o defeito 1/8 das vezes é melhor que nada e pior que
# suficiente: o A1 já passou despercebido uma vez.
#
# Estes dois testes reproduzem a divergência ARITMETICAMENTE, a partir do
# instante exato que a comissão registrou. Valem a qualquer hora, em qualquer
# fuso, para sempre.

_INSTANTE_DA_COMISSAO = datetime(2026, 8, 24, 0, 24, tzinfo=timezone.utc)
_FUSO_DO_FABIANO = "America/Recife"      # −03, sem horário de verão


def _dia_local(instante, fuso: str):
    from zoneinfo import ZoneInfo
    return instante.astimezone(ZoneInfo(fuso)).date()


def test_o_defeito_A1_existe_e_esta_reproduzido():
    """A divergência que causou tudo, em números — sem relógio de parede.

    00:24 UTC de 24/08 é 21:24 de 23/08 em Recife. Uma janela fechada no dia
    LOCAL termina às 23:59:59 de 23/08; o registro, carimbado em UTC, nasce em
    24/08. Fica fora, e ninguém percebe porque a data existe e parece certa.
    """
    dia_local = _dia_local(_INSTANTE_DA_COMISSAO, _FUSO_DO_FABIANO)
    dia_utc = _INSTANTE_DA_COMISSAO.date()
    assert dia_local != dia_utc, "o cenário do A1 deixou de divergir"

    fim_da_janela_local = datetime.combine(
        dia_local, datetime.max.time().replace(microsecond=0))
    registro = _INSTANTE_DA_COMISSAO.replace(tzinfo=None)
    assert registro > fim_da_janela_local, (
        "a reprodução do A1 parou de reproduzir — revisar o cenário antes de "
        "concluir que o defeito sumiu"
    )


def test_a_janela_em_UTC_teria_incluido_o_registro():
    """A outra metade: com o dia em UTC, o mesmo registro cai DENTRO.

    É a prova de que a correção resolve o cenário — e não apenas de que o
    cenário existe.
    """
    dia_utc = _INSTANTE_DA_COMISSAO.date()
    fim_da_janela_utc = datetime.combine(
        dia_utc, datetime.max.time().replace(microsecond=0))
    inicio = datetime.combine(dia_utc, datetime.min.time()) - timedelta(days=30)
    registro = _INSTANTE_DA_COMISSAO.replace(tzinfo=None)
    assert inicio <= registro <= fim_da_janela_utc


# ---------------------------------------------------------------------------
# 3 — a guarda estática: `date.today()` não volta para dentro das janelas
# ---------------------------------------------------------------------------

def _corpo_da_janela(arquivo: str) -> str:
    fonte = (_ROUTERS / arquivo).read_text(encoding="utf-8")
    m = re.search(r"def _janela_periodo\(.*?\n(?=\n\n|\ndef |\n@)", fonte, re.S)
    assert m, f"_janela_periodo sumiu de {arquivo}"
    return m.group(0)


@pytest.mark.parametrize("arquivo", ["dispensadores.py", "clinicas.py"])
def test_a_janela_nao_pergunta_a_hora_local(arquivo):
    """`date.today()` dentro da janela é o A1 de volta.

    Ignora comentários: o corpo EXPLICA o defeito citando `date.today()`, e
    guarda que acusa a própria explicação é ruído.
    """
    corpo = "\n".join(
        l for l in _corpo_da_janela(arquivo).splitlines()
        if not l.strip().startswith("#")
    )
    assert "date.today()" not in corpo, (
        f"{arquivo}: a janela voltou a usar a hora local do processo (A1)"
    )
    assert "hoje_utc()" in corpo, f"{arquivo}: a janela deixou de usar o relógio UTC"


class TestAsGuardasMordem:
    def test_date_today_na_janela_seria_acusado(self):
        falso = "        df = date.today()\n        di = df - timedelta(days=30)"
        corpo = "\n".join(l for l in falso.splitlines() if not l.strip().startswith("#"))
        assert "date.today()" in corpo

    def test_o_comentario_que_explica_nao_e_acusado(self):
        ok = ("        # antes usava date.today() — hora local, era o A1\n"
              "        df = hoje_utc()")
        corpo = "\n".join(l for l in ok.splitlines() if not l.strip().startswith("#"))
        assert "date.today()" not in corpo
