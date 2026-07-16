"""
TICKET-UNIDADE-QUANTIDADE-VISIVEL — generalização (fecha a classe do defeito).

O bug original: seed_demo.py inseria `prescricao_itens` via SQL cru SEM a coluna
`unidade_quantidade` → NULL → o comprovante imprimia "21" sem dizer 21 de quê.

O caminho clínico (POST /prescricoes) SEMPRE exige `unidade_quantidade` — regra
CFM `campos_cfm_ausentes_no_item` (domain/assinatura.py). O seed escapava dessa
validação por escrever direto no banco.

Este teste aplica a MESMA regra do endpoint aos itens que o seed cria. Se o seed
voltar a gravar dado que a API rejeitaria, o gate fica vermelho.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from app.domain.assinatura import CAMPOS_CFM_ITEM, campos_cfm_ausentes_no_item
from tests.conftest import _init_schema


@pytest.fixture()
def seeded_conn(tmp_path):
    """DB temporário com o schema real + as personas/receita do seed_demo."""
    db_path = str(tmp_path / "seed_demo_test.db")
    _init_schema(db_path)

    import seed_demo

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        seed_demo._garantir_prescritor(
            conn, seed_demo.PRESCRITOR["cns"], seed_demo.PRESCRITOR["nome"]
        )
        seed_demo._garantir_paciente(
            conn, seed_demo.PACIENTE["cpf"], seed_demo.PACIENTE["nome"]
        )
        seed_demo._garantir_receita_na_fila(conn)
        conn.commit()
        yield conn
    finally:
        conn.close()


def _itens_semeados(conn) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT nome_medicamento, quantidade, unidade_quantidade, posologia "
        "FROM prescricao_itens ORDER BY id"
    ).fetchall()
    assert rows, "o seed deveria ter criado ao menos um item"
    return rows


def test_seed_nao_grava_unidade_quantidade_nula(seeded_conn):
    """Aceite Frente A: SELECT unidade_quantidade → sem NULL."""
    rows = _itens_semeados(seeded_conn)
    nulos = [r["nome_medicamento"] for r in rows if r["unidade_quantidade"] is None]
    assert not nulos, f"itens do seed com unidade_quantidade NULL: {nulos}"


def test_seed_satisfaz_regra_cfm_do_endpoint(seeded_conn):
    """
    Generalização: cada item do seed satisfaz `campos_cfm_ausentes_no_item` —
    a MESMA regra que o POST /prescricoes aplica. Impede o seed de reintroduzir
    dado que a API rejeitaria.
    """
    rows = _itens_semeados(seeded_conn)
    for r in rows:
        item = SimpleNamespace(**{campo: r[campo] for campo in CAMPOS_CFM_ITEM})
        ausentes = campos_cfm_ausentes_no_item(item)
        assert ausentes == [], (
            f"item '{r['nome_medicamento']}' viola a regra CFM do endpoint — "
            f"campos ausentes: {ausentes}"
        )
