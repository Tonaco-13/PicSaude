"""
F2 — validação da cadeia de confiança ICP-Brasil (app/domain/validacao_cadeia_icp.py).

Cobre:
  - certificado encadeado a uma AC-Raiz confiável → válido;
  - autoassinado com emissor forjado → rejeitado (o buraco que o Jules apontou);
  - certificado de uma CA fora do truststore → rejeitado;
  - sem truststore: dev/test pula (avaliada=False); prod falha fechado.
"""
from __future__ import annotations

import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

from app.domain.validacao_cadeia_icp import (
    TrustStoreIndisponivel,
    validar_cadeia_icp,
)

_NOW = dt.datetime(2026, 1, 1)
_MOMENTO = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _pem(cert) -> str:
    return cert.public_bytes(Encoding.PEM).decode("utf-8")


def _build_ca(cn: str):
    key = _key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(cn)).issuer_name(_name(cn))
        .public_key(key.public_key()).serial_number(1)
        .not_valid_before(_NOW).not_valid_after(dt.datetime(2030, 1, 1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _build_leaf(ca_key, ca_cert, cn: str):
    key = _key()
    return (
        x509.CertificateBuilder()
        .subject_name(_name(cn)).issuer_name(ca_cert.subject)
        .public_key(key.public_key()).serial_number(2)
        .not_valid_before(_NOW).not_valid_after(dt.datetime(2027, 1, 1))
        .sign(ca_key, hashes.SHA256())   # assinado pela CA
    )


def _build_autoassinado_forjado(cn: str, issuer_falso: str):
    """Cert assinado pela própria chave, mas com nome de emissor forjado."""
    key = _key()
    return (
        x509.CertificateBuilder()
        .subject_name(_name(cn)).issuer_name(_name(issuer_falso))
        .public_key(key.public_key()).serial_number(3)
        .not_valid_before(_NOW).not_valid_after(dt.datetime(2027, 1, 1))
        .sign(key, hashes.SHA256())      # assinado pela PRÓPRIA chave
    )


def _truststore(tmp_path, *cas) -> str:
    path = tmp_path / "icp_roots.pem"
    with open(path, "wb") as fh:
        for c in cas:
            fh.write(c.public_bytes(Encoding.PEM))
    return str(path)


# ---------------------------------------------------------------------------

def test_cadeia_valida_quando_ancorada_em_ac_confiavel(tmp_path, monkeypatch):
    ca_key, ca = _build_ca("AC Raiz Teste")
    leaf = _build_leaf(ca_key, ca, "DR TESTE:12345678901")
    monkeypatch.setenv("PICSAUDE_ICP_TRUSTSTORE", _truststore(tmp_path, ca))

    r = validar_cadeia_icp(_pem(leaf), momento=_MOMENTO)
    assert r.valida is True and r.avaliada is True


def test_autoassinado_forjado_rejeitado(tmp_path, monkeypatch):
    """O caso do Jules: autoassinado com emissor forjado NÃO pode passar."""
    ca_key, ca = _build_ca("AC Raiz Teste")
    fake = _build_autoassinado_forjado("DR FRAUDE:99999999999", "AC Raiz Teste")
    monkeypatch.setenv("PICSAUDE_ICP_TRUSTSTORE", _truststore(tmp_path, ca))

    r = validar_cadeia_icp(_pem(fake), momento=_MOMENTO)
    assert r.valida is False


def test_ca_fora_do_truststore_rejeitada(tmp_path, monkeypatch):
    ca_key, ca = _build_ca("AC Verdadeira")
    leaf = _build_leaf(ca_key, ca, "DR TESTE:12345678901")
    _, outra_ca = _build_ca("AC Estranha")
    monkeypatch.setenv("PICSAUDE_ICP_TRUSTSTORE", _truststore(tmp_path, outra_ca))

    r = validar_cadeia_icp(_pem(leaf), momento=_MOMENTO)
    assert r.valida is False


def test_sem_truststore_em_dev_pula(monkeypatch):
    monkeypatch.delenv("PICSAUDE_ICP_TRUSTSTORE", raising=False)
    monkeypatch.setenv("PICSAUDE_ENV", "dev")
    ca_key, ca = _build_ca("AC")
    leaf = _build_leaf(ca_key, ca, "DR:1")

    r = validar_cadeia_icp(_pem(leaf), momento=_MOMENTO)
    assert r.valida is True and r.avaliada is False


@pytest.mark.parametrize("env", ["stg", "prod"])
def test_sem_truststore_fora_de_dev_test_falha_fechado(monkeypatch, env):
    monkeypatch.delenv("PICSAUDE_ICP_TRUSTSTORE", raising=False)
    monkeypatch.setenv("PICSAUDE_ENV", env)
    ca_key, ca = _build_ca("AC")
    leaf = _build_leaf(ca_key, ca, "DR:1")

    with pytest.raises(TrustStoreIndisponivel):
        validar_cadeia_icp(_pem(leaf), momento=_MOMENTO)
