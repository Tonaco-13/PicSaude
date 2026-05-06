"""
retencao.py
===========
Vocabulário e referências para o GRUPO_RETENCAO — Ticket 18.

CONTEXTO REGULATÓRIO
--------------------
A Portaria SVS/MS nº 344/1998 classifica substâncias por LISTAS
(A, B, C, D) — campo `classe_controle` no PicSaúde.

A RDC Anvisa nº 471/2021 (que substituiu a RDC 20/2011) regula
medicamentos sujeitos à retenção de receita por SUBSTÂNCIA (DCB),
fora do escopo da Portaria 344. Atualmente cobre:

- Antimicrobianos (RDC 471/2021 + IN 83/2021)
- Agonistas de GLP-1 (incluídos pela IN 360/2025, vigente desde 23/06/2025)

Os dois sistemas regulatórios são INDEPENDENTES:

  Portaria 344/1998 — listas → campo classe_controle
  RDC 471/2021      — substância → campo tipo_retencao   (este módulo)

Referência SNGPC: código "1" (RDC 471) vs código "2" (Portaria 344).
A referência ao SNGPC é apenas documental — não é usada na lógica
de roteamento do motor regulatório neste ticket.

DESIGN
------
Este módulo é importado por `motor_regulatorio.py` E `medicamento.py`.
Mantê-lo enxuto — apenas constantes — evita o ciclo de import que
existiria se cada um chamasse o outro.
"""
from __future__ import annotations

from typing import FrozenSet, Mapping


# ---------------------------------------------------------------------------
# Vocabulário controlado
# ---------------------------------------------------------------------------

# Tipos de retenção aceitos. Único set fonte-de-verdade — não duplicar.
TIPOS_RETENCAO_VALIDOS: FrozenSet[str] = frozenset({
    "antimicrobiano",
    "glp1_agonista",
})


# Labels humanos (display, documentação, mensagens de erro).
TIPOS_RETENCAO_LABELS: Mapping[str, str] = {
    "antimicrobiano": "Antimicrobiano (RDC 471/2021 + IN 83/2021)",
    "glp1_agonista":  "Agonista GLP-1 (IN 360/2025)",
}


# Substâncias GLP-1 documentadas pela IN 360/2025 (vigente desde 23/06/2025).
# REFERÊNCIA — não é usada para validação. O backend não tem catálogo
# de substâncias por DCB hoje; o prescritor declara `tipo_retencao` no
# nível do item.
#
# Exenatida foi EXCLUÍDA da IN 360/2025 por não haver registro válido
# no Brasil. Monitorar em ticket futuro caso a Anvisa publique
# atualização.
SUBSTANCIAS_GLP1_IN360: tuple[str, ...] = (
    "semaglutida",
    "liraglutida",
    "dulaglutida",
    "tirzepatida",
    "lixisenatida",
)


def tipo_retencao_valido(valor: str | None) -> bool:
    """True se `valor` está em TIPOS_RETENCAO_VALIDOS (case-sensitive,
    após strip+lower). NULL/'' são considerados ausentes (retornam False)."""
    if valor is None:
        return False
    v = str(valor).strip().lower()
    return v in TIPOS_RETENCAO_VALIDOS
