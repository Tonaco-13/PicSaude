"""
normalizacao_exame.py
=====================
Normalização textual de nomes de exames/procedimentos diagnósticos.

Objetivo: reduzir variabilidade semântica de entrada antes do lookup TUSS.

Pipeline:
  1. Lowercase
  2. Remover acentuação
  3. Expandir abreviações conhecidas
  4. Normalizar espaços e pontuação

Garantia: função pura, sem efeitos colaterais, sem acesso a banco.
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Mapa de abreviações clínicas → forma expandida
# Ordem importa: abreviações mais específicas antes das genéricas
# ---------------------------------------------------------------------------

_ABREVIACOES: list[tuple[str, str]] = [
    # Imagem
    (r"\btc\b",    "tomografia computadorizada"),
    (r"\btac\b",   "tomografia computadorizada"),
    (r"\brm\b",    "ressonancia magnetica"),
    (r"\brmn\b",   "ressonancia magnetica"),
    (r"\bpet\b",   "pet scan"),
    (r"\bpet-ct\b","pet scan tomografia computadorizada"),
    (r"\bus\b",    "ultrassonografia"),
    (r"\busg\b",   "ultrassonografia"),
    (r"\beco\b",   "ecocardiograma"),      # predominância cardiológica
    (r"\brx\b",    "radiografia"),
    (r"\bray\b",   "radiografia"),
    (r"\braio x\b","radiografia"),
    (r"\braio-x\b","radiografia"),
    # Cardiologia
    (r"\becg\b",   "eletrocardiograma"),
    (r"\bekg\b",   "eletrocardiograma"),
    (r"\bholter\b","holter 24 horas"),
    (r"\becott\b", "ecocardiograma transtorácico"),
    # Neurologia
    (r"\beeg\b",   "eletroencefalograma"),
    (r"\bpolissonografia\b", "polissonografia"),
    # Laboratório — hematologia
    (r"\bhemo\b",  "hemograma"),
    (r"\bhct\b",   "hematócrito"),
    (r"\bhgb\b",   "hemoglobina"),
    (r"\bvhs\b",   "velocidade de hemossedimentacao"),
    (r"\bpcr\b",   "proteina c reativa"),
    # Laboratório — bioquímica
    (r"\bglic\b",  "glicemia"),
    (r"\bgli\b",   "glicemia"),
    (r"\bhba1c\b", "hemoglobina glicada"),
    (r"\ba1c\b",   "hemoglobina glicada"),
    (r"\btgo\b",   "aspartato aminotransferase"),
    (r"\tast\b",   "aspartato aminotransferase"),
    (r"\btgp\b",   "alanina aminotransferase"),
    (r"\balt\b",   "alanina aminotransferase"),
    (r"\bggt\b",   "gama glutamil transferase"),
    (r"\bfa\b",    "fosfatase alcalina"),
    # Hormonal / tireóide
    (r"\btsh\b",   "tireoestimulante"),
    (r"\bt4l\b",   "tiroxina livre"),
    (r"\bt4 livre\b", "tiroxina livre"),
    (r"\bt3\b",    "triiodotironina"),
    (r"\bft4\b",   "tiroxina livre"),
    # Renal
    (r"\bcrea\b",  "creatinina"),
    (r"\bur\b",    "ureia"),
    (r"\bau\b",    "acido urico"),
    # Urina / fezes
    (r"\beas\b",   "urina tipo i"),
    (r"\burina i\b","urina tipo i"),
    (r"\bexame de urina\b", "urina tipo i"),
    (r"\bparasitologico\b", "parasitologico de fezes"),
    (r"\bcoprológico\b",   "parasitologico de fezes"),
    # Lipídeos
    (r"\bct\b",    "colesterol total"),
    (r"\bhdl\b",   "hdl colesterol"),
    (r"\bldl\b",   "ldl colesterol"),
    (r"\btg\b",    "triglicerides"),
    (r"\btrig\b",  "triglicerides"),
    # Anatomia patológica
    (r"\bbiopsia\b",  "biópsia"),
    (r"\bap\b",       "anatomia patologica"),
    # Genérico
    (r"\blaudo\b",    "exame"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in _ABREVIACOES]


def _remover_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_nome_exame(nome: str) -> str:
    """
    Normaliza um nome de exame para comparação com a base TUSS.

    Exemplos:
      "US abd total"  → "ultrassonografia abdome total"
      "ECG"           → "eletrocardiograma"
      "TGO/TGP"       → "aspartato aminotransferase alanina aminotransferase"
    """
    if not nome:
        return ""

    texto = nome.lower().strip()
    texto = _remover_acentos(texto)

    # Substituir separadores por espaço
    texto = re.sub(r"[/\\|,;]", " ", texto)
    # Remover parênteses
    texto = re.sub(r"[()[\]]", " ", texto)
    # Remover caracteres especiais, preservar alfanumérico e espaço
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)

    # Expandir abreviações
    for pattern, repl in _COMPILED:
        texto = pattern.sub(repl, texto)

    # Normalizar espaços múltiplos
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto
