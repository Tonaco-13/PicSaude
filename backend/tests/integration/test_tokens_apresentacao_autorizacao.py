"""TICKET-J.6.b — o token distingue o TIPO do objeto, sem virar oráculo.

O ACHADO (excursão de 14/08): colar o protocolo de um ATESTADO no gerador de
token devolvia "Prescrição não encontrada" — mensagem que diz *sumiu* quando o
objeto existe e apenas não usa esse mecanismo. O token de apresentação é da
RECEITA: existe para ela ser apresentada no balcão da farmácia.

A PARTE QUE ESTE ARQUIVO REALMENTE GUARDA é a outra metade: a mensagem melhor
**não pode virar oráculo de existência**. O tipo só é revelado quando o objeto é
do próprio paciente autenticado; para protocolo alheio — ou inexistente — a
resposta continua genérica. Sem isso, qualquer um poderia varrer protocolos e
descobrir quais existem e de que tipo são.

Por isso o arquivo se chama `_autorizacao`: o critério que ele trava é de
autorização, não de redação. (E é o que o faz casar com o `-k` do gate.)

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CPF_OUTRO_PACIENTE = "98765432100"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _emitir_pedido_exame(client, token_pre: str) -> str:
    r = client.post(
        "/pedidos-exame",
        json={
            "cns_prescritor":  SEED_PRESCRITOR_CNS,
            "nome_prescritor": "DR. TESTE TICKET13",
            "cpf_paciente":    SEED_PACIENTE_CPF,
            "nome_paciente":   SEED_PACIENTE_NOME,
            "tipo_emissao":    "novo",
            "prioridade":      "rotina",
            "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
        },
        headers=_headers(token_pre),
    )
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _gerar_token(client, cpf: str, proto: str):
    return client.post(
        "/tokens/apresentacao",
        json={"protocolo": proto},
        headers=_headers(_tok(cpf, "paciente")),
    )


# ---------------------------------------------------------------------------
# A mensagem
# ---------------------------------------------------------------------------

def test_protocolo_de_outro_objeto_do_paciente_explica_o_tipo(
    client, seed_usuario, seed_paciente
):
    """AC — protocolo de pedido de exame DO PACIENTE: a resposta nomeia o tipo e
    diz para que serve o token, em vez de alegar que o objeto não existe."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido_exame(client, token_pre)

    r = _gerar_token(client, SEED_PACIENTE_CPF, proto)
    assert r.status_code == 404, r.text
    detalhe = r.json()["detail"].lower()
    assert "pedido de exame" in detalhe, detalhe
    assert "não encontrada" not in detalhe, "seguiu dizendo que o objeto sumiu"


# ---------------------------------------------------------------------------
# O anti-vazamento — a metade que importa
# ---------------------------------------------------------------------------

def test_protocolo_de_objeto_alheio_nao_revela_o_tipo(client, seed_usuario, seed_paciente):
    """O objeto existe, mas é de OUTRO paciente: resposta genérica.

    Se o tipo vazasse aqui, a mensagem "melhor" viraria um oráculo — bastaria
    varrer protocolos para mapear o que existe e de que natureza é.
    """
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido_exame(client, token_pre)   # pertence ao paciente semeado

    r = _gerar_token(client, _CPF_OUTRO_PACIENTE, proto)
    assert r.status_code == 404, r.text
    detalhe = r.json()["detail"].lower()
    assert "pedido de exame" not in detalhe, f"vazou o tipo para não-dono: {detalhe}"
    assert "prescrição não encontrada" in detalhe


def test_protocolo_inexistente_segue_generico(client, seed_usuario, seed_paciente):
    r = _gerar_token(client, SEED_PACIENTE_CPF, "PROTO-QUE-NAO-EXISTE-J6B")
    assert r.status_code == 404, r.text
    assert "prescrição não encontrada" in r.json()["detail"].lower()


def test_receita_valida_continua_gerando_token(client, seed_usuario, seed_paciente):
    """Regressão: o caminho feliz não foi tocado — a mensagem nova só entra
    quando NÃO há prescrição para aquele protocolo."""
    token_pre = obter_token_prescritor(client, seed_usuario)
    r = client.post(
        "/prescricoes",
        json={
            "cns_prescritor":  SEED_PRESCRITOR_CNS,
            "nome_prescritor": "DR. TESTE TICKET13",
            "cpf_paciente":    SEED_PACIENTE_CPF,
            "nome_paciente":   SEED_PACIENTE_NOME,
            "tipo_emissao":    "nova",
            "assinatura_modo": "gov_br_nuvem",
            "itens": [{
                "nome_medicamento": "DIPIRONA", "concentracao": "500mg",
                "quantidade": 1, "unidade_quantidade": "comprimido",
                "posologia": "1 comprimido a cada 6h",
            }],
        },
        headers=_headers(token_pre),
    )
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    rt = _gerar_token(client, SEED_PACIENTE_CPF, proto)
    assert rt.status_code == 201, rt.text
    assert rt.json().get("codigo_curto"), rt.json()
