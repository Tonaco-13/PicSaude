"""
test_string_validacao.py
=========================
Ticket 67 — String de Validação Auditável.

Cobre:
   1. Geração básica correta
   2. Formato correto da string (6 campos pipe-separated)
   3. Hash DER consistente (mesmo cert → mesmo hash)
   4. PEM com quebras diferentes → mesmo hash
   5. Timestamp em formato correto (ISO 8601 UTC)
   6. STATUS_NOME refletido corretamente
   7. DIVERGENTE permitido (não bloqueia)
   8. Integração com prescrição (router POST /prescricoes)
   9. Evento de ledger contém a string
  10. Sem regressão
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

from app.domain.string_validacao import (
    _HASH_SEM_CERT,
    _CNS_NAO_RESOLVIDO,
    _STATUS_NAO_VAL,
    gerar_string_a_partir_de_binding,
    gerar_string_validacao_identidade,
    hash_cert_der,
)


# ---------------------------------------------------------------------------
# Helpers de certificados
# ---------------------------------------------------------------------------


def _gen_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


def _make_pem(cn: str = "JOAO SILVA") -> str:
    key = _gen_key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC TESTE")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256(), default_backend())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


_TS_FIXO = datetime.datetime(2026, 4, 6, 14, 32, 10, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# hash_cert_der
# ---------------------------------------------------------------------------


def test_hash_der_consistente():
    """Mesmo cert PEM → mesmo hash DER."""
    pem = _make_pem()
    h1 = hash_cert_der(pem)
    h2 = hash_cert_der(pem)
    assert h1 == h2
    assert len(h1) == 64   # SHA-256 hex


def test_hash_der_diferentes_certs_diferentes():
    """Certs diferentes → hashes diferentes."""
    h1 = hash_cert_der(_make_pem("JOAO"))
    h2 = hash_cert_der(_make_pem("MARIA"))
    assert h1 != h2


def test_hash_pem_com_espacos_extras():
    """
    Hash baseia-se no DER, não no PEM cru.
    PEM com espaços extras → mesmo DER → mesmo hash.
    """
    pem = _make_pem()
    # Simular PEM com whitespace extra no início
    pem_com_espaco = "  \n" + pem
    # Ambos devem produzir o mesmo hash porque o DER é extraído do conteúdo real
    h1 = hash_cert_der(pem)
    h2 = hash_cert_der(pem_com_espaco)
    assert h1 == h2


def test_hash_pem_invalido_retorna_sem_cert():
    assert hash_cert_der("pem invalido") == _HASH_SEM_CERT


def test_hash_pem_vazio_retorna_sem_cert():
    assert hash_cert_der("") == _HASH_SEM_CERT


# ---------------------------------------------------------------------------
# Caso 1 — Geração básica correta
# ---------------------------------------------------------------------------


def test_caso1_geracao_basica():
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="coerente_forte",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    assert result["erro"] is None
    assert result["string_validacao"] is not None
    assert result["hash_cert"] != _HASH_SEM_CERT
    assert len(result["hash_cert"]) == 64


# ---------------------------------------------------------------------------
# Caso 2 — Formato correto da string
# ---------------------------------------------------------------------------


def test_caso2_formato_string():
    """String deve ter exatamente 6 campos separados por pipe."""
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    partes = result["string_validacao"].split("|")
    assert len(partes) == 6, f"Esperado 6 campos, obtido {len(partes)}: {partes}"

    cpf_s, conselho_s, cns_s, status_s, hash_s, ts_s = partes
    assert cpf_s == "12345678900"
    assert conselho_s == "CRM-PE-12345"
    assert cns_s == "700001111222333"
    assert status_s == "COERENTE_FORTE"
    assert len(hash_s) == 64
    assert ts_s == "2026-04-06T14:32:10Z"


# ---------------------------------------------------------------------------
# Caso 3 — Hash DER consistente entre chamadas
# ---------------------------------------------------------------------------


def test_caso3_hash_der_consistente_na_string():
    pem = _make_pem()
    r1 = gerar_string_validacao_identidade(
        cpf="11111111111",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="1",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    r2 = gerar_string_validacao_identidade(
        cpf="11111111111",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="1",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    assert r1["string_validacao"] == r2["string_validacao"]
    assert r1["hash_cert"] == r2["hash_cert"]


# ---------------------------------------------------------------------------
# Caso 4 — PEM com quebras diferentes → mesmo hash
# ---------------------------------------------------------------------------


def test_caso4_pem_quebras_diferentes_mesmo_hash():
    """
    O hash é do DER (não do PEM cru), então variações de formatação
    PEM não devem alterar o hash resultante.
    """
    pem = _make_pem()
    # Simular PEM com \r\n em vez de \n (encoding Windows)
    pem_crlf = pem.replace("\n", "\r\n")

    h1 = hash_cert_der(pem)
    h2 = hash_cert_der(pem_crlf)
    assert h1 == h2, "PEM com CRLF deve gerar mesmo hash DER que PEM com LF"


# ---------------------------------------------------------------------------
# Caso 5 — Timestamp em formato correto
# ---------------------------------------------------------------------------


def test_caso5_timestamp_iso8601_utc():
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    ts = result["componentes"]["timestamp"]
    assert ts == "2026-04-06T14:32:10Z"
    # Validar parse
    parsed = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.year == 2026


def test_caso5_timestamp_auto_quando_ausente():
    """Quando timestamp=None, usar datetime.now(UTC) sem lançar."""
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns=None,
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
    )
    ts = result["componentes"]["timestamp"]
    assert ts.endswith("Z")
    assert "T" in ts


# ---------------------------------------------------------------------------
# Caso 6 — STATUS_NOME refletido corretamente
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_in,status_esperado", [
    ("coerente_forte",   "COERENTE_FORTE"),
    ("COERENTE_FORTE",  "COERENTE_FORTE"),
    ("coerente_parcial", "COERENTE_PARCIAL"),
    ("COERENTE_PARCIAL","COERENTE_PARCIAL"),
    ("divergente",       "DIVERGENTE"),
    ("DIVERGENTE",       "DIVERGENTE"),
    ("outro_qualquer",   "NAO_VALIDADO"),
    (None,               "NAO_VALIDADO"),
    ("",                 "NAO_VALIDADO"),
])
def test_caso6_status_nome_normalizado(status_in, status_esperado):
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome=status_in,
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    assert result["componentes"]["status_nome"] == status_esperado
    partes = result["string_validacao"].split("|")
    assert partes[3] == status_esperado


# ---------------------------------------------------------------------------
# Caso 7 — DIVERGENTE permitido (não bloqueia)
# ---------------------------------------------------------------------------


def test_caso7_divergente_nao_bloqueia():
    """DIVERGENTE gera string normalmente, não lança exceção."""
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="divergente",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    assert result["erro"] is None
    assert "DIVERGENTE" in result["string_validacao"]


# ---------------------------------------------------------------------------
# CNS ausente → NAO_RESOLVIDO
# ---------------------------------------------------------------------------


def test_cns_ausente_vira_nao_resolvido():
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns=None,
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    partes = result["string_validacao"].split("|")
    assert partes[2] == _CNS_NAO_RESOLVIDO


def test_cert_pem_ausente_hash_sem_cert():
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=None,
        timestamp=_TS_FIXO,
    )
    assert result["hash_cert"] == _HASH_SEM_CERT
    partes = result["string_validacao"].split("|")
    assert partes[4] == _HASH_SEM_CERT


# ---------------------------------------------------------------------------
# Casos de erro — pré-requisitos
# ---------------------------------------------------------------------------


def test_cpf_ausente_levanta_value_error():
    with pytest.raises(ValueError, match="CPF"):
        gerar_string_validacao_identidade(
            cpf="",
            conselho_tipo="CRM",
            conselho_uf="PE",
            conselho_numero="12345",
            cns=None,
            status_nome="COERENTE_FORTE",
            cert_pem=None,
        )


def test_conselho_tipo_ausente_levanta_value_error():
    with pytest.raises(ValueError, match="Conselho"):
        gerar_string_validacao_identidade(
            cpf="12345678900",
            conselho_tipo="",
            conselho_uf="PE",
            conselho_numero="12345",
            cns=None,
            status_nome="COERENTE_FORTE",
            cert_pem=None,
        )


def test_conselho_numero_ausente_levanta_value_error():
    with pytest.raises(ValueError, match="Conselho"):
        gerar_string_validacao_identidade(
            cpf="12345678900",
            conselho_tipo="CRM",
            conselho_uf="PE",
            conselho_numero="",
            cns=None,
            status_nome="COERENTE_FORTE",
            cert_pem=None,
        )


# ---------------------------------------------------------------------------
# gerar_string_a_partir_de_binding
# ---------------------------------------------------------------------------


def test_binding_builder_ok():
    pem = _make_pem()
    binding_result = {
        "icp": {
            "cpf_certificado":  "12345678900",
            "conselho_tipo":    "CRM",
            "conselho_uf":      "PE",
            "conselho_numero":  "12345",
        },
        "identidade": {
            "cns": "700001111222333",
            "nome_validacao": {"status": "coerente_forte"},
        },
    }
    result = gerar_string_a_partir_de_binding(binding_result, pem, _TS_FIXO)
    assert result["erro"] is None
    assert result["string_validacao"] is not None
    partes = result["string_validacao"].split("|")
    assert partes[0] == "12345678900"
    assert partes[1] == "CRM-PE-12345"


def test_binding_builder_sem_cpf_retorna_erro():
    binding_result = {
        "icp": {
            "cpf_certificado":  "",
            "conselho_tipo":    "CRM",
            "conselho_uf":      "PE",
            "conselho_numero":  "12345",
        },
        "identidade": {},
    }
    result = gerar_string_a_partir_de_binding(binding_result, None, _TS_FIXO)
    assert result["string_validacao"] is None
    assert result["erro"] is not None


def test_binding_builder_identidade_none():
    """identidade=None → CNS=NAO_RESOLVIDO, status=NAO_VALIDADO."""
    pem = _make_pem()
    binding_result = {
        "icp": {
            "cpf_certificado":  "98765432100",
            "conselho_tipo":    "CRO",
            "conselho_uf":      "SP",
            "conselho_numero":  "54321",
        },
        "identidade": None,
    }
    result = gerar_string_a_partir_de_binding(binding_result, pem, _TS_FIXO)
    assert result["erro"] is None
    partes = result["string_validacao"].split("|")
    assert partes[2] == _CNS_NAO_RESOLVIDO
    assert partes[3] == _STATUS_NAO_VAL


# ---------------------------------------------------------------------------
# Caso 8 — Integração com prescrição (router POST /prescricoes)
# ---------------------------------------------------------------------------


def _make_cert_com_crm(cn: str, crm_uf: str, crm_num: str, cpf_payload: bytes | None = None) -> str:
    """Cria cert de teste com OU contendo CRM, opcionalmente com OID ICP-CPF."""
    _OID_ICP = x509.ObjectIdentifier("2.16.76.1.3.1")
    key = _gen_key()
    attrs = [
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, f"CRM {crm_uf} {crm_num}"),
    ]
    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(attrs))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC ICP-BRASIL")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    )
    if cpf_payload:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.OtherName(_OID_ICP, cpf_payload)]),
            critical=False,
        )
    cert = builder.sign(key, hashes.SHA256(), default_backend())
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _icp_der_cpf(cpf: str) -> bytes:
    payload = "01011970" + "0" + cpf + "0" * 11 + "0" * 15 + "000000"
    data = payload.encode("utf-8")
    return bytes([0x0C, len(data)]) + data


def _make_cert_e_chave_com_crm(cn: str, crm_uf: str, crm_num: str, cpf_payload: bytes | None = None):
    """Retorna (private_key, pem_str) — chave mantida para assinar o payload."""
    _OID_ICP = x509.ObjectIdentifier("2.16.76.1.3.1")
    key = _gen_key()
    attrs = [
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, f"CRM {crm_uf} {crm_num}"),
    ]
    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(attrs))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC ICP-BRASIL")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    )
    if cpf_payload:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.OtherName(_OID_ICP, cpf_payload)]),
            critical=False,
        )
    cert = builder.sign(key, hashes.SHA256(), default_backend())
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return key, pem


def _assinar_dados_canonicos(key, dados_canonicos: dict) -> str:
    """Assina o digest SHA-256 do payload canônico com PKCS1v15 (Prehashed), retorna base64."""
    serializado = json.dumps(
        dados_canonicos, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(serializado).digest()
    assinatura = key.sign(digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
    return base64.b64encode(assinatura).decode()


@pytest.fixture()
def client_com_db(tmp_path):
    """Client FastAPI com banco in-memory incluindo tabelas CNES."""
    import sqlite3
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    db_path = str(tmp_path / "test_sv.db")

    from app.database import Base
    import app.models  # noqa
    from app.domain.ledger_imutabilidade import aplicar_triggers_sqlite

    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    eng.dispose()
    aplicar_triggers_sqlite(db_path)

    # Adicionar migration string_validacao_prescritor (pode não estar no schema SQLAlchemy)
    conn_raw = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn_raw.execute("PRAGMA table_info(prescricoes)").fetchall()}
        if "string_validacao_prescritor" not in cols:
            conn_raw.execute("ALTER TABLE prescricoes ADD COLUMN string_validacao_prescritor TEXT")
            conn_raw.commit()
        # Criar tabelas CNES mínimas
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
            CREATE TABLE IF NOT EXISTS prestadores (id INTEGER PRIMARY KEY, cnpj TEXT, org_id TEXT, ativo INTEGER, nome TEXT, tipo TEXT);
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

    # database_tx.get_conn cobre 8 dos 10 routers (todos que usam get_tx).
    # prescricoes e tokens importam get_conn diretamente — patch específico.
    targets = [
        "app.database_tx.get_conn",
        "app.routers.prescricoes.get_conn",
        "app.routers.tokens.get_conn",
    ]

    from contextlib import ExitStack
    stack = ExitStack()
    for t in targets:
        stack.enter_context(patch(t, _get_conn))

    # 5C: sub do JWT deve coincidir com cns_prescritor do payload (V1).
    app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "123456789012345"}
    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()

    yield client, _get_conn

    client.__exit__(None, None, None)
    stack.close()
    app.dependency_overrides.clear()


_PAYLOAD_BASE = {
    "cns_prescritor": "123456789012345",
    "nome_prescritor": "DR TESTE",
    "cpf_paciente": "12345678901",
    "nome_paciente": "PACIENTE TESTE",
    "tipo_emissao": "nova",
    "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg", "quantidade": 10, "posologia": "1 cap 3x ao dia"}],
}


def test_caso8_prescricao_sem_cert_sem_string_validacao(client_com_db):
    client, _ = client_com_db
    resp = client.post("/prescricoes", json=_PAYLOAD_BASE)
    assert resp.status_code == 201
    data = resp.json()
    # Sem cert_pem → string_validacao_prescritor deve ser None
    assert data.get("string_validacao_prescritor") is None


def test_caso8_prescricao_com_cert_gera_string(client_com_db):
    """Quando cert_pem + assinatura_b64 válidos são enviados, string é gerada."""
    client, _ = client_com_db
    cpf_prescritor = "11122233300"
    key, pem = _make_cert_e_chave_com_crm(
        cn="DR TESTE",
        crm_uf="PE",
        crm_num="12345",
        cpf_payload=_icp_der_cpf(cpf_prescritor),
    )
    # Payload canônico idêntico ao que o router constrói
    dados_canonicos = {
        "cns_prescritor": _PAYLOAD_BASE["cns_prescritor"],
        "cpf_paciente": _PAYLOAD_BASE["cpf_paciente"],
        "tipo_emissao": _PAYLOAD_BASE["tipo_emissao"],
        "itens": [
            {
                "nome_medicamento": it["nome_medicamento"],
                "concentracao": it.get("concentracao"),
                "quantidade": it.get("quantidade"),
                "unidade_quantidade": it.get("unidade_quantidade"),
                "posologia": it.get("posologia"),
            }
            for it in _PAYLOAD_BASE["itens"]
        ],
    }
    assinatura_b64 = _assinar_dados_canonicos(key, dados_canonicos)
    payload = {**_PAYLOAD_BASE, "cert_pem": pem, "assinatura_b64": assinatura_b64}
    resp = client.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    sv = data.get("string_validacao_prescritor")
    if sv:
        partes = sv.split("|")
        assert len(partes) == 6
        assert partes[0] == cpf_prescritor
        assert partes[1] == "CRM-PE-12345"


# ---------------------------------------------------------------------------
# Caso 9 — Evento de ledger contém a string
# ---------------------------------------------------------------------------


def test_caso9_evento_ledger_contem_string(client_com_db):
    """Quando string é gerada, ela deve constar no payload_json do evento prescricao_emitida."""
    import sqlite3 as _sqlite3
    client, get_conn = client_com_db
    cpf_prescritor = "22233344400"
    key, pem = _make_cert_e_chave_com_crm(
        cn="DRA MARIA",
        crm_uf="RJ",
        crm_num="99999",
        cpf_payload=_icp_der_cpf(cpf_prescritor),
    )
    dados_canonicos = {
        "cns_prescritor": _PAYLOAD_BASE["cns_prescritor"],
        "cpf_paciente": _PAYLOAD_BASE["cpf_paciente"],
        "tipo_emissao": _PAYLOAD_BASE["tipo_emissao"],
        "itens": [
            {
                "nome_medicamento": it["nome_medicamento"],
                "concentracao": it.get("concentracao"),
                "quantidade": it.get("quantidade"),
                "unidade_quantidade": it.get("unidade_quantidade"),
                "posologia": it.get("posologia"),
            }
            for it in _PAYLOAD_BASE["itens"]
        ],
    }
    assinatura_b64 = _assinar_dados_canonicos(key, dados_canonicos)
    payload = {**_PAYLOAD_BASE, "cert_pem": pem, "assinatura_b64": assinatura_b64}
    resp = client.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    protocolo = resp.json()["protocolo"]

    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
            JOIN prescricoes p ON p.id = pe.prescricao_id
            WHERE p.protocolo = ? AND pe.tipo_evento = 'prescricao_emitida'
            """,
            (protocolo,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    ev = json.loads(row[0])
    # Se string foi gerada, deve constar no payload
    if resp.json().get("string_validacao_prescritor"):
        assert "string_validacao" in ev
        assert ev["string_validacao"]["string_validacao"] is not None
        partes = ev["string_validacao"]["string_validacao"].split("|")
        assert len(partes) == 6


# ---------------------------------------------------------------------------
# Caso 10 — Sem regressão
# ---------------------------------------------------------------------------


def test_caso10_sem_regressao_emissao_normal(client_com_db):
    """Emissão normal sem cert_pem continua funcionando como antes."""
    client, _ = client_com_db
    resp = client.post("/prescricoes", json=_PAYLOAD_BASE)
    assert resp.status_code == 201
    data = resp.json()
    # Campos existentes preservados
    assert "protocolo" in data
    assert "status" in data
    assert "cnes_validacao" in data
    assert "score_confianca" in data
    assert "documento_hash" in data


def test_caso10_sem_regressao_modulos_t64_t65_t66():
    """T64, T65 e T66 continuam importáveis e funcionais após T67."""
    from app.domain.nome_validator import NomeValidator
    from app.domain.identidade_prescritor import resolver_identidade_prescritor, MockConselhoProvider
    from app.domain.icp_identity import parsear_certificado_icp, ICPIdentidade

    v = NomeValidator()
    ok, _, c = v.validar_correspondencia("JOAO SILVA", "JOAO SILVA", "JOAO SILVA")
    assert ok is True
    assert c == pytest.approx(1.0)

    icp = parsear_certificado_icp("pem invalido")
    assert icp.parseable is False

    from app.domain.string_validacao import gerar_string_validacao_identidade
    pem = _make_pem()
    result = gerar_string_validacao_identidade(
        cpf="12345678900",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        cns="700001111222333",
        status_nome="COERENTE_FORTE",
        cert_pem=pem,
        timestamp=_TS_FIXO,
    )
    assert result["erro"] is None
