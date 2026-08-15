"""TICKET-J.7 (`core`) — custódia é posse; agenda é compromisso.

A REGRA QUE ESTE ARQUIVO TRAVA
------------------------------
Martelo do Fabiano em 15/08 (DESPACHO-ENG-011 §11a), verbatim:

  > transferir ao laboratório é um ato de posse (custódia), não de agenda;
  > itens continuam `pendente`; quem promove a `agendado` é o laboratório,
  > criando agendamento com data/hora/unidade — ou realizando direto.

Domínio puro (sem banco): a máquina de estados é o contrato, e contrato se testa
direto. O ciclo HTTP está em `tests/integration/test_transferencia_exame_cidadao.py`
e o das telas em `tests/browser/test_j7_transferir_e_posse.py`.

O QUE ESTAS GUARDAS IMPEDEM
---------------------------
1. Que alguém devolva a `transferir-laboratorio` o poder de mover estado —
   trocando de volta a custódia pelo status como resposta a "onde está?".
2. Que a coleta direta suma. O martelo tem duas metades ("criando agendamento
   — OU realizando direto"), e a segunda depende de UMA aresta; sem guarda, um
   refactor a apaga sem que nada fique vermelho.
3. Que o contrato declarado e a derivação real discordem em silêncio:
   `derivar_status_pedido` NÃO valida transição, então uma derivação sem aresta
   declarada passa despercebida até uma auditoria de ledger.
"""
from __future__ import annotations

import pytest

from app.domain.states_exame import (
    ESTADOS_ITEM_EXAME,
    ESTADOS_PEDIDO_EXAME,
    TRANSICOES_ITEM_EXAME,
    TRANSICOES_PEDIDO_EXAME,
    derivar_status_pedido,
    transicao_valida_item_exame,
    transicao_valida_pedido,
)


# ---------------------------------------------------------------------------
# 1 — a coleta direta existe (a segunda metade do martelo)
# ---------------------------------------------------------------------------

def test_item_pendente_pode_ir_direto_a_coletado():
    """"…ou realizando direto": o laboratório com o material na mão não precisa
    inventar um agendamento retroativo para registrar a coleta."""
    assert transicao_valida_item_exame("pendente", "coletado")


def test_pedido_emitido_pode_ir_direto_a_coletado():
    """Espelho no nível do pedido — é o que a derivação produz quando o único
    item vai de `pendente` a `coletado` sem escala em `agendado`."""
    assert transicao_valida_pedido("emitido", "coletado")


def test_o_caminho_com_agendamento_continua_valendo():
    """A primeira metade do martelo não foi trocada pela segunda."""
    assert transicao_valida_item_exame("pendente", "agendado")
    assert transicao_valida_item_exame("agendado", "coletado")
    assert transicao_valida_pedido("emitido", "agendado")
    assert transicao_valida_pedido("agendado", "coletado")


# ---------------------------------------------------------------------------
# 2 — transferir não move estado: `pendente` deriva `emitido`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("itens", [
    ["pendente"],
    ["pendente", "pendente"],
    ["pendente", "pendente", "pendente"],
])
def test_pedido_na_posse_do_laboratorio_repousa_em_emitido(itens):
    """Depois de transferir, TODOS os itens seguem `pendente` — e o pedido
    permanece `emitido`. É o que torna a custódia a única fonte da posse:
    `emitido` deixou de significar "está com o cidadão".
    """
    assert derivar_status_pedido(itens) == "emitido"


def test_derivacao_da_coleta_direta_bate_com_a_aresta_declarada():
    """Contrato e realidade, confrontados.

    `derivar_status_pedido` não valida transição — ela apenas calcula. Se a
    aresta `emitido → coletado` não estivesse declarada, a máquina real
    executaria um caminho que a máquina declarada nega, e ninguém veria.
    """
    derivado = derivar_status_pedido(["coletado"])
    assert derivado == "coletado"
    assert transicao_valida_pedido("emitido", derivado), (
        f"derivação produz 'emitido → {derivado}', que o contrato não declara"
    )


# ---------------------------------------------------------------------------
# 3 — nenhum estado novo (a proibição do §4.2)
# ---------------------------------------------------------------------------

def test_j7_nao_inventou_estado():
    """O §4.2 proíbe estado novo sem passar por AGENTS §7, DDL-doc e governança.

    O J.7 acrescentou ARESTAS, não vocabulário: os conjuntos abaixo são os
    mesmos de antes do ticket. Congelados por valor — se alguém acrescentar um
    estado, este teste é o primeiro a acusar, e a lista de governança tem de ser
    atualizada junto.
    """
    assert ESTADOS_PEDIDO_EXAME == frozenset({
        "emitido", "agendado", "coletado", "em_analise", "resultado_disponivel",
        "encerrado", "cancelado", "expirado", "encerrado_fisico",
    })
    assert ESTADOS_ITEM_EXAME == frozenset({
        "pendente", "agendado", "coletado", "em_analise", "resultado_disponivel",
        "encerrado", "cancelado", "nao_realizado", "encerrado_fisico",
    })


@pytest.mark.parametrize("mapa,estados", [
    (TRANSICOES_PEDIDO_EXAME, ESTADOS_PEDIDO_EXAME),
    (TRANSICOES_ITEM_EXAME, ESTADOS_ITEM_EXAME),
])
def test_toda_aresta_aponta_para_estado_que_existe(mapa, estados):
    """As arestas novas não podem apontar para fora do vocabulário."""
    for origem, destinos in mapa.items():
        assert origem in estados, f"origem '{origem}' fora do contrato"
        for destino in destinos:
            assert destino in estados, f"'{origem}' → '{destino}' aponta para fora"
