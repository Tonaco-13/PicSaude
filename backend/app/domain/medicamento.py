"""
medicamento.py
==============
Vocabulário controlado de unidades farmacêuticas do PicSaúde.

REFERÊNCIA NORMATIVA
--------------------
ANVISA — RDC 429/2020 e RDC 57/2009: nomenclatura de formas farmacêuticas.
CFM — Resolução 2.299/2021: campos obrigatórios por item na prescrição digital.

DISTINÇÃO SEMÂNTICA
-------------------
  unidade_quantidade : unidade contável para fins de dispensação e controle
                       de saldo. É a base para aritmética de custódia.
                       Ex.: "comprimido", "cápsula", "frasco".

  forma_farmaceutica : apresentação comercial ou galénica declarada pelo
                       prescritor.  Campo livre para contexto clínico; não
                       entra na aritmética de dispensação.
                       Ex.: "caixa com 30 cápsulas", "frasco 100 mL".

NOTA SOBRE SALDO
----------------
A dispensação parcial opera sobre `quantidade` (Integer) + `unidade_quantidade`.
A soma de `dispensacoes.quantidade_dispensada` nunca pode superar
`prescricao_itens.quantidade` — indiferente da apresentação comercial.

EVOLUÇÃO FUTURA
---------------
DEF (Denominação Farmacêutica Brasileira) / GGMED-ANVISA:
  Futuro: substituir texto livre de nome_medicamento por código DEF.
  O vocabulário de unidade_quantidade será derivado do DEF para cada produto.
  Isso permitirá validação automática de unidade × forma × concentração.
"""

from __future__ import annotations

from typing import FrozenSet

from app.domain.retencao import TIPOS_RETENCAO_VALIDOS

# ---------------------------------------------------------------------------
# Vocabulário controlado — unidade de dispensação
# ---------------------------------------------------------------------------

UNIDADES_QUANTIDADE: FrozenSet[str] = frozenset({
    "ampola",
    "bisnaga",
    "caixa",
    "capsula",          # sem acento — normalizado internamente
    "cápsula",
    "comprimido",
    "drágea",
    "dragea",
    "envelope",
    "frasco",
    "frasco-ampola",
    "pastilha",
    "sachê",
    "sache",
    "supositório",
    "supositorio",
    "unidade",
})

# Exibição canônica (normalizada → display)
_DISPLAY_UNIDADE: dict[str, str] = {
    "capsula":      "cápsula",
    "cápsula":      "cápsula",
    "dragea":       "drágea",
    "drágea":       "drágea",
    "sache":        "sachê",
    "sachê":        "sachê",
    "supositorio":  "supositório",
    "supositório":  "supositório",
}

# Lista ordenada para select/dropdown no frontend
UNIDADES_LISTA: list[str] = sorted({
    _DISPLAY_UNIDADE.get(u, u) for u in UNIDADES_QUANTIDADE
})


def normalizar_unidade(unidade: str | None) -> str | None:
    """
    Retorna a forma canônica (com acentos) ou None se inválida.
    Aceita variação sem acento e case-insensitive.
    """
    if not unidade:
        return None
    u = unidade.strip().lower()
    # tenta match direto no frozenset (normalizado)
    if u in {x.lower() for x in UNIDADES_QUANTIDADE}:
        # recupera o display canônico
        for original in UNIDADES_QUANTIDADE:
            if original.lower() == u:
                return _DISPLAY_UNIDADE.get(original, original)
    return None


def unidade_valida(unidade: str | None) -> bool:
    """Retorna True se a unidade pertence ao vocabulário controlado."""
    return normalizar_unidade(unidade) is not None


# ---------------------------------------------------------------------------
# Circulação atomizada — política de elegibilidade (Ticket 44)
# ---------------------------------------------------------------------------

# Classes regulatórias que bloqueiam circulação atomizada.
# Referência: Portaria SVS/MS 344/98 (Listas A, B, C5, D).
CLASSES_CONTROLE_ESPECIAL: FrozenSet[str] = frozenset({
    "A1", "A2", "A3",   # entorpecentes — receituário amarelo (3 vias, retido)
    "B1", "B2",          # psicotrópicos — receituário azul (2 vias, 1 retida)
    "C5",                # antimicrobianos — receita de controle especial (Portaria 2.814/98)
    "D1", "D2",          # retinoides e talidomida — controle especial obrigatório
})

# Estados de item que permitem geração de novo token de circulação.
# Itens em estados terminais ou já em custódia ativa não recebem novo token.
ESTADOS_ITEM_CIRCULAVEIS: FrozenSet[str] = frozenset({
    "pendente",
    "devolvido_paciente",   # abandono de compra — item disponível novamente
})


def eh_item_atomizavel(item: dict, conn=None) -> bool:
    """
    Retorna True se o item pode participar de circulação atomizada.
    Bloqueiam atomização:
      - classe_controle ∈ CLASSES_CONTROLE_ESPECIAL (Portaria 344, T44)
      - tipo_retencao ∈ TIPOS_RETENCAO_VALIDOS (RDC 471/2021, T18)
      - **Salvaguarda T20:** se `conn` é fornecido, consulta também o
        catálogo regulatório — se a substância consta como controlada
        (mesmo que o prescritor não tenha declarado), bloqueia.

    O parâmetro `conn` é OPCIONAL para preservar compatibilidade com
    chamadas existentes. Sem `conn`, o comportamento é idêntico ao
    pré-T20 (apenas campos declarados).
    """
    classe = (item.get("classe_controle") or "").strip().upper()
    if classe in CLASSES_CONTROLE_ESPECIAL:
        return False
    tipo_ret = (item.get("tipo_retencao") or "").strip().lower()
    if tipo_ret in TIPOS_RETENCAO_VALIDOS:
        return False

    # T20 — salvaguarda via catálogo. Import local evita ciclo:
    # catalogo_regulatorio.py não importa medicamento.py.
    if conn is not None:
        from app.domain.catalogo_regulatorio import buscar_substancia_por_nome
        substancia = buscar_substancia_por_nome(item.get("nome_medicamento"), conn)
        if substancia and (substancia.classe_controle or substancia.tipo_retencao):
            return False

    return True


def prescricao_atomizavel(itens: list[dict]) -> tuple[bool, "str | None"]:
    """
    Retorna (True, None) se todos os itens são elegíveis para atomização.
    Retorna (False, motivo) se qualquer item bloqueia a atomização inteira.

    INVARIANTE ARQUITETURAL (docs/CIRCULACAO_ATOMIZADA.md §15.1):
      A atomização é da prescrição inteira — não existe atomização seletiva.
      Um item inelegível bloqueia a prescrição inteira.
    """
    for item in itens:
        motivo = motivo_nao_atomizavel(item)
        if motivo:
            return False, motivo
    return True, None


def motivo_nao_atomizavel(item: dict) -> "str | None":
    """
    Retorna descrição do motivo de inelegibilidade, ou None se o item é elegível.
    """
    classe = (item.get("classe_controle") or "").strip().upper()
    if classe in CLASSES_CONTROLE_ESPECIAL:
        nome = item.get("nome_medicamento") or "(item)"
        return (
            f"'{nome}' — classe de controle especial ({classe}): "
            "requer receituário especial não compatível com circulação atomizada. "
            "Emita uma prescrição separada para este medicamento."
        )
    tipo_ret = (item.get("tipo_retencao") or "").strip().lower()
    if tipo_ret in TIPOS_RETENCAO_VALIDOS:
        nome = item.get("nome_medicamento") or "(item)"
        return (
            f"'{nome}' — sujeito a retenção (RDC 471/2021, {tipo_ret}): "
            "requer receituário com retenção, não compatível com circulação atomizada. "
            "Emita uma prescrição separada para este medicamento."
        )
    return None
