"""
test_semaforo_espelhos_2026_09.py — os dois ESPELHOS da caneta de 28/09.

ENG-026, martelo do Fabiano, verbatim: **"A1 fora · A2 espelha F00 · A3 mantém
· A4 espelha A52 em A53 · A5 mantém · A6 volta às 8 rows · K21 por diretriz ·
E03 semente."** Deste martelo saíram três gestos de dado; dois deles são
espelhos, e é o que este arquivo guarda.

O QUE É UM ESPELHO, E POR QUE ELE PRECISA DE GUARDA PRÓPRIA
-----------------------------------------------------------
A cadeia do semáforo sobe de subcategoria para categoria (`A53.0` → `A53`),
mas **não atravessa categorias**: quem codifica `F00` não alcança `G30`, e
quem codifica `A53` não alcança `A52`. São códigos irmãos, não pai e filho.

Quando o mesmo elenco clínico vale nos dois, a única forma de o prescritor
receber o mesmo sinal nos dois caminhos de codificação é **escrever as rows
duas vezes**. Isso cria uma duplicação real — e duplicação sem guarda é
divergência marcada para acontecer: alguém corrige a dose de um lado, não vê
o outro, e o sistema passa a dar duas respostas para a mesma pergunta clínica.

Por isso o espelho não é "duas curadorias": é **uma curadoria copiada com
prova de igualdade**. A guarda abaixo é essa prova. Se os lados derivarem —
por edição, por caneta nova, por merge desatento —, ela reprova antes que a
tela mostre duas verdades.

> A `_REPETE_POR_PROTOCOLO` do `test_semaforo_flip_j44_i50.py` também admite
> estes seis ativos, mas por outro motivo e com outra força: lá a afirmação é
> só *"a repetição é declarada"*. A afirmação forte — *"os textos são
> IDÊNTICOS, caractere a caractere"* — mora aqui.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.posologia_sugerida import sugerir
from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_VERDE,
    avaliar_semaforo,
    canon_ativo,
    carregar_regras,
)

_CSV = Path(__file__).resolve().parents[3] / "data" / "decisao_semaforo.csv"


def _carregar():
    return carregar_regras(str(_CSV))


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = _carregar()
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


def _elenco(cid: str) -> set[str]:
    aprovados, _ex, _p = _carregar()
    return {a for (c, a) in aprovados if c == cid}


class TestOEspelhoF00:
    """A2 — `F00` (demência NA doença de Alzheimer) espelha `G30`.

    O PCDT de Alzheimer é um só e serve as duas codificações; o prescritor
    escolhe entre "a doença" e "a demência na doença" conforme o caso, e
    nenhuma das duas escolhas deveria deixá-lo sem sinal.
    """

    ELENCO = ("donepezila", "galantamina", "rivastigmina", "memantina")

    def test_o_elenco_e_exatamente_o_mesmo(self):
        assert _elenco("F00") == _elenco("G30"), (
            "o espelho F00 derivou do G30 no ELENCO — um dos dois ganhou ou "
            "perdeu fármaco sozinho"
        )
        assert _elenco("F00") == {canon_ativo(a) for a in self.ELENCO}

    def test_os_quatro_acendem_verde_nos_dois_codigos(self):
        for ativo in self.ELENCO:
            for cid in ("F00", "G30"):
                assert _av(cid, ativo).sinal == SINAL_VERDE, (cid, ativo)

    def test_a_posologia_e_identica_caractere_a_caractere(self):
        for ativo in self.ELENCO:
            f00, g30 = sugerir(ativo, "F00"), sugerir(ativo, "G30")
            assert f00 is not None and g30 is not None, ativo
            assert f00.posologia == g30.posologia, (
                f"a posologia de {ativo} DIVERGIU entre F00 e G30. Espelho que "
                "deriva é duas verdades para a mesma pergunta — corrija os dois "
                "lados no mesmo PR."
            )

    def test_a_subcategoria_do_f00_casa_na_categoria(self):
        """O espelho é no nível da categoria; as subcategorias sobem por cadeia."""
        for sub in ("F00.0", "F00.1", "F00.2", "F00.9"):
            assert _av(sub, "donepezila").sinal == SINAL_VERDE, sub

    def test_o_espelho_nao_afrouxou_o_amarelo(self):
        """Copiar o elenco não pode copiar permissividade: fora dele, 🟡."""
        for cid in ("F00", "G30"):
            a = _av(cid, "rivaroxabana")
            assert a.sinal == SINAL_AMARELO and a.causa == "ausente_lista_exaustiva", cid

    def test_a_proveniencia_diz_que_e_alias(self):
        """Quem ler a row precisa saber que ela nasceu de uma caneta de espelho,
        não de uma segunda leitura do protocolo."""
        aprovados, _e, _p = _carregar()
        fonte = aprovados[("F00", "donepezila")].fonte
        assert "alias F00<-G30" in fonte and "28/09" in fonte, fonte
        assert aprovados[("F00", "donepezila")].versao == "semaforo_f00_alias_v1_2026-09"


class TestOEspelhoA53:
    """A4 — `A53` espelha `A52`, com o esquema TARDIO.

    Não é simetria automática: é o que o Quadro 15 do PCDT IST 2021 (p. 23-24)
    manda. Ele define sífilis tardia como *"sífilis latente tardia (com mais de
    um ano de evolução) **ou latente com duração ignorada** e sífilis
    terciária"* — e `A53.0` é, na CID-10, *"sífilis latente, não especificada
    se recente ou tardia"*. A duração ignorada É o caso tardio, por decisão do
    protocolo, e por isso o espelho copia o A52 e nunca o A51.
    """

    ELENCO = ("benzilpenicilina benzatina", "doxiciclina")

    def test_o_elenco_e_exatamente_o_mesmo_do_a52(self):
        assert _elenco("A53") == _elenco("A52")
        assert _elenco("A53") == {canon_ativo(a) for a in self.ELENCO}

    def test_a_posologia_e_a_TARDIA_e_nao_a_recente(self):
        """A afirmação clínica do espelho, e a que erraria feio se invertida."""
        for ativo in self.ELENCO:
            a53, a52, a51 = (sugerir(ativo, c) for c in ("A53", "A52", "A51"))
            assert a53 is not None and a52 is not None and a51 is not None, ativo
            assert a53.posologia == a52.posologia, (
                f"{ativo}: o espelho A53 derivou do A52"
            )
            assert a53.posologia != a51.posologia, (
                f"{ativo}: o A53 recebeu o esquema RECENTE. O Quadro 15 trata "
                "duração ignorada como TARDIA — subtratar sífilis tardia com "
                "dose única é erro clínico, não detalhe de dado."
            )

    def test_o_esquema_tardio_e_o_de_tres_semanas(self):
        """Ancorado no texto, não só na igualdade entre CIDs."""
        benz = sugerir("benzilpenicilina benzatina", "A53").posologia
        assert "3 semanas" in benz and "7,2 milhões UI" in benz, benz
        doxi = sugerir("doxiciclina", "A53").posologia
        assert "30 dias" in doxi, doxi

    def test_as_subcategorias_do_a53_casam_na_categoria(self):
        for sub in ("A53.0", "A53.9"):
            for ativo in self.ELENCO:
                assert _av(sub, ativo).sinal == SINAL_VERDE, (sub, ativo)

    def test_o_espelho_nao_trouxe_o_que_nao_e_da_sifilis(self):
        for ativo in ("azitromicina", "ceftriaxona", "metronidazol"):
            assert _av("A53", ativo).sinal == SINAL_AMARELO, ativo

    def test_a_proveniencia_diz_que_e_alias_e_por_que(self):
        aprovados, _e, _p = _carregar()
        fonte = aprovados[("A53", "benzilpenicilina benzatina")].fonte
        assert "alias A53<-A52" in fonte and "28/09" in fonte, fonte
        assert "duração ignorada" in fonte, (
            "a fonte não registra o CRITÉRIO clínico do espelho — sem ele, a "
            "row parece simetria arbitrária entre códigos vizinhos"
        )
        assert aprovados[("A53", "benzilpenicilina benzatina")].versao == (
            "semaforo_a53_alias_v1_2026-09"
        )


def test_os_dois_espelhos_entraram_no_conjunto_exaustivo():
    _ap, exaustivos, _p = _carregar()
    assert {"F00", "A53"} <= exaustivos, (
        "espelho sem exaustividade é row que não julga nada — o portão da "
        "exaustividade calaria o sinal que a caneta quis dar"
    )
