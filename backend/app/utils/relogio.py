"""
relogio.py — o "agora" do SISTEMA, não o de quem roda o processo.

POR QUE ESTE MÓDULO EXISTE
--------------------------
ENG-017 PR C, a partir do achado A1 da comissão de diagnóstico (#189).

O PicSaúde carimba todo registro em **UTC** (`datetime.utcnow()` espalhado pelos
routers) e calculava a janela dos relatórios com `date.today()`, que é **hora
local do processo**. No fuso −03, entre 21h e 24h, o "hoje" local já é ONTEM em
UTC — e tudo o que fosse criado nessa faixa caía **fora** da janela padrão de 30
dias.

A prova, colhida na comissão:

    local  2026-08-23 21:24 -03      UTC  2026-08-24 00:24
    janela do relatório → até 2026-08-23 23:59:59   (date.today(), LOCAL)
    registro gravado    →    2026-08-24 00:24       (utcnow(), UTC)
    dentro da janela?   → False

Alcance medido: relatório SNGPC, faturamento, histórico da clínica e o E2E do
laboratório — 10 arquivos de integração, 1 de unidade, 3 casos de navegador.

E O GATE NUNCA VIU: o CI roda em **UTC**, onde local e UTC coincidem. Um defeito
real de produção ficou invisível por escolha de fuso do runner. É a segunda vez
que esta família aparece (a primeira foi o "500 do faturamento por fuso").

A REGRA, DAQUI PARA A FRENTE
----------------------------
**Quem compara com dado carimbado em UTC pergunta a hora a este módulo.**
`date.today()` e `datetime.now()` sem fuso continuam válidos para o que é
LOCAL de verdade — nome de arquivo que o operador baixa, saudação na tela —,
mas nunca para recortar dado.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def agora_utc() -> datetime:
    """O instante atual em UTC, ciente de fuso."""
    return datetime.now(timezone.utc)


def hoje_utc() -> date:
    """O DIA corrente em UTC — o mesmo relógio que carimba os registros.

    É esta a função que as janelas de relatório usam. Trocá-la por
    `date.today()` reabre o A1: a janela passa a fechar em meia-noite local
    contra registros gravados em UTC.
    """
    return agora_utc().date()
