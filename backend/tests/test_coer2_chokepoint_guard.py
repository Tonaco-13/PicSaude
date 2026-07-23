"""
tests/test_coer2_chokepoint_guard.py
====================================

Guarda executável do choke-point de posse (TICKET-COERENCIA-DEVOLUCOES-2, §8).
Roda no gate SEM PostgreSQL — é invariante de código, não de dados. A guarda de
BANCO (constraint de unicidade) é testada em
`tests/integration/test_custodia_devolucao.py::test_guarda_unicidade_custodia_ativa`.

Lição do R2 (§2a): invariante executável, não memória de revisor. Se um 6º caminho
de posse voltar a fazer `_fechar_custodia_ativa` + `_abrir_custodia` à mão numa
linha, o gate acusa — em vez de ser caçado depois.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.domain.states import (
    ESTADOS_PRESCRICAO,
    ESTADOS_TERMINAIS_PRESCRICAO,
    TRANSICOES_PRESCRICAO,
    EVENTOS_PRESCRICAO,
    transicao_valida_prescricao,
)

_ROUTERS = Path(__file__).resolve().parent.parent / "app" / "routers"
_ARQS_POSSE = ("custodia.py", "auth.py", "dispensacoes.py")

# Padrão do anti-caminho: fecha + abre na MESMA linha (o grep literal do §8).
_ANTIPATTERN = re.compile(r"_fechar_custodia_ativa.*_abrir_custodia")


def _linhas_de_codigo(texto: str):
    """Ignora linhas de comentário/docstring (que só *mencionam* as funções)."""
    for i, linha in enumerate(texto.splitlines(), 1):
        strip = linha.strip()
        if strip.startswith("#"):
            continue
        if "`" in linha:  # menção em docstring usa backticks
            continue
        yield i, linha


# --- §8: nenhum caminho faz fecha+abre à mão (fora do choke-point) ------------

def test_nenhum_fecha_abre_na_mesma_linha_fora_do_helper():
    ofensores = []
    for nome in _ARQS_POSSE:
        arq = _ROUTERS / nome
        for i, linha in _linhas_de_codigo(arq.read_text(encoding="utf-8")):
            if _ANTIPATTERN.search(linha):
                ofensores.append(f"{nome}:{i}: {linha.strip()}")
    assert not ofensores, (
        "fecha+abre de custódia à mão detectado — roteie por transferir_posse:\n"
        + "\n".join(ofensores)
    )


# --- Os routers inline (auth.py) e o estorno (dispensacoes.py) roteiam ---------

def test_auth_e_dispensacoes_importam_o_chokepoint():
    for nome in ("auth.py", "dispensacoes.py"):
        src = (_ROUTERS / nome).read_text(encoding="utf-8")
        assert "from app.routers.custodia import transferir_posse" in src, (
            f"{nome} não importa o choke-point transferir_posse — "
            "os caminhos inline ainda fazem posse à mão."
        )


# --- Estado do ramo prescritor (Opção B, ratificada por Fabiano 2026-07-23) ----

def test_transferida_prescritor_existe_e_e_nao_terminal():
    assert "transferida_prescritor" in ESTADOS_PRESCRICAO
    # NÃO é terminal: aguarda prescrição derivada (correção), mirror de transferida_paciente.
    assert "transferida_prescritor" not in ESTADOS_TERMINAIS_PRESCRICAO
    # Tem saída para os terminais (revogação / expiração) — não fica preso.
    assert TRANSICOES_PRESCRICAO["transferida_prescritor"] == frozenset({"cancelada", "expirada"})


def test_transferida_prescritor_e_alcancavel_pelos_caminhos_de_devolucao():
    # dispensador→prescritor (em_custodia) e paciente→prescritor (transferida_paciente/pendente).
    assert transicao_valida_prescricao("em_custodia", "transferida_prescritor")
    assert transicao_valida_prescricao("transferida_paciente", "transferida_prescritor")
    assert transicao_valida_prescricao("pendente", "transferida_prescritor")
    # Cada entrada emite custodia_transferida (posse muda → ledger registra).
    for de in ("em_custodia", "transferida_paciente", "pendente"):
        assert EVENTOS_PRESCRICAO[(de, "transferida_prescritor")] == "custodia_transferida"
