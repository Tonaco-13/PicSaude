"""
test_caneta_dos_8.py — a caneta dos 8 (ENG-030): 7 pares + a US morfológica.

Caneta do assinante, 29/09/2026, verbatim: **"Hemograma casa com o COMPLETO ·
Glicose do jejum · T4 por dosagem · TC crânio confirma · RM lombossacra ·
Urina pelo EAS · Parasitológico ovos e cistos · US morfológica solta, chave
honesta"**.

O QUE ESTE ARQUIVO PROVA
------------------------
1. Os **7 pares** entraram exatamente como canetados, e a `fonte` de cada um
   registra que foi ESCOLHA, não automatismo — a distinção importa: nos 26 do
   ENG-029 a fonte apontava um caminho só; aqui apontava vários, e alguém
   assinou qual.
2. A **US morfológica** virou três registros honestos onde havia um híbrido.
3. A guarda **par-cruzado** é regra geral: par que o mapa desmente não casa,
   e par que o mapa endossa continua casando (o teste-par do §5.3 — sem ele,
   a guarda nova poderia engolir os 29 legítimos e ninguém veria).

POR QUE ESTES SETE PRECISARAM DE CANETA
----------------------------------------
Porque o mapa oficial oferece MAIS DE UM SIGTAP para o mesmo TUSS, e a
ambiguidade é semântica de verdade: o TUSS fundiu, na terminologia da saúde
suplementar, coisas que o SUS publica separadas. Glicose no soro e no líquido
sinovial são um código TUSS só e dois SIGTAP. Escolher entre eles é dizer
*qual exame o registro é* — curadoria, não engenharia.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.ai import tuss_base

_RAIZ = Path(__file__).resolve().parents[3]
_SIGTAP = _RAIZ / "data" / "sigtap_exames.csv"


def _base() -> list[dict]:
    return tuss_base._construir_base()


def _por_tuss() -> dict[str, dict]:
    return {r["codigo_tuss"]: r for r in _base() if r.get("codigo_tuss")}


# ---------------------------------------------------------------------------
# §5.1 — o fingerprint dos 8
# ---------------------------------------------------------------------------

class TestOsSetePares:

    CANETA = {
        "40304361": ("0202020380", "hemograma completo"),
        "40302040": ("0202010473", "glicose de jejum"),
        "40316491": ("0202060381", "T4 livre por dosagem"),
        "41001010": ("0206010079", "TC crânio (confirmação)"),
        "41101227": ("0207010048", "RM lombossacra"),
        "40311210": ("0202050017", "urina tipo I pelo EAS"),
        "40303110": ("0202040127", "parasitológico: ovos e cistos"),
    }

    def test_os_sete_pares_sao_exatamente_os_canetados(self):
        por_tuss = _por_tuss()
        erros = []
        for tuss, (sigtap, rot) in self.CANETA.items():
            reg = por_tuss.get(tuss)
            if reg is None:
                erros.append(f"{rot}: o TUSS {tuss} sumiu da base")
            elif reg.get("codigo_sigtap") != sigtap:
                erros.append(f"{rot}: esperado {sigtap}, obtido {reg.get('codigo_sigtap')}")
        assert not erros, erros

    def test_a_tabela_da_caneta_esta_declarada_no_codigo(self):
        """Por VALOR, com o fundamento de cada escolha citado da fonte — é o
        que separa uma decisão datada de uma regra que alguém inferiu depois.
        """
        assert set(tuss_base._CANETA_SIGTAP) == set(self.CANETA)
        for tuss, (sigtap, fundamento) in tuss_base._CANETA_SIGTAP.items():
            assert sigtap == self.CANETA[tuss][0]
            assert len(fundamento) > 60, f"{tuss} sem fundamento citado"

    def test_a_fonte_registra_que_foi_ESCOLHA(self):
        """Nos 26 do ENG-029 a fonte apontava um caminho só; aqui apontava
        vários. Quem ler a row precisa saber a diferença."""
        por_tuss = _por_tuss()
        for tuss, (_s, rot) in self.CANETA.items():
            fonte = por_tuss[tuss]["fonte"]
            assert "caneta ENG-030" in fonte, f"{rot}: {fonte}"

    def test_o_tc_cranio_foi_CONFIRMADO_e_nao_reescrito(self):
        """O par já existia por nome e o mapa o endossa — a caneta é
        confirmação. Confirmação não reescreve; registra que foi conferida."""
        reg = _por_tuss()["41001010"]
        assert reg["codigo_sigtap"] == "0206010079"
        assert "confirmação" in reg["fonte"]

    def test_os_pares_preteridos_seguem_como_linha_propria(self):
        """A escolha não apaga o outro candidato do catálogo. Quem pedir
        contagem de plaquetas isolada, glicose no líquido sinovial, índice de
        T4 ou pesquisa de larvas continua achando — cada um na sua linha."""
        codigos = {r.get("codigo_sigtap") for r in _base()}
        for preterido, o_que_e in (
            ("0202020029", "CONTAGEM DE PLAQUETAS (o hemograma já a inclui)"),
            ("0202090124", "glicose no LÍQUIDO SINOVIAL"),
            ("0202060012", "ÍNDICE de tiroxina livre (cálculo, não dosagem)"),
            ("0202040089", "pesquisa de LARVAS"),
            ("0206010060", "TC de sela túrcica"),
            ("0207010030", "RM de coluna cervical"),
        ):
            assert preterido in codigos, f"{preterido} ({o_que_e}) sumiu do catálogo"


# ---------------------------------------------------------------------------
# §3 e §5.5 — a US morfológica: três registros honestos
# ---------------------------------------------------------------------------

class TestAUSMorfologica:
    """O único par cruzado da casa, desfeito.

    O registro curado carregava o TUSS da morfológica fundido ao SIGTAP da
    obstétrica SIMPLES — par desmentido nas DUAS pontas: a morfológica não tem
    par nenhum no mapa, e a simples aponta para outro TUSS. A raiz era o
    `nome_busca` genérico ("ultrassonografia obstetrica"), resíduo histórico
    em que a palavra "morfológica" vivia só nos aliases.
    """

    def test_a_chave_do_curado_e_honesta(self):
        reg = next(r for r in _base() if r.get("codigo_tuss") == "40901262")
        assert reg["nome_busca"] == "ultrassonografia obstetrica morfologica"

    def test_a_morfologica_ficou_SEM_sigtap_e_diz_por_que(self):
        """Sem par por fidelidade à fonte, não por esquecimento — e o alerta
        conta isso a quem for prescrever."""
        reg = next(r for r in _base() if r.get("codigo_tuss") == "40901262")
        assert reg.get("codigo_sigtap") is None
        alerta = " ".join(reg["alertas_base"])
        assert "NÃO publica linha própria" in alerta and "0205020143" in alerta

    def test_a_simples_sobreviveu_e_fundiu_sozinha(self):
        """§3.4: a linha bare simples ganha 40901238 pelo mapa, unívoca."""
        reg = next(r for r in _base() if r.get("codigo_sigtap") == "0205020143")
        assert reg["codigo_tuss"] == "40901238"
        assert "mapeamento oficial" in reg["fonte"]

    def test_sao_TRES_registros_onde_havia_um_hibrido(self):
        us = sorted(r["nome_busca"] for r in _base()
                    if "obstetrica" in r["nome_busca"])
        assert len(us) == 3, us
        assert "ultrassonografia obstetrica" in us
        assert "ultrassonografia obstetrica morfologica" in us

    def test_o_hibrido_e_estado_PROIBIDO(self):
        """§5.2 — a asserção direta: TUSS da morfológica e SIGTAP da simples
        juntos, em qualquer registro, é o par que mentia."""
        for r in _base():
            assert not (r.get("codigo_tuss") == "40901262"
                        and r.get("codigo_sigtap") == "0205020143"), (
                "o par cruzado voltou"
            )


# ---------------------------------------------------------------------------
# §5.3 — a guarda par-cruzado é regra, e não engole os legítimos
# ---------------------------------------------------------------------------

class TestAGuardaParCruzado:

    def test_o_predicado_recusa_quando_o_mapa_desmente(self):
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        curado = {"codigo_tuss": "40901262"}
        alvo = {"codigo_sigtap": "0205020143"}
        assert tuss_base._par_cruzado(curado, alvo, mapa) is True

    def test_o_predicado_ACEITA_quando_o_mapa_endossa(self):
        """O teste-par. Sem ele, uma guarda ampla demais engoliria os 29
        pares legítimos por nome e ninguém veria — é o mesmo cuidado do
        teste-par do retroativo no #281."""
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        curado = {"codigo_tuss": "41001010"}
        alvo = {"codigo_sigtap": "0206010079"}
        assert tuss_base._par_cruzado(curado, alvo, mapa) is False

    def test_o_predicado_se_cala_quando_a_fonte_nao_diz_nada(self):
        """Só morde com fonte UNÍVOCA sobre o alvo. Mapa silencioso ou
        ambíguo não desmente nada, e o join por nome segue valendo."""
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        assert tuss_base._par_cruzado(
            {"codigo_tuss": "40901262"}, {"codigo_sigtap": "9999999999"}, mapa) is False
        assert tuss_base._par_cruzado(
            {"codigo_tuss": None}, {"codigo_sigtap": "0205020143"}, mapa) is False

    def test_os_fundidos_por_nome_continuam_endossados(self):
        """A prova exaustiva do arquiteto, virada teste: nenhum par por nome
        que sobrou é desmentido pelo mapa."""
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        cruzados = []
        for r in _base():
            if not (r.get("codigo_tuss") and r.get("codigo_sigtap")):
                continue
            if tuss_base._par_cruzado(r, r, mapa):
                cruzados.append((r["nome_padrao"], r["codigo_tuss"], r["codigo_sigtap"]))
        assert not cruzados, f"pares cruzados vivos na base: {cruzados}"


# ---------------------------------------------------------------------------
# §4.4 e §5.4 — as contagens e os quatro que sobram
# ---------------------------------------------------------------------------

def test_as_contagens_do_despacho():
    b = _base()
    f = [r for r in b if r.get("codigo_sigtap") and r.get("codigo_tuss")]
    st = [r for r in b if r.get("codigo_tuss") and not r.get("codigo_sigtap")]
    ss = [r for r in b if r.get("codigo_sigtap") and not r.get("codigo_tuss")]
    assert (len(b), len(f), len(st), len(ss)) == (1109, 671, 4, 434), (
        f"base={len(b)} fundidos={len(f)} só-TUSS={len(st)} só-SIGTAP={len(ss)}; "
        "o despacho declara 1109/671/4/434"
    )


def test_os_quatro_so_tuss_sao_os_nomeados():
    """§5.4. E a razão é uniforme e verificável: o mapa de 2017-04 não tem
    destino para nenhum dos quatro. Não é escolha nossa de deixar de fora —
    é ausência na fonte, e não se inventa par."""
    inverso = tuss_base._carregar_mapa_sigtap_por_tuss(tuss_base._resolver_tuss_mapa_csv())
    so_tuss = {r["codigo_tuss"]: r for r in _base()
               if r.get("codigo_tuss") and not r.get("codigo_sigtap")}
    assert set(so_tuss) == {"40304922", "40901262", "41001095", "40310183"}, (
        {c: r["nome_padrao"] for c, r in so_tuss.items()}
    )
    for codigo, reg in so_tuss.items():
        assert reg["alertas_base"], f"{reg['nome_padrao']} sem alerta"
        assert not inverso.get(codigo), (
            f"{reg['nome_padrao']} TEM destino no mapa e mesmo assim ficou sem "
            "SIGTAP — ou é caneta que falta, ou é regressão da fusão"
        )


def test_nenhum_codigo_sigtap_aparece_em_dois_registros():
    """O colapso continua sendo colapso, também para os pares da caneta."""
    vistos: dict[str, str] = {}
    for r in _base():
        c = r.get("codigo_sigtap")
        if not c:
            continue
        assert c not in vistos, f"{c} em '{vistos[c]}' E em '{r['nome_padrao']}'"
        vistos[c] = r["nome_padrao"]


def test_todo_sigtap_da_base_existe_no_catalogo():
    """A caneta não pode ter inventado código: todo SIGTAP da base sai do CSV."""
    with _SIGTAP.open(encoding="utf-8", newline="") as f:
        oficiais = {r["codigo_sigtap"] for r in csv.DictReader(f)}
    for r in _base():
        c = r.get("codigo_sigtap")
        assert not c or c in oficiais, f"{r['nome_padrao']}: {c} fora do catálogo"
