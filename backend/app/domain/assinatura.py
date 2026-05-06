"""
assinatura.py
=============
Fonte de verdade canônica para modos de assinatura e níveis de validade
formal de prescrições no PicSaúde.

CONTEXTO REGULATÓRIO
--------------------
A Resolução CFM 2.299/2021 exige que prescrições médicas digitais sejam
assinadas com certificado digital ICP-Brasil ou pelo serviço gov.br para
ter validade jurídica e clínica plena.

O PicSaúde distingue dois perfis de uso da prescrição digital:

  Prescrição operacional
    Rastreada no sistema de custódia, mas sem pretensão declarada de validade
    formal CFM. Caso de uso: sistemas hospitalares com fluxo interno onde a
    assinatura eletrônica simples é suficiente operacionalmente.
    Nível formal resultante: "operacional".

  Prescrição com pretensão de validade CFM
    Declara assinatura ICP-Brasil (token A1/A3) ou assinatura gov.br em nuvem.
    Exige campos obrigatórios da resolução: posologia e quantidade em todos os
    itens, CPF real do paciente (não sentinela).
    Nível formal resultante: "cfm_pendente" ou "cfm_gov_br_pendente".
    Nota MVP: o hash criptográfico da assinatura ainda não é armazenado.
    A coluna assinatura_hash será introduzida na migração para PostgreSQL.

MODOS DE ASSINATURA (assinatura_modo em prescricoes)
-----------------------------------------------------
  icp_brasil_local    Certificado digital ICP-Brasil, token A1/A3 local.
                      Modo de produção atual. MVP: hash não armazenado.
  gov_br_nuvem        Assinatura em nuvem gov.br. Em implantação.
  fisica              Impressão em papel sem cadeia digital.
                      Não é armazenado em assinatura_modo; inferido pelo
                      endpoint POST /prescricoes/fisica e pelo status
                      encerrada_localmente.

GOVERNANÇA
----------
Novos modos de assinatura devem ser adicionados a este arquivo, ao DDL
em docs/picsaude_ddl_postgres_v1.sql e à seção "Modelo de Assinatura" de
docs/ARQUITETURA.md.
"""

from __future__ import annotations

from typing import FrozenSet, Literal

# ---------------------------------------------------------------------------
# Tipos e constantes canônicas
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tipos de certificado aceitos em prescricao_assinatura.tipo_certificado
# ---------------------------------------------------------------------------

TipoCertificado = Literal["A1", "A3", "gov_br_nuvem"]

TIPOS_CERTIFICADO_VALIDOS: FrozenSet[str] = frozenset({"A1", "A3", "gov_br_nuvem"})


# ---------------------------------------------------------------------------
# Status de validação da assinatura  (prescricao_assinatura.status_validacao)
# ---------------------------------------------------------------------------

StatusAssinatura = Literal[
    "assinatura_pendente",    # metadados recebidos, validação ICP-Brasil ainda não realizada (MVP)
    "assinada_valida",        # assinatura criptograficamente verificada (pós-MVP)
    "assinada_invalida",      # assinatura falhou na verificação (pós-MVP)
    "certificado_expirado",   # certificado expirado no momento da assinatura (pós-MVP)
    "revogada",               # certificado estava revogado (pós-MVP)
]

# Frozenset para validação em runtime
STATUS_ASSINATURA_VALIDOS: FrozenSet[str] = frozenset({
    "assinatura_pendente",
    "assinada_valida",
    "assinada_invalida",
    "certificado_expirado",
    "revogada",
})

# Status que indicam assinatura formalmente válida
STATUS_ASSINATURA_VALIDA: FrozenSet[str] = frozenset({"assinada_valida"})

# Status terminais (não transitam mais)
STATUS_ASSINATURA_TERMINAIS: FrozenSet[str] = frozenset({
    "assinada_valida",
    "assinada_invalida",
    "certificado_expirado",
    "revogada",
})

# Descrições legíveis para exibição / logs
DESCRICAO_STATUS_ASSINATURA: dict[str, str] = {
    "assinatura_pendente":  "Metadados registrados. Validação ICP-Brasil pendente (MVP stub).",
    "assinada_valida":      "Assinatura digital criptograficamente verificada.",
    "assinada_invalida":    "Assinatura falhou na verificação criptográfica.",
    "certificado_expirado": "Certificado digital estava expirado no momento da assinatura.",
    "revogada":             "Certificado digital estava revogado (CRL/OCSP).",
}

ModoAssinatura = Literal["icp_brasil_local", "gov_br_nuvem"]

# Todos os valores aceitos em prescricoes.assinatura_modo (NULL = operacional)
MODOS_DIGITAIS_VALIDOS: FrozenSet[str] = frozenset({"icp_brasil_local", "gov_br_nuvem"})

# Modos que implicam pretensão de validade formal CFM
MODOS_COM_VALIDADE_CFM: FrozenSet[str] = frozenset({"icp_brasil_local", "gov_br_nuvem"})

# Modos em operação produtiva (os demais são "em implantação")
MODOS_EM_PRODUCAO: FrozenSet[str] = frozenset({"icp_brasil_local"})

# Modos que ainda não têm integração ativa com provedor externo
MODOS_EM_IMPLANTACAO: FrozenSet[str] = frozenset({"gov_br_nuvem"})


# ---------------------------------------------------------------------------
# Nível de validade formal
# Calculado na camada de aplicação — NÃO armazenado no banco nesta versão.
# ---------------------------------------------------------------------------

NivelFormal = Literal[
    "fisica",               # papel, sem ciclo digital
    "operacional",          # digital sem pretensão CFM (assinatura_modo NULL)
    "cfm_pendente",         # declara ICP-Brasil; hash não armazenado (MVP)
    "cfm_gov_br_pendente",  # declara gov.br; módulo em implantação
]

DESCRICAO_NIVEL_FORMAL: dict[str, str] = {
    "fisica":              "Emissão exclusivamente em papel. Sem cadeia digital.",
    "operacional":         "Prescrição rastreada digitalmente. Sem pretensão de validade CFM.",
    "cfm_pendente":        "Declara assinatura ICP-Brasil (token A1/A3). Hash não armazenado (MVP).",
    "cfm_gov_br_pendente": "Declara assinatura gov.br em nuvem. Módulo em implantação.",
}


# ---------------------------------------------------------------------------
# Campos obrigatórios por nível — referência normativa
# (aplicados como validação em prescricoes.py para MODOS_COM_VALIDADE_CFM)
# ---------------------------------------------------------------------------

# Campos da Resolução CFM 2.299/2021 exigidos para prescrições digitais válidas.
# Prescritor
CAMPOS_CFM_PRESCRITOR: FrozenSet[str] = frozenset({
    "cns_prescritor",   # identificação única do prescritor
    "nome_prescritor",  # nome completo para impressão/visualização
})

# Paciente — CPF real obrigatório (não pode ser o sentinela 00000000000)
CAMPOS_CFM_PACIENTE: FrozenSet[str] = frozenset({
    "cpf_paciente",     # CPF válido (não sentinela)
    "nome_paciente",    # nome completo
})

# Por item terapêutico
CAMPOS_CFM_ITEM: FrozenSet[str] = frozenset({
    "nome_medicamento",   # denominação genérica ou comercial
    "quantidade",         # quantidade prescrita (inteiro positivo)
    "unidade_quantidade", # unidade do vocabulário controlado (ex: "comprimido", "cápsula")
    "posologia",          # instruções de uso completas
})


# ---------------------------------------------------------------------------
# Helper: calcular nivel_formal
# ---------------------------------------------------------------------------

def calcular_nivel_formal(
    assinatura_modo: str | None,
    tipo_emissao: str | None = None,
) -> str:
    """
    Retorna o NivelFormal correspondente ao modo de assinatura e tipo de emissão.

    Regras (em ordem de precedência):
      1. tipo_emissao == 'fisica'  →  'fisica'
      2. assinatura_modo is None   →  'operacional'
      3. 'icp_brasil_local'        →  'cfm_pendente'
      4. 'gov_br_nuvem'            →  'cfm_gov_br_pendente'
      5. qualquer outro            →  'operacional'
    """
    if tipo_emissao == "fisica":
        return "fisica"
    if assinatura_modo is None:
        return "operacional"
    if assinatura_modo == "icp_brasil_local":
        return "cfm_pendente"
    if assinatura_modo == "gov_br_nuvem":
        return "cfm_gov_br_pendente"
    return "operacional"


# ---------------------------------------------------------------------------
# Helper: verificar campos CFM ausentes em um item
# ---------------------------------------------------------------------------

def campos_cfm_ausentes_no_item(item: object) -> list[str]:
    """
    Retorna lista de campos de CAMPOS_CFM_ITEM ausentes ou vazios num ItemIn.
    Usado na validação de prescrições com pretensão de validade CFM.
    """
    ausentes = []
    for campo in sorted(CAMPOS_CFM_ITEM):
        valor = getattr(item, campo, None)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            ausentes.append(campo)
    return ausentes
