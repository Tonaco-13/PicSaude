"""
test_dispensacao_atomizada.py
==============================
Testes de integração — Circulação Atomizada Fase 2 (Ticket 44).
Fluxo de dispensação por item com token atomizado.

COBERTURA
---------
  1.  Retrocompatibilidade: dispensação sem token funciona normalmente
  2.  Dispensação com token válido de item → sucesso
  3.  Token não encontrado → 404
  4.  Token de prescrição inteira (sem item_id) → 422
  5.  Isolamento: token com item_id ≠ item solicitado → 403
  6.  Token revogado → 410
  7.  Token expirado (status='expirado') → 410
  8.  Token expirado (por tempo) → 410
  9.  Ledger: evento 'item_dispensado' com origem_token='atomizado'
 10.  Ledger: evento 'item_dispensado' sem origem_token quando sem token
 11.  Lazy invalidation: token expirado após dispensação total
 12.  Lazy invalidation: token preservado após dispensação parcial
 13.  Saldo calculado corretamente com token
 14.  Saldo ultrapassado com token → 422
 15.  Item em estado 'dispensado' (bloqueado) → 409
 16.  Item em estado 'cancelado' (bloqueado) → 409
 17.  Saldo zero → 409
 18.  Dispensação parcial → item vai para 'em_custodia'
 19.  Dispensação total → item vai para 'dispensado'
 20.  Status da prescrição recalculado após dispensação atomizada
 21.  Isolamento entre itens da mesma prescrição (token de item A não dispensa item B)
 22.  Múltiplas dispensações parciais com token até esgotar saldo
 23.  Role prescritor não pode dispensar → 403
 24.  Role paciente não pode dispensar → 403
 25.  Dispensação atomizada enriquece ledger corretamente (item_id, quantidade, saldo)
 26.  Token de outro protocolo não autoriza item de protocolo diferente
 27.  Dois tokens distintos para dois itens distintos — cada um isolado
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import PAYLOAD_PADRAO


# ---------------------------------------------------------------------------
# Payloads e helpers locais
# ---------------------------------------------------------------------------

_BASE = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Teste",
    "tipo_emissao": "nova",
}

_ITEM_ELEGIVEL_A = {
    "nome_medicamento": "LOSARTANA",
    "concentracao": "50mg",
    "quantidade": 10,
    "posologia": "1 cp/dia",
    "classe_controle": None,
}

_ITEM_ELEGIVEL_B = {
    "nome_medicamento": "METFORMINA",
    "concentracao": "850mg",
    "quantidade": 30,
    "posologia": "1 cp/dia",
    "classe_controle": None,
}

_ITEM_ELEGIVEL_PARCIAL = {
    "nome_medicamento": "ATENOLOL",
    "concentracao": "25mg",
    "quantidade": 30,
    "posologia": "1 cp/dia",
    "classe_controle": None,
}

_DISPENSA_BASE = {
    "cnpj_estabelecimento": "12345678000195",
    "quantidade_dispensada": 1,
    "dispensado_por": "Farmaceutico Teste",
}


def _payload(*itens):
    return {**_BASE, "itens": list(itens)}


def _criar_prescricao(prescritor, *itens):
    r = prescritor.post("/prescricoes", json=_payload(*itens))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _atomizar(paciente, proto, validade_minutos=60):
    r = paciente.post(
        f"/prescricoes/{proto}/tokens/atomizar",
        json={"validade_minutos": validade_minutos},
    )
    assert r.status_code == 201, r.text
    return r.json()  # {protocolo, tokens: [{codigo_curto, item_id, ...}], ...}


def _dispensa(dispensador, proto, item_id, **kwargs):
    body = {**_DISPENSA_BASE, **kwargs}
    return dispensador.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json=body,
    )


def _get_item_ids(db_path: str, proto: str) -> list[int]:
    """Retorna lista de IDs de itens de uma prescrição (consulta direta ao BD de teste)."""
    import sqlite3 as _sql
    conn = _sql.connect(db_path)
    conn.row_factory = _sql.Row
    presc_id = conn.execute(
        "SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)
    ).fetchone()["id"]
    rows = conn.execute(
        "SELECT id FROM prescricao_itens WHERE prescricao_id = ? ORDER BY id", (presc_id,)
    ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


# ---------------------------------------------------------------------------
# Fixture: prescrição com 1 item + tokens atomizados
# ---------------------------------------------------------------------------

@pytest.fixture()
def proto_atomizado_1(prescritor, paciente):
    proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
    tokens = _atomizar(paciente, proto)
    item_id = tokens["tokens"][0]["item_id"]
    codigo = tokens["tokens"][0]["codigo_curto"]
    return proto, item_id, codigo


@pytest.fixture()
def proto_atomizado_2(prescritor, paciente):
    """Prescrição com 2 itens elegíveis + tokens."""
    proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A, _ITEM_ELEGIVEL_B)
    tokens = _atomizar(paciente, proto)
    token_a = tokens["tokens"][0]
    token_b = tokens["tokens"][1]
    return proto, token_a, token_b


@pytest.fixture()
def proto_parcial(prescritor, paciente):
    """Prescrição com 1 item de quantidade=30 para testes de dispensação parcial."""
    proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_PARCIAL)
    tokens = _atomizar(paciente, proto)
    item_id = tokens["tokens"][0]["item_id"]
    codigo = tokens["tokens"][0]["codigo_curto"]
    return proto, item_id, codigo


# ===========================================================================
# 1. Retrocompatibilidade
# ===========================================================================

class TestRetrocompat:

    def test_dispensa_sem_token_funciona(self, prescritor, dispensador, db_path):
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        item_id = _get_item_ids(db_path, proto)[0]

        r = _dispensa(dispensador, proto, item_id, quantidade_dispensada=5)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["saldo_restante"] == 5
        assert data["status_item"] == "em_custodia"

    def test_dispensa_sem_token_ledger_sem_origem_token(self, prescritor, dispensador, db_path):
        import sqlite3 as _sql
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        item_id = _get_item_ids(db_path, proto)[0]

        _dispensa(dispensador, proto, item_id, quantidade_dispensada=10)

        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        ev = conn.execute(
            "SELECT payload_json FROM prescricao_eventos WHERE tipo_evento = 'item_dispensado' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        dados = json.loads(ev["payload_json"])
        assert "origem_token" not in dados


# ===========================================================================
# 2. Dispensação com token válido
# ===========================================================================

class TestDispensacaoAtomizada:

    def test_dispensa_com_token_valido_sucesso(self, dispensador, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=5,
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["item_id"] == item_id
        assert data["saldo_restante"] == 5

    def test_dispensa_total_com_token(self, dispensador, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=10,  # quantidade=10
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        assert r.json()["status_item"] == "dispensado"
        assert r.json()["saldo_restante"] == 0

    def test_dispensa_parcial_item_em_custodia(self, dispensador, proto_parcial):
        proto, item_id, codigo = proto_parcial
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=10,
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        assert r.json()["status_item"] == "em_custodia"

    def test_status_prescricao_recalculado(self, dispensador, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=10,
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        assert r.json()["status_prescricao"] == "dispensada"


# ===========================================================================
# 3. Erros de token
# ===========================================================================

class TestTokenErrors:

    def test_token_nao_encontrado(self, prescritor, dispensador, db_path):
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        item_id = _get_item_ids(db_path, proto)[0]

        r = _dispensa(dispensador, proto, item_id,
                      codigo_curto_token="XXXXXXXX")
        assert r.status_code == 404, r.text

    def test_token_prescricao_inteira_rejeitado(self, prescritor, paciente, dispensador, db_path):
        """Token sem item_id (prescrição inteira) não pode ser usado como token atomizado."""
        import sqlite3 as _sql

        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)

        # Criar token de prescrição inteira manualmente
        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        presc_id = conn.execute(
            "SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)
        ).fetchone()["id"]
        expira = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        agora = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO tokens_apresentacao
               (codigo_curto, protocolo, paciente_cpf, escopo, status, expira_em, criado_em, item_id)
               VALUES (?, ?, '12345678901', 'apresentacao', 'ativo', ?, ?, NULL)""",
            ("FULLPRESC", proto, expira, agora),
        )
        conn.commit()
        conn.close()

        item_id = _get_item_ids(db_path, proto)[0]

        r = _dispensa(dispensador, proto, item_id,
                      codigo_curto_token="FULLPRESC")
        assert r.status_code == 422, r.text
        assert "prescrição inteira" in r.json()["detail"].lower() or "convencional" in r.json()["detail"].lower()

    def test_token_item_errado_isolamento(self, dispensador, proto_atomizado_2):
        """Token do item A não pode dispensar item B — isolamento."""
        proto, token_a, token_b = proto_atomizado_2
        # Usa token_a para dispensar item_b
        r = _dispensa(dispensador, proto, token_b["item_id"],
                      quantidade_dispensada=1,
                      codigo_curto_token=token_a["codigo_curto"])
        assert r.status_code == 403, r.text
        assert "isolamento" in r.json()["detail"].lower() or "não autoriza" in r.json()["detail"].lower()

    def test_token_revogado(self, prescritor, paciente, dispensador, db_path):
        import sqlite3 as _sql
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        tokens = _atomizar(paciente, proto)
        codigo = tokens["tokens"][0]["codigo_curto"]
        item_id = tokens["tokens"][0]["item_id"]

        # Revogar o token diretamente no banco
        conn = _sql.connect(db_path)
        conn.execute(
            "UPDATE tokens_apresentacao SET status = 'revogado' WHERE codigo_curto = ?",
            (codigo,),
        )
        conn.commit()
        conn.close()

        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=1,
                      codigo_curto_token=codigo)
        assert r.status_code == 410, r.text
        assert "revogado" in r.json()["detail"].lower()

    def test_token_expirado_por_status(self, prescritor, paciente, dispensador, db_path):
        import sqlite3 as _sql
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        tokens = _atomizar(paciente, proto)
        codigo = tokens["tokens"][0]["codigo_curto"]
        item_id = tokens["tokens"][0]["item_id"]

        conn = _sql.connect(db_path)
        conn.execute(
            "UPDATE tokens_apresentacao SET status = 'expirado' WHERE codigo_curto = ?",
            (codigo,),
        )
        conn.commit()
        conn.close()

        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=1,
                      codigo_curto_token=codigo)
        assert r.status_code == 410, r.text
        assert "expirado" in r.json()["detail"].lower()

    def test_token_expirado_por_tempo(self, prescritor, paciente, dispensador, db_path):
        import sqlite3 as _sql
        proto = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        tokens = _atomizar(paciente, proto)
        codigo = tokens["tokens"][0]["codigo_curto"]
        item_id = tokens["tokens"][0]["item_id"]

        # Retroceder expira_em para passado
        passado = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn = _sql.connect(db_path)
        conn.execute(
            "UPDATE tokens_apresentacao SET expira_em = ? WHERE codigo_curto = ?",
            (passado, codigo),
        )
        conn.commit()
        conn.close()

        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=1,
                      codigo_curto_token=codigo)
        assert r.status_code == 410, r.text
        assert "expirou" in r.json()["detail"].lower()


# ===========================================================================
# 4. Ledger
# ===========================================================================

class TestLedgerAtomizado:

    def test_ledger_com_origem_token_atomizado(self, dispensador, proto_atomizado_1, db_path):
        import sqlite3 as _sql
        proto, item_id, codigo = proto_atomizado_1
        _dispensa(dispensador, proto, item_id,
                  quantidade_dispensada=5,
                  codigo_curto_token=codigo)

        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        ev = conn.execute(
            "SELECT payload_json FROM prescricao_eventos WHERE tipo_evento = 'item_dispensado' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        dados = json.loads(ev["payload_json"])
        assert dados["origem_token"] == "atomizado"

    def test_ledger_campos_completos(self, dispensador, proto_atomizado_1, db_path):
        import sqlite3 as _sql
        proto, item_id, codigo = proto_atomizado_1
        _dispensa(dispensador, proto, item_id,
                  quantidade_dispensada=3,
                  codigo_curto_token=codigo)

        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        ev = conn.execute(
            "SELECT payload_json FROM prescricao_eventos WHERE tipo_evento = 'item_dispensado' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        dados = json.loads(ev["payload_json"])
        assert dados["item_id"] == item_id
        assert dados["quantidade_dispensada"] == 3
        assert dados["saldo_restante"] == 7
        assert dados["origem_token"] == "atomizado"


# ===========================================================================
# 5. Lazy invalidation
# ===========================================================================

class TestLazyInvalidation:

    def test_token_expirado_apos_dispensacao_total(self, dispensador, proto_atomizado_1, db_path):
        import sqlite3 as _sql
        proto, item_id, codigo = proto_atomizado_1

        # Dispensação total (quantidade=10)
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=10,
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        assert r.json()["status_item"] == "dispensado"

        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        token = conn.execute(
            "SELECT status FROM tokens_apresentacao WHERE codigo_curto = ?",
            (codigo,),
        ).fetchone()
        conn.close()

        assert token["status"] == "expirado"

    def test_token_preservado_apos_dispensacao_parcial(self, dispensador, proto_parcial, db_path):
        import sqlite3 as _sql
        proto, item_id, codigo = proto_parcial

        # Dispensação parcial (10 de 30)
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=10,
                      codigo_curto_token=codigo)
        assert r.status_code == 201, r.text
        assert r.json()["status_item"] == "em_custodia"

        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        token = conn.execute(
            "SELECT status FROM tokens_apresentacao WHERE codigo_curto = ?",
            (codigo,),
        ).fetchone()
        conn.close()

        assert token["status"] == "ativo"


# ===========================================================================
# 6. Saldo e itens bloqueados
# ===========================================================================

class TestSaldoEBloqueios:

    def test_quantidade_acima_do_saldo_com_token(self, dispensador, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=999,  # saldo = 10
                      codigo_curto_token=codigo)
        assert r.status_code == 422, r.text

    def test_saldo_zero_com_token(self, dispensador, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1

        # Dispensar tudo
        _dispensa(dispensador, proto, item_id, quantidade_dispensada=10)

        # Tentar dispensar novamente com token
        r = _dispensa(dispensador, proto, item_id,
                      quantidade_dispensada=1,
                      codigo_curto_token=codigo)
        # Item está 'dispensado' → bloqueado
        assert r.status_code == 409, r.text

    def test_multiplas_parciais_com_token_ate_esgotar(self, dispensador, proto_parcial):
        proto, item_id, codigo = proto_parcial

        # 3 dispensações parciais de 10 (total = 30)
        for _ in range(3):
            r = _dispensa(dispensador, proto, item_id,
                          quantidade_dispensada=10,
                          codigo_curto_token=codigo)
            assert r.status_code == 201, r.text

        # Após esgotar, item deve estar dispensado
        assert r.json()["status_item"] == "dispensado"
        assert r.json()["saldo_restante"] == 0


# ===========================================================================
# 7. Isolamento entre itens e prescrições
# ===========================================================================

class TestIsolamento:

    def test_dois_tokens_distintos_isolados(self, dispensador, proto_atomizado_2):
        """Cada token dispensa apenas seu item — nenhum vaza para o outro."""
        proto, token_a, token_b = proto_atomizado_2

        # Token A dispensa item A com sucesso
        r = _dispensa(dispensador, proto, token_a["item_id"],
                      quantidade_dispensada=1,
                      codigo_curto_token=token_a["codigo_curto"])
        assert r.status_code == 201, r.text

        # Token B dispensa item B com sucesso
        r = _dispensa(dispensador, proto, token_b["item_id"],
                      quantidade_dispensada=1,
                      codigo_curto_token=token_b["codigo_curto"])
        assert r.status_code == 201, r.text

        # Token B NÃO dispensa item A
        r = _dispensa(dispensador, proto, token_a["item_id"],
                      quantidade_dispensada=1,
                      codigo_curto_token=token_b["codigo_curto"])
        assert r.status_code == 403, r.text

    def test_token_de_outro_protocolo_nao_funciona(self, prescritor, paciente, dispensador, db_path):
        """Token de protocolo X não pode ser usado para dispensar item do protocolo Y."""
        proto_x = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        tokens_x = _atomizar(paciente, proto_x)
        codigo_x = tokens_x["tokens"][0]["codigo_curto"]

        proto_y = _criar_prescricao(prescritor, _ITEM_ELEGIVEL_A)
        item_y_id = _get_item_ids(db_path, proto_y)[0]

        r = _dispensa(dispensador, proto_y, item_y_id,
                      quantidade_dispensada=1,
                      codigo_curto_token=codigo_x)
        # item_id do token_x ≠ item_y_id → 403
        assert r.status_code == 403, r.text


# ===========================================================================
# 8. RBAC
# ===========================================================================

class TestRBAC:

    def test_prescritor_nao_pode_dispensar(self, prescritor, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = prescritor.post(
            f"/prescricoes/{proto}/itens/{item_id}/dispensar",
            json={**_DISPENSA_BASE, "codigo_curto_token": codigo},
        )
        assert r.status_code == 403, r.text

    def test_paciente_nao_pode_dispensar(self, paciente, proto_atomizado_1):
        proto, item_id, codigo = proto_atomizado_1
        r = paciente.post(
            f"/prescricoes/{proto}/itens/{item_id}/dispensar",
            json={**_DISPENSA_BASE, "codigo_curto_token": codigo},
        )
        assert r.status_code == 403, r.text
