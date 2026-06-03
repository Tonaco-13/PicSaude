from __future__ import annotations

import re

from fastapi import HTTPException

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


# ---------------------------------------------------------------------------
# Helpers de ownership (ADR-002, Helpers 1 e 2 — introduzidos pelo TICKET-5C-BIS-A)
# ---------------------------------------------------------------------------
# Puros, sem acesso a banco. Centralizam o contrato de erro {codigo, mensagem}
# em PT (5C §3.5) e a normalização de identidade do JWT. As queries de ownership
# permanecem locais a cada subdomínio (ADR-002 opção C estendida).


def _assert_or_403(condicao: bool, codigo: str, mensagem: str) -> None:
    """Garante `condicao` ou levanta 403 com o formato {codigo, mensagem} em PT.

    Helper 1 da ADR-002 §2.1. Não faz query, comparação nem normalização —
    recebe um booleano já avaliado. Elimina a duplicação do raise em ~9 sites.
    """
    if not condicao:
        raise HTTPException(
            status_code=403,
            detail={"codigo": codigo, "mensagem": mensagem},
        )


def _normalizar_identidade_jwt(usuario: dict) -> tuple[str, str]:
    """Extrai (papel, identificador canônico) do payload JWT.

    Helper 2 da ADR-002 §2.1. Contrato de **totalidade** (§6.2 do TICKET-5C-BIS-A):
    nunca levanta exceção; sempre retorna a tupla para qualquer payload.

      - prescritor → (papel, CNS)  · paciente → (papel, CPF)
      - dispensador → (papel, CNPJ)  — via normalize_cnpj (remove máscara E o
        sufixo `.0` de artefato Excel, §8.2); o strip genérico de dígitos NÃO
        equivale a normalize_cnpj, daí o ramo dedicado.
      - admin/auditor/integrador → (papel, <dígitos do sub ou "">). O
        identificador desses papéis não tem semântica clínica e não deve ser
        comparado a registro de banco; o caller faz o bypass de `admin` ANTES
        de usar o identificador (§7.1).
    """
    papel = usuario.get("role", "")
    sub = usuario.get("sub", "")
    if papel == "dispensador":
        ident = normalize_cnpj(sub)            # remove máscara E sufixo .0 (§8.2)
    else:
        ident = re.sub(r"\D", "", sub or "")   # prescritor=CNS, paciente=CPF;
                                               # admin/auditor → dígitos ou "" (nunca levanta)
    return papel, ident


def cbo_where_clause() -> str:
    parts = [f"r.CO_CBO LIKE '{p}%'" for p in CBO_PREFIXES]
    return "(" + " OR ".join(parts) + ")"


def vinculo_ativo_where_clause() -> str:
    # A base nacional (tbCargaHorariaSus) não tem DT_DESLIGAMENTO —
    # o snapshot mensal do CNES já contém apenas vínculos ativos.
    return "1=1"
