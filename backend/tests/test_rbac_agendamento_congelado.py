"""Guarda executável do RBAC de `agendamentos.py` — congelado POR VALOR.

MICRO-TICKET RBAC (`core`), FASE 3 do `DESPACHO-ENG-013`. Roda no gate SEM
PostgreSQL: é invariante de CÓDIGO.

POR QUE CONGELAR
----------------
A assimetria que este ticket fecha (`remarcar`/`nao-compareceu` sem
`dispensador`) não foi decisão registrada em lugar nenhum — foi um papel
esquecido em duas listas, e sobreviveu meses porque nada o vigiava. Uma tabela
de RBAC que ninguém trava volta a divergir do mesmo jeito.

Lição do R2 (§2a) e do COER-2: invariante executável, não memória de revisor.
Mudar RBAC é `core` (taxonomia §10) — aqui, mudar exige mexer nesta linha, o
que faz a mudança aparecer no diff como decisão, não como efeito colateral.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

_AGENDAMENTOS = Path(__file__).resolve().parent.parent / "app" / "routers" / "agendamentos.py"

# rota → papéis aceitos. Congelado por valor.
_RBAC_ESPERADO = {
    ("POST", "/agendamentos"):                         {"prescritor", "paciente", "admin", "dispensador"},
    ("GET",  "/agendamentos/{protocolo}"):             {"prescritor", "paciente", "admin", "dispensador"},
    # ENG-015 (PR 1) — o papel já estava aqui; o que mudou foi o OWNERSHIP, que
    # recusava o dispensador sempre. Era a última assimetria da família do #171.
    ("GET",  "/pedidos-exame/{protocolo_pedido}/agendamentos"):
                                                       {"prescritor", "paciente", "admin", "dispensador"},
    ("POST", "/agendamentos/{protocolo}/confirmar"):    {"prescritor", "admin", "dispensador"},
    ("POST", "/agendamentos/{protocolo}/realizar"):     {"prescritor", "admin", "dispensador"},
    ("POST", "/agendamentos/{protocolo}/cancelar"):     {"prescritor", "paciente", "admin", "dispensador"},
    # Os dois que este ticket mudou:
    ("POST", "/agendamentos/{protocolo}/nao-compareceu"):
                                                       {"prescritor", "admin", "dispensador"},
    ("POST", "/agendamentos/{protocolo}/remarcar"):     {"prescritor", "paciente", "admin", "dispensador"},
}

_DECORADOR = re.compile(r'@router\.(get|post)\("([^"]+)"')
_REQUIRE = re.compile(r'require_role\(([^)]*)\)')


def _rbac_do_arquivo() -> dict:
    """Lê o RBAC declarado no fonte — o que está escrito, não o que se lembra."""
    fonte = _AGENDAMENTOS.read_text(encoding="utf-8")
    achado, rota_atual = {}, None
    for linha in fonte.splitlines():
        m = _DECORADOR.search(linha)
        if m:
            rota_atual = (m.group(1).upper(), m.group(2))
            continue
        if rota_atual:
            r = _REQUIRE.search(linha)
            if r:
                papeis = set(re.findall(r'"([a-z_]+)"', r.group(1)))
                achado[rota_atual] = papeis
                rota_atual = None
    return achado


def test_rbac_de_agendamentos_congelado():
    assert _rbac_do_arquivo() == _RBAC_ESPERADO, (
        "RBAC de agendamentos mudou. Se foi de propósito, atualize esta linha — "
        "mudar RBAC é `core` (taxonomia §10) e pede martelo, não um diff silencioso."
    )


@pytest.mark.parametrize("rota", [
    "/agendamentos/{protocolo}/remarcar",
    "/agendamentos/{protocolo}/nao-compareceu",
])
def test_o_prestador_esta_nos_dois_endpoints_do_ticket(rota):
    """A regra do ticket, dita em voz alta.

    Quem MARCA (`POST /agendamentos`, que sempre aceitou `dispensador`) precisa
    poder REMARCAR; e quem PRESENCIA a falta precisa poder registrá-la. Se o
    papel sumir de um dos dois, a assimetria voltou.
    """
    assert "dispensador" in _rbac_do_arquivo()[("POST", rota)]


def test_paciente_nao_registra_a_propria_falta():
    """O ticket acrescentou UM papel; não abriu o endpoint para todos."""
    assert "paciente" not in _rbac_do_arquivo()[("POST", "/agendamentos/{protocolo}/nao-compareceu")]


class TestAGuardaMorde:
    """Sem isto, um regex que nunca casa deixaria a guarda verde para sempre."""

    def test_leitura_encontrou_todas_as_rotas(self):
        assert len(_rbac_do_arquivo()) == len(_RBAC_ESPERADO)

    def test_divergencia_seria_pega(self):
        falso = dict(_rbac_do_arquivo())
        falso[("POST", "/agendamentos/{protocolo}/remarcar")] -= {"dispensador"}
        assert falso != _RBAC_ESPERADO

def test_o_dispensador_nao_e_mais_recusado_no_ownership_do_GET():
    """ENG-015 (PR 1) — a recusa em BLOCO do papel morreu.

    O `require_role` sempre listou `dispensador` neste endpoint; quem o barrava
    era um `_assert_or_403(False, ...)` no ramo `else`, com a mensagem
    "Prestador não lista agendamentos por pedido". Enquanto isso o mesmo
    operador MARCAVA, REMARCAVA e REGISTRAVA FALTA (#171).

    Congelar o `require_role` não pegaria esse caso — a assimetria vivia no
    ownership, não na lista de papéis. Esta guarda olha onde ela morava.
    """
    fonte = _AGENDAMENTOS.read_text(encoding="utf-8")

    # O CONSTRUTO, não a menção: a docstring do endpoint cita a mensagem antiga
    # para explicar o que morreu, e uma guarda que acusasse a própria explicação
    # seria ruído — ruído no gate é como se treina a ignorá-lo.
    assert "_assert_or_403(False" not in fonte, (
        "recusa em BLOCO por papel voltou a `agendamentos.py` — o dispensador "
        "era barrado assim no GET, e é o que este ticket desfez"
    )
    assert "dispensador_tem_algo_no_pedido" in fonte, (
        "o GET deixou de escopar por POSSE — sem isso, ou recusa todo mundo ou "
        "abre para quem não é parte"
    )
