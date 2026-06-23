"""
routers/ia.py
=============
Endpoints da camada de IA do PicSaúde — v1.

PRINCÍPIOS
----------
  - Consulta pura: nenhum endpoint grava em DB, chama custódia ou ledger.
  - Stateless: cada request é independente.
  - Autenticado: prescritor | dispensador | admin (nunca público).
  - Não bloqueante: retorna sugestões e alertas, nunca impede fluxo clínico.

ROTAS
-----
  POST /ia/medicamentos/sugerir   ← sugestão farmacológica stateless
  POST /ia/exames/normalizar      ← normalização TUSS stateless
  POST /ia/cid/buscar             ← busca CID stateless (Ticket 33)
  GET  /ia/cid/status             ← status da base CID
  GET  /ia/status                 ← diagnóstico de todas as bases carregadas
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.config import PICSAUDE_DECISAO_CLINICA
from app.ai.ia_farmaceutica import sugerir_medicamento
from app.ai.lookup_def import tamanho_base, versao_base as _versao_base, buscar_medicamentos
from app.ai.apresentacoes_comerciais import apresentacoes_comerciais
from app.ai.ia_exames import normalizar_exame
from app.ai.tuss_base import BASE_TUSS
from app.ai.ia_cid import buscar_cid as _buscar_cid
from app.ai.base_cid import BASE_CID
from app.ai_documental.ia_documental import validar_atestado as _validar_atestado
from app.ai_documental.templates_atestado import (
    VERSAO_TEMPLATE as _VERSAO_TEMPLATE_ATESTADO,
    DESCRICAO_TEMPLATE as _DESCRICAO_TEMPLATE_ATESTADO,
    TEMPLATES_PLANEJADOS_V2 as _TEMPLATES_V2,
)


router = APIRouter(prefix="/ia", tags=["ia"])

_CONTEXTOS_FARMA  = {"prescricao", "dispensacao"}
_CONTEXTOS_EXAMES = {"pedido_exame", "laudo"}
_CONTEXTOS_CID    = {"pedido_exame", "prescricao", "laudo", "geral"}

# Versão das regras do módulo documental (usada em GET /ia/documentos/status)
_VERSAO_REGRAS_DOCUMENTAL = "atestado_cfm_v2"


# ---------------------------------------------------------------------------
# Schema de entrada
# ---------------------------------------------------------------------------

class SugerirMedicamentoIn(BaseModel):
    nome_medicamento:   str
    forma_farmaceutica: Optional[str] = None
    unidade_quantidade: Optional[str] = None
    contexto:           str = "prescricao"

    @field_validator("nome_medicamento")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_medicamento não pode ser vazio.")
        return v.strip()

    @field_validator("contexto")
    @classmethod
    def contexto_valido(cls, v: str) -> str:
        if v not in _CONTEXTOS_FARMA:
            raise ValueError(
                f"contexto inválido: '{v}'. Valores aceitos: {sorted(_CONTEXTOS_FARMA)}"
            )
        return v


# ---------------------------------------------------------------------------
# POST /ia/medicamentos/sugerir
# ---------------------------------------------------------------------------

@router.post(
    "/medicamentos/sugerir",
    summary="Sugestão farmacológica stateless (IA v1)",
    response_description="Sugestão de forma, unidade e alertas de incoerência",
)
def sugerir(
    payload: SugerirMedicamentoIn,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """
    Consulta a IA farmacêutica v1 e retorna sugestões para o item informado.

    **O que este endpoint faz:**
    - Normaliza o nome do medicamento.
    - Busca na base local DEF (lookup exato, alias ou aproximado).
    - Aplica regras determinísticas (forma → unidade, incoerências clínicas).
    - Retorna sugestões com metadados de rastreabilidade.

    **O que este endpoint NÃO faz:**
    - Não grava nada no banco de dados.
    - Não altera prescrições, itens, custódia ou ledger.
    - Não bloqueia emissão ou dispensação.
    - Não usa LLM nem ML generativo.

    **Campos de rastreabilidade retornados:**
    - `match_tipo`: exato | alias | aproximado | regra | nenhum
    - `score`: confiança do match (0.0–1.0)
    - `fonte`: origem da sugestão
    - `versao_base`: versão da base farmacêutica consultada
    """
    return sugerir_medicamento(
        nome_medicamento   = payload.nome_medicamento,
        forma_farmaceutica = payload.forma_farmaceutica,
        unidade_quantidade = payload.unidade_quantidade,
        contexto           = payload.contexto,
    )


# ---------------------------------------------------------------------------
# POST /ia/medicamentos/buscar  — autocomplete multi-resultado (stateless)
# ---------------------------------------------------------------------------

class BuscarMedicamentoIn(BaseModel):
    termo:          str
    max_resultados: int = 8

    @field_validator("termo")
    @classmethod
    def termo_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("termo não pode ser vazio.")
        return v.strip()


@router.post(
    "/medicamentos/buscar",
    summary="Busca multi-resultado de medicamentos (autocomplete)",
    response_description="Lista de candidatos da base ANVISA/CMED",
)
def buscar_medicamentos_endpoint(
    payload: BuscarMedicamentoIn,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """Autocomplete farmacêutico: retorna até N candidatos da base local
    (ANVISA/CMED), ordenados por score. Stateless — não grava nada, não usa LLM."""
    limite = max(1, min(payload.max_resultados, 20))
    medicamentos = buscar_medicamentos(payload.termo, limite)
    return {
        "medicamentos": medicamentos,
        "total":        len(medicamentos),
        "versao_base":  _versao_base(),
    }


# ---------------------------------------------------------------------------
# POST /ia/medicamentos/apresentacoes — embalagens comerciais (opcional, CMED)
# ---------------------------------------------------------------------------

class ApresentacoesIn(BaseModel):
    principio_ativo: str
    concentracao:    str = ""
    forma:           str

    @field_validator("principio_ativo", "forma")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("campo obrigatório não pode ser vazio.")
        return v.strip()


@router.post(
    "/medicamentos/apresentacoes",
    summary="Apresentações comerciais (embalagens reais da CMED) — opcional",
    response_description="Lista de embalagens (ex.: 'caixa com 30 comprimidos')",
)
def apresentacoes_endpoint(
    payload: ApresentacoesIn,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """Embalagens reais da CMED para o medicamento (princípio ativo · concentração ·
    forma) escolhido no autocomplete. Stateless. Campo opcional — a prescrição
    padrão é por quantidade total (genérico)."""
    return {
        "apresentacoes": apresentacoes_comerciais(
            payload.principio_ativo, payload.concentracao, payload.forma
        ),
    }


# ---------------------------------------------------------------------------
# Schema de entrada — exames
# ---------------------------------------------------------------------------

class NormalizarExameIn(BaseModel):
    nome_exame: str
    contexto:   str = "pedido_exame"

    @field_validator("nome_exame")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_exame não pode ser vazio.")
        return v.strip()

    @field_validator("contexto")
    @classmethod
    def contexto_valido(cls, v: str) -> str:
        if v not in _CONTEXTOS_EXAMES:
            raise ValueError(
                f"contexto inválido: '{v}'. Valores aceitos: {sorted(_CONTEXTOS_EXAMES)}"
            )
        return v


# ---------------------------------------------------------------------------
# POST /ia/exames/normalizar
# ---------------------------------------------------------------------------

@router.post(
    "/exames/normalizar",
    summary="Normalização TUSS stateless (IA v1)",
    response_description="Código TUSS sugerido, preparo e alertas de rastreabilidade",
)
def normalizar(
    payload: NormalizarExameIn,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """
    Consulta a IA de exames v1 e retorna o código TUSS sugerido.

    **O que este endpoint faz:**
    - Normaliza o nome do exame (lowercase, sem acentos, expande abreviações).
    - Busca na base TUSS local (lookup exato, alias ou fuzzy).
    - Retorna código TUSS, preparo do paciente e alertas.

    **O que este endpoint NÃO faz:**
    - Não grava nada no banco de dados.
    - Não altera pedidos de exame, laudos, custódia ou ledger.
    - Não bloqueia emissão.
    - Não usa LLM nem ML generativo.

    **Campos de rastreabilidade retornados:**
    - `match_tipo`: exato | alias | aproximado | nenhum
    - `score`: confiança do match (0.0–1.0)
    - `versao_base`: versão da base TUSS consultada
    """
    return normalizar_exame(
        nome_exame = payload.nome_exame,
        contexto   = payload.contexto,
    )


# ---------------------------------------------------------------------------
# GET /ia/status
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Status da base farmacêutica carregada",
)
def status_ia(
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """
    Retorna diagnóstico da base farmacêutica local.

    Útil para validar se a base foi carregada corretamente e qual versão está ativa.
    """
    n      = tamanho_base()
    versao = _versao_base()
    return {
        "farmaceutica": {
            "base_carregada":  n > 0,
            "total_registros": n,
            "versao_base":     versao,
            "fonte":           "DEF/BASE_LOCAL",
            "modelo":          "lookup + regras (v1 — sem ML)",
            "aviso_base":      "Subset MVP (41 medicamentos). Será expandido para top-200 RENAME em GFI #62.",
        },
        "exames": {
            "base_carregada":  BASE_TUSS.total > 0,
            "total_registros": BASE_TUSS.total,
            "versao_base":     BASE_TUSS.versao,
            "fonte":           "TUSS/BASE_LOCAL",
            "modelo":          "lookup + fuzzy (v1 — sem ML)",
        },
        "cid": {
            "base_carregada":  BASE_CID.total > 0,
            "total_registros": BASE_CID.total,
            "versao_base":     BASE_CID.versao,
            "fonte":           "CID10/BASE_LOCAL",
            "modelo":          "lookup + fuzzy (v1 — sem ML)",
            "aviso_base":      "Subset representativo MVP (~240 códigos). Substituir por tabela DATASUS completa na v2.",
        },
    }


# ---------------------------------------------------------------------------
# Schema de entrada — CID
# ---------------------------------------------------------------------------

class BuscarCidIn(BaseModel):
    texto_clinico: str
    contexto:      str = "geral"

    @field_validator("texto_clinico")
    @classmethod
    def texto_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("texto_clinico não pode ser vazio.")
        return v.strip()

    @field_validator("contexto")
    @classmethod
    def contexto_valido(cls, v: str) -> str:
        if v not in _CONTEXTOS_CID:
            raise ValueError(
                f"contexto inválido: '{v}'. Valores aceitos: {sorted(_CONTEXTOS_CID)}"
            )
        return v


# ---------------------------------------------------------------------------
# POST /ia/cid/buscar
# ---------------------------------------------------------------------------

@router.post(
    "/cid/buscar",
    summary="Busca CID assistida stateless (IA v1)",
    response_description="Lista de sugestões CID com metadados de rastreabilidade",
)
def buscar_cid_endpoint(
    payload: BuscarCidIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Consulta a IA CID v1 e retorna sugestões de códigos CID para o texto informado.

    **O que este endpoint faz:**
    - Normaliza o texto clínico livre (coloquial → vocabulário clínico).
    - Busca na base CID-10 local (lookup exato, alias, fuzzy).
    - Retorna lista ordenada de sugestões com código, descrição e metadados.

    **O que este endpoint NÃO faz:**
    - Não diagnostica.
    - Não escolhe CID automaticamente.
    - Não grava nada no banco de dados.
    - Não altera `indicacao_clinica` de nenhum objeto clínico.
    - Não usa LLM nem ML generativo.

    **Campos de rastreabilidade retornados:**
    - `match_tipo`: exato | alias | aproximado
    - `score`: confiança do match (0.75–1.0)
    - `fonte`: origem da base
    - `versao_base`: versão da base CID consultada
    """
    return _buscar_cid(
        texto_clinico = payload.texto_clinico,
        contexto      = payload.contexto,
    )


# ---------------------------------------------------------------------------
# GET /ia/cid/status
# ---------------------------------------------------------------------------

@router.get(
    "/cid/status",
    summary="Status da base CID carregada",
)
def status_cid(
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Retorna diagnóstico da base CID-10 local.

    Útil para validar se a base foi carregada corretamente e qual versão está ativa.
    """
    return {
        "base_carregada":  BASE_CID.total > 0,
        "total_registros": BASE_CID.total,
        "versao_base":     BASE_CID.versao,
        "fonte":           "CID10/BASE_LOCAL",
        "modelo":          "lookup + fuzzy (v1 — sem ML)",
        "aviso_base": (
            "Subset representativo MVP (~240 códigos CID-10). "
            "Tabela oficial DATASUS (~14.000 subcategorias) deve substituir na v2. "
            "Fonte: http://tabnet.datasus.gov.br"
        ),
    }


# ---------------------------------------------------------------------------
# Ticket 35 — IA Documental v1
# ---------------------------------------------------------------------------
# Schema de entrada — atestado
# ---------------------------------------------------------------------------

class ValidarAtestadoIn(BaseModel):
    """
    Campos do atestado médico a ser validado.

    Todos os campos são opcionais no schema Pydantic — a validação de
    presença/validade é feita por validar_atestado() dentro do módulo
    ai_documental, que retorna 'faltantes' em vez de rejeitar a request.

    Isso permite que o frontend submeta o formulário parcialmente preenchido
    e receba feedback estruturado (quais campos faltam), sem erro 422.
    """
    paciente_nome:        Optional[str] = None
    finalidade:           Optional[str] = None   # obrigatória na validação de domínio
    indicacao_clinica:    Optional[str] = None   # opcional (privacidade do diagnóstico)
    codigo_cid:           Optional[str] = None   # opcional
    dias_afastamento:     Optional[int] = None
    data_documento:       Optional[str] = None
    nome_profissional:    Optional[str] = None
    registro_profissional: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /ia/documentos/atestado/validar
# ---------------------------------------------------------------------------

@router.post(
    "/documentos/atestado/validar",
    summary="Validação estrutural de atestado médico (IA Documental v1)",
    response_description="Resultado da validação com alertas, sugestões e documento base",
)
def validar_atestado_endpoint(
    payload: ValidarAtestadoIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Valida a estrutura de um atestado médico e retorna resultado explicável.

    **Princípio central:** A IA não escreve o atestado — ela garante que
    o atestado esteja correto.

    **O que este endpoint faz:**
    - Verifica campos obrigatórios (ok=False se algum ausente ou inválido).
    - Alerta sobre linguagem clínica vaga (não-bloqueante).
    - Verifica coerência entre texto clínico e CID selecionado (não-bloqueante).
    - Sugere melhorias de redação (determinísticas — nunca automáticas).
    - Renderiza documento_base quando todos os campos estão válidos.

    **O que este endpoint NÃO faz:**
    - Não grava nada no banco de dados.
    - Não gera o atestado definitivo (apenas rascunho base).
    - Não substitui texto automaticamente.
    - Não diagnostica nem sugere CID — apenas verifica coerência.
    - Não usa LLM nem ML generativo.

    **Campos de rastreabilidade retornados:**
    - `ok`: bool — True somente quando todos os campos obrigatórios válidos
    - `faltantes`: lista de campos ausentes/inválidos
    - `alertas`: avisos não-bloqueantes (texto vago, inconsistência CID)
    - `sugestoes`: sugestões de redação (para o profissional)
    - `documento_base`: atestado renderizado (None quando há faltantes)
    - `aviso`: disclaimer fixo obrigatório
    - `versao_template`: versão do template utilizado
    """
    return _validar_atestado(
        paciente_nome         = payload.paciente_nome,
        finalidade            = payload.finalidade,
        indicacao_clinica     = payload.indicacao_clinica,
        codigo_cid            = payload.codigo_cid,
        dias_afastamento      = payload.dias_afastamento,
        data_documento        = payload.data_documento,
        nome_profissional     = payload.nome_profissional,
        registro_profissional = payload.registro_profissional,
    )


# ---------------------------------------------------------------------------
# GET /ia/documentos/status
# ---------------------------------------------------------------------------

@router.get(
    "/documentos/status",
    summary="Status do módulo de IA Documental v1",
)
def status_documentos(
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Retorna estado e configuração do módulo de IA Documental v1.

    Útil para verificar quais templates estão disponíveis e qual versão
    das regras está ativa.
    """
    return {
        "modulo_ativo":          True,
        "templates_disponiveis": ["atestado"],
        "templates_planejados":  _TEMPLATES_V2,
        "versao_regras":         _VERSAO_REGRAS_DOCUMENTAL,
        "template_atual": {
            "id":        "atestado",
            "versao":    _VERSAO_TEMPLATE_ATESTADO,
            "descricao": _DESCRICAO_TEMPLATE_ATESTADO,
        },
        "aviso": (
            "Templates planejados (declaração, relatório, laudo) não estão "
            "implementados neste ticket. Escopo atual: atestado médico."
        ),
    }


# ---------------------------------------------------------------------------
# POST /ia/decisao/validar — semáforo de apoio à decisão (validador)
# ---------------------------------------------------------------------------

class ValidarDecisaoIn(BaseModel):
    """Escolha do prescritor a validar contra a indicação (CID)."""
    codigo_cid:      Optional[str] = None
    principio_ativo: Optional[str] = None


@router.post(
    "/decisao/validar",
    summary="Semáforo de apoio à decisão — coerência fármaco ↔ CID (não-bloqueante)",
)
def validar_decisao_endpoint(
    payload: ValidarDecisaoIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """Confere a coerência do fármaco ESCOLHIDO pelo prescritor com a indicação
    (CID) e devolve um sinal discreto 🟢/🟡. NÃO recomenda fármaco, NÃO bloqueia.

    Atrás de feature flag (`PICSAUDE_DECISAO_CLINICA`). Desligado → `{ativo: false}`
    (o frontend não exibe o sinal). Ver docs/ARQUITETURA_DECISAO_CLINICA.md.
    """
    if not PICSAUDE_DECISAO_CLINICA:
        return {"ativo": False}

    from app.domain.semaforo_decisao import avaliar
    a = avaliar(payload.codigo_cid, payload.principio_ativo)
    # Ficha de explicabilidade (camada 2): a resposta carrega tudo que justifica
    # o sinal — entrada normalizada, regra disparada, proveniência (condição,
    # fonte, quem validou, versão), exaustividade e a garantia de determinismo.
    # A UI usa isso no "por quê?". Ver docs/EXPLICABILIDADE_DECISAO_CLINICA.md.
    ficha = a.to_ficha()
    return {
        "ativo":  True,
        "sinal":  a.sinal,        # verde | amarelo | neutro  (vermelho = Fase 2)
        "motivo": a.motivo,
        "fonte":  a.fonte,
        "explicabilidade": ficha["explicabilidade"],
        "aviso": (
            "Sinal de apoio à decisão, não-bloqueante. A escolha e a "
            "responsabilidade são do prescritor."
        ),
    }


# ---------------------------------------------------------------------------
# POST /ia/posologia/sugerir — sugestão de posologia usual (avaliar + editar)
# ---------------------------------------------------------------------------

class SugerirPosologiaIn(BaseModel):
    """Fármaco escolhido — para sugerir a posologia usual ao prescritor."""
    principio_ativo: Optional[str] = None


@router.post(
    "/posologia/sugerir",
    summary="Sugestão de posologia usual (companheiro do semáforo, não-vinculante)",
)
def sugerir_posologia_endpoint(
    payload: SugerirPosologiaIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """Sugere a posologia usual do fármaco para o prescritor **avaliar e editar**
    (pré-popula o campo, sempre editável). NÃO prescreve, NÃO bloqueia.

    Determinístico; só serve conteúdo clínico VALIDADO (rascunhos ficam dormentes).
    Atrás da flag `PICSAUDE_DECISAO_CLINICA` (mesma família do semáforo).
    Desligado / sem posologia validada → `{disponivel: false}` (a UI não oferece nada).
    """
    if not PICSAUDE_DECISAO_CLINICA:
        return {"disponivel": False}

    from app.domain.posologia_sugerida import sugerir
    p = sugerir(payload.principio_ativo)
    if not p:
        return {"disponivel": False}
    return {
        "disponivel":   True,
        "principio_ativo": p.principio_ativo,
        "posologia":    p.posologia,        # texto que pré-popula o campo (editável)
        "condicao":     p.condicao or None,
        "fonte":        p.fonte,
        "validado_por": p.validado_por,
        "versao":       p.versao,
        "observacao":   p.observacao or None,
        "aviso": (
            "Sugestão de posologia usual — confira dose, via, contraindicações e "
            "ajuste ao paciente. O prescritor é o responsável final."
        ),
    }
