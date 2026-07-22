"""
test_frontend_acao_sem_silencio.py — TICKET-FALHA-SILENCIOSA-FRONTEND.

A REGRA QUE ESTE ARQUIVO TRAVA
------------------------------
> Toda função disparada por CLIQUE do usuário termina em feedback visível —
> sucesso ou motivo da falha. Nada de `return` mudo em caminho de ação.

POR QUE EXISTE
--------------
Três falhas silenciosas na mesma semana, todas com a mesma forma: uma guarda
defensiva CORRETA que evita o crash e esconde o problema.

  1. `<select>` de conselho (#103) — seletor vazio, sem aviso.
  2. unidade NULL — viraria "unidade" inventada (evitado por decisão).
  3. "Imprimir rascunho" — `window.open` bloqueado, `if (!win) return;`, e o
     profissional clicava sem que nada acontecesse.

A DISTINÇÃO QUE DEFINE O ESCOPO (vinculante)
--------------------------------------------
Guarda muda em código de RENDERIZAÇÃO é defensiva sadia: se o elemento não
existe, não há o que desenhar. Guarda muda em AÇÃO DO USUÁRIO é defeito: o
profissional clica em "Dispensar", nada acontece, e ele não sabe se dispensou.

Por isso o registro abaixo é uma LISTA EXPLÍCITA de funções de ação, e não uma
varredura de todos os `return`. A varredura mediu 100 `if (!x) return;` nas seis
telas e a maioria é legítima; varrer tudo transformaria o gate em ruído e
treinaria todo mundo a silenciar o teste. Aqui, acrescentar uma função de ação à
lista é uma decisão consciente de quem a escreve.

O QUE ESTE TESTE NÃO É
----------------------
Não é análise sintática de JS. É guarda de presença/ausência de texto, no mesmo
molde das guardas de `test_frontend_atestado.py` — que já provaram morder. A
prova de que ESTA morde está em `TestAGuardaMorde`, que reintroduz o defeito num
fonte sintético e exige que o gate acuse.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Registro de funções de AÇÃO — as 12 do ticket.
#
# imprimirRascunhoAtestado entra aqui porque é a origem da varredura: sem ela na
# lista, a regressão que motivou tudo isto não teria guarda. As outras 11 vieram
# do levantamento do ticket.
# ---------------------------------------------------------------------------

_ACOES: dict[str, tuple[str, ...]] = {
    "prescritor.html": (
        "async function emitirPedidoExame",
        "async function baixarPdfExame",
        "async function assinarExame",
        "async function assinarBaixarPdf",
        "async function baixarPdfAtestado",
        "async function assinarAtestado",
        "function imprimirRascunhoAtestado",
        # Item 3 (2026-07-22): emissão física do atestado (caminho A — POST → PDF do
        # servidor). Ação de clique com 6 caminhos de falha; cada um termina em
        # feedback visível (container inline), nenhum `return` mudo.
        "async function imprimirAtestadoFisico",
    ),
    "dispensador.html": (
        "async function dispensarItem",
        "async function estornarDispensacao",
        "async function baixarComprovantePdf",
    ),
    "clinica.html": (
        "async function enviarProposta",
        "async function enviarRemarcacao",
        # Encontradas na revisão deste PR: mesmo padrão (gate CNES mudo), mesmo
        # onclick, e agendamento/circulação também escrevem no ledger. Ficaram de
        # fora da contagem original de 12; entram aqui por decisão do Fabiano.
        "async function criarAgendamento",
        "async function confirmarAgendamento",
        "async function realizarAgendamento",
        "async function realizarCirculacao",
    ),
}

# Chamadas que CONTAM como feedback visível ao usuário.
#
# `innerHTML`/`textContent` entram porque várias telas escrevem a mensagem
# direto num container inline (#fila-msg, #circ-feedback, #pedido-exame-status-msg).
# `reportValidity` é feedback nativo do navegador — o balão do próprio campo.
_FEEDBACK = (
    "showToast(",
    "avisarFalha(",
    "alert(",
    "_filaMsg(",
    "_circFeedback(",
    "mostrarMsgItem(",
    "mostrarFeedback(",
    "mostrarMensagemFormulario(",
    "_avisarFalhaDeImpressao(",
    "tratarSessaoExpirada(",
    "handleUnauthorized(",
    "reportValidity(",
    "innerHTML",
    "textContent",
    "_msg(",
    "_mostrar(",
)

# Desistência que o PRÓPRIO usuário provocou não precisa de aviso: ele acabou de
# clicar em "Cancelar". Detectado pela origem do valor testado (prompt/confirm)
# na mesma linha ou logo acima — não por comentário, que envelhece sem quebrar.
_CANCELAMENTO = ("prompt(", "confirm(", "=== null", "cancelou")

# Quantas linhas antes do `return` ainda contam como "a mesma guarda".
_JANELA = 3


def _fonte(tela: str) -> str:
    return (_RAIZ / tela).read_text(encoding="utf-8")


def _sem_comentarios(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", js)


def _corpo_da_funcao(fonte: str, assinatura: str) -> str:
    """Corpo da função por contagem de chaves, a partir da assinatura.

    Mais preciso que cortar na próxima declaração: estas funções contêm
    arrow-functions internas (`_msg`, `_mostrar`) cujos returns também importam.
    """
    i = fonte.index(assinatura)
    abre = fonte.index("{", i)
    nivel, j = 0, abre
    while j < len(fonte):
        if fonte[j] == "{":
            nivel += 1
        elif fonte[j] == "}":
            nivel -= 1
            if nivel == 0:
                return fonte[i:j + 1]
        j += 1
    raise AssertionError(f"Chaves desbalanceadas em {assinatura!r}")


def _returns_mudos(corpo: str) -> list[str]:
    """Linhas com `return;` nu sem feedback na guarda — o defeito."""
    linhas = _sem_comentarios(corpo).split("\n")
    achados = []
    for n, linha in enumerate(linhas):
        if not re.search(r"\breturn\s*;", linha):
            continue
        janela = "\n".join(linhas[max(0, n - _JANELA):n + 1])
        if any(t in janela for t in _FEEDBACK):
            continue
        if any(t in janela for t in _CANCELAMENTO):
            continue
        achados.append(linha.strip())
    return achados


# ---------------------------------------------------------------------------
# A guarda
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("tela", "assinatura"),
    [(t, a) for t, acoes in _ACOES.items() for a in acoes],
    ids=lambda v: v.replace("async function ", "").replace(".html", ""),
)
def test_acao_nunca_desiste_calada(tela: str, assinatura: str) -> None:
    mudos = _returns_mudos(_corpo_da_funcao(_fonte(tela), assinatura))
    assert not mudos, (
        f"{tela}: {assinatura} desiste sem avisar o usuário.\n"
        f"Returns mudos: {mudos}\n\n"
        "Toda função de AÇÃO termina em feedback visível — sucesso ou motivo da "
        "falha. Use showToast()/avisarFalha() (config.js) ou o container inline "
        "da tela, e diga O QUE FAZER, não só que falhou."
    )


def test_registro_nao_encolhe_em_silencio() -> None:
    """O registro não pode encolher sem alguém perceber.

    Remover uma função da lista faria o gate ficar verde por omissão — o mesmo
    silêncio, um andar acima. São as 12 do ticket + 4 do mesmo padrão achadas
    na revisão daquele PR (agendamento/circulação) + 1 do item 3 de 2026-07-22
    (imprimirAtestadoFisico). Baixar este número é uma decisão, não um efeito
    colateral: mude o literal de propósito ou não mude.
    """
    total = sum(len(v) for v in _ACOES.values())
    assert total == 17, f"Registro de ações mudou de tamanho: {total} != 17"


@pytest.mark.parametrize("tela", sorted(_ACOES))
def test_acoes_declaradas_existem_na_tela(tela: str) -> None:
    """Assinatura renomeada sem atualizar o registro = guarda que não guarda."""
    fonte = _fonte(tela)
    for assinatura in _ACOES[tela]:
        assert assinatura in fonte, f"{tela}: {assinatura!r} não existe mais"


# ---------------------------------------------------------------------------
# Helper único — a régua da semana: uma mensagem, um lugar
# ---------------------------------------------------------------------------

class TestHelperUnico:
    def test_showtoast_mora_no_config_js(self) -> None:
        assert "function showToast(" in _fonte("config.js")

    def test_nenhuma_tela_redefine_showtoast(self) -> None:
        """cidadao.html tinha a sua cópia; foi promovida, não duplicada."""
        for tela in ("prescritor.html", "dispensador.html", "clinica.html",
                     "cidadao.html", "index.html", "validar.html"):
            assert "function showToast(" not in _fonte(tela), (
                f"{tela} redefine showToast — duas implementações divergem, é a "
                "lição do texto do atestado aplicada ao aviso."
            )

    def test_toda_tela_carrega_o_config(self) -> None:
        for tela in ("prescritor.html", "dispensador.html", "clinica.html",
                     "cidadao.html", "index.html", "validar.html"):
            assert '<script src="config.js">' in _fonte(tela)

    def test_toast_e_anunciado_para_leitor_de_tela(self) -> None:
        """Aviso que só existe em pixel ainda é silêncio para quem não vê."""
        config = _fonte("config.js")
        assert "aria-live" in config and "role" in config


# ---------------------------------------------------------------------------
# A guarda morde? — mutação sobre fonte sintético
# ---------------------------------------------------------------------------

class TestAGuardaMorde:
    """Guarda que não falha quando deveria é decoração.

    A mutação roda sobre um fonte sintético, e não sobre os HTMLs reais, para
    que a prova continue valendo mesmo depois de o código de produção mudar —
    e para não deixar o repositório sujo se o teste for interrompido no meio.
    O teste de mutação sobre o arquivo REAL foi executado à mão e está relatado
    no ticket.
    """

    _MUDA = """
        async function acaoQualquer() {
            const alvo = document.getElementById('x');
            if (!alvo) return;
            await fazerAlgo();
        }
    """

    _FALANTE = """
        async function acaoQualquer() {
            const alvo = document.getElementById('x');
            if (!alvo) { avisarFalha('Nada selecionado. Escolha um item.'); return; }
            await fazerAlgo();
        }
    """

    _CANCELADA = """
        async function acaoQualquer() {
            const senha = window.prompt('Senha:');
            if (senha === null) return;
            await fazerAlgo();
        }
    """

    def test_return_mudo_e_detectado(self) -> None:
        corpo = _corpo_da_funcao(self._MUDA, "async function acaoQualquer")
        assert _returns_mudos(corpo), "A guarda NÃO detectou um return mudo."

    def test_return_com_feedback_passa(self) -> None:
        corpo = _corpo_da_funcao(self._FALANTE, "async function acaoQualquer")
        assert not _returns_mudos(corpo)

    def test_cancelamento_do_usuario_nao_e_defeito(self) -> None:
        """Quem clicou em "Cancelar" já sabe o que aconteceu."""
        corpo = _corpo_da_funcao(self._CANCELADA, "async function acaoQualquer")
        assert not _returns_mudos(corpo)

    def test_comentario_nao_engana_a_guarda(self) -> None:
        """Explicar o defeito em comentário não o conserta."""
        fonte = """
        async function acaoQualquer() {
            // aqui deveria chamar avisarFalha('...') e mostrar innerHTML
            if (!alvo) return;
        }
        """
        corpo = _corpo_da_funcao(fonte, "async function acaoQualquer")
        assert _returns_mudos(corpo), "Comentário passou por feedback."
