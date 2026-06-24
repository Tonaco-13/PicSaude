from app.models.paciente import Paciente
from app.models.prescritor import Prescritor
from app.models.estabelecimento import Estabelecimento
from app.models.prescricao import Prescricao
from app.models.prescricao_item import PrescricaoItem
from app.models.prescricao_evento import PrescricaoEvento
from app.models.codigo_login import CodigoLogin
from app.models.prescricao_custodia import PrescricaoCustodia
from app.models.dispensacao import Dispensacao
from app.models.usuario import Usuario
from app.models.prescricao_assinatura import PrescricaoAssinatura
from app.models.solicitacao_renovacao import SolicitacaoRenovacao
from app.models.pedido_exame import PedidoExame
from app.models.pedido_exame_item import PedidoExameItem
from app.models.pedido_exame_evento import PedidoExameEvento
from app.models.pedido_exame_custodia import PedidoExameCustodia
from app.models.laudo import Laudo
from app.models.laudo_item import LaudoItem
from app.models.laudo_evento import LaudoEvento
from app.models.laudo_custodia import LaudoCustodia
from app.models.token_apresentacao import TokenApresentacao
from app.models.token_apresentacao_uso import TokenApresentacaoUso
from app.models.dispensacao_hospitalar import DispensacaoHospitalar  # Ticket 27
from app.models.agendamento import Agendamento                       # Ticket 29
from app.models.agendamento_evento import AgendamentoEvento          # Ticket 29
from app.models.evento_publicacao import EventoPublicacao            # G4A
from app.models.meta_instalacao import MetaInstalacao               # G5-impl
from app.models.prestador import Prestador                          # Ticket 30
from app.models.unidade import Unidade                              # Ticket 30
from app.models.api_key import ApiKey                               # G4B
from app.models.circulacao_diagnostica import CirculacaoDiagnostica           # Ticket 52
from app.models.circulacao_diagnostica_item import CirculacaoDiagnosticaItem  # Ticket 52
from app.models.circulacao_diagnostica_evento import CirculacaoDiagnosticaEvento  # Ticket 52
from app.models.receituario import Receituario, ReceituarioItem                   # Ticket 15
from app.models.catalogo_substancia import CatalogoSubstancia                       # Ticket 20
from app.models.prescritor_certificado import PrescritorCertificado                  # Ticket 21
from app.models.encaminhamento import Encaminhamento                                 # TICKET-ENCAMINHAMENTO-E1
from app.models.encaminhamento_item import EncaminhamentoItem                         # TICKET-ENCAMINHAMENTO-E1
from app.models.encaminhamento_evento import EncaminhamentoEvento                     # TICKET-ENCAMINHAMENTO-E1
from app.models.encaminhamento_custodia import EncaminhamentoCustodia                 # TICKET-ENCAMINHAMENTO-E1
from app.models.contrarreferencia import Contrarreferencia                             # TICKET-ENCAMINHAMENTO-E2
from app.models.contrarreferencia_evento import ContrarreferenciaEvento               # TICKET-ENCAMINHAMENTO-E2
from app.models.contrarreferencia_custodia import ContrarreferenciaCustodia           # TICKET-ENCAMINHAMENTO-E2
from app.models.atestado import Atestado                                               # Atestado (objeto sanitário)
from app.models.atestado_evento import AtestadoEvento                                  # Atestado
from app.models.atestado_custodia import AtestadoCustodia                              # Atestado

__all__ = [
    "Paciente",
    "Prescritor",
    "Estabelecimento",
    "Prescricao",
    "PrescricaoItem",
    "PrescricaoEvento",
    "CodigoLogin",
    "PrescricaoCustodia",
    "Dispensacao",
    "Usuario",
    "PrescricaoAssinatura",
    "SolicitacaoRenovacao",
    "PedidoExame",
    "PedidoExameItem",
    "PedidoExameEvento",
    "PedidoExameCustodia",
    "Laudo",
    "LaudoItem",
    "LaudoEvento",
    "LaudoCustodia",
    "TokenApresentacao",
    "TokenApresentacaoUso",
    "DispensacaoHospitalar",  # Ticket 27
    "Agendamento",            # Ticket 29
    "AgendamentoEvento",      # Ticket 29
    "EventoPublicacao",       # G4A
    "MetaInstalacao",         # G5-impl
    "Prestador",              # Ticket 30
    "Unidade",                # Ticket 30
    "ApiKey",                 # G4B
    "CirculacaoDiagnostica",       # Ticket 52
    "CirculacaoDiagnosticaItem",   # Ticket 52
    "CirculacaoDiagnosticaEvento", # Ticket 52
    "Receituario",                 # Ticket 15
    "ReceituarioItem",             # Ticket 15
    "CatalogoSubstancia",          # Ticket 20
    "PrescritorCertificado",       # Ticket 21
    "Encaminhamento",              # TICKET-ENCAMINHAMENTO-E1
    "EncaminhamentoItem",          # TICKET-ENCAMINHAMENTO-E1
    "EncaminhamentoEvento",        # TICKET-ENCAMINHAMENTO-E1
    "EncaminhamentoCustodia",      # TICKET-ENCAMINHAMENTO-E1
    "Contrarreferencia",           # TICKET-ENCAMINHAMENTO-E2
    "ContrarreferenciaEvento",     # TICKET-ENCAMINHAMENTO-E2
    "ContrarreferenciaCustodia",   # TICKET-ENCAMINHAMENTO-E2
    "Atestado",                    # Atestado (objeto sanitário)
    "AtestadoEvento",              # Atestado
    "AtestadoCustodia",            # Atestado
]
