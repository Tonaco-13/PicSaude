"""
certificado_teste.py
====================
Geradores de certificados ICP-Brasil-like para testes — Ticket 21.

Os certificados aqui produzidos são autoassinados e SIMULAM a estrutura
ICP-Brasil para fins de teste:
  - Nome no CN no formato "FABIANO TESTE:CPF"
  - OID 2.16.76.1.3.1 com payload Pessoa Física DOC-ICP-04.4
  - KeyUsage.digitalSignature opcional (parametrizável)
  - Validade configurável (para testar certificado expirado)

NÃO usar em produção. Não é encadeado a uma AC raiz real ICP-Brasil.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


# OID ICP-Brasil Pessoa Física (DOC-ICP-04.4)
_OID_ICP_PESSOA_FISICA = x509.ObjectIdentifier("2.16.76.1.3.1")


@dataclass
class CertificadoTeste:
    pfx_bytes:       bytes
    senha:           str
    cert_pem:        bytes
    cpf:             str
    nome:            str
    serial:          int
    valido_de:       datetime.datetime
    valido_ate:      datetime.datetime


def gerar_certificado_teste(
    *,
    nome: str = "FABIANO TESTE BORGES",
    cpf: str = "00000000191",   # CPF de teste (Receita Federal — sentinela)
    senha: str = "teste123",
    validade_dias: int = 365,
    com_keyusage_digital_signature: bool = True,
    valido_de: datetime.datetime | None = None,
) -> CertificadoTeste:
    """Gera certificado autoassinado simulando ICP-Brasil A1.

    O certificado tem:
      - CN no formato Serpro: "{nome}:{cpf}"
      - SAN com OID 2.16.76.1.3.1 contendo CPF na posição 9–19
      - KeyUsage.digitalSignature por default (parametrizável p/ teste de bloqueio)
    """
    if valido_de is None:
        valido_de = datetime.datetime.now(datetime.timezone.utc)
    valido_ate = valido_de + datetime.timedelta(days=validade_dias)

    # 1. Chave RSA 2048 (compatível com pyHanko)
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # 2. Subject + Issuer (autoassinado)
    nome_cn = f"{nome}:{cpf}"
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "AC TESTE PICSAUDE"),
        x509.NameAttribute(NameOID.COMMON_NAME, nome_cn),
    ])

    # 3. Payload do OID 2.16.76.1.3.1 (DOC-ICP-04.4 Pessoa Física)
    #    Posição  0-7  : DDMMAAAA → "01011980"
    #    Posição  8    : E (tipo de documento)
    #    Posição  9-19 : CPF sem pontuação (11 chars)
    #    Posição 20-30 : NIS (11 zeros)
    #    Posição 31-45 : RG (15 chars com espaços à direita)
    #    Posição 46-51 : Órgão emissor (6 chars com espaços)
    payload_pf = (
        "01011980" + "E" + cpf + "0" * 11 +
        "000000000000000" + "ZZZZZZ"
    )
    # Codificação ASN.1 PrintableString do payload — pyHanko/cryptography
    # aceita OtherName com bytes. Usamos a representação DER mínima.
    payload_der = b"\x13" + bytes([len(payload_pf)]) + payload_pf.encode("ascii")

    san = x509.SubjectAlternativeName([
        x509.OtherName(_OID_ICP_PESSOA_FISICA, payload_der),
    ])

    # 4. Builder
    serial = x509.random_serial_number()
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(chave.public_key())
        .serial_number(serial)
        .not_valid_before(valido_de.replace(tzinfo=None))
        .not_valid_after(valido_ate.replace(tzinfo=None))
        .add_extension(san, critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
    )

    if com_keyusage_digital_signature:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    else:
        # Cert sem digitalSignature — usado para testar rejeição.
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

    cert = builder.sign(chave, hashes.SHA256())

    # 5. Empacotar como .pfx/.p12
    pfx = pkcs12.serialize_key_and_certificates(
        name=b"teste-picsaude",
        key=chave,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode("utf-8")),
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    return CertificadoTeste(
        pfx_bytes=pfx,
        senha=senha,
        cert_pem=cert_pem,
        cpf=cpf,
        nome=nome,
        serial=serial,
        valido_de=valido_de,
        valido_ate=valido_ate,
    )
