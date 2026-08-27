"""ENG-019 PR 6 — resultado em branco não entra no ledger.

CONSULTA-UX-001/NC-7: `registrarResultado` capturava o resumo num `prompt()`
nativo e só barrava `null` (o cancelar). String vazia passava: o item avançava
para `resultado_disponivel` com um resultado clínico SEM CONTEÚDO.

Por que isto não é cosmético — e por que sobe na ordem: o ledger é imutável por
trigger (§2 do CLAUDE.md). Um resultado em branco gravado hoje não pode ser
corrigido NUNCA, só superado por outro objeto. Atrito de tela se conserta amanhã;
registro permanente sem conteúdo, não.

A REGRA, com a distinção que importa:

    ""  ou "   "   →  não é dado. 422.
    None           →  ausência declarada. Segue aceita.

A segunda linha não é indulgência: o caminho do LAUDO manda `resultado_resumo`
nulo de propósito (`_coletarItensDoEditor` faz `.trim() || null`) quando o RT
preenche conclusão e valor de referência e deixa o resumo livre em branco. Ali o
artefato é o laudo; o resumo do item é ponteiro. Exigir texto quebraria o Ticket G
sem defender nada.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

import pytest

from tests.integration.test_e2_laudo_apos_resultado import (
    _h,
    _pedido,
    _percurso_e2,
    _tok_lab,
)
from tests.integration.conftest import obter_token_prescritor


def _post_resultado(client, proto, item_id, corpo: dict):
    return client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json=corpo, headers=_h(_tok_lab()),
    )


@pytest.mark.parametrize("branco", ["", "   ", "\t", "\n  \t "])
def test_resumo_em_branco_e_recusado(client, seed_usuario, seed_paciente, branco):
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["GLICEMIA CAPILAR"])

    r = _post_resultado(client, proto, ids[0], {"resultado_resumo": branco})
    assert r.status_code == 422, (
        f"resumo {branco!r} foi aceito — entraria no ledger imutável sem conteúdo"
    )

    # E o item NÃO avançou: o AC é este, não a mensagem de erro.
    assert _pedido(client, proto, _tok_lab())["itens"][0]["status_item"] == "coletado"


def test_resumo_ausente_segue_aceito(client, seed_usuario, seed_paciente):
    """O caminho do laudo manda nulo de propósito — não pode quebrar."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["GLICEMIA CAPILAR"])

    r = _post_resultado(client, proto, ids[0], {})
    assert r.status_code == 201, r.text
    assert _pedido(client, proto, _tok_lab())["itens"][0]["status_item"] == "resultado_disponivel"


def test_resumo_com_conteudo_e_gravado_sem_sobra_de_espaco(
    client, seed_usuario, seed_paciente
):
    """Espaço nas bordas é digitação, não dado — e o ledger não aceita errata."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["GLICEMIA CAPILAR"])

    r = _post_resultado(client, proto, ids[0], {"resultado_resumo": "  Glicemia 92 mg/dL  "})
    assert r.status_code == 201, r.text

    item = _pedido(client, proto, _tok_lab())["itens"][0]
    assert item["resultado_resumo"] == "Glicemia 92 mg/dL"
