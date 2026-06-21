"""
lookup_def.py
=============
Lookup farmacêutico contra a base local DEF (data/def_medicamentos.csv).

ESTRATÉGIA DE MATCH
-------------------
  1. Exato     — nome_normalizado == normalizar(entrada)
  2. Alias     — entrada normalizada bate com qualquer alias registrado
  3. Aproximado — rapidfuzz WRatio >= THRESHOLD_APROXIMADO (default 82)
  4. Nenhum    — sem correspondência aceitável

CARREGAMENTO DA BASE
--------------------
  A base é carregada uma vez no import do módulo (singleton em memória).
  É completamente readonly — sem mutação em runtime.

CAMPOS DO CSV
-------------
  principio_ativo      nome_normalizado      forma_farmaceutica
  unidade_dispensavel  concentracao_texto    via_administracao
  aliases              fonte                 versao_base

RESULTADO
---------
  {
    "principio_ativo":          str | None,
    "nome_normalizado_base":    str | None,
    "forma_farmaceutica":       str | None,
    "unidade_dispensavel":      str | None,
    "concentracao_texto":       str | None,
    "via_administracao":        str | None,
    "match_tipo":               "exato" | "alias" | "aproximado" | "nenhum",
    "score":                    float,          # 0.0–1.0
    "fonte":                    str | None,
    "versao_base":              str | None,
  }
"""

from __future__ import annotations

import csv
import os
import re
from typing import Optional

from rapidfuzz import fuzz, process

from app.ai.normalizacao_medicamento import normalizar_nome_medicamento


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def _resolver_base_csv() -> str:
    """Caminho da base DEF.

    Prioriza a env `PICSAUDE_DEF_CSV` (empacotamento: o Docker copia a CSV para
    um caminho estável FORA de `/data`, que é diretório de volume e seria sombreado
    por um mount). Sem a env, usa o layout de dev (raiz do repo). Sem isso, na
    imagem a CSV não é encontrada e a base DEF fica vazia (o DEF "não carrega").
    """
    override = os.getenv("PICSAUDE_DEF_CSV")
    if override:
        return override
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),   # backend/app/ai/
            "..", "..", "..",             # raiz do repo (em dev)
            "data", "def_medicamentos.csv",
        )
    )


_BASE_CSV = _resolver_base_csv()

THRESHOLD_APROXIMADO: int = 88   # 2026-05-25 — subido de 82
                                  # após bug WRatio "N mg" empate
                                  # em 85.5 (todas as queries
                                  # fora da base viravam amoxicilina)


# ---------------------------------------------------------------------------
# Carregamento da base (singleton em memória)
# ---------------------------------------------------------------------------

def _carregar_base(caminho: str) -> list[dict]:
    """Lê o CSV e retorna lista de registros normalizados."""
    registros: list[dict] = []
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normaliza aliases para lista
                aliases_raw = row.get("aliases", "") or ""
                aliases = [
                    normalizar_nome_medicamento(a.strip())
                    for a in aliases_raw.split("|")
                    if a.strip()
                ]
                registros.append({
                    "principio_ativo":       (row.get("principio_ativo") or "").strip(),
                    "nome_normalizado":       (row.get("nome_normalizado") or "").strip(),
                    "forma_farmaceutica":     (row.get("forma_farmaceutica") or "").strip(),
                    "unidade_dispensavel":    (row.get("unidade_dispensavel") or "").strip(),
                    "concentracao_texto":     (row.get("concentracao_texto") or "").strip() or None,
                    "via_administracao":      (row.get("via_administracao") or "").strip() or None,
                    "aliases":               aliases,
                    "fonte":                 (row.get("fonte") or "DEF/BASE_LOCAL").strip(),
                    "versao_base":           (row.get("versao_base") or "").strip(),
                })
    except FileNotFoundError:
        # Base ausente — retorna vazio; módulo funciona no modo "nenhum"
        pass
    return registros


# Carregamento único na inicialização do módulo
_BASE: list[dict] = _carregar_base(_BASE_CSV)

# Índice de nomes normalizados para busca rápida exata
_INDICE_EXATO: dict[str, dict] = {r["nome_normalizado"]: r for r in _BASE}

# Índice de aliases: alias_normalizado → registro
_INDICE_ALIAS: dict[str, dict] = {}
for _reg in _BASE:
    for _alias in _reg["aliases"]:
        if _alias and _alias not in _INDICE_ALIAS:
            _INDICE_ALIAS[_alias] = _reg

# Lista de nomes para busca fuzzy (nome_normalizado + aliases)
_CANDIDATOS_FUZZY: list[str] = list(_INDICE_EXATO.keys()) + list(_INDICE_ALIAS.keys())


# ---------------------------------------------------------------------------
# Resultado vazio padrão
# ---------------------------------------------------------------------------

def _resultado_nenhum() -> dict:
    return {
        "principio_ativo":       None,
        "nome_normalizado_base": None,
        "forma_farmaceutica":    None,
        "unidade_dispensavel":   None,
        "concentracao_texto":    None,
        "via_administracao":     None,
        "match_tipo":            "nenhum",
        "score":                 0.0,
        "fonte":                 None,
        "versao_base":           None,
    }


def _unidade_de_forma(forma: str) -> str:
    """Mapeia a forma farmacêutica para a unidade de DISPENSAÇÃO mais usual
    (alinhada às opções do seletor do prescritor). Evita unidade vazia/errada
    para líquidos, injetáveis e semissólidos (ex.: 'solução' não é unidade)."""
    f = (forma or "").lower()
    head = f.split()[0] if f else ""
    if head in ("comprimido", "cápsula", "drágea", "pastilha", "supositório"):
        return head
    if "injetável" in f:
        return "frasco-ampola" if ("pó" in f or "liofilizado" in f) else "ampola"
    if "infusão" in f:
        return "frasco"
    if head in ("creme", "pomada", "gel", "pasta"):
        return "bisnaga"
    if head == "granulado":
        return "envelope"
    if head in ("solução", "suspensão", "xarope", "elixir", "emulsão",
                "loção", "xampu", "líquido", "pó", "aerossol", "spray"):
        return "frasco"
    return "unidade"


def _resultado_de_registro(reg: dict, match_tipo: str, score: float) -> dict:
    return {
        "principio_ativo":       reg["principio_ativo"] or None,
        "nome_normalizado_base": reg["nome_normalizado"] or None,
        "forma_farmaceutica":    reg["forma_farmaceutica"] or None,
        "unidade_dispensavel":   _unidade_de_forma(reg["forma_farmaceutica"]),
        "concentracao_texto":    reg["concentracao_texto"],
        "via_administracao":     reg["via_administracao"],
        "match_tipo":            match_tipo,
        "score":                 round(score, 4),
        "fonte":                 reg["fonte"],
        "versao_base":           reg["versao_base"] or None,
    }


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def buscar_medicamento(
    nome_medicamento: str,
    concentracao: Optional[str] = None,
    forma_farmaceutica: Optional[str] = None,
    threshold: int = THRESHOLD_APROXIMADO,
) -> dict:
    """
    Busca um medicamento na base local DEF.

    Parâmetros
    ----------
    nome_medicamento    : nome livre (será normalizado internamente)
    concentracao        : texto de concentração opcional (ex.: '500 mg')
    forma_farmaceutica  : forma opcional (ex.: 'comprimido')
    threshold           : score mínimo para match aproximado (0–100)

    Retorno
    -------
    dict com campos: principio_ativo, nome_normalizado_base, forma_farmaceutica,
    unidade_dispensavel, concentracao_texto, via_administracao, match_tipo,
    score (0.0–1.0), fonte, versao_base.

    match_tipo pode ser: 'exato' | 'alias' | 'aproximado' | 'nenhum'
    """
    if not _BASE:
        return _resultado_nenhum()

    # Montar texto de busca — pode incluir concentração e forma
    partes = [nome_medicamento or ""]
    if concentracao:
        partes.append(concentracao)
    if forma_farmaceutica:
        partes.append(forma_farmaceutica)
    texto_busca = normalizar_nome_medicamento(" ".join(partes))

    if not texto_busca:
        return _resultado_nenhum()

    # 1. Match exato no nome_normalizado
    if texto_busca in _INDICE_EXATO:
        return _resultado_de_registro(_INDICE_EXATO[texto_busca], "exato", 1.0)

    # 2. Match exato em alias
    if texto_busca in _INDICE_ALIAS:
        return _resultado_de_registro(_INDICE_ALIAS[texto_busca], "alias", 1.0)

    # 3. Match aproximado (fuzzy) — rapidfuzz WRatio
    if not _CANDIDATOS_FUZZY:
        return _resultado_nenhum()

    melhor = process.extractOne(
        texto_busca,
        _CANDIDATOS_FUZZY,
        scorer=fuzz.WRatio,
    )

    if melhor is None:
        return _resultado_nenhum()

    melhor_texto, melhor_score, _ = melhor

    if melhor_score < threshold:
        return _resultado_nenhum()

    # Localizar registro correspondente ao candidato vencedor
    reg = _INDICE_EXATO.get(melhor_texto) or _INDICE_ALIAS.get(melhor_texto)
    if reg is None:
        return _resultado_nenhum()

    return _resultado_de_registro(reg, "aproximado", melhor_score / 100.0)


_BUSCA_NORM_CACHE: Optional[list[tuple]] = None


def _busca_norm_cache() -> list[tuple]:
    """(reg, texto_normalizado_para_busca) por registro — calculado uma vez."""
    global _BUSCA_NORM_CACHE
    if _BUSCA_NORM_CACHE is None:
        _BUSCA_NORM_CACHE = [
            (
                reg,
                normalizar_nome_medicamento(
                    (reg.get("principio_ativo") or "") + " "
                    + (reg.get("nome_normalizado") or "")
                ),
            )
            for reg in _BASE
        ]
    return _BUSCA_NORM_CACHE


def _conc_ordenavel(texto: str) -> float:
    """Extrai o 1º número da concentração para ordenar 5 < 10 < 15 < 20 mg."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", texto or "")
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def buscar_medicamentos(nome_medicamento: str, max_resultados: int = 8) -> list[dict]:
    """Busca multi-resultado (autocomplete): até `max_resultados` candidatos.

    Prioridade:
      1. SUBSTRING no princípio ativo / nome — quem contém o termo vem primeiro,
         ordenado por concentração. Isso evita que o fuzzy traga fármacos errados
         (capecitabina para "escita") e empurre as concentrações certas para fora
         do limite.
      2. Fuzzy (rapidfuzz WRatio) — completa o resto, tolerando erro de digitação.
    Deduplicado por registro.
    """
    if not _BASE or not _CANDIDATOS_FUZZY:
        return []
    texto = normalizar_nome_medicamento(nome_medicamento or "")
    if len(texto) < 2:
        return []

    resultados: list[dict] = []
    vistos: set[int] = set()

    def _adiciona(reg: dict, tipo: str, score: float) -> bool:
        if reg is None or id(reg) in vistos:
            return False
        vistos.add(id(reg))
        resultados.append(_resultado_de_registro(reg, tipo, score))
        return len(resultados) >= max_resultados

    # 1) Correspondência por substring (relevância forte), ordenada por concentração.
    diretos = [reg for reg, alvo in _busca_norm_cache() if texto in alvo]
    diretos.sort(key=lambda r: (
        (r.get("principio_ativo") or ""),
        (r.get("forma_farmaceutica") or ""),
        _conc_ordenavel(r.get("concentracao_texto") or ""),
    ))
    for reg in diretos:
        if _adiciona(reg, "substring", 1.0):
            return resultados

    # 2) Fuzzy completa o restante (sem repetir).
    brutos = process.extract(
        texto, _CANDIDATOS_FUZZY, scorer=fuzz.WRatio, limit=max_resultados * 4
    )
    for nome_cand, score, _ in brutos:
        reg = _INDICE_EXATO.get(nome_cand) or _INDICE_ALIAS.get(nome_cand)
        if reg is None or id(reg) in vistos:
            continue
        if score >= 100 and nome_cand in _INDICE_EXATO:
            tipo = "exato"
        elif score >= 100:
            tipo = "alias"
        else:
            tipo = "aproximado"
        if _adiciona(reg, tipo, score / 100.0):
            break
    return resultados


def tamanho_base() -> int:
    """Retorna o número de entradas carregadas na base."""
    return len(_BASE)


def versao_base() -> str | None:
    """Retorna a versao_base do primeiro registro (todas iguais no MVP)."""
    return _BASE[0]["versao_base"] if _BASE else None
