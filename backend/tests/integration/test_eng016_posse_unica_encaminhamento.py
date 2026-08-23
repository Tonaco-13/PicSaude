"""Posse única no encaminhamento e na contrarreferência — ENG-016 §6, dialeto PostgreSQL.

O QUE ESTE ARQUIVO TRAVA
------------------------
1. **A constraint existe e MORDE, nas DUAS tabelas.** Dupla posse ativa do mesmo
   encaminhamento — ou da mesma contrarreferência — é `IntegrityError`. O R2 na
   camada de custódia (CLAUDE.md §2a): um objeto em dois lugares ao mesmo tempo
   é alarme, não erro cosmético. Deixa de ser convenção de código e vira
   invariante de banco.
2. **A guarda vale no nível-OBJETO**, que é o único que estas tabelas usam hoje
   (`item_id` sempre NULL). Sem `NULLS NOT DISTINCT`, dois `(obj_id, NULL)` não
   colidiriam e o índice não guardaria absolutamente nada — seria uma constraint
   decorativa, o pior dos mundos (parece protegido e não está).
3. **Todo caminho de produto continua deixando UMA posse ativa.** Emitir,
   agendar e atender passam pelo par fechar→abrir; depois de cada um existe
   exatamente uma. É o que a constraint prova em silêncio e o que este arquivo
   prova em voz alta, gesto por gesto — a regressão que o PR 2 vai exercitar
   quando o gesto `entregar` do cidadão (§1a) entrar.
4. **A constraint guarda EXCLUSIVIDADE, não imobilidade**: posse encerrada
   convive com posse ativa, senão o objeto não poderia circular.

O par em SQLite está em `tests/test_eng016_posse_unica_sqlite.py` (§9 do
CLAUDE.md: os dois dialetos, sempre — foi assim que os triggers do ledger
passaram meses existindo só no bootstrap).

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

from contextlib import contextmanager

import psycopg2

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNS_DESTINO = "700000000000001"
_CNS_OUTRO   = "700000000000002"


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _tok_destino(cns: str = _CNS_DESTINO) -> str:
    return criar_access_token(sub=cns, role="prescritor", nome="DR DESTINO")


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


def _ativas(outer_conn, enc_id: int) -> list[tuple]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id, detentor_tipo, detentor_id FROM encaminhamento_custodia "
            " WHERE encaminhamento_id = %s AND encerrada_em IS NULL ORDER BY id",
            (enc_id,),
        )
        return cur.fetchall()


@contextmanager
def _espera_unique_violation(outer_conn, nome: str):
    """Espera `UniqueViolation` SEM destruir o isolamento do teste.

    O `outer_conn` mantém UM outer tx por teste, revertido no teardown. Depois
    de um erro o PostgreSQL bloqueia a transação até um rollback; mas
    `outer_conn.rollback()` desfaria o setup deste teste e `commit()` vazaria
    linhas para os seguintes — rompendo a isolação do arquivo inteiro. SAVEPOINT
    contém a violação onde ela acontece.
    """
    with outer_conn.cursor() as cur:
        cur.execute(f"SAVEPOINT {nome}")
    try:
        yield
    except psycopg2.errors.UniqueViolation:
        with outer_conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {nome}")
        return
    raise AssertionError(
        "esperava UniqueViolation — a constraint de posse única não mordeu"
    )


# ---------------------------------------------------------------------------
# 1 — a constraint morde, nas duas tabelas
# ---------------------------------------------------------------------------

def test_constraint_recusa_dupla_posse_ativa_do_encaminhamento(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Injetado por SQL CRU, de propósito: o objetivo é provar que o BANCO
    recusa, não que o código evita. Invariante que só o código sustenta é a
    lição do COER-2, e é ela que este PR encerra na terceira circulação."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)

    assert len(_ativas(outer_conn, eid)) == 1, "a emissão abriu exatamente uma posse"

    with _espera_unique_violation(outer_conn, "sp_dupla_enc"):
        with outer_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO encaminhamento_custodia
                  (encaminhamento_id, item_id, detentor_tipo, detentor_id,
                   transferida_em, encerrada_em, motivo, created_at)
                VALUES (%s, NULL, 'prescritor', %s, 'agora', NULL, 'injetado', NOW())
                """,
                (eid, _CNS_OUTRO),
            )


def test_constraint_recusa_dupla_posse_ativa_da_contrarreferencia(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A metade que quase ficou de fora.

    A CR tem custódia PRÓPRIA (errata 1 do arquiteto — Fork 3, verificado): é
    objeto derivado com posse própria, não um campo do encaminhamento. Guardar
    só o encaminhamento deixaria metade da terceira circulação no regime antigo.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok_destino()
    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-10T09:00:00"},
                       headers=_h(td)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender",
                       headers=_h(td)).status_code == 200
    r = client.post(f"/encaminhamentos/{proto}/contrarreferir", json={
        "conteudo_clinico": "avaliado; conduta ajustada e devolvido à origem",
    }, headers=_h(td))
    assert r.status_code == 201, r.text

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM contrarreferencias WHERE protocolo = %s",
                    (r.json()["protocolo_contrarreferencia"],))
        cr_id = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM contrarreferencia_custodia "
            " WHERE contrarreferencia_id = %s AND encerrada_em IS NULL", (cr_id,))
        assert cur.fetchone()[0] == 1

    with _espera_unique_violation(outer_conn, "sp_dupla_cr"):
        with outer_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contrarreferencia_custodia
                  (contrarreferencia_id, item_id, detentor_tipo, detentor_id,
                   transferida_em, encerrada_em, motivo, created_at)
                VALUES (%s, NULL, 'prescritor', %s, 'agora', NULL, 'injetado', NOW())
                """,
                (cr_id, _CNS_OUTRO),
            )


def test_a_constraint_guarda_exclusividade_nao_imobilidade(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Posse ENCERRADA convive com posse ativa — senão o objeto não circularia.

    O índice é PARCIAL (`WHERE encerrada_em IS NULL`) exatamente por isto. Um
    índice total sobre `(obj, item)` travaria o segundo handoff e transformaria
    a guarda contra dupla posse numa guarda contra o próprio fluxo.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)

    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE encaminhamento_custodia SET encerrada_em = 'fechada' "
            " WHERE encaminhamento_id = %s AND encerrada_em IS NULL", (eid,))
        cur.execute(
            """
            INSERT INTO encaminhamento_custodia
              (encaminhamento_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, NULL, 'prescritor', %s, 'agora', NULL, 'segundo_dono', NOW())
            """,
            (eid, _CNS_DESTINO),
        )
    assert len(_ativas(outer_conn, eid)) == 1


# ---------------------------------------------------------------------------
# 2 — os caminhos de produto deixam UMA posse ativa (regressão para o PR 2)
# ---------------------------------------------------------------------------

def test_emitir_abre_a_posse_no_cidadao(client, outer_conn, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    eid = _enc_id(outer_conn, _emitir(client, tp))
    ativas = _ativas(outer_conn, eid)
    assert len(ativas) == 1
    assert ativas[0][1] == "paciente", "o encaminhamento nasce na mão do cidadão"


def test_cada_gesto_deixa_exatamente_uma_posse_ativa(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A cadeia de hoje, gesto a gesto.

    Vale como REGRESSÃO para o §1a: o PR 2 tira a escrita de custódia do
    `agendar` e a move para o gesto `entregar` do cidadão. O que não pode mudar
    é o invariante — uma posse ativa depois de cada gesto —, e é o que este
    teste fixa antes da mudança.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    eid = _enc_id(outer_conn, proto)
    td = _tok_destino()

    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-10T09:00:00"},
                       headers=_h(td)).status_code == 200
    ativas = _ativas(outer_conn, eid)
    assert len(ativas) == 1, f"agendar deixou {len(ativas)} posses ativas"

    assert client.post(f"/encaminhamentos/{proto}/atender",
                       headers=_h(td)).status_code == 200
    ativas = _ativas(outer_conn, eid)
    assert len(ativas) == 1, f"atender deixou {len(ativas)} posses ativas"
    assert ativas[0][1] == "paciente", "atender devolve a posse ao cidadão"
