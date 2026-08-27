"""
test_frontend_recepcao_decisoes.py — ENG-015, PR 2 (§2 e §3 do desenho).

AS REGRAS QUE ESTE ARQUIVO TRAVA
--------------------------------
1. **"Coletar agora" é a COLETA DIRETA do J.7 — um fato.** (Rótulo unificado
   no MARTELO 27/08, PR 2 do desenho de circulação — antes "Executar agora" só
   na Recepção; hoje o mesmo texto em toda casa que coleta.) É a *guarda de
   rumo* que o arquiteto declarou por escrito: a consulta externa propôs
   "agendamento instantâneo" (criar + confirmar + realizar) para o gesto, e
   foi **rejeitada com evidência** — inventaria três fatos para um ato que não
   teve compromisso, ressuscitando o `pedido_agendado` fantasma que o martelo
   do J.7 matou. Nenhum caminho de coleta desta tela pode criar agendamento.

2. **As três decisões vivem na Recepção, e "Não realizamos" saiu da
   Realização** (§2, demanda do Fabiano). Recusar não é etapa de execução: quem
   recusa não vai coletar.

3. **O ato composto são dois fatos, na ordem certa** (§2): cancela e SÓ ENTÃO
   devolve — `devolver` exige item `pendente`, e é o cancelamento que o devolve
   a `pendente`.

POR QUE ESTÁTICO
----------------
Mesmo molde de `test_frontend_abas_j8_j9.py`: roda em TODO PR, antes e
independentemente do gate de navegador (que só roda em PR que toca `**.html` e
no nightly). O E2E (`tests/browser/test_recepcao_tres_decisoes.py`) prova que a
tela funciona; estas guardas provam que a DECISÃO continua escrita no código —
e a nº 1 é uma rejeição registrada, o tipo de coisa que volta em silêncio na
refatoração seguinte de quem não estava na conversa.

A prova de que mordem está em `TestAsGuardasMordem`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_CLINICA = _RAIZ / "clinica.html"


def _fonte() -> str:
    return _CLINICA.read_text(encoding="utf-8")


def _corpo_da_funcao(html: str, nome: str) -> str:
    """Corpo de uma função de topo da `clinica.html` (indentação de 4)."""
    m = re.search(rf"function {nome}\(.*?\)\s*\{{(.*?)\n    \}}", html, re.S)
    assert m, f"{nome} sumiu de clinica.html"
    return m.group(1)


def _sem_comentarios(corpo: str) -> str:
    """Tira as linhas de comentário.

    Sem isto a guarda acusaria a própria EXPLICAÇÃO: os comentários destes
    caminhos citam `/agendamentos` justamente para dizer que não se chama.
    Guarda que morde o texto que a justifica é ruído — a lição do #181.
    """
    return "\n".join(
        l for l in corpo.splitlines() if not l.strip().startswith("//")
    )


# ---------------------------------------------------------------------------
# 1 — a guarda de RUMO: coleta direta é um fato, não três
# ---------------------------------------------------------------------------

_CAMINHOS_DE_COLETA = ["registrarColeta", "executarAgoraDaFila"]


@pytest.mark.parametrize("funcao", _CAMINHOS_DE_COLETA)
def test_coleta_direta_nao_cria_agendamento(funcao):
    """A rejeição do "agendamento instantâneo", executável.

    Coletar direto é `POST /pedidos-exame/{p}/itens/{id}/coletar` — a aresta
    `pendente → coletado` que o J.7 abriu. Se um destes caminhos passar a falar
    com `/agendamentos`, o ato ganhou fatos que não aconteceram.
    """
    corpo = _sem_comentarios(_corpo_da_funcao(_fonte(), funcao))
    assert "/agendamentos" not in corpo, (
        f"{funcao} passou a criar/mover agendamento para coletar — é o "
        "'agendamento instantâneo' REJEITADO pelo arquiteto (§2 do desenho)"
    )


def test_a_coleta_direta_chama_o_endpoint_de_coleta():
    """O complemento da guarda acima: provar que o caminho certo continua lá.

    Sem isto, apagar a chamada inteira passaria — "não chama /agendamentos" é
    verdade também para uma função vazia.
    """
    corpo = _sem_comentarios(_corpo_da_funcao(_fonte(), "registrarColeta"))
    assert "/coletar" in corpo, "registrarColeta deixou de chamar `/coletar`"


# ---------------------------------------------------------------------------
# 2 — as três decisões, e a Realização com um gesto só (§2)
# ---------------------------------------------------------------------------

def _ramos_de_acao(html: str) -> dict[str, str]:
    """Separa o ramo da Recepção do ramo da Realização em `_pintarItens`."""
    corpo = _corpo_da_funcao(html, "_pintarItens")
    m = re.search(
        r"if \(contexto === 'recepcao'\) \{(.*?)\n        \} else if \(item\.status_item === 'pendente'"
        r".*?\{(.*?)\n        \} else if \(item\.status_item === 'coletado'",
        corpo, re.S,
    )
    assert m, "os ramos de ação de `_pintarItens` mudaram de forma"
    return {"recepcao": m.group(1), "realizacao": m.group(2)}


@pytest.mark.parametrize("gesto", [
    "agendarItemDaRecepcao",   # Agendar
    "registrarColeta",         # Coletar agora
    "devolverItemExame",       # Não realizamos
])
def test_a_recepcao_tem_as_tres_decisoes(gesto):
    assert gesto in _ramos_de_acao(_fonte())["recepcao"], (
        f"a decisão `{gesto}` sumiu da Recepção — o §2 pede as TRÊS num só lugar"
    )


def test_a_realizacao_nao_recusa_mais():
    """§2, demanda do Fabiano: "Não realizamos" SAI da Realização."""
    assert "devolverItemExame" not in _ramos_de_acao(_fonte())["realizacao"], (
        "a recusa voltou para a Realização — recusar é triagem, não execução"
    )


# ---------------------------------------------------------------------------
# 3 — o ato composto: dois fatos, nesta ordem (§2)
# ---------------------------------------------------------------------------

def test_o_ato_composto_cancela_antes_de_devolver():
    """A ordem não é estilo: `devolver` exige item `pendente`, e é o
    cancelamento que o devolve a `pendente`. Invertida, a segunda metade
    falharia sempre — e o item ficaria preso."""
    corpo = _sem_comentarios(_corpo_da_funcao(_fonte(), "naoRealizamosDaFila"))
    i_cancelar = corpo.find("_cancelarAgendamentoComMotivo")
    i_devolver = corpo.find("_devolverItem(")
    assert i_cancelar != -1 and i_devolver != -1, (
        "o ato composto perdeu uma das metades"
    )
    assert i_cancelar < i_devolver, (
        "devolver antes de cancelar: a devolução vai bater em item `agendado` e falhar"
    )


def test_a_recusa_declara_motivo():
    """§2: "`motivo` explícito sempre (capacidade ≠ desistência ≠ erro clínico)".

    A REGRA é "recusa muda é proibida". O `prompt()` era o ACIDENTE — e o
    ENG-019 PR 6 o trocou pelo modal `#modal-fato`, que ao contrário do diálogo
    nativo valida conteúdo. A guarda acompanha o mecanismo e continua exigindo
    as duas metades: pedir o motivo, e NÃO seguir sem ele. Sem a segunda, a
    tela poderia perguntar e ignorar a resposta — recusa muda com formulário.
    """
    corpo = _corpo_da_funcao(_fonte(), "naoRealizamosDaFila")
    assert "pedirTexto(" in corpo and "motivo" in corpo, (
        "a recusa deixou de pedir o motivo — cancelamento mudo é o que o §2 proíbe"
    )
    assert "if (!motivo) return;" in corpo, (
        "a recusa pede o motivo mas segue sem ele — o §2 exige o motivo, não a pergunta"
    )


# ---------------------------------------------------------------------------
# 4 — a trava da falta é de UX, e existe (§3)
# ---------------------------------------------------------------------------

def test_registrar_falta_tem_trava_de_horario():
    html = _fonte()
    assert "_faltaJaPodeSerRegistrada" in html, "a trava de horário da falta sumiu"
    assert re.search(r"faltaLiberada \? '' : 'disabled'", html), (
        "a trava existe mas não desabilita o botão — regra que não morde é comentário"
    )


def test_a_trava_da_falta_nao_virou_regra_de_dominio():
    """A tela não legisla sobre o domínio: o `POST /nao-compareceu` continua
    aceitando sempre. Se a trava aparecesse no backend, seria regra nova —
    e regra nova de estado é decisão `core`, não ajuste de tela."""
    backend = (_RAIZ / "backend" / "app" / "routers" / "agendamentos.py").read_text(encoding="utf-8")
    corpo = re.search(r"def nao_compareceu\(.*?\n(?=@router|# ---)", backend, re.S)
    assert corpo, "nao_compareceu sumiu de agendamentos.py"
    assert "data_hora" not in corpo.group(0), (
        "a validação de horário migrou para o domínio — era declaradamente de UX (§3)"
    )


# ---------------------------------------------------------------------------
# As guardas mordem?
# ---------------------------------------------------------------------------

class TestAsGuardasMordem:
    """Guarda que nunca falha quando deveria é decoração (lição do R2, §2a)."""

    def test_agendamento_instantaneo_seria_acusado(self):
        falso = (
            "    function registrarColeta(itemId) {\n"
            "      await fetch(BACKEND + '/agendamentos', {method:'POST'});\n"
            "      await fetch(BACKEND + '/agendamentos/' + p + '/realizar');\n"
            "    }"
        )
        corpo = _sem_comentarios(_corpo_da_funcao(falso, "registrarColeta"))
        assert "/agendamentos" in corpo, "o extrator não veria o agendamento instantâneo"

    def test_o_comentario_que_explica_a_rejeicao_nao_e_acusado(self):
        """Falso positivo que a guarda TEM de evitar: o comentário do caminho
        cita `/agendamentos` para dizer que não se chama."""
        ok = (
            "    function registrarColeta(itemId) {\n"
            "      // NUNCA POST /agendamentos aqui — coleta direta é um fato só\n"
            "      await fetch(BACKEND + '/coletar');\n"
            "    }"
        )
        corpo = _sem_comentarios(_corpo_da_funcao(ok, "registrarColeta"))
        assert "/agendamentos" not in corpo, "a guarda acusaria a própria explicação"

    def test_ordem_invertida_do_ato_composto_seria_acusada(self):
        falso = (
            "    function naoRealizamosDaFila(p) {\n"
            "      await _devolverItem(1, 'x');\n"
            "      await _cancelarAgendamentoComMotivo(a, 'x');\n"
            "    }"
        )
        corpo = _sem_comentarios(_corpo_da_funcao(falso, "naoRealizamosDaFila"))
        assert corpo.find("_cancelarAgendamentoComMotivo") > corpo.find("_devolverItem("), (
            "o extrator não enxergaria a ordem invertida"
        )
