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

from app.adapters.sncr_interface import (
    NumeracaoSNCR,
    RegistroUtilizacao,
    ResultadoSNCR,
    SNCRAdapter,
    SNCR_ERRO_INVALIDO,
)

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

    Contadores são por (ano × tipo) e mantidos em memória (thread-safe).
    Cada instância do stub mantém seu próprio contador — instâncias
    diferentes geram sequências independentes. Para um teste que precise
    de sequências previsíveis entre processos, usar um banco real ou
    instância única.
    """

    nome_adapter: str = "stub"

    def __init__(self) -> None:
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
