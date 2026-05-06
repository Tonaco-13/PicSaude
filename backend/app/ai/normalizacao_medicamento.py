"""
normalizacao_medicamento.py
===========================
Normalização textual de nomes de medicamentos para busca e comparação.

TRANSFORMAÇÕES APLICADAS (em ordem)
-------------------------------------
1. Lowercase
2. Remoção de acentos e diacríticos (NFKD → ASCII puro)
3. Separação número/unidade colados  (500mg → 500 mg, 0,5mg → 0 5 mg)
4. Expansão de abreviações farmacêuticas comuns
5. Singularização de formas farmacêuticas (cápsulas → capsula)
6. Colapso de espaços múltiplos e trim

PROPRIEDADES
------------
  Determinística   — sem aleatoriedade, sem estado.
  Idempotente      — normalizar(normalizar(x)) == normalizar(x).
  Sem dependências externas além da stdlib.

EXEMPLOS
--------
  'Amoxicilina 500mg Cápsulas'        → 'amoxicilina 500 mg capsula'
  'Insulina NPH 100 UI/mL inj.'       → 'insulina nph 100 ui/ml injetavel'
  'Metformina 850mg Cpr.'             → 'metformina 850 mg comprimido'
  'Dipirona Sód. 500mg/mL - Gotas'   → 'dipirona sod 500 mg/ml gotas'
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Tabela de singularização: plural/variante → forma canônica (sem acento)
# ---------------------------------------------------------------------------

_SINGULAR: dict[str, str] = {
    # Formas farmacêuticas
    "capsulas":       "capsula",
    "cápsulas":       "capsula",
    "cápsula":        "capsula",
    "comprimidos":    "comprimido",
    "drageas":        "dragea",
    "drágeas":        "dragea",
    "drágea":         "dragea",
    "ampolas":        "ampola",
    "bisnagas":       "bisnaga",
    "frascos":        "frasco",
    "pastilhas":      "pastilha",
    "saches":         "sache",
    "sachês":         "sache",
    "sachê":          "sache",
    "supositórios":   "supositorio",
    "supositorio":    "supositorio",
    "supositórios":   "supositorio",
    "envelopes":      "envelope",
    "gotas":          "gota",
    "pomadas":        "pomada",
    "sprays":         "spray",
    "aerossois":      "aerossol",
    "inaladores":     "inalador",
    # Vias de administração (variantes)
    "v.o.":           "oral",
    "v.o":            "oral",
}


# ---------------------------------------------------------------------------
# Tabela de abreviações: regex → expansão
# ---------------------------------------------------------------------------

_ABREVIACOES: list[tuple[re.Pattern, str]] = [
    # Formas farmacêuticas
    (re.compile(r"\bcaps?\b",              re.I), "capsula"),
    (re.compile(r"\bcp(?:r)?s?\b",         re.I), "comprimido"),
    (re.compile(r"\bdrg\b",               re.I), "dragea"),
    (re.compile(r"\bamp\b",               re.I), "ampola"),
    (re.compile(r"\bsusp\b",              re.I), "suspensao"),
    (re.compile(r"\bsol\b",               re.I), "solucao"),
    (re.compile(r"\binj\b",               re.I), "injetavel"),
    (re.compile(r"\baer\b",               re.I), "aerossol"),
    (re.compile(r"\binh\b",               re.I), "inalatorio"),
    # Vias de administração
    (re.compile(r"\bv\.?o\.?\b",          re.I), "oral"),
    (re.compile(r"\bi\.?v\.?\b",          re.I), "intravenosa"),
    (re.compile(r"\bi\.?m\.?\b",          re.I), "intramuscular"),
    (re.compile(r"\bs\.?c\.?\b",          re.I), "subcutanea"),
    # Unidades de medida (padronizar caixa)
    (re.compile(r"\bmcg\b",               re.I), "mcg"),
    (re.compile(r"\bµg\b",                re.I), "mcg"),
    (re.compile(r"\bui\b",                re.I), "ui"),
    # Sufixos químicos comuns (não expandir, só remover ponto)
    (re.compile(r"\bsód\.?\b",            re.I), "sod"),
    (re.compile(r"\bclorid\.?\b",         re.I), "cloridrato"),
    (re.compile(r"\bmale\.?\b",           re.I), "maleato"),
    (re.compile(r"\bsuc\.?\b",            re.I), "succinato"),
]


# ---------------------------------------------------------------------------
# Regex auxiliares
# ---------------------------------------------------------------------------

# Separa número colado à unidade: 500mg → 500 mg, 0,5mg → 0,5 mg
_RE_NUM_UNIDADE = re.compile(
    r"(\d+(?:[.,]\d+)?)"
    r"\s*"
    r"(mg/ml|mcg/ml|ui/ml|mg/dose|mcg/dose|mg|mcg|µg|g\b|ml\b|ui\b|%)",
    re.IGNORECASE,
)

# Remove caracteres não farmacêuticos (manter: letras, dígitos, espaço, /, +, -)
_RE_LIXO = re.compile(r"[^\w\s/+\-.,]", re.UNICODE)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def remover_acentos(texto: str) -> str:
    """Converte para ASCII removendo diacríticos via NFKD."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def separar_numero_unidade(texto: str) -> str:
    """
    Insere espaço entre número e unidade farmacêutica colados.
    Ex.: '500mg' → '500 mg', '0,5mg' → '0,5 mg', '100UI/mL' → '100 ui/ml'
    """
    return _RE_NUM_UNIDADE.sub(lambda m: f"{m.group(1)} {m.group(2).lower()}", texto)


def normalizar_nome_medicamento(nome: str | None) -> str:
    """
    Normaliza um nome de medicamento para busca e comparação.

    Retorna string lowercase sem acentos, com formas singularizadas
    e abreviações expandidas.

    Exemplos:
        'Amoxicilina 500mg Cápsulas'     → 'amoxicilina 500 mg capsula'
        'Insulina NPH 100 UI/mL Inj.'    → 'insulina nph 100 ui/ml injetavel'
        'Dipirona 500mg/mL Gotas'        → 'dipirona 500 mg/ml gota'
    """
    if not nome:
        return ""

    texto = nome.strip()

    # 1. Remove caracteres decorativos antes de qualquer coisa
    texto = _RE_LIXO.sub(" ", texto)

    # 2. Lowercase
    texto = texto.lower()

    # 3. Remove acentos
    texto = remover_acentos(texto)

    # 4. Separa número/unidade colados
    texto = separar_numero_unidade(texto)

    # 5. Expande abreviações
    for padrao, expansao in _ABREVIACOES:
        texto = padrao.sub(expansao, texto)

    # 6. Singulariza formas
    tokens = texto.split()
    tokens = [_SINGULAR.get(t, t) for t in tokens]
    texto = " ".join(tokens)

    # 7. Normaliza espaços residuais e vírgulas numéricas
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto
