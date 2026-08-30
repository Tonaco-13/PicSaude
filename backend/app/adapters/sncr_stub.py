"""
sncr_stub.py
============
Ticket 16A — Implementação stub do SNCRAdapter.

PROPÓSITO
---------
Mock local do SNCR para desenvolvimento e testes. Permite exercitar o
fluxo completo (router → adapter → banco → ledger) sem depender da API
real da Anvisa, que ainda não está documentada (abril/2026).

GUARDRAILS
----------
1. Toda numeração gerada começa com "STUB-" — distinguível de numeração
   real do SNCR (que terá outro formato quando a API for documentada).
2. O endpoint consumidor MARCA o receituário com status="numerado_stub"
   (não "numerado") quando este adapter é usado — impede que numeração
   stub seja confundida com real ao percorrer o sistema.
3. Logs sempre prefixados com "[SNCR-STUB]" para grep em produção.

EM PRODUÇÃO
-----------
Este stub NÃO deve ser usado em produção. A factory (`sncr_factory.py`)
seleciona implementações via env var `SNCR_ADAPTER`. Em produção:
    SNCR_ADAPTER=real
forçará o uso de SNCRReal (Ticket 16B), e a factory NÃO faz fallback
silencioso para o stub.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Mapping

import uuid

from app.adapters.sncr_interface import (
    LoteSNCR,
    NumeracaoSNCR,
    RegistroUtilizacao,
    ResultadoSNCR,
    SNCRAdapter,
    SNCR_ERRO_INVALIDO,
)

from app.database import row_lock_suffix

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapa tipo_receituario → abreviação de 3 letras usada no formato STUB-...
# Vocabulário fixo conforme `domain/motor_regulatorio.py::GRUPOS_REGULATORIOS`.
# ---------------------------------------------------------------------------

_ABREV_TIPO: Mapping[str, str] = {
    "notificacao_receita_a":         "NRA",
    "notificacao_receita_b":         "NRB",
    "receita_controle_especial":     "RCE",
    "notificacao_receita_especial":  "NRE",
    "receita_retencao":              "RRT",
    # receita_simples / receita_comum não passam pelo SNCR (requer_sncr=False),
    # mas mantemos abreviação caso o stub seja chamado em teste explícito.
    "receita_simples":               "RSI",
    "receita_comum":                 "RCM",
}

_PREFIXO_STUB = "STUB"


# ---------------------------------------------------------------------------
# Implementação
# ---------------------------------------------------------------------------

class SNCRStub(SNCRAdapter):
    """Implementação stub do SNCRAdapter.

    Gera numerações locais no formato:
        STUB-{ANO}-{TIPO_ABREV}-{SEQUENCIAL:09d}

    Exemplos:
        STUB-2026-NRA-000000001  (Notificação A)
        STUB-2026-NRB-000000017  (Notificação B)
        STUB-2026-RCE-000000003  (Receita Controle Especial)

    Contadores de numeração SEM lote são por (ano × tipo) e mantidos em
    memória (thread-safe) — comportamento original, intocado (DESENHO
    §2: "sem lote, mantém comportamento atual"). Cada instância do stub
    mantém seu próprio contador — instâncias diferentes geram sequências
    independentes. Para um teste que precise de sequências previsíveis
    entre processos, usar um banco real ou instância única.

    LOTES (DESENHO-TALAO-DIGITAL-SNCR.md §2, G2) são a exceção: precisam
    sobreviver entre instâncias (o router cria um `SNCRStub` novo a cada
    request), então vivem em `sncr_lotes` (tabela própria do adapter,
    sem FK clínica) — exige `conn` no construtor. Sem `conn`, o stub
    funciona exatamente como antes (numeração sob demanda em memória);
    `adquirir_lote` e o desvio para lote em `requisitar_numeracao` ficam
    indisponíveis (falha explícita, nunca fallback silencioso para uma
    persistência que não existe).
    """

    nome_adapter: str = "stub"

    def __init__(self, conn=None) -> None:
        self._conn = conn
        self._contadores: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()
        # Registro local de numerações emitidas — usado por verificar_numeracao
        # para confirmar que a numeração veio deste stub. NÃO é persistente:
        # o objetivo é apenas dar comportamento útil em testes.
        self._emitidas: dict[str, NumeracaoSNCR] = {}

    # -----------------------------------------------------------------------
    # Operações
    # -----------------------------------------------------------------------

    def requisitar_numeracao(
        self,
        tipo_receituario: str,
        prescritor_cpf: str,
        quantidade: int = 1,
    ) -> list[ResultadoSNCR]:
        if quantidade < 1:
            return [
                ResultadoSNCR(
                    sucesso=False,
                    erro=f"quantidade inválida: {quantidade}",
                    codigo_erro=SNCR_ERRO_INVALIDO,
                )
            ]

        abrev = _ABREV_TIPO.get(tipo_receituario)
        if abrev is None:
            return [
                ResultadoSNCR(
                    sucesso=False,
                    erro=f"tipo_receituario desconhecido: {tipo_receituario!r}",
                    codigo_erro=SNCR_ERRO_INVALIDO,
                )
                for _ in range(quantidade)
            ]

        agora = datetime.utcnow()
        ano = str(agora.year)

        # DESENHO §2 (G2): com `conn` disponível, tenta sacar do lote ativo
        # do par (prescritor, tipo) antes de cair no sob-demanda em memória.
        # Sem lote utilizável (nenhum, esgotado, ou vencido — AC4: skip é
        # LOGADO, não silencioso) OU quantidade maior que a faixa restante
        # (simplificação deliberada: não mistura números de lote com
        # sob-demanda numa mesma chamada), segue exatamente o caminho
        # original (AC2: "nada quebra no meio").
        if self._conn is not None:
            do_lote = self._sacar_do_lote_ativo(
                tipo_receituario, prescritor_cpf, quantidade, agora
            )
            if do_lote is not None:
                for numeracao in do_lote:
                    self._emitidas[numeracao.numero] = numeracao
                    logger.info(
                        "[SNCR-STUB] numeracao emitida do lote: numero=%s "
                        "lote_id=%s tipo=%s cpf=***%s",
                        numeracao.numero,
                        numeracao.lote_id,
                        tipo_receituario,
                        prescritor_cpf[-3:] if prescritor_cpf else "",
                    )
                return [ResultadoSNCR(sucesso=True, dados=n) for n in do_lote]

        chave_contador = (ano, abrev)

        resultados: list[ResultadoSNCR] = []
        with self._lock:
            base = self._contadores.get(chave_contador, 0)
            for offset in range(1, quantidade + 1):
                seq = base + offset
                numero = f"{_PREFIXO_STUB}-{ano}-{abrev}-{seq:09d}"
                numeracao = NumeracaoSNCR(
                    numero=numero,
                    tipo_receituario=tipo_receituario,
                    prescritor_cpf=prescritor_cpf,
                    concedida_em=agora,
                    valida_ate=None,
                    lote_id=None,
                )
                self._emitidas[numero] = numeracao
                resultados.append(
                    ResultadoSNCR(sucesso=True, dados=numeracao)
                )
                logger.info(
                    "[SNCR-STUB] numeracao emitida: numero=%s tipo=%s cpf=***%s",
                    numero,
                    tipo_receituario,
                    prescritor_cpf[-3:] if prescritor_cpf else "",
                )
            self._contadores[chave_contador] = base + quantidade

        return resultados

    # -----------------------------------------------------------------------
    # Lotes (talonários digitais) — DESENHO-TALAO-DIGITAL-SNCR.md §2 (G2)
    # -----------------------------------------------------------------------

    def _sacar_do_lote_ativo(
        self,
        tipo_receituario: str,
        prescritor_cpf: str,
        quantidade: int,
        agora: datetime,
    ) -> list[NumeracaoSNCR] | None:
        """Tenta sacar `quantidade` números do lote ativo do par (tipo,
        prescritor). Retorna None (não list vazia) quando não há lote
        utilizável — sinal para o chamador cair no caminho sob-demanda.

        "Utilizável" = existe, não esgotou (`proximo <= fim`) e não venceu
        (`valida_ate` NULL ou >= agora). Um lote existente mas vencido é
        LOGADO (AC4: afirma, não silencia) e tratado como inexistente daqui
        em diante — a emissão não bloqueia por numeração (§5).

        Só saca quando o lote cobre a quantidade INTEIRA pedida — não
        mistura números de lote com sob-demanda numa mesma chamada
        (simplificação deliberada; o único chamador de produção hoje pede
        sempre quantidade=1, então o caso de fronteira é só de robustez).
        """
        row = self._conn.execute(
            """
            SELECT id, lote_id, inicio, fim, proximo, valida_ate
              FROM sncr_lotes
             WHERE prescritor_identificador = ? AND tipo_receituario = ?
             ORDER BY criado_em DESC
             LIMIT 1
            """
            + row_lock_suffix(),
            (prescritor_cpf, tipo_receituario),
        ).fetchone()
        if row is None:
            return None

        # Acesso por dict, não por posição: RealDictCursor (PG) devolve um
        # dict — iterar/desempacotar por posição pega as CHAVES, não os
        # valores. sqlite3.Row aceita os dois; dict é o caminho seguro nos
        # dois dialetos (mesmo padrão de `_row_dict` em catalogo_regulatorio.py).
        d = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(row)
        lote_pk = d["id"]
        lote_id = d["lote_id"]
        fim = d["fim"]
        proximo = d["proximo"]
        valida_ate = d["valida_ate"]
        if isinstance(valida_ate, str):
            valida_ate = datetime.fromisoformat(valida_ate)
        if valida_ate is not None and valida_ate < agora:
            logger.info(
                "[SNCR-STUB] lote vencido, ignorado: lote_id=%s valida_ate=%s",
                lote_id, valida_ate,
            )
            return None
        restante = fim - proximo + 1
        if restante < quantidade:
            if restante <= 0:
                logger.info("[SNCR-STUB] lote esgotado, ignorado: lote_id=%s", lote_id)
            return None

        numeracoes: list[NumeracaoSNCR] = []
        for offset in range(quantidade):
            seq = proximo + offset
            # lote_id já começa com "STUB-" — não duplica o prefixo aqui.
            numero = f"{lote_id}-{seq:09d}"
            numeracoes.append(
                NumeracaoSNCR(
                    numero=numero,
                    tipo_receituario=tipo_receituario,
                    prescritor_cpf=prescritor_cpf,
                    concedida_em=agora,
                    valida_ate=valida_ate,
                    lote_id=lote_id,
                )
            )
        self._conn.execute(
            "UPDATE sncr_lotes SET proximo = ? WHERE id = ?",
            (proximo + quantidade, lote_pk),
        )
        return numeracoes

    def adquirir_lote(
        self,
        tipo_receituario: str,
        prescritor_cpf: str,
        quantidade: int,
        valida_ate: datetime | None = None,
    ) -> ResultadoSNCR:
        if quantidade < 1:
            return ResultadoSNCR(
                sucesso=False,
                erro=f"quantidade inválida: {quantidade}",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )
        abrev = _ABREV_TIPO.get(tipo_receituario)
        if abrev is None:
            return ResultadoSNCR(
                sucesso=False,
                erro=f"tipo_receituario desconhecido: {tipo_receituario!r}",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )
        if self._conn is None:
            return ResultadoSNCR(
                sucesso=False,
                erro="adquirir_lote requer conexão de banco (SNCRStub(conn=...))",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )

        agora = datetime.utcnow()
        ano = str(agora.year)
        # Placeholder com UUID: nunca colide, mesmo sob concorrência — evita
        # o placeholder fixo (que colidiria na constraint UNIQUE entre duas
        # aquisições simultâneas) sem depender de round-trip extra pro PK
        # antes de gravar. Regravado com o id real logo abaixo.
        placeholder = f"{_PREFIXO_STUB}-LOTE-TEMP-{uuid.uuid4().hex}"
        cur = self._conn.execute(
            """
            INSERT INTO sncr_lotes
              (lote_id, tipo_receituario, prescritor_identificador,
               inicio, fim, proximo, valida_ate, adapter_usado, criado_em)
            VALUES (?, ?, ?, 1, ?, 1, ?, ?, ?)
            """,
            (placeholder, tipo_receituario, prescritor_cpf, quantidade,
             valida_ate, self.nome_adapter, agora),
        )
        lote_pk = cur.lastrowid
        lote_id = f"{_PREFIXO_STUB}-LOTE-{ano}-{abrev}-{lote_pk:06d}"
        self._conn.execute(
            "UPDATE sncr_lotes SET lote_id = ? WHERE id = ?",
            (lote_id, lote_pk),
        )
        logger.info(
            "[SNCR-STUB] lote adquirido: lote_id=%s tipo=%s cpf=***%s faixa=[1..%d]",
            lote_id, tipo_receituario,
            prescritor_cpf[-3:] if prescritor_cpf else "", quantidade,
        )
        lote = LoteSNCR(
            lote_id=lote_id,
            tipo_receituario=tipo_receituario,
            prescritor_cpf=prescritor_cpf,
            inicio=1,
            fim=quantidade,
            proximo=1,
            concedido_em=agora,
            valida_ate=valida_ate,
        )
        return ResultadoSNCR(sucesso=True, dados=lote)

    def verificar_numeracao(self, numero_sncr: str) -> ResultadoSNCR:
        if not numero_sncr or not numero_sncr.startswith(f"{_PREFIXO_STUB}-"):
            return ResultadoSNCR(
                sucesso=False,
                erro="Numeração não reconhecida pelo stub (prefixo STUB- ausente)",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )
        numeracao = self._emitidas.get(numero_sncr)
        if numeracao is None:
            return ResultadoSNCR(
                sucesso=False,
                erro=f"Numeração {numero_sncr} não foi emitida por esta instância do stub",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )
        logger.info("[SNCR-STUB] verificacao: numero=%s OK", numero_sncr)
        return ResultadoSNCR(sucesso=True, dados=numeracao)

    def registrar_utilizacao(
        self,
        numero_sncr: str,
        dispensador_cnes: str,
        data_dispensacao: datetime,
    ) -> ResultadoSNCR:
        if not numero_sncr.startswith(f"{_PREFIXO_STUB}-"):
            return ResultadoSNCR(
                sucesso=False,
                erro="Numeração não reconhecida pelo stub (prefixo STUB- ausente)",
                codigo_erro=SNCR_ERRO_INVALIDO,
            )
        registro = RegistroUtilizacao(
            numero_sncr=numero_sncr,
            registrado_em=data_dispensacao,
            dispensador_cnes=dispensador_cnes,
            status="utilizado",
        )
        logger.info(
            "[SNCR-STUB] utilizacao registrada: numero=%s cnes=%s",
            numero_sncr,
            dispensador_cnes,
        )
        return ResultadoSNCR(sucesso=True, dados=registro)

    def health_check(self) -> bool:
        # Stub está sempre disponível — não há rede envolvida.
        return True
