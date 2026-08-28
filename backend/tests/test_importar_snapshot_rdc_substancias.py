"""
test_importar_snapshot_rdc_substancias.py — DESENHO-TALAO-DIGITAL-SNCR.md
§1/§1.1, G1 (`adapter`), Opção 2.

Cobre a validação do importador (sem banco) e a guarda AC1/AC4 (script
não é invocado por runtime/deploy — mesma disciplina do importador CBO,
`test_importar_snapshot_cbo_encaminhamento.py`). O caminho end-to-end (com
banco real) fica em `tests/integration/test_importar_snapshot_rdc_pg.py`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = _RAIZ / "backend" / "scripts" / "importar_snapshot_rdc_substancias.py"
_APP_DIR = _RAIZ / "backend" / "app"

sys.path.insert(0, str(_RAIZ / "backend" / "scripts"))
import importar_snapshot_rdc_substancias as importador  # noqa: E402


def _snapshot_valido() -> dict:
    return {
        "fonte": "Portaria 344/98 Anexo I (teste)",
        "versao": "RDC 999/2099",
        "data_snapshot": "2099-01-01",
        "entradas": [
            {"dcb": "Morfina", "classe_controle": "A1", "tipo_retencao": None, "observacao": None},
            {"dcb": "Amoxicilina", "classe_controle": None, "tipo_retencao": "antimicrobiano", "observacao": None},
        ],
    }


# ---------------------------------------------------------------------------
# Validação do snapshot (pura, sem banco)
# ---------------------------------------------------------------------------

def test_snapshot_valido_passa():
    importador._validar_snapshot(_snapshot_valido())  # não deve lançar


@pytest.mark.parametrize("campo", ["fonte", "versao", "data_snapshot"])
def test_recusa_campo_obrigatorio_ausente(campo):
    dado = _snapshot_valido()
    dado[campo] = ""
    with pytest.raises(ValueError, match=campo):
        importador._validar_snapshot(dado)


def test_recusa_entradas_vazia():
    dado = _snapshot_valido()
    dado["entradas"] = []
    with pytest.raises(ValueError, match="entradas"):
        importador._validar_snapshot(dado)


def test_recusa_dcb_ausente():
    dado = _snapshot_valido()
    dado["entradas"].append({"dcb": "", "classe_controle": "A1"})
    with pytest.raises(ValueError, match="dcb"):
        importador._validar_snapshot(dado)


def test_recusa_dcb_duplicada():
    dado = _snapshot_valido()
    dado["entradas"].append({"dcb": "MORFINA", "classe_controle": "A1"})  # mesma DCB, case diferente
    with pytest.raises(ValueError, match="[Dd]uplicad"):
        importador._validar_snapshot(dado)


def test_recusa_entrada_sem_classe_e_sem_retencao():
    """Uma entrada sem classe_controle E sem tipo_retencao não pertence a
    uma lista de controlados — sinal de dado mal transcrito."""
    dado = _snapshot_valido()
    dado["entradas"].append({"dcb": "Dipirona", "classe_controle": None, "tipo_retencao": None})
    with pytest.raises(ValueError, match="Dipirona"):
        importador._validar_snapshot(dado)


# ---------------------------------------------------------------------------
# CLI — arquivo ausente aborta com exit != 0
# ---------------------------------------------------------------------------

def test_main_aborta_se_arquivo_nao_existe(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--arquivo", str(tmp_path / "nao-existe.json")],
        cwd=str(_RAIZ / "backend"),
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    assert "não existe" in proc.stdout or "não existe" in proc.stderr


# ---------------------------------------------------------------------------
# AC1/AC4 — nunca em runtime/deploy (mesma guarda do importador CBO)
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
