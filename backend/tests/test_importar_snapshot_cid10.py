"""
test_importar_snapshot_cid10.py — TICKET-FILA-6-CID10-COMPLETO.md, teto
acessível (§6, martelo do Fabiano 29/08/2026).

Cobre a transformação pura (sem I/O), a guarda AC1/AC4 de ferramenta
offline (mesma disciplina dos importadores CBO/RDC) e a regressão de
formato (AC2 do ticket) sobre a base real pós-transformação.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = _RAIZ / "backend" / "scripts" / "importar_snapshot_cid10.py"
_APP_DIR = _RAIZ / "backend" / "app"
_CSV = _RAIZ / "data" / "cid10.csv"

sys.path.insert(0, str(_RAIZ / "backend" / "scripts"))
import importar_snapshot_cid10 as importador  # noqa: E402

_RE_FORMATO_CID = re.compile(r"^[A-Z]\d{2}(\.\d)?$")


def _linhas_de_teste():
    return [
        {"codigo_cid": "A00", "descricao": "Cólera", "fonte": "DATASUS/CID-10 V2008"},
        {"codigo_cid": "U07.1", "descricao": "COVID-19, vírus identificado",
         "fonte": "OMS/CID-10 uso emergencial 2020"},
        {"codigo_cid": "U08.9", "descricao": "História pessoal de COVID-19, não especificada",
         "fonte": "OMS/CID-10 uso emergencial 2020 (set/2020)"},
    ]


# ---------------------------------------------------------------------------
# Transformação pura
# ---------------------------------------------------------------------------

def test_transformar_estampa_versao_snapshot_em_toda_row():
    rows, _stats = importador._transformar(_linhas_de_teste())
    assert all(r["versao_snapshot"] == importador.VERSAO_SNAPSHOT for r in rows)


def test_transformar_recita_apenas_os_codigos_de_remendo():
    rows, stats = importador._transformar(_linhas_de_teste())
    por_codigo = {r["codigo_cid"]: r for r in rows}

    # A0O não é remendo — fonte intocada.
    assert por_codigo["A00"]["fonte"] == "DATASUS/CID-10 V2008"

    # U07.1 é coberto pelo doc MS 2025.
    assert por_codigo["U07.1"]["fonte"] == importador._FONTE_MS_2025
    # U08.9 não é coberto pelo doc MS — cai no doc OMS updates 3/4.
    assert por_codigo["U08.9"]["fonte"] == importador._FONTE_OMS_UPD34

    codigos_recitados = {c for c, _antes, _depois in stats["recitadas"]}
    assert codigos_recitados == {"U07.1", "U08.9"}


def test_transformar_nunca_toca_codigo_ou_descricao():
    originais = _linhas_de_teste()
    rows, _stats = importador._transformar([dict(r) for r in originais])
    for antes, depois in zip(originais, rows):
        assert antes["codigo_cid"] == depois["codigo_cid"]
        assert antes["descricao"] == depois["descricao"]


def test_transformar_e_idempotente():
    rows1, stats1 = importador._transformar(_linhas_de_teste())
    rows2, stats2 = importador._transformar([dict(r) for r in rows1])
    assert rows1 == rows2
    assert stats1["recitadas"]        # 1ª rodada: 2 códigos mudaram
    assert not stats2["recitadas"]    # 2ª rodada: nada muda (já estava recitado)


def test_todos_os_sete_remendos_tem_fonte_definida():
    """Guard contra typo silencioso — os 7 códigos do §1 do ticket precisam
    estar no mapa, nem um a mais nem a menos."""
    esperado = {"U07.1", "U07.2", "U08.9", "U09.9", "U10.9", "U11.9", "U12.9"}
    assert set(importador._REMENDOS_RECITADOS) == esperado


# ---------------------------------------------------------------------------
# AC2 — regressão de formato sobre a base real, pós-transformação
# ---------------------------------------------------------------------------

def test_regressao_formato_100_por_cento_na_base_real():
    with _CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "base vazia — teste não cobriria nada"
    nao_bate = [r["codigo_cid"] for r in rows if not _RE_FORMATO_CID.match(r["codigo_cid"].strip())]
    assert not nao_bate, f"códigos fora do formato: {nao_bate[:10]}"
    letras = {r["codigo_cid"].strip()[0] for r in rows}
    assert len(letras) == 26, f"esperado 26 letras, achou {len(letras)}: {sorted(letras)}"


def test_toda_row_da_base_real_tem_versao_snapshot():
    with _CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    sem_versao = [r["codigo_cid"] for r in rows if not (r.get("versao_snapshot") or "").strip()]
    assert not sem_versao, f"rows sem versao_snapshot: {sem_versao[:10]}"


# ---------------------------------------------------------------------------
# AC1/AC5 — nunca em runtime/deploy (mesma guarda dos importadores CBO/RDC)
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
