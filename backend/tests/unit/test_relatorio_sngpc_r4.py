"""
test_relatorio_sngpc_r4.py — TICKET-R4-ESCRITURACAO-REGULATORIA (lógica PURA).

Prova que o relatório SNGPC PROJETA a identidade regulatória congelada no
movimento (CLAUDE.md §2a R4), sem re-resolver na leitura:

  - `grupo_regulatorio_id` é coluna do CSV, junto do bloco do medicamento
  - dispensação de item controlado → o grupo congelado aparece na linha
  - item não-controlado (grupo None) → coluna vazia (NUNCA inventa)
  - estorno herda o grupo da dispensação de origem
"""
from __future__ import annotations

from app.domain import relatorio_sngpc as sngpc


def _disp(dispensacao_id, item_id, quantidade, data, grupo=None, **kw):
    return {
        "dispensacao_id": dispensacao_id,
        "data_movimento": data,
        "item_id": item_id,
        "protocolo_prescricao": kw.get("protocolo", "PROTO-1"),
        "medicamento": kw.get("medicamento", "CLONAZEPAM"),
        "dose": "2mg",
        "unidade_quantidade": "comprimido",
        "grupo_regulatorio_id": grupo,
        "quantidade": quantidade,
        "lote": "L1",
        "fabricante": "FAB",
        "paciente_nome": "JOAO",
        "paciente_cpf": "11111111111",
        "comprador_nome": None,
        "comprador_documento": None,
        "prescritor_nome": "DRA MARIA",
        "prescritor_cns": "980001112223334",
        "status_item": "dispensado",
    }


def _est(estorno_id, origem_dispensacao_id, item_id, quantidade, data, grupo=None):
    return {
        "dispensacao_id": origem_dispensacao_id,
        "estorno_protocolo": f"EST-{estorno_id}",
        "data_movimento": data,
        "item_id": item_id,
        "protocolo_prescricao": "PROTO-1",
        "medicamento": "CLONAZEPAM",
        "dose": "2mg",
        "unidade_quantidade": "comprimido",
        "grupo_regulatorio_id": grupo,
        "quantidade": quantidade,
        "lote": "L1",
        "fabricante": "FAB",
        "paciente_nome": "JOAO",
        "paciente_cpf": "11111111111",
        "comprador_nome": None,
        "comprador_documento": None,
        "prescritor_nome": "DRA MARIA",
        "prescritor_cns": "980001112223334",
        "motivo_estorno": "erro_operacional",
        "status_item": "estornado",
        "estorno_id": estorno_id,
    }


def test_grupo_regulatorio_e_coluna_do_csv_junto_do_medicamento():
    i = sngpc.CABECALHO_CSV.index("grupo_regulatorio_id")
    # Bloco do medicamento/controle: logo após unidade_quantidade, antes da quantidade.
    assert sngpc.CABECALHO_CSV[i - 1] == "unidade_quantidade"
    assert sngpc.CABECALHO_CSV[i + 1] == "quantidade"


def test_dispensacao_controlada_projeta_grupo_congelado():
    m = sngpc.construir_movimentos(
        [_disp(1, 10, 5, "2026-07-17T10:00:00", grupo="notificacao_receita_b")], []
    )[0]
    idx = sngpc.CABECALHO_CSV.index("grupo_regulatorio_id")
    assert sngpc.linha_csv(m)[idx] == "notificacao_receita_b"


def test_dispensacao_nao_controlada_projeta_vazio():
    """grupo None → coluna vazia; nunca 'receita_simples' nem placeholder."""
    m = sngpc.construir_movimentos(
        [_disp(2, 11, 5, "2026-07-17T10:00:00", grupo=None)], []
    )[0]
    idx = sngpc.CABECALHO_CSV.index("grupo_regulatorio_id")
    assert sngpc.linha_csv(m)[idx] == ""


def test_estorno_herda_grupo_da_origem():
    movs = sngpc.construir_movimentos(
        [_disp(3, 12, 5, "2026-07-17T10:00:00", grupo="notificacao_receita_b")],
        [_est(9, 3, 12, 2, "2026-07-17T11:00:00", grupo="notificacao_receita_b")],
    )
    idx = sngpc.CABECALHO_CSV.index("grupo_regulatorio_id")
    for m in movs:
        assert sngpc.linha_csv(m)[idx] == "notificacao_receita_b"
