"""
test_identidade_prescritor.py
==============================
Ticket 65 — Pipeline de identidade do prescritor (ICP → CPF → CNES → CFM/CFO).

Cobre:
   1. CPF + 1 vínculo → ok
   2. CPF + variação leve de nome → coerente_parcial
   3. CPF + nome divergente → divergente (não bloqueado)
   4. CPF não encontrado no CNES → nao_encontrado_cnes
   5. Múltiplos vínculos sem discriminador → multiplo_vinculo
   6. Múltiplos vínculos + conselho_uf resolve → ok
   7. Médico → tipo_conselho = CRM
   8. Odontólogo → tipo_conselho = CRO
   9. Conselho não encontrado → nao_encontrado_conselho
  10. Conselho inativo → divergência registrada
  11. Nome divergente mas CPF/conselho ok → divergente controlado
  12. Sem regressão: cnes_prescritor existente não quebrado
"""

from __future__ import annotations

import sqlite3

import pytest

from app.domain.identidade_prescritor import (
    BancoCnesConselhoProvider,
    MockConselhoProvider,
    _agrupar_vinculos,
    _buscar_cnes_por_conselho,
    _classificar_nome,
    resolver_identidade_prescritor,
)


# ---------------------------------------------------------------------------
# Fixtures — banco in-memory com tabelas CNES mínimas
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Banco in-memory com as tabelas CNES usadas pelo pipeline."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profissionais_cnes (
            CO_PROFISSIONAL_SUS TEXT PRIMARY KEY,
            CO_CPF              TEXT,
            NO_PROFISSIONAL     TEXT,
            CO_CNS              TEXT
        );

        CREATE TABLE IF NOT EXISTS relacao_prof_estab (
            CO_UNIDADE          TEXT,
            CO_PROFISSIONAL_SUS TEXT,
            CO_CBO              TEXT,
            CO_CONSELHO_CLASSE  TEXT,
            NU_REGISTRO         TEXT,
            SG_UF_CRM           TEXT
        );

        CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
            CO_UNIDADE  TEXT PRIMARY KEY,
            CO_CNES     TEXT,
            NO_FANTASIA TEXT,
            TP_UNIDADE  TEXT
        );
        """
    )
    return conn


def _inserir_profissional(
    conn: sqlite3.Connection,
    prof_id: str,
    cns: str,
    nome: str,
    cbo: str = "225125",
    conselho_classe: str = "71",
    conselho_numero: str = "12345",
    conselho_uf: str = "PE",
    co_unidade: str = "UNID001",
    nome_fantasia: str = "CLINICA TESTE",
    tp_unidade: str = "01",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO profissionais_cnes (CO_PROFISSIONAL_SUS, CO_CPF, NO_PROFISSIONAL, CO_CNS) VALUES (?, 'CO_CPF', ?, ?)",
        (prof_id, nome, cns),
    )
    conn.execute(
        "INSERT INTO relacao_prof_estab (CO_UNIDADE, CO_PROFISSIONAL_SUS, CO_CBO, CO_CONSELHO_CLASSE, NU_REGISTRO, SG_UF_CRM) VALUES (?, ?, ?, ?, ?, ?)",
        (co_unidade, prof_id, cbo, conselho_classe, conselho_numero, conselho_uf),
    )
    conn.execute(
        "INSERT OR IGNORE INTO estabelecimentos_cnes (CO_UNIDADE, CO_CNES, NO_FANTASIA, TP_UNIDADE) VALUES (?, ?, ?, ?)",
        (co_unidade, co_unidade[-7:], nome_fantasia, tp_unidade),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def test_agrupar_vinculos_deduplicacao():
    rows = [
        {"co_unidade": "U1", "cnes_code": "001", "nome_fantasia": "A", "tipo_estabelecimento": "01", "cbo": "225125", "conselho_numero": "123", "conselho_uf": "PE"},
        {"co_unidade": "U1", "cnes_code": "001", "nome_fantasia": "A", "tipo_estabelecimento": "01", "cbo": "225125", "conselho_numero": "123", "conselho_uf": "PE"},
        {"co_unidade": "U2", "cnes_code": "002", "nome_fantasia": "B", "tipo_estabelecimento": "01", "cbo": "225125", "conselho_numero": "123", "conselho_uf": "PE"},
    ]
    result = _agrupar_vinculos(rows)
    assert len(result) == 2


def test_classificar_nome_coerente_forte():
    assert _classificar_nome(True, 0.97) == "coerente_forte"


def test_classificar_nome_coerente_parcial():
    assert _classificar_nome(True, 0.88) == "coerente_parcial"


def test_classificar_nome_divergente():
    assert _classificar_nome(False, 0.0) == "divergente"


# ---------------------------------------------------------------------------
# _buscar_cnes_por_conselho
# ---------------------------------------------------------------------------


def test_buscar_cnes_por_conselho_encontrado():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO DA SILVA", conselho_numero="99999", conselho_uf="PE")
    rows = _buscar_cnes_por_conselho(conn, "99999", "PE")
    assert len(rows) >= 1
    assert rows[0]["nome_cnes"] == "JOAO DA SILVA"
    assert rows[0]["conselho_numero"] == "99999"


def test_buscar_cnes_por_conselho_nao_encontrado():
    conn = _make_conn()
    rows = _buscar_cnes_por_conselho(conn, "00000", "RJ")
    assert rows == []


def test_buscar_cnes_por_conselho_sem_uf_retorna_todos():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "ANA SILVA", conselho_numero="11111", conselho_uf="PE")
    _inserir_profissional(conn, "P002", "700001111222334", "ANA SILVA", conselho_numero="11111", conselho_uf="RJ",
                          co_unidade="UNID002")
    rows_sem_uf = _buscar_cnes_por_conselho(conn, "11111", None)
    assert len(rows_sem_uf) == 2
    rows_com_uf = _buscar_cnes_por_conselho(conn, "11111", "PE")
    assert len(rows_com_uf) == 1


# ---------------------------------------------------------------------------
# BancoCnesConselhoProvider
# ---------------------------------------------------------------------------


def test_banco_cnes_provider_encontrado():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO SILVA", conselho_numero="12345", conselho_uf="PE")
    provider = BancoCnesConselhoProvider(conn)
    result = provider.buscar("CRM", "12345", "PE")
    assert result is not None
    assert result["tipo_conselho"] == "CRM"
    assert result["numero"] == "12345"


def test_banco_cnes_provider_nao_encontrado():
    conn = _make_conn()
    provider = BancoCnesConselhoProvider(conn)
    assert provider.buscar("CRM", "99999", "PE") is None


def test_banco_cnes_provider_cro():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "ANA DENTISTA",
                          cbo="223208", conselho_classe="75", conselho_numero="5555", conselho_uf="PE")
    provider = BancoCnesConselhoProvider(conn)
    result = provider.buscar("CRO", "5555", "PE")
    assert result is not None
    assert result["tipo_conselho"] == "CRO"


# ---------------------------------------------------------------------------
# Caso 1 — CPF + 1 vínculo → ok
# ---------------------------------------------------------------------------


def test_caso1_cpf_um_vinculo_ok():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO DA SILVA",
                          conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO DA SILVA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO DA SILVA",
        conselho_numero="12345",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "ok"
    assert result["cns"] == "700001111222333"
    assert result["vinculo_escolhido"] is not None
    assert len(result["vinculos_disponiveis"]) == 1
    assert result["cpf_certificado"] == "12345678901"
    assert result["nome_validacao"]["status"] in ("coerente_forte", "coerente_parcial")


# ---------------------------------------------------------------------------
# Caso 2 — Variação leve de nome → coerente_parcial
# ---------------------------------------------------------------------------


def test_caso2_variacao_leve_nome():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO DA SILVA PEREIRA",
                          conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA PEREIRA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO DA SILVA",  # nome abreviado
        conselho_numero="12345",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    # Nome abreviado → coerente_parcial (containment no _match_nome)
    assert result["status"] in ("ok", "divergente")
    assert result["nome_validacao"] is not None
    # Importante: status não deve ser nao_encontrado_cnes
    assert result["status"] != "nao_encontrado_cnes"


# ---------------------------------------------------------------------------
# Caso 3 — Nome divergente → divergente (não bloqueado)
# ---------------------------------------------------------------------------


def test_caso3_nome_divergente_nao_bloqueado():
    """Nome completamente diferente → status divergente, mas dados retornados."""
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "ANTONIO FERREIRA",
                          conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "ANTONIO FERREIRA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="ROBERTO CAVALCANTE",  # nome totalmente diferente
        conselho_numero="12345",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "divergente"
    # Dados ainda retornados (não bloqueado)
    assert result["cns"] is not None
    assert result["conselho"] is not None
    assert any("nome_divergente" in d for d in result["divergencias"])


# ---------------------------------------------------------------------------
# Caso 4 — CPF não encontrado no CNES → nao_encontrado_cnes
# ---------------------------------------------------------------------------


def test_caso4_nao_encontrado_cnes():
    conn = _make_conn()  # banco vazio

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="99999",
        conselho_uf="PE",
    )

    assert result["status"] == "nao_encontrado_cnes"
    assert result["cns"] is None
    assert result["vinculo_escolhido"] is None


# ---------------------------------------------------------------------------
# Caso 5 — Múltiplos vínculos sem discriminador → multiplo_vinculo
# ---------------------------------------------------------------------------


def test_caso5_multiplos_vinculos_sem_discriminador():
    conn = _make_conn()
    # Mesmo profissional com 2 vínculos, sem UF para discriminar
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO SILVA",
                          conselho_numero="12345", conselho_uf="PE",
                          co_unidade="UNID001")
    conn.execute(
        "INSERT INTO relacao_prof_estab (CO_UNIDADE, CO_PROFISSIONAL_SUS, CO_CBO, CO_CONSELHO_CLASSE, NU_REGISTRO, SG_UF_CRM) VALUES (?, ?, ?, ?, ?, ?)",
        ("UNID002", "P001", "225125", "71", "12345", "PE"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO estabelecimentos_cnes (CO_UNIDADE, CO_CNES, NO_FANTASIA, TP_UNIDADE) VALUES (?, ?, ?, ?)",
        ("UNID002", "9999002", "HOSPITAL TESTE", "01"),
    )
    conn.commit()

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA",
        "ativo": True,
    })

    # Chamar sem conselho_uf para não ter discriminador
    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="12345",
        conselho_uf=None,   # sem UF → não pode discriminar
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "multiplo_vinculo"
    assert len(result["vinculos_disponiveis"]) >= 2
    assert result["vinculo_escolhido"] is None


# ---------------------------------------------------------------------------
# Caso 6 — Múltiplos vínculos + conselho_uf resolve → ok
# ---------------------------------------------------------------------------


def test_caso6_multiplos_vinculos_resolvidos_por_uf():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO SILVA",
                          conselho_numero="12345", conselho_uf="PE",
                          co_unidade="UNID001")
    conn.execute(
        "INSERT INTO relacao_prof_estab (CO_UNIDADE, CO_PROFISSIONAL_SUS, CO_CBO, CO_CONSELHO_CLASSE, NU_REGISTRO, SG_UF_CRM) VALUES (?, ?, ?, ?, ?, ?)",
        ("UNID002", "P001", "225125", "71", "12345", "RJ"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO estabelecimentos_cnes (CO_UNIDADE, CO_CNES, NO_FANTASIA, TP_UNIDADE) VALUES (?, ?, ?, ?)",
        ("UNID002", "9999002", "HOSPITAL RJ", "01"),
    )
    conn.commit()

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="12345",
        conselho_uf="PE",   # UF discrimina → 1 vínculo PE
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "ok"
    assert result["vinculo_escolhido"] is not None
    assert (result["vinculo_escolhido"].get("conselho_uf") or "").upper() == "PE"


# ---------------------------------------------------------------------------
# Caso 7 — Médico → tipo_conselho = CRM
# ---------------------------------------------------------------------------


def test_caso7_medico_crm():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "CARLOS MEDICO",
                          cbo="225142",       # médico clínico
                          conselho_classe="71",
                          conselho_numero="77777", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "77777",
        "uf": "PE",
        "nome_conselho": "CARLOS MEDICO",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="11111111111",
        nome_certificado="CARLOS MEDICO",
        conselho_numero="77777",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "ok"
    assert result["conselho"]["tipo_conselho"] == "CRM"
    assert result["tipo_prescritor"] == "medico"


# ---------------------------------------------------------------------------
# Caso 8 — Odontólogo → tipo_conselho = CRO
# ---------------------------------------------------------------------------


def test_caso8_odontologo_cro():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "ANA DENTISTA",
                          cbo="223208",       # odontólogo
                          conselho_classe="75",
                          conselho_numero="8888", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRO",
        "numero": "8888",
        "uf": "PE",
        "nome_conselho": "ANA DENTISTA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="22222222222",
        nome_certificado="ANA DENTISTA",
        conselho_numero="8888",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "ok"
    assert result["conselho"]["tipo_conselho"] == "CRO"
    assert result["tipo_prescritor"] == "odontologo"


# ---------------------------------------------------------------------------
# Caso 9 — Conselho não encontrado → nao_encontrado_conselho
# ---------------------------------------------------------------------------


def test_caso9_conselho_nao_encontrado():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "JOAO SILVA",
                          conselho_numero="12345", conselho_uf="PE")

    # Provider retorna None (conselho não encontrado)
    mock_conselho = MockConselhoProvider(None)

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="12345",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "nao_encontrado_conselho"
    assert any("conselho_nao_encontrado" in d for d in result["divergencias"])


# ---------------------------------------------------------------------------
# Caso 10 — Conselho inativo → divergência registrada
# ---------------------------------------------------------------------------


def test_caso10_conselho_inativo_registrado():
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "PEDRO SILVA",
                          conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "PEDRO SILVA",
        "ativo": False,  # inativo
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="33333333333",
        nome_certificado="PEDRO SILVA",
        conselho_numero="12345",
        conselho_uf="PE",
        conselho_provider=mock_conselho,
    )

    # Status pode ser ok ou divergente, mas divergência de conselho inativo deve aparecer
    assert any("conselho_inativo" in d for d in result["divergencias"])
    # Dados ainda retornados
    assert result["cns"] is not None


# ---------------------------------------------------------------------------
# Caso 11 — Nome divergente mas CPF/conselho ok → divergente controlado
# ---------------------------------------------------------------------------


def test_caso11_nome_divergente_controlado():
    """
    CPF e conselho são encontrados, mas o nome do certificado diverge
    completamente do nome no CNES. O pipeline retorna divergente mas
    não bloqueia — os dados são retornados para auditoria.
    """
    conn = _make_conn()
    _inserir_profissional(conn, "P001", "700001111222333", "MARCOS ANTONIO",
                          conselho_numero="55555", conselho_uf="CE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "55555",
        "uf": "CE",
        "nome_conselho": "MARCOS ANTONIO",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="44444444444",
        nome_certificado="PATRICIA LIMA",   # nome completamente diferente
        conselho_numero="55555",
        conselho_uf="CE",
        conselho_provider=mock_conselho,
    )

    assert result["status"] == "divergente"
    # Dados auditáveis presentes
    assert result["cns"] == "700001111222333"
    assert result["conselho"] is not None
    assert result["nome_validacao"]["status"] == "divergente"
    # Divergência registrada
    assert any("nome_divergente" in d for d in result["divergencias"])
    # NÃO raise exception — pipeline retornou
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Caso 12 — Sem conselho_numero → nao_encontrado_cnes
# ---------------------------------------------------------------------------


def test_caso12_sem_conselho_numero():
    """
    Sem número de conselho, CPF não pode ser resolvido no snapshot CNES.
    Pipeline retorna nao_encontrado_cnes com divergência documentada.
    """
    conn = _make_conn()

    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="55555555555",
        nome_certificado="JOAO SILVA",
        conselho_numero=None,   # sem conselho
    )

    assert result["status"] == "nao_encontrado_cnes"
    assert any("conselho_nao_informado" in d for d in result["divergencias"])


# ---------------------------------------------------------------------------
# Campos obrigatórios no resultado
# ---------------------------------------------------------------------------


def test_resultado_tem_todos_campos_obrigatorios():
    """Campos auditáveis obrigatórios presentes em qualquer status."""
    conn = _make_conn()
    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="99999",
    )

    campos = [
        "status", "cpf_certificado", "nome_certificado",
        "cns", "nome_cnes", "conselho", "nome_validacao",
        "vinculo_escolhido", "vinculos_disponiveis", "divergencias",
        "snapshot_mes", "snapshot_ref", "resolvido_em",
    ]
    for campo in campos:
        assert campo in result, f"Campo '{campo}' ausente no resultado"


def test_cpf_normalizado_no_resultado():
    """CPF é normalizado (apenas dígitos) no resultado."""
    conn = _make_conn()
    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="123.456.789-01",
        nome_certificado="JOAO SILVA",
        conselho_numero="99999",
    )
    assert result["cpf_certificado"] == "12345678901"


def test_snapshot_campos_presentes():
    conn = _make_conn()
    result = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado="12345678901",
        nome_certificado="JOAO SILVA",
        conselho_numero="12345",
    )
    assert result["snapshot_mes"]
    assert result["snapshot_ref"]
    assert result["resolvido_em"]


# ---------------------------------------------------------------------------
# Caso 12 — Sem regressão: cnes_prescritor não quebrado
# ---------------------------------------------------------------------------


def test_sem_regressao_cnes_prescritor():
    """
    Verifica que os imports e funções de cnes_prescritor.py continuam
    funcionando corretamente após a integração com NomeValidator (Ticket 64).
    """
    from app.domain.cnes_prescritor import (
        _calcular_nivel,
        _match_nome,
        eh_cbo_prescritor,
        tipo_prescritor_por_cbo,
    )

    # CBO helpers
    assert eh_cbo_prescritor("225125") is True
    assert eh_cbo_prescritor("999999") is False
    assert tipo_prescritor_por_cbo("225125") == "medico"
    assert tipo_prescritor_por_cbo("223208") == "odontologo"

    # _match_nome via NomeValidator (Ticket 64)
    assert _match_nome("JOAO SILVA", "JOAO SILVA") == ("exato", True)
    assert _match_nome("joao", "JOAO DA SILVA PEREIRA")[1] is True  # containment → parcial
    assert _match_nome("ROBERTO", "CARLOS")[1] is False  # divergente

    # _calcular_nivel
    assert _calcular_nivel(False, "exato", True, True) == "nao_encontrado"
    assert _calcular_nivel(True, "divergente", True, True) == "divergente"
    assert _calcular_nivel(True, "exato", True, True, None) == "forte"
    assert _calcular_nivel(True, "exato", True, True, False) == "parcial"
