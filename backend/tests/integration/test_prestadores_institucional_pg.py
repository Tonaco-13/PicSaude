"""TICKET-5C-BIS-C.1 — gate PG do schema institucional (prestadores.org_id + unidades).

Antes da migration, na PG: `prestadores` era o baseline sem org_id e `unidades`
não existia → CRUD de prestadores/unidades quebrava. Esta suíte prova que, após
`alembic upgrade head` (conftest), o subsistema funciona no PostgreSQL.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token


def _admin():
    return {"Authorization": f"Bearer {criar_access_token(sub='admin', role='admin', nome='ADMIN')}"}


def test_schema_migrado_org_id_e_unidades(outer_conn):
    """O schema Ticket-30 está na PG: prestadores.org_id e tabela unidades."""
    with outer_conn.cursor() as cur:
        # não levanta UndefinedColumn (org_id existe)
        cur.execute("SELECT org_id, ativo FROM prestadores WHERE 1=0")
        # unidades existe com a FK/colunas esperadas
        cur.execute("SELECT prestador_id, unidade_id, ativo FROM unidades WHERE 1=0")
    # ativo é Boolean: comparação com TRUE funciona sem cast
    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM prestadores WHERE ativo = true")
        assert cur.fetchone()[0] >= 0


def test_crud_prestador_e_unidade_funcionam_na_pg(client):
    h = _admin()
    # criar prestador (antes quebrava: org_id ausente)
    r = client.post("/prestadores", json={
        "org_id": "org-aaa", "nome": "Lab A", "tipo": "laboratorio",
        "cnpj": "12345678000195",
    }, headers=h)
    assert r.status_code == 201, r.text

    # obter por org_id
    assert client.get("/prestadores/org-aaa", headers=h).status_code == 200

    # criar unidade (antes quebrava: tabela unidades ausente)
    ru = client.post("/prestadores/org-aaa/unidades", json={
        "unidade_id": "u1", "nome": "Unidade 1", "tipo": "laboratorio",
    }, headers=h)
    assert ru.status_code == 201, ru.text

    # listar unidades
    assert client.get("/prestadores/org-aaa/unidades", headers=h).status_code == 200


def test_org_id_unico(client):
    h = _admin()
    assert client.post("/prestadores", json={
        "org_id": "org-dup", "nome": "X", "tipo": "clinica",
    }, headers=h).status_code == 201
    # mesmo org_id de novo → conflito (UNIQUE org_id)
    r = client.post("/prestadores", json={
        "org_id": "org-dup", "nome": "Y", "tipo": "clinica",
    }, headers=h)
    assert r.status_code in (409, 422), r.text


def test_smoke_login_prestador_e_api_keys(client):
    """Smoke (CODEX rodada 2): os caminhos que consultavam `prestadores.org_id` e
    quebravam na PG funcionam após a migration.

    Nota: o caminho 200 do login-prestador (com prestador cadastrado) cruza com
    `estabelecimentos_cnes`, outra tabela ausente na PG (FORA do escopo do C.1 —
    ver follow-up no ticket). Por isso o smoke usa o caminho 404 (CNPJ não
    cadastrado), que exercita a query de `prestadores.org_id` e levanta 404 ANTES
    do cruzamento CNES — provando que a coluna org_id existe e a query roda."""
    h = _admin()
    assert client.post("/prestadores", json={
        "org_id": "org-sm", "nome": "Lab SM", "tipo": "laboratorio",
        "cnpj": "99999999000191",
    }, headers=h).status_code == 201

    # login-prestador com CNPJ NÃO cadastrado → 404 (query org_id rodou, sem CNES)
    disp = {"Authorization": f"Bearer {criar_access_token(sub='00000000000000', role='dispensador', nome='X')}"}
    assert client.get("/auth/me/institucional", headers=disp).status_code == 404

    # api_keys: criar para org existente → 201 (verifica org_id em prestadores)
    rk = client.post("/admin/api-keys", json={"org_id": "org-sm", "nome": "Integrador X"}, headers=h)
    assert rk.status_code == 201, rk.text


def test_login_prestador_200_path_cnes_ausente_fail_open(client):
    """Fechamento do gap C.1 §7: o caminho 200 do /auth/me/institucional (prestador
    CADASTRADO) NÃO quebra na PG quando `estabelecimentos_cnes` está ausente — degrada
    com `cnes_verificado=False`. Antes do fix retornava 500 (UndefinedTable na PG,
    pois o except só capturava sqlite3.OperationalError)."""
    h = _admin()
    cnpj = "99888777000166"
    assert client.post("/prestadores", json={
        "org_id": "org-cnes", "nome": "Farmacia CNES", "tipo": "farmacia", "cnpj": cnpj,
    }, headers=h).status_code == 201
    disp = {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='X')}"}
    r = client.get("/auth/me/institucional", headers=disp)
    assert r.status_code == 200, r.text          # antes: 500
    body = r.json()
    assert body["org_id"] == "org-cnes"
    assert body["cnes_verificado"] is False       # tabela CNES ausente → fail open


def test_cnes_verificado_true_com_linha_cnes(client, outer_conn):
    """
    T0.5b — com a linha CNES presente (CNPJ + TP_UNIDADE de farmácia ∈ _TP_FARMACIA),
    /auth/me/institucional devolve cnes_verificado=true. É o que a Farmácia Demo passa
    a ter (deixa de cair no modal de confirmação manual de CNES).

    Check do Jules (no-orphan): `estabelecimentos_cnes` é dado de REFERÊNCIA (sem FK)
    e `cnes_verificado` é flag COMPUTADO read-only (não persistido) — semear a linha
    não cria estado órfão em tabela adjacente.
    """
    h = _admin()
    cnpj = "99999999000191"
    assert client.post("/prestadores", json={
        "org_id": "org-demo-farm", "nome": "Farmácia Demo", "tipo": "farmacia", "cnpj": cnpj,
    }, headers=h).status_code == 201

    with outer_conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS estabelecimentos_cnes "
            "(CO_CNES TEXT, NU_CNPJ TEXT, TP_UNIDADE TEXT, NO_FANTASIA TEXT, CO_MUNICIPIO TEXT)"
        )
        cur.execute(
            "INSERT INTO estabelecimentos_cnes (CO_CNES, NU_CNPJ, TP_UNIDADE, NO_FANTASIA, CO_MUNICIPIO) "
            "VALUES ('9900001', %s, '04', 'Farmácia Demo', '261160')",
            (cnpj,),
        )

    disp = {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='X')}"}
    r = client.get("/auth/me/institucional", headers=disp)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["org_id"] == "org-demo-farm"
    assert body["cnes_verificado"] is True        # ← T0.5b: farmácia demo verificada

    # No-orphan: apenas a linha de referência CNES; nada persistido em tabela adjacente.
    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM estabelecimentos_cnes WHERE NU_CNPJ = %s", (cnpj,))
        assert cur.fetchone()[0] == 1
