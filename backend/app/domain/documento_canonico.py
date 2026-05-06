"""
documento_canonico.py
=====================
Representação canônica de uma prescrição PicSaúde para fins de assinatura
digital (ICP-Brasil / gov.br).

PRINCÍPIO
---------
A assinatura digital não assina "um PDF" nem "um HTML". Ela assina um
conjunto determinístico de campos que representam a intenção clínica do
prescritor. Para que a verificação seja possível anos depois, o documento
canônico deve:

  1. Ser determinístico: o mesmo conteúdo sempre gera a mesma string.
  2. Ser compacto: sem espaços, sem quebras de linha.
  3. Ter ordem fixa de campos: uso de sort_keys=True no JSON.
  4. Usar apenas identificadores semânticos: CNS, CPF — nunca IDs internos.
  5. Excluir estado mutable: status, data_validade, created_at, updated_at.

O hash SHA-256 do documento serializado é armazenado em
prescricoes.assinatura_hash como âncora de integridade.
A prova criptográfica completa (assinatura PKCS#7 / CAdES) será adicionada
na integração com token A1/A3 ou com a API gov.br (versão pós-MVP).

VERSÃO DO ESQUEMA
-----------------
versao_esquema="1" identifica esta estrutura. Qualquer alteração de campos
obrigatórios deve incrementar a versão e adicionar lógica de migração de
hashes antigos.

CAMPOS INCLUÍDOS
----------------
  versao_esquema   string fixo "1"
  protocolo        UUID da prescrição
  tipo_emissao     nova | correcao | renovacao
  assinatura_modo  icp_brasil_local | gov_br_nuvem | null
  data_emissao     ISO 8601 UTC (ex: "2026-03-14T10:30:00.000000")
  prescritor       { cns, nome }
  paciente         { cpf, nome }
  itens            [ { ordem, nome_medicamento, concentracao, quantidade, unidade_quantidade, posologia } ]

CAMPOS EXCLUÍDOS INTENCIONALMENTE
----------------------------------
  id / prescritor_id / paciente_id  IDs internos do banco
  status                            estado mutable
  origem_prescricao_id              linkagem interna (não faz parte do conteúdo clínico)
  data_validade                     derivada, calculada externamente
  created_at / updated_at           timestamps de infraestrutura
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Versão do esquema — incrementar se campos obrigatórios mudarem
# ---------------------------------------------------------------------------

VERSAO_ESQUEMA = "2"  # v2: unidade_quantidade adicionada ao hash de cada item


# ---------------------------------------------------------------------------
# Resultado imutável
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentoCanonicoResult:
    """
    Encapsula os três artefatos produzidos para uma prescrição:

    documento     dict Python com campos ordenados (para inspeção/debug)
    serializado   string JSON compact/sorted (base para hash e assinatura)
    hash_sha256   hex digest SHA-256 do serializado codificado em UTF-8
    """
    documento:   dict
    serializado: str
    hash_sha256: str


# ---------------------------------------------------------------------------
# Construção do documento a partir de valores já normalizados
# (chamado em criar_prescricao após todas as inserções)
# ---------------------------------------------------------------------------

def montar_documento(
    *,
    protocolo:       str,
    data_emissao,          # str ou datetime — normalizado internamente
    tipo_emissao:    str,
    assinatura_modo: Optional[str],
    cns_prescritor:  str,
    nome_prescritor: str,
    cpf_paciente:    str,
    nome_paciente:   str,
    itens: list,       # List[ItemIn] ou list[dict] com os campos do item
) -> DocumentoCanonicoResult:
    """
    Monta o documento canônico a partir de valores já normalizados.

    Parâmetros
    ----------
    itens : sequência de objetos com atributos (ItemIn) ou dicts com chaves:
            nome_medicamento, concentracao, quantidade, unidade_quantidade, posologia.
            A ordem da sequência define o campo `ordem` (1-based).
    """
    # PostgreSQL retorna colunas TIMESTAMP como datetime; normalizar para ISO string
    if hasattr(data_emissao, "isoformat"):
        data_emissao = data_emissao.isoformat()

    def _ler(obj, campo):
        """Lê atributo de objeto Pydantic ou chave de dict."""
        if isinstance(obj, dict):
            return obj.get(campo)
        return getattr(obj, campo, None)

    itens_canonicos = [
        {
            "concentracao":      _ler(item, "concentracao"),
            "nome_medicamento":  _ler(item, "nome_medicamento"),
            "ordem":             idx + 1,
            "posologia":         _ler(item, "posologia"),
            "quantidade":        _ler(item, "quantidade"),
            "unidade_quantidade": _ler(item, "unidade_quantidade"),
        }
        for idx, item in enumerate(itens)
    ]

    documento = {
        "assinatura_modo": assinatura_modo,
        "data_emissao":    data_emissao,
        "itens":           itens_canonicos,
        "paciente": {
            "cpf":  cpf_paciente,
            "nome": nome_paciente,
        },
        "prescritor": {
            "cns":  cns_prescritor,
            "nome": nome_prescritor,
        },
        "protocolo":       protocolo,
        "tipo_emissao":    tipo_emissao,
        "versao_esquema":  VERSAO_ESQUEMA,
    }

    return _finalizar(documento)


# ---------------------------------------------------------------------------
# Reconstrução do documento a partir do banco (GET /documento)
# ---------------------------------------------------------------------------

def montar_documento_de_conn(conn, protocolo: str) -> Optional[DocumentoCanonicoResult]:
    """
    Reconstrói o documento canônico consultando o banco.
    Retorna None se o protocolo não existir.

    Usado por GET /prescricoes/{protocolo}/documento para:
      - Inspecionar o conteúdo que foi (ou será) assinado.
      - Verificar integridade: re-calcular hash e comparar com assinatura_hash.
    """
    row = conn.execute(
        """
        SELECT
            p.protocolo,
            p.data_emissao,
            p.tipo_emissao,
            p.assinatura_modo,
            p.assinatura_hash,
            pr.cns        AS cns_prescritor,
            pr.nome       AS nome_prescritor,
            pa.cpf        AS cpf_paciente,
            pa.nome       AS nome_paciente
        FROM prescricoes p
        JOIN prescritores pr ON pr.id = p.prescritor_id
        JOIN pacientes    pa ON pa.id = p.paciente_id
        WHERE p.protocolo = ?
        """,
        (protocolo,),
    ).fetchone()

    if not row:
        return None

    itens_rows = conn.execute(
        """
        SELECT nome_medicamento, concentracao, quantidade, unidade_quantidade, posologia
          FROM prescricao_itens
         WHERE prescricao_id = (SELECT id FROM prescricoes WHERE protocolo = ?)
         ORDER BY id
        """,
        (protocolo,),
    ).fetchall()

    itens_dicts = [dict(r) for r in itens_rows]

    resultado = montar_documento(
        protocolo       = row["protocolo"],
        data_emissao    = row["data_emissao"],
        tipo_emissao    = row["tipo_emissao"],
        assinatura_modo = row["assinatura_modo"],
        cns_prescritor  = row["cns_prescritor"],
        nome_prescritor = row["nome_prescritor"],
        cpf_paciente    = row["cpf_paciente"],
        nome_paciente   = row["nome_paciente"],
        itens           = itens_dicts,
    )

    return resultado, row["assinatura_hash"]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _finalizar(documento: dict) -> DocumentoCanonicoResult:
    """
    Serializa e calcula o hash do documento.

    sort_keys=True  →  campos em ordem alfabética (determinismo entre envs)
    separators      →  sem espaços (compacto, sem ambiguidade de whitespace)
    ensure_ascii    →  False para preservar acentos (UTF-8 nativo)
    """
    serializado = json.dumps(
        documento,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    hash_sha256 = hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    return DocumentoCanonicoResult(
        documento=documento,
        serializado=serializado,
        hash_sha256=hash_sha256,
    )
