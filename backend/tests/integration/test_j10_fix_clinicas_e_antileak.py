"""FIX do J.10 — relatório/faturamento por item + ordem anti-leak restaurada.

Achados da revisão retroativa do #170 (ENG-013 FASE 2), ambos reproduzidos antes
de corrigir. Este arquivo é a guarda executável dos dois.

ACHADO 1 — `clinicas.py` lia só posse de NÍVEL-PEDIDO
-----------------------------------------------------
A transferência parcial FECHA a linha de nível-pedido (§3.3 do DESENHO-J10) e
abre uma por item. As duas queries de `clinicas.py` filtravam `c.item_id IS
NULL`, então deixavam de casar qualquer linha: o pedido sumia inteiro do
relatório E do faturamento da unidade que detém itens dele — enquanto a FILA
continuava mostrando o trabalho. A unidade executava e não faturava, sem que
nada acusasse.

O mesmo fix fecha o outro lado da moeda: o `JOIN` antigo trazia TODOS os itens
do pedido para quem detivesse a linha de pedido. Depois da parcial isso vazaria
item de outro prestador — por isso há teste dos dois sentidos (o que aparece e
o que NÃO aparece).

ACHADO 2 — a ordem anti-leak (#52) invertida em três endpoints
--------------------------------------------------------------
Em `coletar`, `em-analise` e `resultado`, o guard do dispensador passou para
depois do 404 do item — e, com ele, para depois do 422 de pedido terminal. Um
CNPJ que não detém NADA aprendia pelo código de status que o pedido está
terminal. A convenção da casa, em todos os módulos, é **403 de posse precede
422 de estado**.

O fix é uma guarda GROSSA antes do estado, que separa **parte** de **estranho**
— distinção real, não repetição da guarda fina:

  · estranho (não detém nada do pedido) → 403, e não aprende NADA: nem que o
    pedido está terminal, nem se aquele id de item existe;
  · parte (detém o pedido ou algum item) → passa, e daí recebe respostas
    honestas, inclusive o 404 de um id que não existe — informação legítima
    para quem já enxerga os próprios itens.

A guarda FINA continua depois e barra a parte que tenta operar item alheio.
No `devolver`, a grossa vem antes também do 404 do item, senão um estranho
enumera os itens de um pedido alheio pelo código de status.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import csv
import io

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
_NOMES = ["HEMOGRAMA", "GLICEMIA", "TSH"]


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)
def _tok_lab(c): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _emitir(client, token_presc: str) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR J10FIX",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in _NOMES],
    }, headers=_h(token_presc))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ids(outer_conn, proto: str) -> list[int]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id FROM pedido_exame_itens i JOIN pedidos_exame p ON p.id = i.pedido_id "
            "WHERE p.protocolo = %s ORDER BY i.id", (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _transferir(client, proto: str, cnpj: str, itens: list[int] | None = None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"}
    if itens is not None:
        body["itens"] = itens
    return client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json=body, headers=_h(_tok_pac()))


def _csv_rows(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


def _relatorio(client, cnpj: str) -> list[dict]:
    return _csv_rows(client.get("/clinicas/relatorio.csv", headers=_h(_tok_lab(cnpj))))


def _faturamento(client, cnpj: str) -> list[dict]:
    return _csv_rows(client.get("/clinicas/faturamento.csv", headers=_h(_tok_lab(cnpj))))


# ===========================================================================
# ACHADO 1 — relatório e faturamento seguem a posse do ITEM
# ===========================================================================

def test_relatorio_mostra_os_itens_que_a_unidade_detem_apos_parcial(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O caso que sumia: 2 de 3 itens com o lab A.

    Antes do fix, o relatório de A vinha VAZIO — a linha de nível-pedido tinha
    sido fechada pela explosão e nada mais casava.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)

    assert _transferir(client, proto, _LAB_A, itens=ids[:2]).status_code == 201

    linhas = [x for x in _relatorio(client, _LAB_A) if x["protocolo"] == proto]
    assert linhas, "o pedido sumiu do relatório da unidade que detém 2 itens"
    assert {x["nome_exame"] for x in linhas} == set(_NOMES[:2])


def test_relatorio_nao_vaza_item_de_outro_detentor(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O outro lado da moeda — e o motivo de o fix ser por ITEM, não por pedido.

    O `JOIN` antigo trazia todos os itens do pedido para quem detivesse a linha
    de pedido. Com a parcial, isso seria vazamento entre prestadores: A veria (e
    faturaria) exame que está com B ou com o cidadão.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)

    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    nomes_a = {x["nome_exame"] for x in _relatorio(client, _LAB_A) if x["protocolo"] == proto}
    nomes_b = {x["nome_exame"] for x in _relatorio(client, _LAB_B) if x["protocolo"] == proto}

    assert nomes_a == {_NOMES[0]}, f"A viu além do que detém: {nomes_a}"
    assert nomes_b == {_NOMES[1]}, f"B viu além do que detém: {nomes_b}"
    # O 3º ficou com o cidadão — não é de ninguém no balcão.
    assert _NOMES[2] not in nomes_a and _NOMES[2] not in nomes_b


def test_faturamento_conta_item_detido_apos_parcial(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O achado que mexe em dinheiro: a unidade coletava, registrava resultado
    e o faturamento vinha com ZERO linhas."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=ids[:2]).status_code == 201

    hl = _h(_tok_lab(_LAB_A))
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/coletar",
                       json={}, headers=hl).status_code == 201
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/resultado",
                       json={"resultado_resumo": "normal"},
                       headers=hl).status_code in (200, 201)

    assert len(_faturamento(client, _LAB_A)) > 0, "item com resultado não entrou no faturamento"


def test_faturamento_nao_conta_item_de_outro_detentor(
    client, outer_conn, seed_usuario, seed_paciente
):
    """B não fatura o que A produziu, ainda que no mesmo pedido."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    hl = _h(_tok_lab(_LAB_A))
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/coletar",
                       json={}, headers=hl).status_code == 201
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/resultado",
                       json={"resultado_resumo": "normal"},
                       headers=hl).status_code in (200, 201)

    assert len(_faturamento(client, _LAB_A)) > 0
    assert len(_faturamento(client, _LAB_B)) == 0, "B faturou item que não detém"


def test_transferencia_integral_segue_como_antes(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Regressão: sem parcial, a posse continua de nível-pedido e o relatório
    lista os itens todos — o caminho do J.7 intacto."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    nomes = {x["nome_exame"] for x in _relatorio(client, _LAB_A) if x["protocolo"] == proto}
    assert nomes == set(_NOMES)


def test_ex_custodiante_nao_aparece_no_relatorio(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Quem devolveu o item sai do próprio relatório — o fix não afrouxou o
    'custódia ATUAL, não histórica' que o relatório já garantia."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    r = client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/devolver",
                    json={"motivo": "não realizamos este exame"},
                    headers=_h(_tok_lab(_LAB_A)))
    assert r.status_code == 200, r.text

    nomes = {x["nome_exame"] for x in _relatorio(client, _LAB_A) if x["protocolo"] == proto}
    assert nomes == set(), f"ex-custodiante seguiu no relatório: {nomes}"


# ===========================================================================
# ACHADO 2 — 403 de posse precede 422 de estado
# ===========================================================================

_ROTAS = [
    ("coletar",    {}),
    ("em-analise", {}),
    ("resultado",  {"resultado_resumo": "x"}),
]


@pytest.mark.parametrize("rota,corpo", _ROTAS)
def test_nao_dono_leva_403_e_nao_o_422_de_pedido_terminal(
    client, outer_conn, seed_usuario, seed_paciente, rota, corpo
):
    """A regressão que este fix desfaz.

    O CÓDIGO importa: `nao_e_dono_do_pedido_exame` prova que o 403 veio da
    POSSE. Um 403 genérico do `require_role` passaria o teste pelo motivo
    errado — `dispensador` está no RBAC destes endpoints.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    assert client.post(f"/pedidos-exame/{proto}/cancelar",
                       json={"motivo": "teste"}, headers=_h(tp)).status_code == 200

    r = client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/{rota}",
                    json=corpo, headers=_h(_tok_lab(_LAB_B)))
    assert r.status_code == 403, f"{rota}: vazou estado ({r.status_code}) a quem não detém nada"
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


@pytest.mark.parametrize("rota,corpo", _ROTAS)
def test_detentor_de_outro_item_segue_barrado_pela_guarda_fina(
    client, outer_conn, seed_usuario, seed_paciente, rota, corpo
):
    """Ser parte do pedido não dá direito ao item alheio.

    B detém o item 1 do mesmo pedido; ao operar o item 0 (de A) ele passa a
    guarda GROSSA e tem de ser barrado pela FINA — com o mesmo 403.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    r = client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/{rota}",
                    json=corpo, headers=_h(_tok_lab(_LAB_B)))
    assert r.status_code == 403, f"{rota}: B operou item de A"
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_detentor_legitimo_continua_operando(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Regressão do caminho feliz: a guarda não barra quem detém."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    hl = _h(_tok_lab(_LAB_A))
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/coletar",
                       json={}, headers=hl).status_code == 201
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/em-analise",
                       json={}, headers=hl).status_code == 200
    assert client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/resultado",
                       json={"resultado_resumo": "normal"},
                       headers=hl).status_code in (200, 201)

@pytest.mark.parametrize("rota,corpo", _ROTAS + [("devolver", {"motivo": "não realizamos"})])
def test_nao_dono_nao_descobre_se_o_item_existe(
    client, outer_conn, seed_usuario, seed_paciente, rota, corpo
):
    """403 precede o 404 do ITEM para quem é ESTRANHO ao pedido.

    Sem isto, quem não detém nada distingue pelo código de status um id de item
    que existe de um que não existe, e enumera os itens de um pedido alheio de
    fora. O par deste teste é o seguinte: para quem é PARTE, o 404 continua
    valendo.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    inexistente = max(ids) + 99_999
    for item in (ids[0], inexistente):
        r = client.post(f"/pedidos-exame/{proto}/itens/{item}/{rota}",
                        json=corpo, headers=_h(_tok_lab(_LAB_B)))
        assert r.status_code == 403, (
            f"{rota}: item {'existente' if item == ids[0] else 'inexistente'} "
            f"devolveu {r.status_code} a quem não detém nada"
        )
        assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_dono_do_pedido_ainda_recebe_404_de_item_inexistente(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O 403 grosso não pode ter engolido o 404 de quem TEM direito a ele.

    É a razão de a guarda ser GROSSA e não a fina promovida: quem é parte do
    pedido passa e recebe o 404 honesto. Foi este par que mostrou que as duas
    guardas guardam coisas diferentes — a fina sozinha, no topo, devolveria 403
    a um custodiante legítimo que só errou o id.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    r = client.post(f"/pedidos-exame/{proto}/itens/{max(ids) + 99_999}/coletar",
                    json={}, headers=_h(_tok_lab(_LAB_A)))
    assert r.status_code == 404, r.text
