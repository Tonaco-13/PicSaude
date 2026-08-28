"""
test_gp3_identidades_sinteticas.py — GP-3: o seed é 100% sintético, PROVADO.

POR QUE UM TESTE, E NÃO UMA AFIRMAÇÃO NO RELATÓRIO
---------------------------------------------------
O despacho foi explícito: *"confirmar o seed 100% sintético, com prova
executável, não afirmação"*. Antes de o repositório virar público, "é tudo
fictício" precisa ser algo que o gate reexecuta, não uma frase que alguém
escreveu num dia e ninguém mais conferiu.

O QUE SE PODE PROVAR — E O QUE NÃO
-----------------------------------
**Não é possível provar que um CPF não pertence a ninguém.** Um CPF
matematicamente válido pode existir no mundo real, e nenhum teste local resolve
isso. O que ESTE arquivo prova é o que de fato importa para a decisão de tornar
o repo público:

  (a) o conjunto de identidades usado é **PEQUENO, FECHADO E DECLARADO** — as
      quatro personas de `config.js DEMO.*` mais o sentinela;
  (b) **nenhuma identidade nova entra sem passar por aqui** — a lista é
      congelada por valor;
  (c) o **sentinela** `00000000000` é matematicamente INVÁLIDO, então nunca
      colide com cidadão real (CLAUDE.md §6a);
  (d) as personas vêm de **fonte única** e o seed não inventa identidade
      própria.

Isso transforma "confie em nós" em "confira a lista": quem auditar o repo lê
seis números, não quatro mil blobs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_CONFIG = _RAIZ / "config.js"
_SEED = _RAIZ / "backend" / "seed_demo.py"

# ── O CONJUNTO FECHADO, congelado por valor ──────────────────────────────
# Toda identidade que a demo usa. Acrescentar uma exige editar esta tupla —
# que é exatamente o ponto de controle que o GP-3 pede.
_CPFS_DEMO = ("12345678909",)
# CPF de login em modo DEV (`config.js::DEV_LOGIN_CPF`). Dígitos repetidos →
# matematicamente INVÁLIDO, como o sentinela: nunca colide com cidadão real.
# Foi ACHADO por esta própria guarda na primeira execução, e declarado aqui —
# que é o ponto de controle funcionando, não uma exceção aberta para ele.
_CPF_DEV = "11111111111"
_CNPJS_DEMO = ("99999999000191", "99999999000272", "11222333000181")
_CNS_DEMO = ("980001112223334", "980001112223335")
_CPF_SENTINELA = "00000000000"


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def _cpf_valido(cpf: str) -> bool:
    """Dígitos verificadores do CPF. Repetidos (000…, 111…) são inválidos."""
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(cpf[i]) * ((n + 1) - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(cpf[n]):
            return False
    return True


# ---------------------------------------------------------------------------
# (c) o sentinela nunca é um cidadão
# ---------------------------------------------------------------------------

def test_o_cpf_de_login_DEV_tambem_e_invalido():
    """`11111111111` só é seguro porque é INVÁLIDO.

    Dígitos repetidos nunca passam na validação, então o CPF de conveniência do
    modo DEV não pode coincidir com pessoa nenhuma. Se um dia alguém o trocar
    por um CPF "bonito" e válido, este teste cai — e tem de cair, porque aí
    passaria a ser uma identidade que pode existir no mundo.
    """
    assert not _cpf_valido(_CPF_DEV)


def test_o_cpf_sentinela_e_matematicamente_invalido():
    """CLAUDE.md §6a: `00000000000` é reservado para emissão física sem
    identificação. Se um dia virar um CPF válido, ele passaria a poder colidir
    com uma pessoa real — e a convenção inteira ruiria em silêncio."""
    assert not _cpf_valido(_CPF_SENTINELA)


# ---------------------------------------------------------------------------
# (a) + (b) o conjunto é fechado e declarado
# ---------------------------------------------------------------------------

def _identidades_no_arquivo(caminho: Path) -> dict[str, set[str]]:
    texto = caminho.read_text(encoding="utf-8")
    return {
        "cpf":  {m for m in re.findall(r"(?<!\d)\d{11}(?!\d)", texto)},
        "cnpj": {m for m in re.findall(r"(?<!\d)\d{14}(?!\d)", texto)},
        "cns":  {m for m in re.findall(r"(?<!\d)\d{15}(?!\d)", texto)},
    }


@pytest.mark.parametrize("arquivo", [_CONFIG, _SEED], ids=["config.js", "seed_demo.py"])
def test_nenhuma_identidade_fora_do_conjunto_declarado(arquivo):
    """A guarda que faz o conjunto ser FECHADO.

    Qualquer CPF/CNPJ/CNS novo em `config.js` ou no seed cai aqui até ser
    declarado na tupla acima. É o ponto de controle: identidade nova passa a
    exigir uma decisão consciente, e não entra de carona num commit.
    """
    achado = _identidades_no_arquivo(arquivo)
    permitidos = {
        "cpf":  set(_CPFS_DEMO) | {_CPF_SENTINELA, _CPF_DEV},
        "cnpj": set(_CNPJS_DEMO),
        "cns":  set(_CNS_DEMO),
    }
    for tipo, valores in achado.items():
        intrusos = sorted(valores - permitidos[tipo])
        assert not intrusos, (
            f"{arquivo.name}: {tipo} fora do conjunto declarado: {intrusos}. "
            "Identidade nova na demo é decisão — declare em "
            "`test_gp3_identidades_sinteticas.py` antes de usá-la."
        )


def test_as_personas_sao_as_declaradas():
    """(d) fonte única: as identidades vivem em `config.js DEMO.*`, e o seed as
    espelha. Se as duas divergirem, uma delas está inventando gente."""
    cfg = _CONFIG.read_text(encoding="utf-8")
    for cpf in _CPFS_DEMO:
        assert cpf in cfg, f"CPF {cpf} declarado aqui e ausente do config.js"
    for cnpj in _CNPJS_DEMO[:1] + _CNPJS_DEMO[2:]:   # a 2ª farmácia só existe no seed
        assert cnpj in cfg, f"CNPJ {cnpj} declarado aqui e ausente do config.js"
    for cns in _CNS_DEMO:
        assert cns in cfg, f"CNS {cns} declarado aqui e ausente do config.js"


def test_o_conjunto_e_pequeno_o_bastante_para_ser_auditado_a_olho():
    """O valor prático desta guarda: quem auditar o repo lê MEIA DÚZIA de
    números, não quatro mil blobs. Se o conjunto crescer muito, a auditoria
    deixa de ser possível a olho — e isso é uma decisão, não um acidente."""
    total = len(_CPFS_DEMO) + len(_CNPJS_DEMO) + len(_CNS_DEMO)
    assert total <= 10, (
        f"o conjunto de identidades da demo cresceu para {total}. Ainda é "
        "auditável a olho? Se sim, ajuste o limite conscientemente."
    )


# ---------------------------------------------------------------------------
# O que este arquivo NÃO prova — dito em voz alta
# ---------------------------------------------------------------------------

def test_documenta_o_limite_da_prova():
    """Um CPF sintético pode, por azar, coincidir com um real — nenhum teste
    local resolve isso, e fingir que resolve seria pior que não testar.

    O que a casa garante é o CONJUNTO FECHADO e DECLARADO acima. Este teste
    existe para que a limitação esteja escrita onde alguém a lerá, e não só num
    relatório que envelhece.
    """
    assert _cpf_valido(_CPFS_DEMO[0]), (
        "o CPF da demo é matematicamente válido — e é assim de propósito: um "
        "CPF inválido não passaria pelas próprias validações do sistema, e a "
        "demo não exercitaria o caminho real"
    )
