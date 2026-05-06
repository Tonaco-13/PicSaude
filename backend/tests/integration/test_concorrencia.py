"""Ticket 13 — concorrência básica: 10 prescrições em paralelo sobre o pool real.

Este teste NÃO usa o isolamento por SAVEPOINT (a raw conn compartilhada não
é thread-safe). Usa a fixture `client_concorrencia`, que faz commits reais
sobre o pool do app e limpa dados no teardown por CPF sentinela.

Critérios de aprovação:
  * 0 respostas com status >= 500
  * ≥ 80 % de 201 (emissão aceita)
"""
from __future__ import annotations

import concurrent.futures
import uuid
from datetime import datetime

import psycopg2
import pytest

from tests.integration.conftest import (
    DATABASE_URL_TEST,
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    SEED_PRESCRITOR_SENHA,
)
from app.auth.jwt import hash_senha


_PAYLOAD = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "nova",
    "itens": [{
        "nome_medicamento": "IBUPROFENO",
        "concentracao":     "400mg",
        "quantidade":       6,
        "posologia":        "1 cp 2x/dia",
    }],
}


@pytest.fixture
def seed_real(client_concorrencia):
    """Cria o prescritor/usuário no banco real (committed).
    O `client_concorrencia` remove no teardown.
    """
    now = datetime.utcnow().isoformat()
    senha_hash = hash_senha(SEED_PRESCRITOR_SENHA)
    conn = psycopg2.connect(DATABASE_URL_TEST)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
                VALUES (%s, %s, %s, %s, true, %s, %s)
                ON CONFLICT (identificador) DO UPDATE SET senha_hash = EXCLUDED.senha_hash
                """,
                ("prescritor", SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, senha_hash, now, now),
            )
            cur.execute(
                """
                INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
                VALUES (%s, %s, true, %s, %s)
                ON CONFLICT (cns) DO NOTHING
                """,
                (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
            )
    finally:
        conn.close()


def _obter_token(client) -> str:
    r = client.post(
        "/auth/token",
        data={"username": SEED_PRESCRITOR_CNS, "password": SEED_PRESCRITOR_SENHA},
    )
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    return r.json()["access_token"]


def test_concorrencia_10_prescricoes_paralelas(client_concorrencia, seed_real):
    client = client_concorrencia
    token = _obter_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    def _criar():
        payload = dict(_PAYLOAD)
        # Variação leve para evitar eventual dedupe
        payload["nome_paciente"] = f"{SEED_PACIENTE_NOME} {uuid.uuid4().hex[:4]}"
        r = client.post("/prescricoes", json=payload, headers=headers)
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(_criar) for _ in range(10)]
        resultados = [f.result() for f in concurrent.futures.as_completed(futs)]

    erros_500 = [r for r in resultados if r >= 500]
    assert not erros_500, f"Respostas 5xx presentes: {resultados}"

    sucesso = [r for r in resultados if r in (200, 201)]
    assert len(sucesso) >= 8, (
        f"Menos de 80% de sucesso sob 10 requests paralelas: {resultados}"
    )
