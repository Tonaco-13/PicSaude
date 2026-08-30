"""
test_paridade_deploy_assets.py — a guarda contra "gate verde, deploy cego".

A ESPÉCIE DE DEFEITO QUE ESTE ARQUIVO EXISTE PARA MATAR
-------------------------------------------------------
O gate serve o **repositório**; a vitrine serve a **imagem Docker**. Enquanto o
`Dockerfile` copiava uma LISTA EXPLÍCITA de assets, todo arquivo novo entrava no
repo, passava em todos os testes — inclusive nos de navegador, que abrem as
telas de verdade — e simplesmente **não existia em produção**.

Três já estavam 404 na vitrine quando o incidente estourou (24/08):

  · `lente.js` (#167) — o "ver rastreabilidade" **nunca** funcionou lá;
  · `catalogos-encaminhamento.js` (#187) — especialidade e CID vazios no
    formulário de encaminhamento;
  · `submodulos.js` / `submodulos.css` (#193) — derrubaram o init do
    prescritor, e o login parou.

**Os dois primeiros eram silenciosos**: degradavam uma função e seguiam em
frente. Só o terceiro quebrou alto o bastante para ser notado — e isso é o pior
da espécie, não o melhor: o defeito ficou meses no ar porque falhou *baixinho*.

POR QUE ESTA GUARDA E TAMBÉM O JOB DE IMAGEM
--------------------------------------------
Este arquivo é **estático e barato**: roda em todo PR, sem Docker, e casa cada
asset referenciado pelas telas contra os padrões de `COPY` do `Dockerfile`.
Pega a omissão no minuto em que ela nasce.

O passo de CI que **builda a imagem e confere os arquivos lá dentro**
(`.github/workflows/gates.yml`) é a prova final — pega o que o parser aqui não
souber ler (um `.dockerignore` novo, uma mudança de estágio, um destino
diferente). Um prova a REGRA de graça; o outro prova o FATO.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_DOCKERFILE = _RAIZ / "Dockerfile"

# Assets referenciados por `src=`/`href=` nas telas da raiz.
# `woff2` entrou no flip da abertura (30/08) — as fontes self-hosted do
# index.html (`<link rel="preload" href="fonts/....woff2">`) são o primeiro
# asset em SUBPASTA (`fonts/`) que esta guarda precisa enxergar.
_RE_ASSET = re.compile(r'(?:src|href)\s*=\s*["\']([^"\':?#]+\.(?:js|css|png|svg|ico|jpg|jpeg|webp|woff2))["\']')

# Destino do frontend dentro da imagem (o `PICSAUDE_FRONTEND_DIR`).
_DESTINO = "/app/frontend/"


def _telas() -> list[Path]:
    return sorted(_RAIZ.glob("*.html"))


def _assets_referenciados() -> dict[str, list[str]]:
    """Asset → telas que o referenciam. Só os LOCAIS: `http(s)://` e `//` são
    de fora e não entram na imagem por definição."""
    achados: dict[str, list[str]] = {}
    for tela in _telas():
        for ref in _RE_ASSET.findall(tela.read_text(encoding="utf-8")):
            if ref.startswith(("http://", "https://", "//", "data:")):
                continue
            achados.setdefault(ref.lstrip("./"), []).append(tela.name)
    return achados


def _padroes_copiados_para_o_frontend() -> list[str]:
    """Os padrões de origem (relativos à raiz do repo) que o Dockerfile copia
    para dentro de `_DESTINO` — direto ou por uma subpasta dela.

    `COPY fonts/ /app/frontend/fonts/` (flip da abertura, 30/08) é o
    primeiro caso de subpasta: o destino não é `_DESTINO` exato, mas começa
    por ele. Nesse caso o padrão vira `<sufixo>*` (ex.: `fonts/*`) — os
    arquivos de `fonts/` continuam acessíveis pelo MESMO caminho relativo
    que o HTML usa (`fonts/arquivo.woff2`), então o casamento contra o
    asset referenciado funciona igual ao caso plano.
    """
    padroes: list[str] = []
    for linha in _DOCKERFILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha.upper().startswith("COPY "):
            continue
        partes = linha[len("COPY "):].split()
        if len(partes) < 2:
            continue
        destino, origens = partes[-1], partes[:-1]
        if destino == _DESTINO:
            padroes.extend(origens)
        elif destino.startswith(_DESTINO) and destino.endswith("/"):
            sufixo = destino[len(_DESTINO):]
            padroes.extend(f"{sufixo}*" for origem in origens if origem.endswith("/"))
    return padroes


# ---------------------------------------------------------------------------
# 1 — o que as telas pedem, a imagem entrega
# ---------------------------------------------------------------------------

def test_o_dockerfile_copia_algo_para_o_frontend():
    """Sanidade do parser: se esta falhar, as outras passariam por vazio."""
    assert _padroes_copiados_para_o_frontend(), (
        f"nenhuma linha `COPY ... {_DESTINO}` encontrada — o parser desta guarda "
        "deixou de enxergar o Dockerfile, e as outras asserções ficariam ocas"
    )


def test_ha_assets_para_conferir():
    assert _assets_referenciados(), "nenhum asset referenciado — parser quebrado"


@pytest.mark.parametrize("asset", sorted(_assets_referenciados()))
def test_todo_asset_referenciado_existe_no_repo(asset):
    assert (_RAIZ / asset).is_file(), (
        f"`{asset}` é referenciado por {_assets_referenciados()[asset]} e não "
        "existe no repositório"
    )


@pytest.mark.parametrize("asset", sorted(_assets_referenciados()))
def test_todo_asset_referenciado_entra_na_IMAGEM(asset):
    """A guarda que teria evitado o incidente.

    Não basta o arquivo existir no repo: ele precisa casar com algum padrão de
    `COPY` que vá para o diretório do frontend. Era exatamente aqui que
    `lente.js`, `catalogos-encaminhamento.js` e `submodulos.*` caíam.
    """
    padroes = _padroes_copiados_para_o_frontend()
    casou = any(fnmatch.fnmatch(asset, p) for p in padroes)
    assert casou, (
        f"`{asset}` é referenciado por {_assets_referenciados()[asset]} e NÃO "
        f"casa com nenhum padrão de COPY para {_DESTINO} ({padroes}). "
        "Em produção ele seria 404 — e o gate, que serve o repo, não veria."
    )


# ---------------------------------------------------------------------------
# 2 — a guarda morde?
# ---------------------------------------------------------------------------

class TestAsGuardasMordem:
    """Guarda que nunca falha quando deveria é decoração (lição do R2, §2a)."""

    def test_asset_fora_da_lista_seria_acusado(self):
        padroes = ["*.html", "config.js", "logo-picsaude.png"]   # a lista do incidente
        for orfao in ("lente.js", "submodulos.js", "submodulos.css",
                      "catalogos-encaminhamento.js"):
            assert not any(fnmatch.fnmatch(orfao, p) for p in padroes), (
                f"o casamento não acusaria `{orfao}` — era exatamente o que "
                "acontecia antes do incidente"
            )

    def test_o_glob_atual_cobre_os_quatro_orfaos(self):
        padroes = _padroes_copiados_para_o_frontend()
        for orfao in ("lente.js", "submodulos.js", "submodulos.css",
                      "catalogos-encaminhamento.js"):
            assert any(fnmatch.fnmatch(orfao, p) for p in padroes), (
                f"`{orfao}` voltou a ficar de fora da imagem"
            )

    def test_o_extrator_enxerga_src_e_href(self, tmp_path):
        falso = tmp_path / "x.html"
        falso.write_text('<script src="a.js"></script><link href="b.css">', encoding="utf-8")
        achados = _RE_ASSET.findall(falso.read_text(encoding="utf-8"))
        assert set(achados) == {"a.js", "b.css"}

    def test_o_extrator_ignora_asset_EXTERNO(self, tmp_path):
        """CDN não entra na imagem — acusá-lo seria falso positivo eterno."""
        falso = tmp_path / "x.html"
        falso.write_text('<script src="https://cdn.exemplo/x.js"></script>', encoding="utf-8")
        externos = [r for r in _RE_ASSET.findall(falso.read_text(encoding="utf-8"))
                    if not r.startswith(("http://", "https://", "//"))]
        assert not externos
