"""
ia_documental.py
================
Função principal da IA Documental v1 — Ticket 35.

PRINCÍPIO CENTRAL
-----------------
  A IA não escreve o atestado — ela garante que o atestado esteja correto.

COMPORTAMENTO
-------------
  - Valida estrutura (campos obrigatórios → bloqueia ok)
  - Alerta sobre texto vago (não-bloqueante)
  - Alerta sobre inconsistência CID ↔ texto (não-bloqueante)
  - Sugere melhorias de redação (não substituição automática)
  - Renderiza documento_base somente quando ok=True

GARANTIAS
---------
  - Stateless: nenhum estado externo, nenhuma gravação em banco
  - Determinístico: mesmo input → mesmo output
  - Explicável: todo alerta e sugestão são rastreáveis às regras que os geraram
  - Nunca diagnóstica: as sugestões são sobre forma, não sobre conteúdo clínico
"""

from __future__ import annotations

from typing import Optional

from app.ai_documental.templates_atestado import (
    VERSAO_TEMPLATE,
    renderizar_atestado,
)
from app.ai_documental.regras_atestado import (
    gerar_sugestoes_redacao,
    verificar_campos_obrigatorios,
    verificar_cid_coerencia,
    verificar_texto_clinico,
)

# ---------------------------------------------------------------------------
# Aviso fixo — obrigatório em toda resposta
# ---------------------------------------------------------------------------

_AVISO_FIXO = (
    "Documento assistido por validação estrutural. "
    "A responsabilidade clínica e legal permanece com o profissional."
)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def validar_atestado(
    paciente_nome:        Optional[str] = None,
    indicacao_clinica:    Optional[str] = None,
    codigo_cid:           Optional[str] = None,
    dias_afastamento:     Optional[int] = None,
    data_documento:       Optional[str] = None,
    nome_profissional:    Optional[str] = None,
    registro_profissional: Optional[str] = None,
) -> dict:
    """
    Valida a estrutura de um atestado médico e retorna resultado explicável.

    Parâmetros
    ----------
    paciente_nome         : Nome completo do paciente.
    indicacao_clinica     : Quadro clínico / hipótese diagnóstica (texto livre).
    codigo_cid            : Código CID-10 escolhido pelo profissional (ex: 'I10').
    dias_afastamento      : Número de dias de afastamento (int > 0).
    data_documento        : Data de emissão (string — ex: '2026-03-24').
    nome_profissional     : Nome do profissional responsável.
    registro_profissional : Registro profissional (ex: 'CRM-PE 12345').

    Retorno
    -------
    ok               → bool  — True somente se todos os campos obrigatórios
                               presentes e válidos (sem faltantes).
    faltantes        → list  — campos ausentes ou inválidos (determinam ok).
    alertas          → list  — avisos não-bloqueantes (texto vago, inconsistência CID).
    sugestoes        → list  — sugestões determinísticas de redação.
    documento_base   → str|None — atestado renderizado (None quando há faltantes).
    aviso            → str  — disclaimer fixo (sempre presente).
    versao_template  → str  — versão do template utilizado.
    """
    dados = {
        "paciente_nome":        paciente_nome,
        "indicacao_clinica":    indicacao_clinica,
        "codigo_cid":           codigo_cid,
        "dias_afastamento":     dias_afastamento,
        "data_documento":       data_documento,
        "nome_profissional":    nome_profissional,
        "registro_profissional": registro_profissional,
    }

    # ------------------------------------------------------------------
    # 1. Campos obrigatórios — determinam ok (bloqueia se faltantes)
    # ------------------------------------------------------------------
    faltantes = verificar_campos_obrigatorios(dados)

    # ------------------------------------------------------------------
    # 2. Alertas de qualidade textual (não-bloqueantes)
    # ------------------------------------------------------------------
    alertas: list = []
    sugestoes: list = []

    indicacao_valida = indicacao_clinica and indicacao_clinica.strip()
    if indicacao_valida:
        alertas.extend(verificar_texto_clinico(indicacao_clinica))   # type: ignore
        sugestoes.extend(
            gerar_sugestoes_redacao(indicacao_clinica, dias_afastamento)  # type: ignore
        )

    # ------------------------------------------------------------------
    # 3. Coerência CID ↔ texto clínico (não-bloqueante, soft dependency)
    #    Só avaliada quando ambos os campos estão presentes e válidos.
    # ------------------------------------------------------------------
    codigo_cid_valido   = codigo_cid and codigo_cid.strip()
    cid_nao_faltante    = "codigo_cid"        not in faltantes
    indic_nao_faltante  = "indicacao_clinica" not in faltantes

    if indicacao_valida and codigo_cid_valido and cid_nao_faltante and indic_nao_faltante:
        alertas.extend(
            verificar_cid_coerencia(indicacao_clinica, codigo_cid)  # type: ignore
        )

    # ------------------------------------------------------------------
    # 4. Documento base — renderizado somente quando sem faltantes
    # ------------------------------------------------------------------
    documento_base: Optional[str] = None
    if not faltantes:
        documento_base = renderizar_atestado(
            paciente_nome         = paciente_nome,        # type: ignore
            indicacao_clinica     = indicacao_clinica,    # type: ignore
            codigo_cid            = codigo_cid,           # type: ignore
            dias_afastamento      = dias_afastamento,     # type: ignore
            data_documento        = data_documento,       # type: ignore
            nome_profissional     = nome_profissional,    # type: ignore
            registro_profissional = registro_profissional, # type: ignore
        )

    return {
        "ok":              len(faltantes) == 0,
        "faltantes":       faltantes,
        "alertas":         alertas,
        "sugestoes":       sugestoes,
        "documento_base":  documento_base,
        "aviso":           _AVISO_FIXO,
        "versao_template": VERSAO_TEMPLATE,
    }
