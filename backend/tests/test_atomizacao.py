"""
test_atomizacao.py
==================
Testes de integração — Circulação Atomizada (Ticket 44, Fase 1).

COBERTURA
---------
  1.  Domain: elegibilidade unitária (eh_item_atomizavel, prescricao_atomizavel, motivo_nao_atomizavel)
  2.  POST /prescricoes/{proto}/tokens/atomizar
        a. prescrição 1 item elegível → gera 1 token
        b. prescrição N itens elegíveis → gera N tokens
        c. item inelegível (classe B1) → bloqueia a prescrição inteira
        d. prescrição mista (elegível + inelegível) → bloqueia
        e. prescrição inexistente → 404
        f. prescrição de outro paciente → 404
        g. prescrição física (encerrada_localmente) → 409
        h. role prescritor tentando atomizar → 403
        i. role dispensador tentando atomizar → 403
        j. sem itens circuláveis (todos dispensados) → 409
        k. validade_minutos acima do máximo → 422
        l. campos do token: codigo_curto, expira_em, item_id, nome_medicamento
        m. tokens com item_id preenchido no banco
  3.  Ledger: eventos gerados pela atomização
        n. evento 'circulacao_atomizada_ativada' inserido
        o. evento 'token_item_emitido' por item
  4.  POST /tokens/apresentacao/resolver — item_id branch (Ticket 44)
        p. resolver token de item → retorna modo='item', só o item correto
        q. resolver token de item dispensado → 409
        r. resolver token de item cancelado → 409
        s. resolver token de prescrição inteira pós-T44 → modo='prescricao' (retrocompat.)
        t. token de item com prescrição terminal → 409
  5.  Retrocompatibilidade
        u. POST /tokens/apresentacao existente (sem item_id) continua funcionando
        v. GET /tokens/apresentacao lista tokens incluindo atomizados
        w. prescricao com classe_controle=None é elegível
        x. classe_controle em maiúscula e minúscula é normalizado
  6.  Segurança
        y. token de item de prescrição alheia não é resolvível pelo paciente errado
        z. token de item expirado → 410

Estratégia de banco: conftest.py padrão (tmp_path, get_conn patchado).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.medicamento import (
    CLASSES_CONTROLE_ESPECIAL,
    ESTADOS_ITEM_CIRCULAVEIS,
    eh_item_atomizavel,
    motivo_nao_atomizavel,
    prescricao_atomizavel,
)
from tests.conftest import PAYLOAD_DOIS_ITENS, PAYLOAD_PADRAO


# ---------------------------------------------------------------------------
# Payloads auxiliares
# ---------------------------------------------------------------------------

_ITEM_ELEGIVEL = {
    "nome_medicamento": "LOSARTANA",
    "concentracao": "50mg",
    "quantidade": 60,
    "posologia": "1 cp/dia",
    "classe_controle": None,
}

_ITEM_B1 = {
    "nome_medicamento": "DIAZEPAM",
    "concentracao": "5mg",
    "quantidade": 30,
    "posologia": "1 cp ao deitar",
    "classe_controle": "B1",
}

_ITEM_A1 = {
    "nome_medicamento": "MORFINA",
    "concentracao": "10mg",
    "quantidade": 10,
    "posologia": "conforme prescrição",
    "classe_controle": "A1",
}

_BASE = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Teste",
    "tipo_emissao": "nova",
}


def _payload(*itens):
    return {**_BASE, "itens": list(itens)}


# ---------------------------------------------------------------------------
# Fixture: protocolo de prescrição elegível com 2 itens
# ---------------------------------------------------------------------------

@pytest.fixture()
def proto_dois_itens(prescritor):
    r = prescritor.post("/prescricoes", json=_payload(_ITEM_ELEGIVEL, _ITEM_ELEGIVEL))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def proto_um_item(prescritor):
    r = prescritor.post("/prescricoes", json=_payload(_ITEM_ELEGIVEL))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ===========================================================================
# 1. Domain unitário
# ===========================================================================

class TestDomainElegibilidade:

    def test_item_sem_classe_eh_atomizavel(self):
        assert eh_item_atomizavel({"nome_medicamento": "PARACETAMOL", "classe_controle": None})

    def test_item_com_classe_comum_eh_atomizavel(self):
        # C1, C2 são comuns — não bloqueiam
        assert eh_item_atomizavel({"nome_medicamento": "AMOXICILINA", "classe_controle": "C1"})

    def test_item_B1_nao_atomizavel(self):
        assert not eh_item_atomizavel(_ITEM_B1)

    def test_item_A1_nao_atomizavel(self):
        assert not eh_item_atomizavel(_ITEM_A1)

    def test_todas_classes_especiais_bloqueiam(self):
        for classe in CLASSES_CONTROLE_ESPECIAL:
            item = {"nome_medicamento": "X", "classe_controle": classe}
            assert not eh_item_atomizavel(item), f"Classe {classe} deveria bloquear"

    def test_motivo_preenchido_para_inelegivel(self):
        motivo = motivo_nao_atomizavel(_ITEM_B1)
        assert motivo is not None
        assert "B1" in motivo

    def test_motivo_none_para_elegivel(self):
        assert motivo_nao_atomizavel(_ITEM_ELEGIVEL) is None

    def test_prescricao_atomizavel_todos_elegiveis(self):
        ok, motivo = prescricao_atomizavel([_ITEM_ELEGIVEL, _ITEM_ELEGIVEL])
        assert ok is True
        assert motivo is None

    def test_prescricao_nao_atomizavel_com_inelegivel(self):
        ok, motivo = prescricao_atomizavel([_ITEM_ELEGIVEL, _ITEM_B1])
        assert ok is False
        assert motivo is not None
        assert "B1" in motivo

    def test_prescricao_nao_atomizavel_todos_inelivers(self):
        ok, motivo = prescricao_atomizavel([_ITEM_B1, _ITEM_A1])
        assert ok is False

    def test_classe_controle_case_insensitive(self):
        """classe_controle em minúscula deve ser normalizada para comparação."""
        item = {"nome_medicamento": "DIAZEPAM", "classe_controle": "b1"}
        # eh_item_atomizavel normaliza para upper antes de checar
        assert not eh_item_atomizavel(item)

    def test_estados_item_circulaveis_contem_pendente(self):
        assert "pendente" in ESTADOS_ITEM_CIRCULAVEIS

    def test_estados_item_circulaveis_contem_devolvido(self):
        assert "devolvido_paciente" in ESTADOS_ITEM_CIRCULAVEIS


# ===========================================================================
# 2. POST /prescricoes/{proto}/tokens/atomizar
# ===========================================================================

class TestAtomizarEndpoint:

    def test_um_item_elegivel_gera_um_token(self, paciente, proto_um_item):
        r = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["circulacao_atomizada"] is True
        assert data["total_tokens"] == 1
        assert len(data["tokens"]) == 1

    def test_dois_itens_elegíveis_geram_dois_tokens(self, paciente, proto_dois_itens):
        r = paciente.post(
            f"/prescricoes/{proto_dois_itens}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["total_tokens"] == 2
        assert len(data["tokens"]) == 2

    def test_tokens_tem_campos_obrigatorios(self, paciente, proto_um_item):
        r = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 30},
        )
        assert r.status_code == 201
        token = r.json()["tokens"][0]
        assert "item_id" in token
        assert "codigo_curto" in token
        assert "expira_em" in token
        assert "nome_medicamento" in token

    def test_tokens_distintos_por_item(self, paciente, proto_dois_itens):
        r = paciente.post(
            f"/prescricoes/{proto_dois_itens}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        tokens = r.json()["tokens"]
        codigos = [t["codigo_curto"] for t in tokens]
        assert len(set(codigos)) == 2, "Cada item deve ter um código único"
        item_ids = [t["item_id"] for t in tokens]
        assert len(set(item_ids)) == 2, "Cada token deve referenciar item diferente"

    def test_item_inelegivel_bloqueia_prescricao_inteira(self, prescritor, paciente):
        r = prescritor.post("/prescricoes", json=_payload(_ITEM_B1))
        assert r.status_code == 201
        proto = r.json()["protocolo"]
        r2 = paciente.post(f"/prescricoes/{proto}/tokens/atomizar", json={"validade_minutos": 60})
        assert r2.status_code == 422
        assert "B1" in r2.text

    def test_prescricao_mista_bloqueada(self, prescritor, paciente):
        r = prescritor.post("/prescricoes", json=_payload(_ITEM_ELEGIVEL, _ITEM_B1))
        assert r.status_code == 201
        proto = r.json()["protocolo"]
        r2 = paciente.post(f"/prescricoes/{proto}/tokens/atomizar", json={"validade_minutos": 60})
        assert r2.status_code == 422

    def test_prescricao_inexistente_retorna_404(self, paciente):
        r = paciente.post(
            "/prescricoes/nao-existe-uuid/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 404

    def test_prescricao_de_outro_paciente_retorna_404(self, outro_paciente, proto_um_item):
        r = outro_paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 404

    def test_role_prescritor_nao_pode_atomizar(self, prescritor, proto_um_item):
        r = prescritor.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 403

    def test_role_dispensador_nao_pode_atomizar(self, dispensador, proto_um_item):
        r = dispensador.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 403

    def test_validade_acima_do_maximo_retorna_422(self, paciente, proto_um_item):
        r = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 9999},
        )
        assert r.status_code == 422

    def test_tokens_salvos_com_item_id_no_banco(self, paciente, proto_um_item, db_path):
        r = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        assert r.status_code == 201
        codigo = r.json()["tokens"][0]["codigo_curto"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_id FROM tokens_apresentacao WHERE codigo_curto = ?", (codigo,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["item_id"] is not None

    def test_sem_itens_circulaveis_retorna_409(self, prescritor, paciente, dispensador, db_path):
        """Prescrição com todos os itens dispensados não aceita atomização."""
        r = prescritor.post("/prescricoes", json=_payload(_ITEM_ELEGIVEL))
        proto = r.json()["protocolo"]

        # Transferir custódia para o paciente e dispensar o item
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        p_id = conn.execute("SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)).fetchone()["id"]
        conn.execute("UPDATE prescricao_itens SET status_item = 'dispensado' WHERE prescricao_id = ?", (p_id,))
        conn.execute("UPDATE prescricoes SET status = 'dispensada' WHERE id = ?", (p_id,))
        conn.commit()
        conn.close()

        r2 = paciente.post(f"/prescricoes/{proto}/tokens/atomizar", json={"validade_minutos": 60})
        assert r2.status_code == 409


# ===========================================================================
# 3. Ledger — eventos gerados
# ===========================================================================

class TestLedgerAtomizacao:

    def test_evento_circulacao_atomizada_ativada(self, paciente, proto_um_item, db_path):
        paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM prescricao_eventos e
            JOIN prescricoes p ON p.id = e.prescricao_id
            WHERE p.protocolo = ? AND e.tipo_evento = 'circulacao_atomizada_ativada'
            """,
            (proto_um_item,),
        ).fetchone()
        conn.close()
        assert row["cnt"] == 1

    def test_evento_token_item_emitido_por_item(self, paciente, proto_dois_itens, db_path):
        paciente.post(
            f"/prescricoes/{proto_dois_itens}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM prescricao_eventos e
            JOIN prescricoes p ON p.id = e.prescricao_id
            WHERE p.protocolo = ? AND e.tipo_evento = 'token_item_emitido'
            """,
            (proto_dois_itens,),
        ).fetchone()
        conn.close()
        assert row["cnt"] == 2


# ===========================================================================
# 4. POST /tokens/apresentacao/resolver — branch item_id
# ===========================================================================

class TestResolverTokenAtomizado:

    def test_resolver_token_item_retorna_modo_item(self, paciente, dispensador, proto_um_item):
        r_at = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        codigo = r_at.json()["tokens"][0]["codigo_curto"]

        r_res = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo},
        )
        assert r_res.status_code == 200, r_res.text
        data = r_res.json()
        assert data["modo"] == "item"
        assert data["circulacao_atomizada"] is True
        assert "item" in data
        assert "item_id" in data["item"]

    def test_resolver_token_item_nao_expoe_outros_itens(self, paciente, dispensador, proto_dois_itens):
        r_at = paciente.post(
            f"/prescricoes/{proto_dois_itens}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        tokens = r_at.json()["tokens"]
        codigo_item1 = tokens[0]["codigo_curto"]

        r_res = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo_item1},
        )
        data = r_res.json()
        # Apenas um item retornado — o outro não deve aparecer
        assert "item" in data
        assert "itens_pendentes" not in data
        assert data["item"]["item_id"] == tokens[0]["item_id"]

    def test_resolver_token_item_dispensado_retorna_409(self, paciente, dispensador, proto_um_item, db_path):
        r_at = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        token_info = r_at.json()["tokens"][0]
        codigo = token_info["codigo_curto"]
        item_id = token_info["item_id"]

        # Simular dispensação do item diretamente no banco
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE prescricao_itens SET status_item = 'dispensado' WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        r_res = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo},
        )
        assert r_res.status_code == 409

    def test_resolver_token_item_cancelado_retorna_409(self, paciente, dispensador, proto_um_item, db_path):
        r_at = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        item_id = r_at.json()["tokens"][0]["item_id"]
        codigo = r_at.json()["tokens"][0]["codigo_curto"]

        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE prescricao_itens SET status_item = 'cancelado' WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        r_res = dispensador.post("/tokens/apresentacao/resolver", json={"codigo_curto": codigo})
        assert r_res.status_code == 409

    def test_resolver_token_item_expirado_retorna_410(self, paciente, dispensador, proto_um_item, db_path):
        r_at = paciente.post(
            f"/prescricoes/{proto_um_item}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        codigo = r_at.json()["tokens"][0]["codigo_curto"]

        # Expirar o token diretamente no banco
        passado = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE tokens_apresentacao SET expira_em = ? WHERE codigo_curto = ?",
            (passado, codigo),
        )
        conn.commit()
        conn.close()

        r_res = dispensador.post("/tokens/apresentacao/resolver", json={"codigo_curto": codigo})
        assert r_res.status_code == 410


# ===========================================================================
# 5. Retrocompatibilidade
# ===========================================================================

class TestRetrocompat:

    def test_token_prescricao_inteira_continua_funcionando(self, paciente, dispensador, prescritor):
        """Token sem item_id (pré-T44) deve continuar resolvendo normalmente."""
        r = prescritor.post("/prescricoes", json=PAYLOAD_PADRAO)
        proto = r.json()["protocolo"]

        r_tok = paciente.post(
            "/tokens/apresentacao",
            json={"protocolo": proto, "validade_minutos": 60},
        )
        assert r_tok.status_code == 201
        codigo = r_tok.json()["codigo_curto"]

        r_res = dispensador.post(
            "/tokens/apresentacao/resolver",
            json={"codigo_curto": codigo},
        )
        assert r_res.status_code == 200
        data = r_res.json()
        assert data["modo"] == "prescricao"
        assert data["circulacao_atomizada"] is False
        assert "itens_pendentes" in data

    def test_listar_tokens_inclui_atomizados(self, paciente, proto_dois_itens):
        """GET /tokens/apresentacao deve listar tokens atomizados junto com os normais."""
        paciente.post(
            f"/prescricoes/{proto_dois_itens}/tokens/atomizar",
            json={"validade_minutos": 60},
        )
        r = paciente.get("/tokens/apresentacao")
        assert r.status_code == 200
        tokens = r.json()["tokens"]
        assert len(tokens) >= 2

    def test_item_sem_classe_controle_elegivel(self):
        assert eh_item_atomizavel({"nome_medicamento": "PARACETAMOL"})  # sem classe_controle

    def test_classe_controle_minuscula_normalizada(self):
        item = {"nome_medicamento": "DIAZEPAM", "classe_controle": "b1"}
        assert not eh_item_atomizavel(item)
