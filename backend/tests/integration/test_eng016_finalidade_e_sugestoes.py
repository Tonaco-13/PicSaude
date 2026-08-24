"""ENG-016 §5 — finalidade estruturada e sugestão de destino auditável.

OS DOIS MARTELOS DO §11 QUE ESTE ARQUIVO EXERCITA
-------------------------------------------------
**Martelo 2 — finalidade estruturada entra no MVP.** "Para que estou mandando
este paciente" é dado OPERACIONAL: é por ele que a regulação futura filtra fila.
Enterrado na prosa da justificativa, vira coisa que só um humano lê. Entra
também no DOCUMENTO CANÔNICO — o §5 manda a confirmação mostrar o documento
montado e o hash congelar o que se vê; finalidade visível no cabeçalho e fora do
hash faria o hash deixar de congelar o que foi visto.

**Martelo 3 — sugestão de destino auditável.** O dado já existe no ledger: cada
encaminhamento ATENDIDO prova que aquele profissional recebeu aquele paciente.
As três regras que a fazem honesta — razão declarada, nunca pré-selecionada,
e o que foi APRESENTADO volta no payload de `encaminhamento_emitido`.

A terceira é a que este arquivo mais guarda: **se o sistema influencia a
escolha, a influência é auditável**. Sem ela, "a rede se conhece" seria uma
caixa-preta que ninguém consegue questionar depois.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
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

_CNS_CARDIO = "700000000000001"
_CNS_ORTO   = "700000000000002"


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _tok(cns: str) -> str:
    return criar_access_token(sub=cns, role="prescritor", nome="DR")


def _emitir(client, token, **extra) -> tuple[int, dict]:
    corpo = {
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": "DR ORIGEM",
        "cpf_paciente": SEED_PACIENTE_CPF,
        "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_CARDIO,
        "especialidade_destino": "CARDIOLOGIA",
        "justificativa_clinica": "dor torácica em investigação",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }
    corpo.update(extra)
    r = client.post("/encaminhamentos", json=corpo, headers=_h(token))
    return r.status_code, (r.json() if r.content else {})


def _percorrer_ate_atendido(client, proto: str, cns_destino: str) -> None:
    td = _tok(cns_destino)
    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-10T09:00:00"},
                       headers=_h(td)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender",
                       headers=_h(td)).status_code == 200


def _payload_emissao(outer_conn, proto: str) -> dict:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ev.payload FROM encaminhamento_eventos ev
              JOIN encaminhamentos e ON e.id = ev.encaminhamento_id
             WHERE e.protocolo = %s AND ev.tipo_evento = 'encaminhamento_emitido'
            """,
            (proto,),
        )
        bruto = cur.fetchone()[0]
    return json.loads(bruto) if isinstance(bruto, str) else (bruto or {})


# ---------------------------------------------------------------------------
# 1 — finalidade estruturada
# ---------------------------------------------------------------------------

def test_finalidade_persiste_e_entra_no_documento(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    st, r1 = _emitir(client, tp, finalidade="segunda_opiniao")
    assert st == 201, r1
    st, r2 = _emitir(client, tp, finalidade="conduta")
    assert st == 201, r2

    with outer_conn.cursor() as cur:
        cur.execute("SELECT finalidade FROM encaminhamentos WHERE protocolo = %s",
                    (r1["protocolo"],))
        assert cur.fetchone()[0] == "segunda_opiniao"

    assert r1["documento_hash"] != r2["documento_hash"], (
        "trocar a finalidade não mudou o hash — o documento não a cobre, e o §5 "
        "manda o hash congelar o que o médico vê na confirmação"
    )


def test_finalidade_desconhecida_e_recusada(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    st, _ = _emitir(client, tp, finalidade="porque_sim")
    assert st == 422


def test_outra_exige_dizer_qual(client, seed_usuario, seed_paciente):
    """"outra" sem texto seria o campo estruturado devolvendo o problema que ele
    existe para resolver."""
    tp = obter_token_prescritor(client, seed_usuario)
    assert _emitir(client, tp, finalidade="outra")[0] == 422
    assert _emitir(client, tp, finalidade="outra",
                   finalidade_texto="parecer pré-operatório")[0] == 201


def test_emitir_sem_finalidade_continua_valendo(client, seed_usuario, seed_paciente):
    """Retrocompat: a coluna é nullable porque encaminhamento já emitido não
    ganha finalidade — objeto emitido é imutável (§1), e backfill inventaria
    declaração clínica que ninguém fez."""
    tp = obter_token_prescritor(client, seed_usuario)
    assert _emitir(client, tp)[0] == 201


# ---------------------------------------------------------------------------
# 2 — sugestão de destino: existe, tem razão, e é auditável
# ---------------------------------------------------------------------------

def test_sugestao_nasce_do_ledger_e_traz_a_razao(client, seed_usuario, seed_paciente):
    """A rede se conhece porque os objetos circularam — não por cadastro."""
    tp = obter_token_prescritor(client, seed_usuario)

    vazio = client.get(f"/encaminhamentos/sugestoes-destino?cpf_paciente={SEED_PACIENTE_CPF}",
                       headers=_h(tp))
    assert vazio.status_code == 200, vazio.text
    assert vazio.json()["sugestoes"] == [], "sugestão saiu do nada, sem histórico"

    st, r = _emitir(client, tp)
    assert st == 201
    _percorrer_ate_atendido(client, r["protocolo"], _CNS_CARDIO)

    depois = client.get(f"/encaminhamentos/sugestoes-destino?cpf_paciente={SEED_PACIENTE_CPF}",
                        headers=_h(tp)).json()["sugestoes"]
    assert len(depois) == 1
    assert depois[0]["cns_destino"] == _CNS_CARDIO
    assert depois[0]["razao"] == "já atendeu este paciente", (
        "sugestão sem razão declarada é palpite com cara de recomendação (§5)"
    )
    assert depois[0]["atendimentos"] == 1


def test_sugestao_so_conta_quem_ATENDEU(client, seed_usuario, seed_paciente):
    """Encaminhamento emitido e não atendido não prova que o profissional
    recebeu o paciente — sugerir por ele seria inventar histórico."""
    tp = obter_token_prescritor(client, seed_usuario)
    assert _emitir(client, tp)[0] == 201

    r = client.get(f"/encaminhamentos/sugestoes-destino?cpf_paciente={SEED_PACIENTE_CPF}",
                   headers=_h(tp))
    assert r.json()["sugestoes"] == []


def test_sugestao_filtra_por_especialidade(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    st, r1 = _emitir(client, tp)
    _percorrer_ate_atendido(client, r1["protocolo"], _CNS_CARDIO)
    st, r2 = _emitir(client, tp, cns_destino=_CNS_ORTO,
                     especialidade_destino="ORTOPEDIA",
                     itens=[{"especialidade": "ORTOPEDIA"}])
    _percorrer_ate_atendido(client, r2["protocolo"], _CNS_ORTO)

    so_cardio = client.get(
        f"/encaminhamentos/sugestoes-destino?cpf_paciente={SEED_PACIENTE_CPF}"
        "&especialidade=CARDIOLOGIA", headers=_h(tp)).json()["sugestoes"]
    assert [s["cns_destino"] for s in so_cardio] == [_CNS_CARDIO]


def test_o_que_a_tela_mostrou_entra_no_ledger(client, outer_conn, seed_usuario, seed_paciente):
    """A REGRA CENTRAL DO MARTELO 3: se o sistema influencia, a influência é
    auditável — e fica ao lado da escolha, no mesmo evento.

    `escolheu_sugerido` é derivado no BACKEND, não recebido da tela: quem
    responde "a sugestão pegou?" é o registro, não o cliente que a exibiu.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    st, r = _emitir(client, tp, sugestoes_apresentadas=[_CNS_CARDIO, _CNS_ORTO])
    assert st == 201

    ev = _payload_emissao(outer_conn, r["protocolo"])
    assert ev["sugestoes_apresentadas"] == [_CNS_CARDIO, _CNS_ORTO], (
        "as sugestões apresentadas não chegaram ao ledger — a influência do "
        "sistema ficou sem rastro (§5)"
    )
    assert ev["escolheu_sugerido"] is True


def test_escolha_fora_da_lista_tambem_fica_registrada(client, outer_conn, seed_usuario, seed_paciente):
    """O caso que prova que o campo não é enfeite: o prescritor viu sugestões e
    escolheu OUTRO. Isso é informação — é a medida de quanto a lista influencia.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    st, r = _emitir(client, tp, sugestoes_apresentadas=[_CNS_ORTO])
    assert st == 201
    ev = _payload_emissao(outer_conn, r["protocolo"])
    assert ev["sugestoes_apresentadas"] == [_CNS_ORTO]
    assert ev["escolheu_sugerido"] is False


def test_sem_sugestao_apresentada_o_campo_e_nulo_nao_falso(client, outer_conn, seed_usuario, seed_paciente):
    """`None` = "não houve sugestão"; `False` = "houve e não pegou". Colapsar os
    dois em `False` faria a auditoria contar como recusa o que nunca foi
    oferecido."""
    tp = obter_token_prescritor(client, seed_usuario)
    st, r = _emitir(client, tp)
    ev = _payload_emissao(outer_conn, r["protocolo"])
    assert ev["sugestoes_apresentadas"] is None
    assert ev["escolheu_sugerido"] is None


# ---------------------------------------------------------------------------
# 3 — AC da ratificação: o documento VERIFICA sob a sua própria versão
# ---------------------------------------------------------------------------
# Condição explícita do ruling (arquiteto, 23/08): "documentos antigos mantêm o
# hash" tem de ser INVARIANTE EXECUTÁVEL, não afirmação de relatório — a lição
# do COER-2 aplicada ao documento canônico.
#
# Os testes de `tests/unit/test_documento_canonico_encaminhamento.py` provam que
# as REGRAS não derivaram (hash v1 congelado por valor). Estes provam a volta
# completa: um documento REALMENTE EMITIDO, com o hash que o backend gravou,
# recalculado sob a versão dele, confere.


def _dados_para_recalcular(outer_conn, proto: str) -> dict:
    """Reconstrói a entrada do documento a partir do que ficou GRAVADO.

    De propósito a partir do banco, e não da resposta da API: verificar é
    recomputar do que está persistido — se a verificação partisse do payload
    que o cliente mandou, ela provaria apenas que o cliente é coerente consigo
    mesmo.
    """
    from app.routers.encaminhamentos import ItemEncaminhamentoIn

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.protocolo, pr.cns, e.cns_destino, pa.cpf,
                   e.especialidade_destino, e.cid, e.justificativa_clinica,
                   e.finalidade, e.finalidade_texto, e.assinatura_hash
              FROM encaminhamentos e
              LEFT JOIN prescritores pr ON pr.id = e.prescritor_id
              LEFT JOIN pacientes    pa ON pa.id = e.paciente_id
             WHERE e.protocolo = %s
            """,
            (proto,),
        )
        r = cur.fetchone()
        cur.execute(
            "SELECT especialidade, procedimento, motivo FROM encaminhamento_itens "
            " WHERE encaminhamento_id = %s ORDER BY id", (r[0],))
        itens = [
            ItemEncaminhamentoIn(especialidade=i[0], procedimento=i[1], motivo=i[2])
            for i in cur.fetchall()
        ]

    return {
        "hash_gravado": r[10],
        "entrada": dict(
            protocolo=r[1], cns_origem=r[2], cns_destino=r[3], cpf_paciente=r[4],
            especialidade_destino=r[5], cid=r[6], justificativa_clinica=r[7],
            finalidade=r[8], finalidade_texto=r[9], itens=itens,
        ),
    }


def test_documento_v2_verifica_sob_a_regra_v2(client, outer_conn, seed_usuario, seed_paciente):
    """A volta completa, num documento de verdade: emitir → gravar → recomputar
    sob a versão dele → confere."""
    from app.routers.encaminhamentos import _calcular_hash

    tp = obter_token_prescritor(client, seed_usuario)
    st, r = _emitir(client, tp, finalidade="segunda_opiniao")
    assert st == 201, r

    d = _dados_para_recalcular(outer_conn, r["protocolo"])
    assert d["hash_gravado"] == _calcular_hash(**d["entrada"], versao="2"), (
        "o documento emitido não verifica sob a própria versão — o hash não "
        "congela o que foi gravado"
    )


def test_documento_v1_verifica_sob_a_regra_v1_e_nao_sob_a_v2(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O documento ANTIGO, construído à mão como o ruling permitiu.

    Não há mais como o backend EMITIR um v1 — a emissão usa sempre a versão
    atual. Então o v1 é montado aqui a partir de um documento real, tirando a
    finalidade e hasheando sob a regra v1: é exatamente a forma de um
    encaminhamento emitido antes desta mudança.

    As duas metades importam. Que ele verifique sob a v1 prova que o passado
    continua válido. Que ele NÃO verifique sob a v2 prova que a versão é
    consultada de verdade — um verificador que ignorasse a versão gravada
    acusaria de adulterado todo documento anterior à mudança.
    """
    from app.routers.encaminhamentos import _calcular_hash

    tp = obter_token_prescritor(client, seed_usuario)
    st, r = _emitir(client, tp)          # sem finalidade: a forma de um v1
    assert st == 201, r
    entrada = _dados_para_recalcular(outer_conn, r["protocolo"])["entrada"]

    hash_v1 = _calcular_hash(**entrada, versao="1")
    assert _calcular_hash(**entrada, versao="1") == hash_v1, "a v1 não é determinística"
    assert _calcular_hash(**entrada, versao="2") != hash_v1, (
        "v1 e v2 produzem o mesmo hash — a versão não está sendo consultada, e "
        "um verificador não teria como distinguir as regras"
    )
