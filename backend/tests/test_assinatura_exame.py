"""
test_assinatura_exame.py — assinatura ICP-Brasil PAdES do pedido de exame.
Fluxo local (SQLite): emite → upload cert teste → assina → PDF tem assinatura.
"""
from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")

import app.routers.pedidos_exame as pe
import app.routers.prescritor as pcert
from app.domain.pdf_assinatura import pdf_tem_assinatura
from tests.fixtures.certificado_teste import gerar_certificado_teste

_BASE = {
    "cns_prescritor": "123456789012345",   # = token sub do RoleClient prescritor
    "nome_prescritor": "Dr. Exame",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Exame",
    "prioridade": "rotina",
    "indicacao_clinica": "Investigação de anemia",
    "itens": [{"nome_exame": "HEMOGRAMA COMPLETO", "quantidade": 1}],
}


def _emitir(prescritor) -> str:
    r = prescritor.post("/pedidos-exame", json=_BASE)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _upload(prescritor, cert):
    return prescritor.post(
        "/prescritor/certificado",
        files={"pfx_file": ("teste.pfx", cert.pfx_bytes, "application/x-pkcs12")},
        data={"senha": cert.senha},
    )


@pytest.fixture
def sem_demo(monkeypatch):
    monkeypatch.setattr(pe, "PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
    yield


class TestAssinaturaExame:

    def test_fluxo_completo_assina_pdf(self, prescritor, sem_demo):
        proto = _emitir(prescritor)
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/pedidos-exame/{proto}/pdf-assinado", json={"senha_pfx": cert.senha})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert pdf_tem_assinatura(r.content)

    def test_sem_certificado_422(self, prescritor, sem_demo):
        proto = _emitir(prescritor)
        r = prescritor.post(f"/pedidos-exame/{proto}/pdf-assinado", json={"senha_pfx": "x"})
        assert r.status_code == 422

    def test_senha_errada_401(self, prescritor, sem_demo):
        proto = _emitir(prescritor)
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/pedidos-exame/{proto}/pdf-assinado", json={"senha_pfx": "errada"})
        assert r.status_code == 401

    def test_demo_mode_403(self, prescritor, monkeypatch):
        monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
        monkeypatch.setattr(pe, "PICSAUDE_DEMO_MODE", True)
        proto = _emitir(prescritor)
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/pedidos-exame/{proto}/pdf-assinado", json={"senha_pfx": cert.senha})
        assert r.status_code == 403
