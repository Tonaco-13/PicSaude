"""
catalogo_seed.py
================
Seed inicial do catálogo regulatório de substâncias — Ticket 20.

Conteúdo
--------
1. 5 agonistas de GLP-1 (IN 360/2025)
2. 30 antimicrobianos mais prescritos na atenção primária (IN 83/2021)
3. 20 substâncias mais prescritas da Portaria SVS/MS 344/1998

Idempotência
------------
A função `aplicar_seed_catalogo(conn)` é idempotente: usa UPSERT por
`dcb_normalizada`. Re-execuções não duplicam, atualizam.

REVISÃO REGULATÓRIA NECESSÁRIA
-------------------------------
A classificação de cada substância foi compilada com base nas referências
do Ticket 20. Antes de usar em produção, conferir cada DCB contra a
versão vigente:
  - Portaria SVS/MS 344/1998 (com atualizações por RDCs)
  - IN Anvisa 83/2021 (antimicrobianos)
  - IN Anvisa 360/2025 (GLP-1)
"""
from __future__ import annotations

from typing import Iterable

from app.domain.catalogo_regulatorio import normalizar_dcb


# ---------------------------------------------------------------------------
# Estrutura do seed
# ---------------------------------------------------------------------------
# Cada entrada: (dcb_display, classe_controle, tipo_retencao, fonte, observacao)

SEED_GLP1: tuple[tuple[str, str | None, str | None, str, str | None], ...] = (
    ("Semaglutida",   None, "glp1_agonista", "in_360_2025", None),
    ("Liraglutida",   None, "glp1_agonista", "in_360_2025", None),
    ("Dulaglutida",   None, "glp1_agonista", "in_360_2025", None),
    ("Tirzepatida",   None, "glp1_agonista", "in_360_2025", None),
    ("Lixisenatida",  None, "glp1_agonista", "in_360_2025", None),
    # Exenatida — IN 360/2025 EXCLUI por falta de registro válido no
    # Brasil. Inserida com ativo=False como histórico/monitoramento.
    # Ver __seed_inativos__ abaixo.
)


# Antimicrobianos mais prescritos (atenção primária). Lista parcial da
# IN 83/2021. Verificação regulatória individual ainda pendente — usar
# observacao para sinalizar.
SEED_ANTIMICROBIANOS: tuple[tuple[str, str | None, str | None, str, str | None], ...] = (
    ("Amoxicilina",                None, "antimicrobiano", "in_83_2021", None),
    ("Azitromicina",               None, "antimicrobiano", "in_83_2021", None),
    ("Cefalexina",                 None, "antimicrobiano", "in_83_2021", None),
    ("Ciprofloxacino",             None, "antimicrobiano", "in_83_2021", None),
    ("Sulfametoxazol + Trimetoprima", None, "antimicrobiano", "in_83_2021", None),
    ("Metronidazol",               None, "antimicrobiano", "in_83_2021", None),
    ("Amoxicilina + Clavulanato",  None, "antimicrobiano", "in_83_2021", None),
    ("Doxiciclina",                None, "antimicrobiano", "in_83_2021", None),
    ("Levofloxacino",              None, "antimicrobiano", "in_83_2021", None),
    ("Norfloxacino",               None, "antimicrobiano", "in_83_2021", None),
    ("Nitrofurantoína",            None, "antimicrobiano", "in_83_2021", None),
    ("Ceftriaxona",                None, "antimicrobiano", "in_83_2021", None),
    ("Clindamicina",               None, "antimicrobiano", "in_83_2021", None),
    ("Eritromicina",               None, "antimicrobiano", "in_83_2021", None),
    ("Gentamicina",                None, "antimicrobiano", "in_83_2021", None),
    ("Ampicilina",                 None, "antimicrobiano", "in_83_2021", None),
    ("Cefalotina",                 None, "antimicrobiano", "in_83_2021", None),
    ("Cefazolina",                 None, "antimicrobiano", "in_83_2021", None),
    ("Cefuroxima",                 None, "antimicrobiano", "in_83_2021", None),
    ("Claritromicina",             None, "antimicrobiano", "in_83_2021", None),
    ("Fluconazol",                 None, "antimicrobiano", "in_83_2021",
        "Conferir IN 83/2021 — antifúngico pode não estar listado entre os "
        "antimicrobianos com retenção."),
    ("Moxifloxacino",              None, "antimicrobiano", "in_83_2021", None),
    ("Oxacilina",                  None, "antimicrobiano", "in_83_2021", None),
    ("Penicilina Benzatina",       None, "antimicrobiano", "in_83_2021", None),
    ("Penicilina V",               None, "antimicrobiano", "in_83_2021", None),
    # Rifampicina: dupla classificação. Portaria 344 lista (C1) + IN 83/2021.
    ("Rifampicina", "C1", "antimicrobiano", "portaria_344+in_83_2021",
        "Dupla classificação: Portaria 344 (C1) e IN 83/2021 (antimicrobiano). "
        "Motor regulatório aplica Portaria 344 por prevalência."),
    ("Tetraciclina",               None, "antimicrobiano", "in_83_2021", None),
    ("Tobramicina",                None, "antimicrobiano", "in_83_2021", None),
    ("Vancomicina",                None, "antimicrobiano", "in_83_2021", None),
    ("Sulfadiazina",               None, "antimicrobiano", "in_83_2021", None),
)


SEED_PORTARIA_344: tuple[tuple[str, str | None, str | None, str, str | None], ...] = (
    # Benzodiazepínicos (B1)
    ("Clonazepam",   "B1", None, "portaria_344", None),
    ("Diazepam",     "B1", None, "portaria_344", None),
    ("Alprazolam",   "B1", None, "portaria_344", None),
    ("Bromazepam",   "B1", None, "portaria_344", None),
    # Antidepressivos (C1)
    ("Fluoxetina",      "C1", None, "portaria_344", None),
    ("Sertralina",      "C1", None, "portaria_344", None),
    ("Escitalopram",    "C1", None, "portaria_344", None),
    ("Venlafaxina",     "C1", None, "portaria_344", None),
    ("Duloxetina",      "C1", None, "portaria_344", None),
    ("Amitriptilina",   "C1", None, "portaria_344", None),
    # Opioides leves
    ("Codeína",   "A2", None, "portaria_344", None),
    ("Tramadol",  "B1", None, "portaria_344", None),
    # Hipnóticos / antiepilépticos
    ("Zolpidem",     "B1", None, "portaria_344", None),
    ("Fenobarbital", "B1", None, "portaria_344", None),
    # Estimulantes
    ("Metilfenidato",     "A3", None, "portaria_344", None),
    ("Lisdexanfetamina",  "A3", None, "portaria_344", None),
    # Retinoides / talidomida
    ("Isotretinoína", "D1", None, "portaria_344", None),
    ("Talidomida",    "D1", None, "portaria_344", None),
    # Opioides fortes
    ("Morfina",    "A1", None, "portaria_344", None),
    ("Fentanila",  "A1", None, "portaria_344", None),
)


# Substâncias INATIVAS (mantidas como histórico).
SEED_INATIVOS: tuple[tuple[str, str | None, str | None, str, str | None], ...] = (
    ("Exenatida", None, None, "in_360_2025",
        "Excluída da IN 360/2025 — sem registro válido no Brasil. "
        "Mantida como ativo=False para monitoramento."),
)


# ---------------------------------------------------------------------------
# Aplicação do seed
# ---------------------------------------------------------------------------

def _upsert(conn, dcb_display: str, classe: str | None,
            tipo_ret: str | None, fonte: str, observacao: str | None,
            ativo: bool = True) -> None:
    norm = normalizar_dcb(dcb_display)
    if not norm:
        raise RuntimeError(f"DCB inválida: {dcb_display!r}")

    # Postgres: ON CONFLICT é traduzido por database.py via _pg_translate.
    # Padrão usado aqui é simples: tentar UPDATE primeiro, depois INSERT
    # se não existir. Idempotente.
    existente = conn.execute(
        "SELECT id FROM catalogo_substancias WHERE dcb_normalizada = ?",
        (norm,),
    ).fetchone()
    if existente:
        conn.execute(
            """
            UPDATE catalogo_substancias
               SET dcb = ?,
                   dcb_display = ?,
                   classe_controle = ?,
                   tipo_retencao = ?,
                   fonte = ?,
                   observacao = ?,
                   ativo = ?
             WHERE dcb_normalizada = ?
            """,
            (dcb_display, dcb_display, classe, tipo_ret, fonte,
             observacao, ativo, norm),
        )
    else:
        conn.execute(
            """
            INSERT INTO catalogo_substancias
                (dcb, dcb_normalizada, dcb_display, classe_controle,
                 tipo_retencao, fonte, observacao, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dcb_display, norm, dcb_display, classe, tipo_ret, fonte,
             observacao, ativo),
        )


def _aplicar_lista(
    conn,
    lista: Iterable[tuple[str, str | None, str | None, str, str | None]],
    *,
    ativo: bool = True,
) -> int:
    n = 0
    for dcb, classe, tipo_ret, fonte, obs in lista:
        _upsert(conn, dcb, classe, tipo_ret, fonte, obs, ativo=ativo)
        n += 1
    return n


def aplicar_seed_catalogo(conn) -> dict:
    """Aplica o seed completo. Retorna contagens por categoria."""
    n_glp1 = _aplicar_lista(conn, SEED_GLP1)
    n_amc = _aplicar_lista(conn, SEED_ANTIMICROBIANOS)
    n_p344 = _aplicar_lista(conn, SEED_PORTARIA_344)
    n_inativos = _aplicar_lista(conn, SEED_INATIVOS, ativo=False)
    return {
        "glp1":            n_glp1,
        "antimicrobianos": n_amc,
        "portaria_344":    n_p344,
        "inativos":        n_inativos,
        "total":           n_glp1 + n_amc + n_p344 + n_inativos,
    }
