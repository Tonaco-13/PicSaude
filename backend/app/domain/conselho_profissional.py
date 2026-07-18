"""
conselho_profissional.py
========================
Conselho profissional emissor do atestado — FONTE ÚNICA (TICKET-ATESTADO-CONFORMIDADE).

O atestado não é um documento genérico: quem o assina determina como ele se chama
("ATESTADO MÉDICO" vs. "ATESTADO ODONTOLÓGICO"), sob que cuidados o paciente esteve
("cuidados médicos" vs. "cuidados odontológicos") e sob qual sigla de registro o
profissional se identifica ("CRM-PE 12345" vs. "CRO-PE 1234").

Esses três derivados vivem AQUI e só aqui. O PDF (`domain/pdf_atestado.py`) e a tela
(`prescritor.html`, via `/config/public`) perguntam a este módulo — nunca hardcodam.
É a mesma régua do `grupo_por_id` do R4 (`domain/motor_regulatorio.py`): o movimento
congela um slug estável, e o nome humano é resolvido a partir do catálogo canônico.
Duplicar "ATESTADO ODONTOLÓGICO" no HTML criaria dois lugares que divergiriam.

Escopo (decisão do Fabiano)
---------------------------
Apenas **CFM** (medicina) e **CFO** (odontologia). Enfermagem (COFEN) NÃO entra agora
— a norma que define atestado de enfermagem está pendente; registrado em
`docs/DIVIDA-TECNICA.md`. Acrescentar um conselho é acrescentar uma entrada em
`CONSELHOS` — nada mais.

Legado
------
`atestados.conselho` é NULLABLE: atestados emitidos antes desta migração não têm
conselho declarado. Para eles vale `CONSELHO_PADRAO` (CFM) — o comportamento
histórico ("ATESTADO MÉDICO"), preservado byte a byte. Slug desconhecido degrada
para o mesmo padrão em vez de levantar: um PDF de atestado nunca deve falhar por
causa de um rótulo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class ConselhoProfissional:
    """Conselho federal que habilita a emissão do atestado.

    id_conselho          — slug estável gravado em `atestados.conselho` ("CFM").
    nome                 — nome por extenso, para telas e documentação.
    sigla_registro       — sigla do registro regional ("CRM"), o que sai no documento.
    titulo_documento     — título em caixa alta no topo do PDF.
    adjetivo_cuidados    — plural, ramo de afastamento: "sob cuidados {adjetivo}".
    adjetivo_atendimento — singular, ramo de comparecimento: "a atendimento {adjetivo}".

    Os dois adjetivos existem porque as duas frases do corpo têm concordância
    diferente ("cuidados médicos" / "atendimento médico"). Um só campo obrigaria o
    PDF a flexionar a palavra — regra de gramática escondida no renderizador.
    """

    id_conselho: str
    nome: str
    sigla_registro: str
    titulo_documento: str
    adjetivo_cuidados: str
    adjetivo_atendimento: str


CONSELHO_CFM = ConselhoProfissional(
    id_conselho="CFM",
    nome="Conselho Federal de Medicina",
    sigla_registro="CRM",
    titulo_documento="ATESTADO MÉDICO",
    adjetivo_cuidados="médicos",
    adjetivo_atendimento="médico",
)

CONSELHO_CFO = ConselhoProfissional(
    id_conselho="CFO",
    nome="Conselho Federal de Odontologia",
    sigla_registro="CRO",
    titulo_documento="ATESTADO ODONTOLÓGICO",
    adjetivo_cuidados="odontológicos",
    adjetivo_atendimento="odontológico",
)

# Lista canônica. Ordem = ordem de exibição na tela.
CONSELHOS: tuple[ConselhoProfissional, ...] = (CONSELHO_CFM, CONSELHO_CFO)

# Conselho assumido quando `atestados.conselho` é NULL (atestado legado, anterior à
# migração) ou quando o slug gravado não existe mais no catálogo. Mantém o
# comportamento histórico do PDF — "ATESTADO MÉDICO" —, que é o que esses documentos
# já exibiam quando foram emitidos.
CONSELHO_PADRAO = CONSELHO_CFM

MAPA_ID_CONSELHO: Mapping[str, ConselhoProfissional] = {c.id_conselho: c for c in CONSELHOS}
MAPA_SIGLA_CONSELHO: Mapping[str, ConselhoProfissional] = {c.sigla_registro: c for c in CONSELHOS}

# Conjunto aceito no payload de emissão (validação Pydantic no router).
IDS_CONSELHO_VALIDOS: frozenset[str] = frozenset(MAPA_ID_CONSELHO)


def conselho_por_id(id_conselho: Optional[str]) -> Optional[ConselhoProfissional]:
    """Resolve o conselho a partir do slug gravado em `atestados.conselho`.

    NULL (legado) ou slug desconhecido → `None`. Quem precisa de um valor sempre
    presente para renderizar usa `conselho_ou_padrao`.
    """
    if not id_conselho:
        return None
    return MAPA_ID_CONSELHO.get(id_conselho.strip().upper())


def conselho_por_sigla(sigla_registro: Optional[str]) -> Optional[ConselhoProfissional]:
    """Resolve o conselho a partir da sigla do registro regional ("CRM" → CFM).

    Existe porque o cadastro do profissional fala em CRM/CRO (a sigla que ele vê na
    carteira), enquanto o atestado grava o conselho federal. A tradução mora aqui,
    não no formulário.
    """
    if not sigla_registro:
        return None
    return MAPA_SIGLA_CONSELHO.get(sigla_registro.strip().upper())


def conselho_ou_padrao(id_conselho: Optional[str]) -> ConselhoProfissional:
    """Conselho para fins de RENDERIZAÇÃO — nunca None, nunca levanta.

    Legado (NULL) e slug desconhecido caem em `CONSELHO_PADRAO`, preservando o
    documento histórico. Use nas trilhas do PDF; use `conselho_por_id` quando
    precisar distinguir "não declarado" de "declarado como CFM".
    """
    return conselho_por_id(id_conselho) or CONSELHO_PADRAO


def formatar_registro(
    id_conselho: Optional[str],
    uf_registro: Optional[str],
    registro_profissional: Optional[str],
) -> Optional[str]:
    """Monta a identificação do profissional: "CRM-PE 12345".

    Três casos, nesta ordem:

    1. Conselho + UF + número declarados → forma canônica ("CRO-PE 1234").
    2. Só o campo `registro_profissional` (LEGADO: antes desta migração ele guardava
       texto livre, muitas vezes já no formato "CRM-PE 12345") → devolve como está.
       Reformatar seria inventar UF que o registro histórico não tem.
    3. Nada declarado → `None`; o chamador omite a linha.
    """
    numero = (registro_profissional or "").strip()
    conselho = conselho_por_id(id_conselho)
    uf = (uf_registro or "").strip().upper()

    if conselho and uf and numero:
        return f"{conselho.sigla_registro}-{uf} {numero}"
    return numero or None


def catalogo_publico() -> list[dict]:
    """Catálogo serializável para a tela (servido em `GET /config/public`).

    É por aqui que o HTML "pergunta ao domínio": o formulário monta o seletor de
    conselho a partir desta lista, em vez de repetir os rótulos no markup.
    """
    return [
        {
            "id_conselho": c.id_conselho,
            "nome": c.nome,
            "sigla_registro": c.sigla_registro,
            "titulo_documento": c.titulo_documento,
        }
        for c in CONSELHOS
    ]
