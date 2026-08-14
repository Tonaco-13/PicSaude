"""TICKET-J.1 (`core`) — `derivar_status_pedido`: o pedido repousa em `resultado_disponivel`.

O DEFEITO QUE ESTE ARQUIVO TRAVA
--------------------------------
`resultado_disponivel` constava em `ESTADOS_PEDIDO_EXAME` e em `_PRIORIDADE_ESTADO`,
mas era **inalcançável**: como também é terminal no nível do ITEM, "todos os itens
com resultado" caía no ramo dos terminais e devolvia `encerrado` direto.

Três consequências, todas vistas na excursão de 14/08 na vitrine:
  1. o pedido nunca exibia "resultado disponível" — o momento que a demo existe
     para mostrar (o cidadão tem o resultado em mãos);
  2. `POST /encerrar` exige `resultado_disponivel` → **422 circular**;
  3. `pedido_encerrado` nunca era emitido e os itens nunca chegavam a `encerrado`,
     porque só o `/encerrar` os promove.

`encerrado` passa a significar o que sempre disse significar: ciência registrada.

Esta suíte é de domínio puro (sem banco) — a máquina de estados é o contrato, e
contrato se testa direto. O ciclo HTTP correspondente está em
`tests/integration/test_pedidos_exame_encerramento.py`.
"""
from __future__ import annotations

import pytest

from app.domain.states_exame import (
    ESTADOS_PEDIDO_EXAME,
    _PRIORIDADE_ESTADO,
    derivar_status_pedido,
)


# ---------------------------------------------------------------------------
# O AC do J.1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("itens", [
    ["resultado_disponivel"],
    ["resultado_disponivel", "resultado_disponivel"],
    ["resultado_disponivel"] * 5,
])
def test_todos_com_resultado_repousa_em_resultado_disponivel(itens):
    """AC — N itens com resultado deixam o PEDIDO em `resultado_disponivel`,
    não em `encerrado`. É o que destrava o `/encerrar`."""
    assert derivar_status_pedido(itens) == "resultado_disponivel"


def test_encerrado_so_quando_todos_os_itens_encerrados():
    """`encerrado` é consequência da CIÊNCIA (via /encerrar, que promove os itens),
    nunca de o laboratório ter terminado."""
    assert derivar_status_pedido(["encerrado"]) == "encerrado"
    assert derivar_status_pedido(["encerrado", "encerrado"]) == "encerrado"


def test_resultado_pendente_tem_precedencia_sobre_item_ja_encerrado():
    """Item já com ciência + item aguardando ciência → o pedido ainda aguarda.
    Enquanto houver resultado sem ciência, o ciclo não fechou."""
    assert derivar_status_pedido(["encerrado", "resultado_disponivel"]) == "resultado_disponivel"
    assert derivar_status_pedido(["resultado_disponivel", "cancelado"]) == "resultado_disponivel"


# ---------------------------------------------------------------------------
# O que NÃO pode ter mudado
# ---------------------------------------------------------------------------

def test_cancelamento_preservado():
    assert derivar_status_pedido(["cancelado"]) == "cancelado"
    assert derivar_status_pedido(["cancelado", "cancelado"]) == "cancelado"
    # Encerrado + cancelado (sem resultado pendente) segue 'cancelado', como antes.
    assert derivar_status_pedido(["encerrado", "cancelado"]) == "cancelado"


def test_fluxo_fisico_preservado():
    assert derivar_status_pedido(["encerrado_fisico"]) == "encerrado"


@pytest.mark.parametrize(("itens", "esperado"), [
    (["pendente"],                              "emitido"),
    (["agendado"],                              "agendado"),
    (["coletado"],                              "coletado"),
    (["em_analise"],                            "em_analise"),
    # Item não-terminal manda: o pedido acompanha o ITEM MENOS ADIANTADO ativo.
    (["resultado_disponivel", "coletado"],      "coletado"),
    (["resultado_disponivel", "em_analise"],    "em_analise"),
    (["resultado_disponivel", "agendado"],      "agendado"),
])
def test_derivacao_com_itens_ativos_inalterada(itens, esperado):
    """Enquanto houver item ativo, ele define o estado — comportamento anterior,
    preservado. `resultado_disponivel` só vence quando NÃO há trabalho pendente,
    e é isso que torna seguro tirar o pedido da fila do laboratório nesse estado."""
    assert derivar_status_pedido(itens) == esperado


def test_vazio_devolve_encerrado_comportamento_anterior():
    """Lista vazia → `encerrado`, por vacuidade do `all()`.

    Comportamento **anterior ao J.1** (verificado com `git stash`), preservado de
    propósito: mexer nele seria alargar um ticket `core` por um caso que não
    ocorre — a emissão recusa pedido sem item (`pedidos_exame.py`, 422 "O pedido
    deve conter ao menos um item"). Fica travado aqui para que, se alguém decidir
    mudar, seja decisão e não efeito colateral.
    """
    assert derivar_status_pedido([]) == "encerrado"


# ---------------------------------------------------------------------------
# Coerência do contrato
# ---------------------------------------------------------------------------

def test_todo_estado_derivavel_existe_no_contrato():
    """A derivação não pode inventar estado fora de `ESTADOS_PEDIDO_EXAME`."""
    casos = [
        [], ["pendente"], ["agendado"], ["coletado"], ["em_analise"],
        ["resultado_disponivel"], ["encerrado"], ["cancelado"],
        ["encerrado_fisico"], ["encerrado", "resultado_disponivel"],
    ]
    for itens in casos:
        assert derivar_status_pedido(itens) in ESTADOS_PEDIDO_EXAME, itens


def test_prioridade_nao_tem_estado_inalcancavel():
    """Guarda contra a reincidência: todo estado listado na prioridade tem de ser
    derivável por ALGUMA combinação de itens. `resultado_disponivel` estava lá e
    não era — foi exatamente o bug do J.1."""
    derivaveis = {
        derivar_status_pedido([e if e != "pendente" else "pendente"])
        for e in _PRIORIDADE_ESTADO
    }
    for estado in _PRIORIDADE_ESTADO:
        alvo = "emitido" if estado == "pendente" else estado
        assert alvo in derivaveis, (
            f"'{alvo}' está em _PRIORIDADE_ESTADO mas nenhuma combinação de itens "
            "o produz — estado fantasma, como o resultado_disponivel antes do J.1"
        )
