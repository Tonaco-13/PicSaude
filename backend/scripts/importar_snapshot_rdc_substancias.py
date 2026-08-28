"""
importar_snapshot_rdc_substancias.py
======================================
DESENHO-TALAO-DIGITAL-SNCR.md §1/§1.1 — G1, Opção 2 (mecânica agora, dado
depois). Importador offline versionado da base regulatória COMPLETA de
substâncias controladas (Anexo I da Portaria SVS/MS 344/1998, consolidado
até a emenda vigente — HOJE isso é a RDC 1.036/2026; NÃO "anexos da RDC
1.000/2025", que é a norma do receituário eletrônico/SNCR, não das listas
de substância — erro corrigido no §1.1 do desenho).

ESTADO EM 28/08: SEM DADO REAL AINDA
--------------------------------------
Este script existe e funciona, mas ninguém o rodou com a fonte real. A
extração de "toda a Portaria 344/98 Anexo I" por busca web se mostrou
inviável nesta sessão — a ferramenta de busca RESUME listas grandes em vez
de enumerar (testado, documentado no §1.1), e dado regulatório carimbado
não se estampa de resumo. O texto consolidado depende de um gesto humano
(Fabiano: abrir o Anvisa Legis, IMPRIMIR → salvar PDF — a rota programática
está fechada por sessão interativa) e de uma transcrição posterior para o
formato JSON que este script consome (ver `_SCHEMA_ESPERADO` abaixo).

Até esse dado chegar, `catalogo_regulatorio_carimbo` permanece com tudo
NULL (estado que a migração 2fb9182a0846 cria) — `validar_classificacao`
continua em modo cauteloso, exatamente como sempre foi. É o "carimbo
explicitamente pendente" que a Opção 2 aprovou.

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a). Roda manualmente, na máquina do desenvolvedor.

FORMATO DE ENTRADA ESPERADO (JSON)
------------------------------------
{
  "fonte": "Portaria SVS/MS 344/1998, Anexo I (consolidado até RDC X/AAAA)",
  "versao": "RDC X/AAAA",
  "data_snapshot": "AAAA-MM-DD",
  "entradas": [
    {"dcb": "Morfina", "classe_controle": "A1", "tipo_retencao": null, "observacao": null},
    {"dcb": "Amoxicilina", "classe_controle": null, "tipo_retencao": "antimicrobiano", "observacao": null},
    ...
  ]
}

`fonte`/`versao`/`data_snapshot` descrevem O SNAPSHOT INTEIRO (uma
publicação só) — não por entrada. Cada entrada precisa de `dcb` e ao menos
um entre `classe_controle`/`tipo_retencao` (uma entrada sem nenhum dos
dois não pertenceria à lista de controlados).

Uso
---
    python3 backend/scripts/importar_snapshot_rdc_substancias.py \\
        --arquivo data/fontes-oficiais/anvisa-controlados-2026-08-28/consolidado.json

Idempotente: `aplicar_snapshot_carimbado` faz upsert por `dcb_normalizada`
(mesma disciplina do seed curado) e ATIVA o carimbo — rodar de novo com o
mesmo arquivo produz o mesmo estado final.

AC5 do desenho (as 56 curadas migram/reconciliam contra a lista oficial,
divergências relatadas) fica para quando este script rodar com dado real
pela primeira vez — não há o que reconciliar contra um arquivo que ainda
não existe.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.database import get_conn
from app.domain.catalogo_seed import aplicar_snapshot_carimbado


def _validar_snapshot(dado: dict) -> None:
    for campo in ("fonte", "versao", "data_snapshot", "entradas"):
        if not dado.get(campo):
            raise ValueError(f"campo obrigatório ausente/vazio no snapshot: {campo!r}")

    if not isinstance(dado["entradas"], list) or not dado["entradas"]:
        raise ValueError("'entradas' precisa ser uma lista não vazia")

    dcbs_vistos: set[str] = set()
    for i, entrada in enumerate(dado["entradas"]):
        dcb = (entrada.get("dcb") or "").strip()
        if not dcb:
            raise ValueError(f"entradas[{i}]: 'dcb' ausente/vazio")
        if dcb.lower() in dcbs_vistos:
            raise ValueError(f"entradas[{i}]: DCB duplicada no snapshot: {dcb!r}")
        dcbs_vistos.add(dcb.lower())
        if not entrada.get("classe_controle") and not entrada.get("tipo_retencao"):
            raise ValueError(
                f"entradas[{i}] ({dcb!r}): sem classe_controle e sem "
                "tipo_retencao — não pertence a uma lista de controlados"
            )


def _entradas_para_tuplas(entradas: list[dict]):
    for e in entradas:
        yield (
            e["dcb"],
            e.get("classe_controle"),
            e.get("tipo_retencao"),
            e.get("observacao"),
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arquivo", required=True,
        help="Caminho do JSON do snapshot consolidado (ver formato no docstring)",
    )
    args = parser.parse_args(argv)

    caminho = Path(args.arquivo)
    if not caminho.is_file():
        print(
            f"❌ ABORTANDO: {caminho} não existe. Este script depende do "
            "gesto humano descrito no §1.1 do DESENHO-TALAO-DIGITAL-SNCR.md "
            "— sem o arquivo, não há o que importar."
        )
        sys.exit(1)

    dado = json.loads(caminho.read_text(encoding="utf-8"))
    _validar_snapshot(dado)

    conn = get_conn()
    try:
        resultado = aplicar_snapshot_carimbado(
            conn,
            fonte=dado["fonte"],
            versao=dado["versao"],
            data_snapshot=dado["data_snapshot"],
            entradas=_entradas_para_tuplas(dado["entradas"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"✅ Snapshot carimbado: {resultado['entradas']} entradas")
    print(f"   Fonte: {resultado['fonte']}")
    print(f"   Versão: {resultado['versao']}  ·  Data: {resultado['data_snapshot']}")
    print("   validar_classificacao() agora afirma 'não-controlado' para ausências.")


if __name__ == "__main__":
    main()
