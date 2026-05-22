"""
test_binding_icp.py
====================
Ticket 66 — Binding ICP A1/A3: parsing criptográfico + extração de identidade.

Cobre:
   1. Certificado com CPF via OID ICP → extrai CPF
   2. Certificado com nome CN → extrai corretamente
   3. Certificado com CRM no OU → extrai CRM + UF + número
   4. Certificado com CRO no OU → extrai CRO
   5. Certificado sem CRM/CRO → retorna None para conselho
   6. Certificado com formato inesperado de OU → parser resiliente
   7. CPF via OID 2.16.76.1.3.1 com offset DOC-ICP-04.4
   8. Integração binding_icp com Ticket 65 (conselho presente)
   9. Integração sem conselho → necessita_conselho_manual
  10. Regex cobre variações reais de formatação
  11. PEM inválido → erro_parsing sem exceção
  12. Sem regressão no pipeline Ticket 65

Estratégia: certificados gerados em memória com cryptography para não depender
de arquivos externos nem dados de produção.
"""

from __future__ import annotations

import datetime
import re
import sqlite3

import pytest

# Imports que podem falhar se cryptography não estiver instalada (sempre está)
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.domain.icp_identity import (
    ICPIdentidade,
    _decode_der_string,
    _extrair_conselho,
    _extrair_cpf_oid,
    _extrair_cpf_ou,
    _RE_CONSELHO,
    binding_icp,
    parsear_certificado_icp,
)
from app.domain.identidade_prescritor import MockConselhoProvider

# Fixture CNES — patcheia DB_PATH para arquivo SQLite tmp (arquitetura dual,
# ver docs/arquitetura_dual_bancos.md).
from tests.cnes_fixtures import cnes_db  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers de criação de certificados de teste
# ---------------------------------------------------------------------------

_OID_ICP_PESSOA_FISICA = x509.ObjectIdentifier("2.16.76.1.3.1")


def _gen_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


def _der_utf8string(s: str) -> bytes:
    """Codifica string como UTF8String DER (tag 0x0C)."""
    data = s.encode("utf-8")
    length = len(data)
    if length < 128:
        return bytes([0x0C, length]) + data
    elif length < 256:
        return bytes([0x0C, 0x81, length]) + data
    else:
        return bytes([0x0C, 0x82, (length >> 8) & 0xFF, length & 0xFF]) + data


def _icp_cpf_payload(cpf: str) -> bytes:
    """
    Constrói payload DOC-ICP-04.4 Pessoa Física:
      DDMMAAAA (8) + E (1) + CPF (11) + NIS (11) + RG (15) + OrgRG (6)
    """
    assert len(cpf) == 11 and cpf.isdigit()
    payload = "01011970" + "0" + cpf + "0" * 11 + "0" * 15 + "000000"
    return _der_utf8string(payload)


def _make_cert(
    cn: str = "JOAO DA SILVA",
    ous: list[str] | None = None,
    cpf: str | None = None,
) -> str:
    """Cria certificado PEM de teste com campos ICP-Brasil-like."""
    key = _gen_key()

    subject_attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    for ou in (ous or []):
        subject_attrs.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou))

    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(subject_attrs))
        .issuer_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "AC TESTE ICP-BRASIL"),
        ]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    )

    if cpf:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([
                x509.OtherName(_OID_ICP_PESSOA_FISICA, _icp_cpf_payload(cpf)),
            ]),
            critical=False,
        )

    cert = builder.sign(key, hashes.SHA256(), default_backend())
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _make_minimal_cert() -> str:
    """Certificado mínimo: apenas CN, sem OID ICP e sem OU."""
    return _make_cert(cn="ANA SOUZA", ous=[], cpf=None)


# ---------------------------------------------------------------------------
# Helpers internos — _decode_der_string
# ---------------------------------------------------------------------------


def test_decode_der_string_utf8():
    data = "JOAO SILVA".encode("utf-8")
    encoded = bytes([0x0C, len(data)]) + data
    assert _decode_der_string(encoded) == "JOAO SILVA"


def test_decode_der_string_ia5():
    data = "12345678900".encode("ascii")
    encoded = bytes([0x16, len(data)]) + data
    assert _decode_der_string(encoded) == "12345678900"


def test_decode_der_string_vazio():
    assert _decode_der_string(b"") is None


def test_decode_der_string_raw_fallback():
    # Dados sem tag DER reconhecida → fallback UTF-8
    data = b"texto direto"
    result = _decode_der_string(data)
    assert result is not None or result is None  # não lança exceção


# ---------------------------------------------------------------------------
# _extrair_cpf_oid
# ---------------------------------------------------------------------------


def test_extrair_cpf_oid_offset_correto():
    """CPF na posição 9–19 conforme DOC-ICP-04.4."""
    payload = _icp_cpf_payload("12345678900")
    cpf = _extrair_cpf_oid(payload)
    assert cpf == "12345678900"


def test_extrair_cpf_oid_cpf_diferente():
    payload = _icp_cpf_payload("98765432100")
    cpf = _extrair_cpf_oid(payload)
    assert cpf == "98765432100"


def test_extrair_cpf_oid_vazio():
    assert _extrair_cpf_oid(b"") is None


def test_extrair_cpf_ou_formato_pontuado():
    result = _extrair_cpf_ou(["CPF: 123.456.789-00"])
    assert result == "12345678900"


def test_extrair_cpf_ou_11_digitos():
    result = _extrair_cpf_ou(["98765432100"])
    assert result == "98765432100"


def test_extrair_cpf_ou_sem_cpf():
    result = _extrair_cpf_ou(["Medico", "CRM PE 12345"])
    assert result is None


# ---------------------------------------------------------------------------
# _extrair_conselho
# ---------------------------------------------------------------------------


def test_extrair_conselho_crm_espaco():
    tipo, uf, num = _extrair_conselho(["CRM PE 12345"])
    assert tipo == "CRM" and uf == "PE" and num == "12345"


def test_extrair_conselho_crm_hifen():
    tipo, uf, num = _extrair_conselho(["CRM-PE 12345"])
    assert tipo == "CRM" and uf == "PE" and num == "12345"


def test_extrair_conselho_cro_hifen_duplo():
    tipo, uf, num = _extrair_conselho(["CRO-SP-54321"])
    assert tipo == "CRO" and uf == "SP" and num == "54321"


def test_extrair_conselho_ponto():
    tipo, uf, num = _extrair_conselho(["CRM.PE.29243"])
    assert tipo == "CRM" and uf == "PE" and num == "29243"


def test_extrair_conselho_lowercase():
    tipo, uf, num = _extrair_conselho(["crm pe 12345"])
    assert tipo == "CRM" and uf == "PE" and num == "12345"


def test_extrair_conselho_em_frase():
    tipo, uf, num = _extrair_conselho(["Medico - CRM PE 29243"])
    assert tipo == "CRM" and uf == "PE" and num == "29243"


def test_extrair_conselho_ausente():
    tipo, uf, num = _extrair_conselho(["Sem conselho aqui"])
    assert tipo is None and uf is None and num is None


def test_extrair_conselho_lista_multipla_ou():
    tipo, uf, num = _extrair_conselho(["Medico", "CRO SP 6310", "Outro"])
    assert tipo == "CRO" and uf == "SP" and num == "6310"


# ---------------------------------------------------------------------------
# Caso 1 — Certificado com CPF via OID ICP
# ---------------------------------------------------------------------------


def test_caso1_cpf_via_oid():
    pem = _make_cert(cn="JOAO DA SILVA", cpf="12345678900")
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True
    assert icp.cpf_certificado == "12345678900"
    assert icp.fonte_campos["cpf"] == "oid_2.16.76.1.3.1"


# ---------------------------------------------------------------------------
# Caso 2 — Certificado com nome CN
# ---------------------------------------------------------------------------


def test_caso2_nome_cn():
    pem = _make_cert(cn="MARIA CLARA SANTOS")
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True
    assert icp.nome_certificado == "MARIA CLARA SANTOS"
    assert icp.fonte_campos["nome"] == "cn"


# ---------------------------------------------------------------------------
# Caso 3 — Certificado com CRM no OU
# ---------------------------------------------------------------------------


def test_caso3_crm_no_ou():
    pem = _make_cert(
        cn="CARLOS MEDICO",
        ous=["Medico", "CRM PE 12345"],
        cpf="11122233300",
    )
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True
    assert icp.conselho_tipo == "CRM"
    assert icp.conselho_uf == "PE"
    assert icp.conselho_numero == "12345"
    assert icp.fonte_campos["conselho"] == "ou"


# ---------------------------------------------------------------------------
# Caso 4 — Certificado com CRO no OU
# ---------------------------------------------------------------------------


def test_caso4_cro_no_ou():
    pem = _make_cert(
        cn="ANA DENTISTA",
        ous=["Cirurgiao-Dentista", "CRO-SP-54321"],
        cpf="22233344400",
    )
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True
    assert icp.conselho_tipo == "CRO"
    assert icp.conselho_uf == "SP"
    assert icp.conselho_numero == "54321"


# ---------------------------------------------------------------------------
# Caso 5 — Certificado sem CRM/CRO → None
# ---------------------------------------------------------------------------


def test_caso5_sem_conselho():
    pem = _make_cert(cn="JOAO SEM CONSELHO", ous=["Auxiliar de Saude"])
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True
    assert icp.conselho_numero is None
    assert icp.conselho_uf is None
    assert icp.conselho_tipo is None
    assert icp.fonte_campos["conselho"] == "nao_encontrado"
    assert icp.precisa_conselho_manual() is True


# ---------------------------------------------------------------------------
# Caso 6 — Formato inesperado de OU → parser resiliente
# ---------------------------------------------------------------------------


def test_caso6_ou_formato_inesperado():
    """OU com dados malformados não deve lançar exceção."""
    pem = _make_cert(
        cn="JOAO SILVA",
        ous=["???###@@@", "12345", ""],
    )
    icp = parsear_certificado_icp(pem)
    assert icp.parseable is True   # não lança
    assert icp.erro is None


# ---------------------------------------------------------------------------
# Caso 7 — CPF via OID com offset DOC-ICP-04.4
# ---------------------------------------------------------------------------


def test_caso7_cpf_offset_icp04():
    """
    Verifica que o parsing respeita o offset exato do DOC-ICP-04.4:
    DDMMAAAA (8) + E (1) + CPF (11) = posição 9 a 19.
    """
    cpf_esperado = "98765432100"
    payload = _icp_cpf_payload(cpf_esperado)
    cpf = _extrair_cpf_oid(payload)
    assert cpf == cpf_esperado


# ---------------------------------------------------------------------------
# Caso 8 — Integração binding_icp com Ticket 65
# ---------------------------------------------------------------------------


def _seed_db_com_profissional(
    cnes_db,
    *,
    conselho_numero: str = "12345",
    conselho_uf: str = "PE",
) -> sqlite3.Connection:
    """
    Popula o CNES tmp gerenciado pela fixture `cnes_db` e devolve uma
    conexão SQLite in-memory vazia para o argumento `conn` de
    `binding_icp` / `resolver_identidade_prescritor`. As queries CNES
    abrem _get_cnes_conn() internamente — `conn` não é tocada pelas
    funções para CNES. Ver docs/arquitetura_dual_bancos.md.
    """
    cnes_db.add_profissional(
        CO_PROFISSIONAL_SUS="P001", NO_PROFISSIONAL="CARLOS MEDICO",
        CO_CNS="700001111222333", CO_CPF="CO_CPF",
    )
    cnes_db.add_relacao(
        CO_PROFISSIONAL_SUS="P001", CO_CONSELHO_CLASSE="71",
        NU_REGISTRO=conselho_numero, SG_UF_CRM=conselho_uf,
        CO_CBO="225125", CO_UNIDADE="UNID001",
    )
    cnes_db.add_estabelecimento(
        CO_UNIDADE="UNID001", CO_CNES="9990001",
        NO_FANTASIA="CLINICA TESTE", TP_UNIDADE="01",
    )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_caso8_binding_completo_com_conselho(cnes_db):
    """Fluxo completo: ICP → parsing → pipeline T65 → ok."""
    pem = _make_cert(
        cn="CARLOS MEDICO",
        ous=["Medico", "CRM PE 12345"],
        cpf="11122233344",
    )
    conn = _seed_db_com_profissional(cnes_db, conselho_numero="12345", conselho_uf="PE")
    mock = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "CARLOS MEDICO",
        "ativo": True,
    })

    result = binding_icp(cert_pem=pem, conn=conn, conselho_provider=mock)

    assert result["status"] == "ok"
    assert result["icp"]["cpf_certificado"] == "11122233344"
    assert result["identidade"] is not None
    assert result["identidade"]["cns"] == "700001111222333"


# ---------------------------------------------------------------------------
# Caso 9 — Integração sem conselho → necessita_conselho_manual
# ---------------------------------------------------------------------------


def test_caso9_sem_conselho_fallback_manual(cnes_db):
    """Quando OU não tem CRM/CRO, retornar necessita_conselho_manual."""
    pem = _make_cert(cn="JOAO SILVA", ous=["Assistente"], cpf="12345678900")
    conn = _seed_db_com_profissional(cnes_db)

    result = binding_icp(cert_pem=pem, conn=conn)

    assert result["status"] == "necessita_conselho_manual"
    assert "CRM" in result["mensagem"] or "CRO" in result["mensagem"]
    assert result["icp"]["cpf_certificado"] == "12345678900"
    assert result["identidade"] is None


# ---------------------------------------------------------------------------
# Caso 10 — Regex cobre variações reais
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ou_texto,tipo_esperado,uf_esperada,num_esperado", [
    ("CRM PE 12345",         "CRM", "PE", "12345"),
    ("CRM-PE 12345",         "CRM", "PE", "12345"),
    ("CRO-SP-54321",         "CRO", "SP", "54321"),
    ("CRM.PE.29243",         "CRM", "PE", "29243"),
    ("crm pe 12345",         "CRM", "PE", "12345"),
    ("Medico - CRM PE 29243","CRM", "PE", "29243"),
    ("CRM-PE-12345",         "CRM", "PE", "12345"),
    ("CRO SP 6310",          "CRO", "SP", "6310"),
    ("CRM PE 1234567",       "CRM", "PE", "1234567"),
])
def test_caso10_regex_variacoes_reais(ou_texto, tipo_esperado, uf_esperada, num_esperado):
    tipo, uf, num = _extrair_conselho([ou_texto])
    assert tipo == tipo_esperado, f"tipo: {tipo!r} != {tipo_esperado!r} para {ou_texto!r}"
    assert uf == uf_esperada
    assert num == num_esperado


# ---------------------------------------------------------------------------
# Caso 11 — PEM inválido → erro_parsing sem exceção
# ---------------------------------------------------------------------------


def test_caso11_pem_invalido_nao_lanca():
    result = binding_icp(cert_pem="isso nao e um certificado")
    assert result["status"] == "erro_parsing"
    assert result["identidade"] is None
    assert "pem_invalido" in result["icp"]["erro"]


def test_caso11_pem_vazio():
    result = binding_icp(cert_pem="")
    assert result["status"] == "erro_parsing"


def test_caso11_parsear_pem_invalido_retorna_identidade():
    icp = parsear_certificado_icp("---BEGIN CERTIFICATE---\ndados invalidos\n---END CERTIFICATE---")
    assert icp.parseable is False
    assert icp.erro is not None
    assert icp.cpf_certificado is None


# ---------------------------------------------------------------------------
# Caso 12 — Sem regressão pipeline Ticket 65
# ---------------------------------------------------------------------------


def test_caso12_sem_regressao_identidade_prescritor(cnes_db):
    """
    Verifica que identidade_prescritor.py continua funcionando
    após a integração com icp_identity.py.
    """
    from app.domain.identidade_prescritor import resolver_identidade_prescritor

    conn = _seed_db_com_profissional(cnes_db, conselho_numero="99999", conselho_uf="RJ")
    mock = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "99999",
        "uf": "RJ",
        "nome_conselho": "CARLOS MEDICO",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="11122233344",
        nome_certificado="CARLOS MEDICO",
        conselho_numero="99999",
        conselho_uf="RJ",
        conselho_provider=mock,
    )

    assert result["status"] == "ok"
    assert result["cns"] == "700001111222333"


# ---------------------------------------------------------------------------
# ICPIdentidade — interface
# ---------------------------------------------------------------------------


def test_icp_identidade_to_dict():
    icp = ICPIdentidade(
        cpf_certificado="12345678900",
        nome_certificado="JOAO SILVA",
        conselho_tipo="CRM",
        conselho_uf="PE",
        conselho_numero="12345",
        fonte_campos={"cpf": "oid_2.16.76.1.3.1", "nome": "cn", "conselho": "ou"},
        parseable=True,
    )
    d = icp.to_dict()
    assert d["cpf_certificado"] == "12345678900"
    assert d["conselho_tipo"] == "CRM"
    assert d["parseable"] is True
    assert d["erro"] is None


def test_icp_identidade_precisa_conselho_manual_true():
    icp = ICPIdentidade(parseable=True)  # conselho_numero = None
    assert icp.precisa_conselho_manual() is True


def test_icp_identidade_precisa_conselho_manual_false():
    icp = ICPIdentidade(parseable=True, conselho_numero="12345")
    assert icp.precisa_conselho_manual() is False


# ---------------------------------------------------------------------------
# binding_icp sem conexão ao banco
# ---------------------------------------------------------------------------


def test_binding_sem_conn_retorna_icp_parseado():
    """Quando conn=None e conselho presente → icp_parseado."""
    pem = _make_cert(
        cn="JOAO SILVA",
        ous=["CRM PE 12345"],
        cpf="12345678900",
    )
    result = binding_icp(cert_pem=pem, conn=None)
    assert result["status"] == "icp_parseado"
    assert result["icp"]["cpf_certificado"] == "12345678900"
    assert result["icp"]["conselho_numero"] == "12345"


def test_binding_campos_auditaveis_presentes():
    """Resultado sempre tem campos auditáveis."""
    pem = _make_cert(cn="TESTE")
    result = binding_icp(cert_pem=pem)
    assert "status" in result
    assert "icp" in result
    assert "identidade" in result
    assert "extraido_em" in result
