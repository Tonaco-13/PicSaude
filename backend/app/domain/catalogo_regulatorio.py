"""
catalogo_regulatorio.py
=======================
Catálogo regulatório de substâncias — Ticket 20.

Propósito
---------
Oráculo de validação para confrontar a classificação declarada pelo
prescritor (`classe_controle` / `tipo_retencao` em `prescricao_itens`)
contra a classificação publicada pela Anvisa.

NÃO é fonte primária — `prescricao_itens.classe_controle` e
`prescricao_itens.tipo_retencao` continuam sendo a fonte-de-verdade
para o roteamento do motor regulatório. O catálogo:

  1. Sugere classificação ao prescritor (autocomplete)
  2. Valida coerência da classificação declarada
  3. Emite alertas (info / warning / critical) — NÃO bloqueia em fase 1

Princípio de cautela (catálogo parcial)
---------------------------------------
A ausência de uma substância no catálogo NÃO é prova de que ela é
livre — é prova de que o catálogo ainda não a tem. O catálogo é
incremental: alertar agressivamente quando há divergência, MAS
permanecer silencioso quando a substância é desconhecida.

Severidade dos alertas
----------------------
- info     — informativo (não usado em fase 1)
- warning  — divergência em substância controlada por classe (Portaria 344)
- critical — divergência em substância de retenção (RDC 471) ou ausência
             completa de classificação para substância controlada
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional


# ---------------------------------------------------------------------------
# Vocabulário de severidade
# ---------------------------------------------------------------------------

Severidade = Literal["info", "warning", "critical"]

# Ordem para escalonamento (max de severidade entre alertas).
_ORDEM_SEVERIDADE = {"info": 0, "warning": 1, "critical": 2}


def _max_severidade(*severidades: Severidade) -> Severidade:
    if not severidades:
        return "info"
    return max(severidades, key=lambda s: _ORDEM_SEVERIDADE[s])


# ---------------------------------------------------------------------------
# Normalização de DCB
# ---------------------------------------------------------------------------

# Regex para colapsar espaços em torno de "+" e múltiplos espaços.
_RE_PLUS = re.compile(r"\s*\+\s*")
_RE_SPACES = re.compile(r"\s+")


def normalizar_dcb(dcb: str) -> str:
    """Normaliza DCB para lookup e unicidade.

    Regras:
      - Strip de espaços nas extremidades
      - Lowercase
      - Remove acentos (NFD + strip combining marks)
      - Padroniza separador de combinações: " + " (espaços simples ao redor)
      - Colapsa espaços múltiplos para espaço único

    Exemplos:
        normalizar_dcb("Amoxicilina")                   == "amoxicilina"
        normalizar_dcb("Sulfametoxazol+Trimetoprima")   == "sulfametoxazol + trimetoprima"
        normalizar_dcb("Amoxicilina + Clavulanato")     == "amoxicilina + clavulanato"
        normalizar_dcb("  Isotretinoína  ")             == "isotretinoina"
    """
    if dcb is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(dcb))
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    resultado = sem_acentos.strip().lower()
    resultado = _RE_PLUS.sub(" + ", resultado)
    resultado = _RE_SPACES.sub(" ", resultado)
    return resultado


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubstanciaCatalogo:
    """Snapshot imutável de uma substância do catálogo, para uso pela
    aplicação. Não persiste nada — é o formato de retorno dos lookups.
    """
    dcb: str
    dcb_display: str
    classe_controle: Optional[str]
    tipo_retencao: Optional[str]
    fonte: str
    observacao: Optional[str] = None


@dataclass
class AlertaRegulatorio:
    """Alerta sobre divergência entre classificação declarada pelo
    prescritor e o catálogo regulatório."""
    severidade: Severidade
    mensagem: str
    sugestao_classe: Optional[str] = None
    sugestao_tipo_retencao: Optional[str] = None


@dataclass
class ResultadoValidacaoCatalogo:
    """Resultado de validar a classificação de UM item de prescrição
    contra o catálogo. Coerente=True implica `alertas == []`."""
    substancia_encontrada: bool
    classificacao_coerente: bool
    alertas: list[AlertaRegulatorio] = field(default_factory=list)
    severidade: Severidade = "info"
    sugestao_classe: Optional[str] = None
    sugestao_tipo_retencao: Optional[str] = None
    substancia: Optional[SubstanciaCatalogo] = None


# ---------------------------------------------------------------------------
# Acesso a dados (queries SQL agnósticas — usam `conn` no padrão do projeto)
# ---------------------------------------------------------------------------

def _row_to_substancia(row: dict) -> SubstanciaCatalogo:
    return SubstanciaCatalogo(
        dcb=row["dcb_normalizada"],
        dcb_display=row.get("dcb_display") or row.get("dcb") or row["dcb_normalizada"],
        classe_controle=row.get("classe_controle"),
        tipo_retencao=row.get("tipo_retencao"),
        fonte=row.get("fonte") or "",
        observacao=row.get("observacao"),
    )


def _row_dict(row) -> dict:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def buscar_substancia(dcb: str, conn) -> Optional[SubstanciaCatalogo]:
    """Lookup direto por DCB normalizada. Retorna None se não houver
    substância ATIVA com esse DCB."""
    norm = normalizar_dcb(dcb)
    if not norm:
        return None
    row = conn.execute(
        """
        SELECT dcb_normalizada, dcb_display, classe_controle,
               tipo_retencao, fonte, observacao
          FROM catalogo_substancias
         WHERE dcb_normalizada = ?
           AND ativo = TRUE
        """,
        (norm,),
    ).fetchone()
    if not row:
        return None
    return _row_to_substancia(_row_dict(row))


def buscar_substancia_por_nome(
    nome_medicamento: Optional[str],
    conn,
) -> Optional[SubstanciaCatalogo]:
    """Heurística para o caso de `nome_medicamento` ser declarado pelo
    prescritor (que pode ter dosagem, marca, etc.). Tenta:

      1. Match exato pela DCB normalizada do nome inteiro
      2. Match exato pela primeira palavra do nome (caso típico:
         "Amoxicilina 500mg" → DCB = "amoxicilina")

    Retorna o primeiro match. Não tenta fuzzy matching (reservado para
    o autocomplete via `buscar_substancias_similar`).
    """
    if not nome_medicamento:
        return None
    inteiro = buscar_substancia(nome_medicamento, conn)
    if inteiro is not None:
        return inteiro
    norm = normalizar_dcb(nome_medicamento)
    if not norm:
        return None
    primeira_palavra = norm.split(" ")[0]
    if primeira_palavra and primeira_palavra != norm:
        return buscar_substancia(primeira_palavra, conn)
    return None


def buscar_substancias_similar(
    termo: str,
    conn,
    *,
    limit: int = 10,
) -> list[SubstanciaCatalogo]:
    """Busca por prefixo ILIKE para autocomplete. Substâncias ativas,
    ordenadas alfabeticamente, limit cap em 20."""
    norm = normalizar_dcb(termo)
    if not norm:
        return []
    limit = max(1, min(int(limit), 20))
    rows = conn.execute(
        """
        SELECT dcb_normalizada, dcb_display, classe_controle,
               tipo_retencao, fonte, observacao
          FROM catalogo_substancias
         WHERE ativo = TRUE
           AND dcb_normalizada LIKE ?
         ORDER BY dcb_normalizada ASC
         LIMIT ?
        """,
        (norm + "%", limit),
    ).fetchall()
    return [_row_to_substancia(_row_dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Validação cruzada
# ---------------------------------------------------------------------------

def _normaliza_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _tipos_retencao_validos() -> frozenset[str]:
    # Import local para evitar ciclo se algum módulo importar este antes do
    # bootstrap do retencao.py.
    from app.domain.retencao import TIPOS_RETENCAO_VALIDOS
    return TIPOS_RETENCAO_VALIDOS


def validar_classificacao(
    substancia: Optional[SubstanciaCatalogo],
    classe_declarada: Optional[str],
    tipo_retencao_declarado: Optional[str],
    *,
    nome_para_msg: str = "(item)",
) -> ResultadoValidacaoCatalogo:
    """Confronta a classificação declarada pelo prescritor com o catálogo.

    Cenários:
      - Substância não encontrada → coerente=True, sem alertas
        (catálogo parcial não deve gerar falsos positivos).
      - Substância encontrada e classificação bate → coerente=True.
      - Substância encontrada com classe Portaria 344 mas declarada vazia
        ou diferente → alerta WARNING (clínico pode ter errado o código,
        mas declaração da Portaria 344 não tem efeito de retenção tão
        crítico quanto RDC 471).
      - Substância encontrada com tipo_retencao mas declarada vazia ou
        diferente → alerta CRITICAL (risco: emissão como receita simples
        para item que exige retenção).
    """
    classe_decl = _normaliza_str(classe_declarada)
    classe_decl_up = classe_decl.upper() if classe_decl else None

    tipo_decl = _normaliza_str(tipo_retencao_declarado)
    tipo_decl_low = tipo_decl.lower() if tipo_decl else None

    # 1. Substância não encontrada → não emitir alerta (cautela)
    if substancia is None:
        return ResultadoValidacaoCatalogo(
            substancia_encontrada=False,
            classificacao_coerente=True,
        )

    alertas: list[AlertaRegulatorio] = []

    # 2. Verificar classe_controle (Portaria 344)
    classe_cat = (substancia.classe_controle or "").strip().upper() or None
    if classe_cat:
        if classe_decl_up != classe_cat:
            if classe_decl_up is None:
                alertas.append(AlertaRegulatorio(
                    severidade="warning",
                    mensagem=(
                        f"'{nome_para_msg}' consta no catálogo como classe "
                        f"{classe_cat} (Portaria 344/1998) mas classe_controle "
                        f"não foi informada."
                    ),
                    sugestao_classe=classe_cat,
                ))
            else:
                alertas.append(AlertaRegulatorio(
                    severidade="warning",
                    mensagem=(
                        f"'{nome_para_msg}' foi declarado como classe "
                        f"{classe_decl_up}, mas catálogo indica classe "
                        f"{classe_cat} (Portaria 344/1998)."
                    ),
                    sugestao_classe=classe_cat,
                ))

    # 3. Verificar tipo_retencao (RDC 471)
    tipo_cat = (substancia.tipo_retencao or "").strip().lower() or None
    if tipo_cat:
        if tipo_decl_low != tipo_cat:
            if tipo_decl_low is None:
                alertas.append(AlertaRegulatorio(
                    severidade="critical",
                    mensagem=(
                        f"'{nome_para_msg}' consta no catálogo como "
                        f"{tipo_cat} (RDC 471/2021) mas tipo_retencao não "
                        f"foi informado. Risco: emissão como receita simples "
                        f"para item sujeito a retenção."
                    ),
                    sugestao_tipo_retencao=tipo_cat,
                ))
            else:
                alertas.append(AlertaRegulatorio(
                    severidade="critical",
                    mensagem=(
                        f"'{nome_para_msg}' foi declarado como tipo_retencao "
                        f"'{tipo_decl_low}', mas catálogo indica '{tipo_cat}' "
                        f"(RDC 471/2021)."
                    ),
                    sugestao_tipo_retencao=tipo_cat,
                ))

    # 4. Validar que tipo_retencao declarado é vocabulário aceito
    if tipo_decl_low and tipo_decl_low not in _tipos_retencao_validos():
        alertas.append(AlertaRegulatorio(
            severidade="critical",
            mensagem=(
                f"'{nome_para_msg}' tem tipo_retencao '{tipo_decl_low}' "
                f"fora do vocabulário aceito (TIPOS_RETENCAO_VALIDOS)."
            ),
        ))

    coerente = len(alertas) == 0
    severidade_max: Severidade = (
        _max_severidade(*(a.severidade for a in alertas)) if alertas else "info"
    )
    sugestao_classe = next(
        (a.sugestao_classe for a in alertas if a.sugestao_classe), None,
    )
    sugestao_tipo_retencao = next(
        (a.sugestao_tipo_retencao for a in alertas if a.sugestao_tipo_retencao),
        None,
    )

    return ResultadoValidacaoCatalogo(
        substancia_encontrada=True,
        classificacao_coerente=coerente,
        alertas=alertas,
        severidade=severidade_max,
        sugestao_classe=sugestao_classe,
        sugestao_tipo_retencao=sugestao_tipo_retencao,
        substancia=substancia,
    )


# ---------------------------------------------------------------------------
# Validação em batch (para integração no /gerar)
# ---------------------------------------------------------------------------

@dataclass
class AlertaItemPrescricao:
    """Alerta com referência ao item da prescrição que o originou."""
    item_id: int
    nome_medicamento: str
    severidade: Severidade
    mensagem: str
    sugestao_classe: Optional[str] = None
    sugestao_tipo_retencao: Optional[str] = None


def validar_itens_prescricao(
    itens: Iterable[dict],
    conn,
) -> list[AlertaItemPrescricao]:
    """Valida cada item da prescrição contra o catálogo. Retorna a lista
    achatada de todos os alertas (com referência ao item de origem).

    Itens passam quando:
      - Substância não encontrada no catálogo (catálogo parcial), OU
      - Substância encontrada e classificação bate.

    Cada divergência gera 1 ou mais `AlertaItemPrescricao` com severidade.
    """
    out: list[AlertaItemPrescricao] = []
    for item in itens:
        nome = item.get("nome_medicamento") or ""
        substancia = buscar_substancia_por_nome(nome, conn)
        resultado = validar_classificacao(
            substancia,
            classe_declarada=item.get("classe_controle"),
            tipo_retencao_declarado=item.get("tipo_retencao"),
            nome_para_msg=nome or "(item)",
        )
        for alerta in resultado.alertas:
            out.append(AlertaItemPrescricao(
                item_id=int(item.get("id") or 0),
                nome_medicamento=nome,
                severidade=alerta.severidade,
                mensagem=alerta.mensagem,
                sugestao_classe=alerta.sugestao_classe,
                sugestao_tipo_retencao=alerta.sugestao_tipo_retencao,
            ))
    return out
