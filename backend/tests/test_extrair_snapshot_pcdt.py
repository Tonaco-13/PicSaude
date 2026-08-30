"""
test_extrair_snapshot_pcdt.py — Onda PCDT, Camada 1 (o extrator).

Cobre a lógica pura de texto (localizador de quadro com pista de título,
os dois normalizadores, as duas estratégias de fatiamento, a derivação de
variante de qualificador de insulina) com fixtures SINTÉTICAS — nenhuma
dessas funções toca pypdf/arquivo, todas recebem `list[str]` de páginas
já extraídas, então testam sem depender do corpus real. A guarda de
ferramenta offline e os testes sobre o corpus real (se estagiado
localmente) seguem o mesmo padrão dos importadores CID/RDC/CBO/SIGTAP.
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = _RAIZ / "backend" / "scripts" / "extrair_snapshot_pcdt.py"
_APP_DIR = _RAIZ / "backend" / "app"
_DECISAO_SEMAFORO_CSV = _RAIZ / "data" / "decisao_semaforo.csv"
_POSOLOGIA_SUGERIDA_CSV = _RAIZ / "data" / "posologia_sugerida.csv"

sys.path.insert(0, str(_RAIZ / "backend" / "scripts"))
import extrair_snapshot_pcdt as extrator  # noqa: E402


# ---------------------------------------------------------------------------
# Normalizadores
# ---------------------------------------------------------------------------

def test_normalizar_preservando_indice_mesmo_comprimento():
    for s in ["Insulina análoga de ação rápida", "Cloridrato de Metformina", "iSGLT2"]:
        assert len(extrator._normalizar_preservando_indice(s)) == len(s)


def test_normalizar_preservando_indice_sem_acento_nem_caixa():
    assert extrator._normalizar_preservando_indice("AÇÃO") == "acao"


def test_normalizar_colapsa_espaco():
    assert extrator._normalizar("insulina    NPH\n\n") == "insulina nph"


# ---------------------------------------------------------------------------
# Extração de portaria (capa)
# ---------------------------------------------------------------------------

def test_extrair_portaria_acha_na_capa():
    paginas = ["Ministério da Saúde\nPORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026\nAprova o PCDT", "resto"]
    assert extrator._extrair_portaria(paginas) == "PORTARIA SCTIE/MS Nº 13, DE 21 DE FEVEREIRO DE 2026"


def test_extrair_portaria_conjunta():
    paginas = ["PORTARIA CONJUNTA SAES/SCTIE Nº 43, DE 24 DE MARÇO DE 2026\ntexto"]
    achado = extrator._extrair_portaria(paginas)
    assert achado is not None and "CONJUNTA" in achado


def test_extrair_portaria_ausente_retorna_none():
    assert extrator._extrair_portaria(["nada aqui", "nem aqui"]) is None


# ---------------------------------------------------------------------------
# Localizador de quadro — protege contra artefato de reflow
# ---------------------------------------------------------------------------

def test_localizar_quadro_acha_com_pista_de_titulo():
    paginas = ["ruído", "texto antes Quadro 15. Esquemas de administração de medicamentos: tabela aqui", "resto"]
    achado = extrator._localizar_quadro(paginas, 15, "esquemas de administração")
    assert achado is not None
    pagina, idx = achado
    assert pagina == 1
    assert paginas[pagina][idx:idx + 9] == "Quadro 15"


def test_localizar_quadro_rejeita_artefato_de_reflow():
    """'Quadro 634.' (dígito de rodapé colado) não deve confundir a busca
    por 'Quadro 6' sem que o título bata — replica o achado real do
    corpus (DM2 p.13, Asma p.38)."""
    paginas = [
        "nota de rodapé aleatória Quadro 634. Valores de HbA1c não relacionados",
        "texto Quadro 6. Metas terapêuticas glicêmicas conforme perfil do paciente",
    ]
    achado = extrator._localizar_quadro(paginas, 6, "metas terapêuticas")
    assert achado is not None
    assert achado[0] == 1  # achou na página certa, não no artefato da página 0


def test_localizar_quadro_ausente_retorna_none():
    assert extrator._localizar_quadro(["nada"], 99, "pista qualquer") is None


# ---------------------------------------------------------------------------
# Estratégia A — fatiamento por dicionário (E11-style)
# ---------------------------------------------------------------------------

def test_fatiar_por_dicionario_basico():
    texto = (
        "Quadro 15 Medicamento Dose Frequência Biguanidas Metformina "
        "500 mg 2 vezes Sulfonilureias Glibenclamida 5 mg 1 vez"
    )
    dicionario = ["Metformina", "Glibenclamida"]
    linhas, sobra = extrator._fatiar_por_dicionario(texto, dicionario)
    assert [l["principio_ativo"] for l in linhas] == ["Metformina", "Glibenclamida"]
    assert "500 mg" in linhas[0]["posologia_bruta"]
    assert "5 mg" in linhas[1]["posologia_bruta"]
    # `sobra` é o texto após a última âncora — por design, o MESMO texto
    # já capturado como posologia_bruta da última row (não há âncora
    # seguinte pra delimitar onde ela termina). Não é "não classificado";
    # extrair_e11 só trata isso como gap quando `linhas` vem vazio.
    assert sobra == linhas[-1]["posologia_bruta"]


def test_fatiar_por_dicionario_nome_ausente_nao_gera_row():
    texto = "Quadro 15 Metformina 500 mg 2 vezes"
    linhas, _ = extrator._fatiar_por_dicionario(texto, ["Metformina", "Sitagliptina"])
    nomes = [l["principio_ativo"] for l in linhas]
    assert nomes == ["Metformina"]
    assert "Sitagliptina" not in nomes


def test_fatiar_por_dicionario_usa_variante_de_busca_mas_reporta_nome_canonico():
    texto = "Insulina humana NPH Dose inicial 0,2 U/kg/dia"
    variantes = {"insulina NPH": "insulina humana NPH"}
    linhas, _ = extrator._fatiar_por_dicionario(texto, ["insulina NPH"], variantes)
    assert len(linhas) == 1
    assert linhas[0]["principio_ativo"] == "insulina NPH"  # canônico, não a variante
    assert "0,2 U/kg" in linhas[0]["posologia_bruta"]


# ---------------------------------------------------------------------------
# Variantes de qualificador de insulina — derivação mecânica, não hardcode
# ---------------------------------------------------------------------------

def test_variante_insulina_so_aparece_quando_forma_literal_falta():
    dicionario = ["insulina NPH", "metformina"]
    texto = "Insulina humana NPH dose tal. Metformina 500mg."
    variantes = extrator._variantes_qualificador_insulina(dicionario, texto)
    assert variantes == {"insulina NPH": "insulina humana NPH"}
    assert "metformina" not in variantes  # não é insulina — não entra na checagem


def test_variante_insulina_nao_gerada_se_forma_literal_ja_bate():
    dicionario = ["insulina NPH"]
    texto = "Insulina NPH dose tal (sem qualificador)."
    assert extrator._variantes_qualificador_insulina(dicionario, texto) == {}


def test_variante_insulina_nao_gerada_se_nem_a_variante_bate():
    dicionario = ["insulina NPH"]
    texto = "Nenhuma menção a essa insulina aqui."
    assert extrator._variantes_qualificador_insulina(dicionario, texto) == {}


def test_variante_insulina_ignora_termos_ja_qualificados():
    """'insulina análoga...' já tem qualificador — não tenta duplicar
    'humana' no meio."""
    dicionario = ["insulina análoga de ação rápida"]
    texto = "nada relevante aqui"
    assert extrator._variantes_qualificador_insulina(dicionario, texto) == {}


# ---------------------------------------------------------------------------
# Classes de insulina análoga — derivadas do próprio Quadro 18
# ---------------------------------------------------------------------------

def test_extrair_classes_insulina_analoga_deriva_do_texto():
    texto_q18 = "Recomendações: Insulina análoga de ação rápida e Insulina análoga de ação prolongada estão incorporadas."
    achados = extrator._extrair_classes_insulina_analoga(texto_q18)
    assert achados == ["Insulina análoga de ação rápida", "Insulina análoga de ação prolongada"]


def test_extrair_classes_insulina_analoga_vazio_sem_mencao():
    assert extrator._extrair_classes_insulina_analoga("nada sobre insulina aqui") == []


# ---------------------------------------------------------------------------
# Estratégia B — fatiamento por marcador de bullet (J45-style)
# ---------------------------------------------------------------------------

def test_fatiar_por_marcadores_bullets():
    texto = (
        "- Salbutamol: dose de 4 a 10 jatos a cada 20 minutos. "
        "- Mepolizumabe: 100 mg por via subcutânea a cada 4 semanas."
    )
    linhas = extrator._fatiar_por_marcadores(texto, extrator._RE_BULLET_MEDICAMENTO)
    assert [n for n, _ in linhas] == ["Salbutamol", "Mepolizumabe"]
    assert "4 a 10 jatos" in dict(linhas)["Salbutamol"]
    assert "100 mg" in dict(linhas)["Mepolizumabe"]


def test_fatiar_por_marcadores_sem_bullet_retorna_vazio():
    assert extrator._fatiar_por_marcadores("prosa contínua sem marcador algum", extrator._RE_BULLET_MEDICAMENTO) == []


# ---------------------------------------------------------------------------
# extrair_e11 / extrair_j45 — integração com páginas sintéticas
# ---------------------------------------------------------------------------

def _csv_semaforo_sintetico(tmp_path: Path) -> Path:
    caminho = tmp_path / "decisao_semaforo.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo_cid", "condicao", "principio_ativo", "fonte"])
        w.writerow(["E11", "Diabetes mellitus tipo 2", "metformina", "teste"])
        w.writerow(["E11", "Diabetes mellitus tipo 2", "insulina NPH", "teste"])
    return caminho


def test_extrair_e11_com_paginas_sinteticas(tmp_path, monkeypatch):
    monkeypatch.setattr(extrator, "_DECISAO_SEMAFORO_CSV", _csv_semaforo_sintetico(tmp_path))
    paginas = [""] * 20
    paginas[14] = (
        "Quadro 15. Esquemas de administração dos medicamentos Metformina 500 mg "
        "2 vezes Insulina humana NPH Dose inicial 0,2 U/kg/dia 1 vez 8.9. Contraindicações"
    )
    paginas[17] = "Quadro 18. Recomendações para o gestor: Metformina, Insulina humana NPH estão incorporadas."
    rows, gaps = extrator.extrair_e11(paginas, "PORTARIA TESTE Nº 1, DE 1 DE JANEIRO DE 2026")
    nomes = {r["principio_ativo"] for r in rows}
    assert nomes == {"metformina", "insulina NPH"}
    assert all(r["status_curadoria"] == "rascunho" for r in rows)
    assert any("variante" in g for g in gaps)  # a variante de NPH deve ser reportada


def test_extrair_e11_quadro_ausente_vira_gap_nao_excecao(tmp_path, monkeypatch):
    monkeypatch.setattr(extrator, "_DECISAO_SEMAFORO_CSV", _csv_semaforo_sintetico(tmp_path))
    rows, gaps = extrator.extrair_e11(["nada de quadro aqui"], "PORTARIA X")
    assert rows == []
    assert any("Quadro 15" in g for g in gaps)


def test_extrair_j45_com_paginas_sinteticas():
    paginas = [""] * 40
    paginas[37] = (
        "7.4.1. Esquemas de administração - Salbutamol: 4 a 10 jatos a cada 20 minutos. "
        "- Mepolizumabe: 100 mg subcutâneo a cada 4 semanas."
    )
    paginas[38] = "7.4.2. Critérios de interrupção: texto irrelevante"
    rows, gaps = extrator.extrair_j45(paginas, "PORTARIA TESTE Nº 2, DE 1 DE JANEIRO DE 2026")
    nomes = {r["principio_ativo"] for r in rows}
    assert nomes == {"Salbutamol", "Mepolizumabe"}
    assert all(r["status_curadoria"] == "rascunho" for r in rows)
    assert all(r["linha"] == "" for r in rows)  # documentado: 7.4.1 não rotula linha
    assert gaps == []


def test_extrair_j45_secao_ausente_vira_gap():
    rows, gaps = extrator.extrair_j45(["nada de 7.4.1 aqui"], "PORTARIA X")
    assert rows == []
    assert any("7.4.1" in g for g in gaps)


# ---------------------------------------------------------------------------
# AC iv — nunca escreve nos arquivos de curadoria assinada
# ---------------------------------------------------------------------------

def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_script_nunca_escreve_em_decisao_semaforo_ou_posologia_sugerida():
    if not (_DECISAO_SEMAFORO_CSV.exists() and _POSOLOGIA_SUGERIDA_CSV.exists()):
        import pytest
        pytest.skip("arquivos de curadoria não presentes neste checkout")
    antes = {
        _DECISAO_SEMAFORO_CSV: _sha256(_DECISAO_SEMAFORO_CSV),
        _POSOLOGIA_SUGERIDA_CSV: _sha256(_POSOLOGIA_SUGERIDA_CSV),
    }
    if extrator._CORPUS.exists():
        extrator.main()
    depois = {
        _DECISAO_SEMAFORO_CSV: _sha256(_DECISAO_SEMAFORO_CSV),
        _POSOLOGIA_SUGERIDA_CSV: _sha256(_POSOLOGIA_SUGERIDA_CSV),
    }
    assert antes == depois


def test_fonte_do_script_nao_abre_arquivos_de_curadoria_em_modo_escrita():
    """Guarda estática: nenhuma chamada `open(..., "w")` no arquivo do
    script referencia os dois CSVs de curadoria assinada."""
    fonte = _SCRIPT.read_text(encoding="utf-8")
    for proibido in ("decisao_semaforo", "posologia_sugerida"):
        for linha in fonte.splitlines():
            if proibido in linha:
                assert '"w"' not in linha and "'w'" not in linha, (
                    f"linha suspeita de escrita em {proibido}: {linha!r}"
                )


# ---------------------------------------------------------------------------
# Idempotência e execução sobre o corpus real — só roda se estagiado
# ---------------------------------------------------------------------------

def test_main_e_idempotente_sobre_corpus_real():
    if not extrator._CORPUS.exists():
        import pytest
        pytest.skip("corpus PCDT não estagiado localmente (data/fontes-oficiais/pcdt/)")
    extrator.main()
    csv_e11_1 = (extrator._SAIDA_DIR / "pcdt_e11_rascunho.csv").read_text(encoding="utf-8")
    csv_j45_1 = (extrator._SAIDA_DIR / "pcdt_j45_rascunho.csv").read_text(encoding="utf-8")
    extrator.main()
    csv_e11_2 = (extrator._SAIDA_DIR / "pcdt_e11_rascunho.csv").read_text(encoding="utf-8")
    csv_j45_2 = (extrator._SAIDA_DIR / "pcdt_j45_rascunho.csv").read_text(encoding="utf-8")
    assert csv_e11_1 == csv_e11_2
    assert csv_j45_1 == csv_j45_2


def test_main_sobre_corpus_real_produz_status_rascunho_sempre():
    if not extrator._CORPUS.exists():
        import pytest
        pytest.skip("corpus PCDT não estagiado localmente (data/fontes-oficiais/pcdt/)")
    extrator.main()
    for nome in ("pcdt_e11_rascunho.csv", "pcdt_j45_rascunho.csv"):
        with open(extrator._SAIDA_DIR / nome, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        assert linhas, f"{nome} veio vazio"
        assert all(l["status_curadoria"] == "rascunho" for l in linhas)
        assert all(l["citacao"] for l in linhas)  # AC i — toda row tem citação


# ---------------------------------------------------------------------------
# AC v — ferramenta offline, nunca em runtime/deploy
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
            f"{nome_modulo} referenciado em {candidato} — extrator é ferramenta "
            "offline, nunca roda em deploy (R4/§2a)"
        )
