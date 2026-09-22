"""
test_posologia_por_condicao.py — a chave composta `(ativo, CID)` (ENG-019).

O DEFEITO QUE ESTAS GUARDAS FECHAM
----------------------------------
O índice de `carregar_posologias` era `dict[ativo → Posologia]`. Duas rows do
mesmo princípio ativo com CIDs diferentes colidiam e **a última do CSV vencia
em silêncio** — a dose de um protocolo passava a ser servida no outro, sem
erro, sem log, sem rastro. Carvedilol começa em 3,125 mg 2x/dia na
insuficiência cardíaca; servir isso como dose de hipertensão é erro clínico
calado, que é o pior tipo, porque não pergunta nada a ninguém.

A guarda mais importante daqui é a do AC1: **reintroduzir `idx[ativo_k] = ...`
tem de reprovar**. Ela não olha a implementação; olha o efeito — duas rows
entram, duas sobrevivem, e cada uma responde pela sua condição. Um índice
chaveado só por ativo perde uma das duas e a asserção cai.

`tests/unit/test_semaforo_flip_j44_i50.py` guarda o mesmo invariante sobre o
CSV DE PRODUÇÃO (o verde-após-o-fix da guarda fail-loud de 13/09). Aqui o dado
é sintético, para exercitar os ramos que o CSV real não tem — colisão sem CID,
cadeia com subcategoria, row sem CID declarado.
"""
from __future__ import annotations

import logging

import pytest

from pathlib import Path

from app.domain.posologia_sugerida import (
    agrupar_por_ativo,
    carregar_posologias,
    sugerir,
)

_PRESCRITOR_HTML = Path(__file__).resolve().parents[3] / "prescritor.html"

_CABECALHO = (
    "principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,"
    "status_curadoria,validado_por,versao,observacao\n"
)


def _csv(tmp_path, linhas: str) -> str:
    p = tmp_path / "posologia.csv"
    p.write_text(_CABECALHO + linhas, encoding="utf-8")
    return str(p)


@pytest.fixture
def indice(monkeypatch):
    """Instala um CSV sintético como índice vigente e limpa depois.

    Troca `_CACHE` direto (é assim que a suíte já fazia) e zera a vista por
    ativo: uma vista velha responderia "unívoco" sobre um CSV que mudou.
    """
    import app.domain.posologia_sugerida as ps

    def _instalar(caminho: str):
        monkeypatch.setattr(ps, "_CACHE", carregar_posologias(caminho))
        monkeypatch.setattr(ps, "_CACHE_POR_ATIVO", None)
        monkeypatch.setattr(ps, "_ULTIMO_IDX", None)
        return ps._CACHE

    return _instalar


# ===========================================================================
# AC1 — colisão: duas sugestões vivas, nenhuma sobrescrita silenciosa
# ===========================================================================

_COLISAO = (
    "losartana,Tomar 50 mg 1x/dia,Hipertensão arterial,I10,RENAME,validado,Dr,v1,has\n"
    "losartana,Inicial 25 mg 1x/dia; alvo 150 mg/dia,Insuficiência cardíaca,I50,PCDT,validado,Dr,v1,ic\n"
)


def test_ac1_duas_rows_do_mesmo_ativo_sobrevivem(tmp_path, indice):
    idx = indice(_csv(tmp_path, _COLISAO))

    assert len(idx) == 2, (
        "uma das duas rows foi engolida no carregamento — é o last-wins de "
        "volta, e com ele o erro clínico calado"
    )
    assert ("losartana", "I10") in idx
    assert ("losartana", "I50") in idx


def test_ac1_cada_cid_recebe_a_sua_dose(tmp_path, indice):
    indice(_csv(tmp_path, _COLISAO))

    has = sugerir("Losartana Potássica", "I10")
    ic = sugerir("Losartana Potássica", "I50")

    assert has is not None and ic is not None
    assert has.posologia.startswith("Tomar 50 mg")
    assert ic.posologia.startswith("Inicial 25 mg")
    assert has.posologia != ic.posologia, "as duas condições receberam a MESMA dose"
    assert has.codigo_cid == "I10" and ic.codigo_cid == "I50"


def test_ac1_a_ordem_das_linhas_nao_decide_a_dose(tmp_path, indice):
    """O coração do defeito: era a POSIÇÃO no arquivo que escolhia a dose."""
    linhas = _COLISAO.splitlines(keepends=True)
    indice(_csv(tmp_path, "".join(linhas)))
    direta = (sugerir("losartana", "I10").posologia, sugerir("losartana", "I50").posologia)

    indice(_csv(tmp_path, "".join(reversed(linhas))))
    invertida = (sugerir("losartana", "I10").posologia, sugerir("losartana", "I50").posologia)

    assert direta == invertida, (
        "inverter a ordem das linhas do CSV mudou a dose servida — a chave não "
        "está discriminando por condição"
    )


# ===========================================================================
# AC2 — sem CID: unívoco serve (retrocompat); colisão cala (+ log)
# ===========================================================================

def test_ac2_sem_cid_ativo_univoco_serve(tmp_path, indice):
    """Retrocompat: quem só tem uma dose curada continua respondendo sem CID."""
    indice(_csv(
        tmp_path,
        "nitrofurantoina,Tomar 100 mg 6/6h,ITU,N39.0,RENAME,validado,Dr,v1,\n",
    ))
    p = sugerir("nitrofurantoína")
    assert p is not None and p.posologia.startswith("Tomar 100 mg")


def test_ac2_sem_cid_colisao_cala(tmp_path, indice):
    indice(_csv(tmp_path, _COLISAO))
    assert sugerir("losartana") is None, (
        "sem CID e com duas doses curadas, servir qualquer uma delas é deixar "
        "a ordem do arquivo escolher a dose do paciente"
    )


def test_ac2_o_silencio_por_colisao_deixa_log(tmp_path, indice, caplog):
    """Silêncio SEM log seria só um sumiço — o operador precisa poder saber."""
    indice(_csv(tmp_path, _COLISAO))
    with caplog.at_level(logging.INFO, logger="app.domain.posologia_sugerida"):
        assert sugerir("losartana") is None
    texto = caplog.text   # já renderizado (msg % args), que é o que o operador lê
    assert "losartana" in texto, f"nenhum log da colisão: {texto!r}"
    assert "I10" in texto and "I50" in texto, (
        "o log tem de nomear as condições em disputa; sem elas ninguém "
        f"diagnostica nada: {texto!r}"
    )


def test_ac2_sem_cid_e_sem_row_continua_none(tmp_path, indice):
    indice(_csv(tmp_path, ""))
    assert sugerir("amoxicilina") is None
    assert sugerir("") is None
    assert sugerir(None) is None


# ===========================================================================
# AC3 — hierarquia: a subcategoria cai na categoria
# ===========================================================================

def test_ac3_subcategoria_cai_na_categoria(tmp_path, indice):
    indice(_csv(
        tmp_path,
        "clonazepam,2 a 4 mg/dia,Transtornos ansiosos,F41,AMB 2008,validado,Dr,v1,\n",
    ))
    p = sugerir("clonazepam", "F41.0")   # pânico, subcategoria de F41
    assert p is not None and p.codigo_cid == "F41"


def test_ac3_a_subcategoria_especifica_tem_prioridade(tmp_path, indice):
    """Havendo row da subcategoria, ela ganha da categoria — mais específico
    primeiro, igual ao semáforo."""
    indice(_csv(
        tmp_path,
        "clonazepam,dose da categoria,Transtornos ansiosos,F41,AMB,validado,Dr,v1,\n"
        "clonazepam,dose do pânico,Transtorno de pânico,F41.0,AMB,validado,Dr,v1,\n",
    ))
    assert sugerir("clonazepam", "F41.0").posologia == "dose do pânico"
    assert sugerir("clonazepam", "F41").posologia == "dose da categoria"


def test_ac3_cid_que_nao_casa_degrada_para_o_silencio(tmp_path, indice):
    """Com CID na mão, NÃO existe fallback para a dose de outra condição —
    nem quando a substância é unívoca. Emprestar dose entre protocolos é o
    defeito, não a conveniência."""
    indice(_csv(
        tmp_path,
        "nitrofurantoina,Tomar 100 mg 6/6h,ITU,N39.0,RENAME,validado,Dr,v1,\n",
    ))
    assert sugerir("nitrofurantoína", "N39.0") is not None
    assert sugerir("nitrofurantoína", "I10") is None


# ===========================================================================
# Bordas do carregamento
# ===========================================================================

def test_row_sem_cid_entra_e_so_e_alcancavel_pelo_univoco(tmp_path, indice):
    """Posologia sem condição declarada não é descartada em silêncio — mas
    também não responde a um CID, porque não diz a qual condição pertence."""
    idx = indice(_csv(
        tmp_path,
        "amoxicilina,Tomar 500 mg 8/8h,,,RENAME,validado,Dr,v1,\n",
    ))
    assert ("amoxicilina", "") in idx
    assert sugerir("amoxicilina") is not None          # unívoca → serve
    assert sugerir("amoxicilina", "J01") is None       # não finge pertencer a J01


def test_agrupar_por_ativo_responde_univocidade(tmp_path):
    idx = carregar_posologias(_csv(tmp_path, _COLISAO +
        "nitrofurantoina,Tomar 100 mg 6/6h,ITU,N39.0,RENAME,validado,Dr,v1,\n"))
    por_ativo = agrupar_por_ativo(idx)
    assert len(por_ativo["losartana"]) == 2
    assert len(por_ativo["nitrofurantoina"]) == 1


def test_rascunho_continua_dormente_mesmo_com_chave_composta(tmp_path, indice):
    """Linha vermelha: a chave mudou, a regra de curadoria não."""
    idx = indice(_csv(
        tmp_path,
        "losartana,Tomar 50 mg 1x/dia,HAS,I10,RENAME,validado,Dr,v1,\n"
        "losartana,dose nao assinada,IC,I50,PCDT,rascunho,,v0,\n",
    ))
    assert ("losartana", "I10") in idx
    assert ("losartana", "I50") not in idx
    assert sugerir("losartana", "I50") is None
    assert sugerir("losartana") is not None   # com o rascunho fora, virou unívoca


# ===========================================================================
# AC6 — proveniência: a ficha carrega o CID casado
# ===========================================================================

from app.auth.dependencies import get_current_user   # noqa: E402
from app.main import app                              # noqa: E402
from fastapi.testclient import TestClient             # noqa: E402


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "123456789012345", "role": "prescritor",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ac6_a_resposta_diz_qual_condicao_fundamentou_a_dose(
    client, monkeypatch, tmp_path, indice
):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    indice(_csv(tmp_path, _COLISAO))

    r = client.post(
        "/ia/posologia/sugerir",
        json={"principio_ativo": "Losartana Potássica", "codigo_cid": "I50"},
    )
    d = r.json()
    assert d["disponivel"] is True
    assert d["codigo_cid"] == "I50", (
        "sem o CID casado na resposta, 'condicao' é rótulo sem chave e o "
        "prescritor não confere de qual protocolo veio a dose"
    )
    assert d["condicao"] == "Insuficiência cardíaca"
    assert d["posologia"].startswith("Inicial 25 mg")


def test_ac6_endpoint_sem_cid_em_colisao_nao_oferece_nada(
    client, monkeypatch, tmp_path, indice
):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    indice(_csv(tmp_path, _COLISAO))

    r = client.post("/ia/posologia/sugerir", json={"principio_ativo": "losartana"})
    assert r.json() == {"disponivel": False}


def test_ac6_endpoint_aceita_payload_antigo_sem_codigo_cid(
    client, monkeypatch, tmp_path, indice
):
    """Retrocompat de CONTRATO: o campo é opcional, o cliente velho não quebra."""
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    indice(_csv(
        tmp_path,
        "nitrofurantoina,Tomar 100 mg 6/6h,ITU,N39.0,RENAME,validado,Dr,v1,\n",
    ))
    r = client.post("/ia/posologia/sugerir", json={"principio_ativo": "nitrofurantoína"})
    d = r.json()
    assert d["disponivel"] is True and d["codigo_cid"] == "N39.0"


# ===========================================================================
# AC4 — o dado curado que voltou, conferido contra a fonte
# ===========================================================================

class TestRowsQueVoltaram:
    """As nove exiladas de 13/09 e as doses de F41 — pelo CSV de produção.

    Não repete as doses aqui (seria uma segunda cópia do dado curado, livre
    para divergir da primeira — a mesma classe de defeito que o ticket fecha).
    Verifica a ESTRUTURA: o par existe, é servido pelo CID certo, e não é o
    mesmo texto do protocolo vizinho.
    """

    @pytest.fixture(autouse=True)
    def _csv_de_producao(self, monkeypatch):
        import app.domain.posologia_sugerida as ps
        monkeypatch.setattr(ps, "_CACHE", None)
        monkeypatch.setattr(ps, "_CACHE_POR_ATIVO", None)
        monkeypatch.setattr(ps, "_ULTIMO_IDX", None)

    @pytest.mark.parametrize(
        "ativo,cid_novo,cid_vizinho",
        [
            ("losartana", "I50", "I10"),
            ("enalapril", "I50", "I10"),
            ("captopril", "I50", "I10"),
            ("hidroclorotiazida", "I50", "I10"),
            ("dapagliflozina", "I50", "E11"),
            ("salbutamol", "J44", "J45"),
            ("budesonida", "J44", "J45"),
            ("prednisona", "J44", "J45"),
        ],
    )
    def test_a_row_exilada_voltou_e_nao_pisa_na_vizinha(self, ativo, cid_novo, cid_vizinho):
        nova = sugerir(ativo, cid_novo)
        vizinha = sugerir(ativo, cid_vizinho)
        assert nova is not None, f"({ativo}, {cid_novo}) não voltou ao CSV"
        assert vizinha is not None, f"({ativo}, {cid_vizinho}) sumiu — foi sobrescrita"
        assert nova.codigo_cid == cid_novo and vizinha.codigo_cid == cid_vizinho
        assert nova.posologia != vizinha.posologia, (
            f"'{ativo}' tem o MESMO texto em {cid_novo} e {cid_vizinho} — se as "
            "doses fossem mesmo iguais, não haveria colisão a resolver"
        )

    @pytest.mark.parametrize("ativo", ["clonazepam", "clomipramina"])
    def test_a_dose_de_f41_entrou_com_proveniencia(self, ativo):
        p = sugerir(ativo, "F41")
        assert p is not None, f"{ativo} não entrou em F41"
        assert p.codigo_cid == "F41"
        assert "AMB" in p.fonte and "p. 9" in p.fonte, (
            f"a dose de {ativo} tem de citar a página do algoritmo que a "
            f"levantou: {p.fonte!r}"
        )
        assert p.validado_por, "dose servida sem responsável de validação"

    def test_formoterol_budesonida_nao_empresta_a_dose_da_asma_para_a_dpoc(self):
        """A nona row NÃO voltou — e é exatamente por isso que esta guarda existe.

        O PCDT DPOC 2025 lista a associação entre os medicamentos (p. 19) mas
        **não traz esquema de administração para LABA+ICS no Quadro 6**: o
        Protocolo diz que a combinação não é opção preferencial na DPOC. Sem
        dose na fonte, não se escreve row — "não se inventa row" é a regra da
        casa, e valeria pouco se cedesse justamente para fechar uma contagem.

        O que importa clinicamente é que o silêncio seja silêncio: a dose de
        ASMA não pode vazar para a DPOC. Com a chave composta, não vaza.
        """
        assert sugerir("formoterol + budesonida", "J45") is not None
        assert sugerir("formoterol + budesonida", "J44") is None


# ===========================================================================
# A última milha — o CID sai da tela e chega ao motor
# ===========================================================================

class TestATelaLevaOCid:
    """Guardas estáticas do `prescritor.html`.

    Ficam AQUI, junto dos ACs do motor, e não num arquivo de frontend, porque
    o que elas vigiam é a mesma regra: *a dose é da condição*. Um motor que
    casa por `(ativo, CID)` e uma tela que não manda o CID é um conserto que
    não chega ao consultório — cada peça correta isolada, e a circulação com
    atrito, que é o defeito que a Regra Zero nomeia.

    Estáticas porque o caminho é de rede + flag (`PICSAUDE_DECISAO_CLINICA`)
    e depende do typeahead da IA; um smoke de navegador para isso exigiria
    encenar a busca de fármaco inteira para provar uma linha de payload.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def html() -> str:
        return _PRESCRITOR_HTML.read_text(encoding="utf-8")

    def test_a_requisicao_de_posologia_leva_o_codigo_cid(self, html):
        trecho = html[html.index("/ia/posologia/sugerir"):][:600]
        assert "codigo_cid" in trecho, (
            "o POST /ia/posologia/sugerir voltou a ir sem o CID — o motor "
            "então só responde quando a substância é unívoca, e toda "
            "substância compartilhada entre protocolos vira silêncio na tela"
        )
        assert "_cidPrimarioDaPrescricao()" in trecho

    def test_o_cid_primario_tem_um_leitor_so(self, html):
        """AC6 do ENG-018 ecoado aqui: a fonte é o hidden canônico — e é UMA.

        Três lugares perguntam "qual é o CID desta prescrição?": o payload da
        emissão, o semáforo e a sugestão de posologia. Se cada um decompuser o
        hidden por conta própria, basta a regra do primário mudar num deles
        para o sinal e a dose passarem a falar de CIDs diferentes — divergência
        silenciosa, a mesma espécie do defeito que este ticket fecha, só que
        na tela.
        """
        import re as _re

        assert html.count("function _cidPrimarioDaPrescricao()") == 1

        # Ninguém mais extrai o primário do hidden da PRESCRIÇÃO à mão. (O
        # atestado tem hidden próprio, `atestado-cid`, e não entra nesta conta.)
        manuais = [
            m.start()
            for m in _re.finditer(r"prescricao-cid-escolhido", html)
            if "[0]" in html[m.start():m.start() + 260]
        ]
        assert len(manuais) == 1, (
            f"a extração do CID primário aparece em {len(manuais)} lugares; "
            "deve morar só dentro de `_cidPrimarioDaPrescricao`"
        )
        # ...e esse único lugar é o próprio helper.
        helper = html.index("function _cidPrimarioDaPrescricao()")
        assert helper < manuais[0] < helper + 400

    def test_escolher_o_cid_depois_do_farmaco_ainda_sugere(self, html):
        """A ordem real do consultório: fármaco primeiro, CID depois.

        Sem isto, a substância compartilhada recebe o silêncio correto do
        motor no momento da escolha e NUNCA mais é perguntada — o campo fica
        vazio para sempre e o ganho do ticket morre na última milha.
        """
        assert "function _resugerirPosologias()" in html
        marca = html.index("if (hiddenId === 'prescricao-cid-escolhido')")
        assert "_resugerirPosologias();" in html[marca:marca + 400], (
            "mudar o CID da prescrição não re-tenta a posologia"
        )
