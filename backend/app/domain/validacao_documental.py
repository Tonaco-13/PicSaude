"""
validacao_documental.py
=======================
Motor de validação estrutural e de integridade das prescrições PicSaúde.

MODELO DE CAMADAS
-----------------
A validação é organizada em 6 camadas independentes. Cada camada retorna
um dict de verificações, cada uma com:

    ok         bool    True = passou | False = falhou
    aplicavel  bool    False quando a verificação não se aplica ao tipo
                       de prescrição (ex.: CFM para física → não aplicável)
    detalhe    str?    Mensagem de erro ou contexto adicional

Camadas em ordem de execução:

  1. estrutural
     Verifica que a prescrição existe no banco, tem estado reconhecido e
     tem ao menos um item com status válido.
     Aplica-se a: todos os tipos.

  2. integridade
     Recomputa o hash SHA-256 do documento canônico e compara com
     prescricoes.assinatura_hash.
     Aplica-se a: prescrições digitais.
     Não aplicável para: física (tipo_emissao='fisica').

  3. cfm
     Verifica campos obrigatórios da Resolução CFM 2.299/2021:
     CPF real, posologia e quantidade por item.
     Aplica-se a: assinatura_modo ∈ {icp_brasil_local, gov_br_nuvem}.
     Não aplicável para: operacional e física.

  4. assinatura_digital
     Verifica se os metadados de assinatura foram registrados em
     prescricao_assinatura e se o hash declarado é coerente.
     Aplica-se a: prescrições digitais.
     Não aplicável para: física.

  5. icp_brasil  (stub MVP)
     Verificações criptográficas contra a AC raiz ICP-Brasil:
     validade do certificado, OCSP/CRL, assinatura PKCS#7.
     Toda verificação retorna ok=False com detalhe explicando que o
     módulo ICP-Brasil não está integrado ainda (MVP).
     Aplica-se a: icp_brasil_local e gov_br_nuvem.

  6. cnes  (ultrasensível)
     Cruzamento do CNS do prescritor com a base CNES Brasil (DataSUS).
     Confirma existência, consistência de nome, categoria profissional
     prescritiva (CBO) e vínculo institucional ativo.
     Não aplicável para: física (prescritor pode não estar na base).
     Falha dura (→ invalido): CNS encontrado mas nome ou CBO contradizem
                              os dados declarados na prescrição.
     Falha leve (→ valido_estrutural): CNS não encontrado no snapshot
                              (profissional pode ser recente; snapshot mensal).

RESULTADO GERAL (resultado_geral)
----------------------------------
  invalido                  ≥1 falha estrutural, integridade, CFM ou
                            contradição CNES (nome/CBO incompatíveis)
  valido_fisico             física + todas estruturais ok
  valido_estrutural         digital/operacional, estrutura + integridade ok,
                            sem modo CFM declarado; CNES não confirmado
  valido_estrutural_cnes    valido_estrutural + CNES confirmou identidade
  valido_cfm_stub           CFM ok, metadados de assinatura presentes,
                            ICP-Brasil pendente; CNES não confirmado
  valido_cfm_cnes_stub      valido_cfm_stub + CNES confirmou identidade
  valido_cfm_completo       (futuro) ICP-Brasil verificado

EXTENSIBILIDADE
---------------
Para adicionar uma nova verificação:
  1. Implemente _check_<nome> abaixo, retornando Verificacao.
  2. Adicione ao dict da camada correspondente.
  3. Atualize calcular_resultado_geral se necessário.
"""

from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from typing import Optional

from app.config import CBO_PREFIXES
from app.domain.cnes_prescritor import _get_cnes_conn
from app.domain.assinatura import (
    MODOS_COM_VALIDADE_CFM,
    MODOS_DIGITAIS_VALIDOS,
    DESCRICAO_STATUS_ASSINATURA,
    calcular_nivel_formal,
)
from app.domain.documento_canonico import montar_documento
from app.domain.states import ESTADOS_ITEM, ESTADOS_PRESCRICAO


# ---------------------------------------------------------------------------
# Estrutura de uma verificação individual
# ---------------------------------------------------------------------------

@dataclass
class Verificacao:
    ok:        bool
    detalhe:   Optional[str] = None
    aplicavel: bool = True          # False → não se aplica ao tipo de prescrição

    def to_dict(self) -> dict:
        return asdict(self)


_NA = Verificacao(ok=True, detalhe="Não aplicável para este tipo de prescrição.", aplicavel=False)


# ---------------------------------------------------------------------------
# Constante sentinela de CPF
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO = "00000000000"


# ---------------------------------------------------------------------------
# Resultado agregado
# ---------------------------------------------------------------------------

@dataclass
class RelatorioValidacao:
    protocolo:          str
    nivel_formal:       str
    resultado_geral:    str
    total_verificacoes: int
    verificacoes_ok:    int
    verificacoes_falha: int
    verificacoes_na:    int   # não aplicáveis
    camadas:            dict  # estrutural, integridade, cfm, assinatura_digital, icp_brasil

    def to_dict(self) -> dict:
        return {
            "protocolo":          self.protocolo,
            "nivel_formal":       self.nivel_formal,
            "resultado_geral":    self.resultado_geral,
            "resumo": {
                "total":      self.total_verificacoes,
                "ok":         self.verificacoes_ok,
                "falha":      self.verificacoes_falha,
                "nao_aplicavel": self.verificacoes_na,
            },
            "camadas": {
                camada: {
                    nome: v.to_dict()
                    for nome, v in checks.items()
                }
                for camada, checks in self.camadas.items()
            },
        }


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def validar_prescricao(conn, protocolo: str) -> RelatorioValidacao:
    """
    Executa todas as camadas de validação para a prescrição `protocolo`.

    Parâmetros
    ----------
    conn      : conexão SQLite aberta (row_factory = sqlite3.Row)
    protocolo : UUID da prescrição a validar

    Retorna
    -------
    RelatorioValidacao com todas as verificações e resultado geral.
    """
    # -----------------------------------------------------------------------
    # Carga de dados da prescrição (único ponto de acesso ao banco)
    # -----------------------------------------------------------------------
    row = conn.execute(
        """
        SELECT
            p.id, p.protocolo, p.status, p.tipo_emissao, p.assinatura_modo,
            p.assinatura_hash, p.data_emissao,
            pr.cns  AS cns_prescritor,
            pr.nome AS nome_prescritor,
            pa.cpf  AS cpf_paciente,
            pa.nome AS nome_paciente
        FROM prescricoes p
        JOIN prescritores pr ON pr.id = p.prescritor_id
        JOIN pacientes    pa ON pa.id = p.paciente_id
        WHERE p.protocolo = ?
        """,
        (protocolo,),
    ).fetchone()

    itens = []
    assinatura_meta = None

    if row:
        itens = conn.execute(
            """
            SELECT nome_medicamento, concentracao, quantidade, unidade_quantidade,
                   forma_farmaceutica, posologia, status_item
              FROM prescricao_itens
             WHERE prescricao_id = ?
             ORDER BY id
            """,
            (row["id"],),
        ).fetchall()

        assinatura_meta = conn.execute(
            """
            SELECT tipo_certificado, emissor, serial_certificado,
                   timestamp_assinatura, hash_documento, dados_assinatura_b64,
                   status_validacao, detalhe_validacao
              FROM prescricao_assinatura
             WHERE prescricao_id = ?
            """,
            (row["id"],),
        ).fetchone()

    tipo_emissao    = row["tipo_emissao"]    if row else None
    assinatura_modo = row["assinatura_modo"] if row else None
    eh_fisica       = tipo_emissao == "fisica"
    eh_cfm          = assinatura_modo in MODOS_COM_VALIDADE_CFM if assinatura_modo else False
    nivel_formal    = calcular_nivel_formal(assinatura_modo, tipo_emissao) if row else "desconhecido"

    # -----------------------------------------------------------------------
    # Camada 1 — Estrutural
    # -----------------------------------------------------------------------
    camada_estrutural = _camada_estrutural(row, itens)

    # -----------------------------------------------------------------------
    # Camada 2 — Integridade do documento canônico
    # -----------------------------------------------------------------------
    camada_integridade = _camada_integridade(row, itens, eh_fisica)

    # -----------------------------------------------------------------------
    # Camada 3 — CFM 2.299/2021
    # -----------------------------------------------------------------------
    camada_cfm = _camada_cfm(row, itens, eh_cfm)

    # -----------------------------------------------------------------------
    # Camada 4 — Metadados de assinatura digital
    # -----------------------------------------------------------------------
    camada_assinatura = _camada_assinatura_digital(row, assinatura_meta, eh_fisica)

    # -----------------------------------------------------------------------
    # Camada 5 — ICP-Brasil (stub MVP)
    # -----------------------------------------------------------------------
    camada_icp = _camada_icp_brasil(assinatura_modo)

    # -----------------------------------------------------------------------
    # Camada 6 — CNES (ultrasensível)
    # -----------------------------------------------------------------------
    cns_prescritor  = row["cns_prescritor"]  if row else None
    nome_prescritor = row["nome_prescritor"] if row else None
    camada_cnes = _camada_cnes(conn, cns_prescritor, nome_prescritor, eh_fisica)

    # -----------------------------------------------------------------------
    # Agregar resultados
    # -----------------------------------------------------------------------
    todas: dict[str, dict[str, Verificacao]] = {
        "estrutural":         camada_estrutural,
        "integridade":        camada_integridade,
        "cfm":                camada_cfm,
        "assinatura_digital": camada_assinatura,
        "icp_brasil":         camada_icp,
        "cnes":               camada_cnes,
    }

    total = sum(len(v) for v in todas.values())
    ok_count = sum(
        1 for v in todas.values() for c in v.values() if c.aplicavel and c.ok
    )
    falha_count = sum(
        1 for v in todas.values() for c in v.values() if c.aplicavel and not c.ok
    )
    na_count = sum(
        1 for v in todas.values() for c in v.values() if not c.aplicavel
    )

    resultado = _calcular_resultado_geral(
        camada_estrutural, camada_integridade, camada_cfm,
        camada_assinatura, camada_icp, camada_cnes,
        eh_fisica, eh_cfm,
    )

    return RelatorioValidacao(
        protocolo          = protocolo,
        nivel_formal       = nivel_formal,
        resultado_geral    = resultado,
        total_verificacoes = total,
        verificacoes_ok    = ok_count,
        verificacoes_falha = falha_count,
        verificacoes_na    = na_count,
        camadas            = todas,
    )


# ---------------------------------------------------------------------------
# Camada 1 — Estrutural
# ---------------------------------------------------------------------------

def _camada_estrutural(row, itens) -> dict[str, Verificacao]:
    checks: dict[str, Verificacao] = {}

    # 1.1 — Prescrição existe
    if row is None:
        checks["prescricao_existe"] = Verificacao(ok=False, detalhe="Protocolo não encontrado no banco.")
        # Demais verificações não podem rodar
        for nome in ("tipo_emissao_reconhecido", "status_reconhecido",
                     "tem_itens", "itens_status_reconhecidos"):
            checks[nome] = Verificacao(ok=False, detalhe="Prescrição não encontrada — verificação bloqueada.")
        return checks

    checks["prescricao_existe"] = Verificacao(ok=True)

    # 1.2 — tipo_emissao reconhecido
    tipos_validos = {"nova", "correcao", "renovacao", "fisica"}
    tipo = row["tipo_emissao"]
    if tipo in tipos_validos:
        checks["tipo_emissao_reconhecido"] = Verificacao(ok=True)
    else:
        checks["tipo_emissao_reconhecido"] = Verificacao(
            ok=False, detalhe=f"tipo_emissao desconhecido: '{tipo}'. Esperado: {sorted(tipos_validos)}"
        )

    # 1.3 — status reconhecido
    status = row["status"]
    if status in ESTADOS_PRESCRICAO:
        checks["status_reconhecido"] = Verificacao(ok=True)
    else:
        checks["status_reconhecido"] = Verificacao(
            ok=False, detalhe=f"Status desconhecido: '{status}'. Esperado: {sorted(ESTADOS_PRESCRICAO)}"
        )

    # 1.4 — tem itens
    if itens:
        checks["tem_itens"] = Verificacao(ok=True)
    else:
        checks["tem_itens"] = Verificacao(ok=False, detalhe="Prescrição sem itens.")

    # 1.5 — status dos itens reconhecidos
    itens_invalidos = [
        f"item {i+1} ({r['nome_medicamento']}): status '{r['status_item']}' não reconhecido"
        for i, r in enumerate(itens)
        if r["status_item"] not in ESTADOS_ITEM
    ]
    if itens_invalidos:
        checks["itens_status_reconhecidos"] = Verificacao(
            ok=False, detalhe="; ".join(itens_invalidos)
        )
    else:
        checks["itens_status_reconhecidos"] = Verificacao(ok=True)

    return checks


# ---------------------------------------------------------------------------
# Camada 2 — Integridade
# ---------------------------------------------------------------------------

def _camada_integridade(row, itens, eh_fisica: bool) -> dict[str, Verificacao]:
    if row is None:
        return {
            "hash_presente": Verificacao(ok=False, detalhe="Prescrição não encontrada."),
            "hash_integro":  Verificacao(ok=False, detalhe="Prescrição não encontrada."),
        }

    if eh_fisica:
        return {
            "hash_presente": _NA,
            "hash_integro":  _NA,
        }

    # 2.1 — hash presente
    hash_armazenado = row["assinatura_hash"]
    if not hash_armazenado:
        return {
            "hash_presente": Verificacao(
                ok=False,
                detalhe="prescricoes.assinatura_hash é NULL. "
                        "Execute novamente init_tables.py para aplicar a migration, "
                        "ou reemita a prescrição.",
            ),
            "hash_integro": Verificacao(
                ok=False,
                detalhe="Verificação bloqueada: hash ausente.",
            ),
        }

    checks = {"hash_presente": Verificacao(ok=True)}

    # 2.2 — hash íntegro: recomputar e comparar
    try:
        doc_result = montar_documento(
            protocolo       = row["protocolo"],
            data_emissao    = row["data_emissao"],
            tipo_emissao    = row["tipo_emissao"],
            assinatura_modo = row["assinatura_modo"],
            cns_prescritor  = row["cns_prescritor"],
            nome_prescritor = row["nome_prescritor"],
            cpf_paciente    = row["cpf_paciente"],
            nome_paciente   = row["nome_paciente"],
            itens           = [dict(r) for r in itens],
        )
        if doc_result.hash_sha256 == hash_armazenado:
            checks["hash_integro"] = Verificacao(ok=True)
        else:
            checks["hash_integro"] = Verificacao(
                ok=False,
                detalhe=(
                    f"Hash divergente. "
                    f"Armazenado: {hash_armazenado[:16]}... "
                    f"Recomputado: {doc_result.hash_sha256[:16]}... "
                    "O conteúdo da prescrição pode ter sido alterado após emissão."
                ),
            )
    except Exception as exc:
        checks["hash_integro"] = Verificacao(
            ok=False, detalhe=f"Erro ao montar documento canônico: {exc}"
        )

    return checks


# ---------------------------------------------------------------------------
# Camada 3 — CFM 2.299/2021
# ---------------------------------------------------------------------------

def _camada_cfm(row, itens, eh_cfm: bool) -> dict[str, Verificacao]:
    if row is None or not eh_cfm:
        msg = "Não aplicável (assinatura_modo não declara validade CFM)."
        return {
            "cpf_real":              _NA if not eh_cfm else Verificacao(ok=False, detalhe="Prescrição não encontrada."),
            "campos_cfm_por_item":   _NA if not eh_cfm else Verificacao(ok=False, detalhe="Prescrição não encontrada."),
            "assinatura_modo_valido": _NA if not eh_cfm else Verificacao(ok=False, detalhe="Prescrição não encontrada."),
        }

    checks: dict[str, Verificacao] = {}

    # 3.1 — CPF real (não sentinela)
    cpf = row["cpf_paciente"] or ""
    if cpf == _CPF_NAO_IDENTIFICADO or not cpf:
        checks["cpf_real"] = Verificacao(
            ok=False,
            detalhe=(
                "CPF sentinela '00000000000' detectado em prescrição com validade CFM. "
                "Prescrições ICP-Brasil exigem CPF real do paciente."
            ),
        )
    else:
        checks["cpf_real"] = Verificacao(ok=True)

    # 3.2 — Campos obrigatórios por item (posologia + quantidade + unidade_quantidade)
    itens_invalidos = []
    for i, item in enumerate(itens, start=1):
        ausentes = []
        if not item["quantidade"]:
            ausentes.append("quantidade")
        if not item["unidade_quantidade"]:
            ausentes.append("unidade_quantidade")
        if not item["posologia"] or not str(item["posologia"]).strip():
            ausentes.append("posologia")
        if ausentes:
            itens_invalidos.append(f"item {i} ({item['nome_medicamento']}): {ausentes}")

    if itens_invalidos:
        checks["campos_cfm_por_item"] = Verificacao(
            ok=False,
            detalhe=(
                "Campos obrigatórios CFM ausentes — Resolução 2.299/2021 "
                "(quantidade, unidade_quantidade, posologia): "
                + "; ".join(itens_invalidos)
            ),
        )
    else:
        checks["campos_cfm_por_item"] = Verificacao(ok=True)

    # 3.3 — assinatura_modo declarado é válido para CFM
    modo = row["assinatura_modo"]
    if modo in MODOS_COM_VALIDADE_CFM:
        checks["assinatura_modo_valido"] = Verificacao(ok=True)
    else:
        checks["assinatura_modo_valido"] = Verificacao(
            ok=False,
            detalhe=f"assinatura_modo='{modo}' não está em {sorted(MODOS_COM_VALIDADE_CFM)}.",
        )

    return checks


# ---------------------------------------------------------------------------
# Camada 4 — Metadados de assinatura digital
# ---------------------------------------------------------------------------

def _camada_assinatura_digital(row, assinatura_meta, eh_fisica: bool) -> dict[str, Verificacao]:
    if row is None:
        return {nome: Verificacao(ok=False, detalhe="Prescrição não encontrada.")
                for nome in ("metadados_registrados", "hash_assinatura_coerente", "tem_prova_criptografica", "status_assinatura")}

    if eh_fisica:
        return {
            "metadados_registrados":    _NA,
            "hash_assinatura_coerente": _NA,
            "tem_prova_criptografica":  _NA,
            "status_assinatura":        _NA,
        }

    checks: dict[str, Verificacao] = {}

    # 4.1 — metadados registrados
    if assinatura_meta is None:
        checks["metadados_registrados"] = Verificacao(
            ok=False,
            detalhe=(
                "Nenhum registro em prescricao_assinatura. "
                "Use POST /prescricoes/{protocolo}/assinatura para registrar."
            ),
        )
        checks["hash_assinatura_coerente"] = Verificacao(
            ok=False, detalhe="Bloqueado: metadados não registrados."
        )
        checks["tem_prova_criptografica"] = Verificacao(
            ok=False, detalhe="Bloqueado: metadados não registrados."
        )
        checks["status_assinatura"] = Verificacao(
            ok=False, detalhe="Nenhum registro de assinatura."
        )
        return checks

    checks["metadados_registrados"] = Verificacao(ok=True)

    # 4.2 — coerência do hash declarado
    hash_doc    = assinatura_meta["hash_documento"]
    hash_stored = row["assinatura_hash"]
    if hash_doc and hash_stored and hash_doc == hash_stored:
        checks["hash_assinatura_coerente"] = Verificacao(ok=True)
    elif not hash_doc:
        checks["hash_assinatura_coerente"] = Verificacao(
            ok=False, detalhe="hash_documento não foi declarado nos metadados de assinatura."
        )
    else:
        checks["hash_assinatura_coerente"] = Verificacao(
            ok=False,
            detalhe=(
                f"hash_documento declarado ({hash_doc[:16]}...) diverge de "
                f"prescricoes.assinatura_hash ({(hash_stored or 'null')[:16]}...). "
                "O documento assinado pode não corresponder ao documento canônico emitido."
            ),
        )

    # 4.3 — prova criptográfica presente
    tem_b64 = bool(assinatura_meta["dados_assinatura_b64"])
    checks["tem_prova_criptografica"] = Verificacao(
        ok=tem_b64,
        detalhe=(
            None if tem_b64
            else "dados_assinatura_b64 ausente (PKCS#7/CAdES). MVP stub: campo não obrigatório nesta fase."
        ),
    )

    # 4.4 — status de validação atual
    status_v = assinatura_meta["status_validacao"]
    descricao = DESCRICAO_STATUS_ASSINATURA.get(status_v, status_v)
    checks["status_assinatura"] = Verificacao(
        ok=status_v == "assinada_valida",
        detalhe=descricao,
    )

    return checks


# ---------------------------------------------------------------------------
# Camada 5 — ICP-Brasil (stub MVP)
# ---------------------------------------------------------------------------

_STUB_MSG = (
    "Módulo ICP-Brasil não integrado (MVP stub). "
    "Esta verificação será habilitada na integração com token A1/A3 ou API gov.br."
)

def _camada_icp_brasil(assinatura_modo: Optional[str]) -> dict[str, Verificacao]:
    if assinatura_modo not in MODOS_COM_VALIDADE_CFM:
        return {
            "certificado_verificado": _NA,
            "ocsp_crl_verificado":    _NA,
            "assinatura_pkcs7_valida": _NA,
        }

    return {
        "certificado_verificado":  Verificacao(ok=False, detalhe=_STUB_MSG),
        "ocsp_crl_verificado":     Verificacao(ok=False, detalhe=_STUB_MSG),
        "assinatura_pkcs7_valida": Verificacao(ok=False, detalhe=_STUB_MSG),
    }


# ---------------------------------------------------------------------------
# Camada 6 — CNES (ultrasensível)
# ---------------------------------------------------------------------------

# Conselhos de classe que habilitam prescrição
_CONSELHOS_PRESCRICAO = {
    "71": "CRM",   # Conselho Regional de Medicina
    "75": "CRO",   # Conselho Regional de Odontologia
    "26": "CRM",   # variante CRM em alguns registros históricos
}

# Limiar de similaridade de nome (0–1). Abaixo → falha dura.
_NOME_SIMILARIDADE_MIN = 0.70


def _similaridade_nome(a: str, b: str) -> float:
    """Razão de similaridade entre dois nomes (case-insensitive, sem acentos simples)."""
    def norm(s: str) -> str:
        return " ".join(s.upper().split())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def _camada_cnes(
    conn,
    cns_prescritor: Optional[str],
    nome_prescritor: Optional[str],
    eh_fisica: bool,
) -> dict[str, Verificacao]:
    """
    Cruzamento do CNS do prescritor com a base CNES Brasil (DataSUS).

    Verificações:
      cns_encontrado       — CNS existe em profissionais_cnes
      nome_consistente     — nome declarado ≈ nome CNES (similaridade ≥ 0.70)
      cbo_prescritivo      — ao menos 1 vínculo com CBO prescritivo (2251/2252/2232)
      conselho_habilitado  — ao menos 1 vínculo com CRM (71) ou CRO (75)
      vinculo_institucional — ao menos 1 estabelecimento vinculado no snapshot

    Falha dura vs. falha leve:
      - CNS não encontrado → cns_encontrado.ok=False;
        demais verificações marcadas _NA (snapshot pode estar desatualizado).
      - CNS encontrado + nome ou CBO contradizem → ok=False (falha dura → invalido).
    """
    # Prescrição física: CNES não se aplica (papel, sem ciclo digital)
    if eh_fisica or not cns_prescritor:
        return {
            "cns_encontrado":       _NA,
            "nome_consistente":     _NA,
            "cbo_prescritivo":      _NA,
            "conselho_habilitado":  _NA,
            "vinculo_institucional": _NA,
        }

    cns_norm = "".join(c for c in (cns_prescritor or "") if c.isdigit())

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    try:
        cnes_conn = _get_cnes_conn()
        try:
            rows = cnes_conn.execute(
                """
                SELECT
                    p.NO_PROFISSIONAL                       AS nome_cnes,
                    r.CO_CONSELHO_CLASSE                    AS conselho,
                    r.NU_REGISTRO                           AS registro,
                    r.SG_UF_CRM                             AS uf_registro,
                    r.CO_CBO                                AS cbo,
                    COUNT(DISTINCT r.CO_UNIDADE)            AS n_vinculos
                FROM profissionais_cnes p
                JOIN relacao_prof_estab r
                  ON r.CO_PROFISSIONAL_SUS = p.CO_PROFISSIONAL_SUS
                WHERE CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) = ?
                GROUP BY p.NO_PROFISSIONAL, r.CO_CONSELHO_CLASSE,
                         r.NU_REGISTRO, r.SG_UF_CRM, r.CO_CBO
                """,
                (cns_norm,),
            ).fetchall()
        finally:
            cnes_conn.close()
    except Exception as exc:
        msg = f"Erro ao consultar base CNES: {exc}"
        return {k: Verificacao(ok=False, detalhe=msg)
                for k in ("cns_encontrado", "nome_consistente",
                          "cbo_prescritivo", "conselho_habilitado",
                          "vinculo_institucional")}

    # ── CNS não encontrado → falha leve ───────────────────────────────────
    if not rows:
        detalhe = (
            f"CNS {cns_norm} não localizado na base CNES Brasil (snapshot dez/2025). "
            "O profissional pode ser recente ou ter vínculo exclusivamente privado. "
            "Validação CNES inconclusiva — auditoria manual recomendada."
        )
        return {
            "cns_encontrado": Verificacao(ok=False, detalhe=detalhe),
            "nome_consistente":      _NA,
            "cbo_prescritivo":       _NA,
            "conselho_habilitado":   _NA,
            "vinculo_institucional": _NA,
        }

    checks: dict[str, Verificacao] = {}
    checks["cns_encontrado"] = Verificacao(ok=True)

    # ── Nome mais frequente no CNES para este CNS ─────────────────────────
    nome_cnes = rows[0]["nome_cnes"] or ""
    sim = _similaridade_nome(nome_prescritor or "", nome_cnes)
    if sim >= _NOME_SIMILARIDADE_MIN:
        checks["nome_consistente"] = Verificacao(
            ok=True,
            detalhe=f"Nome CNES: '{nome_cnes}' (similaridade {sim:.0%}).",
        )
    else:
        checks["nome_consistente"] = Verificacao(
            ok=False,
            detalhe=(
                f"Nome declarado '{nome_prescritor}' diverge do nome CNES "
                f"'{nome_cnes}' (similaridade {sim:.0%} < {_NOME_SIMILARIDADE_MIN:.0%}). "
                "Possível uso indevido de CNS alheio."
            ),
        )

    # ── CBO prescritivo ───────────────────────────────────────────────────
    cbos_prescritivos = [
        r["cbo"] for r in rows
        if r["cbo"] and any(r["cbo"].startswith(p) for p in CBO_PREFIXES)
    ]
    if cbos_prescritivos:
        cbos_str = ", ".join(sorted(set(cbos_prescritivos)))
        checks["cbo_prescritivo"] = Verificacao(
            ok=True,
            detalhe=f"CBO prescritivo confirmado: {cbos_str}.",
        )
    else:
        cbos_encontrados = sorted({r["cbo"] for r in rows if r["cbo"]})
        checks["cbo_prescritivo"] = Verificacao(
            ok=False,
            detalhe=(
                f"Nenhum CBO prescritivo (2251*/2252*/2232*) encontrado. "
                f"CBOs registrados: {cbos_encontrados or '—'}. "
                "O profissional pode não ter habilitação prescritiva no CNES."
            ),
        )

    # ── Conselho habilitado ───────────────────────────────────────────────
    conselhos = {
        r["conselho"]: (r["registro"], r["uf_registro"])
        for r in rows
        if r["conselho"] in _CONSELHOS_PRESCRICAO
    }
    if conselhos:
        detalhes_conselho = [
            f"{_CONSELHOS_PRESCRICAO[c]}-{uf or '??'} {reg or '???'}"
            for c, (reg, uf) in conselhos.items()
        ]
        checks["conselho_habilitado"] = Verificacao(
            ok=True,
            detalhe="Conselho: " + "; ".join(detalhes_conselho) + ".",
        )
    else:
        conselhos_todos = sorted({r["conselho"] for r in rows if r["conselho"]})
        checks["conselho_habilitado"] = Verificacao(
            ok=False,
            detalhe=(
                f"Nenhum conselho habilitador para prescrição (CRM=71, CRO=75) encontrado. "
                f"Conselhos registrados: {conselhos_todos or '—'}."
            ),
        )

    # ── Vínculo institucional ─────────────────────────────────────────────
    total_vinculos = sum(r["n_vinculos"] for r in rows)
    if total_vinculos > 0:
        checks["vinculo_institucional"] = Verificacao(
            ok=True,
            detalhe=f"{total_vinculos} vínculo(s) institucional(is) ativo(s) no CNES.",
        )
    else:
        checks["vinculo_institucional"] = Verificacao(
            ok=False,
            detalhe=(
                "Nenhum vínculo institucional ativo encontrado no snapshot CNES. "
                "Profissional pode atuar exclusivamente em consultório privado."
            ),
        )

    return checks


# ---------------------------------------------------------------------------
# Resultado geral
# ---------------------------------------------------------------------------

def _calcular_resultado_geral(
    estrutural:  dict[str, Verificacao],
    integridade: dict[str, Verificacao],
    cfm:         dict[str, Verificacao],
    assinatura:  dict[str, Verificacao],
    icp:         dict[str, Verificacao],
    cnes:        dict[str, Verificacao],
    eh_fisica:   bool,
    eh_cfm:      bool,
) -> str:
    """
    Calcula o resultado geral a partir das camadas.

    Precedência:
      1. Qualquer falha estrutural ou de integridade → "invalido"
      2. Contradição dura CNES (nome/CBO/conselho incompatíveis) → "invalido"
      3. física sem falhas estruturais → "valido_fisico"
      4. Sem modo CFM + integridade ok:
           CNES confirmado → "valido_estrutural_cnes"
           caso contrário  → "valido_estrutural"
      5. CFM ok + ICP pendente:
           CNES confirmado → "valido_cfm_cnes_stub"
           caso contrário  → "valido_cfm_stub"
      6. ICP-Brasil verificado (futuro) → "valido_cfm_completo"
    """
    def falhou(camada: dict[str, Verificacao]) -> bool:
        return any(v.aplicavel and not v.ok for v in camada.values())

    def cnes_confirmado() -> bool:
        """True se todas as verificações CNES aplicáveis passaram."""
        return all(
            not v.aplicavel or v.ok
            for v in cnes.values()
        )

    def cnes_contradicao_dura() -> bool:
        """
        True se o CNS foi encontrado mas nome, CBO ou conselho contradizem
        os dados declarados. Contradição ativa → invalido.
        CNS simplesmente ausente (cns_encontrado=False) → falha leve, não bloqueia.
        """
        cns_ok = cnes.get("cns_encontrado")
        if cns_ok is None or not cns_ok.aplicavel or not cns_ok.ok:
            return False   # CNS não encontrado → falha leve, não é contradição
        # CNS foi encontrado: falha em nome/CBO/conselho é contradição dura
        for chave in ("nome_consistente", "cbo_prescritivo", "conselho_habilitado"):
            v = cnes.get(chave)
            if v and v.aplicavel and not v.ok:
                return True
        return False

    if falhou(estrutural) or falhou(integridade):
        return "invalido"

    if cnes_contradicao_dura():
        return "invalido"

    if eh_fisica:
        return "valido_fisico"

    if not eh_cfm:
        return "valido_estrutural_cnes" if cnes_confirmado() else "valido_estrutural"

    if falhou(cfm):
        return "invalido"

    # CFM declarado: verifica ICP e depois se metadados foram ao menos registrados
    if not falhou(icp):
        return "valido_cfm_completo"   # nunca ocorre no MVP

    meta_registrados = assinatura.get("metadados_registrados")
    tem_meta = meta_registrados and meta_registrados.aplicavel and meta_registrados.ok
    if tem_meta:
        return "valido_cfm_cnes_stub" if cnes_confirmado() else "valido_cfm_stub"

    # CFM campos ok mas sem metadados de assinatura registrados ainda
    return "valido_estrutural_cnes" if cnes_confirmado() else "valido_estrutural"
