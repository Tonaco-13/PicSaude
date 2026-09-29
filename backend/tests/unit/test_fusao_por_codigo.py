"""
test_fusao_por_codigo.py — a fusão por código (ENG-029, degraus 1 e 2).

Anuência do assinante, 29/09/2026, verbatim: **"Mergeado 281, vamos ao
despachos degraus 1 e 2."**

O QUE ESTE ARQUIVO PROVA
------------------------
1. **Degrau 1 — o zero à esquerda.** O mapa da ANS mistura códigos SIGTAP de
   9 e 10 dígitos; o CSV da casa usa 10. Indexar com a string crua fazia
   `get("0202010317")` não achar `"202010317"` — e o resultado não era erro,
   era SILÊNCIO: dos 659 exames com par unívoco na fonte, só 96 mordiam.
2. **Degrau 2 — o sentido inverso, com colapso.** O mapa responde às duas
   perguntas; a casa fazia uma. 26 curados acharam o seu SIGTAP pelo TUSS —
   e o registro bare correspondente MORREU, em vez de conviver duplicado.
3. **Não há escolha em passo nenhum.** Ou o par é unívoco na fonte oficial,
   ou não entra. O que a ambiguidade produz é ausência, nunca palpite.

O QUE ELE NÃO PROVA, DE PROPÓSITO
----------------------------------
Nada sobre os 7 ambíguos da mesa do §6 — hemograma, glicose, T4 livre e
companhia seguem sem `codigo_sigtap` até a caneta do assinante. A guarda
`test_ambiguo_nao_entra` existe para que continuem assim.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.ai import tuss_base

_RAIZ = Path(__file__).resolve().parents[3]
_SIGTAP = _RAIZ / "data" / "sigtap_exames.csv"
_TUSS = _RAIZ / "data" / "tuss_procedimentos.csv"


def _rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _base() -> list[dict]:
    return tuss_base._construir_base()


# ---------------------------------------------------------------------------
# §5.1 — o par de 9 dígitos morde
# ---------------------------------------------------------------------------

class TestODegrau1ConsertaOIndice:

    def test_a_chave_canonica_iguala_os_dois_formatos(self):
        assert tuss_base._chave_sigtap("0202010317") == tuss_base._chave_sigtap("202010317")
        assert tuss_base._chave_sigtap("  0202010317 ") == "202010317"
        assert tuss_base._chave_sigtap(None) == ""

    def test_a_fonte_realmente_mistura_os_dois_formatos(self):
        """Sem isto, a guarda acima seria teoria: é o dado que justifica a
        normalização, e se um dia a ANS padronizar, este teste avisa."""
        comprimentos = {len(r["codigo_sigtap"]) for r in
                        _rows(_RAIZ / "data" / "tuss_sigtap_mapeamento.csv")}
        assert comprimentos == {9, 10}, comprimentos

    def test_a_creatinina_de_9_digitos_encontra_o_par(self):
        """O caso nominal do §5.1: o mapa traz `202010317` (sem o zero) e o
        catálogo traz `0202010317`. Antes do degrau 1 não se achavam."""
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        pares = mapa.get(tuss_base._chave_sigtap("0202010317"), [])
        assert {p["codigo_tuss"] for p in pares} == {"40301630"}, pares

    def test_o_piso_de_univocos_mapeados(self):
        """§5.2 — PISO, não contagem exata: não quebra quando uma competência
        nova entrar, mas pega qualquer regressão do índice (que derrubaria o
        número de 659 para 96 de uma vez)."""
        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        exames = {r["codigo_sigtap"] for r in _rows(_SIGTAP)}
        univocos = [s for s in exames
                    if len({p["codigo_tuss"]
                            for p in mapa.get(tuss_base._chave_sigtap(s), [])}) == 1]
        assert len(univocos) >= 600, (
            f"só {len(univocos)} exames com par unívoco — antes do conserto do "
            "índice eram 96. Regressão da normalização?"
        )


# ---------------------------------------------------------------------------
# §5.3 — a tabela dos 26 é fingerprint
# ---------------------------------------------------------------------------

class TestODegrau2FundeExatamenteOs26:
    """A tabela do §3 do despacho, por valor — mesma disciplina do
    `test_as_armadilhas...` do #281: o conjunto é literal para que um par
    novo aparecendo sem alguém declarar seja alarme, não conveniência."""

    OS_26 = {
        "40301150": "0202010120", "40302512": "0202010651", "40302504": "0202010643",
        "40301605": "0202010295", "40301630": "0202010317", "40901106": "0205010032",
        "40103170": "0211050040", "40302075": "0202010503", "40301583": "0202010279",
        "20102020": "0211020044", "40301591": "0202010287", "40302318": "0202010600",
        "40308391": "0202030083", "40805026": "0204030153", "41101014": "0207010064",
        "40304558": "0202020037", "40302423": "0202010635", "40316521": "0202060250",
        "41001079": "0206020031", "40302547": "0202010678", "40316556": "0202060390",
        "40901130": "0205020038", "40901122": "0205020046", "40302580": "0202010694",
        "40310213": "0202080080", "40304370": "0202020150",
    }
    # †  monodirecionais: o SIGTAP também casa com outro TUSS (ambíguo em
    #    s→t, unívoco em t→s). Fundem mesmo assim — a afirmação t→s é da
    #    fonte e não tem alternativa; não se preenche TUSS nenhum aqui.
    MONODIRECIONAIS = {"40302512", "40103170", "40302075", "20102020",
                       "41101014", "40316521", "40316556", "40901122", "40310213"}

    def _fundidos_por_codigo(self) -> dict:
        return {r["codigo_tuss"]: r["codigo_sigtap"] for r in _base()
                if "fusão por código" in (r.get("fonte") or "")}

    def test_os_26_pares_sao_exatamente_os_declarados(self):
        obtido = self._fundidos_por_codigo()
        assert obtido == self.OS_26, (
            f"faltam: {sorted(set(self.OS_26) - set(obtido))} | "
            f"sobram: {sorted(set(obtido) - set(self.OS_26))} | "
            f"divergem: {sorted(k for k in self.OS_26 if obtido.get(k) not in (None, self.OS_26[k]))}"
        )

    def test_os_9_monodirecionais_fundiram(self):
        """A assimetria é registrada, não evitada: a urocultura é o exemplo
        canônico — TUSS "cultura de urina" aponta para o SIGTAP genérico
        "cultura de bactérias p/ identificação", que também recebe outro TUSS.
        """
        obtido = self._fundidos_por_codigo()
        for tuss in self.MONODIRECIONAIS:
            assert tuss in obtido, f"o monodirecional {tuss} não fundiu"

    def test_a_fonte_do_registro_conta_que_foi_fusao_por_codigo(self):
        for reg in _base():
            if reg["codigo_tuss"] in self.OS_26 and reg.get("codigo_sigtap"):
                fonte = reg["fonte"]
                assert "fusão por código" in fonte and "ANS 2017-04" in fonte, fonte


# ---------------------------------------------------------------------------
# §5.7 — o colapso é colapso
# ---------------------------------------------------------------------------

class TestOColapsoNaoDeixaOrfa:

    def test_a_cardinalidade_caiu_em_26(self):
        """26 fusões, não 26 fusões + 26 órfãs. Se o colapso não acontecesse,
        o mesmo procedimento existiria duas vezes no catálogo — uma com
        preparo e alertas, outra sem."""
        # ENG-030: 1.114 -> 1.109. Os 26 colapsos do ENG-029 continuam lá; os
        # 5 novos são da caneta dos 8 (6 pares fundem, e o TC crânio já
        # estava fundido por nome — a caneta dele foi confirmação).
        assert len(_base()) == 1109, len(_base())

    def test_nenhum_codigo_sigtap_aparece_em_dois_registros(self):
        vistos: dict[str, str] = {}
        for r in _base():
            c = r.get("codigo_sigtap")
            if not c:
                continue
            assert c not in vistos, (
                f"{c} aparece em '{vistos[c]}' E em '{r['nome_padrao']}' — "
                "o colapso não removeu a linha bare"
            )
            vistos[c] = r["nome_padrao"]

    def test_todo_tuss_repetido_e_repetido_PELA_FONTE(self):
        """Aqui a asserção óbvia está ERRADA, e vale dizer por quê.

        "Nenhum código TUSS aparece em dois registros" parece o espelho da
        guarda acima — mas reprova, e reprova com razão: **47 códigos TUSS
        aparecem em 2 registros cada**, e nos 47 é o MAPA OFICIAL que os põe
        ali. A metodologia da ANS (item 3) diz que o mapeamento é de um ou
        vários para um ou vários, nos dois sentidos: o TUSS "dosagem de
        fosfatase alcalina" cobre o SIGTAP simples E o "no esperma"; a
        "osmolaridade" cobre o clearance osmolar E a determinação.

        Repetir o TUSS aí é FIDELIDADE, não duplicação — e é assimétrico com
        o SIGTAP de propósito: um exame do SUS tem um código do SUS (por isso
        a guarda acima é absoluta), mas pode não ter um equivalente exato na
        saúde suplementar.

        O que a guarda afirma, então, não é ausência de repetição: é que
        **toda repetição tem origem na fonte**. Um TUSS duplicado que o mapa
        não justifique seria defeito nosso, e é o que ela pega.
        """
        import collections

        por_tuss = collections.defaultdict(list)
        for r in _base():
            if r.get("codigo_tuss"):
                por_tuss[r["codigo_tuss"]].append(r["nome_padrao"])
        repetidos = {k: v for k, v in por_tuss.items() if len(v) > 1}

        mapa = tuss_base._carregar_mapa_tuss_sigtap(tuss_base._resolver_tuss_mapa_csv())
        destinos = collections.defaultdict(set)
        for chave, pares in mapa.items():
            for par in pares:
                destinos[par["codigo_tuss"]].add(chave)

        sem_causa = {k: v for k, v in repetidos.items() if len(destinos.get(k, ())) < 2}
        assert not sem_causa, (
            f"código(s) TUSS repetido(s) sem a fonte justificar: {sem_causa}"
        )

    def test_as_contagens_do_despacho(self):
        b = _base()
        fundidos = [r for r in b if r.get("codigo_sigtap") and r.get("codigo_tuss")]
        so_tuss = [r for r in b if r.get("codigo_tuss") and not r.get("codigo_sigtap")]
        so_sigtap = [r for r in b if r.get("codigo_sigtap") and not r.get("codigo_tuss")]
        # ENG-030: 669/9/436 -> 671/4/434. O salto é pequeno DE PROPÓSITO —
        # em 4 dos 6 pares o SIGTAP já morava numa linha bare, e o que a
        # caneta faz é transferir o dono: ele passa para o registro que tem
        # aliases, preparo e alertas. O ganho é o par viajar junto da
        # curadoria, não o número (§4 do ENG-030).
        assert (len(fundidos), len(so_tuss), len(so_sigtap)) == (671, 4, 434), (
            f"fundidos={len(fundidos)} só-TUSS={len(so_tuss)} "
            f"só-SIGTAP={len(so_sigtap)}; o ENG-030 declara 671/4/434"
        )


# ---------------------------------------------------------------------------
# §5.6 — o alias absorvido
# ---------------------------------------------------------------------------

def test_a_creatinina_responde_pelo_nome_do_sigtap():
    """Quem buscava "dosagem de creatinina" caía na linha bare. A linha morreu
    — e a busca tem de continuar achando, agora no registro curado, que traz
    preparo e alertas junto. Sem isto, o colapso seria perda de função."""
    reg = next(r for r in _base() if r["nome_busca"] == "creatinina")
    assert reg["codigo_sigtap"] == "0202010317"
    assert "dosagem de creatinina" in reg["aliases"]
    assert reg["preparo"], "o registro curado perdeu o preparo no colapso"


# ---------------------------------------------------------------------------
# §5.4 — ambíguo NÃO entra
# ---------------------------------------------------------------------------

class TestOAmbiguoNaoEntra:
    """A mesa do §6 continua aberta, e é isto que a mantém aberta.

    Sete casos são escolha CLÍNICA, não de engenharia — hemograma (o completo
    já traz plaquetas? então contar plaquetas à parte é duplo faturamento),
    glicose (jejum ou líquido sinovial), T4 livre (dosagem ou índice), urina
    tipo I (EAS ou contagem global), parasitológico (ovos/cistos ou larvas),
    RM lombossacra (lombar ou cervical). Nenhum entra até a caneta.
    """

    # ENG-030 (29/09) — A MESA FECHOU, e esta lista é a digital da caneta.
    #
    # Ela existia para manter os 7 ambíguos SEM `codigo_sigtap` até alguém
    # assinar qual deles era. O assinante assinou ("Hemograma casa com o
    # COMPLETO · Glicose do jejum · T4 por dosagem..."), e os sete saíram
    # daqui — cada um com o fundamento citado em `_CANETA_SIGTAP`.
    #
    # A lista NÃO ficou vazia, e é por isso que ela continua existindo: os
    # quatro que sobram não têm destino no mapa de 2017-04. Não é escolha
    # pendente — é ausência na fonte, e não se inventa par.
    SEM_SIGTAP = ("coagulograma (tap + ttpa + fibrinogênio)",
                  "tomografia computadorizada do abdome",
                  "coprocultura com antibiograma",
                  "ultrassonografia obstétrica (morfológica)")

    def test_os_ambiguos_seguem_sem_codigo_sigtap(self):
        por_nome = {r["nome_padrao"].lower(): r for r in _base()}
        for nome in self.SEM_SIGTAP:
            reg = por_nome.get(nome)
            assert reg is not None, f"sumiu o registro {nome!r}"
            assert not reg.get("codigo_sigtap"), (
                f"{nome} ganhou SIGTAP sem caneta. Os quatro que restam não "
                "têm par no mapa de 2017-04 — a porta é fonte mais nova, não "
                "escolha (§6 do ENG-030)."
            )

    def test_o_codigo_recusa_o_ambiguo_por_construcao(self):
        """Não é sorte: é `len(presentes) != 1 → continue`, nos dois sentidos."""
        fonte = (_RAIZ / "backend" / "app" / "ai" / "tuss_base.py").read_text(
            encoding="utf-8")
        assert "if len(codigos) != 1:" in fonte      # sentido direto
        assert "if len(presentes) != 1:" in fonte    # sentido inverso


# ---------------------------------------------------------------------------
# §5.5 — o TUSS que o mapa aponta é vigente na Tabela 22
# ---------------------------------------------------------------------------

def test_nenhum_par_aponta_tuss_morto():
    """Guarda NOVA: hoje são 0, e ela existe para o dia em que um mapa mais
    novo apontar código já encerrado. Sem ela, a fusão traria para o catálogo
    um código que a ANS aposentou — e o faturamento só descobriria no balcão.
    """
    vigentes = {r["codigo_tuss"] for r in _rows(_TUSS)
                if not (r["vigencia_fim"] or "").strip()}
    mortos = []
    for reg in _base():
        c = reg.get("codigo_tuss")
        if c and c not in vigentes:
            mortos.append((reg["nome_padrao"], c))
    assert not mortos, f"registros com TUSS não vigente: {mortos}"
