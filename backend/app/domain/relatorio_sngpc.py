"""
relatorio_sngpc.py
==================
Lógica PURA da escrituração SNGPC do dispensador (TICKET-F5-RELATORIO-SNGPC, Fatia A).

Escrituração POR MOVIMENTO, não por estado (CLAUDE.md §2 — ledger imutável):
  - cada dispensação = 1 movimento  (tipo_movimento='dispensacao', +quantidade)
  - cada estorno     = 1 movimento  (tipo_movimento='estorno',     −quantidade)

O estorno é objeto derivado e imutável (T2, TICKET-ESTORNO-OBJETO-DERIVADO): não
muta a dispensação de origem. O saldo efetivo do item = Σ dispensado − Σ estornado.

CORTE TEMPORAL DO SALDO (nota 2 do Z AI, §3 do ticket):
  `saldo_escriturado_item` de cada linha é o saldo NA DATA DO MOVIMENTO (running
  balance): Σ dos movimentos do mesmo item cuja chave-de-ordem é ≤ a da linha.
  Consequência normativa: o relatório de um período fechado é estável para sempre
  — um estorno registrado depois do `data_fim` não altera nenhuma linha já emitida
  (critério §5.9). Mesma filosofia do ledger imutável: a linha nunca "muda de
  valor" quando o futuro acontece.

ESCOPO: as linhas recebidas já vêm filtradas pelo CNPJ do JWT (WHERE no router).
O saldo é o running balance DENTRO da escrituração deste estabelecimento — que é
exatamente o que o SNGPC registra (livro por estabelecimento). Não há leitura de
movimento de outro CNPJ (critério §5.1).

Módulo PURO — sem FastAPI, sem I/O — testável isoladamente.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

# CPF sentinela — nunca é cidadão real (CLAUDE.md §6a). Excluído na query do router;
# reexposto aqui apenas como documentação da constante.
_CPF_NAO_IDENTIFICADO = "00000000000"

# Ordem das colunas do CSV — uma linha por movimento (§3 do ticket).
# `protocolo_raiz` (R3, CLAUDE.md §2a): logo após `protocolo_prescricao` — a
# linhagem-mãe resolvida ao lado do protocolo do movimento. Projeção, nunca
# persistida (§10): ver resolver_protocolo_raiz.
CABECALHO_CSV = [
    "tipo_movimento",
    "data_movimento",
    "dispensacao_id",
    "estorno_protocolo",
    "protocolo_prescricao",
    "protocolo_raiz",
    "medicamento",
    "dose",
    "unidade_quantidade",
    "quantidade",
    "saldo_escriturado_item",
    "lote",
    "fabricante",
    "paciente_nome",
    "paciente_cpf",
    "comprador_nome",
    "comprador_documento",
    "comprador_eh_paciente",
    "prescritor_nome",
    "prescritor_cns",
    "motivo_estorno",
    "status_item",
]


def normalizar_dt(v: Any) -> Optional[datetime]:
    """Paridade SQLite×PostgreSQL: o PostgreSQL devolve `datetime` de colunas
    DateTime, o SQLite devolve string ISO (gravada via `datetime.utcnow().isoformat()`
    — ver dispensacoes.py:214). Normaliza para `datetime` naïve (tz removida) para
    ordenar, comparar e exibir de forma idêntica nos dois bancos."""
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        s = str(v)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            # Último recurso: descarta frações/sufixos não-ISO ("YYYY-MM-DDTHH:MM:SS").
            dt = datetime.fromisoformat(s[:19])
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _comprador(nome, documento, paciente_nome, paciente_cpf):
    """Semântica do comprovante (dispensacoes.py:96 · §2.5 do ticket): sem
    comprador declarado na dispensação → o comprador É o próprio paciente, com
    flag explícita `comprador_eh_paciente`."""
    if nome:
        return nome, documento, False
    return paciente_nome, paciente_cpf, True


def _movimento_de_dispensacao(r: dict) -> dict:
    dt = normalizar_dt(r["data_movimento"])
    c_nome, c_doc, c_eh_pac = _comprador(
        r.get("comprador_nome"), r.get("comprador_documento"),
        r["paciente_nome"], r["paciente_cpf"],
    )
    q = r["quantidade"] or 0
    return {
        "tipo_movimento": "dispensacao",
        "data_movimento": dt.isoformat() if dt else "",
        "dispensacao_id": r["dispensacao_id"],
        "estorno_protocolo": None,
        "protocolo_prescricao": r["protocolo_prescricao"],
        "medicamento": r["medicamento"],
        "dose": r.get("dose"),
        "unidade_quantidade": r.get("unidade_quantidade"),
        "quantidade": q,
        "lote": r.get("lote"),
        "fabricante": r.get("fabricante"),
        "paciente_nome": r["paciente_nome"],
        "paciente_cpf": r["paciente_cpf"],
        "comprador_nome": c_nome,
        "comprador_documento": c_doc,
        "comprador_eh_paciente": c_eh_pac,
        "prescritor_nome": r["prescritor_nome"],
        "prescritor_cns": r.get("prescritor_cns"),
        "motivo_estorno": None,
        "status_item": r.get("status_item"),
        # ----- campos internos de ordenação/saldo (prefixo _, não vão ao CSV) ----
        "_dt": dt,
        "_item_id": r["item_id"],
        "_prescricao_id": r.get("prescricao_id"),   # ponto de partida da walk R3
        "_tipo_rank": 0,             # dispensação precede seu estorno na cronologia
        "_seq": r["dispensacao_id"],
        "_signed": q,               # dispensação soma ao saldo
    }


def _movimento_de_estorno(r: dict) -> dict:
    dt = normalizar_dt(r["data_movimento"])
    # Comprador/paciente/lote/fabricante vêm da dispensação de origem (JOIN no router).
    c_nome, c_doc, c_eh_pac = _comprador(
        r.get("comprador_nome"), r.get("comprador_documento"),
        r["paciente_nome"], r["paciente_cpf"],
    )
    q = r["quantidade"] or 0
    return {
        "tipo_movimento": "estorno",
        "data_movimento": dt.isoformat() if dt else "",
        "dispensacao_id": r["dispensacao_id"],   # = origem_dispensacao_id (§3)
        "estorno_protocolo": r["estorno_protocolo"],
        "protocolo_prescricao": r["protocolo_prescricao"],
        "medicamento": r["medicamento"],
        "dose": r.get("dose"),
        "unidade_quantidade": r.get("unidade_quantidade"),
        "quantidade": q,
        "lote": r.get("lote"),
        "fabricante": r.get("fabricante"),
        "paciente_nome": r["paciente_nome"],
        "paciente_cpf": r["paciente_cpf"],
        "comprador_nome": c_nome,
        "comprador_documento": c_doc,
        "comprador_eh_paciente": c_eh_pac,
        "prescritor_nome": r["prescritor_nome"],
        "prescritor_cns": r.get("prescritor_cns"),
        "motivo_estorno": r["motivo_estorno"],
        "status_item": r.get("status_item"),
        "_dt": dt,
        "_item_id": r["item_id"],
        "_prescricao_id": r.get("prescricao_id"),   # ponto de partida da walk R3
        "_tipo_rank": 1,
        "_seq": r["estorno_id"],
        "_signed": -q,              # estorno subtrai do saldo (reversão)
    }


def _chave_ordem(m: dict) -> tuple:
    """Ordem total determinística: (data, dispensacao_id, tipo, seq). Ascendente =
    cronológica — a dispensação (rank 0) precede seu estorno (rank 1) em empate de
    tempo. `datetime.min` como piso defensivo para data ausente."""
    return (m["_dt"] or datetime.min, m["dispensacao_id"], m["_tipo_rank"], m["_seq"])


def resolver_protocolo_raiz(prescricao_id: Any, linhagem: dict, cache: dict) -> Any:
    """R3 (CLAUDE.md §2a) — resolve a LINHAGEM-MÃE: sobe a cadeia
    `origem_prescricao_id` até a raiz (origem NULL) e devolve o protocolo da
    prescrição-mãe. WALK EM PYTHON, nunca CTE recursiva — motor puro, paridade
    SQLite×PG, testável sem banco.

    ASSERÇÃO (pré-check do arquiteto, main@2f510ed): `origem_prescricao_id` é
    imutável pós-criação — zero UPDATE/SET na coluna, só INSERT de derivação. A
    linhagem é, por construção, um DAG acíclico; a detecção de ciclo abaixo é
    guarda defensiva contra corrupção de dados, não caminho esperado.

    `linhagem`: mapa {prescricao_id: {"origem": origem_prescricao_id|None,
    "protocolo": protocolo}} cobrindo o nó e todos os seus ancestrais.

    `cache`: memoização POR-EXECUÇÃO — dict novo a cada relatório, passado como
    parâmetro. NUNCA global/@lru_cache: ficaria stale quando nasce prescrição
    derivada nova entre dois relatórios.

    Ciclo → falha ALTO, determinística, nomeando a cadeia que fechou (não laço
    infinito, não mensagem genérica).
    """
    if prescricao_id in cache:
        return cache[prescricao_id]

    caminho: list = []
    vistos: set = set()
    atual = prescricao_id
    while True:
        if atual in cache:
            raiz = cache[atual]
            break
        if atual in vistos:
            inicio = caminho.index(atual)
            ciclo = caminho[inicio:] + [atual]
            nomes = [linhagem.get(i, {}).get("protocolo") or f"id={i}" for i in ciclo]
            raise ValueError(
                "Ciclo detectado na linhagem: " + " → ".join(str(n) for n in nomes)
            )
        vistos.add(atual)
        caminho.append(atual)
        entrada = linhagem.get(atual)
        if entrada is None:
            # Mapa incompleto: nó/ancestral não carregado. Não ocorre com o fecho
            # transitivo do router; guarda defensiva contra chamada mal-formada.
            raise ValueError(
                f"Linhagem incompleta: prescricao_id={atual} ausente do mapa."
            )
        origem = entrada["origem"]
        if origem is None:
            raiz = entrada["protocolo"]   # nó sem mãe = a própria raiz
            break
        atual = origem

    for pid in caminho:               # memoiza todos os nós do caminho de uma vez
        cache[pid] = raiz
    return raiz


def _raiz_do_movimento(m: dict, linhagem: Optional[dict], cache: dict) -> Any:
    """Resolve `protocolo_raiz` do movimento. Sem mapa de linhagem (motor puro
    exercitado sem DB) → a própria prescrição é a raiz (R3: prescrição sem
    origem resolve ao próprio protocolo)."""
    pid = m.get("_prescricao_id")
    if linhagem is None or pid is None:
        return m["protocolo_prescricao"]
    return resolver_protocolo_raiz(pid, linhagem, cache)


def construir_movimentos(disp_rows, est_rows, linhagem: Optional[dict] = None) -> list[dict]:
    """Unifica dispensações e estornos e calcula `saldo_escriturado_item` com CORTE
    TEMPORAL (running balance) por item, considerando TODOS os movimentos do
    estabelecimento — nunca só os do período de exibição, senão o saldo estaria
    errado no recorte. Retorna a lista em ordem ASCENDENTE (cronológica).

    `linhagem` (opcional): mapa de linhagem para resolver `protocolo_raiz` (R3).
    O cache de raízes é instanciado AQUI — memoização por-execução (§2a R3),
    fresca a cada chamada do relatório."""
    movs = [_movimento_de_dispensacao(dict(r)) for r in disp_rows]
    movs += [_movimento_de_estorno(dict(r)) for r in est_rows]
    movs.sort(key=_chave_ordem)

    saldo_por_item: dict[Any, int] = {}
    cache_raiz: dict = {}             # memoização POR-EXECUÇÃO (§2a R3)
    for m in movs:
        item = m["_item_id"]
        saldo_por_item[item] = saldo_por_item.get(item, 0) + m["_signed"]
        m["saldo_escriturado_item"] = saldo_por_item[item]
        m["protocolo_raiz"] = _raiz_do_movimento(m, linhagem, cache_raiz)
    return movs


def filtrar_periodo(
    movs, dt_inicio: Optional[datetime], dt_fim: Optional[datetime]
) -> list[dict]:
    """Filtra os movimentos EXIBIDOS pela janela [dt_inicio, dt_fim]. O saldo já
    foi calculado sobre o histórico completo em `construir_movimentos`, então
    filtrar aqui não altera nenhum saldo (critério §5.9)."""
    out = []
    for m in movs:
        dt = m["_dt"]
        if dt is None:
            continue
        if dt_inicio is not None and dt < dt_inicio:
            continue
        if dt_fim is not None and dt > dt_fim:
            continue
        out.append(m)
    return out


def ordenar_exibicao(movs) -> list[dict]:
    """ORDER BY data_movimento DESC, dispensacao_id DESC (desempate determinístico
    por tipo/seq) — régua Jules de determinismo (custodia.py:827)."""
    return sorted(movs, key=_chave_ordem, reverse=True)


def linha_csv(m: dict) -> list:
    """Projeta um movimento para a linha do CSV, na ordem de `CABECALHO_CSV`."""
    return [
        m["tipo_movimento"],
        m["data_movimento"],
        m["dispensacao_id"],
        m["estorno_protocolo"] or "",
        m["protocolo_prescricao"],
        m.get("protocolo_raiz") or m["protocolo_prescricao"],
        m["medicamento"] or "",
        m["dose"] or "",
        m["unidade_quantidade"] or "",
        m["quantidade"],
        m["saldo_escriturado_item"],
        m["lote"] or "",
        m["fabricante"] or "",
        m["paciente_nome"] or "",
        m["paciente_cpf"] or "",
        m["comprador_nome"] or "",
        m["comprador_documento"] or "",
        "sim" if m["comprador_eh_paciente"] else "nao",
        m["prescritor_nome"] or "",
        m["prescritor_cns"] or "",
        m["motivo_estorno"] or "",
        m["status_item"] or "",
    ]
