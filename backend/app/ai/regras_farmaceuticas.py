"""
regras_farmaceuticas.py
=======================
Camada de regras determinísticas para IA farmacêutica v1.

RESPONSABILIDADES
-----------------
  1. Sugerir unidade_quantidade a partir da forma_farmaceutica conhecida.
  2. Detectar incoerências clínicas evidentes (forma × princípio ativo).
  3. Gerar alertas textuais — nunca bloqueios.

PRINCÍPIOS
----------
  Determinística   — regras explícitas sem probabilidade.
  Explicável       — cada alerta indica a regra que o originou.
  Não bloqueante   — retorna alertas, nunca exceções de negócio.
  Extensível       — adicionar regras apenas neste arquivo.

TABELAS EXPORTADAS
------------------
  FORMA_PARA_UNIDADE       dict[str, str]
  verificar_incoerencias() → list[str]
  sugerir_unidade()        → str | None
"""

from __future__ import annotations

from app.ai.normalizacao_medicamento import normalizar_nome_medicamento, remover_acentos


# ---------------------------------------------------------------------------
# Mapa forma_farmaceutica (normalizada) → unidade_dispensavel sugerida
#
# Alinhado com UNIDADES_QUANTIDADE em domain/medicamento.py
# ---------------------------------------------------------------------------

FORMA_PARA_UNIDADE: dict[str, str] = {
    "comprimido":    "comprimido",
    "capsula":       "cápsula",
    "dragea":        "drágea",
    "pastilha":      "pastilha",
    "ampola":        "ampola",
    "frasco":        "frasco",
    "frasco-ampola": "frasco-ampola",
    "bisnaga":       "bisnaga",
    "sachê":         "sachê",
    "sache":         "sachê",
    "envelope":      "envelope",
    "supositorio":   "supositório",
    "supositório":   "supositório",
    "caixa":         "caixa",
    # Apresentações que mapeiam para "frasco"
    "solucao":       "frasco",
    "suspensao":     "frasco",
    "xarope":        "frasco",
    "gota":          "frasco",
    "colirio":       "frasco",
    # Apresentações que mapeiam para "bisnaga"
    "pomada":        "bisnaga",
    "creme":         "bisnaga",
    "gel":           "bisnaga",
    # Apresentações inalatórias
    "aerossol":      "frasco",
    "inalador":      "frasco",
    "spray":         "frasco",
}


# ---------------------------------------------------------------------------
# Regras de incoerência
# Cada entrada: (keyword_principio_ativo, keyword_forma, mensagem_alerta)
#
# keyword_principio_ativo: substring normalizada no nome do medicamento
# keyword_forma:           substring normalizada na forma farmacêutica
# ---------------------------------------------------------------------------

_INCOERENCIAS: list[tuple[str, str, str]] = [
    # Insulinas não são sólidas
    ("insulina", "comprimido",
     "Insulina não é administrada em comprimido — verificar forma farmacêutica."),
    ("insulina", "capsula",
     "Insulina não é administrada em cápsula — verificar forma farmacêutica."),
    ("insulina", "dragea",
     "Insulina não é administrada em drágea — verificar forma farmacêutica."),
    ("insulina", "pastilha",
     "Insulina não é administrada em pastilha — verificar forma farmacêutica."),

    # Colírios não são formas sólidas ou parenterais
    ("colirio", "comprimido",
     "Colírio não é apresentado em comprimido — verificar forma farmacêutica."),
    ("colirio", "capsula",
     "Colírio não é apresentado em cápsula — verificar forma farmacêutica."),
    ("colirio", "ampola",
     "Colírio não é apresentado em ampola — verificar forma farmacêutica."),

    # Pomadas / cremes / géis não são líquidos parenterais
    ("pomada", "ampola",
     "Pomada não é apresentada em ampola — verificar forma farmacêutica."),
    ("pomada", "comprimido",
     "Pomada não é apresentada em comprimido — verificar forma farmacêutica."),
    ("pomada", "capsula",
     "Pomada não é apresentada em cápsula — verificar forma farmacêutica."),
    ("creme",  "ampola",
     "Creme não é apresentado em ampola — verificar forma farmacêutica."),
    ("gel",    "ampola",
     "Gel não é apresentado em ampola — verificar forma farmacêutica."),

    # Xaropes / suspensões não são sólidos
    ("xarope", "comprimido",
     "Xarope não é apresentado em comprimido — verificar forma farmacêutica."),
    ("xarope", "ampola",
     "Xarope não é apresentado em ampola — verificar forma farmacêutica."),
    ("suspensao", "ampola",
     "Suspensão não é apresentada em ampola — verificar forma farmacêutica."),

    # Injetáveis não são formas sólidas orais
    ("injetavel", "comprimido",
     "Solução injetável não é apresentada em comprimido — verificar forma farmacêutica."),
    ("injetavel", "capsula",
     "Solução injetável não é apresentada em cápsula — verificar forma farmacêutica."),

    # Aerossóis / sprays inalatórios não são comprimidos/cápsulas
    ("aerossol", "comprimido",
     "Aerossol não é apresentado em comprimido — verificar forma farmacêutica."),
    ("aerossol", "capsula",
     "Aerossol não é apresentado em cápsula — verificar forma farmacêutica."),
    ("inalador", "comprimido",
     "Inalador não é apresentado em comprimido — verificar forma farmacêutica."),
    ("inalador", "capsula",
     "Inalador não é apresentado em cápsula — verificar forma farmacêutica."),
]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _normalizar_simples(texto: str | None) -> str:
    """Lowercase + remove acentos + strip. Não expande abreviações."""
    if not texto:
        return ""
    import unicodedata
    n = unicodedata.normalize("NFKD", texto.lower().strip())
    return "".join(c for c in n if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def sugerir_unidade(forma_farmaceutica: str | None) -> str | None:
    """
    Sugere unidade_quantidade a partir da forma_farmaceutica.

    Retorna None se a forma não for reconhecida.

    Exemplos:
        'comprimido'  → 'comprimido'
        'Cápsulas'    → 'cápsula'
        'solução oral'→ 'frasco'
        'pomada'      → 'bisnaga'
        'xyz'         → None
    """
    if not forma_farmaceutica:
        return None

    forma_norm = _normalizar_simples(forma_farmaceutica)

    # Tenta match direto
    if forma_norm in FORMA_PARA_UNIDADE:
        return FORMA_PARA_UNIDADE[forma_norm]

    # Tenta se alguma chave conhecida é substring da forma informada
    for chave, unidade in FORMA_PARA_UNIDADE.items():
        if chave in forma_norm:
            return unidade

    return None


def verificar_incoerencias(
    nome_medicamento: str | None,
    forma_farmaceutica: str | None,
) -> list[str]:
    """
    Aplica as regras de incoerência e retorna lista de alertas textuais.

    Parâmetros
    ----------
    nome_medicamento    : nome livre do medicamento (ex.: "insulina glargina")
    forma_farmaceutica  : forma declarada (ex.: "comprimido")

    Retorno
    -------
    Lista de strings descrevendo incoerências detectadas.
    Lista vazia = sem incoerências.

    Nunca lança exceção.
    """
    if not nome_medicamento and not forma_farmaceutica:
        return []

    nome_norm  = _normalizar_simples(nome_medicamento)
    forma_norm = _normalizar_simples(forma_farmaceutica)
    alertas    = []

    for kw_nome, kw_forma, mensagem in _INCOERENCIAS:
        if kw_nome in nome_norm and kw_forma in forma_norm:
            alertas.append(mensagem)

    return alertas
