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
  - Quadro clínico / CID obrigatório (política PicSaúde)
  - Período de afastamento explícito em dias
  - Data de emissão
  - Identificação do profissional (nome + registro)
  - Clareza do afastamento (sem ambiguidades)

O atestado gerado é um rascunho base. O profissional é responsável por
revisar, complementar e assinar antes de entregar ao paciente.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Template v1 — estrutura mínima CFM-aligned
# ---------------------------------------------------------------------------

_TEMPLATE_ATESTADO_V1 = (
    "Atesto, para os devidos fins, que {paciente_nome} encontra-se em "
    "acompanhamento clínico, com quadro compatível com {indicacao_clinica} "
    "(CID: {codigo_cid}), necessitando de afastamento por {dias_afastamento} "
    "dia(s), a contar desta data.\n\n"
    "{data_documento}\n\n"
    "{nome_profissional}\n"
    "{registro_profissional}"
)

# Metadados do template
VERSAO_TEMPLATE    = "atestado_cfm_v1"
DESCRICAO_TEMPLATE = (
    "Atestado médico estruturado — baseado em estrutura mínima CFM-aligned. "
    "Inclui: identificação do paciente, quadro clínico, CID, "
    "período de afastamento, data e identificação profissional."
)

# Documentos planejados para v2 (não implementados neste ticket)
TEMPLATES_PLANEJADOS_V2 = ["declaracao", "relatorio", "laudo"]


# ---------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------

def renderizar_atestado(
    paciente_nome:        str,
    indicacao_clinica:    str,
    codigo_cid:           str,
    dias_afastamento:     int,
    data_documento:       str,
    nome_profissional:    str,
    registro_profissional: str,
) -> str:
    """
    Renderiza o template de atestado com os dados fornecidos.

    Pré-condição: todos os campos já foram validados por validar_atestado().
    Não aplica validação adicional — renderização pura.
    """
    return _TEMPLATE_ATESTADO_V1.format(
        paciente_nome         = paciente_nome,
        indicacao_clinica     = indicacao_clinica,
        codigo_cid            = codigo_cid,
        dias_afastamento      = dias_afastamento,
        data_documento        = data_documento,
        nome_profissional     = nome_profissional,
        registro_profissional = registro_profissional,
    )
