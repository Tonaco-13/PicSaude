"""TICKET-J.2 (`core`) — integridade do documento canônico × caixa do nome.

O DEFEITO QUE ESTE ARQUIVO TRAVA
--------------------------------
A emissão hasheia `normalize_nome(payload.nome_paciente)` — MAIÚSCULAS. Mas ela
**não atualiza** `pacientes.nome` quando o paciente já existe: resolve por CPF e
reaproveita a linha. A reconstrução (`montar_documento_de_conn`) lê `pa.nome`
cru do banco. Se a linha foi criada com outra caixa — "João Demo da Silva" —, o
hash recomputado **nunca** bate com o armazenado.

Efeito na vitrine (excursão de 14/08): `GET /documento` → `integro: false` e
`GET /validacao` acusando "conteúdo pode ter sido alterado após emissão" em
receita recém-emitida. É a pior mensagem possível numa demo pública — o sistema
acusando a si mesmo de adulteração.

POR QUE O GATE NÃO VIA
----------------------
O `conftest` de integração semeia `SEED_PACIENTE_NOME = "PACIENTE TESTE TICKET13"`
— **já em maiúsculas**. Nesse dado, `normalize_nome` é no-op e o hash casa por
acidente. O `seed_demo.py` (vitrine) usa "João Demo da Silva", Title Case. O bug
só existia onde o dado tinha caixa mista, e nenhum teste tinha dado assim.

Por isso os casos abaixo criam o paciente com Title Case **de propósito**: é a
forma do dado, não o endpoint, que reproduz o defeito.

Nome do arquivo casa com `integridade` no `-k` do gate (gates.yml) — de propósito.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from tests.integration.conftest import obter_token_prescritor

_CPF_TITLE_CASE = "32165498700"
_NOME_TITLE_CASE = "João Demo da Silva"       # a forma do seed da vitrine
_NOME_ESPACOS = "  Maria   dos   Santos  "    # caixa mista + espaços redundantes
_CPF_ESPACOS = "74185296300"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _semear_paciente(outer_conn, cpf: str, nome: str) -> None:
    """Cria o paciente COMO O SEED DA VITRINE cria — sem normalizar a caixa."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, NOW(), NOW()) ON CONFLICT (cpf) DO NOTHING",
            (cpf, nome),
        )


def _emitir(client, token: str, cpf: str, nome: str) -> str:
    payload = {
        "cns_prescritor":   "987654321098765",
        "nome_prescritor":  "DR. TESTE TICKET13",
        "cpf_paciente":     cpf,
        "nome_paciente":    nome,
        "tipo_emissao":     "nova",
        "assinatura_modo":  "gov_br_nuvem",
        "itens": [{
            "nome_medicamento": "DIPIRONA",
            "concentracao": "500mg",
            "quantidade": 1,
            "unidade_quantidade": "comprimido",
            "posologia": "1 comprimido a cada 6h",
        }],
    }
    r = client.post("/prescricoes", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ---------------------------------------------------------------------------
# AC do J.2
# ---------------------------------------------------------------------------

def test_documento_integro_com_paciente_em_title_case(client, outer_conn, seed_usuario):
    """AC — receita emitida para paciente cujo nome está em Title Case no banco
    devolve `integro: true`. É o caso exato da vitrine."""
    _semear_paciente(outer_conn, _CPF_TITLE_CASE, _NOME_TITLE_CASE)
    token = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token, _CPF_TITLE_CASE, _NOME_TITLE_CASE)

    r = client.get(f"/prescricoes/{proto}/documento", headers=_headers(token))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["integro"] is True, (
        "hash não casou — a reconstrução leu o nome com caixa diferente da que "
        f"foi hasheada na emissão. doc={corpo['documento'].get('paciente')}"
    )
    assert corpo["hash_recomputado"] == corpo["hash_armazenado"]


def test_documento_integro_quando_payload_diverge_da_caixa_do_banco(
    client, outer_conn, seed_usuario
):
    """O prescritor digita em caixa qualquer; o banco guarda outra. O documento
    canônico é o mesmo — a caixa do nome nunca fez parte do que o hash promete."""
    _semear_paciente(outer_conn, _CPF_ESPACOS, _NOME_ESPACOS.strip())
    token = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token, _CPF_ESPACOS, "maria DOS santos")

    corpo = client.get(f"/prescricoes/{proto}/documento", headers=_headers(token)).json()
    assert corpo["integro"] is True, corpo["documento"].get("paciente")


def test_documento_canonico_serializa_o_nome_normalizado(client, outer_conn, seed_usuario):
    """A normalização é do DOCUMENTO, não só da comparação: quem lê o canônico
    tem de ver a mesma forma que foi assinada, senão o documento exibido e o
    documento hasheado seriam dois."""
    _semear_paciente(outer_conn, _CPF_TITLE_CASE, _NOME_TITLE_CASE)
    token = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token, _CPF_TITLE_CASE, _NOME_TITLE_CASE)

    doc = client.get(
        f"/prescricoes/{proto}/documento", headers=_headers(token)
    ).json()["documento"]
    assert doc["paciente"]["nome"] == "JOÃO DEMO DA SILVA", doc["paciente"]
    # Acento preservado: normalize_nome faz upper + colapso de espaços, não
    # remove diacrítico. Perder o acento aqui mudaria o hash de todo o histórico.
    assert "JOAO" not in doc["paciente"]["nome"]


def test_validacao_nao_acusa_adulteracao_falsa(client, outer_conn, seed_usuario):
    """AC — `GET /validacao` sem alerta de adulteração para receita íntegra.

    O endpoint é a superfície que o cidadão/auditor vê; era ali que a demo
    afirmava que o próprio sistema tinha adulterado o documento.
    """
    _semear_paciente(outer_conn, _CPF_TITLE_CASE, _NOME_TITLE_CASE)
    token = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token, _CPF_TITLE_CASE, _NOME_TITLE_CASE)

    r = client.get(f"/prescricoes/{proto}/validacao", headers=_headers(token))
    assert r.status_code == 200, r.text
    texto = r.text.lower()
    for acusacao in ("alterado após emissão", "adulterad"):
        assert acusacao not in texto, f"validação acusou adulteração falsa: {r.text[:400]}"
