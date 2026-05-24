"""
cnes_prescritor.py
==================
Camada 6 — Validação CNES do Prescritor na emissão de prescrições.

Objetivo: cruzar o CNS declarado na prescrição contra as tabelas CNES
(profissionais_cnes + relacao_prof_estab) e retornar um bloco
`cnes_validacao` que é gravado no evento `prescricao_emitida`.

A emissão NUNCA é bloqueada por este módulo — valida, classifica e registra.
O resultado serve para auditoria, rastreabilidade e camada 6 do motor de
validação documental (validacao_documental.py).

Níveis de validação (nivel_validacao_cnes)
------------------------------------------
  forte          CNS encontrado + nome exato + CBO prescritivo + conselho habilitado
                 AND vínculo com prestador confirmado (se org_id informado)
  parcial        CNS encontrado + CBO prescritivo + nome ok, mas sem conselho OU
                 nome parcial (não exato) OU vínculo com prestador negativo
  divergente     CNS encontrado, mas nome diverge OU CBO não é prescritivo —
                 contradição direta; indica possível uso indevido de CNS alheio
  nao_encontrado CNS ausente do snapshot CNES (snapshot mensal — pode ser recente)

Matching de nome (Ticket 48)
-----------------------------
  exato    nomes idênticos após normalização (sem acentos, maiúsculas, espaços)
  parcial  um nome contido no outro (abreviações, nomes compostos parciais)
  divergente  sem correspondência → falha dura de identidade

Limitação documentada — snapshot mensal
-----------------------------------------
O snapshot CNES é atualizado mensalmente pelo DataSUS.
A ausência de um profissional NÃO indica irregularidade.
A emissão nunca é bloqueada por qualquer nível deste módulo.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from app.config import CBO_PREFIXES, CNES_SNAPSHOT_MES, CNES_SNAPSHOT_REF
from app.domain.nome_validator import NomeValidator

_nome_validator = NomeValidator()


def _get_cnes_conn() -> sqlite3.Connection:
    """Abre conexão SQLite read-only ao banco CNES.

    Usa `_resolve_sqlite_db_path()` (TICKET-6 P1#1 / 6.1) — em demo, abre
    o DB demo (sem tabelas CNES → toda validação retorna `nao_encontrado`,
    aceitável porque persona demo usa CNS sintético e a validação CNES é
    não-bloqueante).

    As tabelas CNES (profissionais_cnes, relacao_prof_estab,
    estabelecimentos_cnes) residem no SQLite independentemente de o
    backend usar PostgreSQL ou SQLite para as tabelas da aplicação.
    """
    import os
    # Import lazy para evitar ciclo com app.database em import-time.
    from app.database import _resolve_sqlite_db_path

    db_path = _resolve_sqlite_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco CNES não encontrado: {db_path}")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

# Prefixos CBO que habilitam prescrição (DataSUS CBO 2022)
_CBO_MEDICO     = "2251"   # Médico (clínico geral e especialistas)
_CBO_CIRURGIAO  = "2252"   # Cirurgião (todas as especialidades)
_CBO_ODONTOLOGO = "2232"   # Cirurgião-dentista / Odontólogo

# Mapeamento prefixo CBO → tipo textual do prescritor
_CBO_TIPO: dict[str, str] = {
    _CBO_MEDICO:     "medico",
    _CBO_CIRURGIAO:  "cirurgiao",
    _CBO_ODONTOLOGO: "odontologo",
}

# Conselhos de classe que habilitam prescrição (CO_CONSELHO_CLASSE no CNES)
_CONSELHOS_PRESCRICAO: dict[str, str] = {
    "71": "CRM",   # Conselho Regional de Medicina
    "75": "CRO",   # Conselho Regional de Odontologia
    "26": "CRM",   # variante histórica de CRM em registros legados
}


# ---------------------------------------------------------------------------
# Helpers públicos de CBO
# ---------------------------------------------------------------------------

def eh_cbo_prescritor(cbo: str) -> bool:
    """
    Retorna True se o código CBO indica habilitação prescritiva.

    Prefixos habilitados: 2251* (médico), 2252* (cirurgião), 2232* (odontólogo).
    """
    if not cbo:
        return False
    return any(cbo.startswith(p) for p in CBO_PREFIXES)


def tipo_prescritor_por_cbo(cbo: str) -> Optional[str]:
    """
    Retorna o tipo do prescritor com base no prefixo CBO.

    Returns
    -------
    "medico" | "cirurgiao" | "odontologo" | None (CBO desconhecido ou vazio)
    """
    if not cbo:
        return None
    for prefixo, tipo in _CBO_TIPO.items():
        if cbo.startswith(prefixo):
            return tipo
    return None


# ---------------------------------------------------------------------------
# Normalização e matching de nome (Ticket 48)
# ---------------------------------------------------------------------------

def _normalizar_nome(nome: str) -> str:
    """
    Normaliza nome para comparação canônica:
      - strip + maiúsculas
      - remove acentos (NFD → descarta Mn)
      - colapsa espaços múltiplos
    """
    nome = nome.strip().upper()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = " ".join(nome.split())
    return nome


def _match_nome(nome_declarado: str, nome_cnes: str) -> tuple[str, bool]:
    """
    Compara dois nomes usando NomeValidator (Ticket 64).

    Delega para NomeValidator.validar_correspondencia() com nome_cnes como
    única fonte disponível (conselho não está separado neste fluxo).

    Mapeamento de confiança → match_tipo:
      confianca >= 0.95  → "exato"   (nomes praticamente idênticos)
      confianca >= 0.0   → "parcial" (correspondência válida com variação)
      valido == False    → "divergente"

    Returns
    -------
    (match_tipo, coincide):
      ("exato",      True)  — correspondência de alta confiança
      ("parcial",    True)  — correspondência com variação ortográfica
      ("divergente", False) — sem correspondência
    """
    if not nome_declarado or not nome_cnes:
        return "divergente", False

    valido, _motivo, confianca = _nome_validator.validar_correspondencia(
        nome_certificado=nome_declarado,
        nome_cnes=nome_cnes,
        nome_conselho=nome_cnes,  # mesmo dado; conselho não disponível neste fluxo
    )

    if valido:
        if confianca >= 0.95:
            return "exato", True
        return "parcial", True

    # Fallback: containment semântico para nomes abreviados no CNES.
    # Dados do DataSUS frequentemente registram nome parcial (composto vs abreviado).
    # Ex: "JOAO SILVA" contido em "JOAO DA SILVA PEREIRA" → parcial (não divergente).
    a = _normalizar_nome(nome_declarado)
    b = _normalizar_nome(nome_cnes)
    if a and b and (a in b or b in a):
        return "parcial", True

    return "divergente", False


# ---------------------------------------------------------------------------
# Cálculo do nível de validação
# ---------------------------------------------------------------------------

def _calcular_nivel(
    cns_encontrado: bool,
    nome_match_tipo: str,
    cbo_prescritivo: bool,
    conselho_habilitado: bool,
    vinculo_com_prestador: Optional[bool] = None,
) -> str:
    """
    Calcula o nivel_validacao_cnes a partir dos checks individuais.

    Regras (por precedência):
      nao_encontrado  → cns ausente
      divergente      → cns encontrado + (nome_divergente OU cbo inválido)
      forte           → nome exato + cbo + conselho + vinculo não negativo
      parcial         → qualquer combinação positiva fora de forte
    """
    if not cns_encontrado:
        return "nao_encontrado"
    # Contradições duras
    if nome_match_tipo == "divergente" or not cbo_prescritivo:
        return "divergente"
    # A partir daqui: cns ok, nome ok (exato ou parcial), cbo ok
    # forte exige nome exato + conselho + vínculo não negativo
    if (nome_match_tipo == "exato"
            and conselho_habilitado
            and vinculo_com_prestador is not False):
        return "forte"
    # qualquer outra combinação positiva = parcial
    return "parcial"


# ---------------------------------------------------------------------------
# Verificação de vínculo com prestador (Ticket 48)
# ---------------------------------------------------------------------------

def _verificar_vinculo_prestador(
    conn,
    org_id: str,
    co_unidades_prescritor: set,
) -> Optional[bool]:
    """
    Verifica se o prescritor tem vínculo CNES com o prestador identificado
    por ``org_id``.

    Fluxo:
      1. Busca CNPJ em ``prestadores`` onde org_id = ?
      2. Busca CO_CNES em ``estabelecimentos_cnes`` pelo CNPJ
      3. Confere se CO_CNES consta nos CO_UNIDADE do prescritor no CNES

    Retorna
    -------
    True   → vínculo direto confirmado
    False  → prestador cadastrado + CNES encontrado, mas sem vínculo
    None   → não foi possível verificar (prestador não cadastrado,
              CNES não mapeado, ou erro de consulta)
    """
    try:
        # prestadores é tabela da aplicação — usa a conexão principal (PG ou SQLite)
        prestador = conn.execute(
            "SELECT cnpj FROM prestadores WHERE org_id = ? AND ativo = true",
            (org_id,),
        ).fetchone()
        if not prestador or not prestador["cnpj"]:
            return None   # prestador não cadastrado → não é divergência

        cnpj = "".join(c for c in (prestador["cnpj"] or "") if c.isdigit())
        if not cnpj:
            return None

        # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
        cnes_conn = _get_cnes_conn()
        try:
            cnes_row = cnes_conn.execute(
                """
                SELECT CO_CNES FROM estabelecimentos_cnes
                WHERE REPLACE(REPLACE(REPLACE(REPLACE(NU_CNPJ, '.', ''), '/', ''), '-', ''), ' ', '') = ?
                LIMIT 1
                """,
                (cnpj,),
            ).fetchone()
        finally:
            cnes_conn.close()

        if not cnes_row:
            return None   # prestador não tem CNES mapeado → não é divergência

        co_cnes = str(cnes_row["CO_CNES"])
        return co_cnes in co_unidades_prescritor
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Função principal de validação — chamada na emissão
# ---------------------------------------------------------------------------

def validar_cns_prescritor(
    conn,
    cns: str,
    nome_declarado: str,
    org_id: Optional[str] = None,
) -> dict:
    """
    Valida o CNS do prescritor contra as tabelas CNES.

    Esta função é chamada em ``criar_prescricao`` (routers/prescricoes.py)
    logo antes do commit, e o resultado é gravado no payload do evento
    ``prescricao_emitida`` como chave ``cnes_validacao``.

    A emissão NUNCA é bloqueada: qualquer exceção ou resultado negativo
    é retornado como dict, não como exceção.

    Parâmetros
    ----------
    conn           Conexão SQLite aberta com ``row_factory = sqlite3.Row``
    cns            CNS do prescritor (normalizado, apenas dígitos internamente)
    nome_declarado Nome informado na prescrição (para comparação de identidade)
    org_id         org_id do prestador onde a prescrição é emitida (opcional).
                   Quando informado, verifica vínculo CNES prescritor ↔ prestador.

    Retorna
    -------
    dict com o bloco ``cnes_validacao``:

    .. code-block:: json

        {
          "nivel_validacao_cnes":     "forte|parcial|divergente|nao_encontrado",
          "cns_encontrado":           true,
          "nome_cnes":                "JOAO DA SILVA",
          "nome_normalizado_coincide": true,
          "nome_match_tipo":          "exato|parcial|divergente",
          "cbo":                      "225125",
          "cbo_prescritor_valido":    true,
          "tipo_prescritor":          "medico",
          "conselho":                 "71",
          "crm_declarado":            "12345",
          "uf_crm_declarado":         "PE",
          "crm_cnes_coincide":        true,
          "uf_cnes_coincide":         true,
          "vinculos_ativos":          3,
          "vinculo_com_prestador":    true,
          "snapshot_mes":             "2025-12",
          "snapshot_ref":             "cnes_br_2025_12",
          "validado_em":              "2026-01-15T10:30:00Z",
          "divergencias":             []
        }
    """
    validado_em = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cns_norm = "".join(c for c in (cns or "") if c.isdigit())

    # ── Resultado base (CNS ausente / erro de consulta) ────────────────────
    resultado_base: dict = {
        "nivel_validacao_cnes":      "nao_encontrado",
        "cns_encontrado":            False,
        "nome_cnes":                 None,
        "nome_normalizado_coincide": None,
        "nome_match_tipo":           None,
        "cbo":                       None,
        "cbo_prescritor_valido":     None,
        "tipo_prescritor":           None,
        "conselho":                  None,
        "crm_declarado":             None,
        "uf_crm_declarado":          None,
        "crm_cnes_coincide":         None,
        "uf_cnes_coincide":          None,
        "vinculos_ativos":           0,
        "vinculo_com_prestador":     None,
        "snapshot_mes":              CNES_SNAPSHOT_MES,
        "snapshot_ref":              CNES_SNAPSHOT_REF,
        "validado_em":               validado_em,
        "divergencias":              [],
    }

    if not cns_norm:
        return resultado_base

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    try:
        cnes_conn = _get_cnes_conn()
        try:
            rows = cnes_conn.execute(
                """
                SELECT
                    p.NO_PROFISSIONAL  AS nome_cnes,
                    r.CO_CONSELHO_CLASSE AS conselho,
                    r.NU_REGISTRO        AS registro,
                    r.SG_UF_CRM          AS uf_registro,
                    r.CO_CBO             AS cbo,
                    r.CO_UNIDADE         AS co_unidade
                FROM profissionais_cnes p
                JOIN relacao_prof_estab r
                  ON r.CO_PROFISSIONAL_SUS = p.CO_PROFISSIONAL_SUS
                WHERE CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) = ?
                """,
                (cns_norm,),
            ).fetchall()
        finally:
            cnes_conn.close()
    except Exception as exc:
        resultado_base["divergencias"].append(
            f"erro_consulta_cnes: {exc}"
        )
        return resultado_base

    # ── CNS não encontrado no snapshot ────────────────────────────────────
    if not rows:
        return resultado_base

    # ── CNS encontrado — extrair dados ────────────────────────────────────
    nome_cnes = rows[0]["nome_cnes"] or ""

    # Nome
    match_tipo, nome_coincide = _match_nome(nome_declarado or "", nome_cnes)

    # CBOs
    todos_cbos = sorted({r["cbo"] for r in rows if r["cbo"]})
    cbos_prescritivos = [c for c in todos_cbos if eh_cbo_prescritor(c)]
    cbo_ok = len(cbos_prescritivos) > 0
    cbo_primario: Optional[str] = cbos_prescritivos[0] if cbos_prescritivos else None
    tipo_prescritor: Optional[str] = (
        tipo_prescritor_por_cbo(cbo_primario) if cbo_primario else None
    )

    # Conselho (CRM / CRO)
    conselhos_habilitadores = [
        r for r in rows
        if r["conselho"] in _CONSELHOS_PRESCRICAO
    ]
    conselho_ok = len(conselhos_habilitadores) > 0
    conselho_codigo: Optional[str]    = None
    crm_numero: Optional[str]         = None
    uf_crm: Optional[str]             = None
    if conselhos_habilitadores:
        melhor = conselhos_habilitadores[0]
        conselho_codigo = melhor["conselho"]
        crm_numero      = melhor["registro"]
        uf_crm          = melhor["uf_registro"]
    crm_cnes_coincide = conselho_ok
    uf_cnes_coincide  = uf_crm is not None

    # Vínculos institucionais
    co_unidades: set = {str(r["co_unidade"]) for r in rows if r["co_unidade"]}
    vinculos_ativos = len(co_unidades)

    # Vínculo com prestador da prescrição
    vinculo_prestador: Optional[bool] = None
    if org_id:
        vinculo_prestador = _verificar_vinculo_prestador(conn, org_id, co_unidades)

    # Divergências detectadas
    divergencias: list[str] = []
    if match_tipo == "divergente":
        divergencias.append(
            f"nome_divergente: declarado='{_normalizar_nome(nome_declarado or '')}' "
            f"cnes='{_normalizar_nome(nome_cnes)}' (match={match_tipo})"
        )
    if not cbo_ok:
        divergencias.append(
            f"cbo_nao_prescritivo: CBOs encontrados={todos_cbos or ['—']} "
            f"(prefixos aceitos: 2251*, 2252*, 2232*)"
        )
    if vinculo_prestador is False:
        divergencias.append(
            f"vinculo_prestador_ausente: CO_UNIDADE do CNES não inclui "
            f"o estabelecimento do prestador org_id='{org_id}'"
        )

    # Nível síntese
    nivel = _calcular_nivel(
        cns_encontrado=True,
        nome_match_tipo=match_tipo,
        cbo_prescritivo=cbo_ok,
        conselho_habilitado=conselho_ok,
        vinculo_com_prestador=vinculo_prestador,
    )

    return {
        "nivel_validacao_cnes":      nivel,
        "cns_encontrado":            True,
        "nome_cnes":                 nome_cnes,
        "nome_normalizado_coincide": nome_coincide,
        "nome_match_tipo":           match_tipo,
        "cbo":                       cbo_primario,
        "cbo_prescritor_valido":     cbo_ok,
        "tipo_prescritor":           tipo_prescritor,
        "conselho":                  conselho_codigo,
        "crm_declarado":             crm_numero,
        "uf_crm_declarado":          uf_crm,
        "crm_cnes_coincide":         crm_cnes_coincide,
        "uf_cnes_coincide":          uf_cnes_coincide,
        "vinculos_ativos":           vinculos_ativos,
        "vinculo_com_prestador":     vinculo_prestador,
        "snapshot_mes":              CNES_SNAPSHOT_MES,
        "snapshot_ref":              CNES_SNAPSHOT_REF,
        "validado_em":               validado_em,
        "divergencias":              divergencias,
    }
