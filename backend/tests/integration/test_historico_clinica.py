"""Aba Histórico da clínica — ENG-014, PR B (projeção read-only).

O QUE ESTE ARQUIVO TRAVA
------------------------
1. **Mesma fonte do relatório.** O Histórico lê a MESMA custódia que a fila e o
   relatório leem (`_SQL_DETENTOR_DO_ITEM`). Uma segunda verdade sobre "o que é
   meu" divergiria da primeira no dia em que a custódia mudasse de forma — foi
   exatamente o que aconteceu com o relatório quando a parcial chegou (#172).
2. **Concluído = tem resultado.** O item em curso é trabalho, não histórico: ele
   vive na fila. Mostrá-lo aqui faria as duas telas competirem.
3. **Read-only.** Nenhuma linha nova em pedido/itens/eventos/custódia depois de
   consultar — a aba projeta, não movimenta.
4. **Isolamento por CNPJ**, incluindo sob custódia parcial: a unidade vê o que
   detém e nada além.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB_A = "12345678000195"
_LAB_B = "98765432000110"
_NOMES = ["HEMOGRAMA", "GLICEMIA", "TSH"]

_TABELAS = ("pedidos_exame", "pedido_exame_itens", "pedido_exame_eventos",
            "pedido_exame_custodia", "laudos")


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)
def _tok_lab(c): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _contagens(outer_conn) -> dict:
    out = {}
    with outer_conn.cursor() as cur:
        for t in _TABELAS:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _emitir(client, tp) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in _NOMES],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ids(outer_conn, proto) -> list[int]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id FROM pedido_exame_itens i JOIN pedidos_exame p ON p.id = i.pedido_id "
            "WHERE p.protocolo = %s ORDER BY i.id", (proto,))
        return [r[0] for r in cur.fetchall()]


def _transferir(client, proto, cnpj, itens=None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"}
    if itens is not None:
        body["itens"] = itens
    return client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json=body, headers=_h(_tok_pac()))


def _concluir(client, proto, item_id, cnpj):
    hl = _h(_tok_lab(cnpj))
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
                       json={}, headers=hl).status_code == 201
    r = client.post(f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
                    json={"resultado_resumo": "normal"}, headers=hl)
    assert r.status_code in (200, 201), r.text


def _historico(client, cnpj) -> dict:
    r = client.get("/clinicas/historico", headers=_h(_tok_lab(cnpj)))
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1 — concluído entra; em curso não
# ---------------------------------------------------------------------------

def test_item_concluido_entra_no_historico(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    _concluir(client, proto, ids[0], _LAB_A)

    h = _historico(client, _LAB_A)
    nomes = {i["nome_exame"] for i in h["itens"]}
    assert _NOMES[0] in nomes


def test_item_em_curso_nao_entra(client, outer_conn, seed_usuario, seed_paciente):
    """A fila é o trabalho; o histórico é o que já foi feito.

    Sem esta separação as duas telas mostrariam a mesma coisa e o operador
    não saberia em qual agir.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    h = _historico(client, _LAB_A)
    assert h["itens"] == [], "item sem resultado apareceu no histórico"


# ---------------------------------------------------------------------------
# 2 — isolamento, inclusive sob custódia parcial
# ---------------------------------------------------------------------------

def test_historico_nao_vaza_entre_unidades(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201
    _concluir(client, proto, ids[0], _LAB_A)
    _concluir(client, proto, ids[1], _LAB_B)

    nomes_a = {i["nome_exame"] for i in _historico(client, _LAB_A)["itens"]}
    nomes_b = {i["nome_exame"] for i in _historico(client, _LAB_B)["itens"]}

    assert nomes_a == {_NOMES[0]}, f"A viu além do que detém: {nomes_a}"
    assert nomes_b == {_NOMES[1]}, f"B viu além do que detém: {nomes_b}"


def test_unidade_sem_nada_recebe_historico_vazio(client, seed_usuario, seed_paciente):
    """Vazio com 200 — não erro, não tudo."""
    h = _historico(client, _LAB_B)
    assert h["itens"] == [] and h["laudos"] == []


# ---------------------------------------------------------------------------
# 3 — laudos liberados
# ---------------------------------------------------------------------------

def test_laudo_liberado_entra_no_historico(client, outer_conn, seed_usuario, seed_paciente):
    """O laudo entra se a unidade detém ao menos UM item do pedido que ele cobre
    — mesmo critério de posse por item do #172."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    _concluir(client, proto, ids[0], _LAB_A)

    hl = _h(_tok_lab(_LAB_A))
    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": _NOMES[0], "conclusao": "normal"}],
    }, headers=hl)
    assert r.status_code == 201, r.text
    lp = r.json()["protocolo"]
    assert client.post(f"/laudos/{lp}/assinar", headers=hl).status_code == 200
    assert client.post(f"/laudos/{lp}/liberar", json={}, headers=hl).status_code == 200

    protos = {l["protocolo"] for l in _historico(client, _LAB_A)["laudos"]}
    assert lp in protos

    # E não vaza para quem não detém nada do pedido.
    assert lp not in {l["protocolo"] for l in _historico(client, _LAB_B)["laudos"]}


# ---------------------------------------------------------------------------
# 4 — read-only
# ---------------------------------------------------------------------------

def test_historico_nao_escreve_nada(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    _concluir(client, proto, ids[0], _LAB_A)

    antes = _contagens(outer_conn)
    for _ in range(3):
        _historico(client, _LAB_A)
    assert _contagens(outer_conn) == antes, "o histórico escreveu no banco"


def test_papel_errado_nao_le_historico(client, seed_usuario, seed_paciente):
    """Só `dispensador` — é a projeção da unidade, não do cidadão."""
    tp = obter_token_prescritor(client, seed_usuario)
    assert client.get("/clinicas/historico", headers=_h(tp)).status_code == 403
    assert client.get("/clinicas/historico", headers=_h(_tok_pac())).status_code == 403
