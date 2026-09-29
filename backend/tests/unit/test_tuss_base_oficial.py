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

class TestACanetaDos38:
    """A guarda VIROU com a caneta — ENG-028, 28/09/2026.

    A versão anterior (#279) travava a DIVERGÊNCIA: "36 dos 38 códigos curados
    não existem na Tabela 22, e não mexa nisso sem declarar". Era o certo
    enquanto a decisão era do Fabiano: a engenharia media e devolvia.

    A caneta veio, verbatim: *"As 27 diretas entram · Glicose pura · TGP geral
    · US total · US superior · ECG convencional · Holter digital · PCR
    quantitativa · Coprocultura padrão · Coagulograma oficial com nota · TC
    abdome total · seed alinha aos mesmos"*. Os 38 foram trocados.

    Então a guarda inverte de sentido, e a inversão é a digital da caneta no
    teste: de *"a divergência tem 36 e não mude sem dizer"* para **"não existe
    mais divergência — todo código curado é oficial"**. Quem reintroduzir um
    código inventado reprova aqui.
    """

    def _curados(self) -> list[tuple[str, str]]:
        src = _MODULO.read_text(encoding="utf-8")
        return re.findall(r'"codigo_tuss":\s*"(\d+)".*?"nome_padrao":\s*"([^"]+)"',
                          src, re.S)

    def test_todos_os_38_curados_sao_oficiais(self):
        """O inverso exato da guarda anterior: a divergência é ZERO."""
        oficiais = {r["codigo_tuss"] for r in _rows(_TUSS)}
        curados = self._curados()
        assert len(curados) == 38, f"{len(curados)} códigos curados"
        ausentes = [(c, n) for c, n in curados if c not in oficiais]
        assert not ausentes, (
            f"{len(ausentes)} código(s) curado(s) fora da Tabela 22: {ausentes}. "
            "Depois do ENG-028 nenhum código de _BASE_RAW pode ser inventado — "
            "se a fonte mudou, rode o import; se é código novo, ele precisa de "
            "caneta como os 38 tiveram."
        )

    def test_os_dois_validos_errados_foram_corrigidos(self):
        """Os dois casos que faturavam outro exame EM SILÊNCIO.

        Eram os piores justamente por serem válidos: código inexistente é
        rejeitado e o erro aparece; estes passavam. São os que a boundary de
        28/09 mandou não deixar passar a semana.
        """
        curados = dict((c, n) for c, n in self._curados())
        por_cod = {r["codigo_tuss"]: r["termo"] for r in _rows(_TUSS)}

        assert "40301079" not in curados, (
            "o hemograma voltou a 40301079, que é 'Ácido beta hidroxi butírico'"
        )
        assert "Hemograma" in curados.get("40304361", ""), curados.get("40304361")
        assert "hemograma" in por_cod["40304361"].lower()

        assert "40308030" not in curados, (
            "o PCR voltou a 40308030, que é 'Fator reumatóide, teste do látex'"
        )
        assert "Proteína C Reativa" in curados.get("40308391", ""), curados.get("40308391")
        assert "proteína c reativa" in por_cod["40308391"].lower()

    def test_as_micro_decisoes_da_caneta_estao_no_codigo(self):
        """As cinco do §3 do despacho, uma a uma — é onde a caneta escolheu
        entre dois códigos oficiais, e onde um "conserto" distraído erraria."""
        curados = dict((c, n) for c, n in self._curados())
        por_cod = {r["codigo_tuss"]: r["termo"] for r in _rows(_TUSS)}

        # 1. PCR quantitativa, não qualitativa
        assert "40308391" in curados and "quantitativa" in por_cod["40308391"]
        # 2. Holter digital 3 canais, não analógico
        assert "40311071" not in curados and "20102020" in curados
        assert "digital" in por_cod["20102020"]
        # 3. TC abdome TOTAL, não superior
        assert "41001095" in curados and "Abdome total" in por_cod["41001095"]
        assert "41001109" not in curados, "entrou o TC de abdome SUPERIOR"
        # 4. Coprocultura padrão, não ampliada
        assert "40310183" in curados and "40310175" not in curados
        # 5. Coagulograma oficial (não None)
        assert "40304922" in curados and "Coagulograma" in por_cod["40304922"]

    def test_as_armadilhas_que_o_arquiteto_rejeitou_nao_entraram(self):
        """As seis sugestões do relatório que eram armadilha.

        O relatório candidatou por SOBREPOSIÇÃO DE STRING, e string não é
        identidade: "Holter 24h" bate 75% com "HOLTER CEREBRAL". O arquiteto
        reabriu contra a fonte e rejeitou as seis. Esta guarda é o que impede
        que elas voltem por um "conserto" que confie no relatório em vez do
        despacho.
        """
        curados = {c for c, _n in self._curados()}
        armadilhas = {
            "20102135": "Holter CEREBRAL no lugar do cardíaco",
            "40901114": "US de MAMAS no lugar do abdome total",
            "41001109": "TC no lugar da US de abdome superior",
            "40101029": "ECG de ALTA RESOLUÇÃO no lugar do convencional",
            "40403840": "TGP HEMOTERÁPICO no lugar do geral",
            "40302032": "glicemia PÓS-SOBRECARGA no lugar da glicose de jejum",
        }
        entraram = {c: p for c, p in armadilhas.items() if c in curados}
        assert not entraram, f"armadilha(s) do relatório entraram: {entraram}"

    def test_a_divergencia_de_escopo_virou_alerta_onde_muda_o_faturamento(self):
        """Nem toda divergência entre nome curado e termo oficial é alerta.

        A maioria é nomenclatura (TGO vira "transaminase oxalacética") e vive
        em `termo_oficial`. Viram ALERTA só as três em que o escopo oficial
        entrega MENOS do que o nome curado promete — e nessas o que falta
        fatura à parte, que é dinheiro e é surpresa no balcão.
        """
        from app.ai import tuss_base

        por_cod = {r["codigo_tuss"]: r for r in tuss_base._BASE_RAW}
        coag = " ".join(por_cod["40304922"]["alertas_base"])
        assert "fibrinogênio" in coag.lower() and "40304264" in coag, coag
        for cultura in ("40310183", "40310213"):
            txt = " ".join(por_cod[cultura]["alertas_base"])
            assert "antibiograma" in txt.lower() and "40310418" in txt, txt

    def test_todo_curado_declara_o_termo_oficial(self):
        """A procedência por linha: quem ler a base sabe o que o código é na
        terminologia, sem abrir o CSV."""
        from app.ai import tuss_base

        por_cod = {r["codigo_tuss"]: r for r in _rows(_TUSS)}
        for reg in tuss_base._BASE_RAW:
            termo = reg.get("termo_oficial")
            assert termo, f"{reg['nome_padrao']} sem termo_oficial"
            oficial = por_cod[reg["codigo_tuss"]]["termo"].replace('"', "'")
            assert termo == oficial, (
                f"{reg['nome_padrao']}: termo_oficial diverge do CSV\n"
                f"  base: {termo!r}\n   CSV: {oficial!r}"
            )


class TestNenhumCodigoInventadoEmLugarNenhum:
    """A guarda NOVA do §4.3 — vale para `_BASE_RAW` E para o seed.

    O ENG-027 descobriu que havia TRÊS fontes de código TUSS nesta casa, e as
    três tinham código inventado. A caneta corrigiu as três; esta guarda é o
    que impede uma quarta de nascer: todo `codigo_tuss` escrito em qualquer
    lugar do código precisa existir na Tabela 22 estagiada, com vigência
    ABERTA.
    """

    _SEED = _RAIZ / "backend" / "seed_demo.py"

    def _oficiais_vigentes(self) -> dict:
        return {r["codigo_tuss"]: r for r in _rows(_TUSS)
                if not (r["vigencia_fim"] or "").strip()}

    def test_todo_codigo_do_base_raw_e_oficial_e_vigente(self):
        from app.ai import tuss_base

        vigentes = self._oficiais_vigentes()
        for reg in tuss_base._BASE_RAW:
            c = reg["codigo_tuss"]
            assert c in vigentes, (
                f"{reg['nome_padrao']}: {c} não está na Tabela 22 com vigência "
                "aberta"
            )

    def test_todo_codigo_do_seed_e_oficial_e_vigente(self):
        """A terceira fonte, que o ENG-027 achou e a caneta alinhou."""
        src = self._SEED.read_text(encoding="utf-8")
        # os códigos TUSS do seed aparecem como literal na tupla do INSERT,
        # sempre 8 dígitos entre aspas e vizinhos de um nome de exame
        codigos = set(re.findall(r'"(\d{8})"', src))
        assert codigos, "nenhum código TUSS literal encontrado no seed"
        vigentes = self._oficiais_vigentes()
        fora = sorted(c for c in codigos if c not in vigentes)
        assert not fora, (
            f"o seed escreve código que não é oficial vigente: {fora}. Foi "
            "exatamente assim que 40301107 e 40302055 viveram na vitrine."
        )

    def test_o_hemograma_tem_UM_codigo_na_casa_inteira(self):
        """O retrato do defeito que a caneta fechou.

        Antes: três códigos para o mesmo exame — 40301107 (seed), 40301079
        (base, que era ácido beta hidroxi butírico) e o oficial 40304361.
        Depois: um só, nos dois lugares.
        """
        from app.ai import tuss_base

        na_base = {r["codigo_tuss"] for r in tuss_base._BASE_RAW
                   if "hemograma" in r["nome_busca"]}
        assert na_base == {"40304361"}, na_base
        src = self._SEED.read_text(encoding="utf-8")
        assert "40301107" not in src and "40301079" not in src
        assert "40304361" in src

    def test_o_retroativo_nao_foi_tocado(self):
        """§4.4 do despacho: histórico é IMUTÁVEL.

        Itens já emitidos mantêm o código com que faturaram — a medição do
        #280 é o registro da exposição, e é assim que o ledger desta casa
        trata o passado (§1/§2 do CLAUDE.md: não se edita o emitido). Nenhum
        UPDATE em `pedido_exame_itens` pode ter entrado nesta caneta.
        """
        import subprocess

        # `git diff origin/main` (sem ...HEAD) compara a ÁRVORE DE TRABALHO
        # com a base: pega o que já foi commitado E o que ainda não foi. Com
        # `...HEAD` a guarda passaria trivialmente antes do primeiro commit —
        # verde sem ter olhado nada, que é o pior tipo de verde.
        # Os caminhos que PODERIAM escrever no banco: app, seed e migrações.
        # `tests/` fica de fora de propósito — este arquivo contém a própria
        # string proibida na asserção abaixo, e incluí-lo faria a guarda
        # reprovar a si mesma (foi o que aconteceu na primeira escrita).
        diff = subprocess.run(
            ["git", "diff", "origin/main", "--",
             "backend/app/", "backend/seed_demo.py", "backend/alembic/", "data/"],
            cwd=str(_RAIZ), capture_output=True, text=True).stdout
        assert diff.strip(), (
            "o diff contra origin/main veio vazio — a guarda não olhou nada"
        )
        for proibido in ("UPDATE pedido_exame_itens", "UPDATE laudo_itens"):
            assert proibido not in diff, (
                f"a caneta introduziu {proibido!r} — o retroativo é imutável"
            )


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
