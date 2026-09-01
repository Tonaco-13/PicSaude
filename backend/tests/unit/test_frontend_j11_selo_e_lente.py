"""test_frontend_j11_selo_e_lente.py — TICKET-J.11 (Adendos §10 e §11b do ENG-011).

AS REGRAS QUE ESTE ARQUIVO TRAVA
--------------------------------
1. **A lente foi EXTRAÍDA, não copiada.** O render do cartão vive em `lente.js`
   e em nenhum outro lugar. Uma cópia no portal ou na `cidadao.html`
   passaria em qualquer E2E e só apareceria no dia em que as duas divergissem —
   é a duplicação com aparência de fonte única, que já custou caro nesta casa.

2. **O portal continua com a lente pública** (§11b: "o index mantém a lente
   pública; função inalterada"). A extração não podia mudar o que o
   visitante anônimo vê. **Flip da abertura (30/08)**: o portal (seletor de
   papéis) mudou de endereço, de `index.html` para `entrar.html` — a REGRA
   (lente pública no portal) não mudou, só o nome do arquivo onde ela mora.
   `index.html` virou a página de abertura/marketing (Kimi/arquiteto),
   deliberadamente SEM a lente real nesta PR — só uma demonstração visual
   rotulada como tal; a fiação real é PR `module` separada. **Despacho
   Entrar (31/08)**: o portal mudou de endereço DE NOVO, de `entrar.html`
   para `demo.html` — `entrar.html` virou a página "em obras" (lista de
   espera), sem seletor e sem lente.

3. **O selo não decide qual agendamento é o corrente.** Esse predicado é do
   backend (`agendamento_atual_do_pedido`). Se a tela voltar a filtrar status
   de agendamento por conta própria, repete o defeito que o J.7 corrigiu —
   derivar na tela o que só o backend sabe.

4. **"Ver rastreabilidade" não pede login.** Os `/public/*` são neutros e
   anônimos; passar token ali seria transformar auditoria pública em consulta
   autenticada.

POR QUE ESTÁTICO
----------------
Mesmo molde de `test_frontend_abas_j8_j9.py`: roda em TODO PR, antes e
independentemente do gate de navegador (que só roda em PR que toca `**.html` e
no nightly). O E2E prova que a tela funciona; estas guardas provam que a REGRA
continua escrita no código.

A prova de que mordem está em `TestAsGuardasMordem`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ    = Path(__file__).resolve().parents[3]
# Flip da abertura (30/08): o portal com a lente pública mudou de endereço,
# de `index.html` para `entrar.html` — `index.html` virou a abertura/marketing.
# Despacho Entrar (31/08): mudou de novo, de `entrar.html` para `demo.html` —
# `entrar.html` virou a página "em obras".
_PORTAL  = _RAIZ / "demo.html"
_CIDADAO = _RAIZ / "cidadao.html"
_LENTE   = _RAIZ / "lente.js"


def _fonte(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 — o componente existe e publica o contrato
# ---------------------------------------------------------------------------

def test_lente_js_existe():
    assert _LENTE.is_file(), "lente.js sumiu — o componente compartilhado é o ticket"


@pytest.mark.parametrize("membro", [
    "consultar", "cartaoHtml", "mensagemDeVazio", "injetarEstilos", "esc", "badge",
])
def test_lente_js_publica_o_contrato(membro):
    js = _fonte(_LENTE)
    assert "window.LenteAuditoria" in js, "o componente não se publica"
    assert re.search(rf"\b{membro}\s*:", js), f"LenteAuditoria.{membro} não exposto"


@pytest.mark.parametrize("pagina", [_PORTAL, _CIDADAO])
def test_paginas_carregam_o_componente(pagina):
    assert '<script src="lente.js"></script>' in _fonte(pagina), \
        f"{pagina.name} não carrega lente.js"


# ---------------------------------------------------------------------------
# 2 — extraída, não copiada
# ---------------------------------------------------------------------------

# Marcas do RENDER do cartão. Se aparecerem fora do lente.js, houve cópia.
#
# São marcas de USO, não de menção: `class="..."` só aparece em quem desenha o
# cartão. Procurar o nome da classe solto pegaria o comentário que documenta a
# própria extração — guarda que acusa a explicação da regra em vez da violação
# dela é ruído, e ruído no gate é como se treina a ignorá-lo.
_MARCAS_DO_RENDER = [
    'class="lente-linhas"',          # as quatro linhas (despacho "a foto exata", 31/08)
    'class="lente-item-row"',        # a linha de item
    "Dados clínicos: não exibidos. Visão de auditoria.",   # a linha fixa de neutralidade
]


@pytest.mark.parametrize("marca", _MARCAS_DO_RENDER)
@pytest.mark.parametrize("pagina", [_PORTAL, _CIDADAO])
def test_render_do_cartao_nao_foi_copiado_para_as_telas(pagina, marca):
    assert marca not in _fonte(pagina), (
        f"{pagina.name} tem '{marca}' — o render do cartão deve viver só em lente.js"
    )


@pytest.mark.parametrize("simbolo", ["LENTE_TIPOS", "renderPublico", "renderCirculacao"])
def test_portal_nao_guarda_mais_a_implementacao(simbolo):
    assert simbolo not in _fonte(_PORTAL), (
        f"{_PORTAL.name} ainda define '{simbolo}' — a extração ficou pela metade"
    )


def test_lista_de_tipos_consultaveis_mora_no_componente():
    js = _fonte(_LENTE)
    for path in ("prescricoes", "exames", "atestados", "laudos",
                 "encaminhamentos", "contrarreferencias"):
        assert f"'{path}'" in js, f"lente.js perdeu o tipo {path}"


# ---------------------------------------------------------------------------
# 3 — o portal continua com a lente pública (§11b)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ancora", [
    'id="lente-input"',            # a busca anônima
    'id="lente-resultado"',
    "consultarObjetoSanitario",    # a função que o botão chama
    "lente-section",               # a moldura da seção no portal
])
def test_portal_preserva_a_lente_publica(ancora):
    assert ancora in _fonte(_PORTAL), f"{_PORTAL.name} perdeu '{ancora}' — função alterada"


# ---------------------------------------------------------------------------
# 4 — o selo lê o corrente do backend; não o escolhe
# ---------------------------------------------------------------------------

def test_selo_le_o_campo_do_backend():
    """A regra: o selo desenha a partir de `pedido.agendamento` — o corrente já
    resolvido no backend por `agendamento_atual_do_pedido`.

    A guarda casava a chamada LITERAL `_seloAgendamento(pedido.agendamento)`.
    O ENG-015 §4 acrescentou um segundo argumento (o protocolo, para o selo
    linkar à aba Agendamentos) e a guarda ficou vermelha sem que a regra tivesse
    mudado — a assinatura era acidente, a FONTE do dado é a regra. Passa a casar
    o primeiro argumento e a ignorar o resto.
    """
    html = _fonte(_CIDADAO)
    assert re.search(r"_seloAgendamento\(\s*pedido\.agendamento\b", html), (
        "o cartão do exame não desenha o selo a partir de `pedido.agendamento` — "
        "se a tela passou a escolher o compromisso, é o defeito que o J.11 fechou"
    )


def test_selo_mostra_data_hora_e_onde():
    html = _fonte(_CIDADAO)
    assert "Agendado:" in html, "o selo perdeu o rótulo com a data"
    assert "ag.local_texto" in html and "ag.unidade_id" in html, \
        "o selo não mostra a unidade (AC do Adendo §10: data/hora E unidade)"


@pytest.mark.parametrize("terminal", ["realizado", "nao_compareceu"])
def test_tela_nao_reimplementa_a_escolha_do_agendamento_corrente(terminal):
    """A tela não pode filtrar estado de agendamento — isso é do backend.

    `cancelado` não entra na lista porque a palavra aparece na `cidadao.html`
    por outros motivos (status de prescrição). `realizado`/`nao_compareceu` são
    exclusivos do vocabulário de agendamento: se surgirem aqui, alguém começou
    a decidir na tela qual compromisso vale.
    """
    assert terminal not in _fonte(_CIDADAO), (
        f"cidadao.html menciona '{terminal}' — a escolha do agendamento corrente "
        "é de `agendamento_atual_do_pedido`, no backend"
    )


# ---------------------------------------------------------------------------
# 5 — "ver rastreabilidade" por cartão, sem login adicional
# ---------------------------------------------------------------------------

def test_cada_cartao_ganha_o_botao():
    html = _fonte(_CIDADAO)
    assert "function _botaoRastreabilidade" in html
    # Um por família de objeto da carteira: receita (posse + histórico),
    # exame, atestado e laudo.
    assert html.count("${_botaoRastreabilidade(") >= 5, (
        "nem todos os cartões da carteira abrem a lente"
    )


def test_rastreabilidade_usa_o_componente_compartilhado():
    html = _fonte(_CIDADAO)
    assert "LenteAuditoria.consultar(" in html
    assert "LenteAuditoria.cartaoHtml(" in html


def test_rastreabilidade_nao_manda_token():
    """AC §11b: cartão → trilha SEM login adicional.

    A chamada da carteira passa `{}` — nada de `Authorization`. Se alguém
    passar o token da sessão aqui, a lente deixa de ser a visão pública e vira
    consulta autenticada com outro nome.
    """
    html = _fonte(_CIDADAO)
    m = re.search(r"LenteAuditoria\.consultar\(([^)]*)\)", html)
    assert m, "a carteira não chama LenteAuditoria.consultar"
    assert "token" not in m.group(1), \
        f"a carteira passa token para a lente pública: consultar({m.group(1)})"


# ---------------------------------------------------------------------------
# 6 — endpoints `core` intocados (§11b: "zero backend" na lente)
# ---------------------------------------------------------------------------

def test_lente_so_fala_com_publicos_e_circulacao():
    js = _fonte(_LENTE)
    rotas = set(re.findall(r"'(/[a-z/-]+)'",js))
    assert rotas <= {"/public/", "/circulacao/"}, (
        f"lente.js fala com rota inesperada: {rotas - {'/public/', '/circulacao/'}}"
    )


# ---------------------------------------------------------------------------
# Prova de que as guardas mordem
# ---------------------------------------------------------------------------

class TestAsGuardasMordem:
    """Cada guarda acima falha quando a regra é violada — provado aqui.

    Sem isto, uma asserção mal escrita (regex que nunca casa, `in` sobre string
    vazia) passa para sempre e a guarda vira decoração.
    """

    def test_copia_do_render_seria_pega(self):
        falso = 'algum html com class="lente-linhas" dentro'
        assert 'class="lente-linhas"' in falso   # o mesmo `in` da guarda real

    def test_token_na_lente_seria_pego(self):
        falso = "LenteAuditoria.consultar(protocolo, { token: sessaoAtual.token })"
        m = re.search(r"LenteAuditoria\.consultar\(([^)]*)\)", falso)
        assert m and "token" in m.group(1)

    def test_filtro_de_estado_na_tela_seria_pego(self):
        falso = "if (ag.status !== 'realizado') { ... }"
        assert "realizado" in falso

    def test_rota_estranha_na_lente_seria_pega(self):
        falso = "await fetch(_base() + '/paciente/pedidos-exame')"
        rotas = set(re.findall(r"'(/[a-z/-]+)'",falso))
        assert not rotas <= {"/public/", "/circulacao/"}
