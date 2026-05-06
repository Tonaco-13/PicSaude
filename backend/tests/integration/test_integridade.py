"""Ticket 13 — integridade referencial do banco real.

Essas queries validam *invariantes de domínio* e rodam contra picsaude_test.
Como o banco é criado e carregado apenas via testes isolados, elas devem
retornar 0 em um banco limpo.

Um resultado > 0 aqui indica bug real (FK pendurada, evento sem prescrição,
prescrição sem ledger). Reporte como achado, não corrija o teste.
"""
from __future__ import annotations

from tests.integration.conftest import obter_token_prescritor


def _count(outer_conn, sql: str, params: tuple = ()) -> int:
    with outer_conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def test_sem_itens_orfaos(outer_conn):
    total = _count(
        outer_conn,
        """
        SELECT COUNT(*) FROM prescricao_itens pi
        LEFT JOIN prescricoes p ON p.id = pi.prescricao_id
        WHERE p.id IS NULL
        """,
    )
    assert total == 0


def test_sem_eventos_orfaos(outer_conn):
    total = _count(
        outer_conn,
        """
        SELECT COUNT(*) FROM prescricao_eventos pe
        LEFT JOIN prescricoes p ON p.id = pe.prescricao_id
        WHERE p.id IS NULL
        """,
    )
    assert total == 0


def test_sem_custodia_orfa(outer_conn):
    total = _count(
        outer_conn,
        """
        SELECT COUNT(*) FROM prescricao_custodia pc
        LEFT JOIN prescricoes p ON p.id = pc.prescricao_id
        WHERE p.id IS NULL
        """,
    )
    assert total == 0


def test_sem_dispensacao_orfa(outer_conn):
    """Dispensações apontam para prescricao_itens (não direto para prescricoes)."""
    total = _count(
        outer_conn,
        """
        SELECT COUNT(*) FROM dispensacoes d
        LEFT JOIN prescricao_itens pi ON pi.id = d.prescricao_item_id
        WHERE pi.id IS NULL
        """,
    )
    assert total == 0


def test_prescricao_criada_gera_ao_menos_um_evento(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Após criar uma prescrição via API, ela deve ter ≥ 1 evento no ledger.

    Invariante arquitetural (CLAUDE.md seção 2): toda prescrição nasce com
    evento `prescricao_emitida`. Este teste garante o caminho feliz e
    também que não há prescrição 'fantasma' (sem ledger).
    """
    token = obter_token_prescritor(client, seed_usuario)

    payload = {
        "cns_prescritor":  "987654321098765",
        "nome_prescritor": "DR. TESTE TICKET13",
        "cpf_paciente":    "12345678901",
        "nome_paciente":   "PACIENTE TESTE TICKET13",
        "tipo_emissao":    "nova",
        "itens": [{
            "nome_medicamento": "PARACETAMOL",
            "concentracao":     "500mg",
            "quantidade":       20,
            "posologia":        "1 comprimido a cada 8h",
        }],
    }
    r = client.post(
        "/prescricoes", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 201, r.text
    protocolo = r.json()["protocolo"]

    total_eventos = _count(
        outer_conn,
        """
        SELECT COUNT(*) FROM prescricao_eventos pe
        JOIN prescricoes p ON p.id = pe.prescricao_id
        WHERE p.protocolo = %s
        """,
        (protocolo,),
    )
    assert total_eventos >= 1, (
        f"Prescrição {protocolo} foi criada sem nenhum evento no ledger "
        "— violação do contrato imutável (CLAUDE.md §2)."
    )
