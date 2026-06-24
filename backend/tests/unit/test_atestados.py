"""
test_atestados.py — emissão e ciclo do atestado (objeto sanitário monolítico).
Harness SQLite (prescritor/db_path do conftest).
"""
from __future__ import annotations

import json
import sqlite3
import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")

import app.routers.atestados as at
import app.routers.prescritor as pcert
from app.domain.pdf_assinatura import pdf_tem_assinatura
from tests.fixtures.certificado_teste import gerar_certificado_teste


@pytest.fixture
def sem_demo(monkeypatch):
    monkeypatch.setattr(at, "PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
    yield


def _upload_cert(prescritor, cert):
    return prescritor.post(
        "/prescritor/certificado",
        files={"pfx_file": ("teste.pfx", cert.pfx_bytes, "application/x-pkcs12")},
        data={"senha": cert.senha},
    )


_BASE = {
    "cns_prescritor": "123456789012345",   # = token sub do RoleClient prescritor
    "nome_prescritor": "Dra. Atesta",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Atesta",
    "finalidade": "Afastamento do trabalho",
    "dias_afastamento": 3,
    "data_documento": "2026-06-23",
}


def _payload(**ov):
    return {**_BASE, **ov}


def _conn(db_path):
    c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
    return c


def _eventos(db_path, protocolo):
    with _conn(db_path) as c:
        rows = c.execute(
            """
            SELECT ae.tipo_evento FROM atestado_eventos ae
              JOIN atestados a ON a.id = ae.atestado_id
             WHERE a.protocolo = ? ORDER BY ae.id
            """,
            (protocolo,),
        ).fetchall()
    return [r["tipo_evento"] for r in rows]


class TestEmissaoDigital:

    def test_emite_e_retorna_protocolo(self, prescritor):
        r = prescritor.post("/atestados", json=_payload())
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["status"] == "emitido"
        assert d["finalidade"] == "Afastamento do trabalho"
        assert d["data_validade"] == "2026-06-26"   # 23 + 3 dias
        assert d["assinatura_hash"]

    def test_ledger_tem_emissao_e_custodia(self, prescritor, db_path):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        evs = _eventos(db_path, proto)
        assert "atestado_emitido" in evs
        assert "custodia_transferida" in evs

    def test_custodia_prescritor_para_paciente(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        r = prescritor.get(f"/atestados/{proto}/custodia")
        assert r.status_code == 200
        cust = r.json()["custodia"]
        assert len(cust) == 1
        assert cust[0]["de"] == "prescritor" and cust[0]["para"] == "paciente"

    def test_consulta_retorna_dados(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(codigo_cid="J11")).json()["protocolo"]
        d = prescritor.get(f"/atestados/{proto}").json()
        assert d["codigo_cid"] == "J11"
        assert d["nome_paciente"]

    def test_sem_dias_nao_tem_validade(self, prescritor):
        d = prescritor.post("/atestados", json=_payload(
            finalidade="Comparecimento", dias_afastamento=None)).json()
        assert d["dias_afastamento"] is None
        assert d["data_validade"] is None

    def test_finalidade_obrigatoria_422(self, prescritor):
        r = prescritor.post("/atestados", json=_payload(finalidade="  "))
        assert r.status_code == 422

    def test_cpf_sentinela_no_digital_422(self, prescritor):
        r = prescritor.post("/atestados", json=_payload(cpf_paciente="00000000000"))
        assert r.status_code == 422


class TestEmissaoFisica:

    def test_fisica_encerrada_localmente_sem_custodia(self, prescritor, db_path):
        r = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345",
            "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento",
        })
        assert r.status_code == 201, r.text
        proto = r.json()["protocolo"]
        assert r.json()["status"] == "encerrada_localmente"
        evs = _eventos(db_path, proto)
        assert evs == ["atestado_impresso", "encerrada_localmente"]
        # sem custódia no fluxo físico
        with _conn(db_path) as c:
            n = c.execute(
                "SELECT COUNT(*) n FROM atestado_custodia ac "
                "JOIN atestados a ON a.id = ac.atestado_id WHERE a.protocolo = ?",
                (proto,),
            ).fetchone()["n"]
        assert n == 0


class TestPdfEAssinatura:

    def test_get_pdf(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        r = prescritor.get(f"/atestados/{proto}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_assina_pdf_e_transiciona_para_assinado(self, prescritor, db_path, sem_demo):
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload_cert(prescritor, cert).status_code == 201
        r = prescritor.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": cert.senha})
        assert r.status_code == 200, r.text
        assert pdf_tem_assinatura(r.content)
        # status transicionou + evento no ledger
        assert prescritor.get(f"/atestados/{proto}").json()["status"] == "assinado"
        assert "atestado_assinado" in _eventos(db_path, proto)

    def test_pdf_assinado_sem_cert_422(self, prescritor, sem_demo):
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        r = prescritor.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": "x"})
        assert r.status_code == 422


class TestValidacaoPublica:

    def test_publico_neutro_nao_vaza_clinica(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(
            finalidade="Afastamento", codigo_cid="J11", indicacao_clinica="gripe")).json()["protocolo"]
        d = prescritor.get(f"/public/atestados/{proto}").json()
        # confirma existência/estado…
        assert d["protocolo"] == proto
        assert d["status"] == "emitido"
        assert d["assinado"] is False
        assert "vigente" in d              # vigência exposta só como booleano derivado
        # …sem JAMAIS vazar clínica/identidade
        blob = json.dumps(d).lower()
        for proibido in ("finalidade", "afastamento", "j11", "gripe", "cid",
                          "paciente", "cpf", "indicacao", "prescritor"):
            assert proibido not in blob, f"vazou: {proibido}"
        # Revisão #60: as datas NÃO podem aparecer — data_validade = data_documento
        # + dias_afastamento permitiria derivar os dias de afastamento (clínico).
        assert "data_documento" not in d and "data_validade" not in d
        assert "2026-06-23" not in blob and "2026-06-26" not in blob

    def test_publico_404(self, prescritor):
        assert prescritor.get("/public/atestados/inexistente").status_code == 404

    def test_publico_assinado_nao_vaza_datas(self, prescritor, sem_demo):
        """Revisão #60: nem no estado assinado o público expõe as datas/dias."""
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload_cert(prescritor, cert).status_code == 201
        assert prescritor.post(f"/atestados/{proto}/pdf-assinado",
                               json={"senha_pfx": cert.senha}).status_code == 200
        d = prescritor.get(f"/public/atestados/{proto}").json()
        assert d["status"] == "assinado" and d["assinado"] is True
        assert "vigente" in d
        assert "data_documento" not in d and "data_validade" not in d
        blob = json.dumps(d).lower()
        assert "2026-06-23" not in blob and "2026-06-26" not in blob


class TestRBACLeitura:
    """Revisão #60 — leitura autenticada: o paciente-titular acessa o próprio
    atestado (GET, /pdf, /custodia); outros papéis e não-titulares recebem 403."""

    def test_paciente_titular_le_atestado_pdf_custodia(self, prescritor, paciente):
        # fixture `paciente`: CPF 12345678901 == cpf_paciente do _BASE → é o titular
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        assert paciente.get(f"/atestados/{proto}").status_code == 200
        assert paciente.get(f"/atestados/{proto}/pdf").status_code == 200
        assert paciente.get(f"/atestados/{proto}/custodia").status_code == 200

    def test_outro_paciente_nao_titular_403(self, prescritor, outro_paciente):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert outro_paciente.get(path).status_code == 403, path

    def test_dispensador_sem_acesso_403(self, prescritor, dispensador):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert dispensador.get(path).status_code == 403, path

    def test_prescritor_nao_autor_403(self, prescritor, _shared_client, sem_demo):
        from app.main import app
        from app.auth.dependencies import get_current_user
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        # passa a ser um prescritor B (CNS distinto do autor)
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "prescritor", "sub": "999999999999999"}
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert _shared_client.get(path).status_code == 403, path
        # …e não pode assinar o atestado de outro (owner-check antes do certificado)
        r = _shared_client.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": "x"})
        assert r.status_code == 403, r.text
