"""
tests/unit/test_semaforo_flip_j44_i50.py — canetas J44 (DPOC) + I50 (IC).

Autorização verbal do Fabiano, 13/09/2026, verbatim: **"Merge e canetas
autorizados"** — mesmo precedente do sinal verde I10 estrito (#256): a
palavra do Fabiano é a assinatura. Executado dos rascunhos auto-checkados
`RASCUNHO-J44-DUPLO-PCDT-2026.md` e `RASCUNHO-I50-DUPLO-PCDT-2026.md`
(agenda R4, 05-06/09), pelo padrão de `test_semaforo_flip_e11_j45.py`.

O QUE ESTE ARQUIVO PROVA
------------------------
1. J44 e I50 estão EXAUSTIVOS — o silêncio mudou de lado: fora do elenco
   agora é amarelo com causa, não neutro.
2. Todo o elenco assinado acende verde, inclusive a combinação fixa
   (`formoterol + budesonida`, `sacubitril + valsartana`), que `canon_ativo`
   não decompõe — sem row própria seria amarelo falso sistemático.
3. O que o rascunho deixou FORA acende amarelo, e por motivo declarado:
   fluticasona, teofilina, roflumilaste, glicopirrônio e salmeterol na DPOC;
   bisoprolol e ivabradina na IC. Todos ausentes da RENAME 2024 (critério
   estrito da casa: 🟢 = reconhecido **e** disponível no SUS), menos
   salmeterol, que consta da RENAME mas não é recomendado pelo protocolo
   vigente — as duas razões levam ao mesmo amarelo, por caminhos diferentes.
4. A proveniência é assinada pelo Fabiano, com versão e página na fonte.
5. **A interseção com outros CIDs continua honesta:** dapagliflozina é 🟢 em
   E11 e agora também em I50 (mesma molécula, dois protocolos), e segue 🟡
   em I10. Fármacos que a IC e a HAS compartilham (enalapril, losartana,
   carvedilol…) acendem nos dois, porque estão nos dois protocolos — não por
   vazamento de elenco.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_VERDE,
    avaliar_semaforo,
    carregar_regras,
)

_CSV = Path(__file__).resolve().parents[3] / "data" / "decisao_semaforo.csv"

_ASSINATURA = "Fabiano Tonaco Borges"
_V_J44 = "semaforo_j44_exaustiva_v1_2026-09"
_V_I50 = "semaforo_i50_exaustiva_v1_2026-09"

_J44_ELENCO = [
    "salbutamol", "ipratrópio", "tiotrópio", "formoterol", "budesonida",
    "formoterol + budesonida", "prednisona", "umeclidínio",
]

_I50_ELENCO = [
    "sacubitril + valsartana", "enalapril", "captopril", "losartana",
    "espironolactona", "furosemida", "hidroclorotiazida", "carvedilol",
    "metoprolol", "digoxina", "hidralazina", "isossorbida", "dapagliflozina",
]

# Fora do elenco, com a razão que o rascunho registrou.
_J44_FORA = {
    "fluticasona": "recomendada no PCDT, ausente da RENAME 2024",
    "teofilina": "não recomendada na DPOC estável + ausente da RENAME",
    "roflumilaste": "apenas anexo histórico do PCDT",
    "glicopirrônio": "LAMA citado no PCDT, ausente da RENAME 2024",
    "salmeterol": "consta da RENAME, mas fora do protocolo vigente",
}
_I50_FORA = {
    "bisoprolol": "citado no PCDT, ausente da RENAME 2024",
    "ivabradina": "citada no PCDT, ausente da RENAME 2024",
}


def _carregar():
    return carregar_regras(str(_CSV))


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = _carregar()
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


def _rows():
    with _CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# 1 — o flip
# ---------------------------------------------------------------------------

def test_j44_e_i50_estao_exaustivos():
    _aprovados, exaustivos, _prov = _carregar()
    assert "J44" in exaustivos
    assert "I50" in exaustivos


def test_o_nucleo_cardiorrespiratorio_cronico_esta_completo():
    """§5 do rascunho I50: com I10 v2 + estas duas, sete condições da APS."""
    _aprovados, exaustivos, _prov = _carregar()
    assert {"I10", "E11", "J45", "J44", "I50", "F32", "N39.0"} <= set(exaustivos)


# ---------------------------------------------------------------------------
# 2 — o elenco assinado acende
# ---------------------------------------------------------------------------

def test_elenco_j44_assinado_acende_verde():
    for ativo in _J44_ELENCO:
        assert _av("J44", ativo).sinal == SINAL_VERDE, ativo


def test_elenco_i50_assinado_acende_verde():
    for ativo in _I50_ELENCO:
        assert _av("I50", ativo).sinal == SINAL_VERDE, ativo


def test_combinacoes_fixas_tem_row_propria():
    """`canon_ativo` não decompõe combinação: sem row, amarelo falso."""
    assert _av("J44", "formoterol + budesonida").sinal == SINAL_VERDE
    assert _av("I50", "sacubitril + valsartana").sinal == SINAL_VERDE


def test_alias_com_dose_digitada_casa():
    """Mesma exigência do flip E11/J45: dose digitada não pode derrubar."""
    assert _av("I50", "Dapagliflozina 10mg").sinal == SINAL_VERDE
    assert _av("I50", "Carvedilol 3,125 mg").sinal == SINAL_VERDE
    assert _av("J44", "Prednisona 20mg").sinal == SINAL_VERDE


# ---------------------------------------------------------------------------
# 3 — o silêncio mudou de lado
# ---------------------------------------------------------------------------

def test_j44_fora_do_elenco_acende_amarelo():
    for ativo, razao in _J44_FORA.items():
        assert _av("J44", ativo).sinal == SINAL_AMARELO, f"{ativo} — {razao}"


def test_i50_fora_do_elenco_acende_amarelo():
    for ativo, razao in _I50_FORA.items():
        assert _av("I50", ativo).sinal == SINAL_AMARELO, f"{ativo} — {razao}"


# ---------------------------------------------------------------------------
# 4 — a interseção entre protocolos continua honesta
# ---------------------------------------------------------------------------

def test_dapagliflozina_verde_em_e11_e_i50_amarela_em_i10():
    """Mesma molécula, dois protocolos — e o contraste didático de I10 vive."""
    assert _av("E11", "dapagliflozina").sinal == SINAL_VERDE
    assert _av("I50", "dapagliflozina").sinal == SINAL_VERDE
    assert _av("I10", "dapagliflozina").sinal == SINAL_AMARELO


def test_i50_nao_vazou_elenco_para_i10():
    """Digoxina e sacubitril são da IC, não da HAS: I10 segue amarelo neles."""
    assert _av("I10", "digoxina").sinal == SINAL_AMARELO
    assert _av("I10", "sacubitril + valsartana").sinal == SINAL_AMARELO


def test_j44_nao_vazou_elenco_para_j45():
    """Tiotrópio e umeclidínio são da DPOC; a asma não os tem no elenco."""
    assert _av("J45", "tiotrópio").sinal == SINAL_AMARELO
    assert _av("J45", "umeclidínio").sinal == SINAL_AMARELO


# ---------------------------------------------------------------------------
# 5 — proveniência
# ---------------------------------------------------------------------------

def test_proveniencia_assinada_com_versao_e_pagina():
    rows = [r for r in _rows() if r["codigo_cid"] in ("J44", "I50")]
    assert len(rows) == len(_J44_ELENCO) + len(_I50_ELENCO)

    for r in rows:
        esperada = _V_J44 if r["codigo_cid"] == "J44" else _V_I50
        assert r["status_curadoria"] == "validado", r
        assert r["validado_por"] == _ASSINATURA, r
        assert r["versao"] == esperada, r
        assert r["exaustivo"] == "true", r
        assert "PCDT" in r["fonte"] and "RENAME 2024" in r["fonte"], r
        assert "p." in r["fonte"], f"fonte sem página: {r}"


def test_nenhuma_row_nova_ficou_rascunho():
    """Rascunhista nunca flipa: se sobrou `rascunho` aqui, algo passou batido."""
    for r in _rows():
        if r["codigo_cid"] in ("J44", "I50"):
            assert r["status_curadoria"] != "rascunho", r


# ---------------------------------------------------------------------------
# 6 — o limite da posologia, achado nesta caneta
# ---------------------------------------------------------------------------

# Substâncias cuja posologia SE REPETE entre CIDs porque o protocolo a repete —
# não porque a chave falhou. Cada entrada precisa da citação que a sustenta.
#
# ENG-025 §C (24/09): a caneta em lote trouxe o primeiro caso real. Até aqui,
# toda substância compartilhada tinha dose diferente em cada condição, e a
# guarda abaixo exigia distinção como PROVA de que a chave discriminava. Com o
# PCDT das IST a premissa caiu: o Quadro 31 (clamídia, p. 60) e o Quadro 39
# (cancroide, p. 72) prescrevem o MESMO esquema de azitromicina — 500 mg,
# 2 comprimidos, VO, dose única. Texto igual ali é fidelidade à fonte, não
# duplicação.
#
# A exigência de distinção era um PROXY para "nenhuma row foi engolida"; o que
# de fato prova isso são as duas asserções acima (o índice tem uma entrada por
# linha validada, e cada par devolve o SEU cid). O proxy virou lista declarada:
# repetição nova segue reprovando até alguém escrevê-la aqui, com a página.
_REPETE_POR_PROTOCOLO = {
    "azitromicina": (
        "PCDT IST 2021: mesmo esquema (500 mg, 2 comprimidos, VO, dose única) "
        "na clamidiose (Quadro 31, p. 60) e no cancroide (Quadro 39, p. 72)."
    ),
    "naproxeno": (
        "PCDT Dor Crônica 2024, Quadro 2 (p. 17-19) com o escopo da p. 14: o "
        "naproxeno é da osteoartrite de QUADRIL E JOELHO (Portaria SCTIE "
        "53/2017). É um esquema só para as duas articulações, e por isso duas "
        "rows (M16 e M17) com o mesmo texto — a fonte não as separa."
    ),
    # ── ENG-026 (28/09): as repetições de ESPELHO ────────────────────────────
    # Caso novo e de outra natureza. Os dois acima repetem porque a FONTE
    # repete; estes quatro + dois repetem porque a CANETA mandou espelhar um
    # CID noutro. A diferença importa: a fonte é a mesma linha do mesmo quadro,
    # e o espelho existe para que o prescritor que codifica o outro código
    # receba o mesmo sinal — não para curar duas vezes a mesma coisa.
    #
    # Se o espelho um dia DERIVAR (texto diferente entre o par), a guarda
    # dedicada de cada um (TestOEspelhoF00 / TestOEspelhoA53) reprova antes
    # desta — é lá que mora a afirmação forte.
    **{ativo: (
        "ESPELHO F00<-G30 (caneta do Fabiano, 28/09/2026): mesmo protocolo, "
        "mesmo Quadro 5 (PCDT Alzheimer 2025, p. 13). O prescritor pode "
        "codificar F00 (demência NA doença de Alzheimer) em vez de G30, e a "
        "cadeia do semáforo NÃO sobe de F00 para G30 — são categorias "
        "distintas. Sem o espelho, o mesmo elenco ficaria mudo num dos dois."
    ) for ativo in ("donepezila", "galantamina", "rivastigmina", "memantina")},
    **{ativo: (
        "ESPELHO A53<-A52 (caneta do Fabiano, 28/09/2026): PCDT IST 2021, "
        "Quadro 15 (p. 23-24), que trata como TARDIA a sífilis \"latente tardia "
        "(com mais de um ano de evolução) OU LATENTE COM DURAÇÃO IGNORADA e "
        "sífilis terciária\". A CID-10 chama A53.0 de \"sífilis latente, não "
        "especificada se recente ou tardia\" — é a mesma situação clínica, e "
        "por isso o esquema tardio vale nos dois códigos."
    ) for ativo in ("benzilpenicilina benzatina", "doxiciclina")},
}


def test_posologia_com_dois_cids_para_o_mesmo_ativo_agora_convive():
    """O VERDE-APÓS-O-FIX da guarda fail-loud desta caneta (ENG-019).

    Esta função nasceu ao contrário. Em 13/09, ao executar as canetas J44/I50,
    descobriu-se que `carregar_posologias` indexava por ATIVO — `idx[ativo_k]`
    — e que duas rows do mesmo princípio com CIDs diferentes colidiam, **com a
    última do CSV vencendo em silêncio**. Nove rows destas canetas colidiam com
    HAS, asma e DM2; carvedilol começa em 3,125 mg 2x/dia na IC, e sobrescrever
    com isso a dose de hipertensão é erro clínico calado. As nove foram
    retiradas, e esta guarda ficou no ar **proibindo colisão** para que a
    próxima falhasse alto em vez de morder.

    O ENG-019 fez o conserto real: a chave passou a ser `(ativo, CID)`. A
    proibição, então, VIRA O SEU CONTRÁRIO — colidir é legítimo, e o que a
    guarda passa a exigir é que a colisão **resolva**: cada par vivo, cada um
    com a sua dose, nenhuma row engolida.

    Inverter em vez de apagar é deliberado: apagada, a guarda não contaria mais
    que o defeito existiu nem provaria que ele está fechado. É a diferença
    entre "não há colisão" (o remendo de ontem) e "colisão não sobrescreve
    ninguém" (o invariante de hoje).
    """
    import csv as _csv

    from app.domain.posologia_sugerida import carregar_posologias, sugerir
    from app.domain.semaforo_decisao import canon_ativo

    caminho = Path(__file__).resolve().parents[3] / "data" / "posologia_sugerida.csv"
    with caminho.open(encoding="utf-8") as fh:
        rows = [
            r
            for r in _csv.DictReader(fh)
            if (r.get("status_curadoria") or "").strip() == "validado"
        ]

    por_ativo: dict[str, list[str]] = {}
    for r in rows:
        por_ativo.setdefault(canon_ativo(r["principio_ativo"]), []).append(
            r["codigo_cid"]
        )

    colisoes = {a: cids for a, cids in por_ativo.items() if len(cids) > 1}
    assert colisoes, (
        "nenhuma substância compartilhada entre protocolos no CSV — as nove "
        "rows exiladas de J44/I50 não voltaram, ou voltaram sob outra chave. "
        "Sem colisão viva, o conserto do ENG-019 não está sendo exercido por "
        "dado real nenhum."
    )

    # NENHUMA row engolida: o índice tem uma entrada por par (ativo, CID)...
    idx = carregar_posologias(str(caminho))
    assert len(idx) == len(rows), (
        "o índice tem menos entradas que o CSV tem linhas validadas — alguma "
        "row foi sobrescrita no carregamento. Se a chave voltou a ser só o "
        "ativo, é exatamente o erro clínico calado que esta guarda vigia."
    )

    # ...e cada par devolve a SUA dose, não a do vizinho.
    for ativo, cids in colisoes.items():
        vistas = {}
        for cid in cids:
            p = sugerir(ativo, cid)
            assert p is not None, f"({ativo}, {cid}) sumiu do índice"
            assert p.codigo_cid == cid, (
                f"({ativo}, {cid}) devolveu a dose de {p.codigo_cid} — "
                "sobrescrita silenciosa de volta"
            )
            vistas[cid] = p.posologia
        repetidas = len(vistas) - len(set(vistas.values()))
        if repetidas:
            assert ativo in _REPETE_POR_PROTOCOLO, (
                f"'{ativo}' devolve a MESMA posologia para CIDs diferentes "
                f"({vistas}) — ou o dado está duplicado, ou a chave não está "
                "discriminando de verdade. Se a repetição for do PROTOCOLO, "
                "declare-a em _REPETE_POR_PROTOCOLO com a citação."
            )


# ---------------------------------------------------------------------------
# 5 — a nona row NÃO existe, e isso agora é um fato cobrado pelo gate
# ---------------------------------------------------------------------------

class TestNonaRowNaoExiste:
    """ENG-025 §B — a caneta foi mandada e a fonte respondeu que não.

    `fumarato de formoterol + budesonida` em J44 é a nona das rows exiladas de
    J44/I50 e a única que o #269 não conseguiu religar. O GO do Fabiano de
    23/09 mandou buscá-la no **PCDT DPOC 2021** (a recomendação (C) do registro
    de 13/09: *"versão em que LABA+ICS ainda era opção inicial e que deve
    trazer o esquema"*). O 2021 foi estagiado e lido: **a hipótese era falsa**.
    O Quadro F (p. 16-18) não tem linha LABA+ICS, exatamente como o Quadro 6 do
    2025 (p. 19-22). As duas edições só trazem a APRESENTAÇÃO da dupla
    (6 mcg + 200 mcg e 12 mcg + 400 mcg) — o que vem na caixa, não quanto se
    toma.

    Registro completo, com os verbatins e as quatro fontes:
    `docs/tickets/REGISTRO-J44-NONA-ROW-SEM-DOSE.md`.

    Esta classe é o que impede o registro de virar papel. Ela morde nos DOIS
    sentidos: se alguém escrever a row sem passar pelo arquiteto, o teste 1
    reprova; se a dose de ASMA voltar a vazar para a DPOC, o teste 2 reprova.
    """

    _PAR = "fumarato de formoterol + budesonida"

    def test_nao_existe_row_de_posologia_do_par_em_j44(self):
        """A ausência é POSIÇÃO, não lacuna — e por isso é verificada.

        Escrever esta row exige uma fonte que nenhuma das quatro consultadas é
        (PCDT 2021, PCDT 2025, GOLD 2023, GOLD 2025). Se ela aparecer, foi
        decisão de curadoria nova, e o registro precisa ser reaberto junto.
        """
        from app.domain.posologia_sugerida import carregar_posologias
        from app.domain.semaforo_decisao import canon_ativo

        caminho = Path(__file__).resolve().parents[3] / "data" / "posologia_sugerida.csv"
        idx = carregar_posologias(str(caminho))
        chave = (canon_ativo(self._PAR), "J44")
        assert chave not in idx, (
            f"apareceu uma row {chave} no posologia_sugerida.csv. Nenhuma das "
            "quatro fontes consultadas em 23-24/09 traz posologia para a dupla "
            "LABA+ICS na DPOC — ver REGISTRO-J44-NONA-ROW-SEM-DOSE.md. Se a "
            "row é legítima, ela veio de uma fonte NOVA: atualize o registro e "
            "esta guarda no mesmo PR."
        )

    def test_a_dose_de_asma_nao_vaza_para_a_dpoc(self):
        """§B.4 do despacho, a asserção que ele nomeou.

        Com o CID declarado, `sugerir` percorre a cadeia e, sem casar, devolve
        `None` — em vez de emprestar a dose de outra condição porque a
        substância é a mesma. É o silêncio honesto: a estratégia AIR/MART da
        asma não é esquema de DPOC.
        """
        from app.domain.posologia_sugerida import sugerir

        assert sugerir(self._PAR, "J44") is None, (
            "a dupla devolveu posologia em J44. Ou nasceu uma row nova (ver o "
            "teste acima), ou a chave voltou a resolver por ativo e a dose de "
            "ASMA vazou para a DPOC."
        )

    def test_a_row_de_asma_continua_intacta(self):
        """A parada não podia custar dado curado.

        O par TEM posologia — em J45, do PCDT Asma 2026. O que não existe é a
        de J44. Se a busca pela nona row tivesse mexido na row que existe, o
        preço da resposta teria sido alto demais.
        """
        from app.domain.posologia_sugerida import sugerir

        p = sugerir(self._PAR, "J45")
        assert p is not None, "a row de asma da dupla sumiu do CSV"
        assert p.codigo_cid == "J45"
        assert "MART" in p.posologia or "AIR" in p.posologia, (
            f"a row de asma mudou de conteúdo: {p.posologia!r}"
        )

    def test_sem_dose_o_semaforo_continua_verde_em_j44(self):
        """Elenco e posologia respondem perguntas DIFERENTES.

        O semáforo pergunta *"esta substância é reconhecida e está disponível
        no SUS para esta condição?"* — e a dupla está no elenco do PCDT
        (2021 §7.4 p. 15 · 2025 §7.2.1 p. 19) e na RENAME. A posologia pergunta
        *"quanto se toma?"* — e ninguém responde. Rebaixar o sinal por causa do
        silêncio da segunda pergunta seria deixar a lacuna de uma tabela
        apagar o fato da outra.
        """
        assert _av("J44", "formoterol + budesonida").sinal == SINAL_VERDE
