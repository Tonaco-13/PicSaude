"""TICKET-5C-BIS-E — Ownership mínimo em dispensação hospitalar.

O endpoint hospitalar recebe ``org_id``/``unidade_id`` no payload. Como
``prescricoes`` ainda não carrega ``org_id`` no rollout institucional (§6b),
o ownership aqui é Padrão A puro: CNPJ do dispensador no JWT resolve para uma
org em ``prestadores`` e essa org deve coincidir com ``payload.org_id``.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)

_ORG_A = "org-hosp-a"
_ORG_B = "org-hosp-b"
_CNPJ_A = "12345678000195"
_CNPJ_MASC = "98.765.432/0001-10"
_CNPJ_LIMPO = "98765432000110"

_TABELAS_MUTACAO = (
    "dispensacoes",
    "dispensacoes_hospitalares",
    "prescricao_eventos",
    "prescricao_custodia",
)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _contagens(outer_conn, tabelas=_TABELAS_MUTACAO):
    out = {}
    with outer_conn.cursor() as cur:
        for tabela in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {tabela}")
            out[tabela] = cur.fetchone()[0]
    return out


def _seed_prestador(client, org_id: str, cnpj: str, nome: str = "Hospital Teste") -> None:
    r = client.post(
        "/prestadores",
        json={"org_id": org_id, "nome": nome, "tipo": "hospital", "cnpj": cnpj},
        headers=_headers(_tok("admin", "admin")),
    )
    assert r.status_code == 201, r.text


def _criar_prescricao(client, seed_usuario) -> str:
    payload = {
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": SEED_PRESCRITOR_NOME,
        "cpf_paciente": SEED_PACIENTE_CPF,
        "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "nova",
        "itens": [
            {
                "nome_medicamento": "AMOXICILINA",
                "concentracao": "500mg",
                "quantidade": 10,
                "posologia": "1 cap 3x ao dia",
            },
        ],
    }
    r = client.post(
        "/prescricoes",
        json=payload,
        headers=_headers(obter_token_prescritor(client, seed_usuario)),
    )
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _item_id(outer_conn, protocolo: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT i.id
              FROM prescricao_itens i
              JOIN prescricoes p ON p.id = i.prescricao_id
             WHERE p.protocolo = %s
             ORDER BY i.id
             LIMIT 1
            """,
            (protocolo,),
        )
        return cur.fetchone()[0]


def _payload(org_id: str = _ORG_A, quantidade: int = 5) -> dict:
    return {
        "org_id": org_id,
        "unidade_id": "farm-hosp-central",
        "setor": "UTI Adulto",
        "leito": "12A",
        "modalidade": "internacao",
        "quantidade_dispensada": quantidade,
        "dispensado_por": "Farm. Teste",
    }


def _url(protocolo: str, item_id: int) -> str:
    return f"/prescricoes/{protocolo}/itens/{item_id}/dispensar/hospitalar"


def test_dispensador_org_match_201_e_persiste_linhas(
    client, outer_conn, seed_usuario, seed_paciente,
):
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_A),
        headers=_headers(_tok(_CNPJ_A, "dispensador")),
    )

    assert r.status_code == 201, r.text
    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM dispensacoes WHERE prescricao_item_id = %s", (item,))
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT COUNT(*) FROM dispensacoes_hospitalares WHERE prescricao_item_id = %s",
            (item,),
        )
        assert cur.fetchone()[0] == 1


def test_dispensador_cross_org_403_rollback(
    client, outer_conn, seed_usuario, seed_paciente,
):
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)
    baseline = _contagens(outer_conn)

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_B),
        headers=_headers(_tok(_CNPJ_A, "dispensador")),
    )

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "dispensador_de_outra_org"
    assert _contagens(outer_conn) == baseline


def test_dispensador_sem_prestador_fail_closed_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_A),
        headers=_headers(_tok(_CNPJ_A, "dispensador")),
    )

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "dispensador_de_outra_org"


def test_cnpj_mascarado_no_cadastro_resolve_201(
    client, outer_conn, seed_usuario, seed_paciente,
):
    _seed_prestador(client, _ORG_A, _CNPJ_MASC)
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_A),
        headers=_headers(_tok(_CNPJ_LIMPO, "dispensador")),
    )

    assert r.status_code == 201, r.text


def test_admin_bypass_201_sem_prestador(
    client, outer_conn, seed_usuario, seed_paciente,
):
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_B),
        headers=_headers(_tok("admin", "admin")),
    )

    assert r.status_code == 201, r.text


def test_antileak_cross_org_403_precede_409_terminal(
    client, outer_conn, seed_usuario, seed_paciente,
):
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    protocolo = _criar_prescricao(client, seed_usuario)
    item = _item_id(outer_conn, protocolo)
    with outer_conn.cursor() as cur:
        cur.execute("UPDATE prescricoes SET status = 'dispensada' WHERE protocolo = %s", (protocolo,))

    r = client.post(
        _url(protocolo, item),
        json=_payload(_ORG_B),
        headers=_headers(_tok(_CNPJ_A, "dispensador")),
    )

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "dispensador_de_outra_org"
