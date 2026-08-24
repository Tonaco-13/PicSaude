"""
test_frontend_abas_j8_j9.py — TICKET-J.8 / J.9 (DESPACHO-ENG-011 §6, §7, §1).

AS REGRAS QUE ESTE ARQUIVO TRAVA
--------------------------------
1. **A tela do laboratório tem as 4 abas do percurso** (Recepção · Agendamento ·
   Realização · Bancada) e a carteira do cidadão tem as 3 dela (Receita · Exames
   · Agendamentos · Encaminhamentos · Atestado) — botão, painel e ligação ARIA
   para cada uma.

2. **Nenhuma aba lê `agendado` como "está com o laboratório".** É a instrução
   explícita do §6: o J.7 pode retirar a transição para `agendado` do ato de
   transferir custódia, e a UI não pode ruir junto. A partição é por PERCURSO
   ("já foi coletado?"), então `agendado` não aparece nas listas que decidem
   aba. Guarda de regressão contra a gambiarra que o despacho proíbe.

3. **403 de posse não é 403 de sessão** (§1). Nenhum sítio da `clinica.html`
   pode mandar um 403 para `handleUnauthorized`, que alerta e desloga.

POR QUE ESTÁTICO
----------------
Mesmo molde de `test_frontend_atestado.py` e `test_frontend_acao_sem_silencio.py`:
roda em TODO PR, antes e independentemente do gate de navegador (que só roda em
PR que toca `**.html` e no nightly). O E2E prova que a tela funciona; estas
guardas provam que a REGRA continua escrita no código.

A prova de que mordem está em `TestAsGuardasMordem`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_CLINICA = _RAIZ / "clinica.html"
_CIDADAO = _RAIZ / "cidadao.html"
_PRESCRITOR = _RAIZ / "prescritor.html"


def _fonte(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 — estrutura das abas
# ---------------------------------------------------------------------------

_ABAS_LAB = ["recepcao", "agendamento", "realizacao", "bancada"]
# A carteira do cidadão trocou a BARRA DE ABAS por CARTÕES-TÍTULO (decisão do
# Fabiano, 24/08) e ganhou o submódulo LAUDOS, que antes era uma seção dentro de
# Exames. A lista cresce por decisão registrada — nunca porque alguém achou a
# guarda chata; tirar uma daqui é tirar a porta da tela sem ninguém notar.
_SUBMODULOS_CARTEIRA = ["receita", "exames", "agendamentos", "laudos",
                        "atestado", "encaminhamentos"]


@pytest.mark.parametrize("aba", _ABAS_LAB)
def test_clinica_tem_botao_e_painel_de_cada_aba(aba):
    html = _fonte(_CLINICA)
    assert f'id="aba-btn-{aba}"' in html, f"falta o botão da aba {aba}"
    assert f'id="aba-{aba}"' in html, f"falta o painel da aba {aba}"
    assert f'aria-controls="aba-{aba}"' in html, f"aba {aba} sem ligação ARIA botão→painel"
    assert f'aria-labelledby="aba-btn-{aba}"' in html, f"painel {aba} sem ligação ARIA painel→botão"


# ── a carteira: a guarda ACOMPANHA a mudança de estrutura, sem afrouxar ────
#
# Os botões deixaram de existir no HTML: são desenhados por `submodulos.js` a
# partir da declaração `_SUBMODULOS_CARTEIRA`. Uma guarda que continuasse
# procurando `id="aba-btn-*"` no arquivo ficaria vermelha por motivo errado —
# ou, pior, seria "consertada" apagando a asserção.
#
# A REGRA é a mesma e continua inteira, agora em três pedaços que juntos
# provam mais do que o original provava:
#   (a) o PAINEL existe no HTML, com o `aria-labelledby` do botão que o abre;
#   (b) a CHAVE está declarada — sem declaração não nasce cartão;
#   (c) o COMPONENTE emite os ids e o ARIA que (a) espera.
# (b) é ganho novo: pega cartão sem painel e painel sem cartão, que a versão
# antiga não pegava.

def _declaracao_submodulos(html: str) -> str:
    m = re.search(r"const _SUBMODULOS_CARTEIRA = \[(.*?)\];", html, re.S)
    assert m, "a declaração dos submódulos sumiu de cidadao.html"
    return m.group(1)


@pytest.mark.parametrize("aba", _SUBMODULOS_CARTEIRA)
def test_cidadao_tem_cartao_e_painel_de_cada_submodulo(aba):
    html = _fonte(_CIDADAO)
    assert f'id="submod-{aba}"' in html, f"falta o painel do submódulo {aba}"
    assert f'aria-labelledby="submod-btn-{aba}"' in html, (
        f"painel {aba} sem ligação ARIA painel→cartão"
    )
    assert f"chave: '{aba}'" in _declaracao_submodulos(html), (
        f"o submódulo {aba} tem painel e NÃO está declarado — cartão que não "
        "nasce deixa o painel inalcançável"
    )


def test_todo_submodulo_declarado_tem_painel():
    """O outro lado: cartão declarado sem painel leva a lugar nenhum."""
    html = _fonte(_CIDADAO)
    declarados = re.findall(r"chave: '([a-z]+)'", _declaracao_submodulos(html))
    assert declarados, "nenhum submódulo declarado"
    sem_painel = [c for c in declarados if f'id="submod-{c}"' not in html]
    assert not sem_painel, f"submódulos declarados sem painel: {sem_painel}"


def test_o_componente_compartilhado_emite_o_ARIA_que_o_painel_espera():
    """(c) — o elo entre a declaração e o painel passa pelo componente.

    Se `submodulos.js` deixar de emitir `id="submod-btn-*"`, os painéis ficam
    com `aria-labelledby` apontando para nada, e nenhuma guarda de HTML veria.
    """
    fonte = (_RAIZ / "submodulos.js").read_text(encoding="utf-8")
    for pedaco in ('id="submod-btn-', 'aria-controls="submod-', 'aria-selected=', 'role="tab"'):
        assert pedaco in fonte, f"o componente deixou de emitir {pedaco}"


# ── UM ARQUIVO, DUAS TELAS (decisão do Fabiano, 24/08) ────────────────────
#
# A consistência entre a carteira e a tela do prescritor é por CONSTRUÇÃO: as
# duas desenham com a mesma função. Estas guardas impedem o caminho de volta —
# alguém reescrever a barra à mão numa das telas "só para ajustar uma coisa" e
# recriar as duas cópias que este ticket eliminou.

@pytest.mark.parametrize("tela", [_CIDADAO, _PRESCRITOR])
def test_as_duas_telas_usam_o_componente_compartilhado(tela):
    html = _fonte(tela)
    assert 'src="submodulos.js"' in html, f"{tela.name} não carrega o componente"
    assert 'href="submodulos.css"' in html, f"{tela.name} não carrega o CSS compartilhado"
    assert "Submodulos.render(" in html, f"{tela.name} não desenha pelo componente"


@pytest.mark.parametrize("tela", [_CIDADAO, _PRESCRITOR])
def test_nenhuma_tela_reescreve_a_barra_a_mao(tela):
    """A marcação das pílulas vive NO COMPONENTE. Se voltar para o HTML de uma
    das telas, as duas cópias renascem — e divergem na primeira mudança."""
    html = _fonte(tela)
    assert 'class="submod-btn' not in html, (
        f"{tela.name} voltou a escrever pílulas à mão — a barra é do componente"
    )


@pytest.mark.parametrize("tela", [_CIDADAO, _PRESCRITOR])
def test_o_css_da_barra_nao_volta_para_a_tela(tela):
    """O CSS foi PROMOVIDO para `submodulos.css`. Redefini-lo localmente faria
    uma tela divergir da outra sem que nenhuma guarda de marcação visse."""
    html = _fonte(tela)
    assert ".submod-btn {" not in html and ".submod-nav {" not in html, (
        f"{tela.name} redefiniu o CSS da barra localmente"
    )


def test_a_barra_quebra_linha_com_seis_itens():
    """A barra do prescritor tinha 3–4 itens e cabia numa linha; a carteira tem
    SEIS. Sem `flex-wrap`, seis pílulas em tela estreita espremem até o texto
    truncar — e o `flex: 1` original não tinha piso."""
    css = (_RAIZ / "submodulos.css").read_text(encoding="utf-8")
    assert "flex-wrap: wrap" in css, "a barra não quebra linha — seis itens truncam"
    assert "flex: 1 1 " in css, "as pílulas voltaram a `flex: 1` sem piso de largura"


def test_a_clinica_comeca_com_uma_aba_ativa():
    """Sem aba ativa inicial a tela abre com tudo escondido."""
    assert _fonte(_CLINICA).count('class="aba-lab ativa"') == 1, (
        "clinica.html: deve haver exatamente UMA aba ativa na marcação inicial"
    )


def test_a_carteira_comeca_com_um_submodulo_ativo():
    """O mesmo invariante, no novo lugar: o ativo inicial agora é estado de JS
    (`_submoduloAtivo`), não classe no HTML — os cartões são desenhados."""
    html = _fonte(_CIDADAO)
    m = re.search(r"let _submoduloAtivo = '([a-z]+)'", html)
    assert m, "cidadao.html não declara o submódulo ativo inicial"
    assert m.group(1) in _SUBMODULOS_CARTEIRA, (
        f"o ativo inicial ('{m.group(1)}') não é um submódulo declarado — a "
        "carteira abriria com todos os painéis escondidos"
    )


# ---------------------------------------------------------------------------
# 1b — as duas decisões registradas da aba Agendamentos (ENG-015 §4)
# ---------------------------------------------------------------------------
# Não são detalhes de implementação: são DIVERGÊNCIAS fundamentadas que o
# arquiteto registrou contra a consulta externa. Divergência que só existe no
# documento volta na próxima refatoração; travada aqui, volta com o gate
# vermelho e a conversa acontece.


def _corpo_da_funcao(html: str, nome: str) -> str:
    """Corpo de uma função de topo da tela (indentação de 8 espaços)."""
    m = re.search(rf"function {nome}\((.*?)\)\s*\{{(.*?)\n        \}}", html, re.S)
    assert m, f"{nome} sumiu de cidadao.html"
    return m.group(2)


def _rotas_de_agendamento_buscadas(html: str) -> list[str]:
    """Rotas passadas a `apiFetch` cujo caminho fala de agendamento."""
    chamadas = re.findall(r"""apiFetch\(\s*[`'"]([^`'"]+)""", html)
    return [c for c in chamadas if "agendamento" in c]


def test_o_selo_do_cartao_mantem_data_e_hora():
    """§4, decisão do arquiteto contra a consulta externa: o selo NÃO vira um
    "ver compromisso" mudo.

    A data no cartão é informação de primeira necessidade — reduzir o selo a um
    link cobraria um clique por ela. E não há risco de divergir do que a aba
    mostra: as duas superfícies leem o MESMO `pedido.agendamento`, resolvido no
    backend por `agendamento_atual_do_pedido`.
    """
    corpo = _corpo_da_funcao(_fonte(_CIDADAO), "_seloAgendamento")
    assert "_dataHoraAgendamento(ag.data_hora)" in corpo, (
        "o selo deixou de mostrar data/hora — é a decisão do §4, não um detalhe visual"
    )


def test_a_aba_agendamentos_agrega_no_front_sem_endpoint_novo():
    """§4: "agregação no front a partir do `agendamento` que os cartões já
    carregam — sem endpoint novo".

    Um `/paciente/agendamentos` seria uma SEGUNDA fonte para "qual é o
    compromisso corrente"; uma chamada por cartão a
    `/pedidos-exame/{p}/agendamentos` seria N+1 e a mesma segunda fonte. Duas
    fontes divergem em silêncio — é a lição que o J.7 cobrou quando a posse era
    lida do status.
    """
    intrusas = _rotas_de_agendamento_buscadas(_fonte(_CIDADAO))
    assert not intrusas, (
        f"a carteira passou a buscar agendamento por rota própria: {intrusas}. "
        "O §4 manda agregar de `pedido.agendamento`, que já vem em /paciente/pedidos-exame"
    )


# ---------------------------------------------------------------------------
# 2 — a partição das abas não pode se acoplar a `agendado` (§6)
# ---------------------------------------------------------------------------

def _listas_de_particao(html: str) -> dict[str, str]:
    """Extrai o corpo das constantes que decidem em qual aba um item cai."""
    achados = {}
    for nome in ("_ETAPAS_POS_COLETA", "_ETAPAS_ENCERRADAS"):
        m = re.search(rf"const\s+{nome}\s*=\s*\[(.*?)\]", html, re.S)
        assert m, f"constante {nome} sumiu de clinica.html (o J.8 foi desfeito?)"
        achados[nome] = m.group(1)
    return achados


def test_particao_das_abas_nao_menciona_agendado():
    """§6, verbatim: "evitar acoplar UI ao estado `agendado` como sinônimo de
    'com o laboratório'".

    Se o J.7 tirar a transição para `agendado` do `transferir-laboratorio`, os
    itens chegam ao laboratório como `pendente`. Uma partição escrita em cima de
    `agendado` mandaria todos eles para lugar nenhum — a aba Realização ficaria
    vazia com trabalho a fazer. Por isso o critério é "já foi coletado?".
    """
    for nome, corpo in _listas_de_particao(_fonte(_CLINICA)).items():
        assert "agendado" not in corpo, (
            f"{nome} passou a depender de `agendado` — é o acoplamento que o §6 proíbe"
        )


def test_realizacao_e_o_complemento_da_bancada_e_nao_uma_lista_de_estados():
    """A aba Realização é definida por NEGAÇÃO (o que não foi coletado nem
    encerrado). Uma lista positiva de estados voltaria a acoplar a UI ao
    vocabulário que o J.7 pode mexer."""
    html = _fonte(_CLINICA)
    m = re.search(r"function _itensDaAbaRealizacao\(itens\)\s*\{(.*?)\n    \}", html, re.S)
    assert m, "_itensDaAbaRealizacao sumiu de clinica.html"
    corpo = m.group(1)
    assert "!_ETAPAS_POS_COLETA.includes" in corpo and "!_ETAPAS_ENCERRADAS.includes" in corpo, (
        "Realização deixou de ser o complemento de Bancada — reacoplamento a estados nominais"
    )


# ---------------------------------------------------------------------------
# 3 — 403 de posse ≠ 403 de sessão (§1)
# ---------------------------------------------------------------------------

_RE_403_PARA_UNAUTHORIZED = re.compile(
    r"status\s*===\s*403.*?handleUnauthorized", re.S
)


def _sitios_que_colapsam_403(html: str) -> list[str]:
    """Linhas que mandam um 403 direto para `handleUnauthorized` (que alerta e
    desloga). Casadas linha a linha — um `.*?` sobre o arquivo inteiro casaria
    trechos separados por milhares de caracteres."""
    return [
        f"linha {n}: {linha.strip()}"
        for n, linha in enumerate(html.splitlines(), 1)
        if _RE_403_PARA_UNAUTHORIZED.search(linha)
    ]


def test_nenhum_403_da_clinica_cai_em_handle_unauthorized():
    """403 é posse: o token vale, o objeto é que não é seu. Mandá-lo para
    `handleUnauthorized` mostra "Sessão expirada" e desloga — mentira para o
    visitante e, fora da demo, expulsão de quem estava logado."""
    ofensas = _sitios_que_colapsam_403(_fonte(_CLINICA))
    assert not ofensas, (
        "403 tratado como sessão expirada em clinica.html "
        "(use `tratarNaoAutorizado`):\n  " + "\n  ".join(ofensas)
    )


def test_o_desambiguante_existe_e_separa_os_dois_codigos():
    html = _fonte(_CLINICA)
    m = re.search(r"async function tratarNaoAutorizado\(.*?\n    \}", html, re.S)
    assert m, "tratarNaoAutorizado sumiu de clinica.html"
    corpo = m.group(0)
    assert "status === 401" in corpo, "o desambiguante não distingue mais o 401"
    assert "handleUnauthorized" in corpo, "401 deixou de renovar/encerrar a sessão"
    assert "mostrarFeedback" in corpo, "403 deixou de avisar no painel da tela"


# ---------------------------------------------------------------------------
# 4 — J.3 preservado (regressão do despacho §7)
# ---------------------------------------------------------------------------

def test_relogin_transparente_do_j3_continua_intacto():
    """§7: "Manter o poll da carteira e o re-login transparente do J.3 intactos
    (o interceptador é global — não duplicar)"."""
    cidadao = _fonte(_CIDADAO)
    assert "_pollCarteira" in cidadao, "o poll da carteira sumiu"
    clinica = _fonte(_CLINICA)
    assert "emDemoComRelogin" in clinica and "renovarSessaoDemo" in clinica, (
        "o re-login transparente do J.3 sumiu de clinica.html"
    )
    # O interceptador vive em config.js — as telas o consomem, não o reimplementam.
    assert clinica.count("function renovarSessaoDemo") == 0, (
        "renovarSessaoDemo foi reimplementado na tela; o interceptador é global (config.js)"
    )


# ---------------------------------------------------------------------------
# 5 — prova por mutação: as guardas mordem
# ---------------------------------------------------------------------------

class TestAsGuardasMordem:
    """Guarda que nunca falha quando deveria é decoração (lição do R2, §2a)."""

    def test_acoplamento_a_agendado_seria_acusado(self):
        falso = "const _ETAPAS_POS_COLETA = ['agendado', 'coletado'];\n" \
                "const _ETAPAS_ENCERRADAS = ['encerrado'];"
        corpos = _listas_de_particao(falso)
        assert "agendado" in corpos["_ETAPAS_POS_COLETA"], (
            "o extrator não enxergaria o acoplamento proibido"
        )

    def test_403_colapsado_seria_acusado(self):
        falso = "        if (resp.status === 401 || resp.status === 403) { handleUnauthorized(); return; }"
        assert _sitios_que_colapsam_403(falso), "o scanner deixou passar um 403 colapsado"

    def test_selo_mudo_seria_acusado(self):
        """O selo reduzido a um link — a proposta que o §4 recusou."""
        falso = (
            "        function _seloAgendamento(ag, proto) {\n"
            "            return `<button onclick=\"verCompromisso('${proto}')\">ver compromisso</button>`;\n"
            "        }"
        )
        assert "_dataHoraAgendamento(ag.data_hora)" not in _corpo_da_funcao(falso, "_seloAgendamento"), (
            "o extrator não enxergaria o selo emudecido"
        )

    def test_selo_com_data_nao_e_acusado(self):
        ok = (
            "        function _seloAgendamento(ag, proto) {\n"
            "            return `<strong>Agendado: ${_dataHoraAgendamento(ag.data_hora)}</strong>`;\n"
            "        }"
        )
        assert "_dataHoraAgendamento(ag.data_hora)" in _corpo_da_funcao(ok, "_seloAgendamento"), (
            "falso negativo: o selo mostra a data e a guarda não viu"
        )

    @pytest.mark.parametrize("rota", [
        "'/paciente/agendamentos'",
        "`/pedidos-exame/${proto}/agendamentos`",
    ])
    def test_rota_propria_de_agendamento_seria_acusada(self, rota):
        """Os dois modos de criar a segunda fonte: endpoint novo e N+1."""
        assert _rotas_de_agendamento_buscadas(f"const r = await apiFetch({rota});"), (
            "o scanner deixou passar uma busca de agendamento por rota própria"
        )

    def test_as_rotas_legitimas_da_carteira_nao_sao_acusadas(self):
        ok = "await apiFetch('/paciente/pedidos-exame'); await apiFetch('/paciente/laudos');"
        assert not _rotas_de_agendamento_buscadas(ok), (
            "falso positivo: a carteira busca pedidos, e o agendamento vem de carona"
        )

    def test_403_tratado_a_parte_nao_e_acusado(self):
        ok = (
            "        if (resp.status === 401) { await handleUnauthorized(); return; }\n"
            "        if (resp.status === 403) { await tratarNaoAutorizado(resp, 'fila-feedback'); return; }"
        )
        assert not _sitios_que_colapsam_403(ok), "falso positivo: 403 já está separado do 401"
