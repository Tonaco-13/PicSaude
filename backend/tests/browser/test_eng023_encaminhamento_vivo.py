"""
tests/browser/test_eng023_encaminhamento_vivo.py — o Encaminhamento Vivo.

O DEFEITO QUE ESTE ARQUIVO FECHA
--------------------------------
O encaminhamento é o único dos quatro objetos cujo papel inteiro APONTA PARA
ALGUÉM — e esse alguém não aparecia em lugar nenhum da tela. O documento só
existia na REVISÃO (um passo antes do ponto de não-retorno) e sumia logo
depois de emitir, com o `form.reset()`, virando linha de lista. Sem alvo de
impressão: o objeto nunca teve papel.

A FORMA VEM DO GABARITO; O DOCUMENTO, NÃO
------------------------------------------
Mesma disciplina de `test_eng018` e `test_eng022`: um teste por AC, com a
sabotagem do W ≡ Y provando que a guarda morde. O que não se copia é a
anatomia — aqui as asserções perguntam pelo DESTINATÁRIO (a assinatura deste
papel), pela frase gerada e pelos itens com procedimento/motivo.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

_TIMEOUT_MS = 15_000

_ESPECIALIDADE = "CARDIOLOGIA"
_CID = "I20"
_CNS_DESTINO = "980001112223335"
_JUSTIFICATIVA = (
    "Paciente com dor toracica atipica recorrente ha 3 meses, sem alteracao "
    "ao ECG de rotina. Solicito avaliacao cardiologica."
)

_PLACEHOLDERS = (
    "digite para buscar",
    "busque por código ou descrição",
    "ex.: parecer pré-operatório",
    "000.000.000-00",
    "Procedimento (ex.:",
    "Motivo deste item",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _abrir(pg: Page, base: str) -> None:
    pg.goto(f"{base}/prescritor.html", wait_until="networkidle")
    pg.locator("#submod-btn-encaminhamento").click()
    expect(pg.locator("#submod-encaminhamento")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(pg.locator("#folha-viva-encaminhamento .enc-folha")).to_have_count(
        1, timeout=_TIMEOUT_MS
    )


def _escolher_canonicos(pg: Page, especialidade: str = _ESPECIALIDADE, cid: str = _CID) -> None:
    """Escreve nos hidden dos typeaheads pelo caminho que eles próprios usam.

    Os dois campos têm `onchange` declarado no HTML; disparar `change` é
    exatamente o que o typeahead faz ao escolher um item.
    """
    pg.evaluate(
        """([esp, cid]) => {
            const e = document.getElementById('enc-especialidade');
            e.value = esp; e.dispatchEvent(new Event('change', { bubbles: true }));
            const c = document.getElementById('enc-cid');
            c.value = cid; c.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [especialidade, cid],
    )
    pg.wait_for_timeout(250)


def _preencher(pg: Page, procedimento: str = "Consulta de avaliacao cardiologica") -> None:
    pg.select_option("#enc-finalidade", index=1)
    _escolher_canonicos(pg)
    pg.fill("#enc-cns-destino", _CNS_DESTINO)
    pg.fill("#enc-justificativa", _JUSTIFICATIVA)
    card = pg.locator("#enc-lista-itens .enc-item-card").nth(0)
    card.locator(".enc-proc").fill(procedimento)
    card.locator(".enc-motivo").fill("Estratificacao de risco cardiovascular.")
    pg.wait_for_timeout(300)


def _texto_folha(pg: Page) -> str:
    return pg.evaluate("() => Encaminhamento.textoDoDocumento('folha-viva-encaminhamento')")


def _texto_documento(pg: Page) -> str:
    return pg.evaluate("() => Encaminhamento.textoDoDocumento('print-area-encaminhamento')")


def _alvos_batem(pg: Page) -> bool:
    """W ≡ Y do ENCAMINHAMENTO, numa tacada só."""
    return pg.evaluate(
        """() => Encaminhamento.textoDoDocumento('folha-viva-encaminhamento')
                 === Encaminhamento.textoDoDocumento('print-area-encaminhamento')"""
    )


def _emitir(pg: Page) -> None:
    pg.locator("#btn-enc-revisar").click()
    expect(pg.locator("#enc-revisao")).to_be_visible(timeout=_TIMEOUT_MS)
    pg.locator("#btn-enc-confirmar").click()
    expect(pg.locator("#folha-viva-encaminhamento .enc-carimbo")).to_have_count(
        1, timeout=_TIMEOUT_MS
    )


# ===========================================================================
# AC1 — a folha se escreve a cada tecla
# ===========================================================================

def test_ac1_a_folha_se_escreve_a_cada_tecla(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)

    folha = _texto_folha(page)
    for pedaco in (
        "CARDIOLOGIA",
        "980 0011 1222 3335",
        "CID-10 I20",
        "dor toracica atipica",
        "CONSULTA DE AVALIACAO CARDIOLOGICA",
        "Estratificacao de risco cardiovascular",
        "João Demo da Silva",
    ):
        assert pedaco in folha, f"{pedaco!r} não apareceu na folha do encaminhamento"

    # — item NOVO: a delegação alcança o que ainda não existia
    page.get_by_role("button", name="+ Adicionar item").click()
    segundo = page.locator("#enc-lista-itens .enc-item-card").nth(1)
    segundo.locator(".enc-proc").fill("Ecocardiograma transtoracico")
    page.wait_for_timeout(300)
    assert "ECOCARDIOGRAMA TRANSTORACICO" in _texto_folha(page)
    expect(page.locator('#folha-viva-encaminhamento .enc-item[data-item="2"]')).to_have_count(1)

    # — item REMOVIDO: a folha encolhe junto
    segundo.get_by_role("button", name="✕ Remover").click()
    page.wait_for_timeout(300)
    assert "ECOCARDIOGRAMA TRANSTORACICO" not in _texto_folha(page)


def test_ac1_a_frase_gerada_e_o_documento_se_definindo(page: Page, app_demo):
    """A frase é o que DEFINE o papel — e o hash v2 toma conta dela."""
    _abrir(page, app_demo)
    _preencher(page)
    frase = page.locator('#folha-viva-encaminhamento [data-campo="frase"]')
    expect(frase).to_contain_text("Encaminho o(a) paciente")
    expect(frase).to_contain_text("João Demo da Silva")
    expect(frase).to_contain_text(_ESPECIALIDADE)


def test_ac1_o_destinatario_aparece_desde_o_inicio(page: Page, app_demo):
    """O bloco que faz deste papel o que ele é: para QUEM ele aponta."""
    _abrir(page, app_demo)
    caixa = page.locator("#folha-viva-encaminhamento .enc-destinatario")
    expect(caixa).to_have_count(1)
    # Vazio, já é lacuna — o lugar do destinatário existe antes de ele existir.
    expect(caixa.locator(".enc-lacuna")).not_to_have_count(0)

    _preencher(page)
    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="especialidade"]')
    ).to_have_text(_ESPECIALIDADE)


# ===========================================================================
# AC2 — lacuna legível, nenhum placeholder vazado
# ===========================================================================

def test_ac2_campo_vazio_e_lacuna_e_placeholder_nao_vaza(page: Page, app_demo):
    _abrir(page, app_demo)

    for campo in ("protocolo", "hash", "especialidade", "justificativa",
                  "itens", "emitente-unidade"):
        expect(
            page.locator(f'#folha-viva-encaminhamento [data-campo="{campo}"] .enc-lacuna')
        ).not_to_have_count(0), f"campo vazio {campo!r} deveria aparecer como lacuna"

    folha = _texto_folha(page)
    for placeholder in _PLACEHOLDERS:
        assert placeholder not in folha, (
            f"placeholder do formulário {placeholder!r} vazou para a folha"
        )

    page.fill("#enc-justificativa", _JUSTIFICATIVA)
    page.wait_for_timeout(300)
    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="justificativa"] .enc-lacuna')
    ).to_have_count(0)


def test_ac2_a_frase_usa_a_lacuna_INLINE_do_nucleo(page: Page, app_demo):
    """A lição do degenerado, estreada aqui.

    A frase corrida é o primeiro lugar dos quatro documentos onde a lacuna
    mora DENTRO de uma sentença. O modo inline já estava no contrato do núcleo
    desde o nascimento (ENG-022), pensado para o atestado — e chegou pronto
    quando o encaminhamento precisou. Em modo de bloco, a largura mínima
    rasgaria a linha no meio da frase.
    """
    _abrir(page, app_demo)
    inline = page.locator('#folha-viva-encaminhamento [data-campo="frase"] .doc-lacuna-inline')
    expect(inline).not_to_have_count(0)
    estilo = inline.first.evaluate(
        "el => ({ display: getComputedStyle(el).display, min: getComputedStyle(el).minWidth })"
    )
    assert estilo["display"] == "inline", (
        f"a lacuna da frase virou bloco ({estilo}) — ela rasga a linha assim"
    )
    assert estilo["min"] in ("0px", "auto")


# ===========================================================================
# AC3 — W ≡ Y com guarda própria do objeto
# ===========================================================================

def test_ac3_w_equivale_a_y_e_sabotar_um_alvo_reprova(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)

    assert _alvos_batem(page), (
        "a folha viva e o #print-area-encaminhamento divergiram no MESMO estado"
    )

    veredito = page.evaluate(
        """() => {
            const igual = () =>
                Encaminhamento.textoDoDocumento('folha-viva-encaminhamento')
                === Encaminhamento.textoDoDocumento('print-area-encaminhamento');
            const antes = igual();
            document.querySelector('#print-area-encaminhamento [data-bloco="destinatario"]')
                    .insertAdjacentHTML('beforeend', '<span>SABOTAGEM</span>');
            return { antes: antes, depois: igual() };
        }"""
    )
    assert veredito["antes"] is True
    assert veredito["depois"] is False, (
        "a comparação W ≡ Y do encaminhamento não detectou uma divergência "
        "plantada — a guarda está cega"
    )

    page.fill("#enc-justificativa", _JUSTIFICATIVA + " Conduta a definir.")
    page.wait_for_timeout(300)
    assert _alvos_batem(page)


def test_ac3_o_w_equiv_y_vale_no_estado_emitido(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)
    assert _alvos_batem(page)
    assert "EMITIDO · CUSTÓDIA AO CIDADÃO" in _texto_documento(page)


def test_ac3_cada_objeto_tem_o_seu_alvo(page: Page, app_demo):
    """Três documentos, três alvos — e nenhum invade o do outro."""
    _abrir(page, app_demo)
    _preencher(page)

    assert "Encaminhamento Médico" in _texto_documento(page)
    receita = page.evaluate("() => Receituario.textoDoDocumento('print-area')")
    exame = page.evaluate("() => PedidoExame.textoDoDocumento('print-area-exame')")
    assert "Encaminhamento Médico" not in receita
    assert "Encaminhamento Médico" not in exame


# ===========================================================================
# AC4 — carimbo sem render novo, e o documento emitido congela
# ===========================================================================

def test_ac4_o_carimbo_cai_na_mesma_folha(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)

    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="protocolo"] .enc-lacuna')
    ).to_have_count(1)

    page.evaluate(
        "() => { document.getElementById('folha-viva-encaminhamento')"
        ".dataset.marcaDoTeste = 'a-mesma-folha'; }"
    )
    _emitir(page)

    assert page.evaluate(
        "() => document.getElementById('folha-viva-encaminhamento').dataset.marcaDoTeste"
    ) == "a-mesma-folha", "a folha foi substituída na emissão — houve render novo"

    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="protocolo"] .enc-lacuna')
    ).to_have_count(0)
    folha = _texto_folha(page)
    assert re.search(r"Protocolo: [0-9a-f]{8}-[0-9a-f]{4}", folha), folha[:250]
    assert re.search(r"Hash SHA-256: [0-9a-f]{64}", folha), folha[:400]


def test_ac4_documento_emitido_nao_se_edita(page: Page, app_demo):
    """O `form.reset()` do fluxo era justamente o que fazia o documento sumir.
    Congelado, ele sobrevive ao reset — e a digitação posterior não o altera."""
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)

    congelada = _texto_folha(page)
    assert _ESPECIALIDADE in congelada, (
        "a folha esvaziou junto com o formulário — o estado emitido não congelou"
    )

    page.locator("#enc-aba-btn-emitir").click()
    page.fill("#enc-justificativa", "texto digitado depois de emitir")
    page.wait_for_timeout(300)
    assert _texto_folha(page) == congelada, (
        "editar o formulário alterou o documento JÁ EMITIDO (CLAUDE.md §1)"
    )
    assert _alvos_batem(page)


def test_ac4_ha_saida_do_congelamento(page: Page, app_demo):
    """Folha congelada sem gesto de saída seria beco: o AC4 proíbe que digitar
    a descongele, e sem botão não se escreveria um segundo encaminhamento sem
    recarregar. É o "Nova Prescrição" deste objeto."""
    _abrir(page, app_demo)
    _preencher(page)

    expect(page.locator("#btn-enc-novo")).to_be_hidden()
    _emitir(page)

    page.locator("#enc-aba-btn-emitir").click()
    novo = page.locator("#btn-enc-novo")
    expect(novo).to_be_visible(timeout=_TIMEOUT_MS)
    novo.click()
    page.wait_for_timeout(300)

    expect(page.locator("#folha-viva-encaminhamento .enc-carimbo")).to_have_count(0)
    expect(novo).to_be_hidden()
    folha = _texto_folha(page)
    assert _ESPECIALIDADE not in folha, "o encaminhamento anterior sobrou na folha"
    assert "dor toracica" not in folha
    assert _alvos_batem(page)


# ===========================================================================
# AC5 · AC10(A6) — a pena não é engolida; o papel tem corpo
# ===========================================================================

def test_ac5_a_pena_nao_e_engolida_e_o_papel_tem_dois_quintos(page: Page, app_demo):
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)
    _preencher(page)

    m = page.evaluate(
        """() => {
            const r = s => document.querySelector(s).getBoundingClientRect().width;
            return { palco: r('.enc-palco'), papel: r('#folha-viva-encaminhamento'),
                     pena: r('.enc-pena'),
                     busca: r('#enc-especialidade-busca'),
                     scroll: document.documentElement.scrollWidth,
                     viewport: window.innerWidth };
        }"""
    )
    fatia = m["papel"] / m["palco"]
    assert fatia >= 0.40, f"o papel ficou com {fatia:.1%} do palco (mínimo 40%)"
    assert m["pena"] >= 520, f"a pena caiu para {m['pena']:.0f}px"
    assert m["busca"] >= 280, (
        f"o typeahead de especialidade ficou com {m['busca']:.0f}px — ele "
        "precisa caber para a escolha canônica continuar possível"
    )
    assert m["scroll"] <= m["viewport"] + 2, "rolagem horizontal em 1366px"


# ===========================================================================
# AC6 — a especialidade vem do valor canônico
# ===========================================================================

def test_ac6_a_especialidade_vem_do_hidden_canonico(page: Page, app_demo):
    _abrir(page, app_demo)
    # O texto digitado na BUSCA menciona outra coisa de propósito.
    page.fill("#enc-especialidade-busca", "neurologia")
    _escolher_canonicos(page)
    page.wait_for_timeout(300)

    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="especialidade"]')
    ).to_have_text(_ESPECIALIDADE)
    assert "NEUROLOGIA" not in _texto_folha(page), (
        "a folha pegou o texto digitado na busca em vez do valor canônico"
    )


def test_ac6_o_escape_OUTRA_continua_funcionando(page: Page, app_demo):
    """O escape não pode ser vítima do canônico: quem não acha na lista ainda
    escreve — e o que escreve cai na folha."""
    _abrir(page, app_demo)
    page.evaluate(
        """() => {
            const e = document.getElementById('enc-especialidade');
            e.value = 'OUTRA'; e.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )
    expect(page.locator("#enc-especialidade-outra-wrap")).to_be_visible(timeout=_TIMEOUT_MS)
    page.fill("#enc-especialidade-texto", "hematologia pediatrica")
    page.wait_for_timeout(300)
    expect(
        page.locator('#folha-viva-encaminhamento [data-campo="especialidade"]')
    ).to_have_text("HEMATOLOGIA PEDIATRICA")


# ===========================================================================
# AC7 — M-D e A2 (com a máscara de CNS)
# ===========================================================================

def test_ac7_md_e_a2_sobrevivem_e_o_cns_ganha_mascara(page: Page, app_demo):
    _abrir(page, app_demo)

    cpf = page.locator("#enc-pac-cpf")
    expect(cpf).to_have_attribute("data-tipo", "cpf")
    assert cpf.evaluate("el => el.readOnly") is True, "lock M-D do CPF sumiu"
    assert page.locator("#enc-pac-nome").evaluate("el => el.readOnly") is True

    cns = page.locator("#enc-cns-destino")
    expect(cns).to_have_attribute("data-tipo", "cns")
    cns.fill(_CNS_DESTINO)
    page.wait_for_timeout(200)
    assert cns.input_value() == "980 0011 1222 3335", (
        f"a máscara de CNS não agrupou: {cns.input_value()!r}"
    )


def test_ac7_os_dois_cns_da_folha_usam_a_mesma_grafia(page: Page, app_demo):
    """O papel canônico escreve CNS com espaços. Duas grafias na mesma folha
    (o do emitente com pontos, o do destino com espaços) seria o documento
    contradizendo a si mesmo."""
    _abrir(page, app_demo)
    _preencher(page)
    folha = _texto_folha(page)
    assert "980 0011 1222 3334" in folha, "o CNS do emitente saiu noutra grafia"
    assert "980 0011 1222 3335" in folha
    assert "980.0011" not in folha


# ===========================================================================
# AC8 — o flutuante não cobre NENHUM dos dois gestos de emissão
# ===========================================================================

def _se_cruzam(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
    )


def test_ac8_o_flutuante_nunca_cobre_os_gestos_de_emissao(page: Page, app_demo):
    """Este é o único dos quatro objetos em que emitir acontece em DOIS tempos
    — revisar e confirmar. Foi por ele que o núcleo passou a vigiar um
    conjunto de gestos em vez de um só."""
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)

    fab = page.locator("#enc-fab")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)

    for alvo in ("#btn-enc-revisar", "#btn-enc-confirmar"):
        botao = page.locator(alvo)
        if not botao.is_visible():
            _preencher(page)
            page.locator("#btn-enc-revisar").click()
            expect(page.locator("#enc-revisao")).to_be_visible(timeout=_TIMEOUT_MS)
        botao.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        caixa_fab = fab.bounding_box() if fab.is_visible() else None
        caixa_alvo = botao.bounding_box()
        assert caixa_alvo is not None
        if caixa_fab is not None:
            assert not _se_cruzam(caixa_fab, caixa_alvo), (
                f"o flutuante está por cima de {alvo}"
            )


def test_ac8_o_flutuante_abre_e_fecha_a_folha(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)
    _preencher(page)

    papel = page.locator("#enc-papel")
    expect(papel).to_be_hidden()
    # Sobe até o topo: preencher deixa o botão "Revisar documento" em cena, e
    # aí o flutuante se recolhe — que é exatamente o AC8 funcionando.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    page.locator("#enc-fab").click()
    expect(papel).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#folha-viva-encaminhamento")).to_contain_text(_ESPECIALIDADE)

    page.locator("#enc-papel .doc-fechar-folha").click()
    expect(papel).to_be_hidden(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC9 — o fluxo de emissão não muda
# ===========================================================================

def test_ac9_o_fluxo_segue_revisao_confirmar_e_termina_nos_encaminhados(
    page: Page, app_demo
):
    """Revisão → confirmar → POST, e a aba Encaminhados no fim. A folha
    carimbada CONVIVE com isso: fica na aba Emitir, à espera."""
    _abrir(page, app_demo)
    _preencher(page)

    chamadas: list[str] = []
    page.on("request", lambda r: chamadas.append(f"{r.method} {r.url}")
            if "/encaminhamentos" in r.url else None)

    page.locator("#btn-enc-revisar").click()
    expect(page.locator("#enc-revisao")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#enc-doc-corpo")).to_contain_text("Encaminho o(a) paciente")

    page.locator("#btn-enc-confirmar").click()
    expect(page.locator("#enc-aba-encaminhados")).to_be_visible(timeout=_TIMEOUT_MS)

    assert any(c.startswith("POST") and c.endswith("/encaminhamentos") for c in chamadas), (
        f"o POST mudou de forma: {chamadas}"
    )
    # E a folha carimbada sobreviveu ao `form.reset()` e à troca de aba.
    assert "EMITIDO · CUSTÓDIA AO CIDADÃO" in _texto_folha(page)


def test_ac9_os_itens_do_formulario_viajam_no_payload(page: Page, app_demo):
    """O endpoint já aceitava `procedimento`/`motivo`; a tela é que mandava um
    item sintético e jogava fora o que o backend sabia guardar. Nenhum campo
    novo no contrato."""
    _abrir(page, app_demo)
    _preencher(page, procedimento="Consulta de avaliacao cardiologica")

    corpos: list[str] = []
    page.on("request", lambda r: corpos.append(r.post_data or "")
            if r.method == "POST" and r.url.endswith("/encaminhamentos") else None)

    _emitir(page)
    page.wait_for_timeout(400)

    assert corpos, "nenhum POST capturado"
    corpo = corpos[0]
    assert "Consulta de avaliacao cardiologica" in corpo, (
        f"o procedimento do formulário não viajou: {corpo[:400]}"
    )
    assert "Estratificacao de risco" in corpo, "o motivo do item não viajou"
    assert '"especialidade": "CARDIOLOGIA"' in corpo or '"especialidade":"CARDIOLOGIA"' in corpo


# ===========================================================================
# AC10 — o selo de custódia
# ===========================================================================

_SELO = "✓ EMITIDO · CUSTÓDIA AO CIDADÃO"


def test_ac10_no_rascunho_nao_ha_selo(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    expect(page.locator("#folha-viva-encaminhamento .enc-carimbo")).to_have_count(0)
    assert "EMITIDO" not in _texto_folha(page)


def test_ac10_o_selo_nasce_na_emissao_com_a_redacao_martelada(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)

    # O fluxo termina na aba Encaminhados (AC9). A folha carimbada fica na aba
    # Emitir — e `getComputedStyle` de elemento em contêiner oculto não devolve
    # a matriz da rotação. Voltamos à aba onde o papel mora.
    page.locator("#enc-aba-btn-emitir").click()
    expect(page.locator("#enc-aba-emitir")).to_be_visible(timeout=_TIMEOUT_MS)

    selo = page.locator("#folha-viva-encaminhamento .enc-carimbo")
    assert _SELO in selo.inner_text(), (
        f"o selo diz {selo.inner_text()!r}; esperado conter {_SELO!r}. "
        '"COM O CIDADÃO" ficou de fora: o selo nomeia o fato jurídico do '
        "ledger (`emissao_digital` abre a posse no cidadão), não a etiqueta "
        "da lista."
    )

    graus = selo.evaluate(
        """el => {
            const m = getComputedStyle(el).transform;
            const n = m.match(/matrix\\(([^)]+)\\)/);
            if (!n) return 0;
            const [a, b] = n[1].split(',').map(Number);
            return Math.atan2(b, a) * 180 / Math.PI;
        }"""
    )
    assert -10.5 <= graus <= -5.5, f"rotação do selo em {graus:.1f}°, esperado ~-8°"
    assert selo.evaluate("el => getComputedStyle(el).textTransform") == "none", (
        "o selo voltou a depender de `text-transform` para a caixa-alta"
    )


# ===========================================================================
# A família, agora com três
# ===========================================================================

def test_o_nucleo_e_consumido_pelos_tres_geradores(page: Page, app_demo):
    _abrir(page, app_demo)
    t = page.evaluate(
        """() => ({
            nucleo: typeof window.DocumentoNucleo,
            receita: typeof window.Receituario,
            exame: typeof window.PedidoExame,
            enc: typeof window.Encaminhamento,
            mesmosModos: window.Receituario.MODOS === window.Encaminhamento.MODOS
                         && window.PedidoExame.MODOS === window.Encaminhamento.MODOS,
            mesmaRegua: window.Receituario.textoDoDocumento
                        === window.Encaminhamento.textoDoDocumento
                        && window.PedidoExame.textoDoDocumento
                        === window.Encaminhamento.textoDoDocumento,
        })"""
    )
    assert t["nucleo"] == "object"
    assert t["receita"] == "object" and t["exame"] == "object" and t["enc"] == "object"
    assert t["mesmosModos"] is True
    assert t["mesmaRegua"] is True, (
        "três documentos com três réguas seriam três promessas diferentes com "
        "o mesmo nome"
    )


def test_os_tres_documentos_convivem_sem_se_misturar(page: Page, app_demo):
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
    expect(page.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)
    page.locator("#lista-medicamentos .med-nome").fill("Losartana Potassica")
    page.wait_for_timeout(250)

    page.locator("#submod-btn-exames").click()
    page.locator("#lista-exames .exame-nome").fill("Hemograma completo")
    page.wait_for_timeout(250)

    page.locator("#submod-btn-encaminhamento").click()
    expect(page.locator("#folha-viva-encaminhamento .enc-folha")).to_have_count(1, timeout=_TIMEOUT_MS)
    _preencher(page)

    receita = page.evaluate("() => Receituario.textoDoDocumento('folha-viva')")
    exame = page.evaluate("() => PedidoExame.textoDoDocumento('folha-viva-exame')")
    enc = _texto_folha(page)

    assert "LOSARTANA POTASSICA" in receita and "LOSARTANA" not in enc
    assert "HEMOGRAMA COMPLETO" in exame and "HEMOGRAMA" not in enc
    assert "CARDIOLOGIA" in enc and "CARDIOLOGIA" not in receita
