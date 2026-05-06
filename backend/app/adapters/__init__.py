"""Adapters de integração com sistemas externos.

Cada adapter encapsula a comunicação com um sistema externo (SNCR/Anvisa,
HIS, TISS, e-SUS, etc.). Adapters seguem a regra do CLAUDE.md §10:

  - NUNCA escrevem diretamente em tabelas clínicas
  - NUNCA emitem eventos no ledger via SQL bypassando a API
  - SEMPRE consomem endpoints oficiais do PicSaúde
  - SEMPRE são versionáveis independentemente do núcleo

Adapters atuais:
  sncr_interface  — contrato (ABC) para integração com o SNCR (RDC 1.000/2025)
  sncr_stub       — implementação mock para desenvolvimento e testes
  sncr_factory    — seleção de implementação via SNCR_ADAPTER (env var)
"""
