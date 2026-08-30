"""DESENHO-TALAO-DIGITAL-SNCR.md §2 (G2) — testes de lotes (talonários
digitais) do SNCRStub e do endpoint POST /receituarios/lotes.

Cobertura
---------
1. Adapter (unidade contra conn real, via `outer_conn`/SavepointConnection):
   - adquirir_lote cria faixa sequencial [1..quantidade], lote_id STUB-LOTE-.
   - requisitar_numeracao saca do lote ativo quando existe (AC1).
   - Lote esgotado → cai no caminho sob-demanda, nada quebra (AC2).
   - Lote vencido (`valida_ate` no passado) → cai no sob-demanda (AC4).
   - Novo lote não invalida o anterior ainda ativo — usa o mais recente.
   - Sem `conn`, adquirir_lote falha explícito (nunca fallback silencioso).

2. Endpoint (TestClient + outer_conn, isolamento por SAVEPOINT):
   - POST /receituarios/lotes → 201, corpo com faixa/lote_id.
   - Tipo desconhecido → 422.
   - Fluxo completo: adquirir lote → /numerar usa o lote (numeração carrega
     o lote_id).

3. Concorrência real (AC3, PG real — SAVEPOINT não serve para isto, mesma
   razão do `test_concorrencia.py`): N threads, N conexões REAIS
   (commits reais, fora do isolamento por SAVEPOINT), sacando do MESMO
   lote pequeno — prova que nenhum número sai duplicado e o lote não é
   sacado além da faixa concedida.
"""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# 1. Adapter — unidade contra conn real (outer_conn / SavepointConnection)
# ---------------------------------------------------------------------------

def _stub(conn):
    from app.adapters.sncr_stub import SNCRStub
    return SNCRStub(conn=conn)


def _sp_conn(outer_conn):
    """Uma SavepointConnection avulsa, fora do TestClient — para exercitar
    o adapter diretamente sem precisar do endpoint /numerar inteiro."""
    from tests.integration.conftest import SavepointConnection
    return SavepointConnection(outer_conn)


def test_adquirir_lote_cria_faixa_sequencial(outer_conn):
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)

    res = stub.adquirir_lote("notificacao_receita_b", "11122233344", 5)
    assert res.sucesso is True
    lote = res.dados
    assert lote.inicio == 1
    assert lote.fim == 5
    assert lote.proximo == 1
    assert lote.lote_id.startswith("STUB-LOTE-")
    assert lote.tipo_receituario == "notificacao_receita_b"
    assert lote.prescritor_cpf == "11122233344"
    conn.commit()


def test_adquirir_lote_tipo_desconhecido_erro(outer_conn):
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)
    res = stub.adquirir_lote("tipo_inexistente", "11122233344", 5)
    assert res.sucesso is False
    assert res.codigo_erro == "SNCR_INVALIDO"


def test_adquirir_lote_quantidade_invalida_erro(outer_conn):
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)
    res = stub.adquirir_lote("notificacao_receita_a", "11122233344", 0)
    assert res.sucesso is False
    assert res.codigo_erro == "SNCR_INVALIDO"


def test_adquirir_lote_sem_conn_falha_explicita():
    """Sem `conn`, lotes ficam indisponíveis — falha explícita, nunca um
    fallback silencioso para uma persistência que não existe."""
    from app.adapters.sncr_stub import SNCRStub
    stub = SNCRStub()  # conn=None, comportamento original intocado
    res = stub.adquirir_lote("notificacao_receita_a", "11122233344", 5)
    assert res.sucesso is False
    assert res.codigo_erro == "SNCR_INVALIDO"


def test_requisitar_numeracao_saca_do_lote_ativo_ac1(outer_conn):
    """AC1 do §2: prescritor com lote ativo emite controlado → número sai
    do lote, sequencial, STUB- prefixado."""
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)

    lote = stub.adquirir_lote("notificacao_receita_a", "22233344455", 3).dados

    r1 = stub.requisitar_numeracao("notificacao_receita_a", "22233344455", 1)
    r2 = stub.requisitar_numeracao("notificacao_receita_a", "22233344455", 1)

    assert r1[0].sucesso is True and r2[0].sucesso is True
    n1, n2 = r1[0].dados, r2[0].dados
    assert n1.numero.startswith("STUB-")
    assert n1.lote_id == lote.lote_id
    assert n2.lote_id == lote.lote_id
    assert n1.numero != n2.numero  # sequencial, não repete
    conn.commit()


def test_lote_esgotado_cai_no_sob_demanda_ac2(outer_conn):
    """AC2 do §2: lote esgotado → emissão sem lote segue o caminho atual,
    nada quebra no meio."""
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)

    stub.adquirir_lote("notificacao_receita_b", "33344455566", 1)
    r1 = stub.requisitar_numeracao("notificacao_receita_b", "33344455566", 1)
    assert r1[0].sucesso is True
    assert r1[0].dados.lote_id is not None  # veio do lote

    # Lote esgotado (proximo > fim) — próxima chamada cai no sob-demanda.
    r2 = stub.requisitar_numeracao("notificacao_receita_b", "33344455566", 1)
    assert r2[0].sucesso is True, "esgotamento do lote não pode quebrar a emissão"
    assert r2[0].dados.lote_id is None  # sob-demanda, não do lote
    assert r2[0].dados.numero.startswith("STUB-")


def test_lote_vencido_cai_no_sob_demanda_ac4(outer_conn):
    """AC4 do §2: valida_ate vencido → lote não saca mais."""
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)

    ontem = datetime.utcnow() - timedelta(days=1)
    stub.adquirir_lote("notificacao_receita_a", "44455566677", 5, valida_ate=ontem)

    r = stub.requisitar_numeracao("notificacao_receita_a", "44455566677", 1)
    assert r[0].sucesso is True, "lote vencido não pode bloquear a emissão"
    assert r[0].dados.lote_id is None  # ignorou o lote vencido, foi ao sob-demanda


def test_adquirir_novo_lote_nao_invalida_lote_ativo_anterior(outer_conn):
    """Repor é gesto explícito — o lote anterior, se ainda ativo, segue
    existindo; o saque usa o MAIS RECENTE dos ativos."""
    conn = _sp_conn(outer_conn)
    stub = _stub(conn)

    lote_antigo = stub.adquirir_lote("notificacao_receita_a", "55566677788", 5).dados
    lote_novo = stub.adquirir_lote("notificacao_receita_a", "55566677788", 5).dados
    assert lote_antigo.lote_id != lote_novo.lote_id

    r = stub.requisitar_numeracao("notificacao_receita_a", "55566677788", 1)
    assert r[0].dados.lote_id == lote_novo.lote_id


# ---------------------------------------------------------------------------
# 2. Endpoint — TestClient + outer_conn
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_adquirir_lote_sucesso(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_a", "quantidade": 10},
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["lote_id"].startswith("STUB-LOTE-")
    assert body["inicio"] == 1
    assert body["fim"] == 10
    assert body["adapter"] == "stub"


def test_endpoint_adquirir_lote_tipo_invalido_422(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "tipo_que_nao_existe", "quantidade": 1},
        headers=_headers(token),
    )
    assert r.status_code == 422, r.text


def test_endpoint_adquirir_lote_sem_token_401(client, outer_conn):
    r = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_a", "quantidade": 1},
    )
    assert r.status_code in (401, 403)


def test_endpoint_numerar_usa_lote_adquirido_antes(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Fluxo completo: adquire lote via endpoint, gera+numera um
    receituário controlado — a numeração deve carregar o lote_id."""
    token = obter_token_prescritor(client, seed_usuario)

    r_lote = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_a", "quantidade": 5},
        headers=_headers(token),
    )
    assert r_lote.status_code == 201, r_lote.text
    lote_id = r_lote.json()["lote_id"]

    now = datetime.utcnow()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cns) DO NOTHING
            """,
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        cur.execute(
            """
            INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cpf) DO NOTHING
            """,
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, (SELECT id FROM prescritores WHERE cns = %s),
                    (SELECT id FROM pacientes WHERE cpf = %s),
                    'pendente', 'icp_brasil_local', 'nova', %s, %s, %s)
            RETURNING id
            """,
            ("TEST-LOTE-NUMERAR-001", SEED_PRESCRITOR_CNS, SEED_PACIENTE_CPF, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               posologia, status_item, classe_controle, created_at, updated_at)
            VALUES (%s, 'MEDICAMENTO A1', '500mg', 10, '1 cp/dia', 'pendente', 'A1', %s, %s)
            """,
            (prescricao_id, now, now),
        )
        cur.execute(
            """
            INSERT INTO prescricao_assinatura
              (prescricao_id, tipo_certificado, status_validacao, created_at, updated_at)
            VALUES (%s, 'A1', 'assinatura_pendente', %s, %s)
            """,
            (prescricao_id, now.isoformat(), now.isoformat()),
        )

    r_gerar = client.post(
        "/prescricoes/TEST-LOTE-NUMERAR-001/receituarios/gerar",
        headers=_headers(token),
    )
    assert r_gerar.status_code == 201, r_gerar.text

    r_numerar = client.post(
        "/prescricoes/TEST-LOTE-NUMERAR-001/receituarios/numerar",
        headers=_headers(token),
    )
    assert r_numerar.status_code == 200, r_numerar.text
    rec = r_numerar.json()["receituarios"][0]
    assert rec["status"] == "numerado_stub"
    assert rec["numeracao_sncr"].startswith(lote_id), (
        f"numeração deveria sair do lote adquirido ({lote_id}), "
        f"veio {rec['numeracao_sncr']!r}"
    )


def test_endpoint_listar_lotes_vazio_quando_nenhum(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.get("/receituarios/lotes", headers=_headers(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"lotes": []}


def test_endpoint_listar_lotes_status_derivado(client, outer_conn, seed_usuario):
    """DESENHO §3 (G3) — status ('ativo'/'esgotado'/'vencido') é derivado
    na leitura, nunca armazenado."""
    token = obter_token_prescritor(client, seed_usuario)

    # Lote ativo, intacto.
    r1 = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_a", "quantidade": 5},
        headers=_headers(token),
    )
    assert r1.status_code == 201, r1.text

    # Lote que já nasce vencido.
    ontem = (datetime.utcnow() - timedelta(days=1)).isoformat()
    r2 = client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_b", "quantidade": 5,
              "valida_ate": ontem},
        headers=_headers(token),
    )
    assert r2.status_code == 201, r2.text

    r_lista = client.get("/receituarios/lotes", headers=_headers(token))
    assert r_lista.status_code == 200, r_lista.text
    por_tipo = {l["tipo_receituario"]: l for l in r_lista.json()["lotes"]}

    ativo = por_tipo["notificacao_receita_a"]
    assert ativo["status"] == "ativo"
    assert ativo["consumido"] == 0
    assert ativo["restante"] == 5

    vencido = por_tipo["notificacao_receita_b"]
    assert vencido["status"] == "vencido"


def test_endpoint_listar_lotes_nao_vaza_lote_de_outro_prescritor(
    client, outer_conn, seed_usuario
):
    token = obter_token_prescritor(client, seed_usuario)
    client.post(
        "/receituarios/lotes",
        json={"tipo_receituario": "notificacao_receita_a", "quantidade": 5},
        headers=_headers(token),
    )

    now = datetime.utcnow()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
            VALUES ('prescritor', '111199998888777', 'OUTRO PRESCRITOR G3', %s, true, %s, %s)
            ON CONFLICT (identificador) DO NOTHING
            """,
            ("hash-nao-usado", now, now),
        )
    from tests.integration.conftest import SavepointConnection
    outro_conn = SavepointConnection(outer_conn)
    from app.adapters.sncr_stub import SNCRStub
    SNCRStub(conn=outro_conn).adquirir_lote("notificacao_receita_b", "111199998888777", 3)
    outro_conn.commit()

    r = client.get("/receituarios/lotes", headers=_headers(token))
    tipos = {l["tipo_receituario"] for l in r.json()["lotes"]}
    assert tipos == {"notificacao_receita_a"}


# ---------------------------------------------------------------------------
# 3. Concorrência real (AC3) — PG real, sem SAVEPOINT, commits de verdade
# ---------------------------------------------------------------------------
#
# Mesma razão do test_concorrencia.py: a conexão SAVEPOINT-isolada não é
# thread-safe e não prova nada sobre o lock real do banco. Aqui cada thread
# abre sua PRÓPRIA conexão real (get_conn() do app, apontando pro mesmo
# DATABASE_URL do processo de teste) e faz commit de verdade — o cenário
# em que duas requisições concorrentes de fato disputam a MESMA linha.

def test_concorrencia_nao_saca_numero_duplicado_do_lote_ac3():
    from app.adapters.sncr_stub import SNCRStub
    from app.database import get_conn

    conn_setup = get_conn()
    prescritor_cpf = "99988877766"
    tipo = "receita_controle_especial"
    tamanho_lote = 20
    try:
        stub_setup = SNCRStub(conn=conn_setup)
        lote = stub_setup.adquirir_lote(tipo, prescritor_cpf, tamanho_lote).dados
        conn_setup.commit()
    finally:
        conn_setup.close()

    def _sacar_um():
        conn = get_conn()
        try:
            stub = SNCRStub(conn=conn)
            res = stub.requisitar_numeracao(tipo, prescritor_cpf, 1)
            conn.commit()
            return res[0]
        finally:
            conn.close()

    # tamanho_lote threads disputando um lote de tamanho_lote — todas devem
    # conseguir sacar (nenhuma sobra), e nenhum número pode repetir.
    with concurrent.futures.ThreadPoolExecutor(max_workers=tamanho_lote) as pool:
        futs = [pool.submit(_sacar_um) for _ in range(tamanho_lote)]
        resultados = [f.result() for f in concurrent.futures.as_completed(futs)]

    assert all(r.sucesso for r in resultados), [r.erro for r in resultados if not r.sucesso]
    numeros = [r.dados.numero for r in resultados]
    assert len(numeros) == len(set(numeros)), (
        f"AC3 violado — número duplicado sacado do lote sob concorrência: {numeros}"
    )
    assert all(n.startswith(lote.lote_id) for n in numeros)

    # Uma disputa a MAIS que o tamanho do lote deve cair no sob-demanda,
    # nunca sacar um 21º número da faixa [1..20] nem quebrar (AC2).
    extra = _sacar_um()
    assert extra.sucesso is True
    assert extra.dados.lote_id is None, "saque além da faixa deveria ter caído no sob-demanda"

    # Limpeza — dado real, commitado (fora do SAVEPOINT), por CPF sentinela.
    conn_cleanup = get_conn()
    try:
        conn_cleanup.execute(
            "DELETE FROM sncr_lotes WHERE prescritor_identificador = ?",
            (prescritor_cpf,),
        )
        conn_cleanup.commit()
    finally:
        conn_cleanup.close()
