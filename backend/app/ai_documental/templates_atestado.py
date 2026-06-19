"""
templates_atestado.py
=====================
Template estruturado de atestado médico — CFM-aligned.

PRINCÍPIOS
----------
- Linguagem formal padronizada (não livre).
- Campos críticos não podem ser omitidos.
- Nenhuma variação livre permitida neste momento.
- v2: suporte a modalidades (afastamento parcial, restrição de atividade, etc.)

CONFORMIDADE CFM
----------------
A estrutura segue os requisitos mínimos de um atestado médico válido
conforme orientações do Conselho Federal de Medicina (CFM):
  - Identificação do paciente
  - Finalidade do atestado — OBRIGATÓRIA (trabalhista, estudantil, judicial, …):
    não se emite atestado sem finalidade declarada
  - Quadro clínico / CID — OPCIONAL: o diagnóstico só é registrado com
    anuência do paciente; o CFM admite atestado sem CID (privacidade)
  - Período de afastamento explícito em dias
  - Data de emissão
  - Identificação do profissional (nome + registro)
  - Clareza do afastamento (sem ambiguidades)

O atestado gerado é um rascunho base. O profissional é responsável por
revisar, complementar e assinar antes de entregar ao paciente.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Template v2 — finalidade obrigatória; quadro clínico/CID opcionais
# ---------------------------------------------------------------------------
#
# A finalidade é o eixo do atestado ("não se dá atestado sem finalidade").
# O quadro clínico e o CID são opcionais — só entram no texto quando o
# profissional os informa, respeitando a privacidade do diagnóstico.
#
# {clausula_clinica} é montada em Python (montar_clausula_clinica) e pode ser
# vazia, só-CID, só-texto ou texto+CID — daí o template não usar .format() nos
# campos opcionais diretamente.

_TEMPLATE_ATESTADO_V2 = (
    "Atesto, para fins {finalidade}, que {paciente_nome} necessita de "
    "afastamento de suas atividades por {dias_afastamento} dia(s), a contar "
    "desta data{clausula_clinica}.\n\n"
    "{data_documento}\n\n"
    "{nome_profissional}\n"
    "{registro_profissional}"
)

# Metadados do template
VERSAO_TEMPLATE    = "atestado_cfm_v2"
DESCRICAO_TEMPLATE = (
    "Atestado médico estruturado — baseado em estrutura mínima CFM-aligned. "
    "Inclui: identificação do paciente, finalidade (obrigatória), quadro "
    "clínico e CID (opcionais), período de afastamento, data e identificação "
    "profissional."
)

# Documentos planejados para v2 (não implementados neste ticket)
TEMPLATES_PLANEJADOS_V2 = ["declaracao", "relatorio", "laudo"]


# ---------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------

def montar_clausula_clinica(
    indicacao_clinica: Optional[str],
    codigo_cid:        Optional[str],
) -> str:
    """
    Monta o trecho clínico OPCIONAL do atestado, com pontuação limpa.

    Quatro casos:
      - texto + CID → ", em razão de quadro clínico compatível com X (CID: Y)"
      - só texto    → ", em razão de quadro clínico compatível com X"
      - só CID      → " (CID: Y)"
      - nenhum      → "" (atestado sem diagnóstico — privacidade preservada)
    """
    ind = (indicacao_clinica or "").strip()
    cid = (codigo_cid or "").strip()
    if ind and cid:
        return f", em razão de quadro clínico compatível com {ind} (CID: {cid})"
    if ind:
        return f", em razão de quadro clínico compatível com {ind}"
    if cid:
        return f" (CID: {cid})"
    return ""


def renderizar_atestado(
    paciente_nome:        str,
    finalidade:           str,
    dias_afastamento:     int,
    data_documento:       str,
    nome_profissional:    str,
    registro_profissional: str,
    indicacao_clinica:    Optional[str] = None,
    codigo_cid:           Optional[str] = None,
) -> str:
    """
    Renderiza o template de atestado com os dados fornecidos.

    Obrigatórios: paciente_nome, finalidade, dias_afastamento, data_documento,
    nome_profissional, registro_profissional.
    Opcionais: indicacao_clinica, codigo_cid (entram via montar_clausula_clinica).

    Pré-condição: os campos obrigatórios já foram validados por
    validar_atestado(). Não aplica validação adicional — renderização pura.
    """
    return _TEMPLATE_ATESTADO_V2.format(
        finalidade            = finalidade,
        paciente_nome         = paciente_nome,
        dias_afastamento      = dias_afastamento,
        clausula_clinica      = montar_clausula_clinica(indicacao_clinica, codigo_cid),
        data_documento        = data_documento,
        nome_profissional     = nome_profissional,
        registro_profissional = registro_profissional,
    )
