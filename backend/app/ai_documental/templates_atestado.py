"""
templates_atestado.py
=====================
RASCUNHO do atestado — composição da tela de conferência.

Este módulo NÃO escreve mais o texto do atestado. Desde o
TICKET-ATESTADO-RASCUNHO-ESPELHO, o corpo vem de `domain/texto_atestado.py`, a
mesma função que o PDF oficial consome. O que sobra aqui é a **moldura** do
rascunho: título, fecho "local, data" e identificação do profissional.

POR QUE ISSO IMPORTA
--------------------
Antes, havia dois construtores de texto e eles divergiam — o profissional
conferia uma frase na tela e assinava outra no PDF. Não era um documento falso;
era um **falso espelho**, que é pior, porque o profissional confia nele. O
cabeçalho de `domain/texto_atestado.py` documenta o defeito por inteiro.

O RASCUNHO NÃO SE VESTE DE DOCUMENTO
------------------------------------
O título aqui é "Atestado" — genérico de propósito. O título completo
("ATESTADO MÉDICO" / "ATESTADO ODONTOLÓGICO") é marca do documento OFICIAL, que
vem do conselho emissor em `domain/conselho_profissional.py`; reproduzi-lo no
papel de trabalho aproximaria o rascunho justamente daquilo que ele não é.
O CORPO tem de ser idêntico (é o que se confere); a CAPA, não (é o que
distingue). Decisão explícita do Fabiano.

CONFORMIDADE CFM
----------------
A estrutura segue os requisitos mínimos de um atestado válido conforme o
Conselho Federal de Medicina:
  - Identificação do paciente
  - Finalidade — OBRIGATÓRIA (trabalhista, estudantil, judicial, …)
  - Quadro clínico / CID — OPCIONAL: só com anuência do paciente (privacidade)
  - Período de afastamento explícito em dias
  - Local e data de emissão
  - Identificação do profissional (nome + registro)
  - Clareza do afastamento (sem ambiguidades)

O documento gerado é um rascunho base. O profissional é responsável por revisar,
complementar e assinar antes de entregar ao paciente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.domain.conselho_profissional import conselho_ou_padrao, formatar_registro
from app.domain.texto_atestado import (
    Paragrafo,
    Trecho,
    clausula_clinica,
    corpo_atestado,
    formatar_data_br,
    texto_puro,
)

# Título do RASCUNHO — genérico por decisão de projeto (ver docstring do módulo).
TITULO_RASCUNHO = "Atestado"

# Metadados do template
VERSAO_TEMPLATE    = "atestado_cfm_v3"
DESCRICAO_TEMPLATE = (
    "Atestado estruturado — CFM-aligned, com corpo em fonte única compartilhada "
    "com o PDF oficial (domain/texto_atestado.py). Inclui: identificação do "
    "paciente, finalidade (obrigatória), quadro clínico e CID (opcionais), "
    "período de afastamento, horário de comparecimento, observação complementar, "
    "local e data, e identificação profissional com registro formatado."
)

# Documentos planejados para v2 (não implementados neste ticket)
TEMPLATES_PLANEJADOS_V2 = ["declaracao", "relatorio", "laudo"]


@dataclass(frozen=True)
class RascunhoAtestado:
    """Rascunho renderizado nas duas formas que a tela precisa.

    `texto`  — sem marcação: é o que vai para a impressão do papel de trabalho e
               é o valor comparado com o PDF no teste de espelho.
    `html`   — mesma composição com `<strong>` nas ênfases, já escapada pelo
               domínio; a tela insere direto, sem escapar de novo.
    `corpo`  — só o corpo (frase + observação), sem a moldura. É a fatia que o
               PDF também renderiza — a unidade do espelho.
    """

    texto: str
    html: str
    corpo: str


def montar_clausula_clinica(
    indicacao_clinica: Optional[str],
    codigo_cid:        Optional[str],
) -> str:
    """Trecho clínico opcional do atestado.

    Mantida como reexportação da função do domínio: o texto é um só, e quem já
    importava daqui continua importando daqui.
    """
    return clausula_clinica(indicacao_clinica, codigo_cid)


def _moldura(
    municipio_emissao: Optional[str],
    data_documento:    str,
    nome_profissional: str,
    registro_formatado: Optional[str],
) -> list[Paragrafo]:
    """Fecho do rascunho: "local, data" + identificação do profissional.

    O fecho segue a mesma regra do PDF: sem município declarado, a linha
    simplesmente não sai. Melhor a ausência honesta do que um local inventado.
    """
    fim: list[Paragrafo] = []
    municipio = (municipio_emissao or "").strip()
    if municipio:
        fim.append(Paragrafo((Trecho(f"{municipio}, {formatar_data_br(data_documento)}."),)))
    else:
        fim.append(Paragrafo((Trecho(formatar_data_br(data_documento)),)))

    identificacao = nome_profissional
    if registro_formatado:
        identificacao = f"{nome_profissional}\n{registro_formatado}"
    fim.append(Paragrafo((Trecho(identificacao),)))
    return fim


def renderizar_atestado(
    paciente_nome:        str,
    finalidade:           str,
    dias_afastamento:     int,
    data_documento:       str,
    nome_profissional:    str,
    registro_profissional: str,
    indicacao_clinica:    Optional[str] = None,
    codigo_cid:           Optional[str] = None,
    municipio_emissao:    Optional[str] = None,
    conselho:             Optional[str] = None,
    uf_registro:          Optional[str] = None,
    hora_inicio:          Optional[str] = None,
    hora_fim:             Optional[str] = None,
    observacao_complementar: Optional[str] = None,
) -> RascunhoAtestado:
    """Renderiza o rascunho do atestado — moldura + corpo da fonte única.

    O `conselho` (CFM | CFO) decide os adjetivos do corpo e a sigla do registro,
    exatamente como no PDF: um atestado do CFO diz "cuidados odontológicos" e
    identifica o profissional como "CRO-PE 1234". Antes, o rascunho ignorava o
    conselho e dizia "médicos" mesmo para o dentista.

    Pré-condição: os campos obrigatórios já foram validados por
    validar_atestado(). Não aplica validação adicional — renderização pura.
    """
    cons = conselho_ou_padrao(conselho)
    registro_fmt = formatar_registro(conselho, uf_registro, registro_profissional)

    corpo = corpo_atestado(
        nome_paciente=paciente_nome,
        finalidade=finalidade,
        dias_afastamento=dias_afastamento,
        data_documento=data_documento,
        indicacao_clinica=indicacao_clinica,
        codigo_cid=codigo_cid,
        adjetivo_cuidados=cons.adjetivo_cuidados,
        adjetivo_atendimento=cons.adjetivo_atendimento,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        observacao_complementar=observacao_complementar,
    )

    completo: tuple[Paragrafo, ...] = (
        Paragrafo((Trecho(TITULO_RASCUNHO, enfase=True),)),
        *corpo,
        *_moldura(municipio_emissao, data_documento, nome_profissional, registro_fmt),
    )

    return RascunhoAtestado(
        texto=texto_puro(completo),
        html="\n\n".join(p.para_html() for p in completo),
        corpo=texto_puro(corpo),
    )
