"""ENG-017 PR B (`core`) — o dono baixa o papel que carrega.

O QUE A COMISSÃO APONTOU (#189, S5)
------------------------------------
A contradição mais direta com a Régua Zero em todo o diagnóstico: o cidadão
**detém a custódia** da receita e do pedido de exame — estão na carteira dele,
ancorados ao CPF dele — e levava **403** ao pedir o PDF do que carrega. O papel
`paciente` simplesmente não estava no `require_role` dos dois endpoints.

AS DUAS METADES DESTE PR
------------------------
1. **Abrir o papel** — `paciente` entra nos dois `require_role`.
2. **Fechar o dono** — e esta é a metade que importa: papel sem ownership
   deixaria QUALQUER paciente autenticado baixar o documento de QUALQUER outro.
   O `sub` do token é o CPF e tem de bater com o do documento.

**Ownership por CPF do DOCUMENTO, não por custódia.** A receita pode estar na
farmácia no momento do download e continua sendo o documento dele; o pedido pode
estar no laboratório e idem. Custódia responde *"onde está"*; ownership responde
*"de quem é"*. O cidadão nunca deixa de ser o paciente do documento.

**`dispensador` continua fora do PDF do pedido**, e não por esquecimento: o
pedido é artefato de quem EMITIU. O que a clínica precisa é comprovante do que
ELA executou, sob escopo de posse — é o S5-bis, delimitado pelo arquiteto e fora
deste PR.

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

_CPF_ALHEIO = "39053344705"
_CNPJ_LAB = "12345678000195"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(cpf=SEED_PACIENTE_CPF): return criar_access_token(sub=cpf, role="paciente", nome="PAC")
def _tok_disp(): return criar_access_token(sub=_CNPJ_LAB, role="dispensador", nome="LAB")


def _emitir_receita(client, tp) -> str:
    r = client.post("/prescricoes", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "itens": [{"nome_medicamento": "DIPIRONA 500MG", "quantidade": 1,
                   "posologia": "1 comprimido a cada 6 horas"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _emitir_pedido(client, tp) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "enviar_ao_paciente": True,
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ---------------------------------------------------------------------------
# 1 — o dono baixa
# ---------------------------------------------------------------------------

def test_o_cidadao_baixa_o_pdf_da_propria_receita(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_receita(client, tp)
    r = client.get(f"/prescricoes/{proto}/pdf", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF", "veio 200 mas não é PDF"


def test_o_cidadao_baixa_o_pdf_do_proprio_pedido_de_exame(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, tp)
    r = client.get(f"/pedidos-exame/{proto}/pdf", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_baixar_nao_depende_de_onde_o_documento_ESTA(client, seed_usuario, seed_paciente):
    """Custódia responde "onde está"; ownership responde "de quem é".

    O pedido entregue ao laboratório continua sendo o documento do cidadão — se
    o download seguisse a custódia, ele perderia o próprio papel ao entregá-lo,
    que é o oposto do que a Regra Zero pede.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, tp)
    assert client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json={"cnpj_laboratorio": _CNPJ_LAB, "nome_laboratorio": "LAB"},
                       headers=_h(_tok_pac())).status_code in (200, 201)

    r = client.get(f"/pedidos-exame/{proto}/pdf", headers=_h(_tok_pac()))
    assert r.status_code == 200, "o cidadão perdeu o próprio documento ao entregá-lo"


# ---------------------------------------------------------------------------
# 2 — e SÓ o dono (a metade que importa)
# ---------------------------------------------------------------------------

def test_paciente_alheio_nao_baixa_a_receita(client, seed_usuario, seed_paciente):
    """Papel sem ownership deixaria qualquer paciente autenticado baixar o
    documento de qualquer outro. É o risco que abrir o papel cria, e a razão de
    este PR ser `core`."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_receita(client, tp)
    r = client.get(f"/prescricoes/{proto}/pdf", headers=_h(_tok_pac(_CPF_ALHEIO)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"


def test_paciente_alheio_nao_baixa_o_pedido(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, tp)
    r = client.get(f"/pedidos-exame/{proto}/pdf", headers=_h(_tok_pac(_CPF_ALHEIO)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_protocolo_inexistente_e_404_para_todos(client, seed_usuario, seed_paciente):
    """Anti-leak (#52): o 404 vem antes do 403 de dono, então um paciente
    alheio não distingue pelo status um protocolo que existe de um que não."""
    for rota in ("/prescricoes/nao-existe/pdf", "/pedidos-exame/nao-existe/pdf"):
        assert client.get(rota, headers=_h(_tok_pac(_CPF_ALHEIO))).status_code == 404


# ---------------------------------------------------------------------------
# 3 — o que este PR NÃO abriu (delimitação do arquiteto)
# ---------------------------------------------------------------------------

def test_o_dispensador_continua_FORA_do_pdf_do_pedido(client, seed_usuario, seed_paciente):
    """A delimitação, executável.

    O pedido é artefato de QUEM EMITIU. Abri-lo ao laboratório daria à clínica o
    documento do prescritor — e o que ela precisa é comprovante do que ELA
    executou, sob escopo de posse (S5-bis, fora deste PR).

    Se um dia alguém "completar" a lista por simetria, este teste cai.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, tp)
    assert client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json={"cnpj_laboratorio": _CNPJ_LAB, "nome_laboratorio": "LAB"},
                       headers=_h(_tok_pac())).status_code in (200, 201)

    r = client.get(f"/pedidos-exame/{proto}/pdf", headers=_h(_tok_disp()))
    assert r.status_code == 403, (
        "o PDF do pedido abriu para o dispensador — é o que a delimitação do "
        "arquiteto proíbe (S5-bis é outro documento, por posse)"
    )


def test_o_dispensador_continua_baixando_a_receita(client, seed_usuario, seed_paciente):
    """Regressão do fluxo de balcão: a receita SEMPRE foi legível ao
    dispensador (é ele quem dispensa). Abrir para o paciente não pode ter
    fechado para ninguém."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_receita(client, tp)
    assert client.get(f"/prescricoes/{proto}/pdf", headers=_h(_tok_disp())).status_code == 200


def test_o_prescritor_dono_continua_baixando(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    for proto, rota in ((_emitir_receita(client, tp), "prescricoes"),
                        (_emitir_pedido(client, tp), "pedidos-exame")):
        assert client.get(f"/{rota}/{proto}/pdf", headers=_h(tp)).status_code == 200
