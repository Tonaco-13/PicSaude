"""
tests/browser/test_eng022_pedido_exame_vivo.py — o Pedido de Exame Vivo.

O DEFEITO QUE ESTE ARQUIVO FECHA
--------------------------------
Pior que o da receita. A receita, antes da onda 1, tinha um `#print-area`
preenchido tarde; o pedido de exame **não tinha documento nenhum em tela** —
nem depois de emitir. O comentário do próprio `imprimirPedidoFisico`
confessava: *"como #print-area só contém o template do RECEITUÁRIO, a
impressão do pedido saía sem documento"*.

A FORMA VEM DO GABARITO; O CONTEÚDO, NÃO
-----------------------------------------
Este arquivo copia a FORMA de `test_eng018_receita_viva.py` — um teste por AC,
nomeado pelo AC, com a sabotagem do W ≡ Y provando que a guarda morde. O que
NÃO se copia é o documento: a anatomia aqui é a do PDF oficial do pedido
(selo de prioridade, TUSS/SIGTAP, preparo, prazo de validade), e é por ela que
as asserções perguntam.

A guarda central é o **W ≡ Y do objeto** (AC3): `PedidoExame.textoDoDocumento`
nos dois alvos do exame, inclusive no estado EMITIDO. O exame tem um alvo
próprio (`#print-area-exame`) — adjudicação 1 do parecer: um alvo por objeto,
nunca um alvo multi-objeto chaveado pela aba ativa.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

_TIMEOUT_MS = 15_000

_CID = "M54.5"
_CID_DESCRICAO = "Dor lombar baixa"

# Placeholders do FORMULÁRIO do exame. Nenhum pode aparecer na folha como
# texto: lá o vocabulário é o do DOCUMENTO.
_PLACEHOLDERS = (
    "Nome do Exame *",
    "Qtd.",
    "Hipótese diagnóstica ou motivo",
    "000.000.000-00",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _abrir(pg: Page, base: str) -> None:
    pg.goto(f"{base}/prescritor.html", wait_until="networkidle")
    pg.locator("#submod-btn-exames").click()
    expect(pg.locator("#submod-exames")).to_be_visible(timeout=_TIMEOUT_MS)
    # A folha está MONTADA (não necessariamente à vista: em celular ela mora
    # atrás do flutuante).
    expect(pg.locator("#folha-viva-exame .exame-folha")).to_have_count(1, timeout=_TIMEOUT_MS)


def _card(pg: Page, n: int = 0):
    return pg.locator("#lista-exames .exame-card").nth(n)


def _normalizacao(pg: Page, n: int, tuss: str, categoria: str, preparo: str) -> None:
    """Simula o que a normalização assistida grava no card.

    Escrevemos nos hidden DEPOIS do nome de propósito: o próprio card limpa
    TUSS/SIGTAP quando o nome muda ("o nome mudou, os dois deixam de valer"),
    e essa é a ordem real — a IA responde depois da digitação.
    """
    pg.evaluate(
        """([n, tuss, categoria, preparo]) => {
            const card = document.querySelectorAll('#lista-exames .exame-card')[n];
            card.querySelector('.exame-codigo-tuss').value = tuss;
            card.querySelector('.exame-categoria').value = categoria;
            card.querySelector('.exame-preparo').value = preparo;
            card.querySelector('.exame-nome').dispatchEvent(
                new Event('change', { bubbles: true }));
        }""",
        [n, tuss, categoria, preparo],
    )
    pg.wait_for_timeout(250)


def _preencher(pg: Page, nome: str = "Hemograma completo com contagem de plaquetas") -> None:
    pg.select_option("#exam-prioridade", "urgente")
    pg.fill("#exam-indicacao", "Lombalgia persistente ha 3 meses; anemia a investigar")
    _card(pg).locator(".exame-nome").fill(nome)
    pg.wait_for_timeout(250)


def _texto_folha(pg: Page) -> str:
    return pg.evaluate("() => PedidoExame.textoDoDocumento('folha-viva-exame')")


def _texto_documento(pg: Page) -> str:
    return pg.evaluate("() => PedidoExame.textoDoDocumento('print-area-exame')")


def _alvos_batem(pg: Page) -> bool:
    """W ≡ Y do EXAME, medido numa tacada só (a lição do ENG-019/020: ler os
    dois alvos em chamadas separadas deixa um repintar legítimo cair no meio)."""
    return pg.evaluate(
        """() => PedidoExame.textoDoDocumento('folha-viva-exame')
                 === PedidoExame.textoDoDocumento('print-area-exame')"""
    )


def _emitir(pg: Page) -> None:
    pg.locator("#btn-emitir-exame").click()
    expect(pg.locator("#folha-viva-exame .exame-carimbo")).to_be_visible(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC1 — a folha se escreve a cada tecla
# ===========================================================================

def test_ac1_a_folha_se_escreve_a_cada_tecla(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    _normalizacao(page, 0, "40301079", "hematologia", "Sem preparo especial.")

    folha = _texto_folha(page)
    for pedaco in (
        "URGENTE",
        "Lombalgia persistente ha 3 meses",
        "HEMOGRAMA COMPLETO COM CONTAGEM DE PLAQUETAS",
        "TUSS 40301079",
        "hematologia",
        "Sem preparo especial.",
        "JOÃO DEMO DA SILVA",
    ):
        assert pedaco in folha, f"{pedaco!r} não apareceu na folha do pedido"

    # — card NOVO: a delegação alcança o que ainda não existia
    page.get_by_role("button", name="+ Adicionar Exame").click()
    _card(page, 1).locator(".exame-nome").fill("Radiografia de coluna lombar")
    page.wait_for_timeout(300)
    assert "RADIOGRAFIA DE COLUNA LOMBAR" in _texto_folha(page)
    expect(page.locator('#folha-viva-exame .exame-item[data-item="2"]')).to_have_count(1)

    # — card REMOVIDO: a folha encolhe junto
    _card(page, 1).get_by_role("button", name="X Remover").click()
    page.wait_for_timeout(300)
    assert "RADIOGRAFIA DE COLUNA LOMBAR" not in _texto_folha(page)
    expect(page.locator('#folha-viva-exame .exame-item[data-item="2"]')).to_have_count(0)


def test_ac1_a_prioridade_vira_selo_na_folha(page: Page, app_demo):
    """O primeiro fato que o prestador lê — e as três redações são do documento."""
    _abrir(page, app_demo)
    for valor, rotulo in (("rotina", "ROTINA"), ("urgente", "URGENTE"),
                          ("urgentissimo", "URGENTÍSSIMO")):
        page.select_option("#exam-prioridade", valor)
        page.wait_for_timeout(250)
        expect(page.locator('#folha-viva-exame [data-campo="prioridade"]')).to_have_text(rotulo)


# ===========================================================================
# AC2 — lacuna pontilhada, e nenhum placeholder vazado
# ===========================================================================

def test_ac2_campo_vazio_e_lacuna_e_placeholder_nao_vaza(page: Page, app_demo):
    _abrir(page, app_demo)

    for campo in ("protocolo", "data-emissao", "validade", "hash",
                  "indicacao", "exames", "prescritor-unidade"):
        expect(
            page.locator(f'#folha-viva-exame [data-campo="{campo}"] .exame-lacuna')
        ).not_to_have_count(0), f"campo vazio {campo!r} deveria aparecer como lacuna"

    folha = _texto_folha(page)
    for placeholder in _PLACEHOLDERS:
        assert placeholder not in folha, (
            f"placeholder do formulário {placeholder!r} vazou para a folha"
        )

    # A lacuna SOME quando a tinta cai.
    page.fill("#exam-indicacao", "Lombalgia persistente")
    page.wait_for_timeout(300)
    expect(page.locator('#folha-viva-exame [data-campo="indicacao"] .exame-lacuna')).to_have_count(0)


def test_ac2_a_lacuna_do_exame_usa_o_vocabulario_do_nucleo(page: Page, app_demo):
    """O par de classes: `doc-lacuna` traz o estilo, `exame-lacuna` é o gancho."""
    _abrir(page, app_demo)
    lac = page.locator("#folha-viva-exame .exame-lacuna").first
    expect(lac).to_have_class(re.compile(r"\bdoc-lacuna\b"))


# ===========================================================================
# AC3 — W ≡ Y com guarda PRÓPRIA do objeto (a central)
# ===========================================================================

def test_ac3_w_equivale_a_y_e_sabotar_um_alvo_reprova(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    _normalizacao(page, 0, "40301079", "hematologia", "Sem preparo especial.")

    assert _alvos_batem(page), (
        "a folha viva e o #print-area-exame divergiram no MESMO estado — o "
        "template do pedido deixou de ser único"
    )

    veredito = page.evaluate(
        """() => {
            const igual = () => PedidoExame.textoDoDocumento('folha-viva-exame')
                                === PedidoExame.textoDoDocumento('print-area-exame');
            const antes = igual();
            document.querySelector('#print-area-exame [data-bloco="paciente"]')
                    .insertAdjacentHTML('beforeend', '<span>SABOTAGEM</span>');
            return { antes: antes, depois: igual() };
        }"""
    )
    assert veredito["antes"] is True
    assert veredito["depois"] is False, (
        "a comparação W ≡ Y do exame não detectou uma divergência plantada — a "
        "guarda está cega"
    )

    page.fill("#exam-indicacao", "outra indicacao")
    page.wait_for_timeout(300)
    assert _alvos_batem(page)


def test_ac3_o_w_equiv_y_vale_tambem_no_estado_emitido(page: Page, app_demo):
    """O ticket exige explicitamente o estado EMITIDO: é nele que o selo, o
    protocolo e o hash entram — e é onde um documento derivaria em silêncio."""
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)
    assert _alvos_batem(page)
    assert "TRANSMITIDO · CUSTÓDIA AO PACIENTE" in _texto_documento(page)


def test_ac3_o_exame_tem_alvo_proprio_e_nao_invade_o_da_receita(page: Page, app_demo):
    """Adjudicação 1: um alvo por objeto. O `#print-area` singular segue da
    receita — imprimir é momento de verdade, e a chave de submódulo seria uma
    variável a mais no caminho."""
    _abrir(page, app_demo)
    _preencher(page)

    expect(page.locator("#print-area-exame")).to_have_count(1)
    # "Pedido de Exames" em caixa-mista: o TÍTULO é rótulo estático, idêntico
    # nos dois modos, e a caixa-alta dele é cromo de CSS — como no receituário.
    # A regra da casa vale para DADO (nome do fármaco, nome do exame, selo de
    # custódia), que passa pela função. Rótulo fixo não distorce o W ≡ Y porque
    # é o mesmo texto nos dois alvos.
    assert "Pedido de Exames" in _texto_documento(page)

    receita = page.evaluate("() => Receituario.textoDoDocumento('print-area')")
    assert "Receituário Médico" in receita
    assert "Pedido de Exames" not in receita, (
        "o documento do exame vazou para o alvo da receita"
    )


# ===========================================================================
# AC4 — o carimbo cai na MESMA folha, e o pedido emitido não se edita
# ===========================================================================

def test_ac4_o_carimbo_cai_na_mesma_folha_sem_navegar(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)

    expect(page.locator('#folha-viva-exame [data-campo="protocolo"] .exame-lacuna')).to_have_count(1)
    expect(page.locator('#folha-viva-exame [data-campo="hash"] .exame-lacuna')).to_have_count(1)

    page.evaluate(
        "() => { document.getElementById('folha-viva-exame').dataset.marcaDoTeste = 'a-mesma-folha'; }"
    )
    _emitir(page)

    assert page.evaluate(
        "() => document.getElementById('folha-viva-exame').dataset.marcaDoTeste"
    ) == "a-mesma-folha", "a folha foi substituída na emissão — houve render novo"

    expect(page.locator("#submod-exames")).to_be_visible()
    expect(page.locator("#folha-viva-exame")).to_be_visible()

    expect(page.locator('#folha-viva-exame [data-campo="protocolo"] .exame-lacuna')).to_have_count(0)
    expect(page.locator('#folha-viva-exame [data-campo="hash"] .exame-lacuna')).to_have_count(0)

    folha = _texto_folha(page)
    assert re.search(r"Protocolo: [0-9a-f]{8}-[0-9a-f]{4}", folha), folha[:250]
    assert re.search(r"Hash SHA-256\s*[0-9a-f]{64}", folha), folha[:400]
    assert re.search(r"Data de emissão\s*\d{2}/\d{2}/\d{4}", folha)
    assert re.search(r"Validade\s*\d{2}/\d{2}/\d{4}", folha)


def test_ac4_pedido_emitido_nao_se_edita(page: Page, app_demo):
    """§1 dentro da tela — e aqui importa MAIS que na receita: o fluxo do exame
    LIMPA o formulário logo após emitir. Sem congelar, a folha carimbada se
    esvaziaria diante de quem acabou de emitir."""
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)

    congelada = _texto_folha(page)
    assert "HEMOGRAMA COMPLETO" in congelada, (
        "a folha esvaziou junto com o formulário — o estado emitido não congelou"
    )

    page.fill("#exam-indicacao", "texto digitado depois de emitir")
    page.wait_for_timeout(300)
    assert _texto_folha(page) == congelada, (
        "editar o formulário alterou o pedido JÁ EMITIDO (CLAUDE.md §1)"
    )
    assert _alvos_batem(page)


# ===========================================================================
# AC5 · A6 — a pena não é engolida; o papel tem corpo
# ===========================================================================

def test_ac5_a_pena_nao_e_engolida_e_o_papel_tem_dois_quintos(page: Page, app_demo):
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)
    _preencher(page)

    # Injeção E medição na MESMA tacada.
    #
    # A normalização assistida é assíncrona e REESCREVE `.ia-exame-container`
    # quando responde (e também quando falha). Injetar num passo e medir no
    # seguinte deixa a resposta dela cair no meio — o teste passava isolado e
    # caía na suíte completa, conforme a latência. É a mesma lição da
    # sabotagem do W ≡ Y: o que precisa ser atômico, mede-se numa avaliação
    # síncrona, não em duas.
    m = page.evaluate(
        """() => {
            const c = document.querySelector('#lista-exames .exame-card .ia-exame-container');
            c.innerHTML = '<div class="ia-exame-bloco ia-exame-bloco-norm">'
                + '<div class="ia-exame-header">Normalização diagnóstica assistida</div>'
                + '<div class="ia-exame-chips"><span class="ia-exame-chip">TUSS 40301079</span>'
                + '<span class="ia-exame-chip">hematologia</span></div></div>';
            const r = s => document.querySelector(s).getBoundingClientRect().width;
            return {
                palco: r('.exame-palco'),
                papel: r('#folha-viva-exame'),
                pena: r('.exame-pena'),
                ia: r('#lista-exames .exame-card .ia-exame-bloco'),
                scroll: document.documentElement.scrollWidth,
                viewport: window.innerWidth,
            };
        }"""
    )

    fatia = m["papel"] / m["palco"]
    assert fatia >= 0.40, f"o papel ficou com {fatia:.1%} do palco (mínimo 40%)"
    assert m["pena"] >= 520, f"a pena caiu para {m['pena']:.0f}px"
    assert m["ia"] >= 300, f"bloco de normalização espremido ({m['ia']:.0f}px)"
    assert m["scroll"] <= m["viewport"] + 2, (
        f"rolagem horizontal em 1366px ({m['scroll']} > {m['viewport']})"
    )


# ===========================================================================
# AC6 — o selo de CID vem do hidden canônico
# ===========================================================================

def test_ac6_selo_de_cid_vem_do_hidden_canonico(page: Page, app_demo):
    _abrir(page, app_demo)
    # O texto digitado menciona OUTRO CID de propósito.
    page.fill("#exam-indicacao", "quadro compativel com M51.1, investigar")
    page.evaluate(
        """([c, d]) => _usarCid('ia-cid-exame-chips', 'exam-cid-escolhido', c, d)""",
        [_CID, _CID_DESCRICAO],
    )
    page.wait_for_timeout(300)

    selo = page.locator("#folha-viva-exame .exame-selo-cid")
    expect(selo).to_have_count(1)
    expect(selo).to_contain_text(f"CID-10 {_CID}")
    expect(selo).to_contain_text(_CID_DESCRICAO)
    assert page.locator('#folha-viva-exame .exame-selo-cid[data-cid="M51.1"]').count() == 0, (
        "o selo saiu do TEXTO digitado, não do hidden canônico"
    )

    page.locator("#ia-cid-exame-chips .ia-cid-chip-x").click()
    page.wait_for_timeout(300)
    expect(page.locator("#folha-viva-exame .exame-selo-cid")).to_have_count(0)


# ===========================================================================
# AC7 — M-D e A2 sobrevivem
# ===========================================================================

def test_ac7_md_e_a2_sobrevivem_no_exame(page: Page, app_demo):
    _abrir(page, app_demo)

    cpf = page.locator("#exam-pac-cpf")
    expect(cpf).to_have_attribute("data-tipo", "cpf")
    expect(cpf).to_have_class(re.compile(r"\bcpf-input\b"))
    assert cpf.evaluate("el => el.readOnly") is True, "lock M-D do CPF do exame sumiu"
    assert page.locator("#exam-pac-nome").evaluate("el => el.readOnly") is True

    assert re.search(r"CPF/CNI \d{3}\.\d{3}\.\d{3}-\d{2}", _texto_folha(page)), (
        f"o CPF travado não chegou formatado à folha: {_texto_folha(page)[:300]!r}"
    )


# ===========================================================================
# AC8 — o flutuante não cobre o emitir
# ===========================================================================

def _se_cruzam(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
    )


def test_ac8_o_flutuante_nunca_cobre_o_botao_de_emitir(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)

    fab = page.locator("#exame-fab")
    emitir = page.locator("#btn-emitir-exame")

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)

    emitir.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    caixa_fab = fab.bounding_box() if fab.is_visible() else None
    caixa_emitir = emitir.bounding_box()
    assert caixa_emitir is not None
    if caixa_fab is not None:
        assert not _se_cruzam(caixa_fab, caixa_emitir), (
            "o flutuante do pedido está por cima do botão de emitir"
        )

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)


def test_ac8_o_flutuante_abre_e_fecha_a_folha(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)
    _preencher(page)

    papel = page.locator("#exame-papel")
    expect(papel).to_be_hidden()
    page.locator("#exame-fab").click()
    expect(papel).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#folha-viva-exame")).to_contain_text("HEMOGRAMA COMPLETO")

    # Escopado à gaveta do EXAME: o botão da receita existe no DOM mas está
    # fora da árvore de acessibilidade (submódulo oculto), e contar índices
    # entre submódulos seria frágil por construção.
    page.locator("#exame-papel .doc-fechar-folha").click()
    expect(papel).to_be_hidden(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC9 — o fluxo físico NÃO muda
# ===========================================================================

def test_ac9_o_fluxo_fisico_continua_sincrono_pelo_servidor(page: Page, app_demo):
    """O papel oficial continua nascendo no backend. O que esta onda
    acrescenta é o carimbo na folha — o prescritor passa a VER o documento que
    acabou de imprimir, em vez de nada."""
    _abrir(page, app_demo)
    _preencher(page)

    chamadas: list[str] = []
    page.on("request", lambda r: chamadas.append(r.url) if "/pedidos-exame" in r.url else None)

    page.get_by_role(
        "button", name="🖨️ Apenas Imprimir Físico (sem envio digital)"
    ).click()
    expect(page.locator("#folha-viva-exame .exame-carimbo")).to_be_visible(timeout=_TIMEOUT_MS)

    assert any(u.endswith("/pedidos-exame/fisica") for u in chamadas), (
        f"o fluxo físico deixou de passar pelo servidor: {chamadas}"
    )
    assert any("/pdf" in u for u in chamadas), (
        "o PDF oficial deixou de ser buscado no backend — o papel do exame "
        "nasce no servidor, e esta onda não muda isso"
    )

    documento = _texto_documento(page)
    assert "IMPRESSO · SEM CUSTÓDIA DIGITAL" in documento
    assert "não gerado — emissão física" in documento, (
        "a folha física precisa dizer que não há documento canônico, em vez de "
        "deixar a lacuna prometendo um hash que não vem"
    )
    assert _alvos_batem(page)


# ===========================================================================
# AC10 — o selo de custódia
# ===========================================================================

_SELO = "✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE"


def test_ac10_no_rascunho_nao_ha_selo(page: Page, app_demo):
    """Ainda não houve transmissão — a folha não anuncia posse que não nasceu."""
    _abrir(page, app_demo)
    _preencher(page)
    expect(page.locator("#folha-viva-exame .exame-carimbo")).to_have_count(0)
    assert "TRANSMITIDO" not in _texto_folha(page)


def test_ac10_o_selo_nasce_na_emissao_com_a_rotacao_e_a_redacao_marteladas(
    page: Page, app_demo
):
    _abrir(page, app_demo)
    _preencher(page)
    _emitir(page)

    selo = page.locator("#folha-viva-exame .exame-carimbo")
    assert _SELO in selo.inner_text(), (
        f"o selo diz {selo.inner_text()!r}; esperado conter {_SELO!r}. "
        '"RUMO AO PRESTADOR" foi rejeitado: anteciparia um fato que ainda não '
        "ocorreu (a lição do `pedido_agendado` fantasma)."
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

    # Caixa-alta na FUNÇÃO, nunca em `text-transform` — o W ≡ Y compara texto.
    assert selo.evaluate("el => getComputedStyle(el).textTransform") == "none"
    assert "TRANSMITIDO · CUSTÓDIA AO PACIENTE" in _texto_documento(page)


# ===========================================================================
# A extração (commit 1) vista de fora: um núcleo, dois consumidores
# ===========================================================================

def test_o_nucleo_e_consumido_pelos_dois_geradores(page: Page, app_demo):
    """O núcleo nunca existe órfão — é a razão de ele nascer nesta onda."""
    _abrir(page, app_demo)
    tipos = page.evaluate(
        """() => ({
            nucleo: typeof window.DocumentoNucleo,
            receita: typeof window.Receituario,
            exame: typeof window.PedidoExame,
            mesmosModos: window.Receituario.MODOS === window.PedidoExame.MODOS,
            mesmaRegua: window.Receituario.textoDoDocumento
                        === window.PedidoExame.textoDoDocumento,
        })"""
    )
    assert tipos["nucleo"] == "object"
    assert tipos["receita"] == "object" and tipos["exame"] == "object"
    assert tipos["mesmosModos"] is True, "os dois documentos usam tabelas de modo diferentes"
    assert tipos["mesmaRegua"] is True, (
        "cada documento trouxe a sua régua de W ≡ Y — três documentos com três "
        "réguas seriam três promessas diferentes com o mesmo nome"
    )


def test_os_dois_documentos_convivem_sem_se_misturar(page: Page, app_demo):
    """A receita e o exame preenchidos ao mesmo tempo: cada folha com o seu."""
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
    expect(page.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)

    page.locator("#lista-medicamentos .med-nome").fill("Losartana Potassica")
    page.wait_for_timeout(250)

    page.locator("#submod-btn-exames").click()
    expect(page.locator("#submod-exames")).to_be_visible(timeout=_TIMEOUT_MS)
    _preencher(page)

    receita = page.evaluate("() => Receituario.textoDoDocumento('folha-viva')")
    exame = _texto_folha(page)

    assert "LOSARTANA POTASSICA" in receita and "LOSARTANA" not in exame
    assert "HEMOGRAMA COMPLETO" in exame and "HEMOGRAMA" not in receita
