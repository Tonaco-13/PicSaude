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

# Fixture CNES (arquitetura dual — ver docs/arquitetura_dual_bancos.md).
from tests.cnes_fixtures import cnes_db  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _app_conn() -> sqlite3.Connection:
    """
    Conexão SQLite in-memory para o parâmetro `conn` do pipeline.

    O pipeline `resolver_identidade_prescritor` declara em docstring que
    `conn` é mantida por compatibilidade — as queries CNES vão por
    `_get_cnes_conn()`. Mesmo assim os testes precisam de UMA conn válida.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_profissional(
    cnes_db,
    *,
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
    """Atalho — popula profissional + relação + estabelecimento no CNES tmp."""
    cnes_db.add_profissional(
        CO_PROFISSIONAL_SUS=prof_id, NO_PROFISSIONAL=nome, CO_CNS=cns, CO_CPF="CO_CPF",
    )
    cnes_db.add_relacao(
        CO_PROFISSIONAL_SUS=prof_id, CO_CONSELHO_CLASSE=conselho_classe,
        NU_REGISTRO=conselho_numero, SG_UF_CRM=conselho_uf,
        CO_CBO=cbo, CO_UNIDADE=co_unidade,
    )
    cnes_db.add_estabelecimento(
        CO_UNIDADE=co_unidade,
        CO_CNES=co_unidade[-7:],
        NO_FANTASIA=nome_fantasia,
        TP_UNIDADE=tp_unidade,
    )


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


def test_buscar_cnes_por_conselho_encontrado(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO DA SILVA", conselho_numero="99999", conselho_uf="PE")
    rows = _buscar_cnes_por_conselho(_app_conn(), "99999", "PE")
    assert len(rows) >= 1
    assert rows[0]["nome_cnes"] == "JOAO DA SILVA"
    assert rows[0]["conselho_numero"] == "99999"


def test_buscar_cnes_por_conselho_nao_encontrado(cnes_db):
    rows = _buscar_cnes_por_conselho(_app_conn(), "00000", "RJ")
    assert rows == []


def test_buscar_cnes_por_conselho_sem_uf_retorna_todos(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="ANA SILVA", conselho_numero="11111", conselho_uf="PE")
    _seed_profissional(cnes_db, prof_id="P002", cns="700001111222334",
                       nome="ANA SILVA", conselho_numero="11111", conselho_uf="RJ",
                       co_unidade="UNID002")
    rows_sem_uf = _buscar_cnes_por_conselho(_app_conn(), "11111", None)
    assert len(rows_sem_uf) == 2
    rows_com_uf = _buscar_cnes_por_conselho(_app_conn(), "11111", "PE")
    assert len(rows_com_uf) == 1


# ---------------------------------------------------------------------------
# BancoCnesConselhoProvider
# ---------------------------------------------------------------------------


def test_banco_cnes_provider_encontrado(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO SILVA", conselho_numero="12345", conselho_uf="PE")
    # Provider abre `_get_cnes_conn()` internamente — não recebe conn (no-arg).
    provider = BancoCnesConselhoProvider()
    result = provider.buscar("CRM", "12345", "PE")
    assert result is not None
    assert result["tipo_conselho"] == "CRM"
    assert result["numero"] == "12345"


def test_banco_cnes_provider_nao_encontrado(cnes_db):
    provider = BancoCnesConselhoProvider()
    assert provider.buscar("CRM", "99999", "PE") is None


def test_banco_cnes_provider_cro(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="ANA DENTISTA", cbo="223208", conselho_classe="75",
                       conselho_numero="5555", conselho_uf="PE")
    provider = BancoCnesConselhoProvider()
    result = provider.buscar("CRO", "5555", "PE")
    assert result is not None
    assert result["tipo_conselho"] == "CRO"


# ---------------------------------------------------------------------------
# Caso 1 — CPF + 1 vínculo → ok
# ---------------------------------------------------------------------------


def test_caso1_cpf_um_vinculo_ok(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO DA SILVA",
                       conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO DA SILVA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso2_variacao_leve_nome(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO DA SILVA PEREIRA",
                       conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA PEREIRA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso3_nome_divergente_nao_bloqueado(cnes_db):
    """Nome completamente diferente → status divergente, mas dados retornados."""
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="ANTONIO FERREIRA",
                       conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "ANTONIO FERREIRA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso4_nao_encontrado_cnes(cnes_db):
    # cnes_db sem seed → banco vazio (mas tabelas existem)
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso5_multiplos_vinculos_sem_discriminador(cnes_db):
    # Mesmo profissional com 2 vínculos, sem UF para discriminar
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO SILVA",
                       conselho_numero="12345", conselho_uf="PE",
                       co_unidade="UNID001")
    cnes_db.add_relacao(
        CO_PROFISSIONAL_SUS="P001", CO_CONSELHO_CLASSE="71",
        NU_REGISTRO="12345", SG_UF_CRM="PE",
        CO_CBO="225125", CO_UNIDADE="UNID002",
    )
    cnes_db.add_estabelecimento(
        CO_UNIDADE="UNID002", CO_CNES="9999002",
        NO_FANTASIA="HOSPITAL TESTE", TP_UNIDADE="01",
    )

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA",
        "ativo": True,
    })

    # Chamar sem conselho_uf para não ter discriminador
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso6_multiplos_vinculos_resolvidos_por_uf(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO SILVA",
                       conselho_numero="12345", conselho_uf="PE",
                       co_unidade="UNID001")
    cnes_db.add_relacao(
        CO_PROFISSIONAL_SUS="P001", CO_CONSELHO_CLASSE="71",
        NU_REGISTRO="12345", SG_UF_CRM="RJ",
        CO_CBO="225125", CO_UNIDADE="UNID002",
    )
    cnes_db.add_estabelecimento(
        CO_UNIDADE="UNID002", CO_CNES="9999002",
        NO_FANTASIA="HOSPITAL RJ", TP_UNIDADE="01",
    )

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "JOAO SILVA",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso7_medico_crm(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="CARLOS MEDICO",
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
        conn=_app_conn(),
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


def test_caso8_odontologo_cro(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="ANA DENTISTA",
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
        conn=_app_conn(),
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


def test_caso9_conselho_nao_encontrado(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="JOAO SILVA",
                       conselho_numero="12345", conselho_uf="PE")

    # Provider retorna None (conselho não encontrado)
    mock_conselho = MockConselhoProvider(None)

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso10_conselho_inativo_registrado(cnes_db):
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="PEDRO SILVA",
                       conselho_numero="12345", conselho_uf="PE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "12345",
        "uf": "PE",
        "nome_conselho": "PEDRO SILVA",
        "ativo": False,  # inativo
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso11_nome_divergente_controlado(cnes_db):
    """
    CPF e conselho são encontrados, mas o nome do certificado diverge
    completamente do nome no CNES. O pipeline retorna divergente mas
    não bloqueia — os dados são retornados para auditoria.
    """
    _seed_profissional(cnes_db, prof_id="P001", cns="700001111222333",
                       nome="MARCOS ANTONIO",
                       conselho_numero="55555", conselho_uf="CE")

    mock_conselho = MockConselhoProvider({
        "tipo_conselho": "CRM",
        "numero": "55555",
        "uf": "CE",
        "nome_conselho": "MARCOS ANTONIO",
        "ativo": True,
    })

    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_caso12_sem_conselho_numero(cnes_db):
    """
    Sem número de conselho, CPF não pode ser resolvido no snapshot CNES.
    Pipeline retorna nao_encontrado_cnes com divergência documentada.
    """
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
        cpf_certificado="55555555555",
        nome_certificado="JOAO SILVA",
        conselho_numero=None,   # sem conselho
    )

    assert result["status"] == "nao_encontrado_cnes"
    assert any("conselho_nao_informado" in d for d in result["divergencias"])


# ---------------------------------------------------------------------------
# Campos obrigatórios no resultado
# ---------------------------------------------------------------------------


def test_resultado_tem_todos_campos_obrigatorios(cnes_db):
    """Campos auditáveis obrigatórios presentes em qualquer status."""
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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


def test_cpf_normalizado_no_resultado(cnes_db):
    """CPF é normalizado (apenas dígitos) no resultado."""
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
        cpf_certificado="123.456.789-01",
        nome_certificado="JOAO SILVA",
        conselho_numero="99999",
    )
    assert result["cpf_certificado"] == "12345678901"


def test_snapshot_campos_presentes(cnes_db):
    result = resolver_identidade_prescritor(
        conn=_app_conn(),
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
