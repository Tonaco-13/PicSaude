"""
importar_snapshot_cid10.py
============================
TICKET-FILA-6-CID10-COMPLETO.md (`docs/tickets/`) — fila 6 da FILA-VIVA,
fechada como TETO ACESSÍVEL (martelo do Fabiano, 29/08/2026, §6 do ticket).

POR QUE "TETO ACESSÍVEL" E NÃO "TABELA NOVA IMPORTADA"
-------------------------------------------------------
O ticket original pedia a revisão brasileira vigente pós-2008 (2ª edição +
atualizações MS). O engenheiro varreu os três candidatos que o ticket
priorizava — Portal SVS/MS, DATASUS, CBCD/USP — e nenhum publica essa
tabela em canal aberto hoje; um achado extra (FHIR RNDS oficial,
`terminologia.saude.gov.br`) tem só metadado público, o dado real está
atrás de autenticação institucional que o PicSaúde não tem. O arquiteto
verificou por fonte independente e o Fabiano martelou: fechar no TETO
ACESSÍVEL, não represar o ticket esperando um acesso que não existe.

O QUE ESTE SCRIPT FAZ (e não faz)
-----------------------------------
NÃO importa códigos novos — não há tabela nova para importar. Faz só dois
gestos de PROVENIÊNCIA sobre o `data/cid10.csv` já existente (14.240
códigos, V2008 + remendos ad-hoc pós-2008):

1. Estampa `versao_snapshot` (constante, mesma em toda row) — hoje a base
   não tinha NENHUMA versão rastreável por linha.
2. RECITA a `fonte` das 7 rows de remendo COVID-19 (família U07-U12): a
   citação genérica "OMS/CID-10 uso emergencial 2020/2021" vira a citação
   de um documento oficial verificado — mesmo dado, proveniência real.
   Duas fontes, porque um único documento não cobre as 7:
     - U07.1/U07.2/U09.9/U10.9/U12.9 → MS/SVSA/Daent, "Orientações para a
       codificação dos demais códigos de emergência relacionados à
       covid-19" (1ª ed. eletrônica, 2025) — confere por `MARCADOR: U09.9`
       / `MARCADOR: U12.9` no texto extraído do PDF.
     - U08.9/U11.9 (não cobertos pelo doc acima) → OMS, "Atualizações 3 e
       4 em relação à codificação da COVID-19 com a CID-10" — confere
       texto quase idêntico às descrições já presentes no CSV.
   Os dois PDFs estão estagiados em `data/fontes-oficiais/cid10/`
   (sha256 no `MANIFEST.md` daquela pasta — pasta gitignored por padrão,
   igual PCDT/ANVISA: o manifest é a proveniência, não o binário).

Terceiro elemento do rito — MEDIR sem IMPORTAR: o relatório que este script
produz (`docs/tickets/RELATORIO-DIFF-CID10.md`) cita a contagem pública de
um espelho de terceiros (tabelacid.com.br, 14.736 códigos declarados) só
para calibrar o tamanho do gap — rotulado CONFERÊNCIA, NUNCA como dado
importado (regra do §2 do ticket: terceiro é espelho, nunca fonte primária).

Uso
---
    python3 backend/scripts/importar_snapshot_cid10.py

Idempotente: `codigo_cid`/`descricao` nunca mudam; `fonte`/`versao_snapshot`
são sobrescritos com o MESMO valor numa segunda rodada — rodar de novo
sobre o CSV já processado produz byte a byte o mesmo arquivo.

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a, CLAUDE.md). Lê e escreve só `data/cid10.csv` local; não é
importado por nenhum caminho de `app/`/`predeploy.sh` (guarda executável
abaixo, no arquivo de teste).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_CSV = _RAIZ / "data" / "cid10.csv"
_RELATORIO = _RAIZ / "docs" / "tickets" / "RELATORIO-DIFF-CID10.md"

_RE_FORMATO_CID = re.compile(r"^[A-Z]\d{2}(\.\d)?$")

VERSAO_SNAPSHOT = "V2008+remendos-2026"

_FONTE_MS_2025 = (
    "MS/SVSA/Daent — Orientações para a codificação dos demais códigos de "
    "emergência relacionados à covid-19, 1ª ed. eletrônica, 2025"
)
_FONTE_OMS_UPD34 = (
    "OMS — Atualizações 3 e 4 em relação à codificação da COVID-19 com a "
    "CID-10 (tradução MS)"
)

# codigo_cid -> nova fonte. Só os 7 remendos COVID (família U07-U12) mudam
# de citação; o resto da base (DATASUS/CID-10 V2008) fica intocado — não há
# tabela nova para importar (ver docstring acima / §6 do ticket).
_REMENDOS_RECITADOS: dict[str, str] = {
    "U07.1": _FONTE_MS_2025,
    "U07.2": _FONTE_MS_2025,
    "U09.9": _FONTE_MS_2025,
    "U10.9": _FONTE_MS_2025,
    "U12.9": _FONTE_MS_2025,
    "U08.9": _FONTE_OMS_UPD34,
    "U11.9": _FONTE_OMS_UPD34,
}

# Medido só para o relatório — NUNCA fonte de dado (§2 do ticket). Número e
# metodologia declarada, conferidos em 29/08/2026 (WebFetch em
# tabelacid.com.br/sobre — citação textual, não scraping de linhas).
GAP_TERCEIRO = {
    "site": "tabelacid.com.br",
    "total_declarado": 14736,
    "metodologia_declarada": (
        'CID-10, versão 2019/2020 (CC-BR-FIC/DataSUS) — "publicada pelo '
        "Centro Colaborador Brasileiro para a Família de Classificações "
        'Internacionais (CC-BR-FIC), Ministério da Saúde"'
    ),
}

_CAMPOS_CSV = ["codigo_cid", "descricao", "fonte", "versao_snapshot"]


def _ler_csv() -> list[dict]:
    with open(_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _recontar_formato(rows: list[dict]) -> dict:
    """AC2 do ticket: 'recontar e registrar'. O ticket citava 14.233/14.233
    como contagem de referência (do arquiteto, 29/08); a recontagem
    independente do engenheiro, na mesma execução, deu 14.240/14.240 — a
    diferença fica registrada aqui em vez de silenciosamente substituída."""
    total = len(rows)
    ok = sum(1 for r in rows if _RE_FORMATO_CID.match((r.get("codigo_cid") or "").strip()))
    letras = sorted({(r.get("codigo_cid") or "").strip()[:1] for r in rows if r.get("codigo_cid")})
    return {"total": total, "casam_formato": ok, "letras": letras}


def _transformar(rows: list[dict]) -> tuple[list[dict], dict]:
    """Stamp de versao_snapshot em toda row + recitação de fonte nas 7 rows
    de remendo COVID. Não adiciona, não remove, não altera descrição de
    nenhum código — só proveniência."""
    recitadas: list[tuple[str, str, str]] = []
    for r in rows:
        r["versao_snapshot"] = VERSAO_SNAPSHOT
        codigo = (r.get("codigo_cid") or "").strip()
        if codigo in _REMENDOS_RECITADOS:
            nova = _REMENDOS_RECITADOS[codigo]
            if r.get("fonte") != nova:
                recitadas.append((codigo, r.get("fonte", ""), nova))
            r["fonte"] = nova
    stats = {
        "total_rows": len(rows),
        "recitadas": recitadas,
        "codigos_recitados_esperados": sorted(_REMENDOS_RECITADOS),
    }
    return rows, stats


def _escrever_csv(rows: list[dict]) -> None:
    with open(_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CAMPOS_CSV)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _CAMPOS_CSV})


def _escrever_relatorio(stats: dict) -> None:
    linhas = [
        "# RELATORIO-DIFF-CID10.md — TICKET-FILA-6, teto acessível",
        "",
        "Gerado por `backend/scripts/importar_snapshot_cid10.py`. "
        f"Total de rows: {stats['total_rows']}.",
        "",
        "## Novos códigos",
        "",
        "Nenhum — não há tabela nova para importar (nenhuma fonte oficial "
        "da revisão pós-2008 foi localizada, acessível e anônima, hoje; "
        "ver §6 do TICKET-FILA-6-CID10-COMPLETO.md).",
        "",
        "## Códigos removidos",
        "",
        "Nenhum — remoção silenciosa é proibida (AC1 do ticket); nenhuma "
        "decisão de remoção foi tomada nesta rodada.",
        "",
        "## Descrições alteradas",
        "",
        "Nenhuma — só proveniência (`fonte`) muda, nunca o conteúdo clínico.",
        "",
        "## Proveniência recitada (fonte genérica → citação verificável)",
        "",
    ]
    for codigo, antes, depois in stats["recitadas"]:
        linhas.append(f"- `{codigo}`: {antes!r} → {depois!r}")
    if not stats["recitadas"]:
        linhas.append(
            "(nenhuma mudança nesta rodada — os 7 códigos já estavam "
            "recitados; script idempotente)"
        )
    fmt = stats["formato"]
    linhas += [
        "",
        "## Regressão de formato (AC2) — recontagem independente",
        "",
        f"`_RE_FORMATO_CID` casa **{fmt['casam_formato']}/{fmt['total']}** "
        f"({len(fmt['letras'])} letras). O ticket citava **14.233/14.233** "
        "como referência do arquiteto (29/08); esta recontagem, na mesma "
        f"execução, deu **{fmt['total']}/{fmt['total']}** — a diferença "
        "(7) fica registrada, não substituída silenciosamente.",
    ]
    gap = GAP_TERCEIRO["total_declarado"] - stats["total_rows"]
    linhas += [
        "",
        "## Gap medido contra espelho de terceiros (CONFERÊNCIA, NÃO FONTE)",
        "",
        f"`{GAP_TERCEIRO['site']}` declara **{GAP_TERCEIRO['total_declarado']}** "
        f"códigos. Metodologia declarada por eles: "
        f"{GAP_TERCEIRO['metodologia_declarada']}.",
        "",
        f"Base local: **{stats['total_rows']}** códigos. Gap aparente: "
        f"**{gap}** códigos — número NÃO verificado independentemente (o "
        "site é espelho de terceiro, nunca fonte primária per §2 do "
        "ticket); serve só para calibrar o tamanho do gatilho de "
        "reabertura (a) do §6.",
        "",
    ]
    _RELATORIO.write_text("\n".join(linhas), encoding="utf-8")


def main() -> None:
    rows = _ler_csv()
    if not rows:
        print(f"❌ ABORTANDO: {_CSV} vazio ou ausente")
        sys.exit(1)
    rows, stats = _transformar(rows)
    stats["formato"] = _recontar_formato(rows)
    _escrever_csv(rows)
    _escrever_relatorio(stats)
    print(f"✅ {stats['total_rows']} rows com versao_snapshot={VERSAO_SNAPSHOT!r}")
    print(f"   {len(stats['recitadas'])} rows recitadas nesta rodada "
          f"({len(_REMENDOS_RECITADOS)} esperadas na primeira execução)")
    fmt = stats["formato"]
    print(f"   formato: {fmt['casam_formato']}/{fmt['total']} "
          f"({len(fmt['letras'])} letras)")
    print(f"   Relatório: {_RELATORIO}")


if __name__ == "__main__":
    main()
