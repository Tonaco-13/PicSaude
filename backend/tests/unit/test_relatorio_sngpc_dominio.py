"""
test_relatorio_sngpc_dominio.py — TICKET-F5, Fatia A (lógica PURA).

Prova determinística (timestamps controlados) das regras do domínio da
escrituração SNGPC do dispensador:
  §5.2 saldo corrido: dispensação + estorno → saldo reposto
  §5.7 ordenação determinística (DESC, estável entre execuções)
  §5.9 corte temporal: período fechado estável (estorno pós-data_fim não altera)
  §2.5 semântica comprador × paciente
  PG≠SQLite: normalizar_dt aceita datetime (PG) e string ISO (SQLite)
"""
from __future__ import annotations

from datetime import datetime

from app.domain import relatorio_sngpc as sngpc


def _disp(dispensacao_id, item_id, quantidade, data, **kw):
    base = {
        "dispensacao_id": dispensacao_id,
        "data_movimento": data,
        "item_id": item_id,
        "protocolo_prescricao": kw.get("protocolo", "PROTO-1"),
        "medicamento": kw.get("medicamento", "LOSARTANA"),
        "dose": "50mg",
        "unidade_quantidade": "comprimido",
        "quantidade": quantidade,
        "lote": "L1",
        "fabricante": "FAB",
        "paciente_nome": kw.get("paciente_nome", "JOAO"),
        "paciente_cpf": kw.get("paciente_cpf", "11111111111"),
        "comprador_nome": kw.get("comprador_nome"),
        "comprador_documento": kw.get("comprador_documento"),
        "prescritor_nome": "DRA MARIA",
        "prescritor_cns": "980001112223334",
        "status_item": kw.get("status_item", "dispensado"),
    }
    return base


def _est(estorno_id, origem_dispensacao_id, item_id, quantidade, data, **kw):
    return {
        "dispensacao_id": origem_dispensacao_id,
        "estorno_protocolo": kw.get("estorno_protocolo", f"EST-{estorno_id}"),
        "data_movimento": data,
        "item_id": item_id,
        "protocolo_prescricao": kw.get("protocolo", "PROTO-1"),
        "medicamento": kw.get("medicamento", "LOSARTANA"),
        "dose": "50mg",
        "unidade_quantidade": "comprimido",
        "quantidade": quantidade,
        "lote": "L1",
        "fabricante": "FAB",
        "paciente_nome": kw.get("paciente_nome", "JOAO"),
        "paciente_cpf": kw.get("paciente_cpf", "11111111111"),
        "comprador_nome": kw.get("comprador_nome"),
        "comprador_documento": kw.get("comprador_documento"),
        "prescritor_nome": "DRA MARIA",
        "prescritor_cns": "980001112223334",
        "motivo_estorno": kw.get("motivo", "outro"),
        "status_item": kw.get("status_item", "dispensado"),
        "estorno_id": estorno_id,
    }


# --------------------------------------------------------------------------- §5.2

def test_saldo_corrido_dispensacao_e_estorno_reposto():
    disp = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00")
    est = _est(1, origem_dispensacao_id=1, item_id=10, quantidade=3, data="2026-07-02T10:00:00")

    movs = sngpc.construir_movimentos([disp], [est])
    por_tipo = {m["tipo_movimento"]: m for m in movs}

    # Na dispensação: saldo = +3. No estorno: saldo reposto a 0 (Σdisp − Σest).
    assert por_tipo["dispensacao"]["saldo_efetivo_item"] == 3
    assert por_tipo["estorno"]["saldo_efetivo_item"] == 0


def test_saldo_corrido_estorno_parcial():
    disp = _disp(1, item_id=10, quantidade=5, data="2026-07-01T10:00:00")
    est = _est(1, origem_dispensacao_id=1, item_id=10, quantidade=2, data="2026-07-02T10:00:00")
    movs = sngpc.construir_movimentos([disp], [est])
    por_tipo = {m["tipo_movimento"]: m for m in movs}
    assert por_tipo["dispensacao"]["saldo_efetivo_item"] == 5
    assert por_tipo["estorno"]["saldo_efetivo_item"] == 3   # 5 − 2


def test_saldo_por_item_independente():
    d1 = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00")
    d2 = _disp(2, item_id=20, quantidade=7, data="2026-07-01T11:00:00")
    movs = sngpc.construir_movimentos([d1, d2], [])
    saldo = {m["dispensacao_id"]: m["saldo_efetivo_item"] for m in movs}
    assert saldo[1] == 3 and saldo[2] == 7   # itens distintos não se somam


# --------------------------------------------------------------------------- §5.9

def test_corte_temporal_periodo_fechado_estavel():
    """Estorno registrado DEPOIS do data_fim não altera a linha da dispensação
    dentro do período — relatório de período fechado é estável para sempre."""
    disp = _disp(1, item_id=10, quantidade=3, data="2026-01-10T10:00:00")
    est_futuro = _est(1, origem_dispensacao_id=1, item_id=10, quantidade=3,
                      data="2026-06-20T10:00:00")

    movs = sngpc.construir_movimentos([disp], [est_futuro])

    # Janela fechada em janeiro — o estorno de junho fica fora da exibição.
    dt_ini = datetime(2026, 1, 1)
    dt_fim = datetime(2026, 1, 31, 23, 59, 59)
    exib = sngpc.ordenar_exibicao(sngpc.filtrar_periodo(movs, dt_ini, dt_fim))

    assert len(exib) == 1
    assert exib[0]["tipo_movimento"] == "dispensacao"
    # Saldo da linha = 3 (só considera movimentos ≤ a data da linha; o estorno
    # de junho é posterior e não entra no corte).
    assert exib[0]["saldo_efetivo_item"] == 3


def test_corte_temporal_saldo_da_linha_ignora_futuro():
    """Mesmo com o estorno visível numa janela ampla, a LINHA da dispensação
    mantém o saldo da sua própria data (não é retroativamente alterada)."""
    disp = _disp(1, item_id=10, quantidade=3, data="2026-01-10T10:00:00")
    est = _est(1, origem_dispensacao_id=1, item_id=10, quantidade=3, data="2026-06-20T10:00:00")
    movs = sngpc.construir_movimentos([disp], [est])
    exib = sngpc.ordenar_exibicao(movs)   # janela ampla (sem filtro)
    por_tipo = {m["tipo_movimento"]: m for m in exib}
    assert por_tipo["dispensacao"]["saldo_efetivo_item"] == 3   # inalterado
    assert por_tipo["estorno"]["saldo_efetivo_item"] == 0


# --------------------------------------------------------------------------- §5.7

def test_ordenacao_desc_e_deterministica():
    d1 = _disp(1, item_id=10, quantidade=1, data="2026-07-01T10:00:00")
    d2 = _disp(2, item_id=11, quantidade=1, data="2026-07-03T10:00:00")
    d3 = _disp(3, item_id=12, quantidade=1, data="2026-07-02T10:00:00")
    movs = sngpc.construir_movimentos([d1, d2, d3], [])

    ordem1 = [m["dispensacao_id"] for m in sngpc.ordenar_exibicao(movs)]
    ordem2 = [m["dispensacao_id"] for m in sngpc.ordenar_exibicao(movs)]
    assert ordem1 == ordem2                      # estável entre execuções
    assert ordem1 == [2, 3, 1]                   # DESC por data_movimento


def test_ordenacao_dispensacao_antes_do_estorno_na_cronologia():
    """Em ordem ascendente (saldo), a dispensação precede seu estorno."""
    disp = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00")
    est = _est(1, origem_dispensacao_id=1, item_id=10, quantidade=3, data="2026-07-02T10:00:00")
    movs = sngpc.construir_movimentos([disp], [est])   # já ascendente
    assert [m["tipo_movimento"] for m in movs] == ["dispensacao", "estorno"]


# --------------------------------------------------------------------------- §2.5

def test_comprador_declarado():
    disp = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00",
                 comprador_nome="MARIA PORTADORA", comprador_documento="22222222222")
    m = sngpc.construir_movimentos([disp], [])[0]
    assert m["comprador_nome"] == "MARIA PORTADORA"
    assert m["comprador_documento"] == "22222222222"
    assert m["comprador_eh_paciente"] is False


def test_comprador_ausente_eh_paciente():
    disp = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00",
                 paciente_nome="JOAO", paciente_cpf="11111111111")
    m = sngpc.construir_movimentos([disp], [])[0]
    assert m["comprador_nome"] == "JOAO"
    assert m["comprador_documento"] == "11111111111"
    assert m["comprador_eh_paciente"] is True


# --------------------------------------------------------------------------- projeção CSV

def test_linha_csv_alinha_com_cabecalho():
    disp = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00")
    m = sngpc.construir_movimentos([disp], [])[0]
    linha = sngpc.linha_csv(m)
    assert len(linha) == len(sngpc.CABECALHO_CSV)


def test_linha_csv_flag_comprador_texto():
    disp_pac = _disp(1, item_id=10, quantidade=3, data="2026-07-01T10:00:00")
    disp_dec = _disp(2, item_id=11, quantidade=3, data="2026-07-01T10:00:00",
                     comprador_nome="MARIA")
    idx = sngpc.CABECALHO_CSV.index("comprador_eh_paciente")
    assert sngpc.linha_csv(sngpc.construir_movimentos([disp_pac], [])[0])[idx] == "sim"
    assert sngpc.linha_csv(sngpc.construir_movimentos([disp_dec], [])[0])[idx] == "nao"


def test_csv_nao_tem_coluna_de_endereco():
    """§5.5 / §2.4 — nenhuma coluna de endereço na escrituração."""
    assert not any("endereco" in c.lower() or "end_" in c.lower()
                   for c in sngpc.CABECALHO_CSV)


# --------------------------------------------------------------------------- PG≠SQLite

def test_normalizar_dt_aceita_datetime_e_string():
    dt_obj = datetime(2026, 7, 1, 10, 0, 0)              # PostgreSQL
    dt_str = "2026-07-01T10:00:00"                       # SQLite (ISO)
    assert sngpc.normalizar_dt(dt_obj) == dt_obj
    assert sngpc.normalizar_dt(dt_str) == dt_obj
    assert sngpc.normalizar_dt(None) is None


def test_normalizar_dt_remove_timezone():
    from datetime import timezone
    dt_aware = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    out = sngpc.normalizar_dt(dt_aware)
    assert out.tzinfo is None
    assert out == datetime(2026, 7, 1, 10, 0, 0)
