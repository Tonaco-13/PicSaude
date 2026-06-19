"""
cofre_pfx.py
============
Cifragem AES-256-GCM dos arquivos .pfx persistidos — Ticket 21.

Princípios
----------
- A chave de criptografia (`PFX_ENCRYPTION_KEY`) é variável de ambiente
  (32 bytes em hex). NUNCA persistida no banco.
- IV de 12 bytes é gerado por upload (não reusar IV com a mesma chave).
- Tag de autenticação de 16 bytes é persistida junto.
- Em modo de teste/dev, se `PFX_ENCRYPTION_KEY` não está definida, o
  cofre usa uma chave fixa derivada de uma sentinela — explicitamente
  insegura e marcada como tal.

Rotação de chave
----------------
A rotação de chave exige re-criptografar todos os .pfx existentes com
a nova chave. Implementação fora do escopo do T21 (futuro: script
`scripts/rotate_pfx_key.py`).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_ENV_KEY = "PFX_ENCRYPTION_KEY"

# Sentinela de dev — derivada determinística para que a base de dev
# possa ser regenerada sem perder cifrados, MAS NUNCA usar em produção.
_DEV_SENTINELA = b"PICSAUDE_DEV_INSECURE_PFX_KEY___"
assert len(_DEV_SENTINELA) == 32


@dataclass(frozen=True)
class PfxCifrado:
    cifrado: bytes
    iv: bytes
    tag: bytes


class CofreChaveInsegura(RuntimeError):
    """Tentativa de operar o cofre com a chave-sentinela (insegura) fora de
    dev/test. Em stg/prod, a ausência de PFX_ENCRYPTION_KEY deve falhar fechado.
    """


# Ambientes onde a chave-sentinela insegura é tolerada — APENAS estes.
_AMBIENTES_CHAVE_INSEGURA_OK = ("dev", "test")


def _exigir_chave_segura(seguro: bool) -> None:
    """Fail-closed (auditoria de segurança — F1).

    Recusa cifrar/decifrar com a chave de desenvolvimento fora de dev/test.
    Em stg/prod a ausência de `PFX_ENCRYPTION_KEY` NÃO pode cair na sentinela
    pública — a operação é recusada em vez de usar chave insegura.
    """
    if seguro:
        return
    env = os.getenv("PICSAUDE_ENV", "dev").lower()
    if env not in _AMBIENTES_CHAVE_INSEGURA_OK:
        raise CofreChaveInsegura(
            f"PFX_ENCRYPTION_KEY ausente ou inválida: o cofre recusa operar com "
            f"a chave de desenvolvimento fora de dev/test (ambiente='{env}'). "
            f"Configure PFX_ENCRYPTION_KEY (32 bytes em hex)."
        )


def _carregar_chave() -> tuple[bytes, bool]:
    """Retorna (chave_32_bytes, é_seguro). False = chave de desenvolvimento."""
    valor = os.environ.get(_ENV_KEY)
    if valor:
        # Aceita hex (64 chars) ou bytes literais (32 chars). Hex é o padrão.
        if len(valor) == 64:
            try:
                return bytes.fromhex(valor), True
            except ValueError:
                pass
        if len(valor) == 32:
            return valor.encode("latin-1"), True
        # Chave de tamanho diferente — derivar via SHA-256 para 32 bytes.
        # Reduz risco de chave malformada bloqueando o app, mas avisa.
        derivada = hashlib.sha256(valor.encode("utf-8")).digest()
        return derivada, True
    # Sem chave configurada → modo dev/teste com sentinela.
    return _DEV_SENTINELA, False


def cifrar_pfx(pfx_bytes: bytes) -> PfxCifrado:
    chave, seguro = _carregar_chave()
    _exigir_chave_segura(seguro)
    aes = AESGCM(chave)
    iv = os.urandom(12)
    cifrado = aes.encrypt(iv, pfx_bytes, associated_data=b"picsaude.pfx")
    # AES-GCM em cryptography retorna ciphertext+tag concatenados.
    # Separamos os 16 bytes finais (tag) para persistência explícita.
    if len(cifrado) < 16:
        raise RuntimeError("Saída AES-GCM inesperadamente curta")
    body = cifrado[:-16]
    tag = cifrado[-16:]
    return PfxCifrado(cifrado=body, iv=iv, tag=tag)


def decifrar_pfx(cifrado: bytes, iv: bytes, tag: bytes) -> bytes:
    chave, seguro = _carregar_chave()
    _exigir_chave_segura(seguro)
    aes = AESGCM(chave)
    return aes.decrypt(iv, cifrado + tag, associated_data=b"picsaude.pfx")


def chave_eh_segura() -> bool:
    """True se PFX_ENCRYPTION_KEY foi configurada (não está no fallback dev)."""
    _, seguro = _carregar_chave()
    return seguro
