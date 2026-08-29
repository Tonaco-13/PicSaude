"""
test_importar_snapshot_sigtap.py — TICKET-FILA-7-SIGTAP-EXAMES.md, fila 7.

Cobre a extração pura (sem I/O de escrita), o corte por whitelist literal
(grupo 02, todos os subgrupos) e a guarda de ferramenta offline (mesma
disciplina dos importadores CID/RDC/CBO já existentes.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = _RAIZ / "backend" / "scripts" / "importar_snapshot_sigtap.py"
_APP_DIR = _RAIZ / "backend" / "app"
_ZIP_REAL = _RAIZ / "data" / "fontes-oficiais" / "sigtap" / "TabelaUnificada_202606_v2606091427.zip"

sys.path.insert(0, str(_RAIZ / "backend" / "scripts"))
import importar_snapshot_sigtap as importador  # noqa: E402


def _zip_minimo(caminho: Path) -> None:
    """Constrói um ZIP SIGTAP mínimo (layout real, dados sintéticos) para
    testar a extração sem depender do dump real de 2.1MB.

    O DATASUS publica os TXT em latin-1 (confirmado no dump real via
    `curl`) — escrever aqui em UTF-8 faria o teste passar por acidente
    contra um encoding que a fonte real não usa; `.encode("latin-1")`
    força o mesmo byte a byte que `extrair()` espera decodificar."""
    tb_grupo = (
        "01" + "Ações de promoção e prevenção em saúde".ljust(100) + "202606\n"
        "02" + "Procedimentos com finalidade diagnóstica".ljust(100) + "202606\n"
    )
    tb_sub_grupo = (
        "0201" + "Coleta de material".ljust(100) + "202606\n"
        "0202" + "Diagnóstico em laboratório clínico".ljust(100) + "202606\n"
    )
    tb_forma = (
        "020101" + "Coleta de material por meio de punção".ljust(100) + "202606\n"
        "020201" + "Exames bioquimicos".ljust(100) + "202606\n"
    )
    # CO_PROCEDIMENTO(10) NO_PROCEDIMENTO(250) ... DT_COMPETENCIA(6) nas
    # posições 331-336 (layout real: Inicio 1, então índice 330 0-based).
    def _linha_proc(codigo, nome, competencia="202606"):
        campos_meio = " " * (330 - 10 - 250)  # entre nome e competência
        return f"{codigo}{nome:<250}{campos_meio}{competencia}\n"

    tb_proc = (
        _linha_proc("0201010011", "AMNIOCENTESE")
        + _linha_proc("0202010473", "DOSAGEM DE GLICOSE")
        + _linha_proc("0101010010", "ACAO NAO DIAGNOSTICA")  # grupo 01 — fora da whitelist
    )

    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr("tb_grupo.txt", tb_grupo.encode("latin-1"))
        zf.writestr("tb_sub_grupo.txt", tb_sub_grupo.encode("latin-1"))
        zf.writestr("tb_forma_organizacao.txt", tb_forma.encode("latin-1"))
        zf.writestr("tb_procedimento.txt", tb_proc.encode("latin-1"))


def test_extrair_corta_por_grupo_diagnostico(tmp_path):
    zip_path = tmp_path / "sigtap_teste.zip"
    _zip_minimo(zip_path)

    rows, stats = importador.extrair(zip_path)

    codigos = {r["codigo_sigtap"] for r in rows}
    assert "0201010011" in codigos   # grupo 02 — entra
    assert "0202010473" in codigos   # grupo 02 — entra
    assert "0101010010" not in codigos  # grupo 01 — fica de fora

    assert stats["total_procedimentos_tabela"] == 3
    assert stats["total_grupo_diagnostico"] == 2


def test_extrair_preenche_taxonomia_por_join(tmp_path):
    zip_path = tmp_path / "sigtap_teste.zip"
    _zip_minimo(zip_path)
    rows, _stats = importador.extrair(zip_path)

    linha = next(r for r in rows if r["codigo_sigtap"] == "0202010473")
    assert linha["nome"] == "DOSAGEM DE GLICOSE"
    assert linha["grupo"] == "Procedimentos com finalidade diagnóstica"
    assert linha["subgrupo"] == "Diagnóstico em laboratório clínico"
    assert linha["forma_organizacao"] == "Exames bioquimicos"
    assert linha["competencia"] == "202606"


def test_extrair_e_idempotente(tmp_path):
    zip_path = tmp_path / "sigtap_teste.zip"
    _zip_minimo(zip_path)
    rows1, _ = importador.extrair(zip_path)
    rows2, _ = importador.extrair(zip_path)
    assert rows1 == rows2


def test_whitelist_e_literal_nao_por_nome(tmp_path):
    """Um nome que 'parece' exame no grupo errado não deve entrar — o
    corte é só (grupo, subgrupo), nunca substring do nome."""
    zip_path = tmp_path / "sigtap_teste.zip"
    _zip_minimo(zip_path)
    rows, _ = importador.extrair(zip_path)
    codigos = {r["codigo_sigtap"] for r in rows}
    assert "0101010010" not in codigos  # "ACAO NAO DIAGNOSTICA" — grupo 01


# ---------------------------------------------------------------------------
# Extração sobre o ZIP real estagiado — só roda se ele existir localmente
# (o binário não é commitado; CI/dev sem o download local pula este teste).
# ---------------------------------------------------------------------------

def test_extrair_sobre_zip_real_se_disponivel():
    if not _ZIP_REAL.exists():
        import pytest
        pytest.skip("ZIP real não estagiado localmente (data/fontes-oficiais/sigtap/)")
    rows, stats = importador.extrair(_ZIP_REAL)
    assert stats["total_grupo_diagnostico"] >= 38 * 10  # AC2: dezenas x a curadoria
    assert all(r["codigo_sigtap"].startswith("02") for r in rows)
    assert len(stats["whitelist_subgrupos"]) == 14


# ---------------------------------------------------------------------------
# AC — nunca em runtime/deploy (mesma guarda dos importadores CID/RDC/CBO)
# ---------------------------------------------------------------------------

def test_script_nao_e_importado_por_nenhum_arquivo_de_app():
    nome_modulo = _SCRIPT.stem
    ofensores = []
    for py in _APP_DIR.rglob("*.py"):
        if nome_modulo in py.read_text(encoding="utf-8"):
            ofensores.append(str(py.relative_to(_RAIZ)))
    assert not ofensores, (
        f"{nome_modulo} referenciado em código de app/ (runtime/deploy): {ofensores}"
    )


def test_script_nao_e_chamado_pelo_predeploy_ou_dockerfile():
    nome_modulo = _SCRIPT.stem
    for candidato in ("backend/predeploy.sh", "Dockerfile"):
        caminho = _RAIZ / candidato
        if not caminho.exists():
            continue
        assert nome_modulo not in caminho.read_text(encoding="utf-8"), (
            f"{nome_modulo} referenciado em {candidato} — importador é ferramenta "
            "offline, nunca roda em deploy (R4/§2a)"
        )
