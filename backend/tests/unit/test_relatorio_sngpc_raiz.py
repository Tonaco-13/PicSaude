"""
test_relatorio_sngpc_raiz.py — TICKET-R3-PROTOCOLO-RAIZ (lógica PURA).

Prova da walk R3 (CLAUDE.md §2a) que resolve a LINHAGEM-MÃE subindo
`origem_prescricao_id` até a raiz. Motor puro — sem DB, sem FastAPI:

  - REC-003 ← REC-002 ← REC-001 → protocolo_raiz = REC-001 nas 3 gerações
  - raiz (origem NULL) → protocolo_raiz == protocolo_prescricao
  - ciclo artificial → ValueError determinístico NOMEANDO a cadeia que fechou
  - memoização por-execução: cache fresco reflete a linhagem daquela chamada

ASSERÇÃO documentada: `origem_prescricao_id` é imutável pós-criação
(pré-check do arquiteto, main@2f510ed) — a linhagem é um DAG acíclico por
construção; o teste de ciclo exercita a guarda defensiva, não o fluxo normal.
"""
from __future__ import annotations

import pytest

from app.domain import relatorio_sngpc as sngpc


# --------------------------------------------------------------------------- helpers

def _linhagem(*nos) -> dict:
    """nos: tuplas (id, origem_id|None, protocolo)."""
    return {i: {"origem": o, "protocolo": p} for (i, o, p) in nos}


# --------------------------------------------------------------------------- walk pura

def test_raiz_de_cadeia_de_tres_geracoes():
    # REC-003 (id=3) ← REC-002 (id=2) ← REC-001 (id=1, raiz)
    linhagem = _linhagem(
        (1, None, "REC-001"),
        (2, 1, "REC-002"),
        (3, 2, "REC-003"),
    )
    cache: dict = {}
    assert sngpc.resolver_protocolo_raiz(3, linhagem, cache) == "REC-001"
    assert sngpc.resolver_protocolo_raiz(2, linhagem, cache) == "REC-001"
    assert sngpc.resolver_protocolo_raiz(1, linhagem, cache) == "REC-001"


def test_raiz_sem_origem_e_o_proprio_protocolo():
    linhagem = _linhagem((1, None, "REC-001"))
    assert sngpc.resolver_protocolo_raiz(1, linhagem, {}) == "REC-001"


def test_memoiza_todos_os_nos_do_caminho():
    """Uma única walk desde a folha deve popular o cache com todos os ancestrais."""
    linhagem = _linhagem(
        (1, None, "REC-001"),
        (2, 1, "REC-002"),
        (3, 2, "REC-003"),
    )
    cache: dict = {}
    sngpc.resolver_protocolo_raiz(3, linhagem, cache)
    assert cache == {1: "REC-001", 2: "REC-001", 3: "REC-001"}


# --------------------------------------------------------------------------- ciclo

def test_ciclo_falha_alto_nomeando_a_cadeia():
    # REC-001 → REC-002 → REC-001 (corrupção artificial: origens em círculo)
    linhagem = _linhagem(
        (1, 2, "REC-001"),
        (2, 1, "REC-002"),
    )
    with pytest.raises(ValueError) as exc:
        sngpc.resolver_protocolo_raiz(1, linhagem, {})

    msg = str(exc.value)
    assert "Ciclo detectado na linhagem" in msg
    # A mensagem nomeia os protocolos que fecham o ciclo (determinística).
    assert "REC-001" in msg and "REC-002" in msg
    assert "→" in msg


def test_ciclo_auto_referencia():
    # REC-001 aponta para si mesma.
    linhagem = _linhagem((1, 1, "REC-001"))
    with pytest.raises(ValueError) as exc:
        sngpc.resolver_protocolo_raiz(1, linhagem, {})
    assert "Ciclo detectado na linhagem: REC-001 → REC-001" == str(exc.value)


def test_linhagem_incompleta_falha_determinista():
    # id=2 referencia origem=99, ausente do mapa → erro claro, não KeyError cru.
    linhagem = _linhagem((2, 99, "REC-002"))
    with pytest.raises(ValueError) as exc:
        sngpc.resolver_protocolo_raiz(2, linhagem, {})
    assert "Linhagem incompleta" in str(exc.value)
    assert "99" in str(exc.value)


# --------------------------------------------------------------------------- integração no motor

def _mov_rows(prescricao_id, protocolo):
    """Uma dispensação mínima carregando prescricao_id (ponto de partida da walk)."""
    return [{
        "dispensacao_id": 1,
        "data_movimento": "2026-07-01T10:00:00",
        "item_id": 10,
        "prescricao_id": prescricao_id,
        "protocolo_prescricao": protocolo,
        "medicamento": "LOSARTANA",
        "dose": "50mg",
        "unidade_quantidade": "comprimido",
        "quantidade": 3,
        "lote": "L1",
        "fabricante": "FAB",
        "paciente_nome": "JOAO",
        "paciente_cpf": "11111111111",
        "comprador_nome": None,
        "comprador_documento": None,
        "prescritor_nome": "DRA MARIA",
        "prescritor_cns": "980001112223334",
        "status_item": "dispensado",
    }]


def test_construir_movimentos_projeta_protocolo_raiz():
    linhagem = _linhagem(
        (1, None, "REC-001"),
        (2, 1, "REC-002"),
        (3, 2, "REC-003"),
    )
    movs = sngpc.construir_movimentos(_mov_rows(3, "REC-003"), [], linhagem)
    assert len(movs) == 1
    assert movs[0]["protocolo_prescricao"] == "REC-003"
    assert movs[0]["protocolo_raiz"] == "REC-001"

    # E a coluna aparece no CSV logo após protocolo_prescricao.
    i = sngpc.CABECALHO_CSV.index("protocolo_raiz")
    assert sngpc.CABECALHO_CSV[i - 1] == "protocolo_prescricao"
    linha = sngpc.linha_csv(movs[0])
    assert linha[i] == "REC-001"


def test_sem_linhagem_raiz_e_o_proprio_protocolo():
    """Motor exercitado sem mapa (compat. com chamadas de 2 args) → self é raiz."""
    movs = sngpc.construir_movimentos(_mov_rows(3, "REC-003"), [])
    assert movs[0]["protocolo_raiz"] == "REC-003"


def test_memoizacao_e_por_execucao_nao_stale():
    """
    Duas 'gerações' do relatório com mapas de linhagem diferentes: cada chamada
    de construir_movimentos instancia cache fresco, então a 2ª enxerga a
    prescrição derivada nova. Prova que o cache não é global/stale.
    """
    # 1ª geração: só a raiz existe.
    linhagem_v1 = _linhagem((1, None, "REC-001"))
    movs1 = sngpc.construir_movimentos(_mov_rows(1, "REC-001"), [], linhagem_v1)
    assert movs1[0]["protocolo_raiz"] == "REC-001"

    # 2ª geração: nasceu REC-002 derivada de REC-001; o movimento agora é dela.
    linhagem_v2 = _linhagem((1, None, "REC-001"), (2, 1, "REC-002"))
    movs2 = sngpc.construir_movimentos(_mov_rows(2, "REC-002"), [], linhagem_v2)
    assert movs2[0]["protocolo_raiz"] == "REC-001"
    assert movs2[0]["protocolo_prescricao"] == "REC-002"
