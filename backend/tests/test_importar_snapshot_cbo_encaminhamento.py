"""
test_importar_snapshot_cbo_encaminhamento.py — typeahead/CBO PR 2 (`adapter`).

DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §3 — ACs do importador de base CBO.
Cobre: AC1 (toda entrada com código+família), AC2 (2515 presente — o caso-
guarda do §1, vermelho-antes-de-verde), AC3 (fonte/versão/data/famílias
declaradas no arquivo), AC4 (script não é invocado por runtime/deploy).
AC5 (CBO_PREFIXES intocado) e AC6 (painel não reaberto) são cobertos no
browser (`test_typeahead_encaminhamento.py`), não aqui.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = _RAIZ / "backend" / "scripts" / "importar_snapshot_cbo_encaminhamento.py"
_CATALOGO_JS = _RAIZ / "catalogos-encaminhamento.js"
_APP_DIR = _RAIZ / "backend" / "app"

sys.path.insert(0, str(_RAIZ / "backend" / "scripts"))
import importar_snapshot_cbo_encaminhamento as importador  # noqa: E402


# ---------------------------------------------------------------------------
# AC1 — toda especialidade oferecida carrega código CBO e família
# ---------------------------------------------------------------------------

def test_toda_entrada_tem_codigo_e_familia_declarados():
    for titulo, codigo, familia, _fonte in importador.ESPECIALIDADES:
        assert codigo, f"{titulo}: sem código"
        assert familia, f"{titulo}: sem família"
        assert codigo.startswith(familia), (
            f"{titulo}: código {codigo} não pertence à família declarada {familia}"
        )


def test_sem_codigo_ou_titulo_duplicado():
    titulos = [t for t, _, _, _ in importador.ESPECIALIDADES]
    codigos = [c for _, c, _, _ in importador.ESPECIALIDADES]
    assert len(titulos) == len(set(titulos)), "título duplicado na lista"
    assert len(codigos) == len(set(codigos)), "código CBO duplicado na lista"


def test_todas_as_familias_usadas_estao_declaradas():
    familias_usadas = {f for _, _, f, _ in importador.ESPECIALIDADES}
    assert familias_usadas <= set(importador.FAMILIAS_INCLUIDAS), (
        f"famílias usadas sem declaração em FAMILIAS_INCLUIDAS: "
        f"{familias_usadas - set(importador.FAMILIAS_INCLUIDAS)}"
    )


def test_titulos_das_15_especialidades_medicas_nao_mudaram():
    """As 15 especialidades já existentes na lista local (PR do painel)
    precisam manter o MESMO título — é o valor que viaja no payload do
    encaminhamento e casa com `DEMO.prescritorDestino.especialidade`
    (config.js) para a demo continuar funcionando. Renomear quebraria a
    circulação de ponta a ponta sem nenhum teste de unidade acusar — só
    apareceria no smoke E2E, tarde demais."""
    _15_ORIGINAIS = {
        "CARDIOLOGIA", "CIRURGIA GERAL", "DERMATOLOGIA", "ENDOCRINOLOGIA",
        "GASTROENTEROLOGIA", "GINECOLOGIA", "NEUROLOGIA", "OFTALMOLOGIA",
        "ORTOPEDIA", "OTORRINOLARINGOLOGIA", "PEDIATRIA", "PNEUMOLOGIA",
        "PSIQUIATRIA", "REUMATOLOGIA", "UROLOGIA",
    }
    titulos_atuais = {t for t, _, _, _ in importador.ESPECIALIDADES}
    faltando = _15_ORIGINAIS - titulos_atuais
    assert not faltando, f"especialidades originais sumiram da lista: {faltando}"


# ---------------------------------------------------------------------------
# AC2 — 2515 presente (o caso-guarda do §1). Vermelho-antes-de-verde: um
# snapshot SEM psicologia precisa reprovar na validação do importador.
# ---------------------------------------------------------------------------

def test_familia_2515_presente():
    familias = {f for _, _, f, _ in importador.ESPECIALIDADES}
    assert "2515" in familias, (
        "família 2515 (psicólogos e psicanalistas) ausente — é o caso-guarda "
        "do §1: psicologia é saúde mas fica fora do subgrupo CBO 22"
    )


def test_validar_reprova_snapshot_sem_psicologia(monkeypatch):
    """Prova por mutação (lição do R2, §2a): sabota a lista removendo 2515
    e confirma que `validar()` recusa — sem isso, a guarda do AC2 é
    decoração."""
    sem_psicologia = [
        e for e in importador.ESPECIALIDADES if e[2] != "2515"
    ]
    assert len(sem_psicologia) < len(importador.ESPECIALIDADES), (
        "pré-condição: a lista real precisa ter 2515 pra sabotagem remover algo"
    )
    monkeypatch.setattr(importador, "ESPECIALIDADES", sem_psicologia)
    with pytest.raises(AssertionError, match="2515"):
        importador.validar()


def test_validar_aceita_o_snapshot_real():
    importador.validar()  # não deve lançar


# ---------------------------------------------------------------------------
# AC3 — o arquivo declara fonte, versão, data e famílias incluídas
# ---------------------------------------------------------------------------

def test_catalogo_js_declara_fonte_versao_data_e_familias():
    txt = _CATALOGO_JS.read_text(encoding="utf-8")
    bloco = re.search(
        r"especialidadesFonte:\s*\{(.*?)\n  \},", txt, re.S
    )
    assert bloco, "bloco especialidadesFonte não encontrado em catalogos-encaminhamento.js"
    corpo = bloco.group(1)

    assert re.search(r'fonte:\s*"[^"]*CBO[^"]*"', corpo), "fonte CBO/MTE não declarada"
    assert re.search(r'versao:\s*"[^"]+"', corpo), "versão não declarada"
    assert re.search(r'data_snapshot:\s*"\d{4}-\d{2}-\d{2}"', corpo), "data_snapshot ausente/mal formatada"
    assert "familias_incluidas" in corpo, "famílias incluídas não declaradas"
    for familia in importador.FAMILIAS_INCLUIDAS:
        assert f'"{familia}"' in corpo, f"família {familia} não aparece em familias_incluidas"


# ---------------------------------------------------------------------------
# AC4 — o script de importação não é invocado por nenhum caminho de
# runtime/deploy (guarda de import/referência — R4/§2a)
# ---------------------------------------------------------------------------

def test_script_nao_e_importado_por_nenhum_arquivo_de_app():
    """Nenhum módulo de `app/` (o código que roda em runtime/deploy) importa
    ou referencia o importador. Só o script existir no repo não é a guarda —
    é ninguém no caminho de execução puxar ele."""
    nome_modulo = _SCRIPT.stem
    ofensores = []
    for py in _APP_DIR.rglob("*.py"):
        texto = py.read_text(encoding="utf-8")
        if nome_modulo in texto:
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


# ---------------------------------------------------------------------------
# Reprodutibilidade — rodar o script de novo, sem mudar os dados, produz o
# MESMO arquivo (a propriedade que prova que o gerado É o script)
# ---------------------------------------------------------------------------

def test_script_e_idempotente(tmp_path):
    original = _CATALOGO_JS.read_text(encoding="utf-8")
    try:
        proc1 = subprocess.run(
            [sys.executable, str(_SCRIPT)], cwd=str(_RAIZ),
            capture_output=True, text=True, timeout=30,
        )
        assert proc1.returncode == 0, proc1.stdout + proc1.stderr
        depois_1 = _CATALOGO_JS.read_text(encoding="utf-8")

        proc2 = subprocess.run(
            [sys.executable, str(_SCRIPT)], cwd=str(_RAIZ),
            capture_output=True, text=True, timeout=30,
        )
        assert proc2.returncode == 0, proc2.stdout + proc2.stderr
        depois_2 = _CATALOGO_JS.read_text(encoding="utf-8")

        assert depois_1 == depois_2, "rodar o importador duas vezes produziu arquivos diferentes"
    finally:
        _CATALOGO_JS.write_text(original, encoding="utf-8")
