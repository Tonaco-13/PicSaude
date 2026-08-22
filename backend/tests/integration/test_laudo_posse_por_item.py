"""Posse por item no laudo — ENG-014, frente 1 (v2) do desenho.

A ERRATA QUE ORIGINOU ESTE ARQUIVO
----------------------------------
A v1 do §2 mandava casar laudo↔pedido pelos itens, mas o elo não existia:
`laudo_itens` guardava `nome_exame`/`codigo_tuss` — texto livre. Autorizar por
NOME é a mesma família de defeito que a casa já rejeitou três vezes (posse lida
do status no J.7, predicado duplicado no #168, relatório lendo nível-pedido no
#172). O engenheiro parou pelo §3; o arquiteto registrou a errata e decidiu:
**elo de verdade (§2.1) + ponte declarada para os legados (§2.2)**.

AS DUAS CAMADAS
---------------
1. **Elo** (`laudo_itens.pedido_item_id`): na CRIAÇÃO por dispensador é
   obrigatório em TODOS os itens, cada um pertencente ao pedido e sob custódia
   da unidade. Na OPERAÇÃO, basta deter UM item com elo.
2. **Ponte (§2.2)**: laudo cujos itens são TODOS legados (`NULL`) é operável
   por quem detém qualquer coisa do pedido — o predicado grossa do #172,
   REUSADO. Menos preciso, e por isso declarado. É ela que fecha o bug em
   aberto: num pedido explodido, `dispensador_detem_pedido` devolve False para
   todos e ninguém conseguia operar o laudo.

ACs cobertos: (i), (vi-criação), (viii), (ix), (x).

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import pytest

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB_A = "12345678000195"
_LAB_B = "98765432000110"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome="PAC")
def _tok_lab(c): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _emitir(client, tp, nomes: list[str]) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in nomes],
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


def _criar_laudo(client, cnpj, proto, itens):
    return client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto, "itens": itens,
    }, headers=_h(_tok_lab(cnpj)))


# ---------------------------------------------------------------------------
# AC (i) e (vi) — criação por item
# ---------------------------------------------------------------------------

def test_unidade_parcial_lauda_os_seus_itens(client, outer_conn, seed_usuario, seed_paciente):
    """O bug que a frente 1 conserta: quem detém 1 de 3 consegue laudar o seu.

    Antes, o direito vinha da posse do PEDIDO INTEIRO — e num pedido explodido
    ninguém a tem.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "GLICEMIA", "TSH"])
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    r = _criar_laudo(client, _LAB_A, proto,
                     [{"nome_exame": "HEMOGRAMA", "pedido_item_id": ids[0],
                       "conclusao": "normal"}])
    assert r.status_code == 201, r.text


def test_nao_lauda_item_alheio(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "GLICEMIA"])
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    r = _criar_laudo(client, _LAB_A, proto,
                     [{"nome_exame": "GLICEMIA", "pedido_item_id": ids[1]}])
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_item_de_outro_pedido_e_recusado(client, outer_conn, seed_usuario, seed_paciente):
    """O elo tem de pertencer ao pedido vinculado — senão seria um elo mentiroso."""
    tp = obter_token_prescritor(client, seed_usuario)
    p1 = _emitir(client, tp, ["HEMOGRAMA"])
    p2 = _emitir(client, tp, ["GLICEMIA"])
    assert _transferir(client, p1, _LAB_A).status_code == 201
    assert _transferir(client, p2, _LAB_A).status_code == 201

    r = _criar_laudo(client, _LAB_A, p1,
                     [{"nome_exame": "GLICEMIA", "pedido_item_id": _ids(outer_conn, p2)[0]}])
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# AC (x) — criação sem elo é recusada
# ---------------------------------------------------------------------------

def test_criacao_por_dispensador_sem_elo_e_422(client, outer_conn, seed_usuario, seed_paciente):
    """Laudo novo de laboratório NUNCA nasce na ponte."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA"])
    assert _transferir(client, proto, _LAB_A).status_code == 201

    r = _criar_laudo(client, _LAB_A, proto, [{"nome_exame": "HEMOGRAMA"}])
    assert r.status_code == 422, r.text
    assert "pedido_item_id" in r.text


def test_prescritor_segue_criando_sem_elo(client, outer_conn, seed_usuario, seed_paciente):
    """O vínculo do prescritor é CLÍNICO, não de posse — regressão nula."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA"])

    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto, "itens": [{"nome_exame": "HEMOGRAMA"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# AC (viii) — o caso que mata o casamento por nome
# ---------------------------------------------------------------------------

def test_dois_itens_de_mesmo_nome_autorizam_pelo_id(client, outer_conn, seed_usuario, seed_paciente):
    """DOIS "HEMOGRAMA" no mesmo pedido, um de cada unidade.

    Se a autorização casasse por `nome_exame`, A e B teriam o mesmo direito
    sobre os dois — o nome não distingue. O id distingue.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "HEMOGRAMA"])
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    # A lauda o SEU hemograma: 201.
    assert _criar_laudo(client, _LAB_A, proto,
                        [{"nome_exame": "HEMOGRAMA", "pedido_item_id": ids[0]}]
                        ).status_code == 201

    # A tenta laudar o hemograma de B — MESMO NOME, id diferente: 403.
    r = _criar_laudo(client, _LAB_A, proto,
                     [{"nome_exame": "HEMOGRAMA", "pedido_item_id": ids[1]}])
    assert r.status_code == 403, (
        "autorização caiu no nome: os dois itens se chamam igual e o direito "
        "tem de vir do ID"
    )


# ---------------------------------------------------------------------------
# AC (ix) — renomear não muda quem opera
# ---------------------------------------------------------------------------

def test_renomear_o_exame_no_laudo_nao_muda_o_direito(client, outer_conn, seed_usuario, seed_paciente):
    """O `nome_exame` do laudo é EXIBIÇÃO — pode divergir do pedido sem efeito.

    Se o direito viesse do nome, escrever outro nome no laudo mudaria (ou
    perderia) a autorização. Com o elo, o nome é livre e a chave é o id.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA COMPLETO"])
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    r = _criar_laudo(client, _LAB_A, proto,
                     [{"nome_exame": "Hemograma (série vermelha)",   # outro nome
                       "pedido_item_id": ids[0], "conclusao": "normal"}])
    assert r.status_code == 201, r.text

    lp = r.json()["protocolo"]
    hl = _h(_tok_lab(_LAB_A))
    assert client.post(f"/laudos/{lp}/assinar", headers=hl).status_code == 200


# ---------------------------------------------------------------------------
# AC (x) — a PONTE: laudo legado
# ---------------------------------------------------------------------------

def test_ponte_legado_operavel_por_quem_detem_algo(client, outer_conn, seed_usuario, seed_paciente):
    """Laudo com TODOS os itens sem elo (legado) → predicado grossa do #172.

    É o bug que estava aberto: pedido explodido em nível-item, e o laudo
    legado sem ninguém que o opere. A ponte devolve o acesso a quem é parte.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "GLICEMIA"])
    ids = _ids(outer_conn, proto)

    # Laudo criado pelo PRESCRITOR (sem elo) — simula o legado.
    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto, "itens": [{"nome_exame": "HEMOGRAMA"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    lp = r.json()["protocolo"]

    # Agora o pedido explode: A fica com 1 de 2. Sem a ponte, ninguém operaria.
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    assert client.post(f"/laudos/{lp}/assinar",
                       headers=_h(_tok_lab(_LAB_A))).status_code == 200, (
        "a ponte do §2.2 não devolveu o acesso ao legado"
    )


def test_ponte_nao_abre_para_quem_nao_e_parte(client, outer_conn, seed_usuario, seed_paciente):
    """A ponte é frouxa, não é aberta: quem não detém nada segue fora."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "GLICEMIA"])
    ids = _ids(outer_conn, proto)

    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto, "itens": [{"nome_exame": "HEMOGRAMA"}],
    }, headers=_h(tp))
    lp = r.json()["protocolo"]
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    assert client.post(f"/laudos/{lp}/assinar",
                       headers=_h(_tok_lab(_LAB_B))).status_code == 403


def test_laudo_com_elo_nao_cai_na_ponte(client, outer_conn, seed_usuario, seed_paciente):
    """Havendo elo, ele MANDA — a ponte não é consultada.

    Sem isto, um laudo moderno herdaria a frouxidão do legado: bastaria deter
    qualquer item do pedido para operar laudo de outra unidade.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp, ["HEMOGRAMA", "GLICEMIA"])
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    # B lauda o SEU item (com elo).
    r = _criar_laudo(client, _LAB_B, proto,
                     [{"nome_exame": "GLICEMIA", "pedido_item_id": ids[1]}])
    assert r.status_code == 201, r.text
    lp = r.json()["protocolo"]

    # A é parte do pedido (detém ids[0]) — mas o laudo TEM elo, e não é dele.
    assert client.post(f"/laudos/{lp}/assinar",
                       headers=_h(_tok_lab(_LAB_A))).status_code == 403, (
        "laudo com elo caiu na ponte — a frouxidão do legado vazou para o novo"
    )
