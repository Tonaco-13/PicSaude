"""
test_cnes_prescritor.py
=======================
Ticket 47 — Camada 6: Validação CNES do Prescritor (base)
Ticket 48 — Robustez: normalização de nome, vínculo com prestador, snapshot auditável

Cobre:

  Helpers de CBO (T47)
    1.  eh_cbo_prescritor — médico (2251*)
    2.  eh_cbo_prescritor — cirurgião (2252*)
    3.  eh_cbo_prescritor — odontólogo (2232*)
    4.  eh_cbo_prescritor — CBO não prescritivo retorna False
    5.  eh_cbo_prescritor — string vazia retorna False
    6.  eh_cbo_prescritor — prefixo com espaços não bate
    7.  tipo_prescritor_por_cbo — médico identificado corretamente
    8.  tipo_prescritor_por_cbo — cirurgião identificado corretamente
    9.  tipo_prescritor_por_cbo — odontólogo identificado corretamente
   10.  tipo_prescritor_por_cbo — CBO desconhecido retorna None
   11.  tipo_prescritor_por_cbo — string vazia retorna None

  Normalização de nome (T48)
   12.  _normalizar_nome — remove acentos
   13.  _normalizar_nome — converte para maiúsculas
   14.  _normalizar_nome — colapsa espaços extras
   15.  _normalizar_nome — combinação: acento + caixa + espaço
   16.  _match_nome — exato após normalização (José vs JOSE)
   17.  _match_nome — exato com acentos distintos
   18.  _match_nome — parcial (nome contido no nome completo)
   19.  _match_nome — parcial inverso (nome completo contido no nome CNES)
   20.  _match_nome — divergente (nomes completamente diferentes)
   21.  _match_nome — string vazia → divergente

  Cálculo de nível (T47/T48)
   22.  forte — nome_exato + cbo + conselho + vinculo=None
   23.  forte — nome_exato + cbo + conselho + vinculo=True
   24.  parcial — vinculo=False rebaixa de forte para parcial
   25.  parcial — sem conselho formal
   26.  parcial — nome_parcial + cbo ok
   27.  divergente — nome_divergente
   28.  divergente — cbo não prescritivo
   29.  divergente — nome e cbo ambos falhando
   30.  nao_encontrado — cns ausente (independente dos demais)

  validar_cns_prescritor — banco in-memory (T47/T48)
   31.  CNS não encontrado → nao_encontrado, cns_encontrado=False
   32.  CNS vazio → nao_encontrado sem consulta ao banco
   33.  Resultado forte — todos os checks ok
   34.  Resultado parcial — sem conselho prescritivo
   35.  Divergente por nome — nome muito diferente
   36.  Divergente por CBO — CBO não prescritivo
   37.  Erro de banco → nao_encontrado sem lançar exceção
   38.  snapshot_ref sempre presente
   39.  snapshot_mes sempre presente
   40.  validado_em sempre presente e não vazio
   41.  cbos_encontrados — cbo primário reportado no campo 'cbo'
   42.  vinculos_ativos contagem correta
   43.  conselhos — conselho + crm_declarado + uf corretamente extraídos
   44.  tipo_prescritor identificado por CBO

  Vínculo com prestador (T48)
   45.  org_id=None → vinculo_com_prestador=None
   46.  org_id fornecido, vínculo encontrado → vinculo_com_prestador=True
   47.  org_id fornecido, prestador sem CNES mapeado → vinculo_com_prestador=None
   48.  org_id fornecido, CO_UNIDADE não bate → vinculo_com_prestador=False
   49.  org_id não existe em prestadores → vinculo_com_prestador=None
   50.  vínculo False adiciona entrada em divergencias

  Divergencias (T48)
   51.  divergencias vazia quando tudo ok e sem org_id
   52.  divergencias contém entrada de nome quando divergente
   53.  divergencias contém entrada de CBO quando não prescritivo

  Integração com POST /prescricoes (T47/T48)
   54.  Resposta contém cnes_validacao com nivel_validacao_cnes
   55.  Resposta contém snapshot_ref e snapshot_mes
   56.  Evento prescricao_emitida contém cnes_validacao no payload_json
   57.  Emissão não é bloqueada mesmo com nivel divergente
"""

from __future__ import annotations

import json
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Importações do domínio
# ---------------------------------------------------------------------------
from app.domain.cnes_prescritor import (
    _calcular_nivel,
    _match_nome,
    _normalizar_nome,
    eh_cbo_prescritor,
    tipo_prescritor_por_cbo,
    validar_cns_prescritor,
)


# ===========================================================================
# Fixtures de banco in-memory
# ===========================================================================

def _make_conn_vazio() -> sqlite3.Connection:
    """Banco in-memory SEM tabelas CNES — simula erro de tabela ausente."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _make_conn_cnes(
    profissionais: list[dict],
    relacoes: list[dict],
    prestadores: list[dict] | None = None,
    cnes_estab: list[dict] | None = None,
) -> sqlite3.Connection:
    """
    Banco in-memory com tabelas CNES + prestadores (opcionais).

    profissionais : CO_PROFISSIONAL_SUS, CO_CNS, NO_PROFISSIONAL
    relacoes      : CO_PROFISSIONAL_SUS, CO_CONSELHO_CLASSE, NU_REGISTRO,
                    SG_UF_CRM, CO_CBO, CO_UNIDADE
    prestadores   : id, org_id, nome, tipo, cnpj, ativo
    cnes_estab    : CO_CNES, NU_CNPJ
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE profissionais_cnes (
            CO_PROFISSIONAL_SUS TEXT,
            CO_CNS              TEXT,
            NO_PROFISSIONAL     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE relacao_prof_estab (
            CO_PROFISSIONAL_SUS TEXT,
            CO_CONSELHO_CLASSE  TEXT,
            NU_REGISTRO         TEXT,
            SG_UF_CRM           TEXT,
            CO_CBO              TEXT,
            CO_UNIDADE          TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE prestadores (
            id TEXT, org_id TEXT, nome TEXT, tipo TEXT,
            cnpj TEXT, ativo INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE estabelecimentos_cnes (
            CO_CNES TEXT,
            NU_CNPJ TEXT
        )
    """)
    for p in profissionais:
        conn.execute(
            "INSERT INTO profissionais_cnes VALUES (?, ?, ?)",
            (p["CO_PROFISSIONAL_SUS"], p["CO_CNS"], p["NO_PROFISSIONAL"]),
        )
    for r in relacoes:
        conn.execute(
            "INSERT INTO relacao_prof_estab VALUES (?, ?, ?, ?, ?, ?)",
            (r["CO_PROFISSIONAL_SUS"], r["CO_CONSELHO_CLASSE"],
             r["NU_REGISTRO"], r["SG_UF_CRM"], r["CO_CBO"], r["CO_UNIDADE"]),
        )
    for p in (prestadores or []):
        conn.execute(
            "INSERT INTO prestadores VALUES (?, ?, ?, ?, ?, ?)",
            (p["id"], p["org_id"], p["nome"], p["tipo"], p["cnpj"], p["ativo"]),
        )
    for e in (cnes_estab or []):
        conn.execute(
            "INSERT INTO estabelecimentos_cnes VALUES (?, ?)",
            (e["CO_CNES"], e["NU_CNPJ"]),
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Dados de fixture reutilizáveis
# ---------------------------------------------------------------------------

_PROF_MEDICO = {
    "CO_PROFISSIONAL_SUS": "PROF001",
    "CO_CNS":              "123456789012345",
    "NO_PROFISSIONAL":     "JOAO DA SILVA",
}
_REL_MEDICO = {
    "CO_PROFISSIONAL_SUS": "PROF001",
    "CO_CONSELHO_CLASSE":  "71",       # CRM
    "NU_REGISTRO":         "12345",
    "SG_UF_CRM":           "PE",
    "CO_CBO":              "225125",
    "CO_UNIDADE":          "UNID001",
}

_PROF_ODONTOLOGO = {
    "CO_PROFISSIONAL_SUS": "PROF002",
    "CO_CNS":              "999888777666555",
    "NO_PROFISSIONAL":     "MARIA SANTOS",
}
_REL_ODONTOLOGO = {
    "CO_PROFISSIONAL_SUS": "PROF002",
    "CO_CONSELHO_CLASSE":  "75",       # CRO
    "NU_REGISTRO":         "5678",
    "SG_UF_CRM":           "PE",
    "CO_CBO":              "223210",
    "CO_UNIDADE":          "UNID002",
}

_PROF_NAO_PRESCRITOR = {
    "CO_PROFISSIONAL_SUS": "PROF003",
    "CO_CNS":              "111222333444555",
    "NO_PROFISSIONAL":     "ANA FERREIRA",
}
_REL_NAO_PRESCRITOR = {
    "CO_PROFISSIONAL_SUS": "PROF003",
    "CO_CONSELHO_CLASSE":  "06",       # COREN
    "NU_REGISTRO":         "9999",
    "SG_UF_CRM":           "PE",
    "CO_CBO":              "322205",   # Enfermeiro
    "CO_UNIDADE":          "UNID003",
}


# ===========================================================================
# GRUPO 1 — Helpers de CBO (T47)
# ===========================================================================

def test_eh_cbo_prescritor_medico():
    """1. Prefixo 2251* → prescritivo."""
    assert eh_cbo_prescritor("225125") is True
    assert eh_cbo_prescritor("225100") is True
    assert eh_cbo_prescritor("225199") is True


def test_eh_cbo_prescritor_cirurgiao():
    """2. Prefixo 2252* → prescritivo."""
    assert eh_cbo_prescritor("225200") is True
    assert eh_cbo_prescritor("225242") is True


def test_eh_cbo_prescritor_odontologo():
    """3. Prefixo 2232* → prescritivo."""
    assert eh_cbo_prescritor("223210") is True
    assert eh_cbo_prescritor("223205") is True


def test_eh_cbo_prescritor_nao_prescritor():
    """4. CBOs que não iniciam com 2251/2252/2232 → False."""
    assert eh_cbo_prescritor("322205") is False
    assert eh_cbo_prescritor("515105") is False
    assert eh_cbo_prescritor("999999") is False


def test_eh_cbo_prescritor_string_vazia():
    """5. String vazia → False."""
    assert eh_cbo_prescritor("") is False


def test_eh_cbo_prescritor_espacos():
    """6. String com espaços não casa (não começa com prefixo limpo)."""
    assert eh_cbo_prescritor("   ") is False
    assert eh_cbo_prescritor(" 2251") is False


def test_tipo_prescritor_medico():
    """7. CBO 2251* → tipo 'medico'."""
    assert tipo_prescritor_por_cbo("225125") == "medico"


def test_tipo_prescritor_cirurgiao():
    """8. CBO 2252* → tipo 'cirurgiao'."""
    assert tipo_prescritor_por_cbo("225242") == "cirurgiao"


def test_tipo_prescritor_odontologo():
    """9. CBO 2232* → tipo 'odontologo'."""
    assert tipo_prescritor_por_cbo("223210") == "odontologo"


def test_tipo_prescritor_none_para_desconhecido():
    """10. CBO não prescritivo → None."""
    assert tipo_prescritor_por_cbo("322205") is None
    assert tipo_prescritor_por_cbo("515105") is None


def test_tipo_prescritor_none_para_vazio():
    """11. String vazia → None."""
    assert tipo_prescritor_por_cbo("") is None


# ===========================================================================
# GRUPO 2 — Normalização e matching de nome (T48)
# ===========================================================================

def test_normalizar_nome_remove_acentos():
    """12. Acentos removidos após normalização."""
    assert _normalizar_nome("José") == "JOSE"
    assert _normalizar_nome("Márcia") == "MARCIA"
    assert _normalizar_nome("João") == "JOAO"
    assert _normalizar_nome("Ângela") == "ANGELA"


def test_normalizar_nome_maiusculas():
    """13. Converte para maiúsculas."""
    assert _normalizar_nome("silva") == "SILVA"
    assert _normalizar_nome("Ana Paula") == "ANA PAULA"


def test_normalizar_nome_espacos():
    """14. Colapsa espaços extras."""
    assert _normalizar_nome("  JOAO   SILVA  ") == "JOAO SILVA"
    assert _normalizar_nome("\tMARIA\n") == "MARIA"


def test_normalizar_nome_combinado():
    """15. Combinação: acento + caixa + espaços."""
    assert _normalizar_nome("  Márcia  Dias  ") == "MARCIA DIAS"
    assert _normalizar_nome("joão   da   silva") == "JOAO DA SILVA"


def test_match_nome_exato_simples():
    """16. Nomes idênticos após normalização → exato."""
    match_tipo, coincide = _match_nome("JOAO DA SILVA", "JOAO DA SILVA")
    assert match_tipo == "exato"
    assert coincide is True


def test_match_nome_exato_com_acento():
    """17. José vs JOSE → exato (acento normalizado)."""
    match_tipo, coincide = _match_nome("José Da Silva", "JOSE DA SILVA")
    assert match_tipo == "exato"
    assert coincide is True


def test_match_nome_parcial_contido():
    """18. Nome declarado contido no nome CNES (nome composto mais longo) → parcial."""
    # "JOAO DA SILVA" está contido em "JOAO DA SILVA PEREIRA SANTOS"
    match_tipo, coincide = _match_nome("JOAO DA SILVA", "JOAO DA SILVA PEREIRA SANTOS")
    assert match_tipo == "parcial"
    assert coincide is True


def test_match_nome_parcial_inverso():
    """19. Nome CNES contido no nome declarado → parcial."""
    match_tipo, coincide = _match_nome("JOAO DA SILVA PEREIRA", "JOAO DA SILVA")
    assert match_tipo == "parcial"
    assert coincide is True


def test_match_nome_divergente():
    """20. Nomes completamente diferentes → divergente."""
    match_tipo, coincide = _match_nome("PEDRO ALVES XYZWQ", "JOAO DA SILVA")
    assert match_tipo == "divergente"
    assert coincide is False


def test_match_nome_vazio():
    """21. String vazia → divergente (sem comparação)."""
    match_tipo, coincide = _match_nome("", "JOAO DA SILVA")
    assert match_tipo == "divergente"
    assert coincide is False


# ===========================================================================
# GRUPO 3 — Cálculo de nível (T47/T48)
# ===========================================================================

def test_nivel_forte_vinculo_none():
    """22. nome_exato + cbo + conselho + vinculo=None → forte."""
    assert _calcular_nivel(True, "exato", True, True, None) == "forte"


def test_nivel_forte_vinculo_true():
    """23. nome_exato + cbo + conselho + vinculo=True → forte."""
    assert _calcular_nivel(True, "exato", True, True, True) == "forte"


def test_nivel_parcial_vinculo_false():
    """24. vinculo=False rebaixa forte para parcial."""
    assert _calcular_nivel(True, "exato", True, True, False) == "parcial"


def test_nivel_parcial_sem_conselho():
    """25. nome_exato + cbo ok, sem conselho → parcial."""
    assert _calcular_nivel(True, "exato", True, False) == "parcial"


def test_nivel_parcial_nome_parcial():
    """26. nome_parcial + cbo ok → parcial."""
    assert _calcular_nivel(True, "parcial", True, True) == "parcial"


def test_nivel_divergente_nome():
    """27. nome_divergente → divergente (falha dura)."""
    assert _calcular_nivel(True, "divergente", True, True) == "divergente"


def test_nivel_divergente_cbo():
    """28. cbo não prescritivo → divergente."""
    assert _calcular_nivel(True, "exato", False, True) == "divergente"


def test_nivel_divergente_ambos():
    """29. nome e cbo ambos falhando → divergente."""
    assert _calcular_nivel(True, "divergente", False, False) == "divergente"


def test_nivel_nao_encontrado():
    """30. cns_encontrado=False → nao_encontrado (independente dos demais)."""
    assert _calcular_nivel(False, "exato", True, True) == "nao_encontrado"
    assert _calcular_nivel(False, "divergente", False, False) == "nao_encontrado"


# ===========================================================================
# GRUPO 4 — validar_cns_prescritor com banco in-memory (T47/T48)
# ===========================================================================

def test_validar_cns_nao_encontrado_banco():
    """31. CNS ausente → nao_encontrado, campos None."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "000000000000001", "QUALQUER NOME")
    assert r["nivel_validacao_cnes"] == "nao_encontrado"
    assert r["cns_encontrado"] is False
    assert r["nome_normalizado_coincide"] is None
    assert r["cbo_prescritor_valido"] is None
    conn.close()


def test_validar_cns_vazio():
    """32. CNS vazio → nao_encontrado sem consulta ao banco."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "", "DR JOSE")
    assert r["nivel_validacao_cnes"] == "nao_encontrado"
    assert r["cns_encontrado"] is False
    conn.close()


def test_validar_cns_forte():
    """33. Resultado forte — todos os checks ok."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["nivel_validacao_cnes"] == "forte"
    assert r["cns_encontrado"] is True
    assert r["nome_normalizado_coincide"] is True
    assert r["nome_match_tipo"] == "exato"
    assert r["cbo_prescritor_valido"] is True
    conn.close()


def test_validar_cns_parcial_sem_conselho():
    """34. Resultado parcial — CBO ok mas conselho inválido."""
    rel_sem_conselho = {**_REL_MEDICO, "CO_CONSELHO_CLASSE": "99"}
    conn = _make_conn_cnes([_PROF_MEDICO], [rel_sem_conselho])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["nivel_validacao_cnes"] == "parcial"
    assert r["cns_encontrado"] is True
    assert r["nome_normalizado_coincide"] is True
    assert r["cbo_prescritor_valido"] is True
    conn.close()


def test_validar_cns_divergente_nome():
    """35. Divergente por nome — nome declarado muito diferente."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "PEDRO COMPLETAMENTE DIFERENTE")
    assert r["nivel_validacao_cnes"] == "divergente"
    assert r["cns_encontrado"] is True
    assert r["nome_normalizado_coincide"] is False
    assert r["nome_match_tipo"] == "divergente"
    conn.close()


def test_validar_cns_divergente_cbo():
    """36. Divergente por CBO — CBO não prescritivo."""
    conn = _make_conn_cnes([_PROF_NAO_PRESCRITOR], [_REL_NAO_PRESCRITOR])
    r = validar_cns_prescritor(conn, "111222333444555", "ANA FERREIRA")
    assert r["nivel_validacao_cnes"] == "divergente"
    assert r["cns_encontrado"] is True
    assert r["cbo_prescritor_valido"] is False
    conn.close()


def test_validar_cns_erro_banco():
    """37. Erro de banco → nao_encontrado sem lançar exceção."""
    conn = _make_conn_vazio()   # tabelas CNES não existem
    r = validar_cns_prescritor(conn, "123456789012345", "DR TESTE")
    assert r["nivel_validacao_cnes"] == "nao_encontrado"
    assert r["cns_encontrado"] is False
    assert any("erro_consulta_cnes" in d for d in r["divergencias"])
    conn.close()


def test_snapshot_ref_presente():
    """38. snapshot_ref sempre presente."""
    conn = _make_conn_cnes([], [])
    r = validar_cns_prescritor(conn, "999999999999999", "X")
    assert "snapshot_ref" in r
    assert r["snapshot_ref"]  # não vazio
    conn.close()


def test_snapshot_mes_presente():
    """39. snapshot_mes sempre presente."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert "snapshot_mes" in r
    assert r["snapshot_mes"]
    conn.close()


def test_validado_em_presente():
    """40. validado_em sempre presente e não vazio."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert "validado_em" in r
    assert r["validado_em"]
    assert "T" in r["validado_em"]   # formato ISO
    conn.close()


def test_cbo_primario_no_campo_cbo():
    """41. Campo 'cbo' retorna o CBO prescritivo primário encontrado."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["cbo"] == "225125"
    assert r["cbo_prescritor_valido"] is True
    conn.close()


def test_vinculos_ativos_contagem():
    """42. vinculos_ativos conta unidades únicas."""
    rel_b = {**_REL_MEDICO, "CO_CBO": "225135", "CO_UNIDADE": "UNID002"}
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO, rel_b])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["vinculos_ativos"] >= 2
    conn.close()


def test_conselho_crm_extraido():
    """43. conselho, crm_declarado e uf_crm_declarado corretamente extraídos."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["conselho"] == "71"
    assert r["crm_declarado"] == "12345"
    assert r["uf_crm_declarado"] == "PE"
    assert r["crm_cnes_coincide"] is True
    assert r["uf_cnes_coincide"] is True
    conn.close()


def test_tipo_prescritor_identificado():
    """44. tipo_prescritor correto a partir do CBO."""
    conn_med = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r_med = validar_cns_prescritor(conn_med, "123456789012345", "JOAO DA SILVA")
    assert r_med["tipo_prescritor"] == "medico"
    conn_med.close()

    conn_odo = _make_conn_cnes([_PROF_ODONTOLOGO], [_REL_ODONTOLOGO])
    r_odo = validar_cns_prescritor(conn_odo, "999888777666555", "MARIA SANTOS")
    assert r_odo["tipo_prescritor"] == "odontologo"
    conn_odo.close()


# ===========================================================================
# GRUPO 5 — Vínculo com prestador (T48)
# ===========================================================================

def test_vinculo_prestador_none_quando_org_id_none():
    """45. org_id=None → vinculo_com_prestador=None (não aplicável)."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id=None)
    assert r["vinculo_com_prestador"] is None
    conn.close()


def test_vinculo_prestador_encontrado():
    """46. CO_UNIDADE do prescritor bate com CO_CNES do prestador → True, nivel=forte."""
    conn = _make_conn_cnes(
        profissionais=[_PROF_MEDICO],
        relacoes=[_REL_MEDICO],       # CO_UNIDADE = "UNID001"
        prestadores=[{
            "id": "UUID-001", "org_id": "HOSP-PE-001",
            "nome": "Hospital Teste", "tipo": "hospital",
            "cnpj": "12345678000195", "ativo": 1,
        }],
        cnes_estab=[{
            "CO_CNES": "UNID001",     # bate com CO_UNIDADE do prescritor
            "NU_CNPJ": "12345678000195",
        }],
    )
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id="HOSP-PE-001")
    assert r["vinculo_com_prestador"] is True
    assert r["nivel_validacao_cnes"] == "forte"
    conn.close()


def test_vinculo_prestador_sem_cnes_mapeado():
    """47. Prestador existe mas sem CO_CNES em estabelecimentos_cnes → None."""
    conn = _make_conn_cnes(
        profissionais=[_PROF_MEDICO],
        relacoes=[_REL_MEDICO],
        prestadores=[{
            "id": "UUID-002", "org_id": "CLINICA-001",
            "nome": "Clínica Sem CNES", "tipo": "clinica",
            "cnpj": "99887766000100", "ativo": 1,
        }],
        cnes_estab=[],   # sem mapeamento
    )
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id="CLINICA-001")
    assert r["vinculo_com_prestador"] is None   # não é divergência
    conn.close()


def test_vinculo_prestador_co_unidade_nao_bate():
    """48. CO_UNIDADE do prescritor não inclui o CO_CNES do prestador → False."""
    conn = _make_conn_cnes(
        profissionais=[_PROF_MEDICO],
        relacoes=[_REL_MEDICO],       # CO_UNIDADE = "UNID001"
        prestadores=[{
            "id": "UUID-003", "org_id": "OUTRO-HOSP",
            "nome": "Outro Hospital", "tipo": "hospital",
            "cnpj": "55555555000155", "ativo": 1,
        }],
        cnes_estab=[{
            "CO_CNES": "UNID999",     # diferente do CO_UNIDADE do prescritor
            "NU_CNPJ": "55555555000155",
        }],
    )
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id="OUTRO-HOSP")
    assert r["vinculo_com_prestador"] is False
    # vínculo False rebaixa de forte → parcial
    assert r["nivel_validacao_cnes"] == "parcial"
    conn.close()


def test_vinculo_prestador_org_inexistente():
    """49. org_id não existe em prestadores → vinculo_com_prestador=None."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id="NAO-EXISTE")
    assert r["vinculo_com_prestador"] is None
    conn.close()


def test_vinculo_false_adiciona_divergencia():
    """50. vinculo_com_prestador=False gera entrada em divergencias."""
    conn = _make_conn_cnes(
        profissionais=[_PROF_MEDICO],
        relacoes=[_REL_MEDICO],
        prestadores=[{
            "id": "UUID-004", "org_id": "EXTERNO",
            "nome": "Externo", "tipo": "clinica",
            "cnpj": "11111111000111", "ativo": 1,
        }],
        cnes_estab=[{
            "CO_CNES": "UNID_EXTERNA",
            "NU_CNPJ": "11111111000111",
        }],
    )
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA", org_id="EXTERNO")
    assert r["vinculo_com_prestador"] is False
    assert any("vinculo_prestador_ausente" in d for d in r["divergencias"])
    conn.close()


# ===========================================================================
# GRUPO 6 — Divergencias (T48)
# ===========================================================================

def test_divergencias_vazia_quando_tudo_ok():
    """51. Resultado forte → divergencias = []."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "JOAO DA SILVA")
    assert r["divergencias"] == []
    conn.close()


def test_divergencias_nome_divergente():
    """52. Nome divergente → divergencias tem entrada de nome."""
    conn = _make_conn_cnes([_PROF_MEDICO], [_REL_MEDICO])
    r = validar_cns_prescritor(conn, "123456789012345", "ZXYWV COMPLETAMENTE OUTRO")
    assert any("nome_divergente" in d for d in r["divergencias"])
    conn.close()


def test_divergencias_cbo_invalido():
    """53. CBO não prescritivo → divergencias tem entrada de cbo."""
    conn = _make_conn_cnes([_PROF_NAO_PRESCRITOR], [_REL_NAO_PRESCRITOR])
    r = validar_cns_prescritor(conn, "111222333444555", "ANA FERREIRA")
    assert any("cbo_nao_prescritivo" in d for d in r["divergencias"])
    conn.close()


# ===========================================================================
# GRUPO 7 — Integração com POST /prescricoes (T47/T48)
# ===========================================================================

def test_resposta_post_prescricoes_tem_cnes_validacao(prescritor):
    """54. Resposta de POST /prescricoes contém cnes_validacao com nivel."""
    payload = {
        "cns_prescritor": "123456789012345",
        "nome_prescritor": "Dr. Teste",
        "cpf_paciente": "12345678901",
        "nome_paciente": "Paciente Teste",
        "tipo_emissao": "nova",
        "itens": [{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
                   "quantidade": 10, "posologia": "1 capsula 3x ao dia"}],
    }
    resp = prescritor.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert "cnes_validacao" in body
    assert body["cnes_validacao"]["nivel_validacao_cnes"] in (
        "forte", "parcial", "divergente", "nao_encontrado"
    )


def test_resposta_tem_snapshot_fields(prescritor):
    """55. Resposta contém snapshot_ref, snapshot_mes e validado_em."""
    payload = {
        "cns_prescritor": "123456789012345",
        "nome_prescritor": "Dr. Teste",
        "cpf_paciente": "12345678901",
        "nome_paciente": "Paciente Teste",
        "tipo_emissao": "nova",
        "itens": [{"nome_medicamento": "DIPIRONA", "concentracao": "500mg",
                   "quantidade": 5, "posologia": "1 comprimido ao dia"}],
    }
    resp = prescritor.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    cv = resp.json()["cnes_validacao"]
    assert "snapshot_ref" in cv and cv["snapshot_ref"]
    assert "snapshot_mes" in cv and cv["snapshot_mes"]
    assert "validado_em" in cv and cv["validado_em"]


def test_evento_emitida_tem_cnes_validacao(prescritor, db_path):
    """56. Evento prescricao_emitida contém cnes_validacao no payload_json."""
    payload = {
        "cns_prescritor": "123456789012345",
        "nome_prescritor": "Dr. Teste",
        "cpf_paciente": "12345678901",
        "nome_paciente": "Paciente Teste",
        "tipo_emissao": "nova",
        "itens": [{"nome_medicamento": "IBUPROFENO", "concentracao": "400mg",
                   "quantidade": 6, "posologia": "1 comprimido 2x ao dia"}],
    }
    resp = prescritor.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    prescricao_id = resp.json()["id"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    evento = conn.execute(
        """SELECT payload_json FROM prescricao_eventos
           WHERE prescricao_id = ? AND tipo_evento = 'prescricao_emitida'""",
        (prescricao_id,),
    ).fetchone()
    conn.close()

    assert evento is not None
    ev = json.loads(evento["payload_json"])
    assert "cnes_validacao" in ev
    assert "nivel_validacao_cnes" in ev["cnes_validacao"]
    assert "snapshot_ref" in ev["cnes_validacao"]
    assert "divergencias" in ev["cnes_validacao"]


def test_emissao_nao_bloqueada_cns_ausente_cnes(prescritor):
    """57. Emissão aceita mesmo com CNS ausente do CNES (nivel nao_encontrado)."""
    payload = {
        "cns_prescritor": "777777777777777",
        "nome_prescritor": "Dr. Inexistente CNES",
        "cpf_paciente": "12345678901",
        "nome_paciente": "Paciente Teste",
        "tipo_emissao": "nova",
        "itens": [{"nome_medicamento": "IBUPROFENO", "concentracao": "400mg",
                   "quantidade": 6, "posologia": "1 comprimido 2x ao dia"}],
    }
    resp = prescritor.post("/prescricoes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["cnes_validacao"]["nivel_validacao_cnes"] == "nao_encontrado"
    assert body["cnes_validacao"]["cns_encontrado"] is False
