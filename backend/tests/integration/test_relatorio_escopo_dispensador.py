"""
tests/integration/test_relatorio_escopo_dispensador.py
======================================================

Cobertura E2E do escopo institucional do relatório de dispensações
(`backend/app/routers/relatorios.py`), após a ampliação de RBAC do
PLANO_DEMO_CIRCULACAO.md (T8): o papel `dispensador` passa a acessar o
relatório, mas **travado ao próprio CNPJ** (CLAUDE.md §6b — guardrail de
escopo institucional).

Invariantes verificadas:
- Dispensador só enxerga as próprias dispensações (filtro por CNPJ forçado).
- Um dispensador NÃO consegue ler o relatório de outro estabelecimento,
  **mesmo forjando** `?cnpj_estabelecimento=` de terceiros (o param é ignorado
  para dispensador — o CNPJ vem do JWT).
- Auditor/admin continuam vendo todas as dispensações.
- CSV e PDF abrem para dispensador (antes eram 403 — só auditor/admin).

Princípios de teste (espelham test_custodia_devolucao.py):
- Cada cenário monta o próprio setup; asserções filtram pelos protocolos
  criados no teste — não consultam estado histórico do banco.
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

_CNPJ_A = "12345678000195"   # Farmácia A (Central)
_CNPJ_B = "99999999000272"   # Farmácia B (Norte, T0.5)


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _jwt_dispensador(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome=f"Farmácia {cnpj}")


def _jwt_auditor() -> str:
    return criar_access_token(sub="auditor-teste", role="auditor", nome="Auditor Teste")


def _seed_dispensacao(outer_conn, cnpj: str) -> str:
    """
    Semeia uma prescrição + 1 item + 1 dispensação atribuída ao `cnpj` dado.
    Retorna o protocolo (chave textual única para localizar no relatório).
    """
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-REL-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) "
            "ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) "
            "ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'parcialmente_dispensada', 'nova', %s, %s, %s)
            RETURNING id
            """,
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               posologia, status_item, created_at, updated_at)
            VALUES (%s, 'MEDICAMENTO_REL', '500mg', 10, '1cp 8/8h', 'em_custodia', %s, %s)
            RETURNING id
            """,
            (prescricao_id, now, now),
        )
        item_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO dispensacoes
              (prescricao_item_id, cnpj_estabelecimento, quantidade_dispensada,
               dispensado_por, dispensado_em, lote, fabricante, observacao,
               origem_contexto, created_at)
            VALUES (%s, %s, 4, 'farmaceutico', %s, 'L1', 'ACME', NULL, 'manual', %s)
            """,
            (item_id, cnpj, now, now),
        )
    return proto


# ---------------------------------------------------------------------------
# CSV — escopo por CNPJ
# ---------------------------------------------------------------------------

def test_relatorio_csv_dispensador_ve_apenas_proprio_cnpj(client, outer_conn):
    proto_a = _seed_dispensacao(outer_conn, _CNPJ_A)
    proto_b = _seed_dispensacao(outer_conn, _CNPJ_B)

    r = client.get(
        "/relatorios/dispensacoes.csv",
        headers=_headers(_jwt_dispensador(_CNPJ_A)),
    )
    assert r.status_code == 200, r.text
    corpo = r.text
    assert proto_a in corpo, "dispensador A não viu a própria dispensação"
    assert proto_b not in corpo, "dispensador A enxergou dispensação de OUTRO estabelecimento (vaza §6b)"


def test_relatorio_csv_dispensador_nao_forja_cnpj_de_terceiro(client, outer_conn):
    """
    Segurança: mesmo passando `?cnpj_estabelecimento=<CNPJ de terceiro>`, o
    dispensador continua travado ao próprio CNPJ (param ignorado).
    """
    proto_a = _seed_dispensacao(outer_conn, _CNPJ_A)
    proto_b = _seed_dispensacao(outer_conn, _CNPJ_B)

    r = client.get(
        f"/relatorios/dispensacoes.csv?cnpj_estabelecimento={_CNPJ_B}",
        headers=_headers(_jwt_dispensador(_CNPJ_A)),
    )
    assert r.status_code == 200, r.text
    corpo = r.text
    assert proto_a in corpo
    assert proto_b not in corpo, "dispensador forjou CNPJ e viu estabelecimento de terceiro"


def test_relatorio_csv_auditor_ve_todos(client, outer_conn):
    proto_a = _seed_dispensacao(outer_conn, _CNPJ_A)
    proto_b = _seed_dispensacao(outer_conn, _CNPJ_B)

    r = client.get(
        "/relatorios/dispensacoes.csv",
        headers=_headers(_jwt_auditor()),
    )
    assert r.status_code == 200, r.text
    corpo = r.text
    assert proto_a in corpo and proto_b in corpo, "auditor não viu todas as dispensações"


# ---------------------------------------------------------------------------
# PDF — RBAC aberto ao dispensador
# ---------------------------------------------------------------------------

def test_relatorio_pdf_abre_para_dispensador(client, outer_conn):
    """Antes do T8, dispensador recebia 403 no PDF. Agora recebe 200 + PDF."""
    _seed_dispensacao(outer_conn, _CNPJ_A)

    r = client.get(
        "/relatorios/dispensacoes.pdf",
        headers=_headers(_jwt_dispensador(_CNPJ_A)),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
