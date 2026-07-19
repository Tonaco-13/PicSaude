"""
test_atestados.py — emissão e ciclo do atestado (objeto sanitário monolítico).
Harness SQLite (prescritor/db_path do conftest).
"""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import warnings
import zlib

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")

import app.routers.atestados as at
import app.routers.prescritor as pcert
from app.domain.pdf_assinatura import pdf_tem_assinatura
from tests.fixtures.certificado_teste import gerar_certificado_teste


@pytest.fixture
def sem_demo(monkeypatch):
    monkeypatch.setattr(at, "PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr(pcert, "PICSAUDE_DEMO_MODE", False)
    yield


def _upload_cert(prescritor, cert):
    return prescritor.post(
        "/prescritor/certificado",
        files={"pfx_file": ("teste.pfx", cert.pfx_bytes, "application/x-pkcs12")},
        data={"senha": cert.senha},
    )


_BASE = {
    "cns_prescritor": "123456789012345",   # = token sub do RoleClient prescritor
    "nome_prescritor": "Dra. Atesta",
    "cpf_paciente": "12345678901",
    "nome_paciente": "Paciente Atesta",
    "finalidade": "Afastamento do trabalho",
    "municipio_emissao": "Recife",         # obrigatório: o CFM exige local e data
    "dias_afastamento": 3,
    "data_documento": "2026-06-23",
}


def _payload(**ov):
    return {**_BASE, **ov}


def _texto_pdf(pdf_bytes: bytes) -> str:
    """Texto visível de um PDF do ReportLab, sem dependência externa.

    Dois passos, ambos necessários:

    1. O ReportLab comprime cada content stream com ASCII85 + Flate. Sem
       desfazer isso, `b"ATESTADO ODONTOLÓGICO" in pdf` é SEMPRE falso e o teste
       passaria por vacuidade.
    2. Do stream inflado extrai só os literais de texto (operandos de `Tj`),
       unidos por espaço. Sem isso, a frase vem picada por operadores de fonte
       — `(...) Tj /F2 12 Tf (...)` — e uma asserção como "cuidados
       odontológicos" quebraria só porque o ReportLab trocou de fonte no meio
       ou mudou de linha. As asserções descrevem o documento, não o layout.

    Devolve latin-1 (o WinAnsi das fontes base); as asserções usam trechos ASCII
    para não depender do acento.
    """
    partes = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        dado = m.group(1).strip()
        try:
            inflado = zlib.decompress(base64.a85decode(dado, adobe=True))
        except Exception:
            continue          # stream não-textual (fonte embutida, imagem)
        for lit in re.finditer(rb"\((.*?)(?<!\\)\)\s*Tj", inflado, re.S):
            partes.append(lit.group(1).replace(rb"\)", b")").replace(rb"\(", b"("))
    return re.sub(r"\s+", " ", b" ".join(partes).decode("latin-1"))


def _pdf_de(prescritor, **ov) -> str:
    proto = prescritor.post("/atestados", json=_payload(**ov)).json()["protocolo"]
    r = prescritor.get(f"/atestados/{proto}/pdf")
    assert r.status_code == 200, r.text
    return _texto_pdf(r.content)


def _conn(db_path):
    c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
    return c


def _eventos(db_path, protocolo):
    with _conn(db_path) as c:
        rows = c.execute(
            """
            SELECT ae.tipo_evento FROM atestado_eventos ae
              JOIN atestados a ON a.id = ae.atestado_id
             WHERE a.protocolo = ? ORDER BY ae.id
            """,
            (protocolo,),
        ).fetchall()
    return [r["tipo_evento"] for r in rows]


class TestEmissaoDigital:

    def test_emite_e_retorna_protocolo(self, prescritor):
        r = prescritor.post("/atestados", json=_payload())
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["status"] == "emitido"
        assert d["finalidade"] == "Afastamento do trabalho"
        assert d["data_validade"] == "2026-06-26"   # 23 + 3 dias
        assert d["assinatura_hash"]

    def test_ledger_tem_emissao_e_custodia(self, prescritor, db_path):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        evs = _eventos(db_path, proto)
        assert "atestado_emitido" in evs
        assert "custodia_transferida" in evs

    def test_custodia_prescritor_para_paciente(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        r = prescritor.get(f"/atestados/{proto}/custodia")
        assert r.status_code == 200
        cust = r.json()["custodia"]
        assert len(cust) == 1
        assert cust[0]["de"] == "prescritor" and cust[0]["para"] == "paciente"

    def test_consulta_retorna_dados(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(codigo_cid="J11")).json()["protocolo"]
        d = prescritor.get(f"/atestados/{proto}").json()
        assert d["codigo_cid"] == "J11"
        assert d["nome_paciente"]

    def test_sem_dias_nao_tem_validade(self, prescritor):
        d = prescritor.post("/atestados", json=_payload(
            finalidade="Comparecimento", dias_afastamento=None)).json()
        assert d["dias_afastamento"] is None
        assert d["data_validade"] is None

    def test_finalidade_obrigatoria_422(self, prescritor):
        r = prescritor.post("/atestados", json=_payload(finalidade="  "))
        assert r.status_code == 422

    def test_cpf_sentinela_no_digital_422(self, prescritor):
        r = prescritor.post("/atestados", json=_payload(cpf_paciente="00000000000"))
        assert r.status_code == 422


class TestEmissaoFisica:

    def test_fisica_encerrada_localmente_sem_custodia(self, prescritor, db_path):
        r = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345",
            "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento",
        })
        assert r.status_code == 201, r.text
        proto = r.json()["protocolo"]
        assert r.json()["status"] == "encerrada_localmente"
        evs = _eventos(db_path, proto)
        assert evs == ["atestado_impresso", "encerrada_localmente"]
        # sem custódia no fluxo físico
        with _conn(db_path) as c:
            n = c.execute(
                "SELECT COUNT(*) n FROM atestado_custodia ac "
                "JOIN atestados a ON a.id = ac.atestado_id WHERE a.protocolo = ?",
                (proto,),
            ).fetchone()["n"]
        assert n == 0


class TestPdfEAssinatura:

    def test_get_pdf(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        r = prescritor.get(f"/atestados/{proto}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_assina_pdf_e_transiciona_para_assinado(self, prescritor, db_path, sem_demo):
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload_cert(prescritor, cert).status_code == 201
        r = prescritor.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": cert.senha})
        assert r.status_code == 200, r.text
        assert pdf_tem_assinatura(r.content)
        # status transicionou + evento no ledger
        assert prescritor.get(f"/atestados/{proto}").json()["status"] == "assinado"
        assert "atestado_assinado" in _eventos(db_path, proto)

    def test_pdf_assinado_sem_cert_422(self, prescritor, sem_demo):
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        r = prescritor.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": "x"})
        assert r.status_code == 422


class TestValidacaoPublica:

    def test_publico_neutro_nao_vaza_clinica(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(
            finalidade="Afastamento", codigo_cid="J11", indicacao_clinica="gripe")).json()["protocolo"]
        d = prescritor.get(f"/public/atestados/{proto}").json()
        # confirma existência/estado…
        assert d["protocolo"] == proto
        assert d["status"] == "emitido"
        assert d["assinado"] is False
        assert "vigente" in d              # vigência exposta só como booleano derivado
        # …sem JAMAIS vazar clínica/identidade
        blob = json.dumps(d).lower()
        for proibido in ("finalidade", "afastamento", "j11", "gripe", "cid",
                          "paciente", "cpf", "indicacao", "prescritor"):
            assert proibido not in blob, f"vazou: {proibido}"
        # Revisão #60: as datas NÃO podem aparecer — data_validade = data_documento
        # + dias_afastamento permitiria derivar os dias de afastamento (clínico).
        assert "data_documento" not in d and "data_validade" not in d
        assert "2026-06-23" not in blob and "2026-06-26" not in blob

    def test_publico_404(self, prescritor):
        assert prescritor.get("/public/atestados/inexistente").status_code == 404

    def test_publico_assinado_nao_vaza_datas(self, prescritor, sem_demo):
        """Revisão #60: nem no estado assinado o público expõe as datas/dias."""
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        cert = gerar_certificado_teste(cpf="12345678901")
        assert _upload_cert(prescritor, cert).status_code == 201
        assert prescritor.post(f"/atestados/{proto}/pdf-assinado",
                               json={"senha_pfx": cert.senha}).status_code == 200
        d = prescritor.get(f"/public/atestados/{proto}").json()
        assert d["status"] == "assinado" and d["assinado"] is True
        assert "vigente" in d
        assert "data_documento" not in d and "data_validade" not in d
        blob = json.dumps(d).lower()
        assert "2026-06-23" not in blob and "2026-06-26" not in blob


class TestRBACLeitura:
    """Revisão #60 — leitura autenticada: o paciente-titular acessa o próprio
    atestado (GET, /pdf, /custodia); outros papéis e não-titulares recebem 403."""

    def test_paciente_titular_le_atestado_pdf_custodia(self, prescritor, paciente):
        # fixture `paciente`: CPF 12345678901 == cpf_paciente do _BASE → é o titular
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        assert paciente.get(f"/atestados/{proto}").status_code == 200
        assert paciente.get(f"/atestados/{proto}/pdf").status_code == 200
        assert paciente.get(f"/atestados/{proto}/custodia").status_code == 200

    def test_outro_paciente_nao_titular_403(self, prescritor, outro_paciente):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert outro_paciente.get(path).status_code == 403, path

    def test_dispensador_sem_acesso_403(self, prescritor, dispensador):
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert dispensador.get(path).status_code == 403, path

    def test_prescritor_nao_autor_403(self, prescritor, _shared_client, sem_demo):
        from app.main import app
        from app.auth.dependencies import get_current_user
        proto = prescritor.post("/atestados", json=_payload(
            assinatura_modo="icp_brasil_local")).json()["protocolo"]
        # passa a ser um prescritor B (CNS distinto do autor)
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "prescritor", "sub": "999999999999999"}
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert _shared_client.get(path).status_code == 403, path
        # …e não pode assinar o atestado de outro (owner-check antes do certificado)
        r = _shared_client.post(f"/atestados/{proto}/pdf-assinado", json={"senha_pfx": "x"})
        assert r.status_code == 403, r.text

    def test_paciente_sentinela_nunca_e_titular_403(self, prescritor, _shared_client):
        """O CPF sentinela (00000000000, fluxo físico não identificado) nunca é
        titular — mesmo coincidindo com o cpf_paciente do atestado físico."""
        from app.main import app
        from app.auth.dependencies import get_current_user
        proto = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345", "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento",
        }).json()["protocolo"]
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "paciente", "sub": "00000000000"}
        for path in (f"/atestados/{proto}", f"/atestados/{proto}/pdf",
                     f"/atestados/{proto}/custodia"):
            assert _shared_client.get(path).status_code == 403, path


# ---------------------------------------------------------------------------
# TICKET-ATESTADO-CONFORMIDADE — pronto para imprimir e assinar (CFM/CFO)
# ---------------------------------------------------------------------------

class TestMunicipioEmissao:
    """O CFM exige LOCAL e data. A data já existia; o local passa a ser exigido."""

    def test_sem_municipio_422(self, prescritor):
        payload = _payload()
        del payload["municipio_emissao"]
        assert prescritor.post("/atestados", json=payload).status_code == 422

    def test_municipio_em_branco_422(self, prescritor):
        assert prescritor.post(
            "/atestados", json=_payload(municipio_emissao="   ")).status_code == 422

    def test_fecho_local_e_data_no_pdf(self, prescritor):
        texto = _pdf_de(prescritor, municipio_emissao="Recife", data_documento="2026-07-18")
        assert "Recife, 18/07/2026" in texto

    def test_fecho_vem_acima_da_area_de_assinatura(self, prescritor):
        texto = _pdf_de(prescritor, municipio_emissao="Olinda", data_documento="2026-07-18")
        # A linha de assinatura é a régua de underscores do bloco de assinatura.
        assert texto.index("Olinda, 18/07/2026") < texto.index("______")

    def test_municipio_devolvido_na_consulta(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(
            municipio_emissao="Caruaru")).json()["protocolo"]
        assert prescritor.get(f"/atestados/{proto}").json()["municipio_emissao"] == "Caruaru"


class TestConselhoNoDocumento:
    """Título, adjetivo e sigla saem da fonte única — o PDF não hardcoda nada."""

    def test_cfo_vira_atestado_odontologico(self, prescritor):
        texto = _pdf_de(prescritor, conselho="CFO", uf_registro="PE",
                        registro_profissional="1234")
        assert "ATESTADO ODONTOL" in texto
        assert "ATESTADO M" not in texto.split("PACIENTE")[0]
        assert "CRO-PE 1234" in texto

    def test_cfo_usa_adjetivo_odontologico_no_corpo(self, prescritor):
        texto = _pdf_de(prescritor, conselho="CFO", uf_registro="PE",
                        registro_profissional="1234", dias_afastamento=3)
        assert "cuidados odontol" in texto

    def test_cfm_vira_atestado_medico(self, prescritor):
        texto = _pdf_de(prescritor, conselho="CFM", uf_registro="PE",
                        registro_profissional="12345")
        assert "ATESTADO M" in texto
        assert "ATESTADO ODONTOL" not in texto
        assert "CRM-PE 12345" in texto
        assert "cuidados m" in texto

    def test_legado_sem_conselho_mantem_atestado_medico(self, prescritor):
        # conselho NULL = atestado anterior à migração: comportamento inalterado.
        texto = _pdf_de(prescritor, registro_profissional="CRM-PE 999")
        assert "ATESTADO M" in texto
        assert "ATESTADO ODONTOL" not in texto
        assert "CRM-PE 999" in texto      # texto livre legado sai como está

    def test_conselho_invalido_422(self, prescritor):
        assert prescritor.post(
            "/atestados", json=_payload(conselho="COFEN")).status_code == 422

    def test_uf_registro_invalida_422(self, prescritor):
        assert prescritor.post(
            "/atestados", json=_payload(uf_registro="PERNAMBUCO")).status_code == 422

    def test_conselho_normalizado_para_maiuscula(self, prescritor):
        proto = prescritor.post("/atestados", json=_payload(
            conselho="cfo", uf_registro="pe", registro_profissional="1")).json()["protocolo"]
        d = prescritor.get(f"/atestados/{proto}").json()
        assert d["conselho"] == "CFO" and d["uf_registro"] == "PE"


class TestEnfaseRegistroAntesDoCns:
    """Quem identifica o profissional na norma é o CRM/CRO+UF, não o CNS."""

    def test_registro_vem_antes_do_cns(self, prescritor):
        texto = _pdf_de(prescritor, conselho="CFM", uf_registro="PE",
                        registro_profissional="12345")
        assert "CRM-PE 12345" in texto
        assert texto.index("CRM-PE 12345") < texto.index("CNS ")

    def test_sem_registro_a_linha_nao_quebra(self, prescritor):
        texto = _pdf_de(prescritor, registro_profissional=None)
        assert "CNS " in texto


class TestHoraComparecimento:
    """Horário é SEMPRE opcional — nunca condicionado à finalidade."""

    def test_comparecimento_com_periodo(self, prescritor):
        texto = _pdf_de(prescritor, finalidade="Comparecimento", dias_afastamento=None,
                        hora_inicio="08:00", hora_fim="12:00")
        assert "no per" in texto and "08:00" in texto and "12:00" in texto

    def test_comparecimento_sem_hora_mantem_frase_atual(self, prescritor):
        texto = _pdf_de(prescritor, finalidade="Comparecimento", dias_afastamento=None)
        assert "compareceu a atendimento" in texto
        assert "no per" not in texto

    def test_apenas_hora_inicio(self, prescritor):
        texto = _pdf_de(prescritor, finalidade="Comparecimento", dias_afastamento=None,
                        hora_inicio="08:00")
        assert "a partir das 08:00" in texto

    def test_apenas_hora_fim(self, prescritor):
        texto = _pdf_de(prescritor, finalidade="Comparecimento", dias_afastamento=None,
                        hora_fim="12:00")
        assert "12:00" in texto

    def test_hora_declarada_nao_some_no_afastamento(self, prescritor):
        # Dado digitado que não aparece no documento é perda silenciosa.
        texto = _pdf_de(prescritor, dias_afastamento=3, hora_inicio="08:00", hora_fim="09:30")
        assert "08:00" in texto and "09:30" in texto

    def test_hora_invalida_422(self, prescritor):
        for ruim in ("8:00", "25:00", "08:60", "0800"):
            assert prescritor.post(
                "/atestados", json=_payload(hora_inicio=ruim)).status_code == 422, ruim

    def test_hora_nao_e_exigida_por_finalidade(self, prescritor):
        # "Comparecimento" não torna a hora obrigatória (finalidade é texto livre).
        assert prescritor.post("/atestados", json=_payload(
            finalidade="Comparecimento", dias_afastamento=None)).status_code == 201


class TestHashCobreConteudoNovo:
    """O hash é a impressão digital do que está IMPRESSO no documento."""

    def test_municipios_diferentes_geram_hashes_diferentes(self, prescritor):
        a = prescritor.post("/atestados", json=_payload(
            municipio_emissao="Recife")).json()["assinatura_hash"]
        b = prescritor.post("/atestados", json=_payload(
            municipio_emissao="Olinda")).json()["assinatura_hash"]
        assert a != b

    def test_conselhos_diferentes_geram_hashes_diferentes(self, prescritor):
        a = prescritor.post("/atestados", json=_payload(conselho="CFM")).json()["assinatura_hash"]
        b = prescritor.post("/atestados", json=_payload(conselho="CFO")).json()["assinatura_hash"]
        assert a != b


class TestFisicaAceitaCamposNovos:
    """Física é fire-and-forget: município NÃO é 422 aqui (a tela é que exige)."""

    def test_fisica_sem_municipio_ainda_registra(self, prescritor):
        r = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345", "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento",
        })
        assert r.status_code == 201, r.text

    def test_fisica_persiste_conselho_e_municipio(self, prescritor, db_path):
        proto = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345", "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento", "municipio_emissao": "Recife",
            "conselho": "CFO", "uf_registro": "PE", "registro_profissional": "1234",
        }).json()["protocolo"]
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT conselho, uf_registro, municipio_emissao FROM atestados WHERE protocolo = ?",
                (proto,),
            ).fetchone()
        assert row["conselho"] == "CFO"
        assert row["uf_registro"] == "PE"
        assert row["municipio_emissao"] == "Recife"


class TestCatalogoConselhosNaConfigPublica:
    """A tela pergunta ao domínio em vez de repetir rótulos no HTML."""

    def test_config_public_serve_o_catalogo(self, _shared_client):
        cat = _shared_client.get("/config/public").json()["conselhos_profissionais"]
        assert [c["id_conselho"] for c in cat] == ["CFM", "CFO"]
        assert {c["sigla_registro"] for c in cat} == {"CRM", "CRO"}


class TestCarteiraDoCidadao:
    """TICKET-ATESTADO-CARTEIRA-CIDADAO — GET /paciente/atestados.

    O atestado já era ENTREGUE ao paciente (custódia transferida na emissão); o
    que faltava era ele CONSEGUIR VER. Sem listagem, o cidadão precisaria saber
    o UUID de cor.

    Nota sobre as datas: o `_BASE` do módulo usa `data_documento` fixo em
    2026-06-23, que já venceu — ele foi escrito para os testes de PDF, onde a
    data é literal esperado. Os casos de VIGÊNCIA aqui emitem com a data de hoje
    (`_hoje_payload`), senão testariam o ramo do histórico sem querer.
    """

    @staticmethod
    def _hoje_payload(**ov):
        from datetime import date
        return _payload(data_documento=date.today().isoformat(), **ov)

    def test_atestado_aparece_sem_acao_extra_do_prescritor(self, prescritor, paciente):
        """Emitir basta. Não há "enviar ao paciente" — o atestado É do paciente.

        Este teste é a prova de que a custódia na emissão já bastava: entre o
        POST e a carteira não há nenhuma chamada intermediária.
        """
        proto = prescritor.post(
            "/atestados", json=self._hoje_payload()).json()["protocolo"]

        vigentes = paciente.get("/paciente/atestados").json()["vigentes"]

        assert proto in [a["protocolo"] for a in vigentes]

    def test_nao_ve_atestado_de_outro_cpf(self, prescritor, outro_paciente):
        """Ownership pelo TOKEN. O molde dos outros três objetos da carteira."""
        proto = prescritor.post("/atestados", json=_payload()).json()["protocolo"]

        dados = outro_paciente.get("/paciente/atestados").json()
        protocolos = [a["protocolo"] for a in dados["vigentes"] + dados["historico"]]

        assert proto not in protocolos

    def test_titulo_vem_do_backend(self, prescritor, paciente):
        """O rótulo nasce da fonte única (conselho_profissional), não da tela.

        Sem isto, o HTML teria que bifurcar entre "ATESTADO MÉDICO" e "ATESTADO
        ODONTOLÓGICO" — dois lugares que divergiriam.
        """
        prescritor.post("/atestados", json=self._hoje_payload(
            conselho="CFO", uf_registro="PE", registro_profissional="1234"))

        odonto = [
            a for a in paciente.get("/paciente/atestados").json()["vigentes"]
            if a["conselho"] == "CFO"
        ]
        assert odonto, "atestado odontológico não chegou à carteira"
        assert odonto[0]["titulo_documento"] == "ATESTADO ODONTOLÓGICO"
        assert odonto[0]["registro_profissional"] == "CRO-PE 1234"

    def test_sem_dias_de_afastamento_o_campo_vem_nulo(self, prescritor, paciente):
        """Ausência é informação: nem todo atestado afasta (ex.: comparecimento).

        O backend devolve None — não 0, que a tela leria como "afastou zero dia".
        """
        proto = prescritor.post("/atestados", json=self._hoje_payload(
            finalidade="Comparecimento", dias_afastamento=None)).json()["protocolo"]

        alvo = next(
            a for a in paciente.get("/paciente/atestados").json()["vigentes"]
            if a["protocolo"] == proto
        )
        assert alvo["dias_afastamento"] is None
        assert alvo["data_validade"] is None

    def test_listagem_nao_expoe_diagnostico(self, prescritor, paciente):
        """CID e indicação clínica NÃO entram na carteira (CFM art. 3º).

        O CID é opcional e só entra no documento com anuência do paciente. Numa
        LISTA viraria exibição incidental de diagnóstico: o titular abre a
        carteira para ver um comprovante e leva o diagnóstico na tela junto. O
        PDF já o carrega quando declarado — abrir o PDF é escolha deliberada.
        """
        prescritor.post("/atestados", json=self._hoje_payload(
            codigo_cid="J11", indicacao_clinica="Sintomas gripais"))

        blob = json.dumps(paciente.get("/paciente/atestados").json()).lower()

        assert "j11" not in blob
        assert "codigo_cid" not in blob and "indicacao_clinica" not in blob
        assert "sintomas gripais" not in blob

    def test_atestado_fisico_fora_da_carteira(self, prescritor, paciente):
        """Emissão física não entra no ciclo digital nem gera custódia (§6)."""
        proto = prescritor.post("/atestados/fisica", json={
            "cns_prescritor": "123456789012345", "nome_prescritor": "Dra. Atesta",
            "finalidade": "Comparecimento", "cpf_paciente": "12345678901",
        }).json()["protocolo"]

        dados = paciente.get("/paciente/atestados").json()
        protocolos = [a["protocolo"] for a in dados["vigentes"] + dados["historico"]]

        assert proto not in protocolos

    def test_vencido_por_data_cai_no_historico(self, prescritor, paciente):
        """Atestado com validade vencida não é "vigente", mesmo sem job que o
        carimbe como expirado — senão a tela mentiria."""
        proto = prescritor.post("/atestados", json=_payload(
            data_documento="2020-01-10", dias_afastamento=3)).json()["protocolo"]

        dados = paciente.get("/paciente/atestados").json()

        assert proto in [a["protocolo"] for a in dados["historico"]]
        assert proto not in [a["protocolo"] for a in dados["vigentes"]]

    def test_ordem_estavel(self, prescritor, paciente):
        """ORDER BY determinístico — duas leituras seguidas dão a mesma lista."""
        for _ in range(3):
            prescritor.post("/atestados", json=self._hoje_payload())

        primeira = [a["protocolo"] for a in paciente.get("/paciente/atestados").json()["vigentes"]]
        segunda  = [a["protocolo"] for a in paciente.get("/paciente/atestados").json()["vigentes"]]

        assert primeira == segunda

    def test_exige_papel_paciente(self, prescritor, dispensador):
        assert prescritor.get("/paciente/atestados").status_code == 403
        assert dispensador.get("/paciente/atestados").status_code == 403
