"""Ticket 20 — Testes do catálogo regulatório de substâncias.

Cobertura
---------
Unitários (sem banco) — normalização e validação pura:
  1. normalizar_dcb: acentos
  2. normalizar_dcb: combinações com "+"
  3. normalizar_dcb: espaços extras
  4. validar_classificacao: coerente
  5. validar_classificacao: classe divergente → warning
  6. validar_classificacao: tipo_retencao divergente → critical
  7. validar_classificacao: classe ausente em substância controlada → warning
  8. validar_classificacao: tipo_retencao ausente em substância de retenção → critical
  9. validar_classificacao: substância desconhecida não bloqueia
 10. validar_classificacao: tipo_retencao fora do vocabulário → critical

G1 (DESENHO-TALAO-DIGITAL-SNCR.md §1/§1.1) — a inversão gated pelo carimbo:
 11. validar_classificacao: SEM carimbo, ausência é silêncio (AC4)
 12. validar_classificacao: COM carimbo, ausência vira afirmação confiável
 13. validar_classificacao: carimbo não interfere quando substância é encontrada

Integração (com PostgreSQL):
 14. Endpoint /catalogo/substancias autocomplete (semaglutida)
 15. Endpoint /catalogo/substancias autocomplete (amoxicilina)
 16. Endpoint exige autenticação
 17. POST /gerar inclui alertas_regulatorios quando antimicrobiano sem tipo_retencao
 18. POST /gerar não gera alertas quando classificação está coerente
 19. Catálogo não bloqueia emissão (alertas são informativos)
 20. eh_item_atomizavel bloqueia substância controlada do catálogo (com conn)
 21. eh_item_atomizavel sem conn ignora catálogo (compat)
 22. carimbo nasce pendente (migração 2fb9182a0846)
 23. aplicar_carimbo + limpar_carimbo — ciclo completo
 24. aplicar_snapshot_carimbado — upsert versionado + ativa carimbo
 25. aplicar_snapshot_carimbado — idempotente
 26. aplicar_snapshot_carimbado — exige fonte/versão/data_snapshot
"""
from __future__ import annotations

from datetime import datetime

import pytest

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ===========================================================================
# UNITÁRIOS — normalização e validação pura
# ===========================================================================

def test_normalizar_dcb_acentos():
    from app.domain.catalogo_regulatorio import normalizar_dcb
    assert normalizar_dcb("Isotretinoína") == "isotretinoina"
    assert normalizar_dcb("Codeína") == "codeina"
    assert normalizar_dcb("Penicilina V") == "penicilina v"


def test_normalizar_dcb_combinacao_com_mais():
    from app.domain.catalogo_regulatorio import normalizar_dcb
    # Sem espaços
    assert normalizar_dcb("Sulfametoxazol+Trimetoprima") \
        == "sulfametoxazol + trimetoprima"
    # Com espaços simples
    assert normalizar_dcb("Amoxicilina + Clavulanato") \
        == "amoxicilina + clavulanato"
    # Com múltiplos espaços
    assert normalizar_dcb("Amoxicilina  +  Clavulanato") \
        == "amoxicilina + clavulanato"


def test_normalizar_dcb_espacos_extras():
    from app.domain.catalogo_regulatorio import normalizar_dcb
    assert normalizar_dcb("  Diazepam  ") == "diazepam"
    assert normalizar_dcb("Penicilina   Benzatina") == "penicilina benzatina"


def test_validar_classificacao_coerente():
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="amoxicilina", dcb_display="Amoxicilina",
        classe_controle=None, tipo_retencao="antimicrobiano",
        fonte="in_83_2021",
    )
    res = validar_classificacao(sub, None, "antimicrobiano",
                                nome_para_msg="Amoxicilina")
    assert res.substancia_encontrada is True
    assert res.classificacao_coerente is True
    assert res.alertas == []


def test_validar_classificacao_divergente_classe():
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="diazepam", dcb_display="Diazepam",
        classe_controle="B1", tipo_retencao=None,
        fonte="portaria_344",
    )
    res = validar_classificacao(sub, "B2", None,
                                nome_para_msg="Diazepam")
    assert res.classificacao_coerente is False
    assert res.severidade == "warning"
    assert res.sugestao_classe == "B1"
    assert any("B1" in a.mensagem for a in res.alertas)


def test_validar_classificacao_divergente_retencao():
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="semaglutida", dcb_display="Semaglutida",
        classe_controle=None, tipo_retencao="glp1_agonista",
        fonte="in_360_2025",
    )
    # Declara como antimicrobiano em vez de glp1_agonista
    res = validar_classificacao(sub, None, "antimicrobiano",
                                nome_para_msg="Semaglutida")
    assert res.classificacao_coerente is False
    assert res.severidade == "critical"
    assert res.sugestao_tipo_retencao == "glp1_agonista"


def test_validar_classificacao_ausente_controlada():
    """Substância da Portaria 344 sem classe_controle declarado → warning."""
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="diazepam", dcb_display="Diazepam",
        classe_controle="B1", tipo_retencao=None,
        fonte="portaria_344",
    )
    res = validar_classificacao(sub, None, None, nome_para_msg="Diazepam")
    assert res.classificacao_coerente is False
    assert res.severidade == "warning"
    assert res.sugestao_classe == "B1"


def test_validar_classificacao_ausente_retencao():
    """Substância de retenção sem tipo_retencao declarado → critical
    (risco: emissão como receita simples)."""
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="amoxicilina", dcb_display="Amoxicilina",
        classe_controle=None, tipo_retencao="antimicrobiano",
        fonte="in_83_2021",
    )
    res = validar_classificacao(sub, None, None, nome_para_msg="Amoxicilina")
    assert res.classificacao_coerente is False
    assert res.severidade == "critical"
    assert res.sugestao_tipo_retencao == "antimicrobiano"
    assert any("receita simples" in a.mensagem.lower() for a in res.alertas)


def test_validar_substancia_desconhecida_nao_bloqueia():
    """Substância ausente do catálogo → coerente=True, sem alertas.
    Catálogo parcial não pode gerar falsos positivos."""
    from app.domain.catalogo_regulatorio import validar_classificacao
    res = validar_classificacao(None, None, None, nome_para_msg="Substancia X")
    assert res.substancia_encontrada is False
    assert res.classificacao_coerente is True
    assert res.alertas == []


# ---------------------------------------------------------------------------
# G1 — a inversão semântica gated pelo carimbo (DESENHO-TALAO-DIGITAL-SNCR.md
# §1/§1.1). AC4: base SEM carimbo não afirma não-controlado — os dois testes
# abaixo testam as duas pontas do gate; juntos são a prova vermelho-antes-de-
# verde (se o gate quebrar pra qualquer lado, um dos dois cai).
# ---------------------------------------------------------------------------

def test_validar_classificacao_sem_carimbo_ausencia_e_silencio():
    """AC4 — o padrão de sempre: sem carimbo (parâmetro omitido OU None
    explícito), ausência não afirma nada. `catalogo_regulatorio_carimbo`
    nasce assim pela migração 2fb9182a0846 — este teste prova que o
    COMPORTAMENTO, não só o dado, começa cauteloso."""
    from app.domain.catalogo_regulatorio import validar_classificacao
    res = validar_classificacao(None, None, None, nome_para_msg="Substancia X")
    assert res.classificacao_coerente is True
    assert res.afirmacao_nao_controlado is None

    res_explicito = validar_classificacao(
        None, None, None, nome_para_msg="Substancia X", carimbo=None,
    )
    assert res_explicito.afirmacao_nao_controlado is None


def test_validar_classificacao_com_carimbo_ausencia_vira_afirmacao_confiavel():
    """A inversão semântica do §1 — SÓ quando `carimbo` é passado
    explicitamente. A afirmação cita fonte/versão/data: é rastreável, não
    um "não-controlado" genérico."""
    from app.domain.catalogo_regulatorio import (
        CarimboRegulatorio, validar_classificacao,
    )
    carimbo = CarimboRegulatorio(
        fonte="Portaria 344/98 Anexo I (teste)",
        versao="RDC 999/2099",
        data_snapshot="2099-01-01",
    )
    res = validar_classificacao(
        None, None, None, nome_para_msg="Substancia X", carimbo=carimbo,
    )
    assert res.substancia_encontrada is False
    assert res.classificacao_coerente is True
    assert res.afirmacao_nao_controlado is not None
    assert "RDC 999/2099" in res.afirmacao_nao_controlado
    assert "2099-01-01" in res.afirmacao_nao_controlado
    assert res.alertas == []  # afirmação não é divergência


def test_validar_classificacao_substancia_encontrada_carimbo_nao_interfere():
    """O carimbo só afeta o caminho de AUSÊNCIA. Substância encontrada segue
    o fluxo de divergência de sempre — a inversão não vaza para o caso que
    já tinha resposta."""
    from app.domain.catalogo_regulatorio import (
        CarimboRegulatorio, SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="amoxicilina", dcb_display="Amoxicilina",
        classe_controle=None, tipo_retencao="antimicrobiano",
        fonte="in_83_2021",
    )
    carimbo = CarimboRegulatorio(fonte="x", versao="y", data_snapshot="2099-01-01")
    res = validar_classificacao(
        sub, None, "antimicrobiano", nome_para_msg="Amoxicilina", carimbo=carimbo,
    )
    assert res.classificacao_coerente is True
    assert res.afirmacao_nao_controlado is None


def test_validar_tipo_retencao_fora_vocabulario():
    """tipo_retencao declarado mas fora de TIPOS_RETENCAO_VALIDOS → critical."""
    from app.domain.catalogo_regulatorio import (
        SubstanciaCatalogo, validar_classificacao,
    )
    sub = SubstanciaCatalogo(
        dcb="amoxicilina", dcb_display="Amoxicilina",
        classe_controle=None, tipo_retencao="antimicrobiano",
        fonte="in_83_2021",
    )
    res = validar_classificacao(sub, None, "valor_invalido",
                                nome_para_msg="Amoxicilina")
    assert res.classificacao_coerente is False
    assert res.severidade == "critical"
    # Pelo menos um alerta sobre vocabulário
    assert any("vocabul" in a.mensagem.lower() for a in res.alertas)


# ===========================================================================
# INTEGRAÇÃO — endpoint /catalogo/substancias
# ===========================================================================

def test_endpoint_catalogo_autocomplete_semaglutida(client, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.get(
        "/catalogo/substancias?q=sema",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    nomes = [item["dcb_display"] for item in body["resultados"]]
    assert "Semaglutida" in nomes
    # Verificar payload completo
    sema = next(item for item in body["resultados"] if item["dcb"] == "semaglutida")
    assert sema["tipo_retencao"] == "glp1_agonista"
    assert sema["classe_controle"] is None
    assert sema["fonte"] == "in_360_2025"


def test_endpoint_catalogo_autocomplete_amoxicilina(client, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.get(
        "/catalogo/substancias?q=amoxi&limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    nomes = [item["dcb_display"] for item in body["resultados"]]
    # Tanto Amoxicilina quanto Amoxicilina + Clavulanato devem aparecer
    assert "Amoxicilina" in nomes
    assert "Amoxicilina + Clavulanato" in nomes


def test_endpoint_catalogo_exige_autenticacao(client):
    r = client.get("/catalogo/substancias?q=sema")
    assert r.status_code in (401, 403)


def test_endpoint_catalogo_q_vazio(client, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    # FastAPI valida via Query(min_length=1) — q vazio retorna 422
    r = client.get(
        "/catalogo/substancias?q=",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_endpoint_catalogo_inativo_nao_aparece(client, seed_usuario):
    """Exenatida foi inserida com ativo=False — não deve aparecer."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.get(
        "/catalogo/substancias?q=exena",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    nomes = [item["dcb"] for item in r.json()["resultados"]]
    assert "exenatida" not in nomes


# ===========================================================================
# INTEGRAÇÃO — alertas no POST /gerar
# ===========================================================================

def _inserir_prescritor_e_paciente(outer_conn) -> tuple[int, int]:
    now = datetime.utcnow().isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        prescritor_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        paciente_id = cur.fetchone()[0]
    return prescritor_id, paciente_id


def _inserir_prescricao(
    outer_conn,
    *,
    assinatura_modo: str | None,
    itens_data: list[dict],
    protocolo: str,
) -> int:
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    now = datetime.utcnow()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', %s, 'nova', %s, %s, %s)
            RETURNING id
            """,
            (protocolo, prescritor_id, paciente_id, assinatura_modo, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        for idx, dados in enumerate(itens_data, start=1):
            cur.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   posologia, status_item, classe_controle, tipo_retencao,
                   created_at, updated_at)
                VALUES (%s, %s, '500mg', 30, '1 cp 8/8h', 'pendente',
                        %s, %s, %s, %s)
                """,
                (
                    prescricao_id,
                    dados["nome"],
                    dados.get("classe_controle"),
                    dados.get("tipo_retencao"),
                    now, now,
                ),
            )
    return prescricao_id


def test_gerar_inclui_alerta_critical_quando_antimicrobiano_sem_classificacao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Amoxicilina declarada SEM tipo_retencao — catálogo deve gerar
    alerta critical (risco: emissão como receita simples)."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "AMOXICILINA"}],  # sem classe nem retencao!
        protocolo="TEST-CATALOGO-CRITICAL-001",
    )
    r = client.post(
        "/prescricoes/TEST-CATALOGO-CRITICAL-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    alertas = body.get("alertas_regulatorios", [])
    assert len(alertas) >= 1
    a = alertas[0]
    assert a["severidade"] == "critical"
    assert a["sugestao_tipo_retencao"] == "antimicrobiano"
    # E mesmo com alerta, o receituário foi gerado (NÃO bloqueia em fase 1)
    assert body["total_receituarios"] == 1


def test_gerar_sem_alertas_quando_classificacao_coerente(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Amoxicilina declarada com tipo_retencao='antimicrobiano' (coerente
    com o catálogo) — nenhum alerta."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "AMOXICILINA",
                     "tipo_retencao": "antimicrobiano"}],
        protocolo="TEST-CATALOGO-COERENTE-001",
    )
    r = client.post(
        "/prescricoes/TEST-CATALOGO-COERENTE-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("alertas_regulatorios", []) == []


def test_gerar_alerta_warning_para_classe_344_ausente(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Diazepam (B1) declarado sem classe_controle — warning (não critical)."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        itens_data=[{"nome": "DIAZEPAM"}],  # sem classe — catálogo sabe que é B1
        protocolo="TEST-CATALOGO-WARN-001",
    )
    r = client.post(
        "/prescricoes/TEST-CATALOGO-WARN-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    alertas = r.json().get("alertas_regulatorios", [])
    assert len(alertas) >= 1
    assert alertas[0]["severidade"] == "warning"
    assert alertas[0]["sugestao_classe"] == "B1"


def test_catalogo_nao_bloqueia_emissao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Mesmo com alerta critical, /gerar retorna 201 e cria receituários.
    Fase 1 = alertas informativos, sem bloqueio."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "SEMAGLUTIDA"}],  # GLP-1 sem classificação
        protocolo="TEST-CATALOGO-NAOBLOC-001",
    )
    r = client.post(
        "/prescricoes/TEST-CATALOGO-NAOBLOC-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    # Receituário foi gerado (como simples, pois prescritor não declarou)
    assert body["total_receituarios"] >= 1
    # Mas alerta CRITICAL foi emitido
    alertas = body.get("alertas_regulatorios", [])
    assert any(a["severidade"] == "critical" for a in alertas)


def test_substancia_desconhecida_nao_gera_alerta(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Catálogo parcial: substância não cadastrada não deve gerar
    falso positivo."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "SUBSTANCIA_FICTICIA_XPTO"}],
        protocolo="TEST-CATALOGO-DESCONHECIDA-001",
    )
    r = client.post(
        "/prescricoes/TEST-CATALOGO-DESCONHECIDA-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json().get("alertas_regulatorios", []) == []


# ===========================================================================
# Atomização: salvaguarda via catálogo
# ===========================================================================

def test_atomizacao_bloqueada_por_catalogo(client, outer_conn):
    """eh_item_atomizavel(item, conn) — substância controlada no
    catálogo bloqueia atomização mesmo SEM classe_controle declarada."""
    from app.database_tx import get_tx
    from app.domain.medicamento import eh_item_atomizavel

    item = {
        "nome_medicamento": "Diazepam 5mg",
        # Sem classe_controle — prescritor esqueceu
        "classe_controle": None,
        "tipo_retencao": None,
    }
    # Sem conn → sem catálogo → ATOMIZÁVEL (compat)
    assert eh_item_atomizavel(item) is True

    # Com conn → consulta catálogo → BLOQUEIA (Diazepam é B1)
    with get_tx() as conn:
        assert eh_item_atomizavel(item, conn=conn) is False


def test_atomizacao_substancia_desconhecida_continua_atomizavel(
    client, outer_conn,
):
    """Substância não cadastrada no catálogo segue atomizável."""
    from app.database_tx import get_tx
    from app.domain.medicamento import eh_item_atomizavel

    item = {
        "nome_medicamento": "DIPIRONA",  # comum, sem controle
        "classe_controle": None,
        "tipo_retencao": None,
    }
    with get_tx() as conn:
        assert eh_item_atomizavel(item, conn=conn) is True


def test_atomizacao_glp1_bloqueada_por_catalogo(client, outer_conn):
    from app.database_tx import get_tx
    from app.domain.medicamento import eh_item_atomizavel

    item = {
        "nome_medicamento": "Semaglutida 1mg",
        "classe_controle": None,
        "tipo_retencao": None,
    }
    with get_tx() as conn:
        assert eh_item_atomizavel(item, conn=conn) is False


# ===========================================================================
# G1 — mecânica do carimbo (DESENHO-TALAO-DIGITAL-SNCR.md §1/§1.1, Opção 2)
#
# Contra as 56 curadas de sempre, com o carimbo explicitamente pendente. O
# que se prova aqui é a MECÂNICA — a fonte real (Anexo I consolidado) ainda
# não chegou (AC5 do desenho fica para quando ela chegar).
# ===========================================================================

def test_carimbo_nasce_pendente(client, outer_conn):
    """A migração 2fb9182a0846 cria a linha única já com tudo NULL —
    `buscar_carimbo_ativo` devolve None num banco recém-migrado, nunca um
    `CarimboRegulatorio` com campos vazios."""
    from app.database_tx import get_tx
    from app.domain.catalogo_regulatorio import buscar_carimbo_ativo

    with get_tx() as conn:
        assert buscar_carimbo_ativo(conn) is None


def test_aplicar_carimbo_e_depois_limpar_carimbo(client, outer_conn):
    """Ciclo completo: carimbar ativa o modo completo; limpar volta ao
    princípio da cautela. `limpar_carimbo` não apaga `catalogo_substancias`
    — só revoga a AFIRMAÇÃO de completude."""
    from app.database_tx import get_tx
    from app.domain.catalogo_regulatorio import buscar_carimbo_ativo
    from app.domain.catalogo_seed import aplicar_carimbo, limpar_carimbo

    with get_tx() as conn:
        aplicar_carimbo(
            conn, fonte="Teste", versao="RDC 000/2026", data_snapshot="2026-08-28",
        )
        carimbo = buscar_carimbo_ativo(conn)
        assert carimbo is not None
        assert carimbo.versao == "RDC 000/2026"
        assert carimbo.data_snapshot == "2026-08-28"

        limpar_carimbo(conn)
        assert buscar_carimbo_ativo(conn) is None


def test_aplicar_snapshot_carimbado_upsert_e_ativa_carimbo(client, outer_conn):
    """`aplicar_snapshot_carimbado` escreve as entradas COM versao/
    data_snapshot por linha e carimba de uma vez — o caminho que o
    importador (`importar_snapshot_rdc_substancias.py`) usa quando a fonte
    real chegar."""
    from app.database_tx import get_tx
    from app.domain.catalogo_regulatorio import (
        buscar_carimbo_ativo, buscar_substancia,
    )
    from app.domain.catalogo_seed import aplicar_snapshot_carimbado

    with get_tx() as conn:
        resultado = aplicar_snapshot_carimbado(
            conn,
            fonte="Portaria 344/98 Anexo I (teste)",
            versao="RDC 001/2099",
            data_snapshot="2099-01-01",
            entradas=[
                ("Substancia Snapshot Teste", "A1", None, None),
            ],
        )
        assert resultado["entradas"] == 1

        sub = buscar_substancia("Substancia Snapshot Teste", conn)
        assert sub is not None
        assert sub.classe_controle == "A1"

        carimbo = buscar_carimbo_ativo(conn)
        assert carimbo is not None
        assert carimbo.versao == "RDC 001/2099"


def test_aplicar_snapshot_carimbado_e_idempotente(client, outer_conn):
    """Rodar duas vezes com o mesmo dado não duplica — upsert por
    `dcb_normalizada`, mesma disciplina do seed curado."""
    from app.database_tx import get_tx
    from app.domain.catalogo_seed import aplicar_snapshot_carimbado

    entradas = [("Substancia Idempotente Teste", "B1", None, None)]
    with get_tx() as conn:
        aplicar_snapshot_carimbado(
            conn, fonte="Teste", versao="v1", data_snapshot="2099-01-01",
            entradas=entradas,
        )
        aplicar_snapshot_carimbado(
            conn, fonte="Teste", versao="v1", data_snapshot="2099-01-01",
            entradas=entradas,
        )
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM catalogo_substancias "
            "WHERE dcb_normalizada = ?",
            ("substancia idempotente teste",),
        ).fetchone()["n"]
        assert n == 1


def test_aplicar_snapshot_carimbado_exige_fonte_versao_data(client, outer_conn):
    """AC2/AC3 — sem fonte/versão/data_snapshot não é um snapshot
    versionado, é o seed de sempre. `aplicar_snapshot_carimbado` recusa."""
    from app.database_tx import get_tx
    from app.domain.catalogo_seed import aplicar_snapshot_carimbado

    with get_tx() as conn:
        for kwargs in (
            {"fonte": "", "versao": "v1", "data_snapshot": "2099-01-01"},
            {"fonte": "Teste", "versao": "", "data_snapshot": "2099-01-01"},
            {"fonte": "Teste", "versao": "v1", "data_snapshot": ""},
        ):
            with pytest.raises(ValueError):
                aplicar_snapshot_carimbado(
                    conn, entradas=[("X", "A1", None, None)], **kwargs,
                )
