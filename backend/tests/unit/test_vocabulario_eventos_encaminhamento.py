"""
test_vocabulario_eventos_encaminhamento.py — ENG-016 PR 2 (guarda da comissão).

A REGRA QUE ESTE ARQUIVO TRAVA
------------------------------
**Todo evento gravado nos ledgers do encaminhamento e da contrarreferência está
declarado em `EVENTOS_ENCAMINHAMENTO`.**

Por que existe: a comissão do bloco §7 do CLAUDE.md descobriu que
`contrarreferencia_registrada` era EMITIDO nos dois ledgers — e no `motivo` da
custódia da CR — sem estar na lista declarada. Ninguém errou ao emitir; a lista
é que não acompanhou. Um relatório registra o achado uma vez; uma guarda impede
que ele volte. É a lição do R2 (§2a): invariante executável, não memória de
revisor.

O SENTIDO DAS DUAS DIREÇÕES
---------------------------
- **emitido ⊆ declarado** é a guarda dura: gravar no ledger um evento que o
  vocabulário não conhece deixa a lista mentindo sobre o que o objeto faz.
- **declarado ⊇ emitido** NÃO é erro: `encaminhamento_em_regulacao` está
  declarado e não é emitido por ninguém — é nome RESERVADO para quando a
  regulação real chegar (ruling do arquiteto, 23/08, na linhagem de
  `nao_realizado` e do `estornado` dormente). Reservar é decisão; emitir sem
  declarar é descuido. Só o segundo é travado aqui.

UM VOCABULÁRIO PARA OS DOIS LEDGERS
-----------------------------------
A contrarreferência é objeto DERIVADO do mesmo módulo e só emite
`contrarreferencia_registrada`. Não há `EVENTOS_CONTRARREFERENCIA` — e criar um
seria abrir superfície `core` para declarar um único nome que já cabe onde está.
"Todo evento dos dois ledgers está no vocabulário declarado" é a leitura da
comissão, e é a que esta guarda executa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domain.states_encaminhamento import EVENTOS_ENCAMINHAMENTO

_RAIZ = Path(__file__).resolve().parents[2]
_FONTES_CLINICAS = [
    _RAIZ / "app" / "routers" / "encaminhamentos.py",
    _RAIZ / "app" / "routers" / "contrarreferencias.py",
]
_MIGRACOES = sorted((_RAIZ / "alembic" / "versions").glob("*.py"))

# ---------------------------------------------------------------------------
# Eventos que NÃO nascem do caminho clínico — congelados por valor.
#
# `custodia_reconciliada_data_fix` é emitido POR MIGRAÇÃO (a1c9e4d70b26), nunca
# por endpoint. O CLAUDE.md já o trata assim nos outros objetos: fato de
# reconciliação, não gesto clínico. Fica FORA do vocabulário do objeto e DENTRO
# desta lista — que é congelada de propósito: se uma migração nova passar a
# gravar outro evento, a guarda acusa e alguém decide, em vez de o nome entrar
# calado.
# ---------------------------------------------------------------------------
_EVENTOS_DE_MIGRACAO: frozenset[str] = frozenset({
    "custodia_reconciliada_data_fix",
})

# `_evento(conn, enc["id"], "x"` · `_evento_enc(...)` · `_evento_cr(conn, cr_id, "x"`
_RE_HELPER = re.compile(r"""_evento(?:_enc|_cr)?\(\s*conn\s*,\s*[^,]+,\s*["']([a-z_]+)["']""")
# INSERT cru em qualquer *_eventos: o literal do tipo_evento no VALUES
_RE_SQL = re.compile(
    r"INSERT INTO\s+\{?(?:tabela_eventos|encaminhamento_eventos|contrarreferencia_eventos)\}?"
    r".*?VALUES.*?['\"]([a-z_]+)['\"]",
    re.S,
)


def _eventos_emitidos(fontes) -> set[str]:
    achados: set[str] = set()
    for f in fontes:
        texto = f.read_text(encoding="utf-8")
        achados |= set(_RE_HELPER.findall(texto))
        achados |= set(_RE_SQL.findall(texto))
    return achados


def _eventos_de_migracao_nos_ledgers() -> set[str]:
    """Só as migrações que escrevem nos DOIS ledgers deste módulo."""
    alvo = [
        m for m in _MIGRACOES
        if "encaminhamento_eventos" in m.read_text(encoding="utf-8")
        or "contrarreferencia_eventos" in m.read_text(encoding="utf-8")
    ]
    return _eventos_emitidos(alvo)


# ---------------------------------------------------------------------------
# 1 — a guarda
# ---------------------------------------------------------------------------

def test_o_caminho_clinico_so_emite_evento_declarado():
    emitidos = _eventos_emitidos(_FONTES_CLINICAS)
    assert emitidos, "o extrator não achou evento nenhum — o scanner quebrou"
    fora = sorted(emitidos - set(EVENTOS_ENCAMINHAMENTO))
    assert not fora, (
        f"eventos emitidos e NÃO declarados em EVENTOS_ENCAMINHAMENTO: {fora}. "
        "Emitir sem declarar deixa o vocabulário mentindo sobre o que o objeto faz."
    )


def test_a_migracao_so_emite_evento_declarado_ou_da_lista_de_migracao():
    emitidos = _eventos_de_migracao_nos_ledgers()
    fora = sorted(emitidos - set(EVENTOS_ENCAMINHAMENTO) - _EVENTOS_DE_MIGRACAO)
    assert not fora, (
        f"migração passou a gravar evento novo nos ledgers do módulo: {fora}. "
        "Se for fato de reconciliação, entra em `_EVENTOS_DE_MIGRACAO` com a "
        "razão escrita; se for gesto clínico, entra no vocabulário (toque `core`)."
    )


def test_o_achado_da_comissao_esta_fechado():
    """O caso concreto que gerou esta guarda, nomeado.

    Guarda genérica que passa por acaso não prova que o defeito específico
    morreu — este teste falha se `contrarreferencia_registrada` sair da lista.
    """
    assert "contrarreferencia_registrada" in EVENTOS_ENCAMINHAMENTO, (
        "o evento voltou a ser emitido sem estar declarado — achado da comissão reaberto"
    )


def test_em_regulacao_segue_reservado_e_isso_nao_e_erro():
    """Ruling do arquiteto: declarado sem emissor é RESERVA, não descuido.

    Se um dia alguém emitir `encaminhamento_em_regulacao`, este teste continua
    passando (a guarda dura é a de cima) — o que ele fixa é que o nome não seja
    APAGADO por parecer sobra.
    """
    assert "encaminhamento_em_regulacao" in EVENTOS_ENCAMINHAMENTO
    assert "encaminhamento_em_regulacao" not in _eventos_emitidos(_FONTES_CLINICAS), (
        "a regulação ganhou emissor — se há engine de verdade, o badge honesto "
        "do §2.5 do desenho precisa ser revisto junto"
    )


# ---------------------------------------------------------------------------
# A guarda morde?
# ---------------------------------------------------------------------------

class TestAsGuardasMordem:
    """Guarda que nunca falha quando deveria é decoração (lição do R2, §2a)."""

    def test_helper_com_evento_novo_seria_pego(self, tmp_path):
        f = tmp_path / "falso.py"
        f.write_text('_evento(conn, enc["id"], "encaminhamento_teletransportado", {})',
                     encoding="utf-8")
        assert "encaminhamento_teletransportado" in _eventos_emitidos([f])

    def test_evento_cr_tambem_e_pego(self, tmp_path):
        """O ledger da CR é o que a comissão descobriu esquecido — o scanner
        precisa enxergar a forma de chamada DELE, não só a do encaminhamento."""
        f = tmp_path / "falso.py"
        f.write_text('_evento_cr(conn, cr_id, "contrarreferencia_rasgada", {})',
                     encoding="utf-8")
        assert "contrarreferencia_rasgada" in _eventos_emitidos([f])

    def test_insert_cru_tambem_e_pego(self, tmp_path):
        """Migração escreve por SQL cru, não pelo helper."""
        f = tmp_path / "falso.py"
        f.write_text(
            "INSERT INTO encaminhamento_eventos (a, tipo_evento) VALUES (1, 'evento_clandestino')",
            encoding="utf-8")
        assert "evento_clandestino" in _eventos_emitidos([f])
