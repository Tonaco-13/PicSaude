"""
transcrever_portaria_344.py
============================
DESENHO-TALAO-DIGITAL-SNCR.md §1/§1.1 — G1, a transcrição que faltava.

Transcreve OFFLINE o **Anexo I da Portaria SVS/MS 344/1998 consolidada** a
partir do PDF do Anvisa Legis, emitindo o JSON que
`importar_snapshot_rdc_substancias.py` consome.

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a). Mesmo padrão da onda das bases (CID-10 / SIGTAP / PCDT):
pypdf sobre um PDF estagiado com sha256 no MANIFEST.

O GESTO HUMANO QUE ESTE SCRIPT DESTRAVOU
-----------------------------------------
O §1.1 registrou o muro: a rota programática do Anvisa Legis exige sessão
interativa, e busca web RESUME listas grandes em vez de enumerar. O PDF
consolidado (IMPRIMIR → salvar) foi o único passo que exigia humano. Ele
chegou em 13/09/2026 — 57 páginas, Atualização nº 101, RDC 1.036/2026 —,
e daqui para a frente tudo é mecânico e reprodutível.

DECISÕES DE TRANSCRIÇÃO — todas verificáveis no PDF, nenhuma por memória
-----------------------------------------------------------------------
1. **A chave de lista é o CÓDIGO** (`LISTA - A1`), não o título formal.
   O título NÃO é chave única: A3 e B1 compartilham "LISTA DAS SUBSTÂNCIAS
   PSICOTRÓPICAS" no consolidado. O título entra só como corroboração.
   (O briefing previa que o PDF traria apenas títulos formais; o texto
   consolidado traz OS DOIS, e é o código que desambigua.)

2. **`ADENDO:` fecha a lista de substâncias.** É o delimitador do próprio
   documento — 17 cabeçalhos de lista para 18 linhas `ADENDO:`. Depois
   dele vêm cláusulas de exceção, que são texto normativo, não substância.
   Heurística de tamanho seria chute; isto é o que o texto declara.

3. **Substância é `N.`; cláusula de adendo é `N)`.** Confirmado por
   varredura: 524 itens `N.` com média de 45 caracteres contra 151 itens
   `N)` com média de 118. Sub-itens `N.N` (ex.: `1.1. os sais...`) são
   normativos e ficam de fora.

4. **O espaço após o ponto é opcional**: A1 traz `1. Acetilmetadol` e B2
   traz `1.Aminorex`. Exigir o espaço zerava B2, C1 e C3 — silenciosamente.

5. **Ligaduras tipográficas** (ﬁ, ﬂ) vêm do PDF e são desfeitas por NFKC.
   Sem isso "Buprenorﬁna" entraria como substância distinta de
   "Buprenorfina" — corrupção silenciosa num dado que vai ser carimbado.

6. **Só listas PRESCRITÍVEIS viram `classe_controle`** (A1, A2, A3, B1,
   B2, C1, C2, C3, C5). D1/D2 (precursores e insumos), E (plantas
   proscritas) e F1–F4 (proscritas) são transcritas para conferência mas
   NÃO entram no catálogo de prescrição: proscrito não é "controlado com
   receita", e marcá-lo como classe faria o semáforo sugerir que existe
   receituário para ele.

VERIFICAÇÃO EMBUTIDA (`--verificar`)
------------------------------------
As listas do Anexo I são numeradas de 1..N sem buraco. O modo de
verificação confere essa continuidade lista a lista — é o que pega item
perdido ou linha capturada indevidamente, que leitura por amostra não pega.
A ordem alfabética também é conferida, mas como AVISO: a fonte tem quebras
reais (`9. Bezitramida` antes de `10. Benzetidina` na A1), então ordem
quebrada é sinal para olhar, não veredito.

Uso
---
    python3 backend/scripts/transcrever_portaria_344.py \\
        --pdf data/fontes-oficiais/anvisa-controlados-2026-08-28/PORTARIA-...pdf \\
        --saida data/fontes-oficiais/anvisa-controlados-2026-08-28/anexo-i-consolidado.json

    python3 backend/scripts/transcrever_portaria_344.py --pdf <path> --verificar
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover — ferramenta de bancada
    print("pypdf não instalado: pip install pypdf", file=sys.stderr)
    raise SystemExit(2)

# Listas cuja substância é PRESCRITÍVEL sob controle especial.
LISTAS_PRESCRITIVEIS = ["A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C5"]

_RE_CABECALHO = re.compile(r"^LISTA\s*[-–]\s*([A-F]\d?)\s*$", re.I)
_RE_CABECALHO_F = re.compile(r"^LISTA\s+(F\d)\s*[-–]", re.I)
_RE_ADENDO = re.compile(r"^ADENDO", re.I)
_RE_ANEXO_SEGUINTE = re.compile(r"^ANEXO\s+(II|III|IV|V|VI|VII|VIII|IX|X)", re.I)
_RE_ITEM = re.compile(r"^(\d{1,3})\.\s*(\S.*)$")
_RE_SUBITEM = re.compile(r"^\d{1,3}\.\d")
_RE_RUIDO = re.compile(
    r"AGÊNCIA NACIONAL|GERÊNCIA-GERAL|ATUALIZAÇÃO N|LISTAS DA PORTARIA|"
    r"^\s*Página\s+\d+$",
    re.I,
)


def normalizar(texto: str) -> str:
    """NFKC desfaz ligaduras (ﬁ→fi); colapsa espaço em branco."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", texto)).strip()


def chave(nome: str) -> str:
    """Chave de comparação: minúscula, sem acento, espaço colapsado."""
    base = unicodedata.normalize("NFKD", nome.casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip()


def extrair(pdf_path: str) -> tuple[dict[str, list[tuple[int, str]]], dict[str, str]]:
    """Devolve {codigo: [(numero, nome_bruto)]} e {codigo: titulo_formal}."""
    leitor = PdfReader(pdf_path)
    linhas = [
        normalizar(linha)
        for pagina in leitor.pages
        for linha in (pagina.extract_text() or "").splitlines()
    ]

    listas: dict[str, list[tuple[int, str]]] = {}
    titulos: dict[str, str] = {}
    atual: str | None = None
    coletando = False
    espera_titulo = False

    for linha in linhas:
        if not linha or _RE_RUIDO.search(linha):
            continue

        cab = _RE_CABECALHO.match(linha) or _RE_CABECALHO_F.match(linha)
        if cab:
            atual = cab.group(1).upper()
            listas.setdefault(atual, [])
            coletando = True
            espera_titulo = True
            continue

        if _RE_ADENDO.match(linha):
            coletando = False  # decisão 2: o adendo fecha a lista
            continue

        if _RE_ANEXO_SEGUINTE.match(linha):
            atual, coletando = None, False
            continue

        if not coletando or atual is None:
            continue

        if espera_titulo:
            espera_titulo = False
            if linha.upper().startswith("LISTA"):
                titulos[atual] = linha
                continue

        if _RE_SUBITEM.match(linha):
            continue

        item = _RE_ITEM.match(linha)
        if item:
            listas[atual].append((int(item.group(1)), item.group(2).strip()))

    return listas, titulos


def limpar_nome(bruto: str) -> str | None:
    """Nome da substância sem as notas de redação do texto consolidado."""
    s = re.sub(
        r"\((?:Redação|Inclu[íi]d|Alterad|Revogad|Excluíd)[^)]*\)", "", bruto, flags=re.I
    )
    s = re.sub(r"\(?(?:NR|N\.R\.)\)?\s*$", "", s).strip(" .;–-\t")
    s = re.sub(r"\s+", " ", s)
    if len(s) < 3 or s.lower() == "(excluído)":
        return None
    return s


def nomes_de(listas, codigo: str) -> list[str]:
    return [n for n in (limpar_nome(b) for _, b in listas.get(codigo, [])) if n]


def designacoes_alternativas(nome: str) -> list[str]:
    """Nomes alternativos que A PRÓPRIA FONTE dá para a substância.

    O consolidado nomeia parte das substâncias pelo nome químico com o nome
    usual entre parênteses — `Ftalimidoglutarimida (talidomida)`,
    `Canabidiol (CBD)`, `Prasterona (deidroepiandrosterona - DHEA)` — ou por
    dois nomes ligados por " ou " (`Metandienona ou metandrostenolona`).

    POR QUE ISTO NÃO É INVENÇÃO E POR QUE É NECESSÁRIO: o lookup do catálogo
    chaveia por `normalizar_dcb`, e `talidomida` NÃO casa com
    `ftalimidoglutarimida (talidomida)`. Sem emitir a designação alternativa,
    quem digita "Talidomida" erra a row oficial C3 e acerta a curada antiga
    (D1) — um catálogo CARIMBADO contendo classe contraditória, que é
    exatamente o que o carimbo promete não ter. O texto alternativo sai do
    próprio Anexo I; o que se acrescenta é a linha de lookup, não o fato.

    Cada alternativa vira entrada própria, contável e marcada na
    `observacao` — nunca se confunde com uma substância a mais da lista.
    """
    formas: list[str] = []

    for alt in re.findall(r"\(([^)]+)\)", nome):
        partes = [p.strip(" -") for p in re.split(r"\s+-\s+", alt)]
        # O " - " tanto separa nome e SIGLA ("deidroepiandrosterona - DHEA")
        # quanto é apenas um hífen espaçado dentro de um nome químico
        # ("ácido gama - hidroxibutírico"). Só é separador quando uma das
        # partes é sigla (maiúscula curta); senão o nome é um só, e partir
        # produziria os cacos "ácido gama" e "hidroxibutírico".
        tem_sigla = any(
            p.isupper() and 2 <= len(p) <= 6 and " " not in p for p in partes
        )
        if len(partes) > 1 and tem_sigla:
            formas.extend(p for p in partes if len(p) >= 3)
        else:
            formas.append(re.sub(r"\s+-\s+", "-", alt).strip(" -"))

    sem_parenteses = re.sub(r"\([^)]*\)", "", nome).strip(" -")
    if " ou " in sem_parenteses:
        formas.extend(p.strip() for p in sem_parenteses.split(" ou "))

    principal = chave(nome)
    vistas, saida = {principal}, []
    for f in formas:
        if chave(f) and chave(f) not in vistas:
            vistas.add(chave(f))
            saida.append(f)
    return saida


def verificar(listas, titulos) -> int:
    """Confere numeração contínua (veredito) e ordem alfabética (aviso)."""
    suspeitas = 0
    for codigo in LISTAS_PRESCRITIVEIS:
        itens = listas.get(codigo, [])
        numeros = [n for n, _ in itens]
        nomes = [s for _, s in itens]
        esperado = list(range(1, len(itens) + 1))
        continua = numeros == esperado
        fora_ordem = [
            (nomes[i - 1], nomes[i])
            for i in range(1, len(nomes))
            if chave(nomes[i]) < chave(nomes[i - 1])
        ]
        if not continua:
            suspeitas += 1
        print(
            "  %-3s %3d itens   numeração: %-9s   ordem: %s"
            % (
                codigo,
                len(itens),
                "1..%d ok" % len(itens) if continua else "QUEBRADA",
                "ok" if not fora_ordem else "%d avisos (fonte)" % len(fora_ordem),
            )
        )
        if not continua:
            print("      ausentes:", sorted(set(esperado) - set(numeros))[:12])
    return suspeitas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, help="PDF consolidado do Anvisa Legis")
    ap.add_argument("--saida", help="JSON de saída (formato do importador)")
    ap.add_argument("--verificar", action="store_true", help="só confere, não escreve")
    ap.add_argument(
        "--fonte",
        default=(
            "Anexo I Portaria 344/98 consolidada, Atualização nº 101 — "
            "RDC 1.036/2026, Anvisa Legis 13/09/2026"
        ),
    )
    ap.add_argument("--versao", default="RDC 1.036/2026 (Atualização nº 101)")
    ap.add_argument("--data-snapshot", default="2026-09-13")
    args = ap.parse_args()

    listas, titulos = extrair(args.pdf)

    print("=== listas do Anexo I ===")
    for codigo in sorted(listas):
        marca = "PRESCRITÍVEL" if codigo in LISTAS_PRESCRITIVEIS else "conferência"
        print(
            "  %-3s %-13s %4d   %s"
            % (
                codigo,
                marca,
                len(nomes_de(listas, codigo)),
                titulos.get(codigo, "(sem título próprio)")[:56],
            )
        )

    print("\n=== verificação de continuidade ===")
    suspeitas = verificar(listas, titulos)
    if suspeitas:
        print("\n%d lista(s) com numeração quebrada — NÃO emitir snapshot" % suspeitas)
        return 1
    print("\nnumeração contínua em todas as listas prescritíveis")

    if args.verificar or not args.saida:
        return 0

    entradas: list[dict] = []
    vistos: dict[str, str] = {}
    duplicados: list[tuple[str, str, str]] = []
    n_alternativas = 0
    for codigo in LISTAS_PRESCRITIVEIS:
        for nome in nomes_de(listas, codigo):
            k = chave(nome)
            if k in vistos:
                duplicados.append((nome, codigo, vistos[k]))
                continue
            vistos[k] = codigo
            entradas.append(
                {
                    "dcb": nome,
                    "classe_controle": codigo,
                    "tipo_retencao": None,
                    "observacao": None,
                }
            )
            for alt in designacoes_alternativas(nome):
                ka = chave(alt)
                if ka in vistos:
                    continue
                vistos[ka] = codigo
                n_alternativas += 1
                entradas.append(
                    {
                        "dcb": alt,
                        "classe_controle": codigo,
                        "tipo_retencao": None,
                        # Delimitador [ ] e não aspas: três substâncias do
                        # Anexo I já trazem aspas no próprio nome
                        # (`Intermediário "a" da petidina`), e um parser de
                        # aspas casaria o `a` em vez do nome inteiro. Nenhuma
                        # entrada usa colchete — conferido na transcrição.
                        "observacao": (
                            "Designação alternativa de [%s] no Anexo I "
                            "(Lista %s). Linha de lookup, não substância "
                            "adicional da lista." % (nome, codigo)
                        ),
                    }
                )

    snapshot = {
        "fonte": args.fonte,
        "versao": args.versao,
        "data_snapshot": args.data_snapshot,
        "entradas": entradas,
    }
    with open(args.saida, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(
        "\nJSON escrito: %s — %d entradas (%d substâncias da lista + %d "
        "designações alternativas)"
        % (args.saida, len(entradas), len(entradas) - n_alternativas, n_alternativas)
    )
    if duplicados:
        print("substância repetida entre listas (mantida a primeira ocorrência):")
        for nome, codigo, antes in duplicados:
            print("   %-30s %s (já em %s)" % (nome, codigo, antes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
