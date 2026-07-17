"""
test_relatorio_dispensacoes_csv.py
===================================
Testes do relatório de dispensações para auditoria (routers/relatorios.py).

CSV e PDF são duas projeções da MESMA query (``_SQL_BASE``). O defeito que
originou este arquivo: a query selecionava ``unidade_quantidade``, o PDF
renderizava, e o CSV — o formato que o auditor efetivamente leva — omitia.
Resultado: "21" pelado no lugar mais consequente, e duas projeções divergentes
saindo da mesma fonte.

COBERTURA
---------
  1.  Paridade CSV↔PDF: todo campo projetado no PDF tem coluna no CSV
  2.  CSV traz unidade_quantidade preenchida
  3.  Item legado (unidade NULL) → célula vazia, sem unidade inventada
  4.  Ordem das colunas de quantidade espelha o PDF
"""
from __future__ import annotations

import csv
import io

import pytest

from tests.conftest import RoleClient

from app.domain.pdf_relatorio_dispensacoes import _CAMPOS as _CAMPOS_PDF
from app.routers.relatorios import _CABECALHO as _CABECALHO_CSV


_BASE = {
    "cns_prescritor":  "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente":    "12345678901",
    "nome_paciente":   "Paciente Teste",
    "tipo_emissao":    "nova",
}

_ITEM_COM_UNIDADE = {
    "nome_medicamento":   "AMOXICILINA",
    "concentracao":       "500mg",
    "quantidade":         21,
    "unidade_quantidade": "cápsula",
    "posologia":          "1 cápsula 3x ao dia",
}

# Item legado: emitido antes do vocabulário de unidades — unidade_quantidade NULL.
_ITEM_SEM_UNIDADE = {
    "nome_medicamento": "DIPIRONA",
    "concentracao":     "500mg",
    "quantidade":       10,
    "posologia":        "1 comprimido 6/6h",
}

_DISPENSA = {
    "cnpj_estabelecimento":  "12345678000195",
    "quantidade_dispensada": 21,
    "dispensado_por":        "Farmaceutico Teste",
}


@pytest.fixture()
def auditor(_shared_client):
    return RoleClient(_shared_client, "auditor")


def _item_ids(db_path: str, proto: str) -> list[int]:
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT i.id FROM prescricao_itens i "
        "JOIN prescricoes p ON p.id = i.prescricao_id "
        "WHERE p.protocolo = ? ORDER BY i.id",
        (proto,),
    ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


def _emitir_e_dispensar(prescritor, dispensador, db_path, item, quantidade) -> None:
    """
    Emite pela API (produz paciente/prescritor/item reais) e semeia a
    ``dispensacao`` direto no banco. A cadeia de custódia/retenção não é o
    objeto sob teste aqui — o que interessa é a projeção da query no CSV.
    """
    import sqlite3

    r = prescritor.post("/prescricoes", json={**_BASE, "itens": [item]})
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    item_id = _item_ids(db_path, proto)[0]

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO dispensacoes "
        "(prescricao_item_id, cnpj_estabelecimento, quantidade_dispensada, "
        " dispensado_por, dispensado_em, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            item_id,
            _DISPENSA["cnpj_estabelecimento"],
            quantidade,
            _DISPENSA["dispensado_por"],
            "2026-07-10T10:00:00",
            "2026-07-10T10:00:00",
        ),
    )
    conn.commit()
    conn.close()


def _linhas_csv(auditor) -> list[dict]:
    r = auditor.get("/relatorios/dispensacoes.csv")
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.text)))


# ===========================================================================
# 1. Paridade CSV↔PDF — o contrato, não a instância
# ===========================================================================

class TestParidadeCsvPdf:
    """
    CSV e PDF projetam a mesma query. O CSV é o formato completo (carrega
    campos que não cabem na página A4: ids, comprador, status, tipo_emissao),
    então a relação é de superconjunto — mas nenhum campo que o PDF mostra
    ao auditor pode faltar no CSV que o auditor arquiva.
    """

    def test_todo_campo_do_pdf_tem_coluna_no_csv(self):
        ausentes = [c for c in _CAMPOS_PDF if c not in _CABECALHO_CSV]
        assert not ausentes, (
            f"Campos projetados no PDF e ausentes no CSV: {ausentes}. "
            f"CSV e PDF saem da mesma query — divergir é defeito."
        )

    def test_unidade_quantidade_esta_nas_duas_projecoes(self):
        assert "unidade_quantidade" in _CAMPOS_PDF
        assert "unidade_quantidade" in _CABECALHO_CSV

    def test_unidade_segue_as_quantidades_como_no_pdf(self):
        """A unidade qualifica a quantidade — vem logo depois dela, nos dois."""
        for colunas in (_CAMPOS_PDF, _CABECALHO_CSV):
            i = colunas.index("unidade_quantidade")
            assert colunas[i - 1] == "quantidade_dispensada"
            assert colunas[i - 2] == "quantidade_prescrita"


# ===========================================================================
# 2. Projeção do dado no CSV
# ===========================================================================

class TestUnidadeNoCsv:

    def test_csv_traz_unidade_preenchida(self, prescritor, dispensador, auditor, db_path):
        _emitir_e_dispensar(prescritor, dispensador, db_path, _ITEM_COM_UNIDADE, 21)

        linhas = _linhas_csv(auditor)
        assert len(linhas) == 1
        linha = linhas[0]

        assert linha["quantidade_dispensada"] == "21"
        assert linha["unidade_quantidade"] == "cápsula"

    def test_item_legado_gera_celula_vazia(self, prescritor, dispensador, auditor, db_path):
        """
        Ausência de unidade é ausência — nunca "unidade" inventada.
        O relatório de auditoria não afirma o que o prescritor não declarou.
        """
        _emitir_e_dispensar(prescritor, dispensador, db_path, _ITEM_SEM_UNIDADE, 10)

        linha = _linhas_csv(auditor)[0]

        assert linha["unidade_quantidade"] == ""

    def test_cabecalho_do_csv_declara_a_coluna(self, auditor):
        r = auditor.get("/relatorios/dispensacoes.csv")
        assert r.status_code == 200
        cabecalho = next(csv.reader(io.StringIO(r.text)))
        assert "unidade_quantidade" in cabecalho
