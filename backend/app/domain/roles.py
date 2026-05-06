"""
PicSaúde — Contrato de Perfis (RBAC)
=====================================
Fonte de verdade para perfis de usuário e permissões por endpoint.

REGRA: nenhum novo perfil deve ser criado sem atualizar este arquivo
e a tabela de mapeamento abaixo.

Perfis ativos:
  prescritor   — emite e cancela prescrições
  dispensador  — transfere custódia e dispensa itens
  auditor      — leitura de relatórios e ledger (sem escrita)
  admin        — acesso total
  cidadao      — (futuro) consulta das próprias prescrições

Mapeamento endpoint → perfis permitidos:
  POST /prescricoes                            prescritor
  POST /prescricoes/fisica                     prescritor
  POST /prescricoes/{p}/custodia/transferir    dispensador, prescritor
  POST /prescricoes/{p}/itens/{i}/dispensar    dispensador
  GET  /dispensacoes/{id}/comprovante          dispensador, prescritor, auditor, admin
  GET  /relatorios/dispensacoes.csv            auditor, admin
  GET  /prescricoes/{protocolo}/qr             prescritor, dispensador, admin
  GET  /public/prescricoes/{protocolo}         público (sem auth)
"""

from __future__ import annotations

from typing import FrozenSet, Literal

# ---------------------------------------------------------------------------
# Tipo literal — mypy bloqueia perfis inválidos em tempo de análise estática
# ---------------------------------------------------------------------------

Perfil = Literal["prescritor", "dispensador", "auditor", "admin", "cidadao"]

# ---------------------------------------------------------------------------
# Frozenset — validação em runtime (ex: dados vindos do banco ou payload JWT)
# ---------------------------------------------------------------------------

PERFIS_VALIDOS: FrozenSet[str] = frozenset({
    "prescritor",
    "dispensador",
    "auditor",
    "admin",
    "cidadao",
})

# ---------------------------------------------------------------------------
# Agrupamentos semânticos úteis nos routers
# ---------------------------------------------------------------------------

PERFIS_CLINICOS:   FrozenSet[str] = frozenset({"prescritor"})
PERFIS_FARMACIA:   FrozenSet[str] = frozenset({"dispensador"})
PERFIS_AUDITORIA:  FrozenSet[str] = frozenset({"auditor", "admin"})
PERFIS_OPERACAO:   FrozenSet[str] = frozenset({"prescritor", "dispensador"})
PERFIS_INTERNOS:   FrozenSet[str] = frozenset({"prescritor", "dispensador", "auditor", "admin"})
PERFIS_ADMIN_ONLY: FrozenSet[str] = frozenset({"admin"})
