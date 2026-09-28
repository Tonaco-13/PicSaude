"""
test_semaforo_flip_lote_2026_09.py — a caneta em lote (ENG-025 §C).

Autorização do Fabiano, 24/09/2026, verbatim: **"Vamos lá prosseguir com 1, 2
e 3."** Executado dos 14 rascunhos auto-checkados no disco, pelo padrão de
`test_semaforo_flip_j44_i50.py`. Cada ponto de decisão seguiu a recomendação
registrada no PRÓPRIO rascunho (precedente #261 §4); os pontos SEM recomendação
voltaram como pendência escrita, nunca adjudicados aqui.

O QUE ESTE ARQUIVO PROVA
------------------------
1. As 14 condições do lote estão EXAUSTIVAS — 25 CIDs novos (as 14 condições,
   mais os 11 CIDs em que a família IST se reparte). O silêncio mudou de lado:
   fora do elenco agora é amarelo com causa, não neutro.
2. Todo o elenco assinado acende verde, inclusive as associações fixas que o
   `canon_ativo` não decompõe.
3. O que os rascunhos deixaram FORA acende amarelo, e por motivo declarado.
4. **O cruzamento com a RENAME 2024 foi EXECUTADO** (os rascunhos o adiavam
   para "a sessão de assinatura", que nunca veio), e mudou três coisas — ver
   `TestOCruzamentoRenameMudouRows`.
5. **As colisões entre condições resolvem** — 9 substâncias vivem em dois ou
   mais CIDs deste lote com doses diferentes. É o exercício real da chave
   composta do #269, e o pôster de por que ela existe.
6. Os CIDs que já eram exaustivos (I10, E11, J45, J44, I50, F32, F41, N39.0)
   continuam intactos: um lote de 143 rows não pode mexer no que já estava.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.domain.posologia_sugerida import carregar_posologias, sugerir
from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_NEUTRO,
    SINAL_VERDE,
    avaliar_semaforo,
    canon_ativo,
    canon_cid,
    carregar_regras,
)

_RAIZ = Path(__file__).resolve().parents[3] / "data"
_CSV = _RAIZ / "decisao_semaforo.csv"
_POS = _RAIZ / "posologia_sugerida.csv"

_ASSINANTE = "Fabiano Tonaco Borges"

# Os 25 CIDs que esta caneta torna exaustivos, e o elenco de cada um.
_LOTE = {
    "A30":   ("semaforo_a30_exaustiva_v1_2026-09",
              ["rifampicina", "clofazimina", "dapsona", "prednisona", "talidomida",
               "pentoxifilina", "ofloxacino", "minociclina", "claritromicina"]),
    "D50":   ("semaforo_d50_v1_2026-09",
              ["sulfato ferroso", "sacarato de hidróxido férrico"]),
    "D57":   ("semaforo_d57_v1_2026-09",
              ["hidroxiureia", "ácido fólico", "fenoximetilpenicilina",
               "benzilpenicilina benzatina", "estolato de eritromicina", "alfaepoetina"]),
    "E28.2": ("semaforo_e28_v1_2026-09",
              ["etinilestradiol + levonorgestrel", "acetato de medroxiprogesterona",
               "noretisterona", "ciproterona", "metformina"]),
    "E78":   ("semaforo_e78_exaustiva_v1_2026-09",
              ["sinvastatina", "atorvastatina", "pravastatina", "bezafibrato",
               "ciprofibrato", "etofibrato", "fenofibrato", "genfibrozila",
               "gemfibrozila", "ácido nicotínico"]),
    "F17":   ("semaforo_f17_exaustiva_v1_2026-09",
              ["bupropiona", "nicotina", "adesivo de nicotina", "goma de nicotina",
               "pastilha de nicotina"]),
    "G20":   ("semaforo_g20_v1_2026-09",
              ["levodopa + carbidopa", "levodopa + benserazida", "pramipexol",
               "rasagilina", "amantadina", "entacapona", "triexifenidil",
               "biperideno", "clozapina", "rivastigmina"]),
    "G30":   ("semaforo_g30_exaustiva_v1_2026-09",
              ["donepezila", "galantamina", "rivastigmina", "memantina"]),
    "G40":   ("semaforo_g40_exaustiva_v1_2026-09",
              ["ácido valproico", "valproato de sódio", "carbamazepina", "clobazam",
               "clonazepam", "etossuximida", "fenitoína", "fenobarbital",
               "gabapentina", "lamotrigina", "levetiracetam", "primidona",
               "topiramato", "vigabatrina"]),
    "L20":   ("semaforo_l20_exaustiva_v1_2026-09",
              ["acetato de hidrocortisona", "dexametasona", "tacrolimo",
               "ciclosporina", "metotrexato", "upadacitinibe"]),
    "L40":   ("semaforo_l40_v1_2026-09",
              ["ácido salicílico", "alcatrão mineral", "calcipotriol", "clobetasol",
               "dexametasona", "acitretina", "metotrexato", "ciclosporina",
               "adalimumabe", "etanercepte", "secuquinumabe", "ustequinumabe",
               "risanquizumabe"]),
    "M81":   ("semaforo_m81_exaustiva_v1_2026-09",
              ["alendronato de sódio", "risedronato sódico", "carbonato de cálcio",
               "carbonato de cálcio + colecalciferol",
               "fosfato de cálcio tribásico + colecalciferol", "ácido zoledrônico",
               "pamidronato dissódico", "raloxifeno", "estrogênios conjugados",
               "romosozumabe", "calcitonina", "calcitriol"]),
    "R52.2": ("semaforo_r52_exaustiva_v1_2026-09",
              ["paracetamol", "dipirona", "ácido acetilsalicílico", "ibuprofeno",
               "omeprazol", "gabapentina", "carbamazepina", "fenitoína",
               "ácido valproico", "valproato de sódio", "amitriptilina",
               "nortriptilina", "clomipramina", "codeína", "morfina", "metadona"]),
    # família IST — o PCDT é um só, os CIDs são doze
    "A51":   ("semaforo_ist_v1_2026-09", ["benzilpenicilina benzatina", "doxiciclina"]),
    "A52":   ("semaforo_ist_v1_2026-09", ["benzilpenicilina benzatina", "doxiciclina"]),
    "A54":   ("semaforo_ist_v1_2026-09", ["ceftriaxona", "azitromicina"]),
    "A55":   ("semaforo_ist_v1_2026-09", ["doxiciclina", "azitromicina"]),
    "A56":   ("semaforo_ist_v1_2026-09", ["azitromicina", "doxiciclina"]),
    "A57":   ("semaforo_ist_v1_2026-09", ["azitromicina", "ceftriaxona", "ciprofloxacino"]),
    "A58":   ("semaforo_ist_v1_2026-09",
              ["azitromicina", "doxiciclina", "ciprofloxacino",
               "sulfametoxazol + trimetoprima"]),
    "A59":   ("semaforo_ist_v1_2026-09", ["metronidazol"]),
    "A60":   ("semaforo_ist_v1_2026-09", ["aciclovir"]),
    "B37.3": ("semaforo_ist_v1_2026-09",
              ["miconazol", "nistatina", "fluconazol", "itraconazol"]),
    "N73":   ("semaforo_ist_v1_2026-09",
              ["ceftriaxona", "doxiciclina", "metronidazol", "cefotaxima"]),
    "N76.0": ("semaforo_ist_v1_2026-09", ["metronidazol", "clindamicina"]),
}

# Fora do elenco, com a razão que o rascunho (ou o cruzamento) registrou.
_FORA = {
    "A30":   {"amoxicilina": "não é antihansênico — fora do Quadro 1 e dos Quadros 4-6",
              "ácido acetilsalicílico": "coadjuvante de profilaxia de TEV, não tratamento (§4.3 do rascunho)",
              "ivermectina": "anti-helmíntico no início da corticoterapia, não tratamento"},
    "D50":   {"fumarato ferroso": "fora do item 8.3 do PCDT 2014",
              "gluconato ferroso": "fora do item 8.3 do PCDT 2014"},
    "D57":   {"azitromicina": "arsenal de INTERCORRÊNCIA infecciosa, não da doença falciforme (§4.2)",
              "ceftriaxona": "arsenal de intercorrência (§4.2)",
              "cefalexina": "arsenal de intercorrência (§4.2)"},
    "E28.2": {"espironolactona": "fora do item 7 do PCDT SOP",
              "pioglitazona": "tiazolidinediona — NÃO recomendada (p. 9)",
              "letrozol": "fora do item 7"},
    "E78":   {"rosuvastatina": "ausente do elenco do PCDT (não há frase de exclusão — §4.2)",
              "ezetimiba": "excluída com citação (p. 9)"},
    "F17":   {"vareniclina": "não incorporada (Portaria 41/SCTIE/MS/2019, p. 41-42)"},
    "G20":   {"rotigotina": "avaliada (Questão 1, Rel. 957/2024) e NÃO incorporada por custo (p. 35)",
              "selegilina": "DESCONTINUADA no Brasil (p. 10)"},
    "G30":   {"rivaroxabana": "sem relação com o elenco do PCDT de Alzheimer"},
    "G40":   {"lacosamida": "excluída com citação (Relatório nº 353, p. 45)"},
    "L20":   {"furoato de mometasona": "no PCDT 2025, AUSENTE da RENAME 2024 — ver TestOCruzamentoRenameMudouRows",
              "dupilumabe": "no PCDT 2025, AUSENTE da RENAME 2024 — idem"},
    "L40":   {"infliximabe": "NÃO incorporado, com relatoria (p. 47)",
              "betametasona": "fora do elenco; a associação com calcipotriol não entrou (p. 47)"},
    "M81":   {"teriparatida": "excluída com citação (item 7.2.5, p. 11)",
              "denosumabe": "fora do elenco dos itens 7.2.7/7.2.8"},
    "R52.2": {"tramadol": "opioide fraco fora do elenco 6.2.6",
              "oxicodona": "opioide forte fora do elenco",
              "naproxeno": "escopo M16/M17 pela Portaria SCTIE 53/2017 (p. 14), não R52"},
    "A54":   {"penicilina": "fora do Quadro 31"},
    "A60":   {"valaciclovir": "fora do Quadro 38"},
    "A59":   {"tinidazol": "fora do Quadro 35"},
    "B37.3": {"secnidazol": "fora do Quadro 33"},
}


def _carregar():
    return carregar_regras(str(_CSV))


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = _carregar()
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


# ---------------------------------------------------------------------------
# 1 — o flip
# ---------------------------------------------------------------------------

def test_as_25_condicoes_do_lote_estao_exaustivas():
    _ap, exaustivos, _prov = _carregar()
    faltando = sorted(set(_LOTE) - exaustivos)
    assert not faltando, f"CIDs do lote que não ficaram exaustivos: {faltando}"


def test_todo_o_elenco_assinado_acende_verde():
    aprovados, exaustivos, prov = _carregar()
    for cid, (_versao, elenco) in _LOTE.items():
        for ativo in elenco:
            a = avaliar_semaforo(cid, ativo, aprovados, exaustivos, prov)
            assert a.sinal == SINAL_VERDE, f"({cid}, {ativo}) deu {a.sinal}"


def test_o_que_ficou_de_fora_acende_amarelo_com_causa():
    aprovados, exaustivos, prov = _carregar()
    for cid, fora in _FORA.items():
        for ativo, porque in fora.items():
            a = avaliar_semaforo(cid, ativo, aprovados, exaustivos, prov)
            assert a.sinal == SINAL_AMARELO, f"({cid}, {ativo}) deu {a.sinal} — {porque}"
            assert a.causa == "ausente_lista_exaustiva", (cid, ativo)


def test_a_proveniencia_do_lote_esta_assinada():
    aprovados, _ex, _p = _carregar()
    for cid, (versao, elenco) in _LOTE.items():
        prov = aprovados[(canon_cid(cid), canon_ativo(elenco[0]))]
        assert prov.versao == versao, (cid, prov.versao)
        assert prov.validado_por == _ASSINANTE, cid
        assert prov.fonte, cid


# ---------------------------------------------------------------------------
# 2 — o cruzamento com a RENAME, que os rascunhos adiavam
# ---------------------------------------------------------------------------

class TestOCruzamentoRenameMudouRows:
    """Os rascunhos deixavam o cruzamento "para a sessão de assinatura".

    Ele foi feito (24/09, `data/fontes-oficiais/rename/rename-2024.pdf`, 254
    páginas indexadas) e mudou três coisas. As três viram guarda porque são o
    tipo de achado que, sem teste, volta a ser suposição no próximo lote.
    """

    def test_mometasona_e_dupilumabe_ficaram_fora_do_verde_do_l20(self):
        """Critério estrito da casa: 🟢 = reconhecido E disponível no SUS.

        Os dois constam do item 6.4 do PCDT de 2025 e têm ZERO ocorrências nas
        254 páginas da RENAME 2024. É o mesmo caso da fluticasona no J44
        ("recomendada no PCDT, ausente da RENAME 2024"), e recebe o mesmo
        tratamento. DIVERGE do §2 do rascunho, que os propunha como rows — e
        está declarado como pendência ao Fabiano, porque quem fecha é ele.
        """
        assert _av("L20", "furoato de mometasona").sinal == SINAL_AMARELO
        assert _av("L20", "dupilumabe").sinal == SINAL_AMARELO
        assert _av("L20", "upadacitinibe").sinal == SINAL_VERDE, (
            "upadacitinibe ESTÁ na RENAME 2024 (p. 90, 220) — a exclusão dos "
            "outros dois não pode arrastá-lo junto"
        )

    def test_o_alias_do_valproato_existe_e_declara_a_ausencia(self):
        """'valproato de sódio' resolve para a chave 'valproato', distinta de
        'acido valproico' — sem a row-alias, a grafia do próprio PCDT daria
        amarelo falso. A RENAME 2024 lista só 'ácido valproico' (p. 93, 125), e
        a fonte da row diz isso em vez de citar a RENAME para os dois."""
        assert canon_ativo("valproato de sódio") == "valproato"
        assert canon_ativo("ácido valproico") == "acido valproico"
        for cid in ("G40", "R52.2"):
            assert _av(cid, "valproato de sódio").sinal == SINAL_VERDE, cid
            assert _av(cid, "ácido valproico").sinal == SINAL_VERDE, cid
        aprovados, _e, _p = _carregar()
        fonte = aprovados[("G40", "valproato")].fonte
        assert "RENAME 2024" in fonte and "NÃO aparece" in fonte, (
            "a fonte do alias precisa registrar a ausência, não citar a RENAME "
            "como se ele estivesse lá"
        )

    def test_as_suspeitas_de_ausencia_do_e78_eram_falsas(self):
        """O rascunho do E78 suspeitava que etofibrato, genfibrozila e ácido
        nicotínico tivessem saído da RENAME. O cruzamento diz que não: p. 44/190,
        44/193 e 41/165. Ficam no verde, e a suspeita fica desmentida por
        teste."""
        for ativo in ("etofibrato", "genfibrozila", "ácido nicotínico"):
            assert _av("E78", ativo).sinal == SINAL_VERDE, ativo


# ---------------------------------------------------------------------------
# 3 — a chave composta exercida por dado real
# ---------------------------------------------------------------------------

class TestAsColisoesEntreCondicoesResolvem:
    """Nove substâncias vivem em dois ou mais CIDs deste lote. É o exercício
    real da chave `(ativo, CID)` do #269 — e o pôster de por que ela existe."""

    COMPARTILHADAS = {
        "benzilpenicilina benzatina": ["A51", "A52", "D57"],
        "doxiciclina": ["A51", "A52", "A55", "A56", "A58", "N73"],
        "azitromicina": ["A54", "A55", "A56", "A57", "A58"],
        "ciprofloxacino": ["A57", "A58"],
        "metronidazol": ["A59", "N73", "N76.0"],
        "ceftriaxona": ["A54", "A57", "N73"],
        "metotrexato": ["L20", "L40"],
        "ciclosporina": ["L20", "L40"],
        "rivastigmina": ["G20", "G30"],
    }

    def test_cada_par_devolve_a_sua_dose_nunca_a_do_vizinho(self):
        for ativo, cids in self.COMPARTILHADAS.items():
            for cid in cids:
                p = sugerir(ativo, cid)
                assert p is not None, f"({ativo}, {cid}) sumiu do índice"
                assert p.codigo_cid == cid, (
                    f"({ativo}, {cid}) devolveu a dose de {p.codigo_cid} — "
                    "sobrescrita silenciosa"
                )

    def test_a_benzatina_da_sifilis_nao_e_a_da_falciforme(self):
        """A prova clínica mais nítida do lote: mesma substância, 2,4 milhões
        UI em dose única na sífilis recente e dose POR PESO na profilaxia da
        doença falciforme. Antes do #269 uma teria engolido a outra."""
        sifilis = sugerir("benzilpenicilina benzatina", "A51").posologia
        falciforme = sugerir("benzilpenicilina benzatina", "D57").posologia
        assert "2,4 milhões UI" in sifilis and "dose única" in sifilis
        assert "300.000 UI" in falciforme and "peso" in falciforme
        assert sifilis != falciforme

    def test_o_metronidazol_tem_tres_esquemas_no_mesmo_pcdt(self):
        vistas = {c: sugerir("metronidazol", c).posologia for c in ("A59", "N73", "N76.0")}
        assert len(set(vistas.values())) == 3, vistas

    def test_o_ciprofloxacino_colide_no_semaforo_mas_o_n39_nao_tem_posologia(self):
        """Achado PRÉ-EXISTENTE, registrado por não ser deste lote.

        O ciprofloxacino é 🟢 em N39.0 desde a caneta da ITU, e agora também em
        A57 e A58. No `posologia_sugerida.csv`, porém, o N39.0 só tem 3 das 8
        substâncias do seu elenco (nitrofurantoína, fosfomicina, cefalexina) —
        o ciprofloxacino não está entre elas. A colisão de SEMÁFORO existe e
        resolve; a de POSOLOGIA não chega a existir, porque falta a row do lado
        do N39.0.

        Não é regressão deste lote e não foi consertada aqui: completar o
        elenco de posologia do N39.0 é curadoria da ITU, com a sua própria
        fonte e a sua própria caneta. Fica travado como fato para que a
        ausência não seja lida como efeito colateral das 143 rows novas.
        """
        assert _av("N39.0", "ciprofloxacino").sinal == SINAL_VERDE
        assert sugerir("ciprofloxacino", "N39.0") is None, (
            "o N39.0 ganhou posologia de ciprofloxacino — atualize esta guarda "
            "e o registro junto"
        )
        for cid in ("A57", "A58"):
            assert sugerir("ciprofloxacino", cid) is not None, cid

    def test_o_metotrexato_e_semanal_nas_duas_dermatoses(self):
        """A colisão que o rascunho do L20 chamou de "erro clínico calado": a
        dose é SEMANAL nas duas, e diferente entre elas."""
        l20 = sugerir("metotrexato", "L20").posologia
        l40 = sugerir("metotrexato", "L40").posologia
        assert "SEMANA" in l20.upper() and "SEMANA" in l40.upper()
        assert l20 != l40

    def test_nenhuma_row_foi_engolida_no_carregamento(self):
        with _POS.open(encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if (r.get("status_curadoria") or "").strip() == "validado"]
        idx = carregar_posologias(str(_POS))
        assert len(idx) == len(rows), (
            f"{len(rows)} linhas validadas viraram {len(idx)} entradas — uma row "
            "foi sobrescrita. Com 143 rows novas, é o risco número um do lote."
        )


# ---------------------------------------------------------------------------
# 4 — o que o lote NÃO podia mexer
# ---------------------------------------------------------------------------

def test_os_cids_que_ja_eram_exaustivos_continuam_intactos():
    for cid, ativo in (("I10", "losartana"), ("E11", "metformina"), ("J45", "beclometasona"),
                       ("J44", "salbutamol"), ("I50", "espironolactona"),
                       ("F32", "fluoxetina"), ("F41", "clonazepam"),
                       ("N39.0", "fosfomicina")):
        assert _av(cid, ativo).sinal == SINAL_VERDE, (cid, ativo)


def test_o_naproxeno_entrou_sem_declarar_exaustividade_em_m16_m17():
    """O PCDT da Dor Crônica manda o naproxeno para M16/M17 (Portaria SCTIE
    53/2017, p. 14), mas NÃO traz o elenco da osteoartrite. Declarar M16/M17
    exaustivos faria o semáforo julgar o que a fonte não afirma — o paracetamol
    ficaria 🟡 na gonartrose, o que é falso. As rows existem; o portão da
    exaustividade mantém o silêncio honesto."""
    _ap, exaustivos, _p = _carregar()
    assert "M16" not in exaustivos and "M17" not in exaustivos
    assert _av("M16", "naproxeno").sinal == SINAL_NEUTRO
    assert _av("M16", "paracetamol").sinal == SINAL_NEUTRO
    assert sugerir("naproxeno", "M17") is not None, "a posologia do naproxeno sumiu"
    assert _av("R52.2", "naproxeno").sinal == SINAL_AMARELO, (
        "naproxeno não pertence ao elenco do R52.2 — o escopo dele é M16/M17"
    )


def test_o_e78_deixou_de_ser_semente():
    """As 2 rows-semente de junho (`semaforo_seed_v1_2026-06`, exaustivo=false)
    foram SUBSTITUÍDAS, não duplicadas — duas provenências para o mesmo par
    seriam duas verdades sobre a mesma coisa."""
    with _CSV.open(encoding="utf-8") as fh:
        e78 = [r for r in csv.DictReader(fh) if r["codigo_cid"] == "E78"]
    assert all(r["versao"] == "semaforo_e78_exaustiva_v1_2026-09" for r in e78), (
        "sobrou row-semente no E78"
    )
    assert len(e78) == 10, f"E78 deveria ter 10 rows, tem {len(e78)}"
    assert _av("E78", "sinvastatina").sinal == SINAL_VERDE
