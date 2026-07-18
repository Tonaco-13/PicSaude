"""
tests/integration/test_relatorio_sngpc_r4.py — TICKET-R4-ESCRITURACAO-REGULATORIA (PG real).

Encarna, contra PostgreSQL, os critérios de aceite do R4 (CLAUDE.md §2a):

  - dispensar item CONTROLADO (B1) → dispensacoes.grupo_regulatorio_id +
    motor_regulatorio_versao CONGELADOS; relatório SNGPC mostra o grupo
  - dispensar item NÃO-CONTROLADO → grupo_regulatorio_id NULL; coluna vazia (sem inventar)
  - R1: congelar, alterar (em teste) a definição do grupo no motor, re-gerar o
    relatório → o movimento passado MANTÉM o grupo congelado (não re-resolve)
  - item com classe_controle inválida → dispensação FALHA ALTA (não congela NULL)

Congelamento POR VALOR (não FK/derivação ao vivo) é a essência do R4.
"""
from __future__ import annotations

import csv
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


def _seed_prescricao(outer_conn, *, classe_controle=None, tipo_retencao=None,
                     cnpj=_CNPJ, quantidade=10):
    """Semeia prescrição com um item (opcionalmente controlado) e custódia no CNPJ,
    pronta para dispensar. Devolve (prescricao_id, proto, item_id)."""
    now = datetime.utcnow().isoformat()
    proto = f"REC-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        pres_id, pac_id = _ids_base(cur)
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "classe_controle, tipo_retencao, posologia, status_item, created_at, updated_at) "
            "VALUES (%s, 'CLONAZEPAM', '2mg', %s, %s, %s, '1cp/noite', 'em_custodia', %s, %s) RETURNING id",
            (prescricao_id, quantidade, classe_controle, tipo_retencao, now, now),
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
    return client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": cnpj, "quantidade_dispensada": qtd},
        headers=_h(cnpj),
    )


def _grupo_congelado(outer_conn, item_id) -> tuple:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT grupo_regulatorio_id, motor_regulatorio_versao FROM dispensacoes "
            "WHERE prescricao_item_id = %s ORDER BY id DESC LIMIT 1",
            (item_id,),
        )
        return cur.fetchone()


def _csv_linhas(client, cnpj=_CNPJ, **params):
    r = client.get("/dispensadores/relatorio.csv", params=params, headers=_h(cnpj))
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.text)))


# --------------------------------------------------------------------- controlado

def test_dispensar_controlado_congela_grupo_e_versao(client, outer_conn):
    from app.domain.motor_regulatorio import MOTOR_REGULATORIO_VERSAO

    _pid, proto, item = _seed_prescricao(outer_conn, classe_controle="B1")
    assert _dispensar(client, proto, item, 3).status_code == 201

    grupo, versao = _grupo_congelado(outer_conn, item)
    assert grupo == "notificacao_receita_b"
    assert versao == MOTOR_REGULATORIO_VERSAO

    linha = next(r for r in _csv_linhas(client) if r["protocolo_prescricao"] == proto)
    assert linha["grupo_regulatorio_id"] == "notificacao_receita_b"


def test_comprovante_controlado_traz_nome_do_slug(client, outer_conn):
    """R4-FRONTEND — o comprovante resolve o NOME humano do slug congelado
    (grupo_por_id, fonte única). Item controlado → controlado=True + nome."""
    _pid, proto, item = _seed_prescricao(outer_conn, classe_controle="B1")
    disp_id = _dispensar(client, proto, item, 3).json()["dispensacao_id"]

    comp = client.get(f"/dispensacoes/{disp_id}/comprovante", headers=_h()).json()
    esc = comp["escrituracao_regulatoria"]
    assert esc["controlado"] is True
    assert esc["grupo_regulatorio_id"] == "notificacao_receita_b"
    assert esc["grupo_regulatorio_nome"] == "Notificação de Receita B (Azul)"


def test_comprovante_nao_controlado_sem_grupo(client, outer_conn):
    """Não-controlado → controlado=False, nome None (a UI não renderiza o bloco)."""
    _pid, proto, item = _seed_prescricao(outer_conn)   # sem classe/retenção
    disp_id = _dispensar(client, proto, item, 3).json()["dispensacao_id"]

    esc = client.get(f"/dispensacoes/{disp_id}/comprovante", headers=_h()).json()["escrituracao_regulatoria"]
    assert esc["controlado"] is False
    assert esc["grupo_regulatorio_nome"] is None


# ----------------------------------------------------------------- não-controlado

def test_dispensar_nao_controlado_congela_null(client, outer_conn):
    _pid, proto, item = _seed_prescricao(outer_conn)  # sem classe/retenção
    assert _dispensar(client, proto, item, 3).status_code == 201

    grupo, versao = _grupo_congelado(outer_conn, item)
    assert grupo is None
    assert versao is None

    linha = next(r for r in _csv_linhas(client) if r["protocolo_prescricao"] == proto)
    assert linha["grupo_regulatorio_id"] == ""   # vazio, nunca inventado


# ------------------------------------------------------------------------- R1

def test_r1_grupo_congelado_imune_a_mudanca_de_regra(client, outer_conn, monkeypatch):
    """R1 — congelar; depois alterar (em teste) a definição do grupo no motor;
    re-gerar o relatório → o movimento passado MANTÉM o grupo congelado.

    O relatório projeta o valor gravado na coluna — não re-resolve o motor. Este
    é o teste que prova o §2a R4: o período fechado é estável para sempre."""
    _pid, proto, item = _seed_prescricao(outer_conn, classe_controle="B1")
    assert _dispensar(client, proto, item, 3).status_code == 201

    # Fotografa o relatório com a regra vigente.
    antes = next(r for r in _csv_linhas(client) if r["protocolo_prescricao"] == proto)
    assert antes["grupo_regulatorio_id"] == "notificacao_receita_b"

    # A RDC "muda" amanhã: a definição do grupo B ganha novo id no motor.
    import app.domain.motor_regulatorio as motor
    grupo_b_novo = motor.GRUPO_B.__class__(**{**motor.GRUPO_B.__dict__, "id_grupo": "grupo_b_v2"})
    monkeypatch.setattr(motor, "GRUPO_B", grupo_b_novo)

    # Re-gera o relatório do MESMO período — o movimento passado não muda.
    depois = next(r for r in _csv_linhas(client) if r["protocolo_prescricao"] == proto)
    assert depois["grupo_regulatorio_id"] == "notificacao_receita_b"   # congelado, não "grupo_b_v2"


# ------------------------------------------------------------------- falha alta

def test_classe_invalida_dispensacao_falha_alta(client, outer_conn):
    """Item com classe_controle preenchida mas fora do vocabulário do motor →
    dispensação falha 422 (não congela NULL para um controlado)."""
    _pid, proto, item = _seed_prescricao(outer_conn, classe_controle="Z9")
    r = _dispensar(client, proto, item, 3)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "classe_controle_inconsistente"

    # Nenhuma dispensação foi gravada (falha antes do INSERT).
    assert _grupo_congelado(outer_conn, item) is None
