"""
test_assinatura_icp.py
=======================
Ticket 68 — Verificação criptográfica da assinatura ICP-Brasil (A1/A3).

Cobre:
   1. Assinatura válida
   2. Assinatura inválida por payload alterado
   3. Assinatura inválida por certificado incompatível
   4. Certificado expirado
   5. Certificado ainda não válido
   6. Base64 inválido
   7. Payload determinístico com ordem de chaves diferente → mesma verificação
   8. Via física sem cert/assinatura (bypass)
   9. Integração com T67: string gerada apenas na via digital válida
  10. Sem regressão

Todos os certificados e assinaturas são gerados em memória.
A assinatura é compatível com WebCrypto: sign(digest, PKCS1v15, SHA256)
usando Prehashed — exatamente o mesmo contrato que o frontend usa.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json

import pytest

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.x509.oid import NameOID

from app.domain.assinatura_icp import (
    ResultadoVerificacao,
    calcular_digest,
    serializar_payload,
    verificar_assinatura_icp,
    verificar_validade_temporal,
    _validade_cert,
)


# ---------------------------------------------------------------------------
# Helpers de geração de chave e certificado
# ---------------------------------------------------------------------------


def _gen_key():
    return rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )


def _make_cert(
    key,
    not_before: datetime.datetime | None = None,
    not_after: datetime.datetime | None = None,
    cn: str = "DR JOAO SILVA",
) -> x509.Certificate:
    now = datetime.datetime.utcnow()
    nb = not_before or now - datetime.timedelta(days=1)
    na = not_after  or now + datetime.timedelta(days=365)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC ICP TEST")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(nb)
        .not_valid_after(na)
        .sign(key, hashes.SHA256(), default_backend())
    )


def _to_pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _assinar(key, dados: dict) -> str:
    """Assina o digest SHA-256 do payload canônico com PKCS1v15 (Prehashed)."""
    digest = calcular_digest(dados)
    sig = key.sign(digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
    return base64.b64encode(sig).decode()


# ---------------------------------------------------------------------------
# Fixtures reutilizáveis
# ---------------------------------------------------------------------------


@pytest.fixture()
def chave_e_cert():
    key = _gen_key()
    cert = _make_cert(key)
    return key, cert, _to_pem(cert)


_PAYLOAD_PADRAO = {
    "cns_prescritor": "706108587809760",
    "cpf_paciente":   "12345678901",
    "tipo_emissao":   "nova",
    "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
               "quantidade": 10, "unidade_quantidade": None, "posologia": "1 cap 3x ao dia"}],
}


# ---------------------------------------------------------------------------
# serializar_payload e calcular_digest
# ---------------------------------------------------------------------------


def test_serializar_payload_determinístico():
    """Mesmos dados em ordens diferentes → mesmos bytes."""
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert serializar_payload(d1) == serializar_payload(d2)


def test_serializar_payload_sem_espacos():
    dados = {"key": "val"}
    s = serializar_payload(dados)
    assert b" " not in s


def test_calcular_digest_consistente():
    d = {"x": 1}
    assert calcular_digest(d) == calcular_digest(d)


def test_calcular_digest_32_bytes():
    assert len(calcular_digest({"a": 1})) == 32


# ---------------------------------------------------------------------------
# verificar_validade_temporal
# ---------------------------------------------------------------------------


def test_validade_cert_dentro_do_prazo():
    key = _gen_key()
    cert = _make_cert(key)
    ok, erro = verificar_validade_temporal(cert)
    assert ok is True
    assert erro is None


def test_validade_cert_expirado():
    key = _gen_key()
    now = datetime.datetime.utcnow()
    cert = _make_cert(
        key,
        not_before=now - datetime.timedelta(days=730),
        not_after =now - datetime.timedelta(days=1),
    )
    ok, erro = verificar_validade_temporal(cert)
    assert ok is False
    assert erro == "certificado_expirado"


def test_validade_cert_nao_ativo():
    key = _gen_key()
    now = datetime.datetime.utcnow()
    cert = _make_cert(
        key,
        not_before=now + datetime.timedelta(days=10),
        not_after =now + datetime.timedelta(days=370),
    )
    ok, erro = verificar_validade_temporal(cert)
    assert ok is False
    assert erro == "certificado_nao_ativo"


# ---------------------------------------------------------------------------
# Caso 1 — Assinatura válida
# ---------------------------------------------------------------------------


def test_caso1_assinatura_valida(chave_e_cert):
    key, cert, pem = chave_e_cert
    sig = _assinar(key, _PAYLOAD_PADRAO)
    result = verificar_assinatura_icp(pem, sig, _PAYLOAD_PADRAO)
    assert result.valida is True
    assert result.assinatura_valida is True
    assert result.certificado_valido is True
    assert result.erro is None
    assert result.digest_hex is not None
    assert len(result.digest_hex) == 64


# ---------------------------------------------------------------------------
# Caso 2 — Assinatura inválida por payload alterado
# ---------------------------------------------------------------------------


def test_caso2_assinatura_invalida_payload_alterado(chave_e_cert):
    key, cert, pem = chave_e_cert
    sig = _assinar(key, _PAYLOAD_PADRAO)
    payload_alterado = {**_PAYLOAD_PADRAO, "cpf_paciente": "99999999999"}
    result = verificar_assinatura_icp(pem, sig, payload_alterado)
    assert result.valida is False
    assert result.assinatura_valida is False
    assert result.erro == "assinatura_invalida"


# ---------------------------------------------------------------------------
# Caso 3 — Assinatura inválida por certificado incompatível
# ---------------------------------------------------------------------------


def test_caso3_certificado_incompativel(chave_e_cert):
    """Assinatura de uma chave, verificação com cert de outra chave."""
    key_a, cert_a, pem_a = chave_e_cert
    key_b = _gen_key()
    cert_b = _make_cert(key_b)
    pem_b = _to_pem(cert_b)

    # Assina com chave A, verifica com cert B (chave pública diferente)
    sig = _assinar(key_a, _PAYLOAD_PADRAO)
    result = verificar_assinatura_icp(pem_b, sig, _PAYLOAD_PADRAO)
    assert result.valida is False
    assert result.assinatura_valida is False
    assert result.erro == "assinatura_invalida"


# ---------------------------------------------------------------------------
# Caso 4 — Certificado expirado
# ---------------------------------------------------------------------------


def test_caso4_certificado_expirado():
    key = _gen_key()
    now = datetime.datetime.utcnow()
    cert = _make_cert(
        key,
        not_before=now - datetime.timedelta(days=730),
        not_after =now - datetime.timedelta(days=1),
    )
    pem = _to_pem(cert)
    sig = _assinar(key, _PAYLOAD_PADRAO)
    result = verificar_assinatura_icp(pem, sig, _PAYLOAD_PADRAO)
    assert result.valida is False
    # Assinatura é matematicamente válida mesmo com cert expirado
    assert result.assinatura_valida is True
    assert result.certificado_valido is False
    assert result.erro == "certificado_expirado"


# ---------------------------------------------------------------------------
# Caso 5 — Certificado ainda não válido
# ---------------------------------------------------------------------------


def test_caso5_certificado_nao_ativo():
    key = _gen_key()
    now = datetime.datetime.utcnow()
    cert = _make_cert(
        key,
        not_before=now + datetime.timedelta(days=10),
        not_after =now + datetime.timedelta(days=370),
    )
    pem = _to_pem(cert)
    sig = _assinar(key, _PAYLOAD_PADRAO)
    result = verificar_assinatura_icp(pem, sig, _PAYLOAD_PADRAO)
    assert result.valida is False
    assert result.assinatura_valida is True   # assinatura ok
    assert result.certificado_valido is False
    assert result.erro == "certificado_nao_ativo"


# ---------------------------------------------------------------------------
# Caso 6 — Base64 inválido
# ---------------------------------------------------------------------------


def test_caso6_base64_invalido(chave_e_cert):
    _, _, pem = chave_e_cert
    result = verificar_assinatura_icp(pem, "!!!nao_e_base64!!!", _PAYLOAD_PADRAO)
    assert result.valida is False
    assert "base64_invalido" in result.erro


def test_caso6_base64_vazio(chave_e_cert):
    _, _, pem = chave_e_cert
    result = verificar_assinatura_icp(pem, "", _PAYLOAD_PADRAO)
    # String vazia decodifica para bytes vazios → InvalidSignature
    assert result.valida is False


# ---------------------------------------------------------------------------
# Caso 7 — Payload determinístico com ordem de chaves diferente
# ---------------------------------------------------------------------------


def test_caso7_payload_ordem_chaves_diferente(chave_e_cert):
    """
    Verifica que sort_keys=True garante que a ordem das chaves não afeta
    o digest. Frontend pode enviar as chaves em qualquer ordem.
    """
    key, cert, pem = chave_e_cert

    # Assinar com uma ordem
    payload_ordem_1 = {
        "tipo_emissao": "nova",
        "cns_prescritor": "706108587809760",
        "cpf_paciente": "12345678901",
        "itens": [{"nome_medicamento": "AMOX", "concentracao": "500mg",
                   "quantidade": 10, "unidade_quantidade": None, "posologia": "1x"}],
    }
    # Mesmos dados, outra ordem
    payload_ordem_2 = {
        "cpf_paciente": "12345678901",
        "itens": [{"posologia": "1x", "quantidade": 10, "nome_medicamento": "AMOX",
                   "concentracao": "500mg", "unidade_quantidade": None}],
        "cns_prescritor": "706108587809760",
        "tipo_emissao": "nova",
    }

    assert calcular_digest(payload_ordem_1) == calcular_digest(payload_ordem_2)

    # Assinar com ordem 1, verificar com ordem 2
    sig = _assinar(key, payload_ordem_1)
    result = verificar_assinatura_icp(pem, sig, payload_ordem_2)
    assert result.valida is True


# ---------------------------------------------------------------------------
# Caso 8 — Via física sem cert/assinatura (bypass)
# ---------------------------------------------------------------------------


def test_caso8_via_fisica_sem_cert_e_assinatura(client_com_db_68):
    """Via física: sem cert_pem e sem assinatura_b64 → emissão não bloqueada."""
    client, _ = client_com_db_68
    resp = client.post("/prescricoes", json=_PAYLOAD_API_PADRAO)
    assert resp.status_code == 201
    data = resp.json()
    # Sem ICP → campos devem ser None/falsy
    assert data.get("string_validacao_prescritor") is None
    assert not data.get("assinatura_valida")


# ---------------------------------------------------------------------------
# Caso 9 — String gerada apenas na via digital válida
# ---------------------------------------------------------------------------


def test_caso9_assinatura_invalida_nao_persiste(client_com_db_68):
    """Quando assinatura é inválida, HTTPException 422 é retornada."""
    client, _ = client_com_db_68
    key = _gen_key()
    cert = _make_cert(key)
    pem = _to_pem(cert)
    sig_invalida = base64.b64encode(b"assinatura_falsa").decode()

    payload = {
        **_PAYLOAD_API_PADRAO,
        "cert_pem": pem,
        "assinatura_b64": sig_invalida,
    }
    resp = client.post("/prescricoes", json=payload)
    assert resp.status_code == 422
    err = resp.json()
    assert "assinatura_invalida" in str(err)


def test_caso9_cert_sem_assinatura_bloqueado(client_com_db_68):
    """cert_pem sem assinatura_b64 → 422 após Ticket 68A (Cenário B bloqueado)."""
    client, _ = client_com_db_68
    key = _gen_key()
    cert = _make_cert(key)
    pem = _to_pem(cert)
    payload = {**_PAYLOAD_API_PADRAO, "cert_pem": pem}
    resp = client.post("/prescricoes", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Caso 10 — Sem regressão
# ---------------------------------------------------------------------------


def test_caso10_sem_regressao_modulos_anteriores():
    """T64, T65, T66, T67 continuam importáveis e funcionais."""
    from app.domain.nome_validator import NomeValidator
    from app.domain.icp_identity import parsear_certificado_icp
    from app.domain.string_validacao import gerar_string_validacao_identidade

    v = NomeValidator()
    ok, _, _ = v.validar_correspondencia("ANA SILVA", "ANA SILVA", "ANA SILVA")
    assert ok is True

    icp = parsear_certificado_icp("pem invalido")
    assert icp.parseable is False

    key = _gen_key()
    cert = _make_cert(key)
    pem = _to_pem(cert)
    from app.domain.string_validacao import hash_cert_der
    h = hash_cert_der(pem)
    assert len(h) == 64


def test_caso10_sem_regressao_emissao_normal(client_com_db_68):
    client, _ = client_com_db_68
    resp = client.post("/prescricoes", json=_PAYLOAD_API_PADRAO)
    assert resp.status_code == 201
    data = resp.json()
    assert "protocolo" in data
    assert "cnes_validacao" in data
    assert "score_confianca" in data


# ---------------------------------------------------------------------------
# ResultadoVerificacao.to_dict
# ---------------------------------------------------------------------------


def test_resultado_verificacao_to_dict():
    r = ResultadoVerificacao(
        valida=True,
        assinatura_valida=True,
        certificado_valido=True,
        erro=None,
        digest_hex="a" * 64,
    )
    d = r.to_dict()
    assert d["valida"] is True
    assert d["assinatura_valida"] is True
    assert d["digest_hex"] == "a" * 64
    assert d["erro"] is None


# ---------------------------------------------------------------------------
# PEM inválido
# ---------------------------------------------------------------------------


def test_pem_invalido_nao_lanca_excecao():
    result = verificar_assinatura_icp("pem invalido", "AAAA", {"a": 1})
    assert result.valida is False
    assert "pem_invalido" in result.erro


# ---------------------------------------------------------------------------
# Fixture de client com DB
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_com_db_68(tmp_path):
    import sqlite3
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    db_path = str(tmp_path / "test_icp.db")

    from app.database import Base
    import app.models  # noqa
    from init_tables import aplicar_triggers_ledger

    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    eng.dispose()
    aplicar_triggers_ledger(db_path)

    conn_raw = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn_raw.execute("PRAGMA table_info(prescricoes)").fetchall()}
        if "string_validacao_prescritor" not in cols:
            conn_raw.execute("ALTER TABLE prescricoes ADD COLUMN string_validacao_prescritor TEXT")
            conn_raw.commit()
        conn_raw.executescript("""
            CREATE TABLE IF NOT EXISTS profissionais_cnes (
                CO_PROFISSIONAL_SUS TEXT PRIMARY KEY, CO_CPF TEXT,
                NO_PROFISSIONAL TEXT, CO_CNS TEXT
            );
            CREATE TABLE IF NOT EXISTS relacao_prof_estab (
                CO_UNIDADE TEXT, CO_PROFISSIONAL_SUS TEXT, CO_CBO TEXT,
                CO_CONSELHO_CLASSE TEXT, NU_REGISTRO TEXT, SG_UF_CRM TEXT
            );
            CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
                CO_UNIDADE TEXT PRIMARY KEY, CO_CNES TEXT, NO_FANTASIA TEXT, TP_UNIDADE TEXT
            );
            CREATE TABLE IF NOT EXISTS prestadores (
                id INTEGER PRIMARY KEY, cnpj TEXT, org_id TEXT, ativo INTEGER, nome TEXT, tipo TEXT
            );
        """)
        conn_raw.commit()
    finally:
        conn_raw.close()

    def _get_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    from app.main import app
    from app.auth.dependencies import get_current_user
    from contextlib import ExitStack

    stack = ExitStack()
    targets = [
        "app.routers.prescricoes.get_conn",
        "app.routers.custodia.get_conn",
        "app.routers.dispensacoes.get_conn",
        "app.routers.tokens.get_conn",
        "app.routers.hospitalares.get_conn",
        "app.routers.agendamentos.get_conn",
        "app.routers.pedidos_exame.get_conn",
        "app.routers.auth.get_conn",
        "app.routers.eventos.get_conn",
        "app.routers.circulacao_diagnostica.get_conn",
    ]
    for t in targets:
        stack.enter_context(patch(t, _get_conn))

    app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "test"}
    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()

    yield client, _get_conn

    client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


_PAYLOAD_API_PADRAO = {
    "cns_prescritor": "706108587809760",
    "nome_prescritor": "DR TESTE",
    "cpf_paciente": "12345678901",
    "nome_paciente": "PACIENTE TESTE",
    "tipo_emissao": "nova",
    "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
               "quantidade": 10, "posologia": "1 cap 3x ao dia"}],
}


# ---------------------------------------------------------------------------
# Ticket 68A — Bloqueio do Cenário B (par incompleto)
# ---------------------------------------------------------------------------


def test_68a_cert_sem_assinatura_retorna_422(client_com_db_68):
    """cert_pem sem assinatura_b64 → 422 antes de qualquer persistência."""
    client, _ = client_com_db_68
    key = _gen_key()
    cert = _make_cert(key)
    pem = _to_pem(cert)
    resp = client.post("/prescricoes", json={**_PAYLOAD_API_PADRAO, "cert_pem": pem})
    assert resp.status_code == 422
    detail = resp.json().get("detail", "")
    assert "Assinatura" in detail or "assinatura" in detail.lower() or "inconsistente" in detail


def test_68a_assinatura_sem_cert_retorna_422(client_com_db_68):
    """assinatura_b64 sem cert_pem → 422 antes de qualquer persistência."""
    client, _ = client_com_db_68
    resp = client.post("/prescricoes", json={
        **_PAYLOAD_API_PADRAO,
        "assinatura_b64": base64.b64encode(b"sig_qualquer").decode(),
    })
    assert resp.status_code == 422


def test_68a_ambos_presentes_segue_fluxo(client_com_db_68):
    """cert_pem + assinatura_b64 (válidos) → fluxo digital normal (201 ou 422 de assinatura)."""
    client, _ = client_com_db_68
    key = _gen_key()
    cert = _make_cert(key)
    pem = _to_pem(cert)
    # Payload canônico igual ao que o router usa
    dados_canonicos = {
        "cns_prescritor": "706108587809760",
        "cpf_paciente": "12345678901",
        "tipo_emissao": "nova",
        "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
                   "quantidade": 10, "unidade_quantidade": None, "posologia": "1 cap 3x ao dia"}],
    }
    sig = _assinar(key, dados_canonicos)
    resp = client.post("/prescricoes", json={**_PAYLOAD_API_PADRAO, "cert_pem": pem, "assinatura_b64": sig})
    # 201 = digital válido; 422 de assinatura seria bug — mas nunca deve ser "par incompleto"
    assert resp.status_code == 201
    assert resp.json().get("assinatura_valida") is True


def test_68a_nenhum_fluxo_fisico_preservado(client_com_db_68):
    """Sem cert_pem e sem assinatura_b64 → fluxo físico normal (201)."""
    client, _ = client_com_db_68
    resp = client.post("/prescricoes", json=_PAYLOAD_API_PADRAO)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("string_validacao_prescritor") is None
    assert not data.get("assinatura_valida")
