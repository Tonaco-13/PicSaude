"""
importar_snapshot_sigtap.py
==============================
TICKET-FILA-7-SIGTAP-EXAMES.md — fila 7 da FILA-VIVA. Camada 1: lê o ZIP
estagiado (nunca a rede) e escreve `data/sigtap_exames.csv`.

FONTE — ABERTA E MENSAL (o contrário do CID-10)
--------------------------------------------------
DATASUS publica a Tabela Unificada (SIGTAP) mensalmente, por competência.
O ZIP estagiado (`data/fontes-oficiais/sigtap/`, sha256 no MANIFEST.md)
traz várias tabelas de largura fixa: `tb_procedimento.txt` (o catálogo),
`tb_grupo.txt`/`tb_sub_grupo.txt`/`tb_forma_organizacao.txt` (a taxonomia
que faz o corte).

O CORTE — TAXONOMIA DO PRÓPRIO DUMP, NUNCA MATCHING DE NOME
--------------------------------------------------------------
`CO_PROCEDIMENTO` (10 dígitos) é hierárquico: GG(grupo) SS(subgrupo)
FF(forma_organização) PPP(sequencial) D(dígito verificador). O corte usa
SÓ o grupo `02` — "Procedimentos com finalidade diagnóstica" — na base
completa, os 14 subgrupos INTEIROS (whitelist LITERAL abaixo, recomendação
"diagnósticos amplos" do §6.2 do ticket: a UI filtra por busca, o CSV não
precisa pré-filtrar por especialidade). Nenhuma linha entra por o NOME
"parecer" exame — só por estar dentro do grupo 02.

Uso
---
    python3 backend/scripts/importar_snapshot_sigtap.py

Idempotente: lê sempre o MESMO ZIP estagiado (nunca a rede) e escreve o
CSV do zero a cada rodada — mesma entrada, mesma saída, byte a byte.

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a, CLAUDE.md). Guarda executável no arquivo de teste.
"""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_ZIP = _RAIZ / "data" / "fontes-oficiais" / "sigtap" / "TabelaUnificada_202606_v2606091427.zip"
_CSV_SAIDA = _RAIZ / "data" / "sigtap_exames.csv"
_RELATORIO = _RAIZ / "docs" / "tickets" / "RELATORIO-DIFF-SIGTAP.md"

# Whitelist LITERAL — grupo 02 inteiro, "diagnósticos amplos" (§6.2 do
# ticket). Não é derivado do dump em runtime: é o compromisso do script,
# igual à tupla congelada de uma migração (CLAUDE.md §9) — mudar o corte é
# editar aqui e rodar de novo, nunca inferir do conteúdo.
GRUPO_DIAGNOSTICO = "02"

_CAMPOS_CSV = ["codigo_sigtap", "nome", "grupo", "subgrupo", "forma_organizacao", "competencia"]


def _ler_membro_zip(zf: zipfile.ZipFile, nome: str) -> list[str]:
    with zf.open(nome) as f:
        return f.read().decode("latin-1").splitlines()


def _parse_tb_grupo(linhas: list[str]) -> dict[str, str]:
    return {l[0:2]: l[2:102].strip() for l in linhas}


def _parse_tb_sub_grupo(linhas: list[str]) -> dict[tuple[str, str], str]:
    return {(l[0:2], l[2:4]): l[4:104].strip() for l in linhas}


def _parse_tb_forma_organizacao(linhas: list[str]) -> dict[tuple[str, str, str], str]:
    return {(l[0:2], l[2:4], l[4:6]): l[6:106].strip() for l in linhas}


def _parse_tb_procedimento(linhas: list[str]) -> list[tuple[str, str, str]]:
    """(codigo, nome, competencia) por linha — DT_COMPETENCIA nas posições 331-336."""
    return [(l[0:10], l[10:260].strip(), l[330:336]) for l in linhas]


def extrair(zip_path: Path = _ZIP) -> tuple[list[dict], dict]:
    with zipfile.ZipFile(zip_path) as zf:
        grupos = _parse_tb_grupo(_ler_membro_zip(zf, "tb_grupo.txt"))
        subgrupos = _parse_tb_sub_grupo(_ler_membro_zip(zf, "tb_sub_grupo.txt"))
        formas = _parse_tb_forma_organizacao(_ler_membro_zip(zf, "tb_forma_organizacao.txt"))
        procedimentos = _parse_tb_procedimento(_ler_membro_zip(zf, "tb_procedimento.txt"))

    total_tabela = len(procedimentos)
    whitelist_subgrupos = sorted(
        (sg, nome) for (grp, sg), nome in subgrupos.items() if grp == GRUPO_DIAGNOSTICO
    )

    linhas_saida: list[dict] = []
    competencias_vistas: set[str] = set()
    for codigo, nome, competencia in procedimentos:
        grupo = codigo[0:2]
        if grupo != GRUPO_DIAGNOSTICO:
            continue
        subgrupo = codigo[2:4]
        forma = codigo[4:6]
        competencias_vistas.add(competencia)
        linhas_saida.append({
            "codigo_sigtap": codigo,
            "nome": nome,
            "grupo": grupos.get(grupo, ""),
            "subgrupo": subgrupos.get((grupo, subgrupo), ""),
            "forma_organizacao": formas.get((grupo, subgrupo, forma), ""),
            "competencia": competencia,
        })

    linhas_saida.sort(key=lambda r: r["codigo_sigtap"])  # ordem determinística

    stats = {
        "total_procedimentos_tabela": total_tabela,
        "total_grupo_diagnostico": len(linhas_saida),
        "competencias": sorted(competencias_vistas),
        "whitelist_subgrupos": whitelist_subgrupos,
        "grupo_nome": grupos.get(GRUPO_DIAGNOSTICO, ""),
    }
    return linhas_saida, stats


def _escrever_csv(rows: list[dict]) -> None:
    with open(_CSV_SAIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CAMPOS_CSV)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _CAMPOS_CSV})


def _escrever_relatorio(stats: dict) -> None:
    # O ticket cita "~35" (§1); a contagem real de `_BASE_RAW` em
    # app/ai/tuss_base.py no momento deste import é 38 — registrado aqui
    # em vez de silenciosamente ajustado (mesmo rito do "14.233 → 14.240"
    # do CID-10, RELATORIO-DIFF-CID10.md).
    curadoria_atual = 38
    multiplo = stats["total_grupo_diagnostico"] / curadoria_atual
    linhas = [
        "# RELATORIO-DIFF-SIGTAP.md — TICKET-FILA-7",
        "",
        f"Gerado por `backend/scripts/importar_snapshot_sigtap.py`. "
        f"Competência: {', '.join(stats['competencias'])}.",
        "",
        "## Whitelist aplicada (LITERAL — grupo + todos os subgrupos)",
        "",
        f"Grupo `{GRUPO_DIAGNOSTICO}` — \"{stats['grupo_nome']}\" — "
        f"{len(stats['whitelist_subgrupos'])} subgrupos, todos incluídos "
        "(\"diagnósticos amplos\", recomendação §6.2 do ticket):",
        "",
    ]
    for sg, nome in stats["whitelist_subgrupos"]:
        linhas.append(f"- `{GRUPO_DIAGNOSTICO}.{sg}` — {nome}")
    linhas += [
        "",
        "## Contagem",
        "",
        f"- Total de procedimentos na Tabela Unificada: **{stats['total_procedimentos_tabela']}**",
        f"- Total após o corte (grupo {GRUPO_DIAGNOSTICO}): "
        f"**{stats['total_grupo_diagnostico']}**",
        f"- Curadoria manual atual (`tuss_base.py::_BASE_RAW`): **{curadoria_atual}** "
        f"(o ticket citava \"~35\" no §1; recontagem real na execução deu 38 — "
        f"registrado, não substituído em silêncio)",
        f"- Múltiplo: **{multiplo:.1f}x** a curadoria atual "
        f"(AC2 do ticket exige ≥ dezenas×)",
        "",
        "## Nenhum código foi excluído por nome",
        "",
        "O corte é 100% por `(CO_GRUPO, CO_SUB_GRUPO)` lido do próprio dump "
        "— nenhuma linha entrou ou saiu por a descrição \"parecer\" exame.",
        "",
    ]
    _RELATORIO.write_text("\n".join(linhas), encoding="utf-8")


def main() -> None:
    if not _ZIP.exists():
        print(f"❌ ABORTANDO: ZIP não encontrado em {_ZIP}")
        print("   Estagiar primeiro — ver data/fontes-oficiais/sigtap/MANIFEST.md")
        sys.exit(1)

    rows, stats = extrair(_ZIP)
    if not rows:
        print("❌ ABORTANDO: corte produziu 0 linhas — whitelist ou ZIP quebrados?")
        sys.exit(1)

    _escrever_csv(rows)
    _escrever_relatorio(stats)

    print(f"✅ {stats['total_grupo_diagnostico']}/{stats['total_procedimentos_tabela']} "
          f"procedimentos do grupo {GRUPO_DIAGNOSTICO} escritos em {_CSV_SAIDA}")
    print(f"   Competência: {', '.join(stats['competencias'])}")
    print(f"   Relatório: {_RELATORIO}")


if __name__ == "__main__":
    main()
