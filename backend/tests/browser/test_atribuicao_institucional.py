"""
tests/browser/test_atribuicao_institucional.py — atribuição institucional
(module+docs, 04/09).

O QUE ESTE ARQUIVO PROVA
------------------------
A fachada passou a falar pela INSTITUIÇÃO. No rodapé do `index.html`, a linha
"Responsável técnico: Dr. Fabiano Tonaco Borges." deu lugar à linha
institucional, que aponta para a certidão do projeto de extensão PJ324-2026.

> A fachada fala pela instituição; o documento fala pela pessoa.

A responsabilidade pessoal não sumiu — mudou para onde é exigível e
verificável: o responsável pela ação está na certidão, o titular no README, e
o assinante de cada curadoria clínica está na própria row (`validado_por`).

1. A linha institucional está no rodapé, **verbatim**, com o href da certidão.
2. A ocorrência pessoal **saiu** do `index.html` — a troca é troca, não
   acréscimo (se as duas coexistissem, a decisão não teria sido aplicada).
3. A linha é visível e clicável na página renderizada.
4. A emenda do FAQ ("Quem faz? Como sei que posso confiar?") está **verbatim**.
5. A régua de pontuação da casa: zero travessão nas duas cópias novas.

A copy das duas é travada pelo arquiteto. A fonte canônica é
`docs/tickets/DESPACHO-ATRIBUICAO-INSTITUCIONAL.md` — este arquivo é a cópia
EXECUTÁVEL dela: se alguém emendar uma palavra na tela, o gate acusa.

A lista fechada de alvos externos do `index.html` (repositório + certidão) é
guardada em `test_link_codigo_fonte_fachada.py`, que já existia para isso.
"""
from __future__ import annotations

import re

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

_CERTIDAO_URL = (
    "https://github.com/Tonaco-13/PicSaude/blob/main/docs/institucional/PJ324-2026.md"
)

# ─── Copy travada — verbatim do despacho, não reescrever ──────────────────────
_LINHA_INSTITUCIONAL = (
    "Um projeto de extensão da Engenharia Biomédica do CTG, "
    "Universidade Federal de Pernambuco."
)
_EMENDA_FAQ = (
    "É um projeto de extensão da UFPE, em código aberto, com licença AGPL e "
    "repositório público. Qualquer pessoa pode ler, auditar, usar e contribuir. "
    "As regras clínicas citam a fonte oficial, com página."
)
_PERGUNTA_FAQ = "Quem faz? Como sei que posso confiar?"

# A linha pessoal que saiu do rodapé da vitrine.
_OCORRENCIA_PESSOAL = "Responsável técnico"


def _texto(bruto: str) -> str:
    """Texto visível, com espaço em branco normalizado (a marcação quebra linhas)."""
    sem_comentario = re.sub(r"<!--.*?-->", " ", bruto, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sem_comentario)).strip()


def _html(app_demo: str) -> str:
    resposta = httpx.get(f"{app_demo}/", timeout=15.0)
    resposta.raise_for_status()
    return resposta.text


def test_a_linha_institucional_esta_no_rodape_verbatim(app_demo):
    html = _html(app_demo)
    rodape = html.split("<footer>", 1)[1]

    assert _CERTIDAO_URL in rodape, "o rodapé não aponta para a certidão PJ324-2026"
    assert _LINHA_INSTITUCIONAL in _texto(rodape), (
        "a linha institucional não está verbatim no rodapé — a copy é travada, "
        f"esperava: {_LINHA_INSTITUCIONAL!r}"
    )


def test_a_ocorrencia_pessoal_saiu_do_rodape(app_demo):
    """Troca é troca: a linha institucional entra NO LUGAR da pessoal."""
    html = _html(app_demo)
    assert _OCORRENCIA_PESSOAL not in html, (
        "a linha 'Responsável técnico' ainda está na abertura — a decisão de "
        "04/09 a substitui pela linha institucional, não convive com ela"
    )


def test_a_linha_institucional_e_visivel_e_clicavel(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")

    link = page.get_by_role("link", name=_LINHA_INSTITUCIONAL)
    expect(link).to_have_count(1)
    expect(link).to_be_visible(timeout=_TIMEOUT_MS)
    expect(link).to_have_attribute("href", _CERTIDAO_URL)


def test_a_emenda_do_faq_esta_verbatim(app_demo):
    html = _html(app_demo)

    itens = re.findall(
        r'<details class="faq-item">\s*<summary>(.*?)</summary>(.*?)</details>',
        html,
        re.S,
    )
    respostas = {_texto(p): _texto(r) for p, r in itens}

    assert _PERGUNTA_FAQ in respostas, (
        f"a pergunta {_PERGUNTA_FAQ!r} sumiu da FAQ; achei {sorted(respostas)}"
    )
    assert respostas[_PERGUNTA_FAQ] == _EMENDA_FAQ, (
        "a resposta 'Quem faz?' divergiu da copy travada.\n"
        f"esperado: {_EMENDA_FAQ!r}\n"
        f"na tela : {respostas[_PERGUNTA_FAQ]!r}"
    )


def test_regua_de_pontuacao_zero_travessao(app_demo):
    """Régua da casa para copy travada: travessão não entra por 'melhoria'."""
    html = _html(app_demo)
    itens = re.findall(
        r'<details class="faq-item">\s*<summary>(.*?)</summary>(.*?)</details>',
        html,
        re.S,
    )
    respostas = {_texto(p): _texto(r) for p, r in itens}

    for rotulo, trecho in (
        ("linha institucional", _LINHA_INSTITUCIONAL),
        ("emenda do FAQ", respostas.get(_PERGUNTA_FAQ, "")),
    ):
        for glifo, nome in (("—", "travessão"), ("–", "en-dash")):
            assert glifo not in trecho, f"{nome} apareceu na {rotulo}: {trecho!r}"
