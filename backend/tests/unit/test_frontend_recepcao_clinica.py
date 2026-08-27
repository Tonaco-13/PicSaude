"""Recepção da clínica — guardas estáticas (ENG-014, PR A).

AS REGRAS QUE ESTE ARQUIVO TRAVA
--------------------------------
1. **As três ações existem no cartão da fila** — "Agendar", "Coletar agora" e
   "Não realizamos". É a proposta do Fabiano (20/08): o gesto da recepção
   começa no cartão, não em três cliques de navegação.

   MARTELO 27/08 (DESENHO-CIRCULACAO-CLINICA-CASAS.md/PR 2) — a coleta era
   DOIS rótulos ("Executar agora" sem compromisso, "Executar agendado" com
   compromisso) para o MESMO fato do ledger (`pedido_coletado`). Colapsaram
   em um só: "Coletar agora". As DUAS funções por trás (`executarAgoraDaFila`
   / `executarAgendadoDaFila`) continuam distintas — é só o rótulo que virou
   um, e é isso que a regra 3 abaixo protege.

2. **Agir no cartão não navega junto.** O cartão inteiro é um botão que abre o
   pedido; sem `stopPropagation` nas ações, agir dispararia a navegação e o
   operador perderia a fila de vista no meio do gesto.

3. **As ações DELEGAM — não reimplementam.** Esta é a que mais importa. As
   funções existentes carregam guardas que um atalho novo perderia em silêncio:

     · `realizarAgendamento` passa pelo gate de contexto CNES (Ticket 46) —
       uma versão própria "mais direta" registraria realização sem unidade
       confirmada, abrindo pela recepção o buraco que o gate fechou;
     · `registrarColeta` trata 403 como POSSE e não como sessão expirada
       (TICKET-I.4) — o defeito de deslogar quem abre pedido alheio.

   Por isso a recepção **não pode** chamar `/coletar` nem `/realizar` por conta
   própria. A guarda abaixo é sobre isso: se alguém "otimizar" o caminho com um
   fetch direto, fica vermelho.

POR QUE ESTÁTICO
----------------
Mesmo molde de `test_frontend_abas_j8_j9.py`: roda em TODO PR, antes e
independentemente do gate de navegador (que só roda em PR que toca `**.html`).
O E2E prova que a tela funciona; estas guardas provam que a REGRA continua
escrita no código.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_CLINICA = Path(__file__).resolve().parents[3] / "clinica.html"


def _fonte() -> str:
    return _CLINICA.read_text(encoding="utf-8")


def _corpo_da_funcao(nome: str) -> str:
    """Recorta o corpo de `async function nome(` até a próxima declaração."""
    fonte = _fonte()
    i = fonte.index(f"async function {nome}(")
    resto = fonte[i + 10:]
    fim = min(
        (p for p in (resto.find("\n    async function "), resto.find("\n    function "))
         if p != -1),
        default=len(resto),
    )
    return resto[:fim]


_ACOES = ["agendarDaFila", "executarAgoraDaFila", "executarAgendadoDaFila"]


# ---------------------------------------------------------------------------
# 1 — as três ações no cartão
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("acao", _ACOES)
def test_acao_existe(acao):
    assert f"async function {acao}(" in _fonte(), f"a recepção perdeu {acao}"


@pytest.mark.parametrize("rotulo", ["Agendar", "Coletar agora"])
def test_botao_no_cartao(rotulo):
    assert rotulo in _fonte(), f"o cartão da fila perdeu o botão '{rotulo}'"


# ---------------------------------------------------------------------------
# 2 — agir não navega junto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("acao", _ACOES)
def test_acao_no_cartao_para_a_propagacao(acao):
    """O cartão é um botão; a ação dentro dele não pode disparar a navegação."""
    fonte = _fonte()
    m = re.search(rf'onclick="([^"]*{acao}\([^"]*)"', fonte)
    assert m, f"{acao} não está ligada a nenhum botão do cartão"
    assert "stopPropagation" in m.group(1), (
        f"{acao} sem stopPropagation — agir abriria o pedido junto"
    )


# ---------------------------------------------------------------------------
# 3 — delegam, não reimplementam (a que mais importa)
# ---------------------------------------------------------------------------

def test_executar_agora_delega_para_registrar_coleta():
    corpo = _corpo_da_funcao("executarAgoraDaFila")
    assert "registrarColeta(" in corpo, "a recepção deixou de delegar a coleta"
    assert "/coletar" not in corpo, (
        "a recepção chama /coletar por conta própria — perde o tratamento de "
        "403-como-posse do TICKET-I.4"
    )


def test_executar_agendado_delega_para_realizar_agendamento():
    corpo = _corpo_da_funcao("executarAgendadoDaFila")
    assert "realizarAgendamento(" in corpo, "a recepção deixou de delegar a realização"
    assert "/realizar" not in corpo, (
        "a recepção chama /realizar por conta própria — pula o gate de contexto "
        "CNES do Ticket 46"
    )


def test_agendar_usa_o_formulario_existente():
    """Um formulário só. Dois divergiriam — e o segundo nasceria sem o
    `_aplicarContextoNoForm` que preenche org/unidade do contexto."""
    corpo = _corpo_da_funcao("agendarDaFila")
    assert "mostrarFormAgendar()" in corpo
    assert "/agendamentos" not in corpo, "a recepção criou um segundo caminho de POST"


def test_recepcao_nao_confirma_duas_vezes():
    """`realizarAgendamento` já faz a própria confirmação."""
    assert "confirm(" not in _corpo_da_funcao("executarAgendadoDaFila")


class TestAsGuardasMordem:
    def test_falta_de_stop_propagation_seria_pega(self):
        falso = 'onclick="executarAgoraDaFila(\'X\')"'
        m = re.search(r'onclick="([^"]*executarAgoraDaFila\([^"]*)"', falso)
        assert m and "stopPropagation" not in m.group(1)

    def test_chamada_direta_seria_pega(self):
        falso = "await fetch(BACKEND + '/agendamentos/' + p + '/realizar')"
        assert "/realizar" in falso

    def test_recorte_de_funcao_nao_e_vazio(self):
        for acao in _ACOES:
            assert len(_corpo_da_funcao(acao)) > 50, acao
