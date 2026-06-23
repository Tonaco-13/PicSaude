"""
test_assinatura_a1_prescricao.py — assinatura ICP-Brasil PAdES da prescrição comum.
==================================================================================
Fluxo local (SQLite + TestClient), end-to-end, com certificado de TESTE:

  1. emite prescrição com assinatura_modo=icp_brasil_local
  2. upload do certificado no cofre (POST /prescritor/certificado)
  3. POST /prescricoes/{proto}/pdf-assinado com a senha → PDF assinado PAdES-B
  4. o PDF retornado tem assinatura embutida (pdf_tem_assinatura)

+ caminhos de erro: sem certificado (422), senha errada (401), modo não-ICP (422),
  modo demo bloqueia a assinatura com chave real (403).

Usa o certificado autoassinado de `tests.fixtures.certificado_teste` — nunca uma
chave real. O cofre cifra em repouso; em PICSAUDE_ENV=test a cadeia ICP é pulada.
"""
from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")

import app.routers.prescricoes as pr
import app.routers.prescritor as pcert
from app.domain.pdf_assinatura import pdf_tem_assinatura
from tests.fixtures.certificado_teste import gerar_certificado_teste

_ITEM = {"nome_medicamento": "captopril", "concentracao": "25mg",
         "quantidade": 30, "unidade_quantidade": "comprimido",
         "posologia": "1x ao dia"}   # modo CFM exige unidade_quantidade
_BASE = {
    "cns_prescritor": "123456789012345",   # = token sub do RoleClient prescritor
    "nome_prescritor": "Dr. Assina",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Assina",
    "tipo_emissao": "nova",
    "itens": [_ITEM],
}


def _emitir(prescritor, **ov) -> str:
    r = prescritor.post("/prescricoes", json={**_BASE, **ov})
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
    """Garante DEMO_MODE desligado nos dois routers (upload + assinatura)."""
    monkeypatch.setattr(pr, "PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
    yield


class TestAssinaturaA1Prescricao:

    def test_fluxo_completo_assina_e_retorna_pdf(self, prescritor, sem_demo):
        proto = _emitir(prescritor, assinatura_modo="icp_brasil_local")
        cert = gerar_certificado_teste(nome="DR ASSINA TESTE", cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201

        r = prescritor.post(f"/prescricoes/{proto}/pdf-assinado",
                            json={"senha_pfx": cert.senha})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert pdf_tem_assinatura(r.content), "PDF retornado não contém assinatura"

    def test_sem_certificado_da_422(self, prescritor, sem_demo):
        proto = _emitir(prescritor, assinatura_modo="icp_brasil_local")
        r = prescritor.post(f"/prescricoes/{proto}/pdf-assinado",
                            json={"senha_pfx": "qualquer"})
        assert r.status_code == 422

    def test_senha_errada_da_401(self, prescritor, sem_demo):
        proto = _emitir(prescritor, assinatura_modo="icp_brasil_local")
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/prescricoes/{proto}/pdf-assinado",
                            json={"senha_pfx": "senha_errada"})
        assert r.status_code == 401

    def test_modo_nao_icp_da_422(self, prescritor, sem_demo):
        proto = _emitir(prescritor)   # sem assinatura_modo → não é icp_brasil_local
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/prescricoes/{proto}/pdf-assinado",
                            json={"senha_pfx": cert.senha})
        assert r.status_code == 422

    def test_demo_mode_bloqueia_assinatura_403(self, prescritor, monkeypatch):
        # upload liberado (cofre dev), mas assinatura com chave real bloqueada
        monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
        monkeypatch.setattr(pr, "PICSAUDE_DEMO_MODE", True)
        proto = _emitir(prescritor, assinatura_modo="icp_brasil_local")
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload(prescritor, cert).status_code == 201
        r = prescritor.post(f"/prescricoes/{proto}/pdf-assinado",
                            json={"senha_pfx": cert.senha})
        assert r.status_code == 403
