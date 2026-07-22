"""
regras_atestado.py
==================
Regras de validação estrutural e sugestões de redação para o atestado médico.

RESPONSABILIDADES
-----------------
  verificar_campos_obrigatorios()  — campos faltantes ou inválidos (bloqueiam ok)
  verificar_texto_clinico()        — alertas de linguagem vaga (não-bloqueante)
  gerar_sugestoes_redacao()        — sugestões determinísticas de melhoria textual
  verificar_cid_coerencia()        — alerta de inconsistência CID ↔ texto (não-bloqueante)

PRINCÍPIOS
----------
  - Alertas nunca bloqueiam o documento (ok é determinado apenas por faltantes).
  - Sugestões nunca substituem automaticamente — são sempre para o profissional.
  - Coerência CID: soft dependency sobre IA CID v1, falha silenciosa.
  - Determinístico: mesmo input → mesmo output (sem aleatoriedade).
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional


# ---------------------------------------------------------------------------
# Normalização interna para comparação de termos
# ---------------------------------------------------------------------------

def _norm(texto: str) -> str:
    """Lowercase + remove acentos + normaliza espaços."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acentos).strip()


# ---------------------------------------------------------------------------
# 1. Campos obrigatórios
# ---------------------------------------------------------------------------

# Finalidade é obrigatória (não se emite atestado sem finalidade declarada).
# indicacao_clinica e codigo_cid são OPCIONAIS — o diagnóstico só entra com
# anuência do paciente (privacidade); o CFM admite atestado sem CID.
#
# dias_afastamento é OPCIONAL: nem todo atestado afasta. dias=0/ausente é um
# atestado de COMPARECIMENTO — o corpo usa `if dias and dias > 0` (domain/
# texto_atestado.py), então exigir dias aqui rejeitaria TODO comparecimento
# (foi o bug relatado na vitrine em 2026-07-22). O tipo é derivado de dias (§10);
# a obrigatoriedade em AFASTAMENTO é imposta na TELA — que conhece o modo pelo
# seletor —, não nesta validação, que é type-blind (só vê dias, não o tipo).
CAMPOS_OBRIGATORIOS = [
    "paciente_nome",
    "finalidade",
    "data_documento",
    "nome_profissional",
    "registro_profissional",
]


def verificar_campos_obrigatorios(dados: dict) -> List[str]:
    """
    Retorna lista de campos faltantes ou inválidos.

    Critérios de "faltante":
      - None
      - string vazia ou só espaços

    dias_afastamento NÃO entra: é opcional (comparecimento não afasta). Ver a
    nota em CAMPOS_OBRIGATORIOS.
    """
    faltantes = []
    for campo in CAMPOS_OBRIGATORIOS:
        valor = dados.get(campo)
        if valor is None:
            faltantes.append(campo)
            continue
        if isinstance(valor, str) and not valor.strip():
            faltantes.append(campo)
    return faltantes


# ---------------------------------------------------------------------------
# 2. Termos vagos — geram alerta (não-bloqueante)
# ---------------------------------------------------------------------------

# Termos normalizados (sem acentos, lowercase) que indicam redação imprecisa.
# Verificados no texto normalizado de indicacao_clinica.
_TERMOS_VAGOS = [
    "doente",
    "indisposto",
    "indisposicao",
    "mal estar",
    "mal-estar",
    "problema de saude",
    "problema",
    "mal definido",
]


def verificar_texto_clinico(indicacao_clinica: str) -> List[str]:
    """
    Retorna alertas se indicacao_clinica contiver termos vagos.

    Nunca bloqueia. Alerta único agrupando todos os termos encontrados.
    """
    texto_norm = _norm(indicacao_clinica)
    encontrados = [t for t in _TERMOS_VAGOS if t in texto_norm]
    if not encontrados:
        return []
    return [
        "Descrição clínica muito genérica. Evite os termos: "
        + ", ".join(f"'{t}'" for t in encontrados)
        + ". Prefira terminologia clínica específica (ex: 'hipertensão arterial sistêmica', "
          "'diabetes mellitus tipo 2')."
    ]


# ---------------------------------------------------------------------------
# 3. Sugestões de redação — determinísticas (não-bloqueante)
# ---------------------------------------------------------------------------

# (padrão normalizado, mensagem de sugestão)
# {DIAS} é substituído pelo valor real de dias_afastamento quando disponível.
_REGRAS_SUGESTAO: List[tuple] = [
    (
        "uns dias",
        "Substitua 'uns dias' por especificação numérica: "
        "'necessitando de afastamento por {DIAS} dia(s)'.",
    ),
    (
        "paciente doente",
        "Substitua 'paciente doente' por 'paciente em acompanhamento clínico'.",
    ),
    (
        "problema de saude",
        "Substitua 'problema de saúde' por 'quadro clínico compatível com "
        "[diagnóstico específico]'.",
    ),
    (
        "mal estar",
        "Substitua 'mal estar' por descrição clínica específica "
        "(ex: 'síndrome vertiginosa', 'cefaleia intensa', 'lombalgia aguda').",
    ),
    (
        "mal-estar",
        "Substitua 'mal-estar' por descrição clínica específica.",
    ),
]


def gerar_sugestoes_redacao(
    indicacao_clinica: str,
    dias_afastamento: Optional[int] = None,
) -> List[str]:
    """
    Retorna sugestões de melhoria textual para indicacao_clinica.

    Determinístico — nunca substitui o texto automaticamente.
    Cada regra disparada produz uma sugestão.
    """
    texto_norm = _norm(indicacao_clinica)
    sugestoes = []
    vistos: set = set()

    for padrao, mensagem in _REGRAS_SUGESTAO:
        if padrao in texto_norm and padrao not in vistos:
            vistos.add(padrao)
            if "{DIAS}" in mensagem:
                dias_str = str(dias_afastamento) if dias_afastamento else "X"
                mensagem = mensagem.replace("{DIAS}", dias_str)
            sugestoes.append(mensagem)

    return sugestoes


# ---------------------------------------------------------------------------
# 4. Coerência CID ↔ texto clínico (soft dependency sobre IA CID v1)
# ---------------------------------------------------------------------------

def verificar_cid_coerencia(indicacao_clinica: str, codigo_cid: str) -> List[str]:
    """
    Verifica se o CID escolhido é coerente com o texto clínico.

    Estratégia:
      1. Rodar buscar_cid(indicacao_clinica)
      2. Se a base retornar sugestões → verificar se codigo_cid está entre elas
      3. Se não estiver → alerta não-bloqueante

    Regras:
      - Texto sem match na base → sem alerta (impossível avaliar coerência)
      - Falha técnica da IA CID → silenciosa (validação continua normalmente)
      - Nunca bloqueia o documento
    """
    try:
        from app.ai.ia_cid import buscar_cid  # soft import — falha silenciosa
        resultado = buscar_cid(indicacao_clinica)
        sugestoes = resultado.get("cid_sugeridos", [])

        if not sugestoes:
            # Base não encontrou match para o texto → sem base para avaliar
            return []

        codigos_sugeridos = [s["codigo"] for s in sugestoes]
        if codigo_cid not in codigos_sugeridos:
            return [
                f"Possível inconsistência: o texto clínico sugere os códigos "
                f"{codigos_sugeridos[:3]} mas o CID selecionado é '{codigo_cid}'. "
                "Verifique se o diagnóstico registrado corresponde ao motivo do afastamento."
            ]
    except Exception:
        # Falha silenciosa — coerência não avaliada se IA CID indisponível
        pass

    return []
