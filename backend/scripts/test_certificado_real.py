#!/usr/bin/env python3
"""
test_certificado_real.py
========================
Script de teste local para certificado ICP-Brasil A1 (.pfx/.p12).

Executa na máquina do prescritor — o certificado NUNCA sai do computador.

Uso:
    cd ~/Desktop/PicSaude_Dev/backend
    python scripts/test_certificado_real.py "../Certificação Digital Cerpro/173960303_FABI...3086439149.pfx"

(substitua o nome do arquivo pelo nome completo do .pfx)

O script vai pedir a senha do certificado no terminal.
"""
from __future__ import annotations

import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ajusta path para importar módulos do PicSaúde
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_certificado_real.py <caminho_do_pfx>")
        print('Ex.:  python scripts/test_certificado_real.py "../Certificação Digital Cerpro/SEU_ARQUIVO.pfx"')
        sys.exit(1)

    pfx_path = Path(sys.argv[1])
    if not pfx_path.exists():
        print(f"ERRO: Arquivo não encontrado: {pfx_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  PicSaúde — Teste de Certificado Digital ICP-Brasil A1")
    print(f"{'='*60}")
    print(f"\nArquivo: {pfx_path.name}")
    print(f"Tamanho: {pfx_path.stat().st_size:,} bytes")

    # 1. Pedir senha
    senha = getpass.getpass("\nDigite a senha do certificado: ")

    # 2. Carregar o .pfx
    print("\n[1/6] Carregando certificado .pfx ...")
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
        from cryptography.hazmat.primitives.serialization import (
            BestAvailableEncryption,
            NoEncryption,
        )
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography import x509
    except ImportError:
        print("ERRO: Biblioteca 'cryptography' não instalada.")
        print("Execute: pip install cryptography")
        sys.exit(1)

    try:
        pfx_data = pfx_path.read_bytes()
        private_key, certificate, cas = pkcs12.load_key_and_certificates(
            pfx_data, senha.encode("utf-8")
        )
    except Exception as e:
        print(f"ERRO ao carregar .pfx: {e}")
        print("Verifique se a senha está correta.")
        sys.exit(1)

    print("  ✓ Certificado carregado com sucesso!")
    print(f"  ✓ Chave privada: {'presente' if private_key else 'AUSENTE'}")
    print(f"  ✓ Certificados CA na cadeia: {len(cas) if cas else 0}")

    # 3. Extrair PEM do certificado
    print("\n[2/6] Extraindo certificado X.509 (PEM) ...")
    cert_pem = certificate.public_bytes(Encoding.PEM).decode("utf-8")
    print(f"  ✓ PEM extraído ({len(cert_pem)} caracteres)")

    # Informações básicas do certificado
    print(f"\n  Subject:    {certificate.subject.rfc4514_string()}")
    print(f"  Issuer:     {certificate.issuer.rfc4514_string()}")
    print(f"  Serial:     {certificate.serial_number}")
    print(f"  Válido de:  {certificate.not_valid_before_utc}")
    print(f"  Válido até: {certificate.not_valid_after_utc}")

    agora = datetime.now(timezone.utc)
    if certificate.not_valid_before_utc <= agora <= certificate.not_valid_after_utc:
        print("  ✓ Certificado dentro do prazo de validade")
    else:
        print("  ⚠ CERTIFICADO FORA DO PRAZO DE VALIDADE")

    # 4. Testar parsear_certificado_icp (extração de identidade)
    print("\n[3/6] Extraindo identidade ICP-Brasil ...")
    try:
        from app.domain.icp_identity import parsear_certificado_icp

        identidade = parsear_certificado_icp(cert_pem)
        print(f"  ✓ Parseável: {identidade.parseable}")
        print(f"  ✓ CPF:       {identidade.cpf_certificado or '(não encontrado)'}")
        print(f"  ✓ Nome:      {identidade.nome_certificado or '(não encontrado)'}")
        print(f"  ✓ Conselho:  {identidade.conselho_tipo or ''} {identidade.conselho_numero or '(não encontrado)'}")
        print(f"  ✓ UF:        {identidade.conselho_uf or '(não encontrado)'}")
        if identidade.erro:
            print(f"  ⚠ Erro:      {identidade.erro}")
        print(f"  ✓ Fontes:    {json.dumps(identidade.fonte_campos, indent=6, ensure_ascii=False)}")
    except Exception as e:
        print(f"  ⚠ Erro ao parsear identidade: {e}")
        identidade = None

    # 5. Criar payload canônico e assinar
    print("\n[4/6] Criando documento canônico de teste ...")
    from app.domain.documento_canonico import montar_documento

    # Extrair nome limpo (sem CPF após ":")
    nome_cert = "Dr. Teste"
    if identidade and identidade.nome_certificado:
        nome_cert = identidade.nome_certificado.split(":")[0].strip()

    itens_teste = [
        {
            "nome_medicamento": "Amoxicilina",
            "concentracao": "500mg",
            "quantidade": 21,
            "unidade_quantidade": "cápsula",
            "posologia": "1 cápsula de 8/8h por 7 dias",
        }
    ]

    try:
        resultado_doc = montar_documento(
            protocolo="TESTE-CERT-001",
            data_emissao=datetime.now().isoformat(),
            tipo_emissao="nova",
            assinatura_modo="icp_brasil_local",
            cns_prescritor="704815923061348",
            nome_prescritor=nome_cert,
            cpf_paciente="00000000000",
            nome_paciente="Paciente Teste",
            itens=itens_teste,
        )
        print(f"  ✓ Hash SHA-256: {resultado_doc.hash_sha256}")
        print(f"  ✓ Documento canônico ({len(resultado_doc.serializado)} bytes)")
    except Exception as e:
        print(f"  ⚠ Erro ao montar documento canônico: {e}")
        print("  Tentando com payload manual...")
        # Fallback: payload manual
        from app.domain.assinatura_icp import serializar_payload, calcular_digest
        payload_manual = {
            "protocolo": "TESTE-CERT-001",
            "prescritor": prescritor_teste,
            "paciente": paciente_teste,
            "itens": itens_teste,
        }
        serializado = serializar_payload(payload_manual)
        digest_hex = calcular_digest(payload_manual)
        resultado_doc = type("R", (), {
            "serializado": serializado,
            "hash_sha256": digest_hex,
        })()
        print(f"  ✓ Hash SHA-256 (manual): {resultado_doc.hash_sha256}")

    # 6. Assinar com a chave privada
    print("\n[5/6] Assinando payload com chave privada A1 ...")
    import base64
    from cryptography.hazmat.primitives.asymmetric import utils

    # O PicSaúde usa Prehashed(SHA256) + PKCS1v15 (compatível com WebCrypto)
    digest_bytes = bytes.fromhex(resultado_doc.hash_sha256)

    try:
        assinatura_bytes = private_key.sign(
            digest_bytes,
            padding.PKCS1v15(),
            utils.Prehashed(hashes.SHA256()),
        )
        assinatura_b64 = base64.b64encode(assinatura_bytes).decode("ascii")
        print(f"  ✓ Assinatura gerada ({len(assinatura_bytes)} bytes)")
        print(f"  ✓ Base64: {assinatura_b64[:60]}...")
    except Exception as e:
        print(f"  ERRO ao assinar: {e}")
        sys.exit(1)

    # 7. Verificar assinatura com verificar_assinatura_icp
    print("\n[6/6] Verificando assinatura com PicSaúde ...")
    try:
        from app.domain.assinatura_icp import verificar_assinatura_icp

        # Reconstruir payload para verificação
        payload_dict = json.loads(resultado_doc.serializado)

        resultado_verif = verificar_assinatura_icp(
            cert_pem=cert_pem,
            assinatura_b64=assinatura_b64,
            dados_payload=payload_dict,
        )
        print(f"  ✓ Válida:              {resultado_verif.valida}")
        print(f"  ✓ Assinatura válida:   {resultado_verif.assinatura_valida}")
        print(f"  ✓ Certificado válido:  {resultado_verif.certificado_valido}")
        print(f"  ✓ Digest:              {resultado_verif.digest_hex}")
        if resultado_verif.erro:
            print(f"  ⚠ Erro:               {resultado_verif.erro}")
    except Exception as e:
        print(f"  ⚠ Erro na verificação: {e}")

    # Resumo final
    print(f"\n{'='*60}")
    print("  RESUMO")
    print(f"{'='*60}")

    tudo_ok = True

    # Certificado válido?
    cert_valido = certificate.not_valid_before_utc <= agora <= certificate.not_valid_after_utc
    print(f"  Certificado válido:     {'✓ SIM' if cert_valido else '✗ NÃO'}")
    tudo_ok = tudo_ok and cert_valido

    # Identidade extraída?
    id_ok = identidade and identidade.parseable and identidade.cpf_certificado
    print(f"  Identidade extraída:    {'✓ SIM' if id_ok else '✗ NÃO'}")
    tudo_ok = tudo_ok and id_ok

    # Assinatura verificada?
    try:
        sig_ok = resultado_verif.valida
    except NameError:
        sig_ok = False
    print(f"  Assinatura verificada:  {'✓ SIM' if sig_ok else '✗ NÃO'}")
    tudo_ok = tudo_ok and sig_ok

    print()
    if tudo_ok:
        print("  ✅ CERTIFICADO COMPATÍVEL COM PICSAÚDE")
        print("     Pipeline completa: identidade + assinatura + verificação")
    else:
        print("  ⚠  VERIFICAÇÃO PARCIAL — revisar itens marcados com ✗")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
