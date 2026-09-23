"""
tests/browser/test_eng024_atestado_vivo.py — o Atestado Vivo, o degenerado.

POR QUE ESTE É O ARQUIVO QUE PROVA A FAMÍLIA
---------------------------------------------
A receita, o exame e o encaminhamento têm ITENS — lista onde a costura de um
documento pode se esconder. O atestado não tem nada disso: 18 campos que se
fecham numa ÚNICA FRASE corrida. Ou ela fecha, ou ela não fecha. Se o padrão
vale aqui, ele deixa de ser o padrão da receita e vira o padrão da casa.

A GUARDA MAIS IMPORTANTE NÃO É O W ≡ Y — É FOLHA ≡ DOMÍNIO
------------------------------------------------------------
O W ≡ Y compara dois alvos do CLIENTE. Aqui existe um risco maior: a frase é
construída duas vezes — em `texto_atestado.py` (servidor, a fonte) e em
`atestado.js` (cliente, para a folha ser viva). Este repositório já pagou por
essa duplicação uma vez: o rascunho e o PDF divergiam, e o profissional
conferia um texto e assinava outro — *"um espelho que mostra outra pessoa é
pior que nenhum espelho"*.

`TestFolhaEquivaleAoDominio` é o que impede a recaída: compara o corpo da
folha com o `corpo_documento` do servidor sobre uma MATRIZ de estados — os
dois ramos × as quatro cláusulas clínicas × conselho × horário × observação.
Com `test_atestado_espelho.py` (PDF ≡ rascunho), a cadeia fecha: PDF ≡
rascunho ≡ folha. Três renderizações, duas guardas, uma fonte.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

_TIMEOUT_MS = 15_000

# Campos que o servidor exige para devolver `corpo_documento` (sem eles a
# resposta é `None` por desenho — "None quando há faltantes").
_PROFISSIONAL = "Dra. Demo Maria Souza"
_REGISTRO = "12345"
_UF = "PE"
_DATA = "2026-09-22"
_MUNICIPIO = "Recife"

_PLACEHOLDERS = (
    "Nome completo do paciente",
    "000.000.000-00",
    "Ex.: virose, lombalgia",
    "Selecione a finalidade",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _abrir(pg: Page, base: str) -> None:
    pg.goto(f"{base}/prescritor.html", wait_until="networkidle")
    pg.locator("#submod-btn-atestado").click()
    expect(pg.locator("#submod-atestado")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(pg.locator("#folha-viva-atestado .at-folha")).to_have_count(1, timeout=_TIMEOUT_MS)


def _base_preenchida(pg: Page) -> None:
    pg.fill("#atestado-data", _DATA)
    pg.fill("#atestado-municipio", _MUNICIPIO)
    pg.select_option("#atestado-finalidade", index=1)
    pg.fill("#atestado-profissional", _PROFISSIONAL)
    pg.fill("#atestado-registro", _REGISTRO)
    pg.select_option("#atestado-uf-registro", _UF)
    pg.wait_for_timeout(250)


def _aplicar(pg: Page, **campos) -> None:
    """Escreve um estado no formulário e deixa a folha se refazer."""
    dias = campos.get("dias", "")
    pg.select_option("#atestado-tipo", "afastamento" if dias not in ("", "0") else "comparecimento")
    pg.evaluate(
        """(c) => {
            const d = document.getElementById('atestado-dias');
            d.disabled = false; d.value = c.dias || '';
            document.getElementById('atestado-indicacao').value = c.indicacao || '';
            document.getElementById('atestado-cid').value = c.cid || '';
            document.getElementById('atestado-conselho').value = c.conselho || 'CFM';
            document.getElementById('atestado-hora-inicio').value = c.hi || '';
            document.getElementById('atestado-hora-fim').value = c.hf || '';
            document.getElementById('atestado-observacao').value = c.obs || '';
            d.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        campos,
    )
    pg.wait_for_timeout(250)


def _texto_folha(pg: Page) -> str:
    return pg.evaluate("() => Atestado.textoDoDocumento('folha-viva-atestado')")


def _texto_documento(pg: Page) -> str:
    return pg.evaluate("() => Atestado.textoDoDocumento('print-area-atestado')")


def _alvos_batem(pg: Page) -> bool:
    return pg.evaluate(
        """() => Atestado.textoDoDocumento('folha-viva-atestado')
                 === Atestado.textoDoDocumento('print-area-atestado')"""
    )


def _corpos(pg: Page) -> dict:
    """Pergunta ao SERVIDOR e à FOLHA o corpo do mesmo estado."""
    return pg.evaluate(
        """async () => {
            const est = _estadoDoFormularioAtestado();
            const resp = await fetch(BACKEND + '/ia/documentos/atestado/validar', {
                method: 'POST', headers: authHeaders(),
                body: JSON.stringify({
                    paciente_nome: est.nome_paciente,
                    finalidade: est.finalidade,
                    indicacao_clinica: est.indicacao_clinica || null,
                    codigo_cid: est.codigo_cid || null,
                    dias_afastamento: est.dias_afastamento
                        ? parseInt(est.dias_afastamento, 10) : null,
                    data_documento: est.data_documento,
                    nome_profissional: est.profissional.nome,
                    registro_profissional: est.profissional.numero,
                    municipio_emissao: est.municipio,
                    conselho: est.conselho,
                    uf_registro: est.profissional.uf,
                    hora_inicio: est.hora_inicio || null,
                    hora_fim: est.hora_fim || null,
                    observacao_complementar: est.observacao_complementar || null,
                })});
            const d = await resp.json();
            return { servidor: d.corpo_documento, folha: Atestado.corpoAtestado(est),
                     faltantes: d.faltantes };
        }"""
    )


def _emitir(pg: Page) -> None:
    pg.locator("#btn-emitir-atestado").click()
    expect(pg.locator("#folha-viva-atestado .at-carimbo")).to_have_count(1, timeout=_TIMEOUT_MS)


# ===========================================================================
# A GUARDA FORTE — folha ≡ domínio
# ===========================================================================

class TestFolhaEquivaleAoDominio:
    """A frase que o prescritor vê é a que o servidor monta — caractere a
    caractere, em toda a matriz de estados."""

    # Os dois ramos × as quatro cláusulas clínicas × conselho × horário × obs.
    MATRIZ = [
        ("afastamento, texto + CID", dict(dias="3", indicacao="quadro gripal agudo", cid="J11")),
        ("afastamento, só texto", dict(dias="5", indicacao="lombalgia", cid="")),
        ("afastamento, só CID", dict(dias="2", indicacao="", cid="J11")),
        ("afastamento, sem cláusula", dict(dias="1", indicacao="", cid="")),
        ("comparecimento simples", dict(dias="0", indicacao="", cid="")),
        ("comparecimento com horário", dict(dias="0", hi="08:00", hf="10:30")),
        ("comparecimento, só hora de início", dict(dias="0", hi="08:00")),
        ("comparecimento, só hora de fim", dict(dias="0", hf="10:30")),
        ("CFO muda os adjetivos", dict(dias="3", conselho="CFO", indicacao="pulpite")),
        ("observação como acréscimo", dict(dias="4", obs="Reavaliacao em 7 dias.")),
        ("CFO + comparecimento + CID", dict(dias="0", conselho="CFO", cid="K02")),
    ]

    @pytest.mark.parametrize("nome,campos", MATRIZ, ids=[m[0] for m in MATRIZ])
    def test_a_folha_reproduz_o_corpo_do_dominio(self, page: Page, app_demo, nome, campos):
        _abrir(page, app_demo)
        _base_preenchida(page)
        _aplicar(page, **campos)

        r = _corpos(page)
        assert not r["faltantes"], (
            f"o servidor não montou o corpo (faltantes: {r['faltantes']}) — "
            "sem corpo do domínio não há o que comparar"
        )
        assert (r["servidor"] or "").strip() == (r["folha"] or "").strip(), (
            f"[{nome}] a folha divergiu do domínio.\n"
            f"  servidor: {r['servidor']!r}\n"
            f"  folha   : {r['folha']!r}"
        )

    def test_a_guarda_morde(self, page: Page, app_demo):
        """Divergência injetada tem de reprovar. Sem isto, a guarda apenas
        confirmaria que duas cópias iguais são iguais — e o valor dela é
        justamente pegar o dia em que deixarem de ser."""
        _abrir(page, app_demo)
        _base_preenchida(page)
        _aplicar(page, dias="3", indicacao="quadro gripal agudo", cid="J11")

        antes = _corpos(page)
        assert (antes["servidor"] or "").strip() == (antes["folha"] or "").strip()

        # Sabotagem cirúrgica no construtor do cliente.
        page.evaluate(
            """() => {
                const original = Atestado.corpoAtestado;
                Atestado.corpoAtestado = (e) => original(e).replace(
                    'esteve sob cuidados', 'permaneceu sob cuidados');
            }"""
        )
        depois = _corpos(page)
        assert (depois["servidor"] or "").strip() != (depois["folha"] or "").strip(), (
            "a guarda folha ≡ domínio não detectou uma divergência plantada"
        )


# ===========================================================================
# AC1 — a folha se escreve a cada tecla
# ===========================================================================

def test_ac1_a_folha_se_escreve_a_cada_tecla(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3", indicacao="quadro gripal agudo", cid="J11")

    folha = _texto_folha(page)
    for pedaco in (
        "ATESTADO MÉDICO",
        _PROFISSIONAL,
        "CRM-PE 12345",
        "João Demo da Silva",
        "Atesto, para fins",
        "esteve sob cuidados médicos",
        "22/09/2026",
        "quadro gripal agudo (CID J11)",
        "3 dia(s)",
        "Recife",
    ):
        assert pedaco in folha, f"{pedaco!r} não apareceu na folha do atestado"


def test_ac1_o_cpf_sai_mascarado_como_no_pdf(page: Page, app_demo):
    """A folha não expõe o CPF inteiro — o documento oficial também não."""
    _abrir(page, app_demo)
    folha = _texto_folha(page)
    assert "123.***.***.09" in folha, f"CPF não mascarado: {folha[:300]!r}"
    assert "123.456.789-09" not in folha


# ===========================================================================
# AC2 — a lacuna INLINE dentro da frase
# ===========================================================================

def test_ac2_a_lacuna_mora_dentro_da_frase(page: Page, app_demo):
    """O gesto característico deste objeto. O modo inline entrou no núcleo no
    #273 pensando no atestado, estreou no encaminhamento (#274) e chega aqui
    pronto — que era o ponto de pô-lo no contrato antes de existir quem o
    pedisse."""
    _abrir(page, app_demo)

    frase = page.locator('#folha-viva-atestado [data-campo="frase"]')
    inline = frase.locator(".doc-lacuna-inline")
    expect(inline).not_to_have_count(0)

    estilo = inline.first.evaluate(
        "el => ({ d: getComputedStyle(el).display, m: getComputedStyle(el).minWidth })"
    )
    assert estilo["d"] == "inline", f"a lacuna da frase virou bloco ({estilo})"
    assert estilo["m"] in ("0px", "auto")


def test_ac2_a_pontuacao_fecha_em_volta_da_lacuna(page: Page, app_demo):
    """A frase tem de continuar sendo frase com a lacuna no meio: a vírgula
    depois da finalidade e o "que" antes do nome não somem."""
    _abrir(page, app_demo)
    texto = page.locator('#folha-viva-atestado [data-campo="frase"]').inner_text()
    assert texto.startswith("Atesto, para fins"), texto[:120]
    assert ", que " in texto, texto[:200]
    assert texto.rstrip().endswith("."), texto[-80:]


def test_ac2_placeholder_nao_vaza(page: Page, app_demo):
    _abrir(page, app_demo)
    folha = _texto_folha(page)
    for placeholder in _PLACEHOLDERS:
        assert placeholder not in folha, f"placeholder {placeholder!r} vazou para a folha"


# ===========================================================================
# AC3 — W ≡ Y nos dois modos
# ===========================================================================

def test_ac3_w_equivale_a_y_e_sabotar_um_alvo_reprova(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3", indicacao="quadro gripal agudo", cid="J11")

    assert _alvos_batem(page)

    veredito = page.evaluate(
        """() => {
            const igual = () => Atestado.textoDoDocumento('folha-viva-atestado')
                                === Atestado.textoDoDocumento('print-area-atestado');
            const antes = igual();
            document.querySelector('#print-area-atestado [data-bloco="corpo"]')
                    .insertAdjacentHTML('beforeend', '<span>SABOTAGEM</span>');
            return { antes: antes, depois: igual() };
        }"""
    )
    assert veredito["antes"] is True
    assert veredito["depois"] is False, (
        "a comparação W ≡ Y do atestado não detectou uma divergência plantada"
    )


def test_ac3_o_w_equiv_y_vale_no_estado_emitido(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")
    _emitir(page)
    assert _alvos_batem(page)
    assert "EMITIDO · CUSTÓDIA AO PACIENTE" in _texto_documento(page)


# ===========================================================================
# AC4 — carimbo sem navegação; emitida não se edita
# ===========================================================================

def test_ac4_o_carimbo_cai_na_mesma_folha(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")

    expect(page.locator('#folha-viva-atestado [data-campo="protocolo"] .at-lacuna')).to_have_count(1)
    page.evaluate(
        "() => { document.getElementById('folha-viva-atestado').dataset.marcaDoTeste = 'a-mesma'; }"
    )
    _emitir(page)

    assert page.evaluate(
        "() => document.getElementById('folha-viva-atestado').dataset.marcaDoTeste"
    ) == "a-mesma", "a folha foi substituída na emissão"

    expect(page.locator("#submod-atestado")).to_be_visible()
    folha = _texto_folha(page)
    assert re.search(r"Protocolo: [0-9a-f]{8}-[0-9a-f]{4}", folha), folha[:250]


def test_ac4_atestado_emitido_nao_se_edita(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")
    _emitir(page)

    congelada = _texto_folha(page)
    page.fill("#atestado-observacao", "texto digitado depois de emitir")
    page.wait_for_timeout(300)
    assert _texto_folha(page) == congelada, (
        "editar o formulário alterou o atestado JÁ EMITIDO (CLAUDE.md §1)"
    )
    assert _alvos_batem(page)


def test_o_limpar_devolve_a_folha_em_branco(page: Page, app_demo):
    """O "Novo atestado" deste objeto. Sem isto, o próximo atestado nasceria
    debaixo do papel do anterior — e a folha congelada nunca mais se soltaria.

    O que se afirma aqui é o que o lock M-D não consegue forjar: o SELO some.
    (Nome e CPF voltam sozinhos em DEMO, de propósito — por isso não servem
    como prova.)"""
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")
    _emitir(page)
    assert re.search(r"Protocolo: [0-9a-f]{8}", _texto_folha(page))

    page.locator('#submod-atestado button:has-text("Limpar")').click()
    expect(page.locator("#folha-viva-atestado .at-carimbo")).to_have_count(0, timeout=_TIMEOUT_MS)

    folha = _texto_folha(page)
    assert not re.search(r"Protocolo: [0-9a-f]{8}", folha), folha[:250]
    assert page.locator(
        '#folha-viva-atestado [data-campo="protocolo"] .at-lacuna'
    ).count() == 1, "o protocolo não voltou a ser lacuna"
    assert _alvos_batem(page), "o alvo de carimbo ficou com o atestado velho"


# ===========================================================================
# AC5 — a pena não é engolida
# ===========================================================================

def test_ac5_a_pena_nao_e_engolida_e_o_papel_tem_dois_quintos(page: Page, app_demo):
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)
    _base_preenchida(page)

    m = page.evaluate(
        """() => {
            const r = s => document.querySelector(s).getBoundingClientRect().width;
            return { palco: r('.at-palco'), papel: r('#folha-viva-atestado'),
                     pena: r('.at-pena'),
                     scroll: document.documentElement.scrollWidth,
                     viewport: window.innerWidth };
        }"""
    )
    fatia = m["papel"] / m["palco"]
    assert fatia >= 0.40, f"o papel ficou com {fatia:.1%} do palco (mínimo 40%)"
    assert m["pena"] >= 520, f"a pena caiu para {m['pena']:.0f}px"
    assert m["scroll"] <= m["viewport"] + 2, "rolagem horizontal em 1366px"


# ===========================================================================
# AC6 — os dois ramos fecham como o domínio
# ===========================================================================

@pytest.mark.parametrize(
    "campos,esperado,proibido",
    [
        (dict(dias="3"), "esteve sob cuidados médicos", "compareceu a atendimento"),
        (dict(dias="0"), "compareceu a atendimento médico", "afastado(a)"),
    ],
    ids=["afastamento", "comparecimento"],
)
def test_ac6_os_dois_ramos(page: Page, app_demo, campos, esperado, proibido):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, **campos)
    folha = _texto_folha(page)
    assert esperado in folha, folha[:300]
    assert proibido not in folha


def test_ac6_a_observacao_acrescenta_e_nunca_substitui(page: Page, app_demo):
    """Os campos estruturados seguem sendo a autoridade sobre dias, datas e
    finalidade — texto livre no lugar do corpo permitiria escrever "5 dias"
    com `dias_afastamento=3` no banco."""
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3", obs="Reavaliacao em 7 dias.")

    folha = _texto_folha(page)
    assert "3 dia(s)" in folha, "o corpo estruturado sumiu"
    assert "Reavaliacao em 7 dias." in folha, "a observação sumiu"
    expect(page.locator('#folha-viva-atestado [data-campo="observacao"]')).to_have_count(1)


# ===========================================================================
# AC7 — o conselho muda o documento inteiro
# ===========================================================================

@pytest.mark.parametrize(
    "conselho,titulo,sigla,adjetivo",
    [("CFM", "ATESTADO MÉDICO", "CRM-PE", "cuidados médicos"),
     ("CFO", "ATESTADO ODONTOLÓGICO", "CRO-PE", "cuidados odontológicos")],
)
def test_ac7_o_conselho_muda_titulo_sigla_e_frase(
    page: Page, app_demo, conselho, titulo, sigla, adjetivo
):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3", conselho=conselho)

    folha = _texto_folha(page)
    assert titulo in folha, f"título errado para {conselho}: {folha[:200]!r}"
    assert sigla in folha, f"sigla do registro errada para {conselho}"
    assert adjetivo in folha, f"adjetivo errado para {conselho}"


# ===========================================================================
# AC8 — M-D e A2
# ===========================================================================

def test_ac8_md_e_a2_sobrevivem(page: Page, app_demo):
    _abrir(page, app_demo)
    cpf = page.locator("#atestado-cpf")
    # A2 — a máscara é declarada pela CLASSE neste campo (`aplicarMascarasCPFGlobais`
    # casa `.cpf-input` OU `[data-tipo="cpf"]`). A asserção é sobre o efeito, não
    # sobre qual das duas declarações foi usada: `data-cpf-mask-applied` só existe
    # depois que a máscara de fato rodou sobre o campo.
    expect(cpf).to_have_class(re.compile(r"\bcpf-input\b"))
    expect(cpf).to_have_attribute("data-cpf-mask-applied", "1")
    assert cpf.evaluate("el => el.readOnly") is True, "lock M-D do CPF sumiu"
    assert page.locator("#atestado-paciente").evaluate("el => el.readOnly") is True


# ===========================================================================
# AC9 — mobile
# ===========================================================================

def _se_cruzam(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
    )


def test_ac9_o_flutuante_nunca_cobre_os_gestos_de_emissao(page: Page, app_demo):
    """A versão variádica do núcleo, pedida pelo encaminhamento, serve aqui
    sem mudança: o atestado tem emitir digital E imprimir físico."""
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)

    fab = page.locator("#at-fab")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)

    for alvo in ("#btn-emitir-atestado", "#btn-imprimir-atestado-fisico"):
        botao = page.locator(alvo)
        botao.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        caixa_fab = fab.bounding_box() if fab.is_visible() else None
        caixa_alvo = botao.bounding_box()
        assert caixa_alvo is not None
        if caixa_fab is not None:
            assert not _se_cruzam(caixa_fab, caixa_alvo), f"o flutuante cobre {alvo}"


def test_ac9_o_flutuante_abre_e_fecha_a_folha(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)
    _base_preenchida(page)

    papel = page.locator("#at-papel")
    expect(papel).to_be_hidden()
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    page.locator("#at-fab").click()
    expect(papel).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#folha-viva-atestado")).to_contain_text("Atesto, para fins")

    page.locator("#at-papel .doc-fechar-folha").click()
    expect(papel).to_be_hidden(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC10 — o fluxo físico é honesto
# ===========================================================================

def test_ac10_o_fisico_diz_que_nao_ha_custodia_nem_hash(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")

    chamadas: list[str] = []
    page.on("request", lambda r: chamadas.append(r.url) if "/atestados" in r.url else None)

    page.locator("#btn-imprimir-atestado-fisico").click()
    expect(page.locator("#folha-viva-atestado .at-carimbo")).to_have_count(1, timeout=_TIMEOUT_MS)

    assert any(u.endswith("/atestados/fisica") for u in chamadas), (
        f"o fluxo físico deixou de passar pelo servidor: {chamadas}"
    )
    assert any("/pdf" in u for u in chamadas), (
        "o PDF oficial deixou de vir do backend — `pdf_atestado.py` é intocado"
    )

    documento = _texto_documento(page)
    assert "IMPRESSO · EMISSÃO FÍSICA — SEM CUSTÓDIA DIGITAL" in documento
    assert "não gerado — emissão física" in documento, (
        "a folha física precisa dizer que não há documento canônico, em vez de "
        "deixar a lacuna prometendo um hash que não vem"
    )
    assert _alvos_batem(page)


# ===========================================================================
# AC11 — o selo por fluxo
# ===========================================================================

def test_ac11_no_rascunho_nao_ha_selo(page: Page, app_demo):
    _abrir(page, app_demo)
    _base_preenchida(page)
    expect(page.locator("#folha-viva-atestado .at-carimbo")).to_have_count(0)
    assert "EMITIDO" not in _texto_folha(page)


def test_ac11_o_selo_digital_e_fato_e_nao_promessa(page: Page, app_demo):
    """"CUSTÓDIA AO PACIENTE" é fato verificado no código: `atestados.py`
    registra a custódia prescritor → paciente na própria emissão."""
    _abrir(page, app_demo)
    _base_preenchida(page)
    _aplicar(page, dias="3")
    _emitir(page)

    selo = page.locator("#folha-viva-atestado .at-carimbo")
    assert "✓ EMITIDO · CUSTÓDIA AO PACIENTE" in selo.inner_text()

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
    assert selo.evaluate("el => getComputedStyle(el).textTransform") == "none"


# ===========================================================================
# A família, fechada — quatro
# ===========================================================================

def test_o_nucleo_e_consumido_pelos_quatro_geradores(page: Page, app_demo):
    _abrir(page, app_demo)
    t = page.evaluate(
        """() => {
            const g = [window.Receituario, window.PedidoExame,
                       window.Encaminhamento, window.Atestado];
            return {
                todos: g.every(x => typeof x === 'object'),
                mesmosModos: g.every(x => x.MODOS === window.DocumentoNucleo.MODOS),
                mesmaRegua: g.every(x => x.textoDoDocumento
                                    === window.DocumentoNucleo.textoDoDocumento),
            };
        }"""
    )
    assert t["todos"] is True, "um dos quatro geradores não carregou"
    assert t["mesmosModos"] is True
    assert t["mesmaRegua"] is True, (
        "quatro documentos com quatro réguas seriam quatro promessas "
        "diferentes com o mesmo nome"
    )


def test_os_quatro_documentos_convivem_sem_se_misturar(page: Page, app_demo):
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
    expect(page.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)
    page.locator("#lista-medicamentos .med-nome").fill("Losartana Potassica")

    page.locator("#submod-btn-exames").click()
    page.locator("#lista-exames .exame-nome").fill("Hemograma completo")

    page.locator("#submod-btn-atestado").click()
    expect(page.locator("#folha-viva-atestado .at-folha")).to_have_count(1, timeout=_TIMEOUT_MS)
    _base_preenchida(page)
    _aplicar(page, dias="3")

    receita = page.evaluate("() => Receituario.textoDoDocumento('folha-viva')")
    exame = page.evaluate("() => PedidoExame.textoDoDocumento('folha-viva-exame')")
    atestado = _texto_folha(page)

    assert "LOSARTANA POTASSICA" in receita and "LOSARTANA" not in atestado
    assert "HEMOGRAMA COMPLETO" in exame and "HEMOGRAMA" not in atestado
    assert "Atesto, para fins" in atestado and "Atesto" not in receita
