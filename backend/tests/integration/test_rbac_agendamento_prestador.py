"""MICRO-TICKET RBAC (`core`) — o laboratório remarca e registra falta.

Origem: §4 do parecer `SESSAO-2026-08-15-PARECER-ARQUITETO-J7-PRS` (assimetria
de RBAC em agendamentos) · §6 do `SESSAO-2026-08-16-TICKET-ENG-012` (os dois
casos concretos, encontrados ao escrever o E2E do J.11) · despachado na FASE 3
do `DESPACHO-ENG-013`.

A ASSIMETRIA QUE ESTE ARQUIVO FECHA
-----------------------------------
`POST /agendamentos` sempre aceitou `dispensador` — o laboratório MARCA. Mas:

  · `POST /agendamentos/{p}/remarcar`      era prescritor · paciente · admin
  · `POST /agendamentos/{p}/nao-compareceu` era prescritor · admin

Ou seja: **o laboratório marcava e não podia remarcar**, e quem PRESENCIA a
falta não podia registrá-la. Nos dois casos o caminho real dependia de um
prescritor para desfazer ou anotar algo que ele não acompanhou — atrito sem
justificativa clínica, que é exatamente o que o §5 dos princípios proíbe.

Era acidente de escrita, não decisão: nenhum documento justifica a exclusão, e
os endpoints vizinhos (`confirmar`, `realizar`, `cancelar`) já a aceitavam.

O QUE **NÃO** MUDA
------------------
O ownership. `_assert_ag_owner` já cobria `dispensador` por `org_id` (two-hop
`prestadores.cnpj → org_id`, fail-closed §D1) — nenhuma linha nova de
autorização foi escrita. Prestador de outra org continua levando 403, e
prestador não cadastrado continua no fail-closed. Este ticket move QUEM pode
disparar, nunca O QUE acontece: remarcar segue sendo derivação (§1 do
CLAUDE.md), com o anterior indo a `cancelado` e um novo nascendo com
`origem_agendamento_id`.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

_CNS_PRESC = "111111111111111"
_CPF_PAC   = "44455566677"
_ORG_A     = "org-aaa"
_ORG_B     = "org-bbb"
_CNPJ_A    = "12345678000195"
_CNPJ_B    = "98765432000110"


def _headers(t): return {"Authorization": f"Bearer {t}"}
def _tok(sub, role, nome="ATOR"): return criar_access_token(sub=sub, role=role, nome=nome)


def _seed_prestador(client, org_id, cnpj, nome="Lab", tipo="laboratorio"):
    r = client.post("/prestadores", json={
        "org_id": org_id, "nome": nome, "tipo": tipo, "cnpj": cnpj,
    }, headers=_headers(_tok("admin", "admin")))
    assert r.status_code == 201, r.text


def _criar_pedido(client):
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": _CNS_PRESC, "nome_prescritor": "DR",
        "cpf_paciente": _CPF_PAC, "nome_paciente": "PAC",
        "tipo_emissao": "novo", "prioridade": "rotina",
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }, headers=_headers(_tok(_CNS_PRESC, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _novo_ag(client, org_id=_ORG_A):
    pedido = _criar_pedido(client)
    r = client.post("/agendamentos", json={
        "pedido_protocolo": pedido, "data_hora": "2026-07-01T10:00:00",
        "org_id": org_id, "unidade_id": "u1", "tipo_agendamento": "exame",
    }, headers=_headers(_tok(_CNS_PRESC, "prescritor")))
    assert r.status_code == 201, r.text
    return pedido, r.json()["protocolo"]


def _itens(client, pedido_proto, token):
    r = client.get(f"/pedidos-exame/{pedido_proto}", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["itens"]


# ---------------------------------------------------------------------------
# 1 — o caminho que estava fechado, agora aberto
# ---------------------------------------------------------------------------

def test_lab_remarca_o_proprio_agendamento(client, outer_conn):
    """O laboratório que marcou pode remarcar. E remarcar segue sendo DERIVAR."""
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    pedido, ag = _novo_ag(client, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_A, "dispensador"))

    r = client.post(f"/agendamentos/{ag}/remarcar",
                    json={"data_hora": "2026-07-09T14:30:00"}, headers=disp)
    assert r.status_code == 201, r.text
    novo = r.json()["protocolo_novo"]
    assert novo != ag

    # O objeto anterior não foi editado: foi cancelado, e o novo aponta para ele.
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM agendamentos WHERE protocolo = %s", (ag,))
        assert cur.fetchone()[0] == "cancelado"
        cur.execute(
            "SELECT a.origem_agendamento_id, o.protocolo, a.tipo_emissao "
            "FROM agendamentos a JOIN agendamentos o ON o.id = a.origem_agendamento_id "
            "WHERE a.protocolo = %s", (novo,),
        )
        origem_id, origem_proto, tipo_emissao = cur.fetchone()
        assert origem_proto == ag
        assert tipo_emissao == "remarcacao"


def test_lab_registra_nao_comparecimento(client, outer_conn):
    """Quem presencia a falta registra a falta — e os itens voltam a 'pendente'.

    O item volta a circular: faltar à coleta não consome o pedido de exame.
    """
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    pedido, ag = _novo_ag(client, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_A, "dispensador"))

    # O agendamento pôs o item em 'agendado'.
    assert [i["status_item"] for i in _itens(client, pedido, _tok(_CNS_PRESC, "prescritor"))] == ["agendado"]

    r = client.post(f"/agendamentos/{ag}/nao-compareceu", headers=disp)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "nao_compareceu"

    assert [i["status_item"] for i in _itens(client, pedido, _tok(_CNS_PRESC, "prescritor"))] == ["pendente"]


# ---------------------------------------------------------------------------
# 2 — o ownership NÃO foi afrouxado
# ---------------------------------------------------------------------------

def test_lab_de_outra_org_nao_remarca(client):
    """Vínculo existe, mas é de outra org → 403. O ticket abriu o papel, não a porta."""
    _seed_prestador(client, _ORG_B, _CNPJ_B)
    _, ag = _novo_ag(client, org_id=_ORG_A)

    r = client.post(f"/agendamentos/{ag}/remarcar",
                    json={"data_hora": "2026-07-09T14:30:00"},
                    headers=_headers(_tok(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_agendamento"


def test_lab_de_outra_org_nao_registra_falta(client):
    _seed_prestador(client, _ORG_B, _CNPJ_B)
    _, ag = _novo_ag(client, org_id=_ORG_A)

    r = client.post(f"/agendamentos/{ag}/nao-compareceu",
                    headers=_headers(_tok(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_agendamento"


def test_prestador_nao_cadastrado_segue_fail_closed(client):
    """Sem `prestadores.cnpj → org_id` que resolva, 403 — §D1 preservado.

    O CÓDIGO importa: `nao_e_dono_do_agendamento` prova que o papel passou pelo
    `require_role` e foi barrado pelo OWNERSHIP. Antes deste ticket, a recusa
    vinha do RBAC e o `detail` era uma string ("Perfil 'dispensador' não tem
    permissão..."). Sem esta asserção, o teste passaria pelo motivo errado —
    e continuaria verde se alguém removesse o papel de volta.
    """
    _, ag = _novo_ag(client, org_id=_ORG_A)          # nenhum prestador semeado

    for rota, corpo in (("remarcar", {"data_hora": "2026-07-09T14:30:00"}),
                        ("nao-compareceu", None)):
        r = client.post(f"/agendamentos/{ag}/{rota}", json=corpo,
                        headers=_headers(_tok(_CNPJ_A, "dispensador")))
        assert r.status_code == 403, (rota, r.text)
        assert isinstance(r.json()["detail"], dict), (
            f"{rota}: recusa veio do require_role, não do ownership — o papel "
            "não está no RBAC"
        )
        assert r.json()["detail"]["codigo"] == "nao_e_dono_do_agendamento", rota


# ---------------------------------------------------------------------------
# 3 — o paciente NÃO ganhou o que não tinha
# ---------------------------------------------------------------------------

def test_paciente_segue_fora_do_nao_compareceu(client):
    """`nao-compareceu` continua sem `paciente` — registrar a própria falta é
    declaração de parte interessada sobre um fato que o serviço constata.
    O ticket acrescentou UM papel; não abriu o endpoint.
    """
    r = client.post(f"/agendamentos/{_novo_ag(client)[1]}/nao-compareceu",
                    headers=_headers(_tok(_CPF_PAC, "paciente")))
    assert r.status_code == 403, r.text
    # Recusa do RBAC (detail string), não de ownership: o papel não está na lista.
    assert isinstance(r.json()["detail"], str)
