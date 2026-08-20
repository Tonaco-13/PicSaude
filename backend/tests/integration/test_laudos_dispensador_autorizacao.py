"""TICKET-C (core) — RBAC do laudo estendido ao dispensador.

O laudo exige Responsável Técnico com CNS, mas quem opera a tela do laboratório
entra como `dispensador` (CNPJ). A decisão: a unidade PRODUZ EM NOME DO RT —
declara `cns_autor`, e o RT continua sendo o `autor_id`. O que autoriza a unidade
não é identidade nominal, é POSSE: o laudo tem que estar vinculado a um pedido
sob sua custódia ATUAL (`pedido_exame_custodia`). Sem coluna nova, sem migração.

Cobertura (critérios de aceite do ticket):
  - Cria laudo de pedido sob custódia; `autor_id` é o RT, nunca o CNPJ; o evento
    `laudo_criado` registra `produzido_por_cnpj`.
  - Assina · libera · encerra · cancela · GET · pdf · qr do laudo próprio.
  - Laudo de OUTRA unidade → 403 em todas as superfícies.
  - Sem `pedido_protocolo` → 422; laudo standalone → 403 com código nomeado.
  - `liberar` grava na custódia o CNPJ da SESSÃO, ignorando o do payload.
  - Custódia ATUAL, não histórica: perder a posse do pedido é perder o laudo.
  - `ciencia-paciente`/`ciencia-prescritor` seguem fechados ao dispensador.

O nome do arquivo termina em `_autorizacao` de propósito: é o que faz a suíte
casar com o `-k` do gate (gates.yml). Suíte de RBAC não-gateada apodrece.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

import json
from datetime import datetime

from app.auth.jwt import criar_access_token

# ---------------------------------------------------------------------------
# Identidades
# ---------------------------------------------------------------------------
_CNS_RT        = "111111111111111"   # responsável técnico (autor do laudo)
_CNS_SOLIC     = "222222222222222"   # prescritor solicitante (emite o pedido)
_CPF_PAC       = "44455566677"
_CNPJ_A        = "12345678000195"    # unidade que detém o pedido
_CNPJ_B        = "98765432000110"    # outra unidade

_SUPERFICIES_LEITURA = ("", "/pdf", "/qr")


def _headers(token): return {"Authorization": f"Bearer {token}"}
def _tok(sub, role, nome="ATOR"): return criar_access_token(sub=sub, role=role, nome=nome)


# ---------------------------------------------------------------------------
# Helpers de fluxo — custódia SEMPRE criada pelos endpoints reais
# ---------------------------------------------------------------------------

def _criar_pedido(client, prescritor_cns=_CNS_SOLIC, paciente_cpf=_CPF_PAC) -> str:
    payload = {
        "cns_prescritor": prescritor_cns, "nome_prescritor": "DR SOLIC",
        "cpf_paciente": paciente_cpf, "nome_paciente": "PACIENTE",
        "tipo_emissao": "novo", "prioridade": "rotina",
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }
    r = client.post("/pedidos-exame", json=payload,
                    headers=_headers(_tok(prescritor_cns, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _pedido_sob_custodia(client, cnpj: str, paciente_cpf=_CPF_PAC) -> str:
    """Pedido agendado no prestador — é isso que dá posse à unidade."""
    proto = _criar_pedido(client, paciente_cpf=paciente_cpf)
    r = client.post(f"/pedidos-exame/{proto}/agendar",
                    json={"cnpj_prestador": cnpj},
                    headers=_headers(_tok(_CNS_SOLIC, "prescritor")))
    assert r.status_code == 201, r.text
    return proto


def _laudo_da_unidade(client, cnpj: str, paciente_cpf=_CPF_PAC, **over) -> str:
    """Laudo produzido pela unidade `cnpj`, em nome do RT."""
    ped = _pedido_sob_custodia(client, cnpj, paciente_cpf=paciente_cpf)
    payload = {
        "cns_autor": _CNS_RT, "nome_autor": "DRA RESPONSAVEL TECNICA",
        "cpf_paciente": paciente_cpf, "nome_paciente": "PACIENTE",
        "pedido_protocolo": ped,
        "itens": [{"nome_exame": "HEMOGRAMA", "conclusao": "normal",
                   "resultado_resumo": "Series normais", "valor_referencia": "4.5-11.0"}],
        **over,
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(cnpj, "dispensador")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _laudo_standalone(client) -> str:
    """Laudo do RT sem pedido vinculado — o caso que o dispensador não alcança."""
    payload = {
        "cns_autor": _CNS_RT, "nome_autor": "DRA RESPONSAVEL TECNICA",
        "cpf_paciente": _CPF_PAC, "nome_paciente": "PACIENTE",
        "itens": [{"nome_exame": "HEMOGRAMA"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNS_RT, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _cns_do_autor(outer_conn, proto: str) -> str:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT pr.cns FROM laudos l JOIN prescritores pr ON pr.id = l.autor_id "
            "WHERE l.protocolo = %s", (proto,),
        )
        return cur.fetchone()[0]


def _payload_evento(outer_conn, proto: str, tipo: str) -> dict:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.dados_json FROM laudo_eventos e JOIN laudos l ON l.id = e.laudo_id "
            "WHERE l.protocolo = %s AND e.tipo_evento = %s ORDER BY e.id", (proto, tipo),
        )
        bruto = cur.fetchone()[0]
    return json.loads(bruto) if isinstance(bruto, str) else bruto


def _custodia(outer_conn, proto: str) -> list[tuple]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT c.de, c.para FROM laudo_custodia c JOIN laudos l ON l.id = c.laudo_id "
            "WHERE l.protocolo = %s ORDER BY c.id", (proto,),
        )
        return cur.fetchall()


def _pedido_id_do_laudo(outer_conn, proto: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT pedido_id FROM laudos WHERE protocolo = %s", (proto,))
        return cur.fetchone()[0]


# ===========================================================================
# Criação — o RT é o autor; a unidade é quem operou
# ===========================================================================

def test_disp_cria_laudo_autor_e_o_rt_e_evento_registra_a_unidade(client, outer_conn):
    """AC — `autor_id` é sempre o RT declarado, NUNCA o CNPJ. Quem operou fica
    no ledger: sem isso, laudo produzido pela unidade seria indistinguível de um
    digitado pelo próprio responsável técnico."""
    proto = _laudo_da_unidade(client, _CNPJ_A)

    assert _cns_do_autor(outer_conn, proto) == _CNS_RT
    assert _pedido_id_do_laudo(outer_conn, proto) is not None

    ev = _payload_evento(outer_conn, proto, "laudo_criado")
    assert ev["produzido_por"] == "dispensador"
    assert ev["produzido_por_cnpj"] == _CNPJ_A


def test_prescritor_cria_laudo_evento_nao_atribui_cnpj(client, outer_conn):
    """Caminho do prescritor preservado — e o novo campo não inventa unidade."""
    proto = _laudo_standalone(client)
    ev = _payload_evento(outer_conn, proto, "laudo_criado")
    assert ev["produzido_por"] == "prescritor"
    assert ev["produzido_por_cnpj"] is None


def test_disp_cria_laudo_sem_pedido_protocolo_422(client):
    """AC — sem vínculo não há posse de onde derivar direito: 422, não laudo órfão."""
    payload = {
        "cns_autor": _CNS_RT, "nome_autor": "DRA RT", "cpf_paciente": _CPF_PAC,
        "nome_paciente": "PACIENTE", "itens": [{"nome_exame": "HEMOGRAMA"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNPJ_A, "dispensador")))
    assert r.status_code == 422, r.text
    assert "pedido_protocolo" in r.text


def test_disp_cria_laudo_com_pedido_de_outra_unidade_403(client):
    """AC — a unidade B não produz laudo sobre pedido que está com a unidade A."""
    ped = _pedido_sob_custodia(client, _CNPJ_A)
    payload = {
        "cns_autor": _CNS_RT, "nome_autor": "DRA RT", "cpf_paciente": _CPF_PAC,
        "nome_paciente": "PACIENTE", "pedido_protocolo": ped,
        "itens": [{"nome_exame": "HEMOGRAMA"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


def test_disp_cria_laudo_posse_precede_vinculo_clinico(client):
    """Ordem anti-leak (#52): a unidade alheia recebe o 403 de POSSE, não o
    `vinculo_pedido_invalido` — que revelaria de quem é o pedido."""
    ped = _pedido_sob_custodia(client, _CNPJ_A, paciente_cpf=_CPF_PAC)
    payload = {
        "cns_autor": _CNS_RT, "nome_autor": "DRA RT",
        "cpf_paciente": "99988877766",           # paciente DIVERGENTE do pedido
        "nome_paciente": "OUTRO", "pedido_protocolo": ped,
        "itens": [{"nome_exame": "HEMOGRAMA"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"


# ===========================================================================
# Ciclo completo da unidade — produzir, assinar, liberar, encerrar
# ===========================================================================

def test_disp_ciclo_completo_do_laudo_proprio(client, outer_conn):
    """AC — a unidade percorre o ciclo inteiro do laudo que produziu."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h = _headers(_tok(_CNPJ_A, "dispensador"))

    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200
    assert client.post(f"/laudos/{proto}/liberar", json={}, headers=h).status_code == 200

    # O laudo chegou ao cidadão: custódia prestador → paciente.
    assert _custodia(outer_conn, proto) == [(_CNPJ_A, "paciente")]

    assert client.post(f"/laudos/{proto}/encerrar", headers=h).status_code == 200


def test_disp_liberar_grava_cnpj_da_sessao_e_ignora_o_payload(client, outer_conn):
    """AC — a custódia registra posse PROVADA (JWT), não posse DECLARADA (corpo).

    Se o payload mandasse, uma unidade poderia assinar a cadeia de custódia com o
    CNPJ de outra — e a cadeia (§3) deixaria de valer como prova.
    """
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200

    r = client.post(f"/laudos/{proto}/liberar",
                    json={"cnpj_prestador": _CNPJ_B},   # forjado
                    headers=h)
    assert r.status_code == 200, r.text

    assert _custodia(outer_conn, proto) == [(_CNPJ_A, "paciente")]
    assert _payload_evento(outer_conn, proto, "laudo_liberado")["cnpj_prestador"] == _CNPJ_A


def test_disp_cancela_laudo_proprio(client):
    proto = _laudo_da_unidade(client, _CNPJ_A)
    r = client.post(f"/laudos/{proto}/cancelar", json={"motivo": "erro de digitação"},
                    headers=_headers(_tok(_CNPJ_A, "dispensador")))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelado"


def test_disp_le_get_pdf_qr_do_laudo_proprio(client):
    """AC — a unidade pré-visualiza o que produziu e acompanha a ciência."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h = _headers(_tok(_CNPJ_A, "dispensador"))
    for sufixo in _SUPERFICIES_LEITURA:
        r = client.get(f"/laudos/{proto}{sufixo}", headers=h)
        assert r.status_code == 200, (sufixo, r.text)


# ===========================================================================
# Ownership — o coração do ticket
# ===========================================================================

def test_disp_de_outra_unidade_403_em_todas_as_superficies(client):
    """AC — unidade A não opera laudo da unidade B, em nenhum endpoint."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h_b = _headers(_tok(_CNPJ_B, "dispensador"))

    for sufixo in _SUPERFICIES_LEITURA:
        r = client.get(f"/laudos/{proto}{sufixo}", headers=h_b)
        assert r.status_code == 403, (sufixo, r.text)
        assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"

    for rota, corpo in (("assinar", None), ("liberar", {}),
                        ("encerrar", None), ("cancelar", {"motivo": "x"})):
        kwargs = {"headers": h_b}
        if corpo is not None:
            kwargs["json"] = corpo
        r = client.post(f"/laudos/{proto}/{rota}", **kwargs)
        assert r.status_code == 403, (rota, r.text)
        assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


def test_disp_laudo_standalone_403_com_codigo_nomeado(client):
    """AC — laudo sem pedido vinculado não tem custódia de onde derivar posse.

    Negar é a resposta correta, não efeito colateral — por isso o código é
    próprio (`laudo_sem_pedido_vinculado`), e não o genérico de ownership.
    """
    proto = _laudo_standalone(client)
    h = _headers(_tok(_CNPJ_A, "dispensador"))

    r = client.get(f"/laudos/{proto}", headers=h)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "laudo_sem_pedido_vinculado"

    r2 = client.post(f"/laudos/{proto}/assinar", headers=h)
    assert r2.status_code == 403, r2.text
    assert r2.json()["detail"]["codigo"] == "laudo_sem_pedido_vinculado"


def test_disp_custodia_atual_nao_historica(client, outer_conn):
    """Perder a posse do pedido é perder o laudo.

    Quem já foi custodiante não continua operando. O MVP não reexpõe
    re-transferência entre prestadores, então a linha mais recente entra por
    INSERT direto — mesmo recurso de `test_pedidos_exame_autorizacao.py`.

    J.10-CORE: a simulação passou a FECHAR a posse anterior antes de abrir a
    nova. Não é concessão à constraint — é a simulação virando fiel: o
    choke-point faz exatamente isso, e um INSERT solto agora seria dupla posse
    ativa, que o banco recusa (e com razão).
    """
    proto = _laudo_da_unidade(client, _CNPJ_A)
    pedido_id = _pedido_id_do_laudo(outer_conn, proto)

    assert client.get(f"/laudos/{proto}",
                      headers=_headers(_tok(_CNPJ_A, "dispensador"))).status_code == 200

    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE pedido_exame_custodia SET encerrada_em = %s "
            "WHERE pedido_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (datetime.utcnow(), pedido_id),
        )
        cur.execute(
            """
            INSERT INTO pedido_exame_custodia
              (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
            VALUES (%s, NULL, 'paciente', %s, %s, NULL, %s)
            """,
            (pedido_id, _CNPJ_B, datetime.utcnow(),
             '{"motivo": "re-transferencia historica (teste)"}'),
        )

    # B (custódia atual) enxerga; A (histórica) não.
    assert client.get(f"/laudos/{proto}",
                      headers=_headers(_tok(_CNPJ_B, "dispensador"))).status_code == 200
    r = client.get(f"/laudos/{proto}", headers=_headers(_tok(_CNPJ_A, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


def test_disp_antileak_403_precede_422_de_estado(client):
    """Unidade alheia não descobre o estado do laudo pelo código de status."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    assert client.post(f"/laudos/{proto}/assinar",
                       headers=_headers(_tok(_CNPJ_A, "dispensador"))).status_code == 200

    # já assinado: para o dono seria 422; para a unidade alheia é 403.
    r = client.post(f"/laudos/{proto}/assinar", headers=_headers(_tok(_CNPJ_B, "dispensador")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


# ===========================================================================
# Fronteiras que o ticket manda NÃO cruzar
# ===========================================================================

def test_disp_nao_da_ciencia_nem_clinica_nem_do_paciente(client):
    """AC — ciência é ato de quem RECEBE o laudo. Quem produziu não dá ciência
    por ninguém: os dois endpoints seguem fechados ao dispensador (portão de
    papel, `detail` string — nem chega no ownership)."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200
    assert client.post(f"/laudos/{proto}/liberar", json={}, headers=h).status_code == 200

    for rota in ("ciencia-paciente", "ciencia-prescritor"):
        r = client.post(f"/laudos/{proto}/{rota}", headers=h)
        assert r.status_code == 403, (rota, r.text)


def test_ciencia_do_cidadao_segue_funcionando_apos_o_enxerto(client):
    """O caminho que a demo depende: o laudo produzido pela unidade chega ao
    cidadão e é ELE quem dá ciência."""
    proto = _laudo_da_unidade(client, _CNPJ_A)
    h = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200
    assert client.post(f"/laudos/{proto}/liberar", json={}, headers=h).status_code == 200

    r = client.post(f"/laudos/{proto}/ciencia-paciente",
                    headers=_headers(_tok(_CPF_PAC, "paciente")))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ciencia_paciente"


def test_prescritor_liberar_sem_cnpj_prestador_422_nomeado(client):
    """`cnpj_prestador` virou opcional no schema (o dispensador não o declara),
    então a obrigatoriedade para o prescritor passou a ser guarda explícita —
    não pode ter virado custódia com `de` nulo."""
    proto = _laudo_standalone(client)
    h = _headers(_tok(_CNS_RT, "prescritor"))
    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200

    r = client.post(f"/laudos/{proto}/liberar", json={}, headers=h)
    assert r.status_code == 422, r.text
    assert "cnpj_prestador" in r.text
