#!/usr/bin/env python3
"""
PicSaúde — Auditoria de Integridade do Ledger
==============================================
Ticket 3: investigação de consistência entre objetos sanitários e eventos.

Regras absolutas deste script:
  - NUNCA chama conn.commit()
  - NUNCA altera dados
  - CPFs mascarados no formato ***.XXX.XXX-**
  - Nomes de pacientes NÃO aparecem na saída

Uso:
  python3 auditar_integridade_ledger.py [--db PATH] [--out DIR]
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_DB   = os.environ.get(
    "PIX_SAUDE_DB",
    str(_PROJECT_ROOT / "data" / "pix_saude_pe.db"),
)
_REPORTS_DIR  = Path(__file__).parent / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_cpf(cpf) -> str:
    """Ofusca CPF: ***.456.789-** (LGPD)."""
    if not cpf:
        return "(sem cpf)"
    raw = re.sub(r"\D", "", str(cpf))
    if len(raw) != 11:
        return "***INVÁLIDO***"
    return f"***.{raw[3:6]}.{raw[6:9]}-**"


def _conn(db_path: str) -> sqlite3.Connection:
    """Abre conexão somente-leitura. NUNCA faz commit."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return r is not None


# ---------------------------------------------------------------------------
# Gravidade
# ---------------------------------------------------------------------------

ALTA   = "ALTA"
MEDIA  = "MÉDIA"
BAIXA  = "BAIXA"


class Inconsistencia:
    def __init__(self, dominio: str, tipo: str, gravidade: str,
                 objeto_id, descricao: str, dado_extra: str = ""):
        self.dominio    = dominio
        self.tipo       = tipo
        self.gravidade  = gravidade
        self.objeto_id  = objeto_id
        self.descricao  = descricao
        self.dado_extra = dado_extra

    def __str__(self) -> str:
        extra = f" | {self.dado_extra}" if self.dado_extra else ""
        return (
            f"[{self.gravidade}] {self.dominio} · {self.tipo} "
            f"· id={self.objeto_id}{extra} · {self.descricao}"
        )


# ---------------------------------------------------------------------------
# Auditoria genérica por domínio
# ---------------------------------------------------------------------------

def _auditar_dominio(
    conn: sqlite3.Connection,
    dominio: str,
    tabela_principal: str,
    tabela_eventos: str,
    fk_col: str,         # coluna em tabela_eventos que referencia tabela_principal
    tipo_col: str,       # coluna com o tipo/nome do evento
    eventos_iniciais: list[str],  # tipos que indicam criação
) -> list[Inconsistencia]:
    """Auditoria básica de consistência entre objeto e seus eventos."""

    inconsistencias: list[Inconsistencia] = []

    if not _table_exists(conn, tabela_principal):
        return inconsistencias
    if not _table_exists(conn, tabela_eventos):
        return inconsistencias

    # A. Objetos sem nenhum evento
    sem_evento = conn.execute(f"""
        SELECT p.id, p.protocolo
        FROM {tabela_principal} p
        LEFT JOIN {tabela_eventos} e ON e.{fk_col} = p.id
        WHERE e.id IS NULL
    """).fetchall()

    for row in sem_evento:
        inconsistencias.append(Inconsistencia(
            dominio    = dominio,
            tipo       = "objeto_sem_evento",
            gravidade  = ALTA,
            objeto_id  = row["id"],
            descricao  = f"Protocolo {row['protocolo']} não possui nenhum evento no ledger",
        ))

    # B. Eventos órfãos (apontam para objeto inexistente)
    orfaos = conn.execute(f"""
        SELECT e.id, e.{fk_col}, e.{tipo_col}
        FROM {tabela_eventos} e
        LEFT JOIN {tabela_principal} p ON p.id = e.{fk_col}
        WHERE p.id IS NULL
    """).fetchall()

    for row in orfaos:
        inconsistencias.append(Inconsistencia(
            dominio    = dominio,
            tipo       = "evento_orfao",
            gravidade  = ALTA,
            objeto_id  = row["id"],
            descricao  = (
                f"Evento '{row[tipo_col]}' referencia {fk_col}={row[fk_col]} "
                "inexistente na tabela principal"
            ),
        ))

    # C. Múltiplos eventos iniciais (se vocabulário definido)
    if eventos_iniciais:
        placeholders = ",".join("?" * len(eventos_iniciais))
        duplos = conn.execute(f"""
            SELECT {fk_col}, COUNT(*) AS cnt
            FROM {tabela_eventos}
            WHERE {tipo_col} IN ({placeholders})
            GROUP BY {fk_col}
            HAVING cnt > 1
        """, eventos_iniciais).fetchall()

        for row in duplos:
            inconsistencias.append(Inconsistencia(
                dominio    = dominio,
                tipo       = "multiplos_eventos_iniciais",
                gravidade  = MEDIA,
                objeto_id  = row[fk_col],
                descricao  = (
                    f"Objeto possui {row['cnt']} eventos iniciais "
                    f"({', '.join(eventos_iniciais)})"
                ),
            ))

    # D. Objetos com status ativo (não terminal) sem evento inicial
    if eventos_iniciais:
        status_terminais = (
            "'dispensada','cancelada','encerrada_localmente','expirada'"  # prescrições
            ",'encerrado','cancelado','encerrado_fisico'"                 # outros
        )
        try:
            placeholders = ",".join("?" * len(eventos_iniciais))
            sem_inicial = conn.execute(f"""
                SELECT p.id, p.protocolo, p.status
                FROM {tabela_principal} p
                WHERE p.status NOT IN ({status_terminais})
                  AND NOT EXISTS (
                    SELECT 1 FROM {tabela_eventos} e
                    WHERE e.{fk_col} = p.id
                      AND e.{tipo_col} IN ({placeholders})
                  )
            """, eventos_iniciais).fetchall()

            for row in sem_inicial:
                inconsistencias.append(Inconsistencia(
                    dominio    = dominio,
                    tipo       = "ativo_sem_evento_inicial",
                    gravidade  = ALTA,
                    objeto_id  = row["id"],
                    descricao  = (
                        f"Objeto ativo (status='{row['status']}') sem evento de criação "
                        f"({', '.join(eventos_iniciais)}) no ledger"
                    ),
                ))
        except sqlite3.OperationalError:
            # tabela_principal pode não ter coluna 'status' (agendamentos usa status)
            pass

    return inconsistencias


# ---------------------------------------------------------------------------
# Auditoria profunda de prescrições
# ---------------------------------------------------------------------------

def _auditar_prescricoes_profundo(
    conn: sqlite3.Connection,
) -> list[Inconsistencia]:
    inconsistencias: list[Inconsistencia] = []

    if not _table_exists(conn, "prescricoes"):
        return inconsistencias

    # 1. Prescrições sem evento inicial esperado (já cobertas no genérico,
    #    mas aqui distinguimos digital vs físico)
    sem_inicial_digital = conn.execute("""
        SELECT p.id, p.protocolo, p.tipo_emissao, p.status,
               EXISTS(
                   SELECT 1 FROM prescricao_eventos e2
                   WHERE e2.prescricao_id = p.id
                     AND e2.tipo_evento = 'RECONCILIACAO_MANUAL'
               ) AS reconciliado
        FROM prescricoes p
        WHERE p.tipo_emissao != 'fisica'
          AND NOT EXISTS (
            SELECT 1 FROM prescricao_eventos e
            WHERE e.prescricao_id = p.id
              AND e.tipo_evento IN ('prescricao_emitida','prescricao_renovada',
                                    'prescricao_corrigida')
          )
    """).fetchall()

    for row in sem_inicial_digital:
        # Objeto reconciliado via Ticket 4: rebaixar para MÉDIA (sem evento normal,
        # mas trilha de auditoria registrada com RECONCILIACAO_MANUAL)
        grav = MEDIA if row["reconciliado"] else ALTA
        nota = " (objeto reconciliado via RECONCILIACAO_MANUAL)" if row["reconciliado"] else ""
        inconsistencias.append(Inconsistencia(
            dominio    = "prescricoes",
            tipo       = "digital_sem_evento_emissao",
            gravidade  = grav,
            objeto_id  = row["id"],
            descricao  = (
                f"Prescrição digital (tipo={row['tipo_emissao']}, "
                f"status={row['status']}) sem evento prescricao_emitida/renovada/corrigida"
                f"{nota}"
            ),
            dado_extra = f"protocolo={row['protocolo']}",
        ))

    sem_inicial_fisica = conn.execute("""
        SELECT p.id, p.protocolo, p.status,
               EXISTS(
                   SELECT 1 FROM prescricao_eventos e2
                   WHERE e2.prescricao_id = p.id
                     AND e2.tipo_evento = 'RECONCILIACAO_MANUAL'
               ) AS reconciliado
        FROM prescricoes p
        WHERE p.tipo_emissao = 'fisica'
          AND NOT EXISTS (
            SELECT 1 FROM prescricao_eventos e
            WHERE e.prescricao_id = p.id
              AND e.tipo_evento = 'prescricao_impressa'
          )
    """).fetchall()

    for row in sem_inicial_fisica:
        grav = MEDIA if row["reconciliado"] else ALTA
        nota = " (objeto reconciliado via RECONCILIACAO_MANUAL)" if row["reconciliado"] else ""
        inconsistencias.append(Inconsistencia(
            dominio    = "prescricoes",
            tipo       = "fisica_sem_evento_impressa",
            gravidade  = grav,
            objeto_id  = row["id"],
            descricao  = (
                f"Prescrição física (status={row['status']}) "
                f"sem evento prescricao_impressa no ledger{nota}"
            ),
            dado_extra = f"protocolo={row['protocolo']}",
        ))

    # 2. Prescrições com itens mas sem nenhum evento
    com_itens_sem_evento = conn.execute("""
        SELECT p.id, p.protocolo, p.status, COUNT(pi.id) AS n_itens
        FROM prescricoes p
        JOIN prescricao_itens pi ON pi.prescricao_id = p.id
        LEFT JOIN prescricao_eventos e ON e.prescricao_id = p.id
        WHERE e.id IS NULL
        GROUP BY p.id
    """).fetchall()

    for row in com_itens_sem_evento:
        inconsistencias.append(Inconsistencia(
            dominio    = "prescricoes",
            tipo       = "com_itens_sem_evento",
            gravidade  = ALTA,
            objeto_id  = row["id"],
            descricao  = (
                f"Prescrição com {row['n_itens']} item(ns) "
                "mas sem nenhum evento no ledger"
            ),
            dado_extra = f"protocolo={row['protocolo']}, status={row['status']}",
        ))

    # 3. Prescrições com custódia mas sem evento de transferência
    if _table_exists(conn, "prescricao_custodia"):
        com_custodia_sem_evento = conn.execute("""
            SELECT p.id, p.protocolo, COUNT(c.id) AS n_custodia
            FROM prescricoes p
            JOIN prescricao_custodia c ON c.prescricao_id = p.id
            WHERE NOT EXISTS (
                SELECT 1 FROM prescricao_eventos e
                WHERE e.prescricao_id = p.id
                  AND e.tipo_evento = 'custodia_transferida'
            )
            GROUP BY p.id
        """).fetchall()

        for row in com_custodia_sem_evento:
            inconsistencias.append(Inconsistencia(
                dominio    = "prescricoes",
                tipo       = "custodia_sem_evento_transferencia",
                gravidade  = MEDIA,
                objeto_id  = row["id"],
                descricao  = (
                    f"Prescrição com {row['n_custodia']} registro(s) de custódia "
                    "sem evento custodia_transferida no ledger"
                ),
                dado_extra = f"protocolo={row['protocolo']}",
            ))

    # 4. Prescrições assinadas (assinatura_hash preenchido) sem evento assinatura_registrada
    if _table_exists(conn, "prescricao_assinatura"):
        assinadas_sem_evento = conn.execute("""
            SELECT p.id, p.protocolo, p.status,
                   EXISTS(
                       SELECT 1 FROM prescricao_eventos e2
                       WHERE e2.prescricao_id = p.id
                         AND e2.tipo_evento = 'RECONCILIACAO_MANUAL'
                   ) AS reconciliado
            FROM prescricoes p
            JOIN prescricao_assinatura a ON a.prescricao_id = p.id
            WHERE NOT EXISTS (
                SELECT 1 FROM prescricao_eventos e
                WHERE e.prescricao_id = p.id
                  AND e.tipo_evento = 'assinatura_registrada'
            )
        """).fetchall()

        for row in assinadas_sem_evento:
            # Objeto reconciliado: assinatura pré-ledger coberta pelo RECONCILIACAO_MANUAL
            grav_ass = BAIXA if row["reconciliado"] else MEDIA
            inconsistencias.append(Inconsistencia(
                dominio    = "prescricoes",
                tipo       = "assinatura_sem_evento",
                gravidade  = grav_ass,
                objeto_id  = row["id"],
                descricao  = (
                    f"Prescrição com registro de assinatura (prescricao_assinatura) "
                    "sem evento assinatura_registrada no ledger"
                ),
                dado_extra = f"protocolo={row['protocolo']}, status={row['status']}",
            ))

    # 5. Prescrições físicas sem status encerrada_localmente
    fisicas_status_errado = conn.execute("""
        SELECT p.id, p.protocolo, p.status
        FROM prescricoes p
        WHERE p.tipo_emissao = 'fisica'
          AND p.status != 'encerrada_localmente'
    """).fetchall()

    for row in fisicas_status_errado:
        inconsistencias.append(Inconsistencia(
            dominio    = "prescricoes",
            tipo       = "fisica_status_inconsistente",
            gravidade  = MEDIA,
            objeto_id  = row["id"],
            descricao  = (
                f"Prescrição física com status '{row['status']}' "
                "(esperado: encerrada_localmente)"
            ),
            dado_extra = f"protocolo={row['protocolo']}",
        ))

    # 6. Items com status encerrado_fisico mas prescrição não é fisica
    if _table_exists(conn, "prescricao_itens"):
        itens_fisico_digital = conn.execute("""
            SELECT p.id, p.protocolo, p.tipo_emissao, COUNT(pi.id) AS n
            FROM prescricoes p
            JOIN prescricao_itens pi ON pi.prescricao_id = p.id
            WHERE pi.status_item = 'encerrado_fisico'
              AND p.tipo_emissao != 'fisica'
            GROUP BY p.id
        """).fetchall()

        for row in itens_fisico_digital:
            inconsistencias.append(Inconsistencia(
                dominio    = "prescricoes",
                tipo       = "item_encerrado_fisico_em_prescricao_digital",
                gravidade  = ALTA,
                objeto_id  = row["id"],
                descricao  = (
                    f"{row['n']} item(ns) com status encerrado_fisico "
                    f"em prescrição digital (tipo_emissao={row['tipo_emissao']})"
                ),
                dado_extra = f"protocolo={row['protocolo']}",
            ))

    return inconsistencias


# ---------------------------------------------------------------------------
# Auditoria de dispensações
# ---------------------------------------------------------------------------

def _auditar_dispensacoes(conn: sqlite3.Connection) -> list[Inconsistencia]:
    inconsistencias: list[Inconsistencia] = []

    if not _table_exists(conn, "dispensacoes"):
        return inconsistencias

    # Dispensações sem evento item_dispensado correspondente
    disp_sem_evento = conn.execute("""
        SELECT d.id, d.prescricao_item_id, pi.prescricao_id
        FROM dispensacoes d
        JOIN prescricao_itens pi ON pi.id = d.prescricao_item_id
        WHERE NOT EXISTS (
            SELECT 1 FROM prescricao_eventos e
            WHERE e.prescricao_id = pi.prescricao_id
              AND e.tipo_evento IN ('dispensacao_registrada','dispensacao_parcial',
                                    'item_dispensado')
        )
    """).fetchall()

    for row in disp_sem_evento:
        inconsistencias.append(Inconsistencia(
            dominio    = "dispensacoes",
            tipo       = "dispensacao_sem_evento_ledger",
            gravidade  = ALTA,
            objeto_id  = row["id"],
            descricao  = (
                f"Dispensação (prescricao_item_id={row['prescricao_item_id']}) "
                "sem evento de dispensação no ledger da prescrição"
            ),
        ))

    return inconsistencias


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------

def _auditar_db(db_path: str) -> tuple[list[Inconsistencia], dict]:
    """Retorna lista de inconsistências e estatísticas."""
    conn = _conn(db_path)
    # SEGURANÇA: nunca chamar conn.commit() neste script
    stats = {}
    all_inc: list[Inconsistencia] = []

    # ── Domínio 1: Prescrições ──────────────────────────────────────────────
    inc = _auditar_dominio(
        conn,
        dominio          = "prescricoes",
        tabela_principal = "prescricoes",
        tabela_eventos   = "prescricao_eventos",
        fk_col           = "prescricao_id",
        tipo_col         = "tipo_evento",
        eventos_iniciais = ["prescricao_emitida", "prescricao_impressa",
                            "prescricao_renovada", "prescricao_corrigida",
                            "RECONCILIACAO_MANUAL"],
    )
    inc += _auditar_prescricoes_profundo(conn)
    inc += _auditar_dispensacoes(conn)
    stats["prescricoes"] = {
        "total": _count(conn, "prescricoes"),
        "eventos": _count(conn, "prescricao_eventos"),
        "inconsistencias": len(inc),
    }
    all_inc += inc

    # ── Domínio 2: Pedidos de Exame ─────────────────────────────────────────
    inc = _auditar_dominio(
        conn,
        dominio          = "pedidos_exame",
        tabela_principal = "pedidos_exame",
        tabela_eventos   = "pedido_exame_eventos",
        fk_col           = "pedido_id",
        tipo_col         = "tipo_evento",
        eventos_iniciais = ["pedido_emitido", "pedido_exame_emitido"],
    )
    stats["pedidos_exame"] = {
        "total": _count(conn, "pedidos_exame"),
        "eventos": _count(conn, "pedido_exame_eventos"),
        "inconsistencias": len(inc),
    }
    all_inc += inc

    # ── Domínio 3: Laudos ───────────────────────────────────────────────────
    inc = _auditar_dominio(
        conn,
        dominio          = "laudos",
        tabela_principal = "laudos",
        tabela_eventos   = "laudo_eventos",
        fk_col           = "laudo_id",
        tipo_col         = "tipo_evento",
        eventos_iniciais = ["laudo_criado", "laudo_emitido"],
    )
    stats["laudos"] = {
        "total": _count(conn, "laudos"),
        "eventos": _count(conn, "laudo_eventos"),
        "inconsistencias": len(inc),
    }
    all_inc += inc

    # ── Domínio 4: Agendamentos ─────────────────────────────────────────────
    inc = _auditar_dominio(
        conn,
        dominio          = "agendamentos",
        tabela_principal = "agendamentos",
        tabela_eventos   = "agendamento_eventos",
        fk_col           = "agendamento_id",
        tipo_col         = "evento",
        eventos_iniciais = ["agendamento_criado"],
    )
    stats["agendamentos"] = {
        "total": _count(conn, "agendamentos"),
        "eventos": _count(conn, "agendamento_eventos"),
        "inconsistencias": len(inc),
    }
    all_inc += inc

    # ── Domínio 5: Circulações Diagnósticas ─────────────────────────────────
    inc = _auditar_dominio(
        conn,
        dominio          = "circulacoes_diagnosticas",
        tabela_principal = "circulacoes_diagnosticas",
        tabela_eventos   = "circulacao_diagnostica_eventos",
        fk_col           = "circulacao_id",
        tipo_col         = "tipo_evento",
        eventos_iniciais = ["circulacao_criada"],
    )
    stats["circulacoes_diagnosticas"] = {
        "total": _count(conn, "circulacoes_diagnosticas"),
        "eventos": _count(conn, "circulacao_diagnostica_eventos"),
        "inconsistencias": len(inc),
    }
    all_inc += inc

    conn.close()
    return all_inc, stats


# ---------------------------------------------------------------------------
# Formatação do relatório
# ---------------------------------------------------------------------------

def _formatar_relatorio(
    db_path: str,
    inconsistencias: list[Inconsistencia],
    stats: dict,
    timestamp: str,
) -> str:
    lines = []
    w = lines.append

    w(f"# Relatório de Auditoria de Integridade do Ledger — PicSaúde")
    w(f"")
    w(f"**Gerado em:** {timestamp}")
    w(f"**Banco auditado:** `{db_path}`")
    w(f"**Script:** `backend/auditar_integridade_ledger.py`")
    w(f"")
    w(f"> ⚠️  Dados pessoais mascarados (LGPD). CPFs no formato `***.XXX.XXX-**`.")
    w(f"> Nomes de pacientes não constam neste relatório.")
    w(f"> Este relatório é somente leitura — nenhum dado foi alterado.")
    w(f"")

    # ── Resumo por domínio ──────────────────────────────────────────────────
    w(f"## Resumo por Domínio")
    w(f"")
    w(f"| Domínio | Registros | Eventos | Inconsistências |")
    w(f"|---|---|---|---|")
    total_inc = 0
    for dominio, s in stats.items():
        w(f"| {dominio} | {s['total']} | {s['eventos']} | {s['inconsistencias']} |")
        total_inc += s["inconsistencias"]
    w(f"")
    w(f"**Total de inconsistências encontradas: {total_inc}**")
    w(f"")

    # ── Detalhamento por gravidade ──────────────────────────────────────────
    por_gravidade = {ALTA: [], MEDIA: [], BAIXA: []}
    for inc in inconsistencias:
        por_gravidade[inc.gravidade].append(inc)

    for grav in (ALTA, MEDIA, BAIXA):
        grupo = por_gravidade[grav]
        if not grupo:
            continue
        w(f"## Inconsistências — Gravidade {grav} ({len(grupo)} ocorrência(s))")
        w(f"")
        for inc in grupo:
            w(f"- **[{inc.dominio}]** `{inc.tipo}`  ")
            w(f"  - `id={inc.objeto_id}`")
            w(f"  - {inc.descricao}")
            if inc.dado_extra:
                w(f"  - `{inc.dado_extra}`")
        w(f"")

    # ── Detalhe por domínio ─────────────────────────────────────────────────
    w(f"## Detalhamento por Domínio")
    w(f"")
    dominios_vistos = {}
    for inc in inconsistencias:
        dominios_vistos.setdefault(inc.dominio, []).append(inc)

    for dominio, grupo in dominios_vistos.items():
        w(f"### {dominio} ({len(grupo)} inconsistência(s))")
        w(f"")
        for inc in grupo:
            w(f"| Campo | Valor |")
            w(f"|---|---|")
            w(f"| ID | `{inc.objeto_id}` |")
            w(f"| Tipo | `{inc.tipo}` |")
            w(f"| Gravidade | **{inc.gravidade}** |")
            w(f"| Descrição | {inc.descricao} |")
            if inc.dado_extra:
                w(f"| Extra | `{inc.dado_extra}` |")
            w(f"")

    # ── Domínios sem inconsistências ────────────────────────────────────────
    limpos = [d for d, s in stats.items() if s["inconsistencias"] == 0]
    if limpos:
        w(f"## Domínios Sem Inconsistências")
        w(f"")
        for d in limpos:
            w(f"- ✓ `{d}` — {stats[d]['total']} registro(s), {stats[d]['eventos']} evento(s)")
        w(f"")

    # ── Recomendações para Ticket 4 ─────────────────────────────────────────
    w(f"## Recomendações para o Ticket 4 (Reconciliação)")
    w(f"")
    if por_gravidade[ALTA]:
        w(f"### Casos de Gravidade Alta — Ação prioritária")
        w(f"")
        for inc in por_gravidade[ALTA]:
            if inc.tipo == "objeto_sem_evento":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Avaliar se o objeto deve receber "
                  f"evento retroativo de criação, ou se é resquício de teste a ser arquivado. "
                  f"Não deletar sem aprovação.")
            elif inc.tipo == "evento_orfao":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Evento referencia objeto inexistente. "
                  f"Investigar se o objeto foi deletado indevidamente (viola imutabilidade) "
                  f"ou se é dado corrompido. Nunca deletar o evento — ledger é imutável.")
            elif inc.tipo in ("digital_sem_evento_emissao", "com_itens_sem_evento",
                              "ativo_sem_evento_inicial"):
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Objeto ativo sem trilha mínima. "
                  f"Reconciliação exige decisão clínica: criar evento retroativo com "
                  f"`criado_em` preservando data original, ou transicionar para estado terminal.")
            elif inc.tipo == "item_encerrado_fisico_em_prescricao_digital":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Violação de invariante de domínio. "
                  f"Exige revisão manual — não corrigir automaticamente.")
            elif inc.tipo == "dispensacao_sem_evento_ledger":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Dispensação sem evento. "
                  f"Inserir evento retroativo `item_dispensado` com dados da dispensação.")
            else:
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Investigar manualmente.")
        w(f"")

    if por_gravidade[MEDIA]:
        w(f"### Casos de Gravidade Média — Revisar antes de produção")
        w(f"")
        for inc in por_gravidade[MEDIA]:
            if inc.tipo == "multiplos_eventos_iniciais":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Múltiplos eventos de criação. "
                  f"Verificar se são retentativas legítimas ou duplicidade — "
                  f"manter ambos (ledger imutável), mas documentar.")
            elif inc.tipo == "assinatura_sem_evento":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Assinatura registrada sem evento. "
                  f"Inserir evento retroativo `assinatura_registrada` se a assinatura for válida.")
            elif inc.tipo == "custodia_sem_evento_transferencia":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Custódia sem evento correspondente. "
                  f"Inserir evento retroativo `custodia_transferida` com dados da custódia.")
            elif inc.tipo == "fisica_status_inconsistente":
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Prescrição física com status errado. "
                  f"Atualizar status para `encerrada_localmente` via endpoint oficial.")
            else:
                w(f"- **[{inc.dominio} id={inc.objeto_id}]** Revisar manualmente.")
        w(f"")

    w(f"---")
    w(f"")
    w(f"**AUDITORIA DO LEDGER CONCLUÍDA**")
    w(f"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PicSaúde — Auditoria de Integridade do Ledger")
    parser.add_argument("--db",  default=_DEFAULT_DB, help="Caminho para o banco SQLite")
    parser.add_argument("--out", default=str(_REPORTS_DIR), help="Diretório de saída do relatório")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"ERRO: banco não encontrado: {db_path}", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*60}")
    print(f"  PicSaúde — Auditoria de Integridade do Ledger")
    print(f"  Banco : {db_path}")
    print(f"  Início: {ts}")
    print(f"{'='*60}\n")

    inconsistencias, stats = _auditar_db(db_path)

    # Resumo no terminal
    print("RESUMO POR DOMÍNIO:")
    for dominio, s in stats.items():
        print(f"  {dominio:40s} total={s['total']:4d}  eventos={s['eventos']:4d}  "
              f"inconsistencias={s['inconsistencias']}")

    n_alta  = sum(1 for i in inconsistencias if i.gravidade == ALTA)
    n_media = sum(1 for i in inconsistencias if i.gravidade == MEDIA)
    n_baixa = sum(1 for i in inconsistencias if i.gravidade == BAIXA)
    print(f"\nTOTAL: {len(inconsistencias)} inconsistência(s) — "
          f"ALTA={n_alta}  MÉDIA={n_media}  BAIXA={n_baixa}")

    if inconsistencias:
        print("\nINCONSISTÊNCIAS ENCONTRADAS:")
        for inc in inconsistencias:
            print(f"  {inc}")

    # Gera relatório em arquivo
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_label = Path(db_path).stem
    out_file = out_dir / f"auditoria_ledger_{db_label}_{ts}.md"

    relatorio = _formatar_relatorio(db_path, inconsistencias, stats, ts)
    out_file.write_text(relatorio, encoding="utf-8")

    print(f"\nRelatório gravado em: {out_file}")
    print(f"\n{'='*60}")
    print(f"  AUDITORIA DO LEDGER CONCLUÍDA")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
