"""
PicSaúde — Contrato de Estados: Pedido de Exame
=================================================
Espelho de states.py para o domínio de pedidos de exame.

REGRA: nenhum router, model ou migration deve introduzir um novo estado
sem atualizar este arquivo, a seção 7 do CLAUDE.md e docs/ARQUITETURA_EXAMES.md.

Princípio central: o estado do PEDIDO é derivado dos estados dos ITENS.
Nunca atualizar pedidos_exame.status diretamente — sempre via função derivar_status_pedido().

TICKET-J.7 (`core`, martelo do Fabiano em 15/08 — DESPACHO-ENG-011 §4 + §11a)
----------------------------------------------------------------------------
**Custódia é posse; agenda é compromisso. São fatos distintos.**

Até aqui, `POST /pedidos-exame/{p}/transferir-laboratorio` fazia os dois de uma
vez: entregava a posse E movia os itens `pendente → agendado`, sem criar
agendamento nenhum. O resultado era um pedido `agendado` que ninguém agendou —
e a fila do laboratório não conseguia distinguir "chegou, esperando marcar" de
"já marcado para quinta às 8h".

A regra martelada:

  > transferir ao laboratório é um ato de posse (custódia), não de agenda;
  > itens continuam `pendente`; quem promove a `agendado` é o laboratório,
  > criando agendamento com data/hora/unidade — ou realizando direto.

Consequências neste arquivo (nenhum estado novo — só arestas):

  · `pendente → coletado` (item) e `emitido → coletado` (pedido) — a coleta
    direta, sem agendamento, que o martelo autoriza.
  · `agendado` volta a significar **o que o nome diz**: existe um objeto
    `agendamentos` com data/hora/unidade. Só `POST /agendamentos` leva um item
    até lá.

Quem responde "onde está o pedido?" passa a ser a CUSTÓDIA
(`pedido_exame_custodia`), não o status. Um pedido `emitido` pode estar com o
cidadão ou com o laboratório; a diferença está na cadeia de custódia, e é ela
que a fila do laboratório (`GET /dispensadores/fila-exames`) e a carteira do
cidadão (`GET /paciente/pedidos-exame`) consultam.
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Tipos literais
# ---------------------------------------------------------------------------

EstadoPedidoExame = Literal[
    "emitido",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
]

EstadoItemExame = Literal[
    "pendente",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "nao_realizado",      # reservado v2 — ver docs/ARQUITETURA_EXAMES.md
    "encerrado_fisico",
]

# ---------------------------------------------------------------------------
# Estados de Pedido  (pedidos_exame.status)
# ---------------------------------------------------------------------------

ESTADOS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "emitido",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",           # terminal
    "cancelado",           # terminal
    "expirado",            # terminal
    "encerrado_fisico",    # terminal — fluxo físico
})

ESTADOS_TERMINAIS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Pedido
# ---------------------------------------------------------------------------

# TICKET-J.7 (`core`, martelo do Fabiano em 15/08 — DESPACHO-ENG-011 §11a):
# `emitido → coletado` é aresta NOVA, e é consequência direta da regra
# martelada. Entregar a posse ao laboratório deixou de mover o pedido para
# `agendado`; ele permanece `emitido` (itens `pendente`) enquanto a custódia
# — não o status — registra quem o detém. Se o laboratório coleta direto, sem
# marcar hora ("ou realizando direto", verbatim do martelo), o pedido é
# derivado de `emitido` para `coletado` sem passar por `agendado`.
#
# Nenhum estado novo: só o caminho que a regra nova torna alcançável. Declarar
# a aresta é o que impede o contrato de mentir — `derivar_status_pedido` não
# valida transição, então sem esta linha a máquina declarada e a máquina real
# discordariam em silêncio.
TRANSICOES_PEDIDO_EXAME: dict[str, frozenset[str]] = {
    "emitido":              frozenset({"agendado", "coletado", "cancelado", "expirado"}),
    "agendado":             frozenset({"coletado", "cancelado", "expirado"}),
    "coletado":             frozenset({"em_analise", "cancelado"}),
    "em_analise":           frozenset({"resultado_disponivel", "cancelado"}),
    "resultado_disponivel": frozenset({"encerrado", "cancelado"}),
    "encerrado":            frozenset(),   # terminal
    "cancelado":            frozenset(),   # terminal
    "expirado":             frozenset(),   # terminal
    "encerrado_fisico":     frozenset(),   # terminal — fluxo físico
}

# ---------------------------------------------------------------------------
# Estados de Item  (pedido_exame_itens.status_item)
# ---------------------------------------------------------------------------

ESTADOS_ITEM_EXAME: frozenset[str] = frozenset({
    "pendente",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",  # terminal de fluxo normal
    "encerrado",             # terminal — ciência registrada
    "cancelado",             # terminal
    "nao_realizado",         # terminal — reservado v2
    "encerrado_fisico",      # terminal — fluxo físico
})

ESTADOS_TERMINAIS_ITEM_EXAME: frozenset[str] = frozenset({
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "nao_realizado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Item
# ---------------------------------------------------------------------------

# TICKET-J.7 — espelho, no nível do item, da aresta acrescentada ao pedido.
# `pendente → coletado` é a "coleta direta": o laboratório que já está com o
# material na mão não precisa inventar um agendamento retroativo para poder
# registrar a coleta. `pendente → agendado` continua sendo o caminho de quem
# MARCA hora (`POST /agendamentos`, evento `agendamento_criado`) — e segue
# sendo o ÚNICO jeito de um item chegar a `agendado` (AC §4.3(iii)).
TRANSICOES_ITEM_EXAME: dict[str, frozenset[str]] = {
    "pendente":              frozenset({"agendado", "coletado", "cancelado"}),
    "agendado":              frozenset({"coletado", "cancelado"}),
    "coletado":              frozenset({"em_analise", "cancelado"}),
    "em_analise":            frozenset({"resultado_disponivel", "cancelado"}),
    "resultado_disponivel":  frozenset({"encerrado"}),
    "encerrado":             frozenset(),   # terminal
    "cancelado":             frozenset(),   # terminal
    "nao_realizado":         frozenset(),   # terminal — reservado v2
    "encerrado_fisico":      frozenset(),   # terminal — nunca volta ao ciclo digital
}

# ---------------------------------------------------------------------------
# Vocabulário de eventos no ledger  (pedido_exame_eventos.tipo_evento)
# ---------------------------------------------------------------------------

EVENTOS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "pedido_emitido",           # emissão digital
    "pedido_impresso",          # fluxo físico — ato de impressão
    "encerrado_localmente",     # fluxo físico — status terminal (mesmo nome da prescrição)
    "pedido_agendado",          # agendamento confirmado com prestador
    "pedido_coletado",          # coleta realizada
    "pedido_em_analise",        # laboratório iniciou processamento
    "resultado_registrado",     # laudo inserido no sistema pelo prestador
    "resultado_comunicado",     # paciente/prescritor notificado
    "pedido_encerrado",         # ciência registrada
    "pedido_cancelado",         # cancelamento (qualquer fase)
    "pedido_expirado",          # validade ultrapassada
    "custodia_transferida",     # qualquer transferência de posse
    "pedido_corrigido",         # derivação por correção
    "pdf_assinado_pades",       # PDF assinado em ICP-Brasil (PAdES-B) via cofre
    # J.10-CORE (migração `d4b8c1e07f36`): normalização do ledger de custódia
    # para o modelo de posse atual. Emitido PELA MIGRAÇÃO, nunca no caminho
    # clínico — espelho do `custodia_reconciliada_data_fix` do COER-2 na
    # prescrição. Significa "linha superada pelo modelo de posse atual".
    "custodia_reconciliada_data_fix",
})

# ---------------------------------------------------------------------------
# Derivação de status do pedido a partir dos itens
# ---------------------------------------------------------------------------

# Prioridade para derivação: quanto menor o índice, mais avançado o estado
_PRIORIDADE_ESTADO = [
    "resultado_disponivel",
    "em_analise",
    "coletado",
    "agendado",
    "pendente",   # == "emitido" no nível do item
]


def derivar_status_pedido(status_itens: list[str]) -> str:
    """
    Deriva o status do pedido a partir da lista de status dos seus itens ativos.

    Itens em estado terminal (encerrado/cancelado/nao_realizado/encerrado_fisico)
    são ignorados no cálculo do estado agregado.

    Se todos os itens estiverem em estado terminal:
    - ao menos um em resultado_disponivel → "resultado_disponivel" (aguarda ciência)
    - todos encerrados/nao_realizados/físicos → "encerrado"
    - caso contrário (há cancelado) → "cancelado"

    TICKET-J.1 (`core`) — o pedido REPOUSA em `resultado_disponivel`.
    Antes, "todos os itens com resultado" caía no ramo dos terminais e devolvia
    `encerrado` direto. Três consequências, todas observadas na excursão de 14/08
    na vitrine:
      1. o estado `resultado_disponivel` do PEDIDO era inalcançável, embora
         declarado em `ESTADOS_PEDIDO_EXAME` e no `_PRIORIDADE_ESTADO` abaixo;
      2. `POST /pedidos-exame/{proto}/encerrar` exige `resultado_disponivel` e
         portanto devolvia **422 circular** — nunca dava para encerrar;
      3. como só o `/encerrar` promove itens a `encerrado` e emite
         `pedido_encerrado`, esse evento **nunca existia** no ledger e os itens
         nunca chegavam ao terminal de verdade.

    `encerrado` passa a ser exclusivamente resultado do ato de ciência
    (`/encerrar`) — que é o que o estado significa. Derivar "encerrado" de
    "o laboratório terminou" confundia *produzir o resultado* com *o cidadão
    tomar ciência dele*: são dois fatos, e o segundo é o que fecha o ciclo.
    """
    ativos_sem_resultado = [s for s in status_itens if s not in ESTADOS_TERMINAIS_ITEM_EXAME]

    if not ativos_sem_resultado:
        # Todos terminais. O resultado pendente de ciência tem precedência: é o
        # único caso em que ainda há ato a praticar sobre o pedido.
        if "resultado_disponivel" in status_itens:
            return "resultado_disponivel"
        if all(s in {"encerrado", "nao_realizado", "encerrado_fisico"} for s in status_itens):
            return "encerrado"
        return "cancelado"

    for estado in _PRIORIDADE_ESTADO:
        if estado in ativos_sem_resultado:
            return estado if estado != "pendente" else "emitido"

    return "emitido"


# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

def transicao_valida_pedido(de: str, para: str) -> bool:
    return para in TRANSICOES_PEDIDO_EXAME.get(de, frozenset())


def transicao_valida_item_exame(de: str, para: str) -> bool:
    return para in TRANSICOES_ITEM_EXAME.get(de, frozenset())


def eh_terminal_pedido(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_PEDIDO_EXAME


def eh_terminal_item_exame(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ITEM_EXAME
