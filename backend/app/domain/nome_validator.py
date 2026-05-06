"""
nome_validator.py
=================
Ticket 64 — Validador fuzzy de nomes de prescritores (ICP Brasil × CNES × Conselho).

Objetivo: garantir que nome do certificado digital corresponde ao mesmo profissional
registrado no CNES e no conselho de classe (CRM/CFO), com tolerância a variações
reais encontradas em dados de saúde brasileiros.

Três camadas:
  1. Normalização  — acentos, caixa, espaços, pontuação (unicodedata)
  2. Extração      — nome próprio, sobrenome, preposições, sufixos
  3. Validação     — fuzzy matching com SequenceMatcher + distância de edição

Sem dependências externas — stdlib apenas (unicodedata + difflib).
"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Vocabulário controlado
# ---------------------------------------------------------------------------

_PREPOSICOES: frozenset[str] = frozenset(
    {"de", "da", "do", "dos", "das", "van", "von"}
)
_SUFIXOS: frozenset[str] = frozenset(
    {"jr", "sr", "filho", "neto", "junior"}
)

# Limiares de similaridade
_LIMIAR_NOME_PROPRIO: float = 0.85
_LIMIAR_SOBRENOME: float = 0.80


# ---------------------------------------------------------------------------
# Camada 1 — Normalização
# ---------------------------------------------------------------------------


def _normalizar(texto: str) -> str:
    """
    Normalização canônica de nome:
      - strip + lower
      - remove acentos: NFKD → encode ASCII ignorando não-ASCII
      - remove pontuação leve (mantém apenas alfanuméricos e espaços)
      - colapsa espaços múltiplos

    Exemplos:
      "JOÃO  DA SILVA." → "joao da silva"
      "Dra. Ana-Luísa"  → "dra ana luisa"
    """
    texto = texto.strip().lower()
    texto = (
        unicodedata.normalize("NFKD", texto)
        .encode("ASCII", "ignore")
        .decode("utf-8")
    )
    texto = "".join(c for c in texto if c.isalnum() or c == " ")
    return " ".join(texto.split())


# ---------------------------------------------------------------------------
# Camada 2 — Extração
# ---------------------------------------------------------------------------


def _extrair(nome: str) -> dict:
    """
    Separa o nome normalizado em componentes:
      nome_proprio : primeira palavra que não é preposição nem sufixo
      sobrenome    : restante (excluindo preposições e sufixos)
      preposicoes  : preposições encontradas (de, da, do, dos, das, van, von)
      sufixos      : sufixos encontrados (jr, sr, filho, neto, junior)

    Exemplo:
      "joao da silva filho" → {
          "nome_proprio": "joao",
          "sobrenome": "silva",
          "preposicoes": ["da"],
          "sufixos": ["filho"],
      }
    """
    tokens = _normalizar(nome).split()
    preposicoes: list[str] = []
    sufixos: list[str] = []
    palavras: list[str] = []

    for token in tokens:
        if token in _PREPOSICOES:
            preposicoes.append(token)
        elif token in _SUFIXOS:
            sufixos.append(token)
        else:
            palavras.append(token)

    nome_proprio = palavras[0] if palavras else ""
    sobrenome = " ".join(palavras[1:]) if len(palavras) > 1 else ""

    return {
        "nome_proprio": nome_proprio,
        "sobrenome": sobrenome,
        "preposicoes": preposicoes,
        "sufixos": sufixos,
    }


# ---------------------------------------------------------------------------
# Similaridade
# ---------------------------------------------------------------------------


def _sim(a: str, b: str) -> float:
    """Ratio de similaridade SequenceMatcher em [0.0, 1.0]."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _edit_distance(a: str, b: str) -> int:
    """
    Distância de edição (Levenshtein) entre duas strings.
    Implementação DP sem dependências externas.
    """
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[j] = prev[j - 1]
            else:
                dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])
    return dp[n]


def _sim_nome_proprio(a: str, b: str) -> float:
    """
    Similaridade especializada para nome próprio.

    Combina SequenceMatcher com verificação de distância de edição 1,
    necessário para capturar variantes ortográficas comuns em dados de saúde
    brasileiros onde a mesma pessoa pode ter grafias diferentes entre sistemas:

      Luiz  → Luis   (substituição z→s — SequenceMatcher dá 0.75, abaixo de 0.85)
      Filipe → Felipe (transposição i/e)

    Para nomes de comprimento >= 3 com edit_distance == 1, a similaridade
    é elevada a 0.87 (variante reconhecida), garantindo que passem no limiar 0.85.

    Returns
    -------
    float: similaridade no intervalo [0.0, 1.0]
    """
    if not a or not b:
        return 0.0
    seq_sim = SequenceMatcher(None, a, b).ratio()
    if seq_sim >= _LIMIAR_NOME_PROPRIO:
        return seq_sim
    # Variante ortográfica: nomes ≥ 3 chars diferindo por exatamente 1 edição
    if len(a) >= 3 and len(b) >= 3 and _edit_distance(a, b) <= 1:
        return max(seq_sim, 0.87)
    return seq_sim


# ---------------------------------------------------------------------------
# Camada 3 — Validação
# ---------------------------------------------------------------------------


class NomeValidator:
    """
    Validador fuzzy de nomes de prescritores para o domínio sanitário brasileiro.

    Uso típico:
        validator = NomeValidator()
        valido, motivo, confianca = validator.validar_correspondencia(
            nome_certificado="JOAO DA SILVA",
            nome_cnes="João da Silva",
            nome_conselho="JOAO SILVA",
        )

    A validação é SEMPRE bidirecionalmente auditável: o motivo descreve
    exatamente qual componente falhou e qual score foi calculado.
    """

    def validar_correspondencia(
        self,
        nome_certificado: str,
        nome_cnes: str,
        nome_conselho: str,
    ) -> tuple[bool, str, float]:
        """
        Valida correspondência de nome entre certificado ICP Brasil e fontes sanitárias.

        Regras aplicadas (por ordem de avaliação):
          REGRA 1 — Nome próprio vs CNES: SequenceMatcher + edit_distance >= 0.85
          REGRA 1 — Nome próprio vs Conselho: idem (se conselho disponível)
          REGRA 4 — Sufixos: se ambos têm sufixo, devem ser iguais
          REGRA 2 — Sobrenome vs CNES: >= 0.80 (se ambos têm sobrenome)
          REGRA 2 — Sobrenome vs Conselho: >= 0.80 (se ambos têm sobrenome)
          REGRA 3 — Preposições: ignoradas completamente
          REGRA 5 — Confiança: min(sim_cnes_full, sim_conselho_full)

        Parameters
        ----------
        nome_certificado : str
            Nome extraído do certificado digital ICP Brasil.
        nome_cnes : str
            Nome registrado no CNES (snapshot DataSUS).
        nome_conselho : str
            Nome registrado no conselho de classe (CRM / CFO).
            Pode ser igual a nome_cnes quando apenas o CNES está disponível.

        Returns
        -------
        tuple[bool, str, float]
            (valido, motivo, confianca)
            - valido    : True se os nomes correspondem ao mesmo profissional
            - motivo    : "ok" ou descrição precisa da falha
            - confianca : score [0.0, 1.0] — min(sim_cnes, sim_conselho)
        """
        cert = _extrair(nome_certificado)
        cnes = _extrair(nome_cnes)
        # Conselho pode não estar disponível; tratar string vazia graciosamente
        cons = _extrair(nome_conselho) if nome_conselho else {
            "nome_proprio": "", "sobrenome": "", "preposicoes": [], "sufixos": []
        }

        # ── REGRA 1 — Nome próprio vs CNES (obrigatório) ──────────────────
        sim_prop_cnes = _sim_nome_proprio(cert["nome_proprio"], cnes["nome_proprio"])
        if sim_prop_cnes < _LIMIAR_NOME_PROPRIO:
            return (
                False,
                (
                    f"nome_proprio_divergente_cnes: "
                    f"cert='{cert['nome_proprio']}' "
                    f"cnes='{cnes['nome_proprio']}' "
                    f"(sim={sim_prop_cnes:.2f})"
                ),
                0.0,
            )

        # ── REGRA 1 — Nome próprio vs Conselho (se disponível) ────────────
        sim_prop_cons = sim_prop_cnes  # padrão: mesmo score quando conselho = cnes
        if cons["nome_proprio"]:
            sim_prop_cons = _sim_nome_proprio(
                cert["nome_proprio"], cons["nome_proprio"]
            )
            if sim_prop_cons < _LIMIAR_NOME_PROPRIO:
                return (
                    False,
                    (
                        f"nome_proprio_divergente_conselho: "
                        f"cert='{cert['nome_proprio']}' "
                        f"conselho='{cons['nome_proprio']}' "
                        f"(sim={sim_prop_cons:.2f})"
                    ),
                    0.0,
                )

        # ── REGRA 4 — Sufixos ─────────────────────────────────────────────
        if cert["sufixos"] and cnes["sufixos"]:
            if set(cert["sufixos"]) != set(cnes["sufixos"]):
                return (
                    False,
                    (
                        f"sufixo_divergente_cnes: "
                        f"cert={cert['sufixos']} cnes={cnes['sufixos']}"
                    ),
                    0.0,
                )
        if cert["sufixos"] and cons["sufixos"]:
            if set(cert["sufixos"]) != set(cons["sufixos"]):
                return (
                    False,
                    (
                        f"sufixo_divergente_conselho: "
                        f"cert={cert['sufixos']} conselho={cons['sufixos']}"
                    ),
                    0.0,
                )

        # ── REGRA 2 — Sobrenome vs CNES (se ambos têm sobrenome) ──────────
        if cert["sobrenome"] and cnes["sobrenome"]:
            sim_sob_cnes = _sim(cert["sobrenome"], cnes["sobrenome"])
            if sim_sob_cnes < _LIMIAR_SOBRENOME:
                return (
                    False,
                    (
                        f"sobrenome_divergente_cnes: "
                        f"cert='{cert['sobrenome']}' "
                        f"cnes='{cnes['sobrenome']}' "
                        f"(sim={sim_sob_cnes:.2f})"
                    ),
                    0.0,
                )

        # ── REGRA 2 — Sobrenome vs Conselho (se ambos têm sobrenome) ──────
        if cert["sobrenome"] and cons["sobrenome"]:
            sim_sob_cons = _sim(cert["sobrenome"], cons["sobrenome"])
            if sim_sob_cons < _LIMIAR_SOBRENOME:
                return (
                    False,
                    (
                        f"sobrenome_divergente_conselho: "
                        f"cert='{cert['sobrenome']}' "
                        f"conselho='{cons['sobrenome']}' "
                        f"(sim={sim_sob_cons:.2f})"
                    ),
                    0.0,
                )

        # ── REGRA 3 — Preposições: ignoradas completamente ────────────────
        # (tratadas pelo _extrair, não entram nas comparações)

        # ── REGRA 5 — Confiança = min(sim_cnes_full, sim_conselho_full) ───
        norm_cert = _normalizar(nome_certificado)
        norm_cnes = _normalizar(nome_cnes)
        norm_cons = _normalizar(nome_conselho) if nome_conselho else norm_cnes

        sim_cnes_full = _sim(norm_cert, norm_cnes)
        sim_cons_full = _sim(norm_cert, norm_cons)
        confianca = min(sim_cnes_full, sim_cons_full)

        return True, "ok", confianca
