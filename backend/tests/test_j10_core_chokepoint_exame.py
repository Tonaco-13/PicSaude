"""
tests/test_j10_core_chokepoint_exame.py
=======================================

Guarda executável do choke-point de posse do EXAME (J.10-CORE, DESPACHO-ENG-012
§7). Roda no gate SEM PostgreSQL — é invariante de CÓDIGO. A guarda de BANCO (a
constraint de unicidade) roda nos dois dialetos em
`tests/integration/test_j10_core_posse_exame.py` e
`tests/test_j10_core_migracao_sqlite.py`.

Lição do R2 (§2a) e do COER-2: invariante executável, não memória de revisor. Se
um novo caminho de posse voltar a dar `INSERT INTO pedido_exame_custodia` à mão,
o gate acusa — em vez de ser caçado depois, quando já houver dupla posse no
banco de alguém.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domain.states_exame import EVENTOS_PEDIDO_EXAME
from app.routers.pedidos_exame import (
    MOTIVOS_CUSTODIA_EXAME,
    transferir_posse_exame,
)

_APP = Path(__file__).resolve().parent.parent / "app"
_ROUTERS = _APP / "routers"

# O choke-point é o ÚNICO lugar autorizado a inserir posse de exame.
_ARQ_CHOKEPOINT = "pedidos_exame.py"


def _linhas_de_codigo(texto: str):
    """Ignora comentário e menção em docstring (que citam o SQL, não o executam)."""
    for i, linha in enumerate(texto.splitlines(), 1):
        strip = linha.strip()
        if strip.startswith("#"):
            continue
        if strip.startswith("--"):     # comentário SQL dentro da string
            continue
        if "`" in linha:               # menção em docstring usa backticks
            continue
        yield i, linha


def _codigo(texto: str) -> str:
    """O texto sem as linhas de comentário.

    As guardas por BLOCO precisam disto: o comentário que EXPLICA a regra cita
    o padrão proibido (`MAX(id)`), e uma guarda que acusa a própria explicação
    é ruído. Ruído no gate treina o time a ignorá-lo — que é como um gate morre.
    """
    return "\n".join(linha for _, linha in _linhas_de_codigo(texto))


# ---------------------------------------------------------------------------
# 1 — nenhum INSERT cru de custódia fora do choke-point
# ---------------------------------------------------------------------------

def test_insert_de_custodia_so_existe_no_chokepoint():
    ofensores = []
    for arq in sorted(_ROUTERS.glob("*.py")):
        texto = arq.read_text(encoding="utf-8")
        for i, linha in _linhas_de_codigo(texto):
            if "INSERT INTO pedido_exame_custodia" in linha:
                if arq.name != _ARQ_CHOKEPOINT:
                    ofensores.append(f"{arq.name}:{i}")
    assert not ofensores, (
        "INSERT de custódia de exame fora de transferir_posse_exame:\n"
        + "\n".join(ofensores)
    )


def test_o_chokepoint_tem_exatamente_um_insert():
    """Um só INSERT no arquivo inteiro — o de dentro do helper.

    Se aparecer um segundo, ou alguém duplicou o helper ou abriu um atalho
    dentro do próprio arquivo, que é o lugar mais fácil de fazê-lo.
    """
    texto = (_ROUTERS / _ARQ_CHOKEPOINT).read_text(encoding="utf-8")
    n = sum(
        1 for _, linha in _linhas_de_codigo(texto)
        if "INSERT INTO pedido_exame_custodia" in linha
    )
    assert n == 1, f"esperado 1 INSERT (o do choke-point), achei {n}"


# ---------------------------------------------------------------------------
# 2 — ninguém lê posse por "última linha"
# ---------------------------------------------------------------------------

# A leitura derivada que o formato de ledger obrigava. Depois da migração, posse
# é `encerrada_em IS NULL`; quem voltar a derivar por MAX(id) lê o passado.
_MAX_ID = re.compile(r"MAX\(\s*\w*\.?id\s*\)", re.IGNORECASE)


def test_ninguem_deriva_posse_de_exame_por_max_id():
    ofensores = []
    for arq in sorted(_ROUTERS.glob("*.py")):
        texto = _codigo(arq.read_text(encoding="utf-8"))
        if "pedido_exame_custodia" not in texto:
            continue
        # Recorta cada bloco SQL que fala da tabela e procura o padrão nele.
        for bloco in re.split(r"\n\s*\n", texto):
            if "pedido_exame_custodia" in bloco and _MAX_ID.search(bloco):
                ofensores.append(arq.name)
                break
    assert not ofensores, (
        "posse de exame derivada por MAX(id) — use `encerrada_em IS NULL`: "
        + ", ".join(sorted(set(ofensores)))
    )


def test_leituras_de_posse_filtram_por_encerrada_em():
    """Todo SELECT de posse na tabela carrega o filtro de posse ativa.

    Sem ele a query devolve histórico como se fosse presente — o defeito que a
    migração existe para tornar impossível de escrever por acidente.
    """
    ofensores = []
    for arq in sorted(_ROUTERS.glob("*.py")):
        texto = _codigo(arq.read_text(encoding="utf-8"))
        for bloco in re.split(r"\n\s*\n", texto):
            if "FROM pedido_exame_custodia" not in bloco:
                continue
            # A leitura de HISTÓRICO (todas as linhas) é legítima e se
            # identifica por pedir `transferido_em` na projeção sem filtrar.
            if "encerrada_em" in bloco:
                continue
            if "de, para, transferido_em" in bloco:   # trilha completa
                continue
            ofensores.append(f"{arq.name}: {bloco.strip()[:90]}")
    assert not ofensores, (
        "SELECT de posse sem `encerrada_em IS NULL`:\n" + "\n".join(ofensores)
    )


# ---------------------------------------------------------------------------
# 3 — motivo canônico
# ---------------------------------------------------------------------------

def test_motivo_nao_canonico_e_recusado():
    """O rótulo do caminho é fechado, como no `custodia.py` da receita.

    Motivo livre viraria vocabulário paralelo: o histórico deixaria de separar
    os caminhos e a auditoria perderia o "por quê" de cada mudança de mão.
    """
    with pytest.raises(ValueError, match="não é canônico"):
        transferir_posse_exame(
            conn=None, pedido_id=1, item_id=None,
            de="paciente", de_id=None,
            para="prestador_exame", para_id="1" * 14,
            detentor="1" * 14,
            motivo="motivo_inventado", agora="2026-08-16T00:00:00",
            instance_id="i",
        )


def test_motivos_canonicos_congelados():
    """Congelado POR VALOR — acrescentar motivo é decisão, não efeito colateral.

    Mesma disciplina do §9 (a migração declara sobre o que agiu): comparar
    contra a lista viva faria o teste concordar com qualquer mudança.

    J.10 (`module`) acrescentou os dois últimos — decisão do desenho §3.2
    (motivo canônico por caminho), não efeito colateral. O congelamento segue
    valendo: o próximo motivo que aparecer sem atualizar esta linha fica
    VERMELHO aqui.
    """
    assert MOTIVOS_CUSTODIA_EXAME == frozenset({
        "entrega_carteira_digital",
        "agendamento_prestador",
        "transferencia_laboratorio",
        "transferencia_parcial",       # J.10 — cidadão entrega só alguns itens
        "devolucao_nao_realizavel",    # J.10 — laboratório devolve o que não realiza
    })


# ---------------------------------------------------------------------------
# 4 — vocabulário do ledger
# ---------------------------------------------------------------------------

def test_evento_do_data_fix_esta_no_vocabulario():
    """A migração emite `custodia_reconciliada_data_fix` — o contrato tem de
    conhecê-lo, senão o ledger ganha um evento que a máquina de estados nega.
    """
    assert "custodia_reconciliada_data_fix" in EVENTOS_PEDIDO_EXAME


def test_custodia_transferida_segue_no_vocabulario():
    assert "custodia_transferida" in EVENTOS_PEDIDO_EXAME
