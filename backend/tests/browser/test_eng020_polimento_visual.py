"""
tests/browser/test_eng020_polimento_visual.py — a alma visual da folha (ENG-020).

POR QUE ESTAS GUARDAS EXISTEM
-----------------------------
A onda 1 (ENG-018) cumpriu a promessa MECÂNICA — um template, dois alvos, W ≡ Y
— e perdeu a visual: a folha saiu parecendo card de dashboard, não papel. O
martelo do Fabiano foi literal: *"o design não ficou igual"*. Este arquivo
transforma os seis itens estéticos do despacho em medida, para que "igual" pare
de ser opinião e vire número.

O QUE SE PODE E O QUE NÃO SE PODE MEDIR
---------------------------------------
Não se testa beleza. Testa-se o que a beleza aqui DEPENDE: a cor da mesa, a
família tipográfica no alvo certo, a borda quente, a rotação do selo, o
contraste da lacuna, a proporção da folha. Cada um desses foi especificado com
valor no despacho — e valor especificado é valor verificável.

O item que mais importa não é estético: o **selo de custódia** (A4) é conteúdo
do ESTADO emitido, não cromo de modo. Por isso a guarda dele termina conferindo
que o W ≡ Y continuou verde — embelezar o carimbo não pode ser a porta pela
qual os dois alvos voltam a divergir.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

_TIMEOUT_MS = 15_000

# A1 — a mesa onde o papel assenta (despacho §2, A1: creme quente ~#F7F5EF).
_CREME = (247, 245, 239)
# A3 — a borda quente da folha (~#D9D2C0).
_BORDA_PAPEL = (217, 210, 192)
# A5 — piso de contraste da lacuna sobre o papel. 3:1 é o limiar WCAG AA para
# elemento não-textual; abaixo disso o pontilhado é sussurro, não convite.
_CONTRASTE_MINIMO = 3.0
# A6 — a folha ocupa pelo menos isto do palco em 1366px.
_FATIA_MINIMA_DO_PAPEL = 0.40
# AC5 do ENG-018, que o A6 estende: a pena continua legível.
_PENA_MINIMA_PX = 520


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _abrir(pg: Page, base: str) -> None:
    pg.goto(f"{base}/prescritor.html", wait_until="networkidle")
    expect(pg.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)


def _rgb(css: str) -> tuple[int, int, int]:
    n = [int(x) for x in re.findall(r"\d+", css)[:3]]
    return (n[0], n[1], n[2])


def _perto(a: tuple[int, int, int], b: tuple[int, int, int], tol: int = 6) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _luminancia(cor: tuple[int, int, int]) -> float:
    def canal(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in cor)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _card(pg: Page, n: int = 0):
    return pg.locator("#lista-medicamentos .med-card").nth(n)


def _preencher(pg: Page, quantidade: str = "30") -> None:
    pg.fill("#pac-idade", "58")
    pg.fill("#pac-endereco", "Rua das Flores, 123 - Boa Viagem")
    pg.fill("#pac-cidade", "Recife")
    pg.fill("#pac-cep", "51021030")
    c = _card(pg)
    c.locator(".med-nome").fill("Losartana Potassica")
    c.locator(".med-conc").fill("50 mg")
    c.locator(".med-qtd").fill(quantidade)
    c.locator(".med-unidade").select_option("comprimido")
    c.locator(".med-posologia").fill("Tomar pela manha.")
    pg.wait_for_timeout(300)


def _alvos_batem(pg: Page) -> bool:
    return pg.evaluate(
        """() => Receituario.textoDoDocumento('folha-viva')
                 === Receituario.textoDoDocumento('print-area')"""
    )


# ===========================================================================
# §1.1 — o plural da unidade: "30 comprimido" não é português
# ===========================================================================

def test_p1_a_unidade_concorda_com_a_quantidade(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page, quantidade="30")

    folha = page.evaluate("() => Receituario.textoDoDocumento('folha-viva')")
    assert "30 comprimidos" in folha, f"a folha ainda diz o singular: {folha[:400]!r}"
    assert "30 comprimido " not in folha


def test_p1_uma_unidade_fica_no_singular(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page, quantidade="1")
    folha = page.evaluate("() => Receituario.textoDoDocumento('folha-viva')")
    # `textContent` não separa elementos vizinhos: o texto sai
    # "… · 1 comprimidoValidade: 30 dias". Ancoramos no separador da esquerda.
    assert "· 1 comprimido" in folha, folha[:400]
    assert "1 comprimidos" not in folha


@pytest.mark.parametrize(
    "unidade,quantidade,esperado",
    [
        ("comprimido", "30", "comprimidos"),
        ("comprimido", "1", "comprimido"),
        ("cápsula", "2", "cápsulas"),
        ("sachê", "10", "sachês"),
        ("frasco-ampola", "3", "frascos-ampola"),   # composto: flexiona o 1º núcleo
        ("frasco-ampola", "1", "frasco-ampola"),
        ("unidade", "5", "unidades"),
        ("comprimido", "", "comprimido"),           # sem número, não se inventa concordância
        ("comprimido", "abc", "comprimido"),
    ],
)
def test_p1_regra_do_plural(page: Page, app_demo, unidade, quantidade, esperado):
    _abrir(page, app_demo)
    obtido = page.evaluate(
        "([u, q]) => Receituario.pluralizarUnidade(u, q)", [unidade, quantidade]
    )
    assert obtido == esperado


def test_p1_uma_correcao_cura_as_tres_superficies(page: Page, app_demo):
    """A martelada ② pagando: a folha viva e o documento impresso recebem o
    plural pela MESMA função. Com dois templates seriam dois consertos — e uma
    data futura em que um deles voltaria a dizer "30 comprimido"."""
    _abrir(page, app_demo)
    _preencher(page, quantidade="30")
    documento = page.evaluate("() => Receituario.textoDoDocumento('print-area')")
    assert "30 comprimidos" in documento
    assert _alvos_batem(page)


# ===========================================================================
# §1.2 — nenhum placeholder cortado no palco
# ===========================================================================

def test_p2_nenhum_placeholder_corta_no_palco(page: Page, app_demo):
    """Generalizada de propósito.

    O despacho nomeia um campo (o telefone, "DDD + Númer…"). Ao medir, eram
    QUATRO — e três deles no card de fármaco, incluindo o do PRINCÍPIO ATIVO:
    regressão da própria onda 1, que mudou a coluna de ~818px para ~564px sem
    rebalancear o formulário. Guardar só o campo nomeado deixaria a mesma
    classe de defeito viva nos outros três.
    """
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)

    cortados = page.evaluate(
        """() => {
            const medir = (el) => {
                const cs = getComputedStyle(el);
                const ctx = document.createElement('canvas').getContext('2d');
                ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
                const texto = ctx.measureText(el.placeholder || '').width;
                const util = el.clientWidth
                           - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
                return { campo: el.id || el.className, ph: el.placeholder,
                         texto: Math.round(texto), util: Math.round(util) };
            };
            return [...document.querySelectorAll(
                        '#submod-receita input[placeholder], #submod-receita textarea[placeholder]')]
                   .filter(el => el.offsetParent !== null)
                   .map(medir)
                   .filter(m => m.texto > m.util);
        }"""
    )
    assert not cortados, (
        "placeholder(s) cortado(s) — o texto não cabe no campo: "
        + "; ".join(f"{c['ph']!r} precisa de {c['texto']}px e tem {c['util']}px"
                    for c in cortados)
    )


# ===========================================================================
# §1.3 — a vitrine para de prometer o que não faz
# ===========================================================================

def test_p3_nenhuma_promessa_govbr_na_tela(page: Page, app_demo):
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
    expect(page.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)

    visivel = page.locator("body").inner_text()
    for promessa in ("gov.br", "em breve", "Em Implantação", "Assinar em Nuvem"):
        assert promessa.lower() not in visivel.lower(), (
            f"a tela do prescritor ainda promete {promessa!r} — vitrine que "
            "promete o que não faz gasta a credibilidade do que ela faz"
        )

    # O que FICA: o certificado ICP-Brasil, que tem modal funcional.
    # `.first`: o rótulo aparece também no <h3> do modal (oculto) — o que
    # importa aqui é o link vivo no bloco de emissão.
    expect(page.get_by_text("Meu certificado ICP-Brasil").first).to_be_visible()
    expect(page.locator("#btn-emitir")).to_be_visible()


# ===========================================================================
# A1 · A3 — a mesa e o papel
# ===========================================================================

def test_a1_o_palco_e_creme_quente_nao_cinza_frio(page: Page, app_demo):
    _abrir(page, app_demo)
    cor = _rgb(page.locator(".receita-palco").evaluate(
        "el => getComputedStyle(el).backgroundColor"))
    assert _perto(cor, _CREME), (
        f"o palco está em {cor}, não no creme {_CREME} — a folha precisa de uma "
        "mesa quente para assentar, não do cinza-azulado da UI"
    )


def test_a3_a_folha_tem_material_de_papel(page: Page, app_demo):
    _abrir(page, app_demo)
    estilo = page.locator("#folha-viva .rec-folha").evaluate(
        """el => {
            const cs = getComputedStyle(el);
            return { borda: cs.borderTopColor, raio: parseFloat(cs.borderTopLeftRadius),
                     sombra: cs.boxShadow };
        }"""
    )
    assert _perto(_rgb(estilo["borda"]), _BORDA_PAPEL), (
        f"borda em {estilo['borda']} — A3 pede a linha quente {_BORDA_PAPEL}"
    )
    assert estilo["raio"] >= 4, "canto reto demais para ler-se como folha"
    assert estilo["sombra"] and estilo["sombra"] != "none", "folha sem sombra não pousa"


# ===========================================================================
# A2 — tipografia dual: documento serifado, UI sans
# ===========================================================================

def test_a2_o_documento_e_serifado_e_a_ui_permanece_sans(page: Page, app_demo):
    _abrir(page, app_demo)
    doc = page.locator("#folha-viva .rec-folha").evaluate(
        "el => getComputedStyle(el).fontFamily").lower()
    ui = page.locator("#pac-nome").evaluate(
        "el => getComputedStyle(el).fontFamily").lower()

    assert "serif" in doc and "sans-serif" not in doc, (
        f"o DOCUMENTO deveria ser serifado (editorial, de papel): {doc!r}"
    )
    assert "serif" not in ui or "sans-serif" in ui, (
        f"a UI virou serifada junto — a metáfora é do papel, não da pele do "
        f"app inteiro (adjudicação de escopo do §2): {ui!r}"
    )


def test_a2_a_serifa_vale_tambem_no_documento_impresso(page: Page, app_demo):
    """É o MESMO documento — não uma versão dele para a tela."""
    _abrir(page, app_demo)
    impresso = page.locator("#print-area .rec-folha").evaluate(
        "el => getComputedStyle(el).fontFamily").lower()
    assert "serif" in impresso and "sans-serif" not in impresso


# ===========================================================================
# A4 — o selo de custódia: conteúdo do estado, W ≡ Y intocado
# ===========================================================================

_SELO = "✓ TRANSMITIDA · CUSTÓDIA AO PACIENTE"


def test_a4_no_rascunho_nao_ha_selo(page: Page, app_demo):
    """Ainda não houve transmissão — e a folha não anuncia posse que não nasceu."""
    _abrir(page, app_demo)
    _preencher(page)
    expect(page.locator("#folha-viva .rec-carimbo")).to_have_count(0)
    assert "TRANSMITIDA" not in page.evaluate(
        "() => Receituario.textoDoDocumento('folha-viva')")


def test_a4_o_selo_nasce_na_emissao_com_a_rotacao_do_prototipo(page: Page, app_demo):
    _abrir(page, app_demo)
    _preencher(page)
    page.locator("#btn-emitir").click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)

    selo = page.locator("#folha-viva .rec-carimbo")
    expect(selo).to_be_visible()
    assert _SELO in selo.inner_text(), (
        f"o selo diz {selo.inner_text()!r}; esperado conter {_SELO!r}"
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


def test_a4_o_selo_e_conteudo_do_estado_e_nao_quebra_o_w_equiv_y(page: Page, app_demo):
    """A guarda que importa: o selo é CONTEÚDO, então vale nos dois alvos — e
    a caixa-alta nasce na função, nunca de `text-transform` (a lei do ENG-018,
    reafirmada no §2). Fosse cromo de CSS, o texto divergiria do que se vê."""
    _abrir(page, app_demo)
    _preencher(page)
    page.locator("#btn-emitir").click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)

    assert _alvos_batem(page), "o selo fez a folha e o documento divergirem"
    documento = page.evaluate("() => Receituario.textoDoDocumento('print-area')")
    assert "TRANSMITIDA · CUSTÓDIA AO PACIENTE" in documento, (
        "o selo não chegou ao documento impresso, ou chegou em minúsculas "
        "(caixa-alta feita em CSS não entra no texto — e o W ≡ Y compara texto)"
    )
    transformado = page.locator("#folha-viva .rec-carimbo").evaluate(
        "el => getComputedStyle(el).textTransform")
    assert transformado == "none", (
        "o selo voltou a depender de `text-transform` para ficar em caixa-alta"
    )


# ===========================================================================
# A5 — a lacuna é convite, não sussurro
# ===========================================================================

def test_a5_a_lacuna_tem_contraste_de_convite(page: Page, app_demo):
    _abrir(page, app_demo)
    lacuna = page.locator("#folha-viva .rec-lacuna").first
    expect(lacuna).to_be_visible()

    cores = lacuna.evaluate(
        """el => {
            const cs = getComputedStyle(el);
            const folha = getComputedStyle(el.closest('.rec-folha'));
            return { tinta: cs.color, pontilhado: cs.borderBottomColor,
                     papel: folha.backgroundColor, estilo: cs.borderBottomStyle };
        }"""
    )
    papel = _rgb(cores["papel"])
    assert cores["estilo"] == "dotted", "a lacuna perdeu o pontilhado"

    for nome, cor in (("texto", cores["tinta"]), ("pontilhado", cores["pontilhado"])):
        razao = _contraste(_rgb(cor), papel)
        assert razao >= _CONTRASTE_MINIMO, (
            f"o {nome} da lacuna tem contraste {razao:.2f}:1 sobre o papel "
            f"(mínimo {_CONTRASTE_MINIMO}) — continua sussurro"
        )


# ===========================================================================
# A6 — proporções: a folha com corpo, a pena legível
# ===========================================================================

def test_a6_o_papel_ocupa_ao_menos_dois_quintos_em_1366(page: Page, app_demo):
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)

    m = page.evaluate(
        """() => {
            const r = s => document.querySelector(s).getBoundingClientRect().width;
            return { palco: r('.receita-palco'), papel: r('#folha-viva'),
                     pena: r('.receita-pena') };
        }"""
    )
    fatia = m["papel"] / m["palco"]
    assert fatia >= _FATIA_MINIMA_DO_PAPEL, (
        f"a folha ficou com {fatia:.1%} do palco (mínimo "
        f"{_FATIA_MINIMA_DO_PAPEL:.0%}) — papel espremido não lê como papel"
    )
    assert m["pena"] >= _PENA_MINIMA_PX, (
        f"a pena caiu para {m['pena']:.0f}px — o A6 estende o AC5, não o revoga"
    )
