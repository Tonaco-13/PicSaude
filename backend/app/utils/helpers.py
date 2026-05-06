from __future__ import annotations

import re

from app.config import CBO_PREFIXES


def normalize_nome(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).upper()


def normalize_cpf(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def normalize_cnpj(s) -> str:
    text = str(s or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return re.sub(r"\D", "", text)


def normalize_cns(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def cbo_where_clause() -> str:
    parts = [f"r.CO_CBO LIKE '{p}%'" for p in CBO_PREFIXES]
    return "(" + " OR ".join(parts) + ")"


def vinculo_ativo_where_clause() -> str:
    # A base nacional (tbCargaHorariaSus) não tem DT_DESLIGAMENTO —
    # o snapshot mensal do CNES já contém apenas vínculos ativos.
    return "1=1"
