"""Selo de agendamento no cartão do exame — TICKET-J.11 (`module`).

Origem: Adendo §10 do `DESPACHO-ENG-011` (decisão do Fabiano em 15/08, "de acordo,
versão A" — inline na aba Exames, sem 4ª aba) e §2 do parecer `J7-PRS`.

A REGRA QUE ESTE ARQUIVO TRAVA
------------------------------
O cidadão vê, **em tempo de leitura**, o compromisso que o laboratório marcou
para o seu exame — e **nada muda de mão por causa disso**:

    informação ≠ custódia

A custódia segue com o `prestador_exame` até o fim. Ler a data não transfere
posse, não muda estado e não escreve no ledger. É a regra que separa este
ticket do J.7: lá, mover a posse mudava o estado indevidamente; aqui, mostrar
a data não pode mover nada.

POR QUE O SELO SÓ FAZ SENTIDO DEPOIS DO J.7
-------------------------------------------
Antes do J.7, `agendado` era o efeito colateral de transferir custódia — um
rótulo sem data por trás. Um "selo de agendamento" naquele mundo mostraria
`Agendado` sem ter o que mostrar. Com o J.7, `agendado` significa que existe
uma linha em `agendamentos` com data/hora/unidade: agora há o que selar.

O CORRENTE, NÃO O HISTÓRICO
---------------------------
Remarcar é derivação (§7 do CLAUDE.md): o anterior vai a `cancelado`, nasce um
novo com `origem_agendamento_id`. O cartão mostra **o vigente**; o histórico
completo fica no ledger, que é o lugar dele (o cidadão não é auditor da própria
agenda). `agendamento_atual_do_pedido` é a fonte única dessa escolha — a tela
não a reimplementa, pela mesma razão que deixou de derivar posse do status.

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

_CNPJ_LAB_A = "12345678000195"

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE J11",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_paciente(cpf: str = SEED_PACIENTE_CPF) -> str:
    return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)


def _emitir_pedido(client, token_prescritor: str) -> str:
    r = client.post("/pedidos-exame", json=_PAYLOAD_BASE,
                    headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _transferir(client, proto: str, cnpj: str = _CNPJ_LAB_A):
    return client.post(
        f"/pedidos-exame/{proto}/transferir-laboratorio",
        json={"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB DEMO"},
        headers=_headers(_token_paciente()),
    )


def _agendar(client, token, proto: str, *, data_hora: str = "2026-09-01T08:00:00",
             unidade: str = "UNIDADE_01") -> str:
    """Cria o agendamento. Quem dispara é o PRESCRITOR, não o laboratório, por
    razão de AMBIENTE e não de regra — o dispensador só passa no ownership de
    criação com `prestadores.cnpj → org_id` semeado (fail-closed §D1), e a
    fixture de integração não semeia prestador. A persona "laboratório agenda"
    é coberta no gate de navegador. Mesma nota do `test_transferencia_exame_
    cidadao.py`; o que se trava aqui é o mecanismo, não o ator.
    """
    r = client.post(
        "/agendamentos",
        json={"pedido_protocolo": proto, "org_id": "LAB_A",
              "unidade_id": unidade, "data_hora": data_hora},
        headers=_headers(token),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["protocolo"]


def _cartao(client, proto: str) -> dict:
    """O cartão do pedido como a carteira do cidadão o recebe."""
    r = client.get("/paciente/pedidos-exame", headers=_headers(_token_paciente()))
    assert r.status_code == 200, r.text
    dados = r.json()
    todos = [*dados["posse"], *dados["em_andamento"], *dados["historico"]]
    achado = [p for p in todos if p["protocolo"] == proto]
    assert achado, f"pedido {proto} sumiu da carteira"
    return achado[0]


def _contar(outer_conn, sql: str, params: tuple) -> int:
    with outer_conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# 1 — ausência é informação: sem compromisso, sem selo
# ---------------------------------------------------------------------------

def test_pedido_sem_agendamento_nao_tem_selo(client, seed_usuario, seed_paciente):
    """`None`, não um objeto vazio.

    O cartão precisa distinguir "ainda não marcaram" de "marcado para —". Um
    dicionário com campos nulos faria a tela desenhar um selo sem data, que é
    exatamente o defeito que o J.7 removeu do rótulo `agendado`.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    assert _cartao(client, proto)["agendamento"] is None

    # Nem depois de entregar: entregar é posse, não agenda (J.7).
    assert _transferir(client, proto).status_code == 201
    assert _cartao(client, proto)["agendamento"] is None


# ---------------------------------------------------------------------------
# 2 — o AC principal: transferiu → agendou → o cidadão vê data/hora/unidade
# ---------------------------------------------------------------------------

def test_cidadao_ve_data_hora_e_unidade_do_agendamento(client, seed_usuario, seed_paciente):
    """AC do Adendo §10, caminho completo."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto).status_code == 201
    ag_proto = _agendar(client, token_p, proto)

    selo = _cartao(client, proto)["agendamento"]
    assert selo is not None
    assert selo["protocolo"]  == ag_proto
    assert selo["data_hora"]  == "2026-09-01T08:00:00"
    assert selo["unidade_id"] == "UNIDADE_01"
    assert selo["status"]     == "criado"
    assert selo["remarcado"]  is False


def test_selo_nao_vaza_a_ficha_operacional_do_laboratorio(client, seed_usuario, seed_paciente):
    """A carteira é leitura do cidadão sobre o próprio compromisso.

    `criado_por` (quem operou no laboratório) e o id interno não têm por que
    atravessar para a tela do cidadão. Projeção mínima, decidida no backend.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto).status_code == 201
    _agendar(client, token_p, proto)

    selo = _cartao(client, proto)["agendamento"]
    assert set(selo) == {
        "protocolo", "status", "data_hora", "unidade_id", "local_texto", "remarcado",
    }


# ---------------------------------------------------------------------------
# 3 — informação ≠ custódia: ler não move nada
# ---------------------------------------------------------------------------

def test_ler_o_selo_nao_gera_evento_nem_move_custodia(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O AC que dá nome ao ticket.

    A carteira lê o compromisso; a posse continua com o laboratório e o ledger
    continua exatamente do mesmo tamanho. Se um dia alguém "aproveitar" esta
    leitura para registrar ciência do cidadão, este teste cai — e deve cair:
    ciência é ato, ato tem evento, e evento não nasce de um GET.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto).status_code == 201
    _agendar(client, token_p, proto)

    sql_ev_pedido = (
        "SELECT COUNT(*) FROM pedido_exame_eventos e "
        "JOIN pedidos_exame p ON p.id = e.pedido_id WHERE p.protocolo = %s"
    )
    sql_ev_agenda = (
        "SELECT COUNT(*) FROM agendamento_eventos e "
        "JOIN agendamentos a ON a.id = e.agendamento_id "
        "JOIN pedidos_exame p ON p.id = a.pedido_id WHERE p.protocolo = %s"
    )
    sql_custodia = (
        "SELECT COUNT(*) FROM pedido_exame_custodia c "
        "JOIN pedidos_exame p ON p.id = c.pedido_id WHERE p.protocolo = %s"
    )

    antes = (
        _contar(outer_conn, sql_ev_pedido, (proto,)),
        _contar(outer_conn, sql_ev_agenda, (proto,)),
        _contar(outer_conn, sql_custodia,  (proto,)),
    )

    for _ in range(3):                       # ler várias vezes não acumula nada
        assert _cartao(client, proto)["agendamento"] is not None

    depois = (
        _contar(outer_conn, sql_ev_pedido, (proto,)),
        _contar(outer_conn, sql_ev_agenda, (proto,)),
        _contar(outer_conn, sql_custodia,  (proto,)),
    )
    assert antes == depois

    # E a posse não voltou para o cidadão por ele ter olhado a data.
    cartao = _cartao(client, proto)
    assert cartao["sob_minha_custodia"] is False
    assert cartao["detentor"] == _CNPJ_LAB_A


# ---------------------------------------------------------------------------
# 4 — remarcação: o cartão mostra o corrente, não o revogado
# ---------------------------------------------------------------------------

def test_remarcacao_mostra_o_agendamento_corrente(client, seed_usuario, seed_paciente):
    """Remarcar é derivar (§7 do CLAUDE.md), não editar.

    O anterior vai a `cancelado` e nasce um derivado. Se o cartão mostrasse "o
    último criado" sem filtrar terminais, um cancelamento simples deixaria o
    cidadão indo ao laboratório na data errada.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto).status_code == 201
    ag_original = _agendar(client, token_p, proto)

    r = client.post(
        f"/agendamentos/{ag_original}/remarcar",
        json={"data_hora": "2026-09-15T14:30:00", "unidade_id": "UNIDADE_02"},
        headers=_headers(token_p),
    )
    assert r.status_code in (200, 201), r.text
    ag_novo = r.json()["protocolo_novo"]

    selo = _cartao(client, proto)["agendamento"]
    assert selo["protocolo"]  == ag_novo
    assert selo["protocolo"]  != ag_original
    assert selo["data_hora"]  == "2026-09-15T14:30:00"
    assert selo["unidade_id"] == "UNIDADE_02"
    assert selo["remarcado"]  is True


def test_agendamento_cancelado_apaga_o_selo(client, seed_usuario, seed_paciente):
    """Cancelou e não remarcou → o cartão volta a não ter compromisso.

    Um selo que sobrevive ao cancelamento é pior que selo nenhum: manda o
    cidadão a uma coleta que não existe mais.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto).status_code == 201
    ag_proto = _agendar(client, token_p, proto)

    r = client.post(f"/agendamentos/{ag_proto}/cancelar", json={},
                    headers=_headers(token_p))
    assert r.status_code == 200, r.text

    assert _cartao(client, proto)["agendamento"] is None


# ---------------------------------------------------------------------------
# 5 — regressão: o J.11 acrescenta campo, não reescreve o contrato
# ---------------------------------------------------------------------------

def test_contrato_do_j7_preservado(client, seed_usuario, seed_paciente):
    """Os baldes e os campos do J.7 continuam de pé.

    O J.11 é aditivo: quem já consumia `posse`/`em_andamento`/`historico`,
    `sob_minha_custodia` e `detentor` não vê diferença.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    r = client.get("/paciente/pedidos-exame", headers=_headers(_token_paciente()))
    assert r.status_code == 200
    assert set(r.json()) == {"posse", "em_andamento", "historico"}

    cartao = _cartao(client, proto)
    assert cartao["sob_minha_custodia"] is True          # nunca saiu do cidadão
    assert cartao["detentor"] == "paciente"
    assert cartao["status"] == "emitido"
    assert "itens" in cartao
