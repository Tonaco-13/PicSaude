"""
sncr_interface.py
=================
Ticket 16A — Contrato de integração com o SNCR (Sistema Nacional de Controle
de Receituários) da Anvisa.

CONTEXTO
--------
A RDC Anvisa nº 1.000/2025 exige que receituários eletrônicos sejam
emitidos exclusivamente por sistemas integrados ao SNCR via API, com
numeração individualizada previamente concedida.

Em abril/2026 a especificação técnica da API do SNCR ainda NÃO está
publicamente disponível. Plataformas como Memed já integraram, mas a
documentação pode estar restrita a parceiros credenciados.

PADRÃO ARQUITETURAL
-------------------
Esta interface (ABC) define o CONTRATO de operações esperadas do SNCR.
Implementações concretas:

  - SNCRStub  — mock local (Ticket 16A — desenvolvimento e testes)
  - SNCRReal  — integração real (Ticket 16B futuro, quando API disponível)

A interface deve permanecer ESTÁVEL: mudanças aqui são `core` e exigem
revisão central (CLAUDE.md §10). Quando a especificação real chegar,
substitui-se a implementação — o resto do sistema (router, motor
regulatório, ledger) não muda.

CAMPOS CONFIRMADOS vs INFERIDOS
-------------------------------
Os dataclasses abaixo refletem requisitos NORMATIVOS conhecidos
(numeração individualizada, vinculação a CPF do prescritor, registro
de utilização). Detalhes exatos (formato do número, lote_id, validade)
são INFERIDOS e podem ser ajustados quando a especificação real chegar.

Não confundir: o CONTRATO de operações (requisitar / verificar /
registrar / health) é estável. O SHAPE dos campos pode variar.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union


# ---------------------------------------------------------------------------
# DTOs do contrato
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NumeracaoSNCR:
    """Resultado de uma requisição de numeração ao SNCR.

    Campos
    ------
    numero            Identificador da numeração (ex: "SNCR-2026-NRA-000001234"
                      ou "STUB-2026-NRA-000000001" no stub).
    tipo_receituario  Slug do tipo (ex: "notificacao_receita_a"). Mesmo
                      vocabulário do `domain/motor_regulatorio.py`.
    prescritor_cpf    CPF do prescritor a quem a numeração foi vinculada.
    concedida_em      Timestamp UTC da concessão.
    valida_ate        Prazo de validade (None se sem prazo declarado).
    lote_id           ID do lote de numeração (opcional).
    """
    numero: str
    tipo_receituario: str
    prescritor_cpf: str
    concedida_em: datetime
    valida_ate: Optional[datetime] = None
    lote_id: Optional[str] = None


@dataclass(frozen=True)
class RegistroUtilizacao:
    """Resultado do registro de utilização (dispensação) de um receituário.

    Operação executada pela farmácia (escopo futuro), exposta na interface
    para completude do contrato. Quando o módulo de dispensação SNCR for
    implementado, este DTO informa o que retorna ao consumidor.
    """
    numero_sncr: str
    registrado_em: datetime
    dispensador_cnes: Optional[str] = None
    status: str = "utilizado"  # "utilizado" | "cancelado"


@dataclass(frozen=True)
class ResultadoSNCR:
    """Wrapper de resultado para qualquer operação SNCR.

    Padroniza retorno: sucesso/erro + payload tipado + código de erro
    classificável (para retries e observabilidade).

    Campos
    ------
    sucesso       True se operação completou sem erro.
    dados         NumeracaoSNCR | RegistroUtilizacao | None — payload da operação.
    erro          Mensagem humana de erro (None se sucesso=True).
    codigo_erro   Código classificável (ex: "SNCR_TIMEOUT", "SNCR_INVALIDO",
                  "SNCR_INDISPONIVEL"). None se sucesso=True.
    tentativa     Número da tentativa atual (para retries futuros).
    """
    sucesso: bool
    dados: Optional[Union[NumeracaoSNCR, RegistroUtilizacao]] = None
    erro: Optional[str] = None
    codigo_erro: Optional[str] = None
    tentativa: int = 1


# ---------------------------------------------------------------------------
# Códigos de erro padronizados (vocabulário controlado)
# ---------------------------------------------------------------------------

SNCR_ERRO_TIMEOUT       = "SNCR_TIMEOUT"
SNCR_ERRO_INDISPONIVEL  = "SNCR_INDISPONIVEL"
SNCR_ERRO_INVALIDO      = "SNCR_INVALIDO"
SNCR_ERRO_NAO_AUTORIZADO = "SNCR_NAO_AUTORIZADO"
SNCR_ERRO_DESCONHECIDO  = "SNCR_DESCONHECIDO"


# ---------------------------------------------------------------------------
# Contrato (ABC) — implementação concreta vive em sncr_stub.py / sncr_real.py
# ---------------------------------------------------------------------------

class SNCRAdapter(ABC):
    """Contrato para integração com o SNCR da Anvisa.

    Implementações disponíveis:
      - SNCRStub: mock local (desenvolvimento e testes)
      - SNCRReal: integração real (Ticket 16B, quando API disponível)

    Seleção via factory (`get_sncr_adapter()` em `sncr_factory.py`),
    configurada por variável de ambiente `SNCR_ADAPTER`.
    """

    # -----------------------------------------------------------------------
    # Identificação da implementação (para observabilidade e ledger)
    # -----------------------------------------------------------------------

    @property
    @abstractmethod
    def nome_adapter(self) -> str:
        """Identificador curto do adapter (ex: "stub", "real").

        Usado em logs, métricas e no campo `adapter_usado` da tabela
        `receituarios` para rastreabilidade — qualquer numeração persistida
        carrega o adapter que a gerou.
        """
        ...

    # -----------------------------------------------------------------------
    # Operações SNCR
    # -----------------------------------------------------------------------

    @abstractmethod
    def requisitar_numeracao(
        self,
        tipo_receituario: str,
        prescritor_cpf: str,
        quantidade: int = 1,
    ) -> list[ResultadoSNCR]:
        """Requisita numeração ao SNCR para receituários.

        Args:
            tipo_receituario: tipo do receituário (slug do motor regulatório,
                ex: "notificacao_receita_a", "notificacao_receita_b",
                "receita_controle_especial", "notificacao_receita_especial").
            prescritor_cpf: CPF do prescritor (vinculação obrigatória pela
                RDC 1.000/2025).
            quantidade: número de numerações solicitadas no lote (>=1).

        Returns:
            Lista de ResultadoSNCR, um por numeração solicitada.
            Lista pode conter mistura de sucesso/falha — chamador deve
            inspecionar cada item.

        A implementação real usará assinatura qualificada ICP-Brasil para
        autenticar a requisição (a definir quando a API for documentada).
        """
        ...

    @abstractmethod
    def verificar_numeracao(
        self,
        numero_sncr: str,
    ) -> ResultadoSNCR:
        """Verifica validade de uma numeração SNCR.

        Usado pela farmácia na dispensação (escopo futuro). Definido na
        interface para completude do contrato.

        Returns:
            ResultadoSNCR.sucesso=True com NumeracaoSNCR válida, ou
            sucesso=False com codigo_erro indicando motivo (não encontrado,
            expirado, revogado, etc.).
        """
        ...

    @abstractmethod
    def registrar_utilizacao(
        self,
        numero_sncr: str,
        dispensador_cnes: str,
        data_dispensacao: datetime,
    ) -> ResultadoSNCR:
        """Registra utilização (dispensação) de um receituário no SNCR.

        Escopo da farmácia, não do prescritor. Exposto na interface para
        completude do contrato — o módulo consumidor (dispensação) será
        implementado em ticket futuro.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verifica se o SNCR está acessível.

        Returns:
            True se o serviço responde (stub: sempre True; real: ping leve).
            False se indisponível — neste caso, operações seguintes devem
            falhar com `SNCR_ERRO_INDISPONIVEL`.
        """
        ...
