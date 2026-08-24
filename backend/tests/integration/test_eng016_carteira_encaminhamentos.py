"""ENG-016 §4 — `GET /paciente/encaminhamentos`: a terceira circulação na carteira.

AS REGRAS QUE ESTE ARQUIVO GUARDA
---------------------------------
**§2 lei 4 — DOIS FATOS, DOIS CAMPOS.** O selo do cidadão mostra a data da
CONSULTA, nunca o timestamp da custódia. Mostrar um no lugar do outro faria a
carteira dizer que a consulta é hoje porque a posse mudou hoje — e o cidadão
apareceria no dia errado.

**§1a — a posse vem da CUSTÓDIA, nunca do status.** Um encaminhamento `agendado`
tanto pode estar com o cidadão (marcaram e ele ainda não foi) quanto com o
destino (já entregou). É `posse_tipo` que decide se o gesto "Entregar" aparece.

**O retorno vem junto.** Do ponto de vista do cidadão o percurso é um só — ele
levou, e o retorno voltou. Obrigá-lo a procurar a contrarreferência noutra lista
partiria em dois o que para ele é uma coisa só.

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

_CNS_DESTINO = "700000000000001"
_DATA_CONSULTA = "2026-09-15T14:30:00"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(cpf=SEED_PACIENTE_CPF): return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)
def _tok_dest(): return criar_access_token(sub=_CNS_DESTINO, role="prescritor", nome="DR DESTINO")


def _emitir(client, token) -> str:
    r = client.post("/encaminhamentos", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DRA ORIGEM",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO, "especialidade_destino": "CARDIOLOGIA",
        "finalidade": "avaliacao", "justificativa_clinica": "dor torácica",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _carteira(client) -> dict:
    r = client.get("/paciente/encaminhamentos", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    return r.json()


def _achar(lista, proto):
    return next((x for x in lista if x["protocolo"] == proto), None)


def test_o_encaminhamento_nasce_na_carteira_com_a_posse_do_cidadao(
    client, seed_usuario, seed_paciente
):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)

    item = _achar(_carteira(client)["ativos"], proto)
    assert item is not None, "o encaminhamento não chegou à carteira"
    assert item["posse_tipo"] == "paciente", "não nasceu na mão do cidadão"
    assert item["especialidade_destino"] == "CARDIOLOGIA"
    assert item["data_consulta"] is None, "sem marcação, não há data de consulta"


def test_a_data_da_consulta_nao_e_o_timestamp_da_custodia(client, seed_usuario, seed_paciente):
    """A LEI Nº 4, executável.

    O laboratório marca para 15/09; o cidadão entrega hoje. Se a carteira
    mostrasse o timestamp da custódia como "sua consulta", ele apareceria no
    dia errado — e o erro seria invisível, porque a data existe e parece certa.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": _DATA_CONSULTA},
                       headers=_h(_tok_dest())).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200

    item = _achar(_carteira(client)["ativos"], proto)
    assert item["data_consulta"] == _DATA_CONSULTA, (
        "a data da consulta se perdeu — ela vive no ledger, que é onde o fato "
        "foi registrado"
    )
    assert item["posse_desde"] != item["data_consulta"], (
        "os dois campos coincidiram: o selo está mostrando custódia como consulta"
    )


def test_a_posse_muda_com_o_gesto_do_cidadao_e_o_estado_nao(client, seed_usuario, seed_paciente):
    """O que decide se o botão "Entregar" aparece é a POSSE (§1a)."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    antes = _achar(_carteira(client)["ativos"], proto)
    assert antes["posse_tipo"] == "paciente"

    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200

    depois = _achar(_carteira(client)["ativos"], proto)
    assert depois["posse_tipo"] == "prescritor", "a entrega não apareceu na carteira"
    assert depois["status"] == antes["status"], "entregar mexeu no estado (§1a)"


def test_a_carteira_le_a_marcacao_MAIS_RECENTE_do_ledger(client, outer_conn, seed_usuario, seed_paciente):
    """O ledger é append-only; a leitura tem de pegar a que VALE.

    ⚠️ ACHADO, registrado como fato: **o encaminhamento não tem remarcação**.
    A máquina não admite `agendado → agendado` (`TRANSICOES_ENCAMINHAMENTO`), e
    não existe `/remarcar` como no objeto Agendamento. Quem quiser mudar a data
    hoje precisa cancelar e emitir de novo — o que, sendo objeto imutável (§1),
    é derivação, não edição.

    Escrevi este teste supondo que dava para remarcar, e a máquina recusou
    (409). O cenário foi refeito para o que EXISTE: o segundo evento é
    injetado direto no ledger — que é exatamente a forma que um `/remarcar`
    futuro produziria —, e o que se prova é que a leitura pega o último.
    Assim a carteira já está certa no dia em que a remarcação nascer.

    (A ausência de remarcação vai para a comissão de diagnóstico como GAP a
    classificar, não como bug desta entrega.)
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok_dest()
    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-01T08:00:00"},
                       headers=_h(td)).status_code == 200
    # A máquina recusa remarcar hoje — a prova de que o achado é real.
    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": _DATA_CONSULTA},
                       headers=_h(td)).status_code == 409

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM encaminhamentos WHERE protocolo = %s", (proto,))
        enc_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO encaminhamento_eventos
              (encaminhamento_id, tipo_evento, ator_tipo, ator_id, payload, created_at)
            VALUES (%s, 'encaminhamento_agendado', 'prescritor', %s, %s, NOW())
            """,
            (enc_id, _CNS_DESTINO, '{"data_agendamento": "%s"}' % _DATA_CONSULTA),
        )

    item = _achar(_carteira(client)["ativos"], proto)
    assert item["data_consulta"] == _DATA_CONSULTA, (
        f"a carteira mostrou uma marcação antiga: {item['data_consulta']} — "
        "mandaria o cidadão no dia que não vale mais"
    )


def test_o_retorno_vem_junto_do_encaminhamento(client, seed_usuario, seed_paciente):
    """Para o cidadão, ida e volta são UM percurso."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok_dest()
    client.post(f"/encaminhamentos/{proto}/agendar",
                json={"data_agendamento": _DATA_CONSULTA}, headers=_h(td))
    client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(_tok_pac()))
    client.post(f"/encaminhamentos/{proto}/atender", headers=_h(td))
    assert client.post(f"/encaminhamentos/{proto}/contrarreferir",
                       json={"conteudo_clinico": "avaliado; manter conduta"},
                       headers=_h(td)).status_code == 201

    item = _achar(_carteira(client)["ativos"], proto)
    assert item["contrarreferencia"] is not None, "o retorno não apareceu na carteira"
    assert "manter conduta" in item["contrarreferencia"]["conteudo_clinico"]
    assert item["posse_tipo"] == "paciente", "o atendimento devolveu a posse"


def test_encerrado_sai_dos_ativos_e_vai_para_o_historico(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok_dest()
    client.post(f"/encaminhamentos/{proto}/agendar",
                json={"data_agendamento": _DATA_CONSULTA}, headers=_h(td))
    client.post(f"/encaminhamentos/{proto}/atender", headers=_h(td))
    client.post(f"/encaminhamentos/{proto}/contrarreferir",
                json={"conteudo_clinico": "ok"}, headers=_h(td))
    assert client.post(f"/encaminhamentos/{proto}/encerrar", headers=_h(tp)).status_code == 200

    carteira = _carteira(client)
    assert _achar(carteira["ativos"], proto) is None
    assert _achar(carteira["historico"], proto) is not None


def test_a_carteira_e_do_dono_do_token(client, seed_usuario, seed_paciente):
    """Ownership vem do TOKEN, nunca de CPF na URL — molde de /paciente/laudos."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    r = client.get("/paciente/encaminhamentos", headers=_h(_tok_pac("39053344705")))
    assert r.status_code == 200
    dados = r.json()
    assert _achar(dados["ativos"], proto) is None, "carteira alheia vazou"
