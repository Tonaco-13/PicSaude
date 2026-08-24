"""ENG-016 §1a — o gesto `entregar` do cidadão, e o `agendar` sem custódia.

AC (vii) DO DESPACHO, LITERAL
----------------------------
  · **entregar muda POSSE sem tocar ESTADO**;
  · **agendar agenda sem tocar POSSE**,
com guarda de rumo CONTANDO EVENTOS — o mesmo método do #183, onde "Executar
agora" precisava provar que continuava sendo um fato só.

POR QUE CONTAR EVENTOS É A GUARDA CERTA AQUI
--------------------------------------------
O defeito que o §1a desfaz não era um bug: era um gesto carregando DOIS fatos
porque era o único gesto disponível. `agendar` marcava hora **e** movia a posse.
Um teste que olhasse só o resultado final ("a posse está no destino") passaria
nas duas versões. O que distingue é a CONTAGEM: depois do §1a, `agendar` emite
`encaminhamento_agendado` e mais nada; a posse só se move quando o cidadão age.

É o J.7 aplicado ao terceiro objeto — e a razão de o corolário valer aqui
também: um encaminhamento `agendado` tanto pode estar com o cidadão (marcou e
ainda não foi) quanto com o destino (já entregou). Quem responde "onde está" é
`encaminhamento_custodia`.

O JUIZ ESTÁ NA MAIN
-------------------
`test_cada_gesto_deixa_exatamente_uma_posse_ativa` (#185) fixa que cada gesto
deixa UMA posse ativa. Ele passa antes e depois desta mudança — é isso que
prova que mover a ESCRITA de gesto não afrouxou o INVARIANTE.

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
_CPF_ALHEIO  = "39053344705"


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _tok_pac(cpf: str = SEED_PACIENTE_CPF) -> str:
    return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)


def _tok_destino() -> str:
    return criar_access_token(sub=_CNS_DESTINO, role="prescritor", nome="DR DESTINO")


def _emitir(client, token_origem: str) -> str:
    r = client.post("/encaminhamentos", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": "DR ORIGEM",
        "cpf_paciente": SEED_PACIENTE_CPF,
        "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "CARDIOLOGIA",
        "justificativa_clinica": "dor torácica em investigação",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, headers=_h(token_origem))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _enc_id(outer_conn, proto: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM encaminhamentos WHERE protocolo = %s", (proto,))
        return cur.fetchone()[0]


def _posse(outer_conn, enc_id: int) -> tuple[str, str, str] | None:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT detentor_tipo, detentor_id, motivo FROM encaminhamento_custodia "
            " WHERE encaminhamento_id = %s AND encerrada_em IS NULL", (enc_id,))
        r = cur.fetchone()
        return tuple(r) if r else None


def _eventos(outer_conn, enc_id: int) -> list[str]:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT tipo_evento FROM encaminhamento_eventos "
                    " WHERE encaminhamento_id = %s ORDER BY id", (enc_id,))
        return [r[0] for r in cur.fetchall()]


def _status(outer_conn, enc_id: int) -> str:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM encaminhamentos WHERE id = %s", (enc_id,))
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# AC (vii), metade 1 — agendar NÃO toca posse
# ---------------------------------------------------------------------------

def test_agendar_nao_move_a_posse_e_emite_um_fato_so(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A guarda de rumo, contando eventos.

    Antes do §1a este gesto emitia DOIS eventos — `encaminhamento_agendado` e
    `custodia_transferida` — e movia a posse ao destino. Marcar hora não é
    entregar documento; se voltar a ser, este teste cai.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)
    antes = _eventos(outer_conn, eid)
    posse_antes = _posse(outer_conn, eid)

    r = client.post(f"/encaminhamentos/{proto}/agendar",
                    json={"data_agendamento": "2026-09-10T09:00:00"},
                    headers=_h(_tok_destino()))
    assert r.status_code == 200, r.text

    novos = _eventos(outer_conn, eid)[len(antes):]
    assert novos == ["encaminhamento_agendado"], (
        f"agendar deixou de ser um fato só: {novos} — a posse voltou a viajar "
        "de carona com a marcação (o padrão pré-J.7)"
    )
    assert _posse(outer_conn, eid) == posse_antes, "agendar moveu a posse"
    assert _status(outer_conn, eid) == "agendado", "o estado, esse sim, mudou"


# ---------------------------------------------------------------------------
# AC (vii), metade 2 — entregar move posse SEM tocar estado
# ---------------------------------------------------------------------------

def test_entregar_move_a_posse_sem_tocar_o_estado(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O gesto do cidadão: espelho do transferir-farmácia e do -laboratório."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)
    assert _posse(outer_conn, eid)[0] == "paciente"
    estado_antes = _status(outer_conn, eid)
    antes = _eventos(outer_conn, eid)

    r = client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text

    tipo, detentor, motivo = _posse(outer_conn, eid)
    assert (tipo, detentor) == ("prescritor", _CNS_DESTINO)
    assert motivo == "apresentacao_cidadao", (
        "o motivo canônico do gesto do cidadão se perdeu"
    )
    assert _status(outer_conn, eid) == estado_antes, (
        "entregar mexeu no ESTADO — posse não é etapa clínica (§1a)"
    )
    novos = _eventos(outer_conn, eid)[len(antes):]
    assert novos == ["custodia_transferida"], f"entregar não é um fato só: {novos}"


def test_entregar_funciona_depois_de_agendado_e_a_ordem_nao_importa(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O corolário do §1a, exercitado: `agendado` NÃO diz onde o objeto está.

    A unidade marca a hora e o cidadão entrega quando for — nesta ordem ou na
    inversa. Se a tela (ou o backend) voltar a amarrar posse a estado, um dos
    dois caminhos quebra.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)

    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-10T09:00:00"},
                       headers=_h(_tok_destino())).status_code == 200
    assert _posse(outer_conn, eid)[0] == "paciente", "agendado e ainda com o cidadão"

    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200
    assert _posse(outer_conn, eid)[0] == "prescritor"
    assert _status(outer_conn, eid) == "agendado", "a entrega não mexe no estado"


# ---------------------------------------------------------------------------
# Guards do gesto novo
# ---------------------------------------------------------------------------

def test_entregar_duas_vezes_ensina_em_vez_de_so_recusar(
    client, outer_conn, seed_usuario, seed_paciente
):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200

    r = client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(_tok_pac()))
    assert r.status_code == 422, r.text
    assert "já está com o profissional de destino" in r.json()["detail"], (
        "a mensagem não diz ao cidadão o que aconteceu — dizer só 'não pode' o "
        "manda procurar um erro que não é dele"
    )


def test_paciente_alheio_nao_entrega_e_nao_descobre_o_protocolo(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Anti-leak (#52): 403 de dono ANTES de qualquer 422 de estado — e 404 para
    o que não existe, sem distinguir pelo status um protocolo alheio."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)

    r = client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(_tok_pac(_CPF_ALHEIO)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_encaminhamento"

    r404 = client.post("/encaminhamentos/nao-existe-mesmo/entregar",
                       headers=_h(_tok_pac(_CPF_ALHEIO)))
    assert r404.status_code == 404


def test_prescritor_nao_entrega_pelo_cidadao(client, outer_conn, seed_usuario, seed_paciente):
    """O gesto é DO CIDADÃO. Se o prescritor pudesse fazê-lo, o §1a viraria
    enfeite: a posse voltaria a se mover sem o protagonista agir."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    r = client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(tp))
    assert r.status_code == 403, r.text


def test_encaminhamento_fisico_nao_circula(client, outer_conn, seed_usuario, seed_paciente):
    """Emissão física não gera custódia (§6 do CLAUDE.md, mesma regra da
    receita). Sem posse não há o que entregar — 422 que explica, não 500."""
    tp = obter_token_prescritor(client, seed_usuario)
    r = client.post("/encaminhamentos/fisica", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": "DR ORIGEM",
        "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "CARDIOLOGIA",
        "justificativa_clinica": "avaliação",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    resp = client.post(f"/encaminhamentos/{proto}/entregar", headers=_h(_tok_pac()))
    assert resp.status_code in (403, 422), resp.text
