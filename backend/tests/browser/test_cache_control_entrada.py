"""
tests/browser/test_cache_control_entrada.py — ENG-018 (flip-readiness).

A REGRA
-------
**HTML, JS e CSS de entrada respondem `Cache-Control: no-cache`.**

POR QUE, COM O CASO CONCRETO
-----------------------------
A família do *"o fix subiu e o usuário ainda vê o bug"*. Aconteceu de verdade:
depois do #196, o cache do próprio Fabiano guardou a era dos 404 e ele
continuou vendo a vitrine quebrada por um tempo **depois** da cura.

Num repositório público é pior: cada visitante carrega a versão que pegou no
primeiro acesso, e um deles vai relatar um defeito **que já não existe** — o
que custa exatamente a confiança que a vitrine existe para construir.

`no-cache` e **não** `no-store`: o navegador pode guardar, mas tem de revalidar
antes de usar. Com ETag, a revalidação devolve 304 e quem não mudou não baixa
de novo — o custo é um round-trip vazio, não o arquivo inteiro.
"""
from __future__ import annotations

import httpx
import pytest

_ENTRADA = [
    "index.html", "entrar.html", "cidadao.html", "prescritor.html",
    "dispensador.html", "clinica.html", "config.js", "submodulos.js",
    "submodulos.css", "lente.js",
    # #238 (31/08) — logo e favicon trocaram de CONTEÚDO sob o MESMO nome de
    # arquivo (`logo-picsaude.png`, `favicon.ico`): exatamente o caso "o fix
    # subiu e o visitante segue vendo o antigo" que este arquivo existe para
    # matar, agora em imagem — não só em HTML/JS/CSS.
    "logo-picsaude.png", "favicon.ico",
]

# Flip da abertura (30/08) — o oposto do `_ENTRADA` acima: fontes self-hosted
# não têm o problema "fix subiu, visitante vê o antigo" (tipografia estável,
# mesmo nome desde a concepção) — cachear sem revalidar é o comportamento
# CORRETO aqui, não um esquecimento.
_FONTES_WOFF2 = [
    "fonts/fraunces-normal.woff2", "fonts/fraunces-italic.woff2",
    "fonts/inter-normal.woff2",
]


@pytest.mark.parametrize("recurso", _ENTRADA)
def test_recurso_de_entrada_nao_se_cacheia_sem_revalidar(app_demo, recurso):
    r = httpx.get(f"{app_demo}/{recurso}", timeout=15.0)
    assert r.status_code == 200, f"{recurso}: {r.status_code}"
    cc = r.headers.get("cache-control", "")
    assert "no-cache" in cc, (
        f"{recurso} respondeu `Cache-Control: {cc or '(ausente)'}` — sem "
        "`no-cache`, o visitante segue vendo a versão que pegou no primeiro "
        "acesso, e relata defeito que já não existe"
    )


@pytest.mark.parametrize("recurso", _ENTRADA)
def test_a_revalidacao_e_barata_ha_ETag(app_demo, recurso):
    """`no-cache` sem ETag transformaria toda visita num download completo.

    Com ETag, a segunda visita manda `If-None-Match` e leva **304** — corpo
    vazio. É o que torna a escolha `no-cache` (em vez de `no-store`) barata.
    """
    r1 = httpx.get(f"{app_demo}/{recurso}", timeout=15.0)
    etag = r1.headers.get("etag")
    assert etag, f"{recurso} não expõe ETag — a revalidação baixaria tudo de novo"

    r2 = httpx.get(f"{app_demo}/{recurso}",
                   headers={"If-None-Match": etag}, timeout=15.0)
    assert r2.status_code == 304, (
        f"{recurso} devolveu {r2.status_code} com ETag válido; esperava 304"
    )


def test_a_raiz_tambem_nao_se_cacheia(app_demo):
    """`/` serve o index pelo `html=True`; sem o cabeçalho, o portal — a
    primeira tela que qualquer visitante vê — congelaria."""
    r = httpx.get(f"{app_demo}/", timeout=15.0)
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")


@pytest.mark.parametrize("fonte", _FONTES_WOFF2)
def test_fonte_woff2_cacheia_agressivo(app_demo, fonte):
    """O OPOSTO da regra de entrada, de propósito: fonte não tem a doença
    que o `no-cache` acima cura, e cachear sem revalidar poupa 3 downloads
    (~200KB) por visita que quase nunca mudam."""
    r = httpx.get(f"{app_demo}/{fonte}", timeout=15.0)
    assert r.status_code == 200, f"{fonte}: {r.status_code}"
    cc = r.headers.get("cache-control", "")
    assert "max-age=31536000" in cc and "immutable" in cc, (
        f"{fonte} respondeu `Cache-Control: {cc or '(ausente)'}` — deveria "
        "cachear por 1 ano como immutable"
    )
    assert "no-cache" not in cc
