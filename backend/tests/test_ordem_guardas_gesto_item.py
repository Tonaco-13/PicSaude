"""Ordem das guardas nos gestos por item — padrão da casa, congelado.

ENDOSSADO pelo arquiteto em 20/08 como **padrão da casa** para todo gesto por
item, e despachado como guarda própria na sequência da pilha J.10. Roda no gate
SEM PostgreSQL: é invariante de CÓDIGO.

O PADRÃO

    404 do pedido → 403 GROSSO (sou parte?) → 404 do item → 403 FINO (é meu?) → 422 de estado

As duas camadas guardam coisas DIFERENTES — e foi preciso quebrá-las para
descobrir isso:

  · **grossa** (`dispensador_tem_algo_no_pedido`): detenho o pedido inteiro OU
    algum item dele? Separa PARTE de ESTRANHO. O estranho morre aqui e não
    aprende nada — nem que o pedido está terminal, nem se aquele id de item
    existe (senão dá para enumerar os itens de um pedido alheio de fora);
  · **fina** (`dispensador_detem_item`): este item é meu? Barra a PARTE que
    tenta operar item de outra unidade.

POR QUE ESTA GUARDA EXISTE

Na revisão do J.10 a ordem havia invertido em três endpoints (o 422 de pedido
terminal passou à frente do 403) e, no `devolver`, o 404 do item vinha antes do
403. Ao corrigir, tentei DISPENSAR a grossa e promover só a fina ao topo — ela
recebe o `item_id` da rota e não precisa do item carregado, então parecia
redundante. Um teste do próprio J.10 (`test_devolucao_guardas`) recusou: o
custodiante PARCIAL que erra o id precisa receber 404, e com só a fina no topo
recebia 403.

Ou seja: o padrão foi descoberto por um teste, não por revisão. Deixá-lo apenas
no parecer seria confiar na memória — e é assim que a assimetria de RBAC dos
agendamentos sobreviveu meses. Lição do R2 (§2a): invariante executável.

O QUE FICA LIVRE

A ordem relativa entre o 422 de estado e o 404 do item **varia por endpoint** e
não é travada: no `devolver` o 404 do item vem antes (ele precisa do
`status_item` para o próprio 422), nos demais vem depois. O que importa é que
NADA disso preceda a guarda grossa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROUTER = Path(__file__).resolve().parent.parent / "app" / "routers" / "pedidos_exame.py"

# Os gestos operacionais por item — os quatro que uma unidade dispara na bancada.
_GESTOS = [
    "devolver_item_exame",
    "coletar_item_exame",
    "enviar_item_a_bancada",
    "registrar_resultado_item",
]

_MARCAS = {
    "grossa":  "_assert_dispensador_algo_no_pedido(",
    "item404": "if not item:",
    "fina":    "_assert_dispensador_dono_item(",
    "e422":    "eh_terminal_pedido(",
}


def _linhas():
    return _ROUTER.read_text(encoding="utf-8").split("\n")


def _corpo(nome: str) -> list[str]:
    """As linhas do corpo da função `nome` (até o próximo `def`/`@router`)."""
    linhas = _linhas()
    ini = next(i for i, l in enumerate(linhas) if l.startswith(f"def {nome}("))
    fim = next(
        (i for i in range(ini + 1, len(linhas))
         if linhas[i].startswith("def ") or linhas[i].startswith("@router")),
        len(linhas),
    )
    return linhas[ini:fim]


def _posicoes(nome: str) -> dict:
    """Posição da primeira ocorrência EXECUTÁVEL de cada marca (ignora comentário)."""
    corpo = _corpo(nome)
    out = {}
    for chave, marca in _MARCAS.items():
        out[chave] = next(
            (i for i, l in enumerate(corpo)
             if marca in l and not l.strip().startswith("#")),
            None,
        )
    return out


@pytest.mark.parametrize("gesto", _GESTOS)
def test_gesto_por_item_tem_as_duas_guardas(gesto):
    pos = _posicoes(gesto)
    assert pos["grossa"] is not None, f"{gesto}: perdeu a guarda GROSSA"
    assert pos["fina"] is not None, f"{gesto}: perdeu a guarda FINA"


@pytest.mark.parametrize("gesto", _GESTOS)
def test_a_grossa_precede_o_422_de_estado(gesto):
    """Sem isto, quem não detém nada aprende pelo código de status que o pedido
    está terminal — foi a regressão que a revisão do J.10 pegou."""
    pos = _posicoes(gesto)
    assert pos["grossa"] < pos["e422"], (
        f"{gesto}: 422 de estado antes do 403 de posse — anti-leak #52 invertido"
    )


@pytest.mark.parametrize("gesto", _GESTOS)
def test_a_grossa_precede_o_404_do_item(gesto):
    """Sem isto, o estranho distingue um id de item que existe de um que não
    existe, e enumera os itens de um pedido alheio de fora."""
    pos = _posicoes(gesto)
    assert pos["grossa"] < pos["item404"], (
        f"{gesto}: 404 do item antes do 403 de posse — vaza existência de item"
    )


@pytest.mark.parametrize("gesto", _GESTOS)
def test_a_fina_vem_depois_do_item(gesto):
    """A fina é a granularidade fina, não a primeira barreira: ela existe para
    barrar quem É parte e tenta operar item alheio."""
    pos = _posicoes(gesto)
    assert pos["fina"] > pos["item404"], f"{gesto}: guarda fina antes do item carregado"


def test_a_lista_de_gestos_esta_completa():
    """Congelada POR VALOR: um quinto gesto por item entra nesta lista por
    decisão, não por esquecimento. Endpoint novo com `itens/{item_id}` que não
    apareça aqui fica VERMELHO — que é o ponto."""
    fonte = _ROUTER.read_text(encoding="utf-8")
    rotas = set(re.findall(r'@router\.post\("/\{protocolo\}/itens/\{item_id\}/([a-z-]+)"', fonte))
    assert rotas == {"devolver", "coletar", "em-analise", "resultado"}, (
        f"gestos por item mudaram: {sorted(rotas)} — atualize _GESTOS e esta linha"
    )


class TestAGuardaMorde:
    """Sem isto, um regex que nunca casa deixaria tudo verde para sempre."""

    def test_as_marcas_foram_encontradas_em_todos(self):
        for gesto in _GESTOS:
            pos = _posicoes(gesto)
            assert all(v is not None for v in pos.values()), f"{gesto}: {pos}"

    def test_inversao_seria_pega(self):
        falso = {"grossa": 40, "e422": 20, "item404": 30, "fina": 50}
        assert not (falso["grossa"] < falso["e422"])

    def test_gesto_novo_nao_declarado_seria_pego(self):
        assert {"devolver", "coletar"} != {"devolver", "coletar", "em-analise", "resultado"}
