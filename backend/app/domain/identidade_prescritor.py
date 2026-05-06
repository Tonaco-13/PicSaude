"""
identidade_prescritor.py
========================
Ticket 65 — Pipeline de identidade profissional do prescritor.

Fluxo:
  1. Receber CPF + nome do certificado ICP-Brasil
  2. Buscar profissional no CNES via número de conselho
  3. Consultar conselho (CFM/CFO) via ConselhoProvider
  4. Validar coerência de nomes com NomeValidator (Ticket 64)
  5. Resolver múltiplos vínculos institucionais
  6. Retornar objeto de identidade auditável

Limitação documentada — snapshot CNES sem CPF
-----------------------------------------------
O snapshot DataSUS público (profissionais_cnes) não inclui CPF por razões
de privacidade. A coluna CO_CPF contém o literal "CO_CPF" (artefato de
importação CSV). O CPF do certificado ICP-Brasil é usado como âncora de
identidade civil, mas a busca no CNES é feita via número de conselho
(NU_REGISTRO + CO_CONSELHO_CLASSE em relacao_prof_estab). Em produção,
a resolução CPF → CNS exigiria a API CNES-DataSUS ou snapshot enriquecido.

Conselhos mapeados (CO_CONSELHO_CLASSE):
  "71" → CRM  (médicos)
  "26" → CRM  (variante histórica)
  "75" → CRO  (odontólogos)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Protocol

from app.config import CNES_SNAPSHOT_MES, CNES_SNAPSHOT_REF
from app.domain.cnes_prescritor import _get_cnes_conn, eh_cbo_prescritor, tipo_prescritor_por_cbo
from app.domain.nome_validator import NomeValidator
from app.utils.helpers import normalize_cpf

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_CONSELHO_CRM = {"71", "26"}
_CONSELHO_CRO = {"75"}
_CONSELHOS_HABILITADORES = _CONSELHO_CRM | _CONSELHO_CRO

_TIPO_CONSELHO: dict[str, str] = {
    "71": "CRM",
    "26": "CRM",
    "75": "CRO",
}

_LIMIAR_CONFIANCA_FORTE: float = 0.95

_nome_validator = NomeValidator()


# ---------------------------------------------------------------------------
# Protocolo: ConselhoProvider
# ---------------------------------------------------------------------------


class ConselhoProvider(Protocol):
    """
    Interface para consulta ao conselho profissional (CFM / CFO).

    Implementações:
      - BancoCnesConselhoProvider  : lê relacao_prof_estab (MVP, offline)
      - MockConselhoProvider       : dados fixos para testes
      - CfmApiProvider (futuro)    : consulta API CFM/CFO real
    """

    def buscar(
        self,
        tipo_conselho: str,
        numero: str,
        uf: Optional[str],
    ) -> Optional[dict]:
        """
        Busca dados do profissional no conselho.

        Returns
        -------
        dict com: tipo_conselho, numero, uf, nome_conselho, ativo
        None se não encontrado.
        """
        ...


# ---------------------------------------------------------------------------
# Implementação: banco CNES local (relacao_prof_estab)
# ---------------------------------------------------------------------------


class BancoCnesConselhoProvider:
    """
    Consulta conselho a partir dos dados já presentes em relacao_prof_estab (SQLite CNES).

    Esta é a implementação MVP: usa o que está disponível no snapshot CNES
    sem chamar APIs externas. Nome do conselho não está disponível nesta fonte.
    """

    def buscar(
        self,
        tipo_conselho: str,
        numero: str,
        uf: Optional[str],
    ) -> Optional[dict]:
        classes = list(_CONSELHO_CRM) if tipo_conselho == "CRM" else list(_CONSELHO_CRO)
        placeholders = ", ".join("?" * len(classes))
        uf_clause = "" if not uf else "AND r.SG_UF_CRM = ?"
        params: list = [numero, *classes]
        if uf:
            params.append(uf)

        try:
            # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
            cnes_conn = _get_cnes_conn()
            try:
                row = cnes_conn.execute(
                    f"""
                    SELECT
                        r.CO_CONSELHO_CLASSE AS classe,
                        r.NU_REGISTRO        AS numero,
                        r.SG_UF_CRM          AS uf
                    FROM relacao_prof_estab r
                    WHERE r.NU_REGISTRO = ?
                      AND r.CO_CONSELHO_CLASSE IN ({placeholders})
                      {uf_clause}
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            finally:
                cnes_conn.close()
        except Exception:
            return None

        if not row:
            return None

        return {
            "tipo_conselho": _TIPO_CONSELHO.get(row["classe"], tipo_conselho),
            "numero": row["numero"],
            "uf": row["uf"] or uf,
            "nome_conselho": None,  # não disponível no snapshot local
            "ativo": None,          # não disponível no snapshot local
        }


# ---------------------------------------------------------------------------
# Implementação: mock (para testes)
# ---------------------------------------------------------------------------


class MockConselhoProvider:
    """Provider fixo para testes unitários."""

    def __init__(self, resultado: Optional[dict] = None):
        self._resultado = resultado

    def buscar(
        self,
        tipo_conselho: str,
        numero: str,
        uf: Optional[str],
    ) -> Optional[dict]:
        return self._resultado


# ---------------------------------------------------------------------------
# Busca CNES por número de conselho
# ---------------------------------------------------------------------------


def _buscar_cnes_por_conselho(
    conn,
    conselho_numero: str,
    conselho_uf: Optional[str],
) -> list[dict]:
    """
    Busca profissional no CNES via número de conselho (CRM/CRO).

    Retorna lista de registros — um por vínculo institucional ativo.
    Lista vazia = não encontrado.

    Join: profissionais_cnes → relacao_prof_estab → estabelecimentos_cnes
    """
    uf_clause = "" if not conselho_uf else "AND r.SG_UF_CRM = ?"
    classes = list(_CONSELHOS_HABILITADORES)
    placeholders = ", ".join("?" * len(classes))
    params: list = [conselho_numero.strip(), *classes]
    if conselho_uf:
        params.append(conselho_uf.strip().upper())

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    try:
        cnes_conn = _get_cnes_conn()
        try:
            rows = cnes_conn.execute(
                f"""
                SELECT
                    p.NO_PROFISSIONAL                              AS nome_cnes,
                    CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT)        AS cns,
                    r.CO_CONSELHO_CLASSE                           AS conselho_classe,
                    r.NU_REGISTRO                                  AS conselho_numero,
                    r.SG_UF_CRM                                    AS conselho_uf,
                    r.CO_CBO                                       AS cbo,
                    r.CO_UNIDADE                                   AS co_unidade,
                    e.NO_FANTASIA                                  AS nome_fantasia,
                    e.TP_UNIDADE                                   AS tipo_estabelecimento,
                    e.CO_CNES                                      AS cnes_code
                FROM profissionais_cnes p
                JOIN relacao_prof_estab r
                  ON r.CO_PROFISSIONAL_SUS = p.CO_PROFISSIONAL_SUS
                LEFT JOIN estabelecimentos_cnes e
                  ON e.CO_UNIDADE = r.CO_UNIDADE
                WHERE r.NU_REGISTRO = ?
                  AND r.CO_CONSELHO_CLASSE IN ({placeholders})
                  {uf_clause}
                """,
                params,
            ).fetchall()
        finally:
            cnes_conn.close()
    except Exception:
        return []

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Agrupamento de vínculos
# ---------------------------------------------------------------------------


def _agrupar_vinculos(rows: list[dict]) -> list[dict]:
    """
    Converte a lista de linhas (1 por vínculo) em lista de vínculos únicos.

    Deduplicação por co_unidade dentro de um mesmo profissional.
    """
    visto: set[str] = set()
    resultado: list[dict] = []
    for r in rows:
        chave = r.get("co_unidade") or ""
        if chave in visto:
            continue
        visto.add(chave)
        resultado.append(
            {
                "co_unidade": r.get("co_unidade"),
                "cnes_code": r.get("cnes_code"),
                "nome_fantasia": r.get("nome_fantasia"),
                "tipo_estabelecimento": r.get("tipo_estabelecimento"),
                "cbo": r.get("cbo"),
                "conselho_numero": r.get("conselho_numero"),
                "conselho_uf": r.get("conselho_uf"),
                "ativo": True,  # snapshot CNES contém apenas vínculos ativos
            }
        )
    return resultado


# ---------------------------------------------------------------------------
# Classificação de coerência de nome
# ---------------------------------------------------------------------------


def _classificar_nome(valido: bool, confianca: float) -> str:
    if not valido:
        return "divergente"
    if confianca >= _LIMIAR_CONFIANCA_FORTE:
        return "coerente_forte"
    return "coerente_parcial"


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def resolver_identidade_prescritor(
    conn,
    cpf_certificado: str,
    nome_certificado: str,
    conselho_numero: Optional[str] = None,
    conselho_uf: Optional[str] = None,
    conselho_provider: Optional[ConselhoProvider] = None,
) -> dict:
    """
    Pipeline de identidade profissional do prescritor.

    Parâmetros
    ----------
    conn               Mantido por compatibilidade de interface — não utilizado para CNES.
                       As queries CNES abrem conexão SQLite dedicada via _get_cnes_conn().
    cpf_certificado    CPF extraído do certificado ICP-Brasil (apenas dígitos)
    nome_certificado   Nome extraído do certificado ICP-Brasil
    conselho_numero    Número de registro no conselho (CRM/CRO) — opcional
    conselho_uf        UF do conselho — opcional, melhora precisão do lookup
    conselho_provider  Provider para consulta ao conselho; se None, usa
                       BancoCnesConselhoProvider (snapshot local)

    Retorna
    -------
    dict com campos:
      status            : "ok" | "nao_encontrado_cnes" | "nao_encontrado_conselho"
                          | "multiplo_vinculo" | "divergente"
      cpf_certificado   : CPF normalizado
      nome_certificado  : nome do certificado
      cns               : CNS do profissional (se encontrado)
      nome_cnes         : nome no CNES (se encontrado)
      conselho          : dados do conselho { tipo_conselho, numero, uf, nome_conselho, ativo }
      nome_validacao    : { status, motivo, confianca }
      vinculo_escolhido : vínculo institucional selecionado (ou None)
      vinculos_disponiveis : todos os vínculos encontrados
      divergencias      : lista de strings descrevendo divergências
      snapshot_mes      : referência do snapshot CNES
      snapshot_ref      : identificador do snapshot CNES
      resolvido_em      : timestamp UTC da resolução
    """
    cpf_norm = normalize_cpf(cpf_certificado or "")
    nome_cert = (nome_certificado or "").strip()
    resolvido_em = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Resultado base — preenchido progressivamente
    resultado: dict = {
        "status":                "nao_encontrado_cnes",
        "cpf_certificado":       cpf_norm,
        "nome_certificado":      nome_cert,
        "cns":                   None,
        "nome_cnes":             None,
        "tipo_prescritor":       None,
        "conselho":              None,
        "nome_validacao":        None,
        "vinculo_escolhido":     None,
        "vinculos_disponiveis":  [],
        "divergencias":          [],
        "snapshot_mes":          CNES_SNAPSHOT_MES,
        "snapshot_ref":          CNES_SNAPSHOT_REF,
        "resolvido_em":          resolvido_em,
    }

    # ── PASSO 1 — Validar entradas mínimas ────────────────────────────────
    if not conselho_numero:
        resultado["divergencias"].append(
            "conselho_nao_informado: CPF não resolvível no snapshot CNES sem "
            "número de conselho (CO_CPF ausente no DataSUS público)"
        )
        return resultado

    # ── PASSO 2 — Busca CNES por número de conselho ───────────────────────
    rows_cnes = _buscar_cnes_por_conselho(conn, conselho_numero, conselho_uf)

    if not rows_cnes:
        return resultado  # status = nao_encontrado_cnes

    # Extrair dados do profissional (primeiro registro determina CNS e nome)
    primeiro = rows_cnes[0]
    cns = primeiro.get("cns") or ""
    nome_cnes = primeiro.get("nome_cnes") or ""
    conselho_classe = primeiro.get("conselho_classe") or ""
    tipo_conselho = _TIPO_CONSELHO.get(conselho_classe, "CRM")

    # CBO prescritivo
    cbos: set[str] = {r.get("cbo") for r in rows_cnes if r.get("cbo")}
    cbos_prescritivos = [c for c in cbos if eh_cbo_prescritor(c)]
    cbo_primario = sorted(cbos_prescritivos)[0] if cbos_prescritivos else None
    tipo_prescritor = tipo_prescritor_por_cbo(cbo_primario) if cbo_primario else None

    resultado["cns"] = cns
    resultado["nome_cnes"] = nome_cnes
    resultado["tipo_prescritor"] = tipo_prescritor

    # Agrupar vínculos
    vinculos = _agrupar_vinculos(rows_cnes)
    resultado["vinculos_disponiveis"] = vinculos

    # ── PASSO 3 — Consulta ao conselho ────────────────────────────────────
    provider = conselho_provider or BancoCnesConselhoProvider()
    dados_conselho = provider.buscar(tipo_conselho, conselho_numero, conselho_uf)

    if dados_conselho is None:
        resultado["status"] = "nao_encontrado_conselho"
        resultado["divergencias"].append(
            f"conselho_nao_encontrado: {tipo_conselho} {conselho_numero}"
            + (f"/{conselho_uf}" if conselho_uf else "")
        )
        return resultado

    resultado["conselho"] = dados_conselho

    # Alertar se conselho inativo (quando disponível)
    if dados_conselho.get("ativo") is False:
        resultado["divergencias"].append(
            f"conselho_inativo: {tipo_conselho} {conselho_numero} "
            f"retornou ativo=False"
        )

    # ── PASSO 4 — Validação de nomes (NomeValidator) ──────────────────────
    nome_conselho = dados_conselho.get("nome_conselho") or nome_cnes
    valido_nome, motivo_nome, confianca_nome = _nome_validator.validar_correspondencia(
        nome_certificado=nome_cert,
        nome_cnes=nome_cnes,
        nome_conselho=nome_conselho,
    )
    status_nome = _classificar_nome(valido_nome, confianca_nome)
    resultado["nome_validacao"] = {
        "status":     status_nome,
        "motivo":     motivo_nome,
        "confianca":  round(confianca_nome, 4),
    }

    if not valido_nome:
        resultado["divergencias"].append(
            f"nome_divergente: cert='{nome_cert}' cnes='{nome_cnes}' "
            f"motivo='{motivo_nome}'"
        )

    # ── PASSO 5 — Resolver múltiplos vínculos ─────────────────────────────
    if len(vinculos) == 0:
        # Improvável (rows_cnes não-vazio), mas tratar
        resultado["status"] = "nao_encontrado_cnes"
        return resultado

    vinculo_escolhido: Optional[dict] = None

    if len(vinculos) == 1:
        # Caso A: 1 vínculo — selecionar automaticamente
        vinculo_escolhido = vinculos[0]

    else:
        # Caso B/C: múltiplos vínculos
        # Tentar filtrar por conselho_uf
        if conselho_uf:
            candidatos = [
                v for v in vinculos
                if (v.get("conselho_uf") or "").upper() == conselho_uf.upper()
            ]
            if len(candidatos) == 1:
                vinculo_escolhido = candidatos[0]

        if vinculo_escolhido is None:
            # Caso C: múltiplos vínculos sem critério forte → não escolher
            resultado["status"] = "multiplo_vinculo"
            # Não preencher vinculo_escolhido
            # (status divergente pode coexistir, mas multiplo_vinculo tem precedência)
            return resultado

    resultado["vinculo_escolhido"] = vinculo_escolhido

    # ── PASSO 6 — Status final ────────────────────────────────────────────
    if not valido_nome:
        resultado["status"] = "divergente"
    else:
        resultado["status"] = "ok"

    return resultado
