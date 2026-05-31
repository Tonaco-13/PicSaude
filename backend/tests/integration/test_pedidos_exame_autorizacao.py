"""TICKET-5C-BIS-A — Autorização mínima de ownership em pedidos_exame.py.

Espelha o §9 (critérios de aceite). Mirror de test_custodia_autorizacao.py
(precedente do 5C): autenticação via criar_access_token forjado para papéis/
identidades distintas; isolamento por outer tx (conftest de integração).

Cobertura:
  - Padrão A (criar/fisica): CNS payload ≠ JWT → 403 prescritor_mismatch + rollback.
  - Padrão B (GET/agendar/cancelar/resultado/qr): não-dono → 403; dono → 2xx.
  - Padrão C (pdf): reusa row; não-dono → 403; dono → 2xx.
  - admin (P1): bypass sem ownership em todos os padrões; sub não-clínico não quebra.
  - dispensador (5 casos §8.1/§8.4): antes do agendar, CNPJ certo, CNPJ errado,
    CNPJ mascarado no agendar (opção A), custódia atual × histórica.
  - paciente (custodia/encerrar): CPF ≠ dono → 403; dono → 2xx.
  - Ordenação anti-leak (#52): 403 precede 422 de estado; mensagem não vaza estado.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Identidades de teste
# ---------------------------------------------------------------------------

_CNS_PRESCRITOR_B = "999888777666555"      # 15 dígitos — prescritor não-dono
_CPF_PACIENTE_B = "99988877766"            # 11 dígitos — paciente não-dono
_CNPJ_A = "12345678000195"                 # 14 dígitos — prestador agendado
_CNPJ_A_MASCARADO = "12.345.678/0001-95"   # mesma raiz, com máscara (§8.4)
_CNPJ_B = "98765432000110"                 # 14 dígitos — outro prestador

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE TICKET13",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}

_TABELAS_PEDIDO = ("pedidos_exame", "pedido_exame_eventos", "pedido_exame_itens")


# ---------------------------------------------------------------------------
# Helpers de autenticação / fluxo
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _contagens(outer_conn, tabelas=_TABELAS_PEDIDO) -> dict:
    out: dict[str, int] = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _criar_pedido(client, token_dono: str, **overrides) -> str:
    """Cria um pedido pertencente ao dono do token (CNS do payload == JWT)."""
    payload = {**_PAYLOAD_BASE, **overrides}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_dono))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _item_id(client, token_dono: str, protocolo: str) -> int:
    r = client.get(f"/pedidos-exame/{protocolo}", headers=_headers(token_dono))
    assert r.status_code == 200, r.text
    return r.json()["itens"][0]["id"]


def _agendar(client, token, protocolo: str, cnpj: str):
    return client.post(
        f"/pedidos-exame/{protocolo}/agendar",
        json={"cnpj_prestador": cnpj},
        headers=_headers(token),
    )


def _pedido_id(outer_conn, protocolo: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM pedidos_exame WHERE protocolo = %s", (protocolo,))
        return cur.fetchone()[0]


# ===========================================================================
# Padrão A — criar / fisica (CNS payload ≠ JWT)
# ===========================================================================

def test_a_criar_cns_mismatch_403_com_rollback(client, outer_conn, seed_usuario, seed_paciente):
    """Prescritor autenticado A declara CNS de B no payload → 403 + zero escrita."""
    token_a = obter_token_prescritor(client, seed_usuario)  # JWT.sub = CNS_A (seed)
    baseline = _contagens(outer_conn)

    payload = {**_PAYLOAD_BASE, "cns_prescritor": _CNS_PRESCRITOR_B}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_a))

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "prescritor_mismatch"

    depois = _contagens(outer_conn)
    for t in _TABELAS_PEDIDO:
        assert depois[t] == baseline[t], f"{t}: rollback incompleto"


def test_a_fisica_cns_mismatch_403_com_rollback(client, outer_conn, seed_usuario):
    token_a = obter_token_prescritor(client, seed_usuario)
    baseline = _contagens(outer_conn)

    payload = {
        "cns_prescritor": _CNS_PRESCRITOR_B,
        "nome_prescritor": "DR. B",
        "nome_paciente": "PACIENTE FISICO",
        "prioridade": "rotina",
        "itens": [{"nome_exame": "GLICEMIA", "quantidade": 1}],
    }
    r = client.post("/pedidos-exame/fisica", json=payload, headers=_headers(token_a))

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "prescritor_mismatch"

    depois = _contagens(outer_conn)
    for t in _TABELAS_PEDIDO:
        assert depois[t] == baseline[t], f"{t}: rollback incompleto"


# ===========================================================================
# Padrão B — GET / qr / agendar / cancelar / resultado (prescritor)
# ===========================================================================

def test_b_get_nao_dono_403_dono_200(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    rb = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNS_PRESCRITOR_B, "prescritor")))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"

    ra = client.get(f"/pedidos-exame/{proto}", headers=_headers(token_a))
    assert ra.status_code == 200, ra.text


def test_b_qr_nao_dono_403_dono_200(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    rb = client.get(f"/pedidos-exame/{proto}/qr", headers=_headers(_token(_CNS_PRESCRITOR_B, "prescritor")))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"

    ra = client.get(f"/pedidos-exame/{proto}/qr", headers=_headers(token_a))
    assert ra.status_code == 200, ra.text


def test_b_agendar_nao_dono_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    r = _agendar(client, _token(_CNS_PRESCRITOR_B, "prescritor"), proto, _CNPJ_A)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_b_cancelar_nao_dono_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    r = client.post(
        f"/pedidos-exame/{proto}/cancelar", json={"motivo": "x"},
        headers=_headers(_token(_CNS_PRESCRITOR_B, "prescritor")),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_b_resultado_nao_dono_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    item_id = _item_id(client, token_a, proto)

    r = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado", json={"resultado_resumo": "ok"},
        headers=_headers(_token(_CNS_PRESCRITOR_B, "prescritor")),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


# ===========================================================================
# Padrão C — pdf (reusa row)
# ===========================================================================

def test_pdf_nao_dono_403_dono_200(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    rb = client.get(f"/pedidos-exame/{proto}/pdf", headers=_headers(_token(_CNS_PRESCRITOR_B, "prescritor")))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"

    ra = client.get(f"/pedidos-exame/{proto}/pdf", headers=_headers(token_a))
    assert ra.status_code == 200, ra.text


# ===========================================================================
# admin (P1) — bypass sem ownership, sub não-clínico não quebra o Helper 2
# ===========================================================================

def test_admin_bypass_em_todos_os_padroes(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    # sub SEM dígitos → ident == "" no Helper 2; admin nunca compara (bypass).
    adm = _token("admin", "admin", "ADMIN")

    # B (GET) · D (custodia) · C (pdf) · B (qr)
    assert client.get(f"/pedidos-exame/{proto}", headers=_headers(adm)).status_code == 200
    assert client.get(f"/pedidos-exame/{proto}/custodia", headers=_headers(adm)).status_code == 200
    assert client.get(f"/pedidos-exame/{proto}/pdf", headers=_headers(adm)).status_code == 200
    assert client.get(f"/pedidos-exame/{proto}/qr", headers=_headers(adm)).status_code == 200

    # E (mutação) — admin agenda e cancela sem ownership.
    r_ag = _agendar(client, adm, proto, _CNPJ_A)
    assert r_ag.status_code == 201, r_ag.text
    r_cancel = client.post(
        f"/pedidos-exame/{proto}/cancelar", json={"motivo": "admin"}, headers=_headers(adm)
    )
    assert r_cancel.status_code == 200, r_cancel.text


# ===========================================================================
# dispensador — 5 casos (§8.1 + §8.4). Custódia criada pelo agendar REAL.
# ===========================================================================

def test_disp_caso1_antes_de_agendar_403(client, seed_usuario, seed_paciente):
    """Sem custódia de prestador → 403. Variante: custódia 'paciente' não conta."""
    token_a = obter_token_prescritor(client, seed_usuario)

    # (a) pedido emitido, sem agendar nem carteira.
    proto = _criar_pedido(client, token_a)
    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"

    # (b) pedido com custódia para='paciente' (carteira) — não é prestador.
    proto2 = _criar_pedido(client, token_a, enviar_ao_paciente=True)
    r2 = client.get(f"/pedidos-exame/{proto2}", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert r2.status_code == 403, r2.text


def test_disp_caso2_cnpj_agendado_2xx(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    assert _agendar(client, token_a, proto, _CNPJ_A).status_code == 201

    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert r.status_code == 200, r.text


def test_disp_caso3_cnpj_diferente_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    assert _agendar(client, token_a, proto, _CNPJ_A).status_code == 201

    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_disp_caso4_cnpj_mascarado_no_agendar_2xx(client, seed_usuario, seed_paciente):
    """§8.4 opção A: agendar com CNPJ mascarado; dispensador com mesma raiz → 2xx.

    Falharia se a normalização-na-escrita não fosse aplicada (custódia guardaria
    o CNPJ mascarado e não casaria com o ident normalizado do JWT).
    """
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    assert _agendar(client, token_a, proto, _CNPJ_A_MASCARADO).status_code == 201

    # dispensador autentica com o CNPJ em qualquer formatação.
    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_A_MASCARADO, "dispensador")))
    assert r.status_code == 200, r.text


def test_disp_coletar_cnpj_agendado_2xx_cnpj_diferente_403(client, seed_usuario, seed_paciente):
    """Endpoint #6: dispensador só coleta se for o prestador na custódia atual."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    item_id = _item_id(client, token_a, proto)
    assert _agendar(client, token_a, proto, _CNPJ_A).status_code == 201

    errado = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
        headers=_headers(_token(_CNPJ_B, "dispensador")),
    )
    assert errado.status_code == 403, errado.text
    assert errado.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"

    certo = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
        headers=_headers(_token(_CNPJ_A, "dispensador")),
    )
    assert certo.status_code == 201, certo.text


def test_disp_caso5_custodia_atual_nao_historica(client, outer_conn, seed_usuario, seed_paciente):
    """§8.1: custódia X (histórica) seguida de Y (atual) → Y 2xx, X 403.

    A custódia atual é a de maior id (ORDER BY id DESC). O fluxo de endpoints do
    MVP não reexpõe re-transferência de prestador; simulamos a linha histórica
    com um 2º INSERT pedido-nível direto (CNPJ já normalizado, como o agendar grava).
    """
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    # X entra pelo agendar real (normaliza na escrita).
    assert _agendar(client, token_a, proto, _CNPJ_A).status_code == 201

    pedido_id = _pedido_id(outer_conn, proto)
    # Y entra como custódia pedido-nível mais recente (id maior).
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pedido_exame_custodia
              (pedido_id, item_id, de, para, transferido_em, dados_json)
            VALUES (%s, NULL, 'paciente', %s, %s, %s)
            """,
            (
                pedido_id,
                _CNPJ_B,
                datetime.utcnow(),
                '{"motivo": "re-transferencia historica (teste)"}',
            ),
        )

    # Y (atual) → 200
    ry = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_B, "dispensador")))
    assert ry.status_code == 200, ry.text

    # X (histórico, perdeu a custódia atual) → 403
    rx = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert rx.status_code == 403, rx.text
    assert rx.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


# ===========================================================================
# paciente — custodia / encerrar
# ===========================================================================

def test_paciente_custodia_dono_200_nao_dono_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    # dono (CPF do paciente do pedido) → 200
    rd = client.get(
        f"/pedidos-exame/{proto}/custodia",
        headers=_headers(_token(SEED_PACIENTE_CPF, "paciente")),
    )
    assert rd.status_code == 200, rd.text

    # não-dono → 403
    rn = client.get(
        f"/pedidos-exame/{proto}/custodia",
        headers=_headers(_token(_CPF_PACIENTE_B, "paciente")),
    )
    assert rn.status_code == 403, rn.text
    assert rn.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_paciente_encerrar_nao_dono_403(client, seed_usuario, seed_paciente):
    """Não-dono recebe 403 mesmo com o pedido fora de 'resultado_disponivel'
    (ownership precede o 422 de estado — anti-leak #52)."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)

    r = client.post(
        f"/pedidos-exame/{proto}/encerrar",
        headers=_headers(_token(_CPF_PACIENTE_B, "paciente")),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


# ===========================================================================
# Ordenação anti-leak (#52) — 403 precede 422 e não vaza estado
# ===========================================================================

def test_antileak_403_precede_422_de_estado(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    # Dono leva a pedido a estado terminal (cancelado).
    assert client.post(
        f"/pedidos-exame/{proto}/cancelar", json={"motivo": "fim"}, headers=_headers(token_a)
    ).status_code == 200

    # Não-dono tenta agendar pedido terminal: deve ver 403 (ownership), NÃO 422.
    r = _agendar(client, _token(_CNS_PRESCRITOR_B, "prescritor"), proto, _CNPJ_A)
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["codigo"] == "nao_e_dono_do_pedido_exame"
    # A mensagem do 403 não revela o estado nem 'cancelado'.
    assert "cancel" not in detail["mensagem"].lower()
    assert "terminal" not in detail["mensagem"].lower()


# ===========================================================================
# Fluxo feliz do dono — owner 2xx em agendar/coletar/resultado/encerrar
# ===========================================================================

def test_fluxo_feliz_dono_completo(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_a)
    item_id = _item_id(client, token_a, proto)

    assert _agendar(client, token_a, proto, _CNPJ_A).status_code == 201

    r_col = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar", headers=_headers(token_a)
    )
    assert r_col.status_code == 201, r_col.text

    r_res = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json={"resultado_resumo": "normal"}, headers=_headers(token_a),
    )
    assert r_res.status_code == 201, r_res.text
    assert r_res.json()["status_pedido"] == "resultado_disponivel"

    r_enc = client.post(f"/pedidos-exame/{proto}/encerrar", headers=_headers(token_a))
    assert r_enc.status_code == 200, r_enc.text
    assert r_enc.json()["status"] == "encerrado"
