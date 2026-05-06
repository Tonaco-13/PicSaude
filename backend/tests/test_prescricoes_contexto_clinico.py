"""
test_prescricoes_contexto_clinico.py
=====================================
Ticket 36 — Prescrição com Contexto Clínico (indicacao_clinica + codigo_cid)

Cobre:
  Criação
    1.  Prescrição com ambos os campos
    2.  Apenas indicacao_clinica
    3.  Apenas codigo_cid
    4.  Sem ambos os campos (retrocompatibilidade)
    5.  Strings vazias tratadas como NULL
    6.  Strings com espaços à esquerda/direita

  Persistência
    7.  indicacao_clinica persistida corretamente no banco
    8.  codigo_cid persistido corretamente no banco
    9.  Ambos persistidos quando fornecidos
   10.  NULL no banco quando não fornecidos

  Ledger
   11.  Payload do evento contém indicacao_clinica quando presente
   12.  Payload do evento contém codigo_cid quando presente
   13.  Payload do evento contém ambos quando ambos presentes
   14.  Payload do evento NÃO contém indicacao_clinica quando ausente
   15.  Payload do evento NÃO contém codigo_cid quando ausente

  Retrocompatibilidade
   16.  Payload sem os campos novos continua retornando 201
   17.  Status e fluxo de dispensação não são afetados
   18.  Prescrição física não aceita os novos campos (não aplica — é FisicaIn)
   19.  Correção (tipo_emissao=correcao) aceita novos campos

  Validação estrutural
   20.  indicacao_clinica muito longa (>2000 chars) é aceita (sem limite rígido no MVP)
   21.  codigo_cid com formato livre é aceito (sem validação semântica no backend)
   22.  Campos presentes na resposta do endpoint (None quando ausentes)
   23.  Campos presentes na resposta quando fornecidos

  Determinismo / idempotência
   24.  Duas prescrições com mesmo CID têm CIDs independentes no banco
"""

from __future__ import annotations

import json
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Fixtures / setup (reutiliza conftest.py da pasta tests/)
# ---------------------------------------------------------------------------

_BASE_ITEM = {
    "nome_medicamento": "AMOXICILINA",
    "concentracao": "500mg",
    "quantidade": 10,
    "posologia": "1 capsula 3x ao dia",
}

_BASE_PRESCRICAO = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "Dr. Contexto",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Contexto",
    "tipo_emissao": "nova",
    "itens": [_BASE_ITEM],
}


def _payload(**overrides) -> dict:
    """Retorna cópia do payload base com overrides aplicados."""
    p = {**_BASE_PRESCRICAO}
    p.update(overrides)
    return p


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------------------
# Classe 1 — Criação com campos de contexto clínico
# ---------------------------------------------------------------------------

class TestCriacaoComContextoClinico:

    def test_ambos_os_campos(self, prescritor):
        """T01 — Prescrição com indicacao_clinica e codigo_cid retorna 201."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Hipertensão arterial sistêmica",
            codigo_cid="I10",
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["indicacao_clinica"] == "Hipertensão arterial sistêmica"
        assert data["codigo_cid"] == "I10"

    def test_apenas_indicacao_clinica(self, prescritor):
        """T02 — Prescrição com apenas indicacao_clinica retorna 201."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Diabetes mellitus tipo 2",
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["indicacao_clinica"] == "Diabetes mellitus tipo 2"
        assert data["codigo_cid"] is None

    def test_apenas_codigo_cid(self, prescritor):
        """T03 — Prescrição com apenas codigo_cid retorna 201."""
        resp = prescritor.post("/prescricoes", json=_payload(
            codigo_cid="E11",
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["codigo_cid"] == "E11"
        assert data["indicacao_clinica"] is None

    def test_sem_ambos_os_campos(self, prescritor):
        """T04 — Prescrição sem os campos novos retorna 201 (retrocompatibilidade)."""
        resp = prescritor.post("/prescricoes", json=_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["indicacao_clinica"] is None
        assert data["codigo_cid"] is None

    def test_string_vazia_tratada_como_null(self, prescritor):
        """T05 — String vazia é tratada como NULL no backend."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="",
            codigo_cid="",
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["indicacao_clinica"] is None
        assert data["codigo_cid"] is None

    def test_strings_com_espacos(self, prescritor):
        """T06 — Strings são aceitas mesmo com espaços."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="  Hipertensão  ",
            codigo_cid=" I10 ",
        ))
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Classe 2 — Persistência no banco de dados
# ---------------------------------------------------------------------------

class TestPersistenciaContextoClinico:

    def test_indicacao_clinica_persiste_no_banco(self, prescritor, db_path):
        """T07 — indicacao_clinica é salva corretamente no banco."""
        texto = "Infecção do trato urinário"
        resp = prescritor.post("/prescricoes", json=_payload(indicacao_clinica=texto))
        assert resp.status_code == 201
        protocolo = resp.json()["protocolo"]

        with _conn(db_path) as c:
            row = c.execute(
                "SELECT indicacao_clinica FROM prescricoes WHERE protocolo = ?",
                (protocolo,),
            ).fetchone()
        assert row is not None
        assert row["indicacao_clinica"] == texto

    def test_codigo_cid_persiste_no_banco(self, prescritor, db_path):
        """T08 — codigo_cid é salvo corretamente no banco."""
        resp = prescritor.post("/prescricoes", json=_payload(codigo_cid="N39"))
        assert resp.status_code == 201
        protocolo = resp.json()["protocolo"]

        with _conn(db_path) as c:
            row = c.execute(
                "SELECT codigo_cid FROM prescricoes WHERE protocolo = ?",
                (protocolo,),
            ).fetchone()
        assert row is not None
        assert row["codigo_cid"] == "N39"

    def test_ambos_persistem_no_banco(self, prescritor, db_path):
        """T09 — indicacao_clinica e codigo_cid persistem juntos."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Angina instável",
            codigo_cid="I20",
        ))
        assert resp.status_code == 201
        protocolo = resp.json()["protocolo"]

        with _conn(db_path) as c:
            row = c.execute(
                "SELECT indicacao_clinica, codigo_cid FROM prescricoes WHERE protocolo = ?",
                (protocolo,),
            ).fetchone()
        assert row["indicacao_clinica"] == "Angina instável"
        assert row["codigo_cid"] == "I20"

    def test_null_no_banco_quando_ausentes(self, prescritor, db_path):
        """T10 — NULL é gravado no banco quando campos não são enviados."""
        resp = prescritor.post("/prescricoes", json=_payload())
        assert resp.status_code == 201
        protocolo = resp.json()["protocolo"]

        with _conn(db_path) as c:
            row = c.execute(
                "SELECT indicacao_clinica, codigo_cid FROM prescricoes WHERE protocolo = ?",
                (protocolo,),
            ).fetchone()
        assert row["indicacao_clinica"] is None
        assert row["codigo_cid"] is None


# ---------------------------------------------------------------------------
# Classe 3 — Ledger
# ---------------------------------------------------------------------------

class TestLedgerContextoClinico:

    def _get_evento(self, db_path: str, protocolo: str, tipo: str) -> dict:
        with _conn(db_path) as c:
            row = c.execute(
                """
                SELECT pe.payload_json
                  FROM prescricao_eventos pe
                  JOIN prescricoes p ON p.id = pe.prescricao_id
                 WHERE p.protocolo = ? AND pe.tipo_evento = ?
                """,
                (protocolo, tipo),
            ).fetchone()
        assert row is not None, f"Evento '{tipo}' não encontrado no ledger"
        return json.loads(row["payload_json"])

    def test_ledger_contem_indicacao_clinica(self, prescritor, db_path):
        """T11 — Payload do evento prescricao_emitida contém indicacao_clinica."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Bronquite aguda",
        ))
        protocolo = resp.json()["protocolo"]
        ev = self._get_evento(db_path, protocolo, "prescricao_emitida")
        assert "indicacao_clinica" in ev
        assert ev["indicacao_clinica"] == "Bronquite aguda"

    def test_ledger_contem_codigo_cid(self, prescritor, db_path):
        """T12 — Payload do evento prescricao_emitida contém codigo_cid."""
        resp = prescritor.post("/prescricoes", json=_payload(codigo_cid="J20"))
        protocolo = resp.json()["protocolo"]
        ev = self._get_evento(db_path, protocolo, "prescricao_emitida")
        assert "codigo_cid" in ev
        assert ev["codigo_cid"] == "J20"

    def test_ledger_contem_ambos(self, prescritor, db_path):
        """T13 — Payload do evento contém ambos quando ambos fornecidos."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Asma brônquica",
            codigo_cid="J45",
        ))
        protocolo = resp.json()["protocolo"]
        ev = self._get_evento(db_path, protocolo, "prescricao_emitida")
        assert ev.get("indicacao_clinica") == "Asma brônquica"
        assert ev.get("codigo_cid") == "J45"

    def test_ledger_nao_contem_indicacao_quando_ausente(self, prescritor, db_path):
        """T14 — Payload do evento NÃO contém indicacao_clinica quando ausente."""
        resp = prescritor.post("/prescricoes", json=_payload())
        protocolo = resp.json()["protocolo"]
        ev = self._get_evento(db_path, protocolo, "prescricao_emitida")
        assert "indicacao_clinica" not in ev

    def test_ledger_nao_contem_cid_quando_ausente(self, prescritor, db_path):
        """T15 — Payload do evento NÃO contém codigo_cid quando ausente."""
        resp = prescritor.post("/prescricoes", json=_payload())
        protocolo = resp.json()["protocolo"]
        ev = self._get_evento(db_path, protocolo, "prescricao_emitida")
        assert "codigo_cid" not in ev


# ---------------------------------------------------------------------------
# Classe 4 — Retrocompatibilidade
# ---------------------------------------------------------------------------

class TestRetrocompatibilidade:

    def test_payload_antigo_funciona(self, prescritor):
        """T16 — Payload sem os campos novos retorna 201 sem erros."""
        payload_antigo = {
            "cns_prescritor": "123456789012345",
            "nome_prescritor": "Dr. Legado",
            "cpf_paciente": "98765432100",
            "nome_paciente": "Paciente Legado",
            "tipo_emissao": "nova",
            "itens": [_BASE_ITEM],
        }
        resp = prescritor.post("/prescricoes", json=payload_antigo)
        assert resp.status_code == 201

    def test_status_inicial_nao_afetado(self, prescritor):
        """T17 — Status da prescrição com CID ainda começa como 'pendente'."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Hipertensão",
            codigo_cid="I10",
        ))
        assert resp.status_code == 201
        assert resp.json()["status"] == "pendente"

    def test_correcao_aceita_novos_campos(self, prescritor):
        """T19 — tipo_emissao=correcao também aceita indicacao_clinica e codigo_cid."""
        # Criar original
        r1 = prescritor.post("/prescricoes", json=_payload())
        assert r1.status_code == 201
        id_orig = r1.json()["id"]

        # Correção com contexto clínico
        correcao = _payload(
            tipo_emissao="correcao",
            origem_prescricao_id=id_orig,
            indicacao_clinica="Hipertensão arterial — corrigida",
            codigo_cid="I10",
        )
        r2 = prescritor.post("/prescricoes", json=correcao)
        assert r2.status_code == 201
        data = r2.json()
        assert data["tipo_emissao"] == "correcao"
        assert data["indicacao_clinica"] == "Hipertensão arterial — corrigida"
        assert data["codigo_cid"] == "I10"


# ---------------------------------------------------------------------------
# Classe 5 — Validação estrutural e resposta
# ---------------------------------------------------------------------------

class TestValidacaoEstruturalEResposta:

    def test_indicacao_longa_e_aceita(self, prescritor):
        """T20 — indicacao_clinica com >2000 chars é aceita sem limite rígido no MVP."""
        texto_longo = "Paciente com " + ("hipertensão arterial sistêmica " * 70)
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica=texto_longo,
        ))
        assert resp.status_code == 201

    def test_codigo_cid_formato_livre_aceito(self, prescritor):
        """T21 — codigo_cid aceita qualquer string (sem validação semântica no backend)."""
        resp = prescritor.post("/prescricoes", json=_payload(
            codigo_cid="Z00.0",  # formato com ponto
        ))
        assert resp.status_code == 201
        assert resp.json()["codigo_cid"] == "Z00.0"

    def test_campos_presentes_na_resposta_quando_ausentes(self, prescritor):
        """T22 — Resposta inclui indicacao_clinica=None e codigo_cid=None quando ausentes."""
        resp = prescritor.post("/prescricoes", json=_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert "indicacao_clinica" in data
        assert "codigo_cid" in data
        assert data["indicacao_clinica"] is None
        assert data["codigo_cid"] is None

    def test_campos_presentes_na_resposta_quando_fornecidos(self, prescritor):
        """T23 — Resposta retorna os valores corretos quando fornecidos."""
        resp = prescritor.post("/prescricoes", json=_payload(
            indicacao_clinica="Cefaleia tensional",
            codigo_cid="G44",
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["indicacao_clinica"] == "Cefaleia tensional"
        assert data["codigo_cid"] == "G44"


# ---------------------------------------------------------------------------
# Classe 6 — Determinismo / isolamento
# ---------------------------------------------------------------------------

class TestDeterminismoIsolamento:

    def test_dois_prescricoes_com_mesmo_cid_sao_independentes(self, prescritor, db_path):
        """T24 — Duas prescrições com mesmo CID têm registros independentes no banco."""
        r1 = prescritor.post("/prescricoes", json=_payload(
            cpf_paciente="11111111111",
            codigo_cid="I10",
        ))
        r2 = prescritor.post("/prescricoes", json=_payload(
            cpf_paciente="22222222222",
            codigo_cid="I10",
        ))
        assert r1.status_code == 201
        assert r2.status_code == 201

        p1 = r1.json()["protocolo"]
        p2 = r2.json()["protocolo"]
        assert p1 != p2

        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT protocolo, codigo_cid FROM prescricoes WHERE codigo_cid = 'I10'"
            ).fetchall()
        protocolos = [r["protocolo"] for r in rows]
        assert p1 in protocolos
        assert p2 in protocolos
        assert len(protocolos) == 2
