"""
extrair_snapshot_pcdt.py
==========================
DESENHO-ONDA-PCDT.md §4 — Camada 1: EXTRAÇÃO ASSISTIDA (rascunho de
máquina). Lê os PDFs já estagiados em `data/fontes-oficiais/pcdt/corpus-
conitec-2026-08-30/` (nunca a rede) e produz uma pré-tabela RASCUNHO:

    pcdt · condicao · cid · principio_ativo · posologia_bruta · linha ·
    citacao (portaria+quadro+página) · status_curadoria=rascunho

LINHA VERMELHA DO VAGÃO, ESTENDIDA À MÁQUINA
---------------------------------------------
Toda row nasce `status_curadoria=rascunho` e morre rascunho até a
assinatura do Fabiano (Camada 2). Este script NUNCA escreve em
`data/decisao_semaforo.csv` nem `data/posologia_sugerida.csv` — só em
`data/fontes-oficiais/pcdt/extracao/` (gitignored, igual ao resto de
`fontes-oficiais/`). "Leitura assistida" (pypdf + heurísticas por PCDT,
documentadas abaixo) é permitida NESTA camada precisamente porque o
produto nunca é servido — grau rascunho por construção, não por promessa.

CADA PCDT TEM OS SEUS QUADROS — duas estratégias, documentadas
------------------------------------------------------------------
O desenho (§4) já avisa: "cada PCDT tem os seus". Duas estruturas
observadas nesta rodada, cada uma com sua função de extração própria:

  E11 (DM2)  — Quadro 15 (p.39) é uma TABELA de esquemas de administração
               (medicamento × dose habitual × dose máxima × frequência).
               O corte por coluna de uma tabela flatten (pypdf lê célula
               a célula em ordem de leitura) é frágil para linhas com
               conteúdo multi-linha (as insulinas). Estratégia: ANCORAR
               por nome de princípio ativo já conhecido (dicionário =
               `data/decisao_semaforo.csv`, escopo do CID + os dois
               nomes de classe de insulina análoga, estes lidos do
               próprio Quadro 18 — nunca hardcoded às cegas) e fatiar o
               texto entre âncoras consecutivas. Nome de princípio ativo
               que não bate no dicionário não vira row — não é
               inventado, e vira gap explícito no relatório.

  J45 (Asma) — não tem uma única "Quadro 15" com todos os fármacos. Em
               compensação, tem uma seção de PROSA estruturada em
               marcadores — "7.4.1. Esquemas de administração" (p.38-40)
               — com um bullet por medicamento/classe: "- Nome: texto".
               Estratégia: fatiar por esse marcador, sem precisar de
               dicionário prévio algum (útil justo por ser a PRIMEIRA
               leitura de J45 — não há levantura humana anterior para
               fornecer os nomes).

FALHAS DE EXTRAÇÃO SÃO LISTADAS, NUNCA ESCONDIDAS (AC iii)
--------------------------------------------------------------
Um PDF que não abre, um quadro que não é localizado, um trecho de texto
que sobra sem âncora reconhecida — tudo isso vira nota no relatório, não
silêncio. O script aborta (nunca inventa) se um PDF/quadro esperado não
existir.

Uso
---
    python3 backend/scripts/extrair_snapshot_pcdt.py

Idempotente: lê sempre os MESMOS PDFs estagiados (nunca a rede) e escreve
o CSV/relatório do zero a cada rodada.

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a, CLAUDE.md). Guarda executável no arquivo de teste.

DEPENDÊNCIA — `pypdf` não está no `requirements.txt` de produção (esta
ferramenta nunca roda no deploy): `pip install pypdf` no ambiente de
desenvolvimento antes de rodar.
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from pathlib import Path

try:
    import pypdf
except ImportError:
    print("❌ ABORTANDO: pypdf não instalado. Rode: pip install pypdf")
    sys.exit(1)

_RAIZ = Path(__file__).resolve().parents[2]
_CORPUS = _RAIZ / "data" / "fontes-oficiais" / "pcdt" / "corpus-conitec-2026-08-30"
_DECISAO_SEMAFORO_CSV = _RAIZ / "data" / "decisao_semaforo.csv"
_SAIDA_DIR = _RAIZ / "data" / "fontes-oficiais" / "pcdt" / "extracao"
_RELATORIO = _RAIZ / "docs" / "tickets" / "RELATORIO-EXTRACAO-PCDT.md"

_CAMPOS_CSV = [
    "pcdt", "condicao", "cid", "principio_ativo", "posologia_bruta",
    "linha", "citacao", "status_curadoria",
]

_RE_PORTARIA = re.compile(
    r"PORTARIA(?:\s+CONJUNTA)?\s+[\w/]+\s*N[ºO°]\s*\d+,?\s*DE\s+\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Utilitários de texto — compartilhados pelas duas estratégias
# ---------------------------------------------------------------------------

def _normalizar(s: str) -> str:
    """Minúsculas, sem acento, espaços colapsados. Uso geral (chaves de
    dicionário, comparação)."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _normalizar_preservando_indice(s: str) -> str:
    """Minúsculas, sem acento, MESMO comprimento/índices de `s` (não
    colapsa espaço) — permite achar substring na versão normalizada e
    recortar a versão original pelo MESMO índice, sem mapeamento
    aproximado."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _ler_paginas(pdf_path: Path) -> list[str]:
    leitor = pypdf.PdfReader(str(pdf_path))
    return [(p.extract_text() or "") for p in leitor.pages]


def _extrair_portaria(paginas: list[str]) -> str | None:
    """Lida da capa do PDF (p.1-2) — nunca digitada à mão, para não
    repetir o defeito que o CLAUDE.md já registrou noutras camadas
    (string escrita à mão envelhece em silêncio)."""
    for texto in paginas[:2]:
        m = _RE_PORTARIA.search(texto)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()
    return None


def _localizar_quadro(
    paginas: list[str], numero: int, pista_titulo: str
) -> tuple[int, int] | None:
    """Acha a página (0-indexed) e o índice de início do TÍTULO do Quadro
    N, validando por uma pista de título — protege contra os artefatos de
    reflow já observados no corpus ("Quadro 634.", "Quadro 103." — "Quadro
    N" solto no meio de frase, sem título coerente). Só aceita o match se
    a pista aparecer nos 200 caracteres seguintes."""
    padrao = re.compile(rf"Quadro\s+{numero}\.\s*")
    pista_norm = _normalizar(pista_titulo)
    for i, texto in enumerate(paginas):
        for m in padrao.finditer(texto):
            trecho = texto[m.end():m.end() + 250]
            if pista_norm in _normalizar(trecho):
                return i, m.start()
    return None


def _dicionario_curado(cid: str) -> list[str]:
    """Nomes de princípio_ativo já curados em `decisao_semaforo.csv` para
    o CID — fonte única, nunca uma lista nova inventada aqui. Ordenado do
    mais longo pro mais curto (evita que um nome curto colida por engano
    dentro de um nome composto)."""
    nomes: set[str] = set()
    if _DECISAO_SEMAFORO_CSV.exists():
        with open(_DECISAO_SEMAFORO_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("codigo_cid", "").strip().upper() == cid.upper():
                    nome = (row.get("principio_ativo") or "").strip()
                    if nome:
                        nomes.add(nome)
    return sorted(nomes, key=len, reverse=True)


# ---------------------------------------------------------------------------
# Estratégia A — âncora por dicionário (tabela flatten, ex.: E11 Quadro 15)
# ---------------------------------------------------------------------------

def _variantes_qualificador_insulina(dicionario: list[str], texto: str) -> dict[str, str]:
    """Nomenclatura observada nos PCDTs qualifica insulinas humanas
    ("Insulina humana NPH", "Insulina Humana Regular") — um qualificador
    que `decisao_semaforo.csv` não carrega ("insulina NPH", "insulina
    regular"), quebrando o match literal. Em vez de cravar essas duas
    strings à mão, aplica a transformação SISTEMATICAMENTE a qualquer
    "insulina X" do dicionário (que ainda não tenha "humana"/"análoga" no
    nome): só usa a variante se ela bater no texto sendo processado — é
    o mesmo princípio de "nunca hardcoded às cegas" já usado para as
    classes de insulina análoga (deriva do documento, não da memória)."""
    texto_norm = _normalizar(texto)
    variantes: dict[str, str] = {}
    for nome in dicionario:
        n = _normalizar(nome)
        if not n.startswith("insulina "):
            continue
        if "humana" in n or "analoga" in n:
            continue
        if n in texto_norm:
            continue  # forma literal já bate — sem variante necessária
        resto = nome.split(" ", 1)[1] if " " in nome else ""
        candidato = f"insulina humana {resto}".strip()
        if _normalizar(candidato) in texto_norm:
            variantes[nome] = candidato
    return variantes


def _fatiar_por_dicionario(
    texto: str, dicionario: list[str], variantes: dict[str, str] | None = None
) -> tuple[list[dict], str]:
    """Localiza cada nome do dicionário (ou sua variante de busca, se
    houver) como substring do texto (normalizado), ordena por posição de
    ocorrência, e fatia o texto ORIGINAL (espaços colapsados, acentos/
    caixa preservados) entre âncoras consecutivas. Cada fatia = {nome,
    posologia_bruta, linha}. `linha` = o texto entre a âncora anterior
    (ou início) e esta — onde o Quadro 15 costuma trazer o rótulo de
    classe farmacológica ("Sulfonilureias", "iSGLT2"...). Nome do
    dicionário ausente do texto (e sem variante que bata) não gera row —
    não é inventado.

    `principio_ativo` na row sempre usa o NOME CANÔNICO do dicionário
    (fonte única com decisao_semaforo.csv), mesmo quando a âncora foi
    localizada pela variante de busca.

    Retorna (linhas, sobra_final) — `sobra_final` é o que sobrou depois
    da última âncora reconhecida (notas de rodapé etc., não é erro)."""
    variantes = variantes or {}
    texto_ws = re.sub(r"\s+", " ", texto).strip()
    texto_match = _normalizar_preservando_indice(texto_ws)

    ocorrencias: list[tuple[int, str, str]] = []
    for nome in dicionario:
        termo_busca = variantes.get(nome, nome)
        termo_norm = _normalizar(termo_busca)
        idx = texto_match.find(termo_norm)
        if idx >= 0:
            ocorrencias.append((idx, nome, termo_busca))
    ocorrencias.sort()

    # remove sobreposição: se duas âncoras começam dentro uma da outra,
    # fica só a que veio primeiro (já é a mais longa, por causa do sort
    # do dicionário por tamanho decrescente antes de popular `ocorrencias`
    # na ordem em que os nomes foram testados — mas a ordenação final é
    # por posição, então reordenamos por tamanho aqui como desempate).
    filtradas: list[tuple[int, str, str]] = []
    for idx, nome, termo_busca in ocorrencias:
        if filtradas:
            fim_anterior = filtradas[-1][0] + len(_normalizar(filtradas[-1][2]))
            if idx < fim_anterior:
                continue
        filtradas.append((idx, nome, termo_busca))

    linhas: list[dict] = []
    anterior_fim = 0
    for i, (idx, nome, termo_busca) in enumerate(filtradas):
        fim = filtradas[i + 1][0] if i + 1 < len(filtradas) else len(texto_ws)
        rotulo_linha = texto_ws[anterior_fim:idx].strip()
        posologia = texto_ws[idx + len(termo_busca):fim].strip()
        # a âncora foi achada no texto NORMALIZADO; para reexibir o nome
        # como apareceu no PDF, recortamos o mesmo trecho do texto_ws.
        nome_como_no_pdf = texto_ws[idx: idx + len(termo_busca)].strip()
        linhas.append({
            "principio_ativo": nome,
            "principio_ativo_como_no_pdf": nome_como_no_pdf,
            "posologia_bruta": posologia,
            "linha": rotulo_linha[-80:] if rotulo_linha else "",
        })
        anterior_fim = idx + len(termo_busca)
    sobra = texto_ws[filtradas[-1][0] + len(filtradas[-1][2]):].strip() if filtradas else texto_ws
    return linhas, sobra


def _extrair_classes_insulina_analoga(texto_quadro18: str) -> list[str]:
    """As duas classes de insulina análoga do elenco 2026 (rápida/
    prolongada) não têm row própria em `decisao_semaforo.csv` hoje — só
    os análogos individuais (asparte, lispro, glargina...), de uma
    levantura anterior. O PCDT elenca por CLASSE (Quadro 18), então
    extraímos as duas frases DO PRÓPRIO Quadro 18 — nunca hardcoded às
    cegas, sempre lidas do documento que está sendo processado."""
    achados = []
    for m in re.finditer(
        r"Insulina\s+an[aá]loga\s+de\s+a[çc][ãa]o\s+(r[aá]pida|prolongada)",
        texto_quadro18, re.IGNORECASE,
    ):
        frase = re.sub(r"\s+", " ", m.group(0)).strip()
        if frase not in achados:
            achados.append(frase)
    return achados


def extrair_e11(paginas: list[str], portaria: str) -> tuple[list[dict], list[str]]:
    """Estratégia A. Quadro 15 (posologia) + Quadro 18 (confirmação do
    elenco + fonte das 2 classes de insulina análoga)."""
    gaps: list[str] = []

    q18 = _localizar_quadro(paginas, 18, "recomendações para o gestor")
    if q18 is None:
        gaps.append("Quadro 18 não localizado — elenco de confirmação e "
                     "classes de insulina análoga ficaram de fora.")
        texto_q18 = ""
        pagina_q18 = None
    else:
        pagina_q18, inicio_q18 = q18
        texto_q18 = paginas[pagina_q18][inicio_q18:inicio_q18 + 4000]

    q15 = _localizar_quadro(paginas, 15, "esquemas de administração")
    if q15 is None:
        gaps.append("Quadro 15 não localizado — nenhuma row de posologia "
                     "pôde ser extraída para E11.")
        return [], gaps
    pagina_q15, inicio_q15 = q15
    # o quadro pode continuar na página seguinte antes da próxima seção
    # (8.9. Contraindicações, observado no corpus) — concatenamos.
    texto_q15 = paginas[pagina_q15][inicio_q15:]
    fim_secao = re.search(r"\n\s*8\.9\.", texto_q15)
    if fim_secao:
        texto_q15 = texto_q15[:fim_secao.end()]

    dicionario = _dicionario_curado("E11")
    dicionario += _extrair_classes_insulina_analoga(texto_q18)
    if not dicionario:
        gaps.append("Dicionário de princípios ativos para E11 veio vazio "
                     "(decisao_semaforo.csv sem rows E11?) — nenhuma âncora "
                     "para fatiar o Quadro 15.")
        return [], gaps

    variantes = _variantes_qualificador_insulina(dicionario, texto_q15)
    for nome, variante in variantes.items():
        gaps.append(
            f"'{nome}' não bate literalmente no Quadro 15 — usada a variante "
            f"'{variante}' (qualificador 'humana' presente no PDF, ausente em "
            f"decisao_semaforo.csv). Achado de nomenclatura, não erro de leitura."
        )
    fatias, sobra = _fatiar_por_dicionario(texto_q15, dicionario, variantes)
    # `sobra` (texto após a última âncora) SEMPRE existe quando há match —
    # é o mesmo texto já capturado como posologia_bruta da última row (não
    # há âncora seguinte para delimitar onde a legenda/nota dela termina).
    # Só é sinal de gap de verdade quando NENHUMA âncora bateu (fatias
    # vazio): aí sim o quadro inteiro ficou sem classificação.
    if not fatias and sobra:
        gaps.append(
            f"Nenhum princípio ativo do dicionário reconhecido no Quadro 15 "
            f"(p.{pagina_q15+1}) — {len(sobra)} caracteres não classificados."
        )

    citacao_q18 = f"{portaria}, Quadro 18, p. {pagina_q18+1}" if pagina_q18 is not None else ""
    rows = []
    for f in fatias:
        termo_confirmacao = variantes.get(f["principio_ativo"], f["principio_ativo"])
        confirmado_q18 = _normalizar(termo_confirmacao) in _normalizar(texto_q18)
        citacao = f"{portaria}, Quadro 15, p. {pagina_q15+1}"
        if confirmado_q18:
            citacao += f" + Quadro 18, p. {pagina_q18+1} (elenco confirmado)"
        else:
            gaps.append(
                f"'{f['principio_ativo']}' achado no Quadro 15 mas NÃO "
                f"confirmado no texto do Quadro 18 — conferir manualmente."
            )
        rows.append({
            "pcdt": "PCDT Diabete Melito Tipo 2",
            "condicao": "Diabete melito tipo 2",
            "cid": "E11",
            "principio_ativo": f["principio_ativo"],
            "posologia_bruta": f["posologia_bruta"],
            "linha": f["linha"],
            "citacao": citacao,
            "status_curadoria": "rascunho",
        })
    return rows, gaps


# ---------------------------------------------------------------------------
# Estratégia B — marcador de prosa (bullets, ex.: J45 "7.4.1.")
# ---------------------------------------------------------------------------

_RE_BULLET_MEDICAMENTO = re.compile(r"-\s+([A-ZÀ-Ý][^:\n]{1,90}):\s*")


def _fatiar_por_marcadores(texto: str, padrao: re.Pattern) -> list[tuple[str, str]]:
    """Fatia texto em blocos usando o padrão como delimitador de início —
    cada bloco vai do fim de um marcador até o início do próximo (ou fim
    do texto). Não precisa de dicionário prévio: é a estratégia certa
    para uma leitura que NASCE da extração, sem levantura humana antes."""
    matches = list(padrao.finditer(texto))
    linhas = []
    for i, m in enumerate(matches):
        nome = re.sub(r"\s+", " ", m.group(1)).strip()
        inicio = m.end()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        bruto = re.sub(r"\s+", " ", texto[inicio:fim]).strip()
        linhas.append((nome, bruto))
    return linhas


def extrair_j45(paginas: list[str], portaria: str) -> tuple[list[dict], list[str]]:
    """Estratégia B. Seção '7.4.1. Esquemas de administração' — um
    marcador "- Nome: ..." por medicamento/classe, terminando em
    '7.4.2.'. As tabelas de dose que caem DENTRO da seção (Quadros 9-13)
    ficam embutidas na posologia_bruta do bullet correspondente — é
    exatamente o esquema de dose daquele bullet, não é ruído."""
    gaps: list[str] = []

    inicio_idx = None
    pagina_inicio = None
    for i, texto in enumerate(paginas):
        m = re.search(r"7\.4\.1\.\s*Esquemas de administra[çc][ãa]o", texto)
        if m:
            inicio_idx = m.end()
            pagina_inicio = i
            break
    if inicio_idx is None:
        gaps.append("Seção '7.4.1. Esquemas de administração' não "
                     "localizada — nenhuma row extraída para J45.")
        return [], gaps

    texto_secao = paginas[pagina_inicio][inicio_idx:]
    pagina_fim = pagina_inicio
    for j in range(pagina_inicio + 1, min(pagina_inicio + 6, len(paginas))):
        m_fim = re.search(r"7\.4\.2\.", paginas[j])
        if m_fim:
            texto_secao += "\n" + paginas[j][:m_fim.start()]
            pagina_fim = j
            break
        texto_secao += "\n" + paginas[j]
        pagina_fim = j
    else:
        gaps.append("Fim da seção 7.4.1 (marcador '7.4.2.') não encontrado "
                     "nas páginas seguintes — seção pode ter sido cortada "
                     "cedo demais ou tarde demais; conferir manualmente.")

    fatias = _fatiar_por_marcadores(texto_secao, _RE_BULLET_MEDICAMENTO)
    if not fatias:
        gaps.append(
            f"Nenhum marcador '- Nome: ' reconhecido na seção 7.4.1 "
            f"(p.{pagina_inicio+1}-{pagina_fim+1}) — verificar padrão manualmente."
        )

    citacao_pag = (f"p. {pagina_inicio+1}" if pagina_inicio == pagina_fim
                   else f"p. {pagina_inicio+1}-{pagina_fim+1}")
    rows = []
    for nome, bruto in fatias:
        if len(bruto) < 15:
            gaps.append(f"'{nome}': posologia_bruta suspeitosamente curta "
                        f"({len(bruto)} caracteres) — conferir.")
        rows.append({
            "pcdt": "PCDT da Asma",
            "condicao": "Asma",
            "cid": "J45",
            "principio_ativo": nome,
            "posologia_bruta": bruto,
            "linha": "",  # a prosa de 7.4.1 não rotula linha terapêutica
                          # por bullet — ver achado no relatório.
            "citacao": f"{portaria}, §7.4.1 Esquemas de administração, {citacao_pag}",
            "status_curadoria": "rascunho",
        })
    return rows, gaps


# ---------------------------------------------------------------------------
# Comparação E11 máquina × rascunho humano (AC principal)
# ---------------------------------------------------------------------------

def comparar_com_rascunho_humano(rows_e11: list[dict]) -> list[dict]:
    """Compara os principio_ativo extraídos pela máquina contra o elenco
    de 8 itens do RASCUNHO-E11-DUPLO-PCDT-2026.md §1 (transcrito aqui só
    como CHAVE de comparação, não como fonte de dado)."""
    elenco_humano = [
        "metformina", "glibenclamida", "gliclazida", "dapagliflozina",
        "insulina NPH", "insulina humana regular",
        "insulina análoga de ação rápida", "insulina análoga de ação prolongada",
    ]
    achados_maquina = {_normalizar(r["principio_ativo"]) for r in rows_e11}
    extras_maquina = [
        r["principio_ativo"] for r in rows_e11
        if _normalizar(r["principio_ativo"]) not in {_normalizar(x) for x in elenco_humano}
    ]
    comparacao = []
    for item in elenco_humano:
        bateu = _normalizar(item) in achados_maquina
        nota = ""
        if not bateu:
            # heurística de delta-de-qualificador: se o item do elenco
            # humano difere de um "extra" da máquina só pela presença de
            # uma palavra-qualificador ("humana"/"humano"), é candidato a
            # RENAME PENDENTE no decisao_semaforo.csv — não divergência de
            # conteúdo clínico. Não é hardcode de fármaco: é uma checagem
            # de delta de palavra, genérica a qualquer par item/extra.
            palavras_item = set(_normalizar(item).split())
            for extra in extras_maquina:
                diff = palavras_item.symmetric_difference(set(_normalizar(extra).split()))
                if diff and diff <= {"humana", "humano"}:
                    nota = (f"máquina achou '{extra}' (mesmo termo do "
                            f"decisao_semaforo.csv, sem o qualificador) — "
                            f"candidato a RENAME pendente, não divergência "
                            f"de conteúdo clínico")
                    break
        comparacao.append({"item": item, "maquina_achou": bateu, "nota": nota})
    return comparacao, extras_maquina


# ---------------------------------------------------------------------------
# Saída — CSV + relatório
# ---------------------------------------------------------------------------

def _escrever_csv(rows: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CAMPOS_CSV)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _CAMPOS_CSV})


def _escrever_relatorio(resultado: dict) -> None:
    linhas = [
        "# RELATORIO-EXTRACAO-PCDT.md — Camada 1, TICKET (fila do vagão PCDT)",
        "",
        "Gerado por `backend/scripts/extrair_snapshot_pcdt.py`. Saída em "
        "`data/fontes-oficiais/pcdt/extracao/` — grau rascunho por "
        "construção, nunca servida, nunca commitada como verdade.",
        "",
    ]

    for cid, dados in resultado.items():
        linhas += [
            f"## {cid} — {dados['pcdt']}",
            "",
            f"- Rows extraídas: **{len(dados['rows'])}**",
            f"- Citação-base: {dados['portaria'] or '⚠️ NÃO ENCONTRADA (ver gaps)'}",
            "",
        ]
        if dados["rows"]:
            linhas.append("| principio_ativo | posologia_bruta (início) | citação |")
            linhas.append("|---|---|---|")
            for r in dados["rows"]:
                pb = (r["posologia_bruta"][:70] + "…") if len(r["posologia_bruta"]) > 70 else r["posologia_bruta"]
                linhas.append(f"| {r['principio_ativo']} | {pb} | {r['citacao']} |")
            linhas.append("")
        linhas.append("### Falhas de extração (declaradas, não escondidas)")
        linhas.append("")
        if dados["gaps"]:
            for g in dados["gaps"]:
                linhas.append(f"- {g}")
        else:
            linhas.append("(nenhuma)")
        linhas.append("")

    if "E11" in resultado:
        comparacao, extras = comparar_com_rascunho_humano(resultado["E11"]["rows"])
        linhas += [
            "## Comparação E11 — máquina × RASCUNHO-E11-DUPLO-PCDT-2026.md §1",
            "",
            "O AC principal desta rodada: se a máquina bate com o humano nos "
            "8 itens do elenco, o pipeline está provado.",
            "",
            "| Item do elenco humano (§1) | Máquina achou? | Nota |",
            "|---|---|---|",
        ]
        for c in comparacao:
            if c["maquina_achou"]:
                marca = "✅ sim"
            elif c["nota"]:
                marca = "🟡 nomenclatura"
            else:
                marca = "❌ NÃO — divergência"
            linhas.append(f"| {c['item']} | {marca} | {c['nota']} |")
        linhas.append("")
        if extras:
            linhas.append("**Itens extras que a máquina achou e não estão no elenco humano de 8:**")
            for e in extras:
                linhas.append(f"- {e}")
            linhas.append("")
        n_bateu = sum(1 for c in comparacao if c["maquina_achou"])
        n_nomenclatura = sum(1 for c in comparacao if not c["maquina_achou"] and c["nota"])
        linhas.append(
            f"**Resultado: {n_bateu}/{len(comparacao)} itens do elenco humano "
            f"confirmados literalmente pela máquina"
            + (f"; +{n_nomenclatura} por só nomenclatura (🟡, ver nota — "
               f"conteúdo clínico presente, nome-chave pendente de rename "
               f"no decisao_semaforo.csv)" if n_nomenclatura else "")
            + ".**"
        )
        linhas.append("")
        linhas += [
            "### Limitação conhecida — linearização de tabela no Quadro 15",
            "",
            "O Quadro 15 é uma tabela (medicamento × dose habitual × dose "
            "máxima × frequência); `pypdf.extract_text()` lineariza célula a "
            "célula em ordem de leitura, não por linha visual. Duas "
            "consequências observadas nesta extração, NÃO corrigidas "
            "automaticamente (fariam a máquina INVENTAR um corte que o "
            "texto não delimita com segurança):",
            "",
            "- **Rótulo de classe grudado no fim de `posologia_bruta`** do "
            "medicamento anterior (ex.: \"...2 a 3 vezes Sulfonilureias\" na "
            "posologia da metformina — \"Sulfonilureias\" pertence à PRÓXIMA "
            "classe, não à metformina).",
            "- **Texto repetido entre `insulina regular` e `Insulina análoga "
            "de ação rápida`**: no PDF, os dois esquemas de dose prandial "
            "aparecem colados na mesma região da tabela; a fatia entre as "
            "duas âncoras saiu idêntica para as duas rows.",
            "",
            "Curadoria humana (Camada 2) deve tratar `posologia_bruta` como "
            "matéria-prima a aparar, não como texto final.",
            "",
        ]
        linhas += [
            "### Nota sobre `linha` (achado desta rodada)",
            "",
            "A extração popula `linha` com o RÓTULO DE CLASSE FARMACOLÓGICA "
            "que precede o princípio ativo no próprio Quadro 15 (ex.: "
            "\"Sulfonilureias\", \"iSGLT2\") — mecanicamente extraível do "
            "texto. O rascunho humano usa `linha` para o PAPEL TERAPÊUTICO "
            "(\"1ª linha\", \"intensificação\"), que vem de prosa nas p.21-22 "
            "do PDF, fora do escopo mecânico desta camada. **Divergência "
            "esperada e documentada, não falha de extração.**",
            "",
        ]

    linhas.append("---")
    linhas.append("*Gerado por script — reprodutível rodando de novo sobre o mesmo corpus estagiado.*")
    _RELATORIO.write_text("\n".join(linhas), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

_PCDTS_DESTA_RODADA = [
    ("pcdt-diabete-melito-tipo-2.pdf", "E11", extrair_e11),
    ("pcdt-da-asma.pdf", "J45", extrair_j45),
]


def main() -> None:
    if not _CORPUS.exists():
        print(f"❌ ABORTANDO: corpus não encontrado em {_CORPUS}")
        sys.exit(1)

    resultado: dict[str, dict] = {}
    for nome_arquivo, cid, funcao in _PCDTS_DESTA_RODADA:
        pdf_path = _CORPUS / nome_arquivo
        if not pdf_path.exists():
            print(f"❌ ABORTANDO: {pdf_path} não existe no corpus estagiado")
            sys.exit(1)

        paginas = _ler_paginas(pdf_path)
        portaria = _extrair_portaria(paginas)
        rows, gaps = funcao(paginas, portaria or "PORTARIA NÃO IDENTIFICADA")
        if portaria is None:
            gaps.insert(0, "Portaria não identificada na capa (p.1-2) — "
                           "citação de todas as rows fica incompleta.")

        resultado[cid] = {
            "pcdt": rows[0]["pcdt"] if rows else nome_arquivo,
            "portaria": portaria,
            "rows": rows,
            "gaps": gaps,
        }

        caminho_csv = _SAIDA_DIR / f"pcdt_{cid.lower()}_rascunho.csv"
        _escrever_csv(rows, caminho_csv)
        print(f"✅ {cid}: {len(rows)} rows -> {caminho_csv} ({len(gaps)} gaps)")

    _escrever_relatorio(resultado)
    print(f"   Relatório: {_RELATORIO}")


if __name__ == "__main__":
    main()
