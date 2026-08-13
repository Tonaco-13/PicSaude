"""TICKET-B — "Enviar à bancada": POST /pedidos-exame/{proto}/itens/{id}/em-analise.

Materializa `coletado → em_analise`, que o contrato já previa (states_exame.py) mas
nenhum endpoint persistia: o `/resultado` emitia `pedido_em_analise` como marco e
escrevia `resultado_disponivel` direto — o item nunca REPOUSAVA na bancada.

Cobertura (critérios de aceite do ticket):
  - Caminho feliz: item `coletado` → 200 → `em_analise` + evento no ledger com
    `item_id` e `setor`; pedido re-derivado para `em_analise`.
  - Corpo ausente (setor opcional) → 200 com `setor: null`.
  - Transição inválida: item `agendado` → 422 com mensagem.
  - RBAC: paciente e prescritor barrados pelo papel (403); dispensador de outra
    unidade barrado pela POSSE (403 com `nao_e_dono_do_pedido_exame`).
  - Ordenação anti-leak (#52): 403 de posse precede 422 de estado.
  - Encadeamento com `/resultado` (é o que o Ticket G consome) — sem duplicar o
    evento `pedido_em_analise`.
  - Ledger INSERT-only: o `pedido_coletado` anterior permanece, na ordem.

Espelha os helpers de test_pedidos_exame_autorizacao.py: custódia SEMPRE criada
pelo `POST /agendar` real (nunca INSERT direto) e dispensador autenticado por JWT
cujo `sub` é o CNPJ.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

import json

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Identidades de teste (mesmas do suite de autorização — mesmo subdomínio)
# ---------------------------------------------------------------------------

_CNPJ_A = "12345678000195"                 # 14 dígitos — prestador agendado
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


# ---------------------------------------------------------------------------
# Helpers de autenticação / fluxo
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _criar_pedido(client, token_dono: str) -> str:
    r = client.post("/pedidos-exame", json=_PAYLOAD_BASE, headers=_headers(token_dono))
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


def _eventos(outer_conn, protocolo: str) -> list[tuple]:
    """(tipo_evento, dados_json) do pedido, na ordem de gravação."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.tipo_evento, e.dados_json FROM pedido_exame_eventos e "
            "JOIN pedidos_exame p ON p.id = e.pedido_id "
            "WHERE p.protocolo = %s ORDER BY e.id",
            (protocolo,),
        )
        return cur.fetchall()


def _payload_do(eventos: list[tuple], tipo: str) -> dict:
    bruto = next(e[1] for e in eventos if e[0] == tipo)
    return json.loads(bruto) if isinstance(bruto, str) else bruto


def _status_item(client, token_dono: str, protocolo: str, item_id: int) -> str:
    r = client.get(f"/pedidos-exame/{protocolo}", headers=_headers(token_dono))
    assert r.status_code == 200, r.text
    return next(i["status_item"] for i in r.json()["itens"] if i["id"] == item_id)


def _preparar_item_coletado(client, token_prescritor, cnpj_prestador: str):
    """Pedido agendado no prestador e item já coletado — pré-condição da bancada."""
    proto = _criar_pedido(client, token_prescritor)
    item_id = _item_id(client, token_prescritor, proto)
    assert _agendar(client, token_prescritor, proto, cnpj_prestador).status_code == 201
    r = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
        headers=_headers(_token(cnpj_prestador, "dispensador")),
    )
    assert r.status_code == 201, r.text
    return proto, item_id


def _bancada(client, token: str, protocolo: str, item_id: int, json_body=None):
    kwargs = {"headers": _headers(token)}
    if json_body is not None:
        kwargs["json"] = json_body
    return client.post(f"/pedidos-exame/{protocolo}/itens/{item_id}/em-analise", **kwargs)


# ===========================================================================
# Caminho feliz — a transição que era fantasma
# ===========================================================================

def test_bancada_coletado_para_em_analise_200_e_ledger(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC1 — item coletado vai à bancada: 200, item e pedido em `em_analise`,
    evento `pedido_em_analise` no ledger com `item_id` e `setor`."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, _token(_CNPJ_A, "dispensador"), proto, item_id,
                 {"setor": "bioquímica"})
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["protocolo"] == proto
    assert body["item_id"] == item_id
    assert body["status_item"] == "em_analise"
    # AC5 — status do pedido re-derivado (derivar_status_pedido: item na bancada
    # arrasta o pedido para `em_analise`).
    assert body["status_pedido"] == "em_analise"

    # A resposta não basta: o estado tem que estar PERSISTIDO (era exatamente o
    # que faltava — `em_analise` existia no contrato e não no banco).
    assert _status_item(client, token_pre, proto, item_id) == "em_analise"
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM pedidos_exame WHERE protocolo = %s", (proto,))
        assert cur.fetchone()[0] == "em_analise"

    eventos = _eventos(outer_conn, proto)
    assert "pedido_em_analise" in [e[0] for e in eventos], eventos
    payload = _payload_do(eventos, "pedido_em_analise")
    assert payload["item_id"] == item_id
    assert payload["setor"] == "bioquímica"


def test_bancada_sem_setor_200_e_setor_nulo(client, outer_conn, seed_usuario, seed_paciente):
    """Corpo ausente é o caso comum (a clínica nem sempre declara o setor).

    Também prova que string vazia não vira setor declarado: o ledger é imutável,
    guardar "" seria afirmar que alguém informou algo.
    """
    token_pre = obter_token_prescritor(client, seed_usuario)

    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)
    r = _bancada(client, _token(_CNPJ_A, "dispensador"), proto, item_id)  # sem corpo
    assert r.status_code == 200, r.text
    assert _payload_do(_eventos(outer_conn, proto), "pedido_em_analise")["setor"] is None

    proto2, item2 = _preparar_item_coletado(client, token_pre, _CNPJ_A)
    r2 = _bancada(client, _token(_CNPJ_A, "dispensador"), proto2, item2, {"setor": "   "})
    assert r2.status_code == 200, r2.text
    assert _payload_do(_eventos(outer_conn, proto2), "pedido_em_analise")["setor"] is None


# ===========================================================================
# Guarda de estado
# ===========================================================================

def test_bancada_de_agendado_422(client, seed_usuario, seed_paciente):
    """AC2 — só se coleta antes de mandar à bancada. Item `agendado` → 422."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    item_id = _item_id(client, token_pre, proto)
    assert _agendar(client, token_pre, proto, _CNPJ_A).status_code == 201

    r = _bancada(client, _token(_CNPJ_A, "dispensador"), proto, item_id, {})
    assert r.status_code == 422, r.text
    assert "coletado" in r.json()["detail"]
    assert "agendado" in r.json()["detail"]


def test_bancada_duas_vezes_422(client, seed_usuario, seed_paciente):
    """Reenviar à bancada um item que já está lá é transição inválida — não
    um segundo evento silencioso no ledger."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)
    tok = _token(_CNPJ_A, "dispensador")

    assert _bancada(client, tok, proto, item_id, {}).status_code == 200
    r = _bancada(client, tok, proto, item_id, {})
    assert r.status_code == 422, r.text
    assert "em_analise" in r.json()["detail"]


def test_bancada_item_inexistente_404(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, _ = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, _token(_CNPJ_A, "dispensador"), proto, 999_999, {})
    assert r.status_code == 404, r.text


# ===========================================================================
# RBAC — papel e posse
# ===========================================================================

def test_bancada_paciente_403(client, seed_usuario, seed_paciente):
    """AC3 — bancada é gesto da unidade. Paciente é barrado no portão de PAPEL
    (require_role): `detail` é string, não o dict de posse."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, _token(SEED_PACIENTE_CPF, "paciente"), proto, item_id, {})
    assert r.status_code == 403, r.text


def test_bancada_prescritor_403(client, seed_usuario, seed_paciente):
    """O prescritor DONO do pedido também não envia à bancada — não é dele a
    bancada. Diferente de `coletar`/`resultado`, que aceitam prescritor."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, token_pre, proto, item_id, {})
    assert r.status_code == 403, r.text


def test_bancada_dispensador_outro_cnpj_403_sem_vazar_conteudo(
    client, seed_usuario, seed_paciente
):
    """AC3 — dispensador sem custódia: 403 de POSSE, e o corpo não vaza o pedido."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, _token(_CNPJ_B, "dispensador"), proto, item_id, {"setor": "x"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"
    corpo = r.text.upper()
    for vazamento in (SEED_PACIENTE_NOME.upper(), SEED_PACIENTE_CPF, "HEMOGRAMA"):
        assert vazamento not in corpo, f"403 vazou '{vazamento}' no corpo: {r.text}"


def test_bancada_403_precede_422_de_estado(client, seed_usuario, seed_paciente):
    """Ordenação anti-leak (#52): item ainda `pendente` (que renderia 422 ao dono)
    devolve 403 ao terceiro. Se o 422 viesse antes, o terceiro aprenderia o
    estado do item pelo código de status."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    item_id = _item_id(client, token_pre, proto)
    assert _agendar(client, token_pre, proto, _CNPJ_A).status_code == 201

    r = _bancada(client, _token(_CNPJ_B, "dispensador"), proto, item_id, {})
    assert r.status_code == 403, r.text
    # O código prova que o 403 veio da POSSE, não do papel barrado no require_role.
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_bancada_admin_bypassa_posse_200(client, seed_usuario, seed_paciente):
    """admin não tem CNPJ e passa sem ownership (§7.2) — `sub` sem dígitos prova
    que o normalizador de identidade nem chega a ser usado."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    r = _bancada(client, _token("admin", "admin", "ADMIN"), proto, item_id, {})
    assert r.status_code == 200, r.text
    assert r.json()["status_item"] == "em_analise"


# ===========================================================================
# Encadeamento (Ticket G) e imutabilidade do ledger
# ===========================================================================

def test_bancada_encadeia_com_resultado_sem_duplicar_evento(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC (opcional do ticket) — depois da bancada, `/resultado` continua levando a
    `resultado_disponivel`. E o `pedido_em_analise` aparece UMA vez: o `/resultado`
    só emite o marco quando parte de `coletado` (pedidos_exame.py), então o
    endpoint novo não duplica identificador de movimento no ledger."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)
    tok = _token(_CNPJ_A, "dispensador")

    assert _bancada(client, tok, proto, item_id, {"setor": "hematologia"}).status_code == 200

    r = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json={"resultado_resumo": "Hemograma normal"},
        headers=_headers(tok),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status_item"] == "resultado_disponivel"

    tipos = [e[0] for e in _eventos(outer_conn, proto)]
    assert tipos.count("pedido_em_analise") == 1, tipos
    assert "resultado_registrado" in tipos, tipos
    # O setor declarado na bancada sobrevive ao resultado — ledger não é editado.
    payload = _payload_do(_eventos(outer_conn, proto), "pedido_em_analise")
    assert payload["setor"] == "hematologia"


def test_bancada_ledger_insert_only(client, outer_conn, seed_usuario, seed_paciente):
    """AC6 — o evento novo é ACRÉSCIMO: os anteriores continuam lá, na ordem."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto, item_id = _preparar_item_coletado(client, token_pre, _CNPJ_A)

    antes = [e[0] for e in _eventos(outer_conn, proto)]
    assert _bancada(client, _token(_CNPJ_A, "dispensador"), proto, item_id, {}).status_code == 200
    depois = [e[0] for e in _eventos(outer_conn, proto)]

    assert depois[: len(antes)] == antes, (antes, depois)
    assert depois[len(antes):] == ["pedido_em_analise"], depois
    assert "pedido_coletado" in antes, antes
