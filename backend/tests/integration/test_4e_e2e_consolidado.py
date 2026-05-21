"""
tests/integration/test_4e_e2e_consolidado.py
============================================

Sub-tarefa 4E.1 — testes E2E consolidados da Etapa 4 (instance_id canônico).

Valida 5 invariantes do contrato instance_id (I1–I5) sobre cadeias clínicas
multi-objeto que atravessam os 5 subdomínios tocados na Etapa 4
(prescrição, pedido_exame, laudo, agendamento, circulação diagnóstica).

Contrato semântico (§3 do ticket):
    instance_id ≡ UUID v4 inalterável que identifica univocamente uma
    instalação PicSaúde. Não é ID de transação. Em uma mesma instância,
    TODOS os eventos têm o MESMO instance_id (invariante I2).

Estratégia de captura (§5.3 do ticket, P1.1 CODEX rodada 1):
    `conftest.py:37` desliga `_lifespan_bootstrap`, então
    `meta_instalacao.instance_id` NÃO está populado até a 1ª chamada a
    `registrar_evento_ledger` (que chama `get_instance_id_conn`). Por isso
    C1/C3/C4/C5/C6 capturam instance_id_canonico DEPOIS do 1º POST que
    grava em algum *_eventos. C5b é exceção: o override por env
    (`PICSAUDE_INSTANCE_ID`) não toca o DB — comparação direta contra
    UUID forçado conhecido pelo teste.

Schema do outbox (§2.2 do ticket, P1.2 CODEX rodada 1):
    `eventos_publicacao` NÃO tem coluna `protocolo`. Usa `objeto_id`.
    Queries: `WHERE objeto_tipo = %s AND objeto_id = %s`.

Referências:
  - app/instance.py            — contrato semântico do instance_id
  - app/domain/ledger.py       — helper registrar_evento_ledger
  - DATA-PROTECTION.md §4.2    — marca d'água da instalação
  - TICKET-4E-1-E2E-CONSOLIDADO.md — spec deste arquivo
  - test_ledger_helper.py:674  — referência do contrato de env override
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Payloads canônicos (cópia local — não importar entre arquivos de teste)
# ---------------------------------------------------------------------------

_PAYLOAD_PRESCRICAO = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "nova",
    "itens": [
        {"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
         "quantidade": 10, "posologia": "1 cap 3x ao dia"},
    ],
}

_PAYLOAD_PEDIDO_A = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}

_PAYLOAD_PEDIDO_B = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "GLICEMIA", "quantidade": 1}],
}

_PAYLOAD_LAUDO = {
    "cns_autor":      SEED_PRESCRITOR_CNS,
    "nome_autor":     SEED_PRESCRITOR_NOME,
    "cpf_paciente":   SEED_PACIENTE_CPF,
    "nome_paciente":  SEED_PACIENTE_NOME,
    "tipo_emissao":   "novo",
    "itens": [{"nome_exame": "HEMOGRAMA", "resultado_resumo": "Sem alterações"}],
}

_AGENDAMENTO_BASE = {
    "data_hora":        "2026-05-20T09:00:00",
    "org_id":           "LAB-TESTE-4E",
    "unidade_id":       "UNIDADE-4E-001",
    "tipo_agendamento": "exame",
}


# ---------------------------------------------------------------------------
# Helpers locais (cópia de test_4d2 — clareza > DRY em testes)
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _eh_uuid_v4(s) -> bool:
    if not s:
        return False
    try:
        u = uuid.UUID(str(s))
    except (ValueError, TypeError):
        return False
    return u.version == 4


@contextmanager
def _override_role(role: str, sub: str = "test"):
    """Override temporário de ``get_current_user`` para endpoints com
    role distinta do prescritor padrão.
    """
    from app.auth.dependencies import get_current_user
    from app.main import app as fastapi_app
    anterior = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_current_user] = lambda: {
        "role": role, "sub": sub,
    }
    try:
        yield
    finally:
        if anterior is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = anterior


def _instance_id_canonico_apos_primeira_transacao(outer_conn) -> str:
    """Retorna o instance_id_canonico após a 1ª transação clínica ter
    populado meta_instalacao via get_instance_id_conn() (chamada de dentro
    de registrar_evento_ledger).

    USAR APENAS APÓS o primeiro POST que grava em algum *_eventos.

    P1.1 CODEX rodada 1: ler antes da 1ª transação retornaria None porque
    conftest.py:37 desliga _lifespan_bootstrap. A linha só existe depois
    que get_instance_id_conn() é chamado pela primeira vez dentro de uma
    request handler.
    """
    cur = outer_conn.cursor()
    cur.execute(
        "SELECT valor FROM meta_instalacao WHERE chave = 'instance_id'"
    )
    row = cur.fetchone()
    assert row is not None, (
        "meta_instalacao.instance_id ausente — esperado preenchido pela "
        "primeira chamada a registrar_evento_ledger. Confirme que o POST "
        "anterior gravou em algum *_eventos."
    )
    return row[0]


# ===========================================================================
# C1 — Cadeia clínica completa em uma sessão de paciente (+ atomização)
# ===========================================================================

def test_cadeia_clinica_completa_preserva_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
) -> None:
    """C1 (absorve C2 — múltiplas transações no mesmo protocolo).

    Cadeia: prescrição → pedido_exame → agendamento → realizar → laudo
    (encadeado via pedido_protocolo) → tokens/atomizar sobre a prescrição.

    Asserções:
      I1+I2 nos 4 ledgers (prescricao_, pedido_exame_, agendamento_,
        laudo_eventos)
      I3   no outbox usando (objeto_tipo, objeto_id) — NÃO `protocolo`
      Coerência clínica: laudo.pedido_id = pedido_id (cadeia real)
    """
    token = obter_token_prescritor(client, seed_usuario)

    # (1) 1ª transação — POST /prescricoes (popula meta_instalacao)
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_prescricao = r.json()["protocolo"]

    # (2) Capturar canônico AGORA (após a 1ª transação)
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )
    assert _eh_uuid_v4(instance_id_canonico), (
        f"instance_id canônico inválido: {instance_id_canonico!r}"
    )

    # (3) POST /pedidos-exame (mesmo paciente)
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    body_pedido = r.json()
    proto_pedido = body_pedido["protocolo"]
    pedido_id = body_pedido["id"]

    # (4) POST /agendamentos vinculado ao pedido
    payload_ag = {**_AGENDAMENTO_BASE, "pedido_protocolo": proto_pedido}
    r = client.post("/agendamentos", json=payload_ag,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_agendamento = r.json()["protocolo"]

    # (5) Realizar agendamento — transita itens do pedido para 'coletado'
    r = client.post(f"/agendamentos/{proto_agendamento}/realizar",
                    headers=_headers(token))
    assert r.status_code == 200, r.text

    # (6) POST /laudos com pedido_protocolo apontando ao pedido (cadeia real)
    payload_laudo = {**_PAYLOAD_LAUDO, "pedido_protocolo": proto_pedido}
    r = client.post("/laudos", json=payload_laudo, headers=_headers(token))
    assert r.status_code == 201, r.text
    body_laudo = r.json()
    proto_laudo = body_laudo["protocolo"]

    # (7) POST /prescricoes/{proto}/tokens/atomizar (paciente — 2ª transação
    #     sobre o protocolo da prescrição — absorção de C2)
    with _override_role("paciente", sub=SEED_PACIENTE_CPF):
        r = client.post(
            f"/prescricoes/{proto_prescricao}/tokens/atomizar",
            json={"validade_minutos": 60},
            headers=_headers(token),
        )
    assert r.status_code == 201, r.text

    # ----- I1 + I2: cada um dos 4 ledgers tem exatamente 1 instance_id, =
    # canônico, formato UUID v4 ---------------------------------------------
    with outer_conn.cursor() as cur:
        for tabela in (
            "prescricao_eventos",
            "pedido_exame_eventos",
            "agendamento_eventos",
            "laudo_eventos",
        ):
            cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
            rows = cur.fetchall()
            assert len(rows) == 1, (
                f"{tabela}: esperado 1 instance_id distinto, recebi {rows}"
            )
            assert rows[0][0] == instance_id_canonico, (
                f"{tabela}: instance_id divergente do canônico: "
                f"{rows[0][0]!r} != {instance_id_canonico!r}"
            )
            assert _eh_uuid_v4(rows[0][0])

        # ----- I3: outbox compartilha instance_id (usar objeto_id) ---------
        for objeto_tipo, objeto_id in (
            ("prescricao",   proto_prescricao),
            ("pedido_exame", proto_pedido),
            ("agendamento",  proto_agendamento),
            ("laudo",        proto_laudo),
        ):
            cur.execute(
                """
                SELECT instance_id
                  FROM eventos_publicacao
                 WHERE objeto_tipo = %s AND objeto_id = %s
                """,
                (objeto_tipo, objeto_id),
            )
            iids_outbox = {r[0] for r in cur.fetchall()}
            assert iids_outbox, (
                f"outbox ({objeto_tipo}, {objeto_id}) sem nenhum row"
            )
            assert iids_outbox == {instance_id_canonico}, (
                f"outbox {objeto_tipo}/{objeto_id}: instance_ids divergentes: "
                f"{iids_outbox} != {{ {instance_id_canonico!r} }}"
            )

        # ----- Coerência clínica: laudo.pedido_id aponta ao pedido criado --
        cur.execute(
            "SELECT pedido_id FROM laudos WHERE protocolo = %s",
            (proto_laudo,),
        )
        row = cur.fetchone()
        assert row is not None, "laudo não encontrado"
        assert row[0] == pedido_id, (
            f"laudo.pedido_id ({row[0]}) != pedido_id criado em (3) ({pedido_id})"
        )

        # ----- Coerência adicional (C2 absorvido): >=2 eventos na prescrição
        # confirmam múltiplas transações sobre o mesmo protocolo, todos com
        # mesmo instance_id ------------------------------------------------
        cur.execute(
            """
            SELECT COUNT(*)
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
            """,
            (proto_prescricao,),
        )
        n_eventos_prescricao = cur.fetchone()[0]
        assert n_eventos_prescricao >= 2, (
            f"esperado >=2 eventos sobre {proto_prescricao} (emissão + "
            f"atomização), recebi {n_eventos_prescricao}"
        )


# ===========================================================================
# C3 — Cadeia diagnóstica (pedido → agendamento → coleta → laudo)
# ===========================================================================

def test_cadeia_diagnostica_preserva_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
) -> None:
    """C3 — valida I5 explicitamente: o outlier de schema em
    `agendamento_eventos` (coluna `evento`/`payload`) é transparente.

    Cadeia: pedido_exame → agendamento → realizar → laudo (encadeado
    via pedido_protocolo).
    """
    token = obter_token_prescritor(client, seed_usuario)

    # (1) 1ª transação — POST /pedidos-exame
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    body_pedido = r.json()
    proto_pedido = body_pedido["protocolo"]
    pedido_id = body_pedido["id"]

    # (2) Capturar canônico
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )

    # (3) POST /agendamentos vinculado
    payload_ag = {**_AGENDAMENTO_BASE, "pedido_protocolo": proto_pedido}
    r = client.post("/agendamentos", json=payload_ag,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_agendamento = r.json()["protocolo"]

    # (4) Realizar agendamento
    r = client.post(f"/agendamentos/{proto_agendamento}/realizar",
                    headers=_headers(token))
    assert r.status_code == 200, r.text

    # (5) POST /laudos com pedido_protocolo apontando ao pedido (1)
    payload_laudo = {**_PAYLOAD_LAUDO, "pedido_protocolo": proto_pedido}
    r = client.post("/laudos", json=payload_laudo, headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_laudo = r.json()["protocolo"]

    # ----- I1 + I2 + I5: agendamento_eventos usa coluna `evento`
    # (outlier) — instance_id ainda fica correto ---------------------------
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ae.evento, ae.instance_id
              FROM agendamento_eventos ae
              JOIN agendamentos a ON a.id = ae.agendamento_id
             WHERE a.protocolo = %s
             ORDER BY ae.id ASC
            """,
            (proto_agendamento,),
        )
        rows_ag = cur.fetchall()
        assert rows_ag, "nenhum evento de agendamento gravado"
        eventos_ag = {r[0] for r in rows_ag}
        assert "agendamento_criado" in eventos_ag
        assert "agendamento_realizado" in eventos_ag
        for evento, iid in rows_ag:
            assert iid == instance_id_canonico, (
                f"evento {evento!r}: instance_id divergente: "
                f"{iid!r} != {instance_id_canonico!r}"
            )
            assert _eh_uuid_v4(iid)

        # ----- I1 + I2 nos 3 ledgers da cadeia ----------------------------
        for tabela in (
            "pedido_exame_eventos",
            "agendamento_eventos",
            "laudo_eventos",
        ):
            cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == instance_id_canonico

        # ----- Coerência clínica: laudo.pedido_id = pedido_id ----------
        cur.execute(
            "SELECT pedido_id FROM laudos WHERE protocolo = %s",
            (proto_laudo,),
        )
        assert cur.fetchone()[0] == pedido_id


# ===========================================================================
# C5 — Smoke agregado nos 5 ledgers (pedido_A + pedido_B separados)
# ===========================================================================

def test_smoke_agregado_5_ledgers_um_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
) -> None:
    """C5 — invariante crítica: a UNION dos 5 ledgers retorna 1 único
    instance_id = instance_id_canonico.

    P2.2 CODEX rodada 1: pedido_B separado porque
    /pedidos-exame/{proto}/circulacao exige item em status `pendente`,
    mas POST /agendamentos move itens de pedido_A para `agendado`.
    """
    token = obter_token_prescritor(client, seed_usuario)

    # (1) 1ª transação — POST /prescricoes
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    prescricao_id = r.json()["id"]

    # (2) Capturar canônico
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )

    # (3) pedido_A — vira agendamento
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    body_A = r.json()
    proto_pedido_A = body_A["protocolo"]
    pedido_A_id = body_A["id"]

    # (4) pedido_B — item permanece pendente para alimentar a circulação
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_B,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    body_B = r.json()
    proto_pedido_B = body_B["protocolo"]
    pedido_B_id = body_B["id"]

    # (5) Agendamento sobre pedido_A
    payload_ag = {**_AGENDAMENTO_BASE, "pedido_protocolo": proto_pedido_A}
    r = client.post("/agendamentos", json=payload_ag,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_agendamento = r.json()["protocolo"]

    # (6) Laudo independente (não precisa de pedido_protocolo aqui — C5 é
    # smoke, cobertura de encadeamento real está em C1/C3)
    r = client.post("/laudos", json=_PAYLOAD_LAUDO, headers=_headers(token))
    assert r.status_code == 201, r.text
    laudo_id = r.json()["id"]

    # (7) Circulação diagnóstica sobre pedido_B (item ainda pendente)
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens WHERE pedido_id = %s "
            "ORDER BY id LIMIT 1",
            (pedido_B_id,),
        )
        item_B_id = cur.fetchone()[0]
    with _override_role("admin"):
        r = client.post(
            f"/pedidos-exame/{proto_pedido_B}/circulacao",
            json={"org_id": "LAB-CIRC-4E", "unidade_id": "UNI-CIRC-4E",
                  "item_ids": [item_B_id]},
            headers=_headers(token),
        )
    assert r.status_code == 201, r.text
    proto_circulacao = r.json()["protocolo"]

    # ----- Invariante crítica: UNION dos 5 ledgers tem 1 só instance_id ---
    with outer_conn.cursor() as cur:
        # Resolve IDs faltantes pelos protocolos (agendamento e circulação
        # devolvem apenas o protocolo na resposta).
        cur.execute(
            "SELECT id FROM agendamentos WHERE protocolo = %s",
            (proto_agendamento,),
        )
        agendamento_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id FROM circulacoes_diagnosticas WHERE protocolo = %s",
            (proto_circulacao,),
        )
        circulacao_id = cur.fetchone()[0]

        # I1 focal (4E.2 §3.1.7): apenas eventos dos objetos criados neste
        # teste — mitiga falso positivo se o banco de teste acumular rows
        # pré-4D.1 com instance_id NULL em ledgers históricos. Cada ledger
        # subdomínio usa o nome da FK específica do objeto (não há
        # objeto_id genérico nos ledgers internos).
        objetos_do_teste = [
            ("prescricao_eventos",             "prescricao_id",  [prescricao_id]),
            ("pedido_exame_eventos",           "pedido_id",      [pedido_A_id, pedido_B_id]),
            ("laudo_eventos",                  "laudo_id",       [laudo_id]),
            ("agendamento_eventos",            "agendamento_id", [agendamento_id]),
            ("circulacao_diagnostica_eventos", "circulacao_id",  [circulacao_id]),
        ]
        for tabela, fk, ids in objetos_do_teste:
            cur.execute(
                f"SELECT COUNT(*) FROM {tabela} "
                f"WHERE {fk} = ANY(%s) AND instance_id IS NULL",
                (ids,),
            )
            nulls = cur.fetchone()[0]
            assert nulls == 0, (
                f"{tabela}: {nulls} eventos dos objetos criados neste teste "
                f"sem instance_id ({fk}={ids}). Bug em código novo — "
                "não é drift histórico."
            )

        # I2 agregada: SELECT DISTINCT sobre UNION = 1 linha = canônico
        cur.execute(
            """
            SELECT DISTINCT instance_id FROM (
                SELECT instance_id FROM prescricao_eventos
                UNION ALL
                SELECT instance_id FROM pedido_exame_eventos
                UNION ALL
                SELECT instance_id FROM laudo_eventos
                UNION ALL
                SELECT instance_id FROM agendamento_eventos
                UNION ALL
                SELECT instance_id FROM circulacao_diagnostica_eventos
            ) AS uniao
            """
        )
        rows = cur.fetchall()
        assert len(rows) == 1, (
            f"esperado 1 instance_id distinto na UNION dos 5 ledgers, "
            f"recebi {len(rows)}: {rows}"
        )
        assert rows[0][0] == instance_id_canonico
        assert _eh_uuid_v4(rows[0][0])


# ===========================================================================
# C4 — Remarcação derivada preserva invariantes
# ===========================================================================

def test_remarcacao_derivada_preserva_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
) -> None:
    """C4 — agendamento_derivado por remarcação carrega o mesmo
    instance_id do original. P3.2 CODEX: asserção primária é
    vocabulário de eventos + origem_agendamento_id, NÃO criado_em<1s.
    """
    token = obter_token_prescritor(client, seed_usuario)

    # (1) Setup: pedido + 1ª transação (POST /agendamentos)
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_pedido = r.json()["protocolo"]

    payload_ag = {**_AGENDAMENTO_BASE, "pedido_protocolo": proto_pedido}
    r = client.post("/agendamentos", json=payload_ag,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_original = r.json()["protocolo"]

    # (2) Capturar canônico
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )

    # (3) Remarcar — gera protocolo_novo + 3 eventos na mesma transação
    r = client.post(
        f"/agendamentos/{proto_original}/remarcar",
        json={"data_hora": "2026-05-25T14:00:00"},
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    proto_derivado = r.json()["protocolo_novo"]

    with outer_conn.cursor() as cur:
        # Resolver IDs dos dois agendamentos
        cur.execute(
            "SELECT id, protocolo FROM agendamentos "
            "WHERE protocolo IN (%s, %s) ORDER BY id ASC",
            (proto_original, proto_derivado),
        )
        rows = cur.fetchall()
        assert len(rows) == 2
        ag_orig_id, ag_deriv_id = rows[0][0], rows[1][0]

        # ----- I1 + I2: todos os eventos do orig + derivado têm 1 só
        # instance_id, igual ao canônico, UUID v4 válido --------------------
        cur.execute(
            """
            SELECT DISTINCT instance_id
              FROM agendamento_eventos
             WHERE agendamento_id IN (%s, %s)
            """,
            (ag_orig_id, ag_deriv_id),
        )
        rows = cur.fetchall()
        assert len(rows) == 1, (
            f"esperado 1 instance_id distinto entre original e derivado, "
            f"recebi {rows}"
        )
        assert rows[0][0] == instance_id_canonico
        assert _eh_uuid_v4(rows[0][0])

        # ----- Coerência clínica robusta (P3.2 — NÃO usar criado_em<1s) ----
        cur.execute(
            "SELECT origem_agendamento_id FROM agendamentos WHERE id = %s",
            (ag_deriv_id,),
        )
        assert cur.fetchone()[0] == ag_orig_id, (
            "agendamento derivado não aponta para original via "
            "origem_agendamento_id"
        )

        cur.execute(
            """
            SELECT evento
              FROM agendamento_eventos
             WHERE agendamento_id IN (%s, %s)
             ORDER BY id ASC
            """,
            (ag_orig_id, ag_deriv_id),
        )
        eventos = [r[0] for r in cur.fetchall()]
        assert "agendamento_criado" in eventos, (
            f"evento agendamento_criado ausente em {eventos}"
        )
        # Pelo menos um dos vocabulários da remarcação deve aparecer
        # (vocabulário em agendamentos.py:506-565)
        assert (
            "agendamento_remarcado" in eventos
            or "agendamento_cancelado" in eventos
        ), f"nenhum evento de remarcação em {eventos}"


# ===========================================================================
# C5b — Override PICSAUDE_INSTANCE_ID em dev (OBRIGATÓRIO)
# ===========================================================================

def test_override_instance_id_env_var(
    client, outer_conn, seed_usuario, seed_paciente, monkeypatch,
) -> None:
    """C5b — env override (`PICSAUDE_INSTANCE_ID`) força instance_id em
    todos os ledgers. Comparação DIRETA contra UUID forçado conhecido pelo
    teste — NÃO ler meta_instalacao (contrato em
    `test_ledger_helper.py:674`: override por env não toca DB).

    Padrão monkeypatch: setenv ANTES de qualquer request (env override é
    lido lazy dentro de `get_instance_id_conn` em cada handler).
    """
    INSTANCE_ID_FORCADO = "deadbeef-dead-4eef-beef-deadbeefcafe"

    monkeypatch.setenv("PICSAUDE_ENV", "dev")
    monkeypatch.setenv("PICSAUDE_INSTANCE_ID", INSTANCE_ID_FORCADO)

    token = obter_token_prescritor(client, seed_usuario)

    # 3 fluxos curtos tocando ledgers distintos
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO,
                    headers=_headers(token))
    assert r.status_code == 201, r.text

    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text

    r = client.post("/laudos", json=_PAYLOAD_LAUDO, headers=_headers(token))
    assert r.status_code == 201, r.text

    # Comparar DIRETO contra UUID forçado (sem ler meta_instalacao)
    with outer_conn.cursor() as cur:
        for tabela in (
            "prescricao_eventos",
            "pedido_exame_eventos",
            "laudo_eventos",
        ):
            cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
            rows = cur.fetchall()
            assert rows, (
                f"{tabela} vazio — esperado >=1 row após POST correspondente"
            )
            iids = {row[0] for row in rows}
            assert iids == {INSTANCE_ID_FORCADO}, (
                f"{tabela}: esperado apenas {{{INSTANCE_ID_FORCADO!r}}}, "
                f"recebi {iids}"
            )
            for iid in iids:
                assert _eh_uuid_v4(iid)


# ===========================================================================
# C6 (OPCIONAL) — Coerência ledger+outbox em cadeia multi-objeto
# ===========================================================================

def test_ledger_outbox_multiobjeto_compartilham_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
) -> None:
    """C6 (opcional) — valida I3 explicitamente em cadeia transversal.

    Limitado a 4 subdomínios com outbox adjacente (decisão CODEX rodada 1):
    prescricao, pedido_exame, laudo, agendamento. Circulação diagnóstica
    NÃO tem outbox adjacente na 4D.2, portanto fora de escopo.

    Para cada row em eventos_publicacao desses tipos, validar que o
    instance_id é igual ao do *_eventos correspondente (via
    objeto_id ↔ protocolo).
    """
    token = obter_token_prescritor(client, seed_usuario)

    # (1) 1ª transação — POST /prescricoes
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_prescricao = r.json()["protocolo"]

    # (2) Capturar canônico
    instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(
        outer_conn
    )

    # (3) Cadeia transversal: pedido + laudo + agendamento (4 objetos com outbox)
    r = client.post("/pedidos-exame", json=_PAYLOAD_PEDIDO_A,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_pedido = r.json()["protocolo"]

    r = client.post("/laudos", json=_PAYLOAD_LAUDO, headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_laudo = r.json()["protocolo"]

    payload_ag = {**_AGENDAMENTO_BASE, "pedido_protocolo": proto_pedido}
    r = client.post("/agendamentos", json=payload_ag,
                    headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_agendamento = r.json()["protocolo"]

    # Nenhum dos 4 ledgers tem coluna `protocolo` direto; todos referenciam
    # o objeto principal via <tipo>_id, então o JOIN é necessário sempre.
    SQL_LEDGER_POR_TIPO = {
        "prescricao": (
            "SELECT DISTINCT pe.instance_id "
            "  FROM prescricao_eventos pe "
            "  JOIN prescricoes p ON p.id = pe.prescricao_id "
            " WHERE p.protocolo = %s"
        ),
        "pedido_exame": (
            "SELECT DISTINCT pe.instance_id "
            "  FROM pedido_exame_eventos pe "
            "  JOIN pedidos_exame x ON x.id = pe.pedido_id "
            " WHERE x.protocolo = %s"
        ),
        "laudo": (
            "SELECT DISTINCT le.instance_id "
            "  FROM laudo_eventos le "
            "  JOIN laudos l ON l.id = le.laudo_id "
            " WHERE l.protocolo = %s"
        ),
        "agendamento": (
            "SELECT DISTINCT ae.instance_id "
            "  FROM agendamento_eventos ae "
            "  JOIN agendamentos a ON a.id = ae.agendamento_id "
            " WHERE a.protocolo = %s"
        ),
        # circulacao_diagnostica fora — sem outbox adjacente (I3 refinada)
    }

    # Filtra pelos protocolos criados POR ESTE teste — `picsaude_test`
    # carrega pollution histórica de rodadas anteriores (210 rows residuais
    # com instance_id NULL, pré-4D.1 ou de testes não-savepoint). Drift
    # operacional do banco de teste, registrado para 4E.2.
    objetos_criados = (
        ("prescricao",   proto_prescricao),
        ("pedido_exame", proto_pedido),
        ("laudo",        proto_laudo),
        ("agendamento",  proto_agendamento),
    )

    with outer_conn.cursor() as cur:
        for objeto_tipo, objeto_id in objetos_criados:
            cur.execute(
                """
                SELECT DISTINCT instance_id
                  FROM eventos_publicacao
                 WHERE objeto_tipo = %s AND objeto_id = %s
                """,
                (objeto_tipo, objeto_id),
            )
            outbox_rows = cur.fetchall()
            assert outbox_rows, (
                f"outbox sem rows para ({objeto_tipo}, {objeto_id})"
            )
            assert len(outbox_rows) == 1, (
                f"outbox {objeto_tipo}/{objeto_id}: instance_ids divergentes "
                f"entre eventos do mesmo objeto: {outbox_rows}"
            )
            iid_outbox = outbox_rows[0][0]
            assert iid_outbox == instance_id_canonico, (
                f"outbox {objeto_tipo}/{objeto_id}: divergente "
                f"({iid_outbox!r} != {instance_id_canonico!r})"
            )

            cur.execute(SQL_LEDGER_POR_TIPO[objeto_tipo], (objeto_id,))
            ledger_rows = cur.fetchall()
            assert len(ledger_rows) == 1, (
                f"{objeto_tipo}/{objeto_id}: esperado 1 instance_id "
                f"distinto no ledger, recebi {ledger_rows}"
            )
            assert ledger_rows[0][0] == iid_outbox == instance_id_canonico
