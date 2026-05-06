from __future__ import annotations

import os
import re
import sqlite3
import random
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DB_PATH = os.environ.get("PIX_SAUDE_DB", "./pix_saude_pe.db")

CBO_PREFIXES: Tuple[str, ...] = ("2251", "2252", "2232")

DEFAULT_LIMIT = 20
MAX_LIMIT = 50

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="PIX da Saúde", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# DB
# -----------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise RuntimeError(f"SQLite DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def normalize_nome(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).upper()

def normalize_cpf(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def normalize_cns(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def cbo_where_clause() -> str:
    parts = [f"r.CO_CBO LIKE '{p}%'" for p in CBO_PREFIXES]
    return "(" + " OR ".join(parts) + ")"

def vinculo_ativo_where_clause() -> str:
    return "(r.DT_DESLIGAMENTO IS NULL OR TRIM(r.DT_DESLIGAMENTO) = '')"

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

# -----------------------------------------------------------------------------
# PRESCRITORES
# -----------------------------------------------------------------------------
@app.get("/busca")
def busca(
    nome: str = Query(..., min_length=3),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    q = normalize_nome(nome)

    sql = f"""
    SELECT
      CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) AS cns,
      p.NO_PROFISSIONAL AS nome,
      COUNT(*) AS qtd_vinculos_ativos
    FROM relacao_prof_estab r
    JOIN profissionais p
      ON p.CO_PROFISSIONAL_SUS = r.CO_PROFISSIONAL_SUS
    WHERE
      {vinculo_ativo_where_clause()}
      AND {cbo_where_clause()}
      AND UPPER(p.NO_PROFISSIONAL) LIKE '%' || ? || '%'
    GROUP BY cns, nome
    ORDER BY nome
    LIMIT ?
    """

    conn = get_conn()
    try:
        rows = conn.execute(sql, (q, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/profissional/{cns}")
def profissional(cns: str):
    cns_n = normalize_cns(cns)

    sql = f"""
    SELECT
      CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) AS cns,
      p.NO_PROFISSIONAL AS nome,
      r.CO_CBO AS cbo,
      e.CO_CNES AS cnes,
      e.NO_FANTASIA AS estabelecimento,
      e.CO_MUNICIPIO_GESTOR AS municipio_ibge
    FROM relacao_prof_estab r
    JOIN profissionais p
      ON p.CO_PROFISSIONAL_SUS = r.CO_PROFISSIONAL_SUS
    JOIN estabelecimentos e
      ON e.CO_UNIDADE = r.CO_UNIDADE
    WHERE
      {vinculo_ativo_where_clause()}
      AND {cbo_where_clause()}
      AND CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) = ?
    ORDER BY e.NO_FANTASIA
    """

    conn = get_conn()
    try:
        rows = conn.execute(sql, (cns_n,)).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Profissional não encontrado")

        first = rows[0]

        return {
            "cns": first["cns"],
            "nome": first["nome"],
            "vinculos_ativos": [
                {
                    "cnes": r["cnes"],
                    "estabelecimento": r["estabelecimento"],
                    "cbo": r["cbo"],
                    "municipio_ibge": r["municipio_ibge"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# PACIENTES
# -----------------------------------------------------------------------------
@app.get("/pacientes")
def listar_pacientes():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT cpf, nome, telefone, ativo FROM pacientes"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# AUTENTICAÇÃO OTP
# -----------------------------------------------------------------------------
@app.post("/paciente/enviar-codigo")
def enviar_codigo(dados: dict):
    cpf = normalize_cpf(dados.get("cpf"))
    telefone = dados.get("telefone")

    if not cpf or not telefone:
        raise HTTPException(status_code=400, detail="CPF e telefone obrigatórios")

    codigo = str(random.randint(100000, 999999))

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO pacientes (cpf, nome, telefone, created_at, ativo)
            VALUES (?, 'PACIENTE', ?, datetime('now'), 0)
            """,
            (cpf, telefone),
        )

        conn.execute(
            """
            INSERT INTO codigos_login (cpf, codigo, expiracao, usado)
            VALUES (?, ?, datetime('now', '+5 minutes'), 0)
            """,
            (cpf, codigo),
        )

        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "codigo_teste": codigo}

@app.post("/paciente/validar-codigo")
def validar_codigo(dados: dict):
    cpf = normalize_cpf(dados.get("cpf"))
    codigo = dados.get("codigo")

    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id FROM codigos_login
            WHERE cpf = ?
              AND codigo = ?
              AND usado = 0
              AND expiracao >= datetime('now')
            ORDER BY id DESC
            LIMIT 1
            """,
            (cpf, codigo),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=400, detail="Código inválido ou expirado")

        conn.execute(
            "UPDATE codigos_login SET usado = 1 WHERE id = ?",
            (row["id"],),
        )

        conn.execute(
            "UPDATE pacientes SET ativo = 1 WHERE cpf = ?",
            (cpf,),
        )

        conn.commit()
    finally:
        conn.close()

    return {"ok": True}
