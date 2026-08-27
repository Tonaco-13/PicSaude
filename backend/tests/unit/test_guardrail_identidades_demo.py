"""Guard-rail — identidades da demo têm FONTE ÚNICA.

TICKET-DEMO-IDENTIDADES-FONTE-UNICA.

A circulação da vitrine fecha num só cidadão: uma receita emitida no
`prescritor.html` cai na carteira DESTE mesmo CPF no `cidadao.html`. Isso só se
sustenta se nenhuma tela chumbar o seu próprio literal — a identidade tem de vir
de um lugar só. Dois checks executáveis materializam a regra:

  (A) ESTÁTICO — nenhum CPF (11 díg.) ou CNPJ (14 díg.) literal nos HTMLs da
      raiz, exceto o sentinela `00000000000` (§6a). A casa dos valores é o
      `config.js` (`DEMO.*`), que este scan não olha.

  (B) CONCORDÂNCIA — os mesmos valores vivem no `seed_demo.py` (lado servidor).
      Frontend em JS e seed em Python não compartilham arquivo; então a régua
      não é "importam do mesmo módulo" — é "os dois batem", travado no gate.

O check (A) sem prova de mordida é decoração (lição do R2, §2a). O
`test_o_guardrail_morde` reintroduz um literal solto num HTML de mentira e exige
que o scanner acuse — se ele deixar passar, o teste falha.

Um estabelecimento por PAPEL: farmácia ≠ clínica. Um CNPJ não pode ser as duas
coisas, então há dois CNPJs nomeados (`DEMO.farmacia`, `DEMO.clinica`), cada um
com o seu par no seed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# backend/tests/unit/ -> raiz do repo
_RAIZ = Path(__file__).resolve().parents[3]
_CONFIG_JS = _RAIZ / "config.js"
_SEED_PY = _RAIZ / "backend" / "seed_demo.py"

# Sentinela de prescrição física sem identificação digital (§6a). Matematicamente
# inválido, nunca um cidadão real — exceção legítima ao scan.
_SENTINELA = "00000000000"

# 11 ou 14 dígitos consecutivos que NÃO são pedaço de um número maior. O
# lookbehind/lookahead é o que faz um CNS de 15 dígitos (ex.: 980001112223334,
# a Dra. Demo) NÃO ser confundido com um CNPJ de 14 — CNS não está no escopo.
_CPF_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_CNPJ_RE = re.compile(r"(?<!\d)\d{14}(?!\d)")


def _flagrantes(texto: str) -> list[str]:
    """Literais de identidade (CPF/CNPJ) chumbados no texto, exceto o sentinela."""
    achados: list[str] = []
    for ln, linha in enumerate(texto.splitlines(), 1):
        for m in _CPF_RE.finditer(linha):
            if m.group() != _SENTINELA:
                achados.append(f"linha {ln}: CPF literal {m.group()}")
        for m in _CNPJ_RE.finditer(linha):
            achados.append(f"linha {ln}: CNPJ literal {m.group()}")
    return achados


def _htmls_da_raiz() -> list[Path]:
    return sorted(_RAIZ.glob("*.html"))


# ---------------------------------------------------------------------------
# (A) scan estático
# ---------------------------------------------------------------------------

def test_nenhum_cpf_ou_cnpj_literal_nos_htmls():
    """Toda identidade de tela vem de `DEMO.*` — nada chumbado nos HTMLs."""
    ofensas: dict[str, list[str]] = {}
    for html in _htmls_da_raiz():
        achados = _flagrantes(html.read_text(encoding="utf-8"))
        if achados:
            ofensas[html.name] = achados

    assert not ofensas, (
        "CPF/CNPJ literal chumbado em tela (deve referenciar DEMO.* de config.js):\n"
        + "\n".join(
            f"  {nome}:\n" + "\n".join(f"    - {a}" for a in achados)
            for nome, achados in ofensas.items()
        )
    )


def test_o_guardrail_morde():
    """PROVA POR MUTAÇÃO: reintroduza um literal solto e o scanner acusa.

    Sem isto, uma guarda que nunca falha quando deveria é decoração. Cobre CPF,
    CNPJ e a exceção do sentinela numa tacada.
    """
    com_cpf = '<input value="70890123456">'
    com_cnpj = "<input value='12345678000199'>"
    so_sentinela = f'<input value="{_SENTINELA}">'
    com_cns = '{ cns: "980001112223334" }'  # 15 díg. — fora do escopo

    assert _flagrantes(com_cpf), "scanner deixou passar um CPF literal"
    assert _flagrantes(com_cnpj), "scanner deixou passar um CNPJ literal"
    assert not _flagrantes(so_sentinela), "sentinela 00000000000 não é ofensa (§6a)"
    assert not _flagrantes(com_cns), "CNS de 15 dígitos não é CPF nem CNPJ"


# ---------------------------------------------------------------------------
# (B) concordância config.js × seed_demo.py
# ---------------------------------------------------------------------------

def _extrair(texto: str, regex: str, rotulo: str) -> str:
    m = re.search(regex, texto, re.S)
    assert m, f"não encontrei {rotulo} (o formato mudou? atualize o guard-rail)"
    return m.group(1)


def _identidades_config() -> dict[str, str]:
    txt = _CONFIG_JS.read_text(encoding="utf-8")
    return {
        "cidadao_cpf":  _extrair(txt, r"cidadao:\s*\{\s*cpf:\s*'(\d{11})'", "DEMO.cidadao.cpf"),
        "farmacia_cnpj": _extrair(txt, r"farmacia:\s*\{\s*cnpj:\s*'(\d{14})'", "DEMO.farmacia.cnpj"),
        "clinica_cnpj":  _extrair(txt, r"clinica:\s*\{\s*cnpj:\s*'(\d{14})'", "DEMO.clinica.cnpj"),
        # M-B — 2º/3º cidadão (chips de quick-pick), ordem literal do array.
        "cidadao2_cpf": _extrair(txt, r"cidadaos\s*=\s*\[[^\]]*?\{\s*cpf:\s*'(\d{11})'", "DEMO.cidadaos[1].cpf"),
        "cidadao3_cpf": _extrair(
            txt,
            r"cidadaos\s*=\s*\[[^\]]*?\{\s*cpf:\s*'\d{11}'[^\]]*?\{\s*cpf:\s*'(\d{11})'",
            "DEMO.cidadaos[2].cpf",
        ),
    }


def _identidades_seed() -> dict[str, str]:
    txt = _SEED_PY.read_text(encoding="utf-8")
    return {
        "cidadao_cpf":  _extrair(txt, r'PACIENTE\s*=\s*dict\(\s*cpf\s*=\s*"(\d{11})"', "PACIENTE.cpf"),
        "farmacia_cnpj": _extrair(txt, r'DISPENSADOR\s*=\s*dict\(\s*cnpj\s*=\s*"(\d{14})"', "DISPENSADOR.cnpj"),
        "clinica_cnpj":  _extrair(txt, r'CLINICA\s*=\s*dict\(\s*cnpj\s*=\s*"(\d{14})"', "CLINICA.cnpj"),
        "cidadao2_cpf": _extrair(txt, r'PACIENTE_2\s*=\s*dict\(\s*cpf\s*=\s*"(\d{11})"', "PACIENTE_2.cpf"),
        "cidadao3_cpf": _extrair(txt, r'PACIENTE_3\s*=\s*dict\(\s*cpf\s*=\s*"(\d{11})"', "PACIENTE_3.cpf"),
    }


def test_config_e_seed_declaram_as_mesmas_identidades():
    """config.js (`DEMO.*`) e seed_demo.py batem CPF/CNPJs — os dois lados, uma verdade."""
    config = _identidades_config()
    seed = _identidades_seed()
    assert config == seed, (
        "Frontend e seed divergem nas identidades da demo — a circulação não "
        f"fecharia num só cidadão.\n  config.js: {config}\n  seed_demo.py: {seed}"
    )


@pytest.mark.parametrize(
    "digitos,validador",
    [
        ("cidadao_cpf", "cpf"),
        ("farmacia_cnpj", "cnpj"),
        ("clinica_cnpj", "cnpj"),
        ("cidadao2_cpf", "cpf"),
        ("cidadao3_cpf", "cpf"),
    ],
)
def test_identidades_passam_na_validacao_de_digitos(digitos, validador):
    """Os canônicos são válidos no módulo 11 — não podem ser inválidos como o
    antigo '11111111111' (CPF) ou '98765432000100' (CNPJ com DV errado)."""
    valor = _identidades_config()[digitos]
    assert _digitos_validos(valor, validador), (
        f"{digitos}={valor} reprova na validação de {validador} (dígitos verificadores)"
    )


def _digitos_validos(numero: str, tipo: str) -> bool:
    if tipo == "cpf":
        if len(numero) != 11 or len(set(numero)) == 1:
            return False
        for i in (9, 10):
            soma = sum(int(numero[j]) * ((i + 1) - j) for j in range(i))
            dv = (soma * 10) % 11 % 10
            if dv != int(numero[i]):
                return False
        return True
    # cnpj
    if len(numero) != 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(numero[k]) * pesos[k] for k in range(pos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(numero[pos]):
            return False
    return True
