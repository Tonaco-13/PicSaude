"""
test_tuss_base_oficial.py — a TUSS ganha fonte (ENG-027 §2.4).

Martelo do Fabiano, 28/09/2026, verbatim: **"vamos ter que montar um hiper
intensivo começando agora para TUSS e Sigtap, para merge do engenheiro até
amanhã às 11;00 de recife."**

O QUE ESTE ARQUIVO PROVA
------------------------
1. A Tabela 22 oficial da ANS está carregada, com contagem e versão
   declaradas — e **linha sem fonte reprova** (AC1).
2. O mapeamento TUSS↔SIGTAP é o **oficial da ANS**, não heurística de nome;
   par declarado sobrevive ao reload, e par fabricado reprova (AC2).
3. A curadoria de `_BASE_RAW` **sobreviveu inteira** — aliases, preparo e
   alertas seguem servindo, que é o que o despacho mandou preservar.
4. A reconciliação contra a fonte está **medida e travada** — 36 dos 38
   códigos curados não correspondem ao exame que nomeiam, e esse número é
   fato cobrado pelo gate até alguém canetar (`RELATORIO-TUSS-RECONCILIACAO.md`).

POR QUE O MAPEAMENTO NÃO É POR NOME
------------------------------------
O ticket previa casar TUSS e SIGTAP por nome normalizado. Não foi preciso: a
ANS publica o mapeamento oficial, feito com o MS, com **grau de equivalência
declarado** (1 a 5). Fonte primária ganha de heurística nossa — e evita
exatamente a armadilha que a sabotagem do AC2 persegue: dois procedimentos
cujos nomes começam igual ("biópsia de…") não são o mesmo exame.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_TUSS = _RAIZ / "data" / "tuss_procedimentos.csv"
_MAPA = _RAIZ / "data" / "tuss_sigtap_mapeamento.csv"
_SIGTAP = _RAIZ / "data" / "sigtap_exames.csv"
_MODULO = _RAIZ / "backend" / "app" / "ai" / "tuss_base.py"

_VERSAO = "ANS-TISS 2017-04 (TUSS 22 competência 201606)"


def _rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# AC1 — o loader TUSS: contagem e versão declaradas; linha sem fonte reprova
# ---------------------------------------------------------------------------

class TestABaseOficialExiste:

    def test_a_tabela_22_esta_no_disco_com_volume_de_tabela_inteira(self):
        rows = _rows(_TUSS)
        assert len(rows) == 5755, (
            f"a Tabela 22 tem {len(rows)} linhas, esperado 5755. Se a fonte "
            "mudou, rode o script de import e atualize este número junto — "
            "contagem que ninguém declara envelhece em silêncio."
        )

    def test_toda_linha_declara_fonte_e_versao(self):
        """AC1, a asserção literal do despacho: linha sem fonte reprova."""
        for i, r in enumerate(_rows(_TUSS), start=2):
            assert (r.get("fonte") or "").strip(), f"linha {i} sem fonte"
            assert r.get("versao_snapshot") == _VERSAO, (
                f"linha {i} com versão {r.get('versao_snapshot')!r}"
            )

    def test_a_idade_da_fonte_esta_declarada_na_propria_row(self):
        """A régua da ITU 2003 e da AMB 2008: fonte velha entra DECLARADA.

        A Tabela 22 deste pacote é da competência 201606. Quem ler uma row
        precisa saber disso sem abrir o MANIFEST — senão lê como corrente.
        """
        primeira = _rows(_TUSS)[0]
        assert "201606" in primeira["versao_snapshot"]
        assert "2017-04" in primeira["fonte"] or "2017-04" in primeira["versao_snapshot"]

    def test_o_codigo_tuss_e_numerico_e_o_termo_nao_e_vazio(self):
        for i, r in enumerate(_rows(_TUSS), start=2):
            assert r["codigo_tuss"].isdigit(), f"linha {i}: {r['codigo_tuss']!r}"
            assert r["termo"].strip(), f"linha {i} sem termo"

    def test_nao_ha_codigo_repetido(self):
        codigos = [r["codigo_tuss"] for r in _rows(_TUSS)]
        assert len(codigos) == len(set(codigos))


# ---------------------------------------------------------------------------
# AC2 — o mapeamento é OFICIAL; par declarado sobrevive, par fabricado reprova
# ---------------------------------------------------------------------------

class TestOMapeamentoEOficial:

    def test_o_mapeamento_tem_volume_e_grau_declarado(self):
        rows = _rows(_MAPA)
        assert len(rows) == 4270, f"{len(rows)} pares, esperado 4270"
        graus = {r["grau_equivalencia"] for r in rows}
        # "dúvida" é valor da PRÓPRIA ANS, não sujeira: a metodologia avisa que
        # "alguns mapeamentos ainda não estão com o grau atribuído", e em parte
        # das linhas a autoridade escreveu a hesitação com todas as letras.
        # Normalizar para vazio esconderia que quem mapeou ficou em dúvida.
        assert graus <= {"", "1", "2", "3", "4", "5", "dúvida"}, graus
        assert "dúvida" in graus, (
            "sumiu o grau 'dúvida' do mapeamento — se o importador passou a "
            "normalizá-lo, a hesitação da fonte deixou de chegar a quem fatura"
        )
        for r in rows:
            if r["grau_equivalencia"]:
                assert r["grau_descricao"], (
                    f"par {r['codigo_tuss']}→{r['codigo_sigtap']} tem grau "
                    "sem descrição — grau sem legenda é número solto"
                )

    def test_toda_ponta_do_par_existe_na_sua_tabela(self):
        """Par que aponta para código inexistente é par fabricado."""
        tuss = {r["codigo_tuss"] for r in _rows(_TUSS)}
        orfaos = {r["codigo_tuss"] for r in _rows(_MAPA)} - tuss
        assert not orfaos, (
            f"{len(orfaos)} códigos TUSS do mapeamento não estão na Tabela 22: "
            f"{sorted(orfaos)[:5]}"
        )

    def test_o_par_declarado_sobrevive_ao_reload(self):
        """AC2 — a base reconstruída devolve o MESMO par, não um par novo."""
        from app.ai import tuss_base

        primeira = tuss_base._construir_base()
        segunda = tuss_base._construir_base()
        pares_1 = {(r["codigo_sigtap"], r["codigo_tuss"]) for r in primeira
                   if r.get("codigo_sigtap") and r.get("codigo_tuss")}
        pares_2 = {(r["codigo_sigtap"], r["codigo_tuss"]) for r in segunda
                   if r.get("codigo_sigtap") and r.get("codigo_tuss")}
        assert pares_1 == pares_2 and pares_1, "o par mudou entre dois reloads"

    def test_so_entra_par_UNIVOCO_no_registro(self):
        """Onde a ANS mapeia o mesmo SIGTAP para vários TUSS, escolher um
        seria inventar precisão que a fonte não tem. Fica sem par."""
        from app.ai import tuss_base

        mapa: dict[str, set[str]] = {}
        for r in _rows(_MAPA):
            mapa.setdefault(r["codigo_sigtap"], set()).add(r["codigo_tuss"])
        ambiguos = {k for k, v in mapa.items() if len(v) > 1}
        assert ambiguos, "sem caso ambíguo, esta guarda não exerce nada"

        for reg in tuss_base._construir_base():
            sig = reg.get("codigo_sigtap")
            if sig in ambiguos and "mapeamento oficial" in (reg.get("fonte") or ""):
                pytest.fail(
                    f"{sig} tem {len(mapa[sig])} códigos TUSS na fonte e mesmo "
                    "assim recebeu um — a base escolheu por conta própria"
                )

    def test_o_mapeamento_nao_e_por_nome(self):
        """A prova de que a fonte é a ANS, e não uma heurística nossa.

        Se fosse casamento por nome, os pares teriam nomes parecidos. O
        mapeamento oficial mapeia 'Consulta em consultório' para 'CONSULTA AO
        PACIENTE CURADO DE TUBERCULOSE' com grau 3 (TUSS menos específico) —
        nenhuma heurística de nome produziria isso, e é justamente o tipo de
        relação que só quem conhece as duas tabelas declara.
        """
        modulo = _MODULO.read_text(encoding="utf-8")
        assert "_carregar_mapa_tuss_sigtap" in modulo
        assert "mapeamento oficial" in modulo
        pares = _rows(_MAPA)
        com_grau_3_ou_4 = [p for p in pares if p["grau_equivalencia"] in ("3", "4")]
        assert len(com_grau_3_ou_4) > 100, (
            "quase nenhum par com equivalência parcial declarada — suspeito de "
            "mapeamento por nome disfarçado de oficial"
        )


# ---------------------------------------------------------------------------
# AC3 — a curadoria NÃO foi apagada; virou camada por cima
# ---------------------------------------------------------------------------

class TestACuradoriaSobreviveu:

    def test_os_38_curados_seguem_na_base_com_aliases_e_preparo(self):
        from app.ai import tuss_base

        base = tuss_base._construir_base()
        curados = [r for r in base if r.get("aliases") or r.get("preparo")]
        assert len(curados) >= 35, (
            f"só {len(curados)} registros ainda têm curadoria — a camada de "
            "enriquecimento foi perdida no caminho"
        )
        # Atenção à armadilha: existe um "HEMOGRAMA COMPLETO" vindo SÓ do
        # SIGTAP (0202020380), sem curadoria. O que se quer aqui é a entrada
        # CURADA — a que carrega aliases e preparo.
        hemograma = next((r for r in base
                          if "hemograma" in r["nome_busca"] and r.get("aliases")), None)
        assert hemograma, "a entrada CURADA do hemograma sumiu da base"
        assert hemograma["aliases"], "o hemograma perdeu os aliases"

    def test_os_exames_que_so_tinham_sigtap_ganharam_tuss_oficial(self):
        """O ganho concreto desta PR: antes, 1.105 procedimentos de exame
        nasciam com `codigo_tuss: None` e o faturamento pelo código da saúde
        suplementar não tinha de onde sair."""
        from app.ai import tuss_base

        base = tuss_base._construir_base()
        oficiais = [r for r in base
                    if "mapeamento oficial" in (r.get("fonte") or "")]
        assert len(oficiais) == 95, (
            f"{len(oficiais)} registros receberam TUSS oficial, esperado 95. "
            "Se a fonte mudou, atualize este número como ato declarado."
        )
        for r in oficiais:
            assert r["codigo_tuss"] and r["codigo_sigtap"]

    def test_a_fonte_de_cada_registro_conta_de_onde_ele_veio(self):
        from app.ai import tuss_base

        for r in tuss_base._construir_base():
            fonte = r.get("fonte") or ""
            assert fonte, f"{r['nome_padrao']} sem fonte"
            assert ("TUSS/BASE_LOCAL" in fonte or "SIGTAP/DATASUS" in fonte), fonte


# ---------------------------------------------------------------------------
# AC4/§5 — a reconciliação está MEDIDA, e o número é fato até alguém canetar
# ---------------------------------------------------------------------------

class TestAReconciliacaoEstaMedida:
    """O achado do ENG-027, travado para não virar papel.

    36 dos 38 códigos TUSS de `_BASE_RAW` não correspondem ao exame que
    nomeiam — e um dos 2 que "existem" é o pior caso: `40301079` é válido na
    Tabela 22, mas significa "Ácido beta hidroxi butírico", não hemograma.
    Código inexistente é rejeitado e aparece; código válido apontando para
    outro exame fatura errado em silêncio.

    **Nada foi corrigido nesta PR** — trocar código de faturamento é caneta
    do Fabiano. O que a guarda faz é impedir que o número mude sem alguém
    declarar, nos dois sentidos: se a curadoria for corrigida, esta guarda
    reprova e o PR que a corrigir terá de dizer o que fez.
    """

    def _curados(self) -> list[tuple[str, str]]:
        src = _MODULO.read_text(encoding="utf-8")
        return re.findall(r'"codigo_tuss":\s*"(\d+)".*?"nome_padrao":\s*"([^"]+)"',
                          src, re.S)

    def test_a_contagem_da_divergencia_e_a_do_relatorio(self):
        oficiais = {r["codigo_tuss"] for r in _rows(_TUSS)}
        curados = self._curados()
        assert len(curados) == 38, f"{len(curados)} códigos curados"
        ausentes = [c for c, _n in curados if c not in oficiais]
        assert len(ausentes) == 36, (
            f"{len(ausentes)} códigos curados fora da Tabela 22, esperado 36. "
            "Mudou para menos? alguém corrigiu — atualize o "
            "RELATORIO-TUSS-RECONCILIACAO.md no mesmo PR."
        )

    def test_o_caso_do_hemograma_esta_nomeado(self):
        """O pior caso, com nome e número, para não se perder no agregado."""
        por_cod = {r["codigo_tuss"]: r["termo"] for r in _rows(_TUSS)}
        assert "40301079" in por_cod, "o código do caso mudou de situação"
        assert "hidroxi butírico" in por_cod["40301079"].lower(), por_cod["40301079"]
        curados = dict((c, n) for c, n in self._curados())
        assert "Hemograma" in curados.get("40301079", ""), (
            "a curadoria não usa mais 40301079 para hemograma — se foi "
            "corrigido, este teste é o lugar de registrar"
        )

    def test_o_relatorio_existe_e_aponta_a_guarda(self):
        rel = _RAIZ / "docs" / "tickets" / "RELATORIO-TUSS-RECONCILIACAO.md"
        assert rel.exists()
        txt = rel.read_text(encoding="utf-8")
        assert "40301079" in txt and "40304361" in txt
        assert "test_tuss_base_oficial.py" in txt


# ---------------------------------------------------------------------------
# AC3 (regressão) — o SIGTAP não foi mexido; a competência continua a 202606
# ---------------------------------------------------------------------------

def test_o_sigtap_continua_na_competencia_202606():
    """§1 do despacho: NÃO houve refresh — 202606 é o teto publicado no canal
    oficial, conferido em 28/09. Fabricar competência que não existe é o erro
    que o registro existe para não cometer."""
    competencias = {r["competencia"] for r in _rows(_SIGTAP)}
    assert competencias == {"202606"}, competencias

    manifest = (_RAIZ / "data" / "fontes-oficiais" / "sigtap" / "MANIFEST.md"
                ).read_text(encoding="utf-8")
    assert "202606 é a competência mais nova PUBLICADA" in manifest, (
        "o MANIFEST perdeu a nota de teto — sem ela, a próxima rodada volta a "
        "chamar o SIGTAP de defasado sem conferir a fonte"
    )


def test_o_manifest_do_tuss_declara_sha256_e_procedencia():
    """AC4 — TUSS com sha256 + proveniência (oficial ou espelho-declarado)."""
    manifest = (_RAIZ / "data" / "fontes-oficiais" / "tuss" / "MANIFEST.md"
                ).read_text(encoding="utf-8")
    assert "b365e36dbace8fea6f2984e69a26c0fbfeed801bca1b6a13f0a8520e8c84662a" in manifest
    assert "Fonte OFICIAL" in manifest and "gov.br/ans" in manifest
    assert "IDADE DECLARADA" in manifest, (
        "o MANIFEST não declara que a fonte é de 2017/competência 201606"
    )
