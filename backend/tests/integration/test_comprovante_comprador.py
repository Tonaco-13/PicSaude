"""
tests/integration/test_comprovante_comprador.py
===============================================

T5 — comprador (portador que retira) × paciente (indicação clínica) no
comprovante de dispensação.

Checks do Jules baked in:
- **Simetria:** criar um novo comprador (nova dispensação) NÃO invalida o
  anterior — o comprador é atributo POR-DISPENSAÇÃO, imutável; cada dispensação
  carrega o seu. Não há overwrite.
- **Orphan:** o PII do comprador vive em `dispensacoes`, ancorado por FK à
  prescrição/paciente — nunca solto numa tabela sem constraint.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
)

_CNPJ = "12345678000195"


def _h(cnpj: str = _CNPJ) -> dict:
    return {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='Farmácia')}"}


def _seed(outer_conn, quantidade: int = 10):
    """Prescrição em_custodia + item + custódia ativa do dispensador (T1.5)."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-COMP-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "posologia, status_item, created_at, updated_at) "
            "VALUES (%s, 'LOSARTANA', '50mg', %s, '1cp/dia', 'em_custodia', %s, %s) RETURNING id",
            (prescricao_id, quantidade, now, now),
        )
        item_id = cur.fetchone()[0]
        for iid in (None, item_id):
            cur.execute(
                "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
                "transferida_em, encerrada_em, motivo, created_at) "
                "VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed', %s)",
                (prescricao_id, iid, _CNPJ, now, now),
            )
    return prescricao_id, proto, item_id


def _dispensar(client, proto, item_id, qtd, comprador_nome=None, comprador_documento=None):
    payload = {"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": qtd}
    if comprador_nome:
        payload["comprador_nome"] = comprador_nome
    if comprador_documento:
        payload["comprador_documento"] = comprador_documento
    r = client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar", json=payload, headers=_h())
    assert r.status_code == 201, r.text
    return r.json()["dispensacao_id"]


def _comprovante(client, disp_id):
    r = client.get(f"/dispensacoes/{disp_id}/comprovante?formato=json", headers=_h())
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------

def test_comprador_gravado_e_no_comprovante(client, outer_conn):
    _, proto, item_id = _seed(outer_conn)
    disp_id = _dispensar(client, proto, item_id, 2, "MARIA PORTADORA", "22233344455")

    comp = _comprovante(client, disp_id)
    assert comp["comprador"]["nome"] == "MARIA PORTADORA"
    assert comp["comprador"]["documento"] == "22233344455"
    assert comp["comprador"]["eh_paciente"] is False
    # Paciente permanece distinto do comprador.
    assert comp["paciente"]["nome"] == SEED_PACIENTE_NOME

    # PDF (mesma chamada do balcão) gera sem quebrar.
    pdf = client.get(f"/dispensacoes/{disp_id}/comprovante?formato=pdf", headers=_h())
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_comprador_mvp_fallback_paciente(client, outer_conn):
    """Sem comprador declarado → comprador = paciente (MVP), sinalizado."""
    _, proto, item_id = _seed(outer_conn)
    disp_id = _dispensar(client, proto, item_id, 2)

    comp = _comprovante(client, disp_id)
    assert comp["comprador"]["eh_paciente"] is True
    assert comp["comprador"]["nome"] == comp["paciente"]["nome"]


def test_simetria_comprador_e_por_dispensacao_imutavel(client, outer_conn):
    """
    Check de Simetria (Jules): uma nova dispensação com outro comprador NÃO
    invalida o comprador da dispensação anterior — cada uma carrega o seu.
    """
    _, proto, item_id = _seed(outer_conn, quantidade=10)
    d1 = _dispensar(client, proto, item_id, 3, "COMPRADOR A", "11111111111")
    d2 = _dispensar(client, proto, item_id, 3, "COMPRADOR B", "22222222222")

    assert _comprovante(client, d1)["comprador"]["nome"] == "COMPRADOR A"
    assert _comprovante(client, d2)["comprador"]["nome"] == "COMPRADOR B"

    # Imutável no banco — a 2ª dispensação não sobrescreveu a 1ª.
    with outer_conn.cursor() as cur:
        cur.execute("SELECT comprador_nome FROM dispensacoes WHERE id = %s", (d1,))
        assert cur.fetchone()[0] == "COMPRADOR A"


def test_orphan_comprador_ancorado_por_fk(client, outer_conn):
    """
    Check de Orphan (Jules): o PII do comprador vive em `dispensacoes`, ancorado
    por FK à prescrição/paciente — nunca solto.
    """
    _, proto, item_id = _seed(outer_conn)
    disp_id = _dispensar(client, proto, item_id, 2, "PORTADOR ANCORADO", "33333333333")

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.comprador_nome, p.protocolo, pac.id
              FROM dispensacoes d
              JOIN prescricao_itens i ON i.id = d.prescricao_item_id
              JOIN prescricoes p       ON p.id = i.prescricao_id
              JOIN pacientes pac       ON pac.id = p.paciente_id
             WHERE d.id = %s
            """,
            (disp_id,),
        )
        row = cur.fetchone()
    assert row is not None, "comprador órfão — dispensação sem cadeia de FK"
    assert row[0] == "PORTADOR ANCORADO"
    assert row[1] == proto
