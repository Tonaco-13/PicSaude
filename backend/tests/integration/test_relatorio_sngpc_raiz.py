"""
tests/integration/test_relatorio_sngpc_raiz.py — TICKET-R3-PROTOCOLO-RAIZ (PG real).

Encarna, contra PostgreSQL, os critérios de aceite da linhagem-mãe (R3) e da
reprodutibilidade (R1) no relatório SNGPC do dispensador:

  - REC-003 ← REC-002 ← REC-001: protocolo_raiz = REC-001 na linha da neta
  - prescrição-raiz: protocolo_raiz == protocolo_prescricao
  - R1: mesmo banco + mesmo snapshot → CSV byte-idêntico (SHA-256 igual em 2 gerações)
  - memoização não-stale: prescrição derivada nasce ENTRE duas gerações; a 2ª a enxerga

O pré-check do arquiteto (origem_prescricao_id imutável, main@2f510ed) fica
encarnado aqui: a cadeia é montada por INSERTs de derivação e nunca alterada; o
relatório resolve a raiz subindo a cadeia, sem CTE recursiva.
"""
from __future__ import annotations

import csv
import hashlib
import io
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


def _ids_base(cur) -> tuple[int, int]:
    """Garante prescritor e paciente-semente; devolve (prescritor_id, paciente_id)."""
    now = datetime.utcnow().isoformat()
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
    return pres_id, pac_id


def _seed_prescricao(outer_conn, *, origem_id=None, tipo_emissao="nova",
                     cnpj=_CNPJ, quantidade=10):
    """Semeia uma prescrição (opcionalmente DERIVADA via origem_id) com item e
    custódia no CNPJ, pronta para dispensar. Devolve (prescricao_id, proto, item_id)."""
    now = datetime.utcnow().isoformat()
    proto = f"REC-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        pres_id, pac_id = _ids_base(cur)
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "origem_prescricao_id, data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', %s, %s, %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, tipo_emissao, origem_id, now, now, now),
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
                (prescricao_id, iid, cnpj, now, now),
            )
    return prescricao_id, proto, item_id


def _dispensar(client, proto, item_id, qtd, cnpj=_CNPJ):
    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": cnpj, "quantidade_dispensada": qtd},
        headers=_h(cnpj),
    )
    assert r.status_code == 201, r.text
    return r.json()["dispensacao_id"]


def _csv_text(client, cnpj=_CNPJ, **params):
    r = client.get("/dispensadores/relatorio.csv", params=params, headers=_h(cnpj))
    assert r.status_code == 200, r.text
    return r.text


def _linhas(texto):
    return list(csv.DictReader(io.StringIO(texto)))


# --------------------------------------------------------------------------- R3

def test_neta_resolve_a_raiz_da_cadeia_pg(client, outer_conn):
    """REC-003 ← REC-002 ← REC-001 → a linha da neta traz protocolo_raiz = REC-001."""
    id1, proto1, _ = _seed_prescricao(outer_conn)
    id2, proto2, _ = _seed_prescricao(outer_conn, origem_id=id1, tipo_emissao="correcao")
    _id3, proto3, item3 = _seed_prescricao(outer_conn, origem_id=id2, tipo_emissao="renovacao")

    _dispensar(client, proto3, item3, 3)

    linha = next(r for r in _linhas(_csv_text(client)) if r["protocolo_prescricao"] == proto3)
    assert linha["protocolo_raiz"] == proto1
    assert linha["protocolo_raiz"] != linha["protocolo_prescricao"]


def test_raiz_resolve_a_si_mesma_pg(client, outer_conn):
    """Prescrição sem origem → protocolo_raiz == protocolo_prescricao."""
    _id, proto, item = _seed_prescricao(outer_conn)
    _dispensar(client, proto, item, 2)

    linha = next(r for r in _linhas(_csv_text(client)) if r["protocolo_prescricao"] == proto)
    assert linha["protocolo_raiz"] == proto


# --------------------------------------------------------------------------- R1

def test_reprodutibilidade_csv_byte_identico_pg(client, outer_conn):
    """R1 — mesmo banco + mesmo snapshot: duas gerações do CSV são byte-idênticas
    (SHA-256 igual). Relatório é projeção pura e determinística do ledger."""
    id1, _proto1, _ = _seed_prescricao(outer_conn)
    _id2, proto2, item2 = _seed_prescricao(outer_conn, origem_id=id1, tipo_emissao="correcao")
    _dispensar(client, proto2, item2, 4)

    t1 = _csv_text(client)
    t2 = _csv_text(client)

    assert hashlib.sha256(t1.encode("utf-8")).hexdigest() == \
           hashlib.sha256(t2.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- não-stale

def test_memoizacao_nao_stale_entre_geracoes_pg(client, outer_conn):
    """
    Prescrição derivada nasce ENTRE duas gerações do relatório: a 2ª a enxerga.
    Prova que a linhagem é refetchada e o cache de raízes é por-execução (nunca
    global/stale). A 1ª geração vê só a raiz; a 2ª vê a derivação resolvendo à raiz.
    """
    id1, proto1, item1 = _seed_prescricao(outer_conn)
    _dispensar(client, proto1, item1, 2)

    # 1ª geração: só a raiz foi dispensada.
    l1 = _linhas(_csv_text(client))
    protos_g1 = {r["protocolo_prescricao"] for r in l1}
    assert proto1 in protos_g1

    # Nasce REC-002 derivada de REC-001 e é dispensada — ENTRE as duas gerações.
    _id2, proto2, item2 = _seed_prescricao(outer_conn, origem_id=id1, tipo_emissao="correcao")
    _dispensar(client, proto2, item2, 3)

    # 2ª geração enxerga a derivação nova, resolvendo à mesma raiz.
    l2 = _linhas(_csv_text(client))
    linha2 = next(r for r in l2 if r["protocolo_prescricao"] == proto2)
    assert proto2 not in protos_g1              # não existia na 1ª geração
    assert linha2["protocolo_raiz"] == proto1   # a 2ª a vê e resolve à raiz
