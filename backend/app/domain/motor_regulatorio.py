"""
motor_regulatorio.py
====================
Motor regulatório local — Ticket 15 — RDC Anvisa 1.000/2025.

Lógica pura (sem FastAPI, sem banco, sem I/O) que:

1. Classifica cada item de prescrição em um **grupo regulatório** a partir
   de `prescricao_itens.classe_controle`.
2. Determina qual **tipo de receituário** atende cada grupo (amarela / azul
   / branca / especial / simples).
3. Agrupa itens de uma prescrição em N receituários distintos, um por tipo.
4. Valida se a `assinatura_modo` da prescrição atende ao **nível mínimo**
   exigido pelo grupo (qualificada / avançada / nenhuma).

Arquitetura
-----------
Este módulo é consumido pelo endpoint
`POST /prescricoes/{protocolo}/receituarios/gerar` (routers/receituarios.py).
Não altera o fluxo existente de emissão de prescrição. Uma prescrição é
emitida normalmente pelo fluxo do Ticket 1–14; a geração de receituários
regulatórios é um passo posterior e opcional que **deriva** receituários
a partir de uma prescrição existente.

O bloqueio de emissão sem assinatura adequada é decisão do endpoint
consumidor. Este motor apenas **reporta** se a assinatura é suficiente
(`ResultadoValidacao.valido`).

Referências
-----------
- RDC Anvisa nº 1.000/2025 — SNCR (adequação até 01/06/2026).
- Portaria SVS/MS nº 344/1998 — Listas A, B, C, D (substâncias controladas).
- RDC Anvisa nº 471/2021 — retinoides sistêmicos.
- Classe de controle no código: `app/domain/medicamento.py::CLASSES_CONTROLE_ESPECIAL`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Optional

from app.domain.medicamento import CLASSES_CONTROLE_ESPECIAL
from app.domain.retencao import TIPOS_RETENCAO_VALIDOS

# ---------------------------------------------------------------------------
# Versão do motor — carimbo de escrituração regulatória (R4, CLAUDE.md §2a)
# ---------------------------------------------------------------------------
# Congelada POR VALOR no movimento de dispensação junto com o grupo resolvido
# (ver escriturar_grupo_regulatorio). É o que dá R1 pleno: se a definição de um
# grupo mudar amanhã (RDC nova), o movimento passado guarda sob QUAL versão de
# regra foi escriturado — sem precisar congelar todos os campos materiais.
#
# Bump SOMENTE quando a semântica de um grupo mudar (classes, vias, retenção,
# assinatura mínima). É um marco regulatório, não um número de build.
MOTOR_REGULATORIO_VERSAO = "1.0.0"


# ---------------------------------------------------------------------------
# Vocabulário de nível de assinatura
# ---------------------------------------------------------------------------

# Níveis de assinatura aceitos pela RDC 1.000:
#   qualificada — assinatura digital ICP-Brasil (certificado A1/A3)
#   avancada    — assinatura eletrônica avançada (gov.br)
#   nenhuma     — não há exigência regulatória
NIVEL_QUALIFICADA = "qualificada"
NIVEL_AVANCADA    = "avancada"
NIVEL_NENHUMA     = "nenhuma"

NIVEIS_ASSINATURA: FrozenSet[str] = frozenset({
    NIVEL_QUALIFICADA, NIVEL_AVANCADA, NIVEL_NENHUMA,
})

# Ordem crescente — um nível presente satisfaz qualquer nível exigido de
# mesma ou menor força. "qualificada" é o mais forte.
_ORDEM_NIVEL: Mapping[str, int] = {
    NIVEL_NENHUMA:     0,
    NIVEL_AVANCADA:    1,
    NIVEL_QUALIFICADA: 2,
}

# Mapeamento assinatura_modo (valor persistido em prescricoes.assinatura_modo)
# → nível equivalente na RDC 1.000.
# Ver app/domain/assinatura.py::MODOS_DIGITAIS_VALIDOS.
MODO_PARA_NIVEL: Mapping[Optional[str], str] = {
    "icp_brasil_local": NIVEL_QUALIFICADA,
    "gov_br_nuvem":     NIVEL_AVANCADA,
    None:               NIVEL_NENHUMA,
    "":                 NIVEL_NENHUMA,
}


# ---------------------------------------------------------------------------
# Estrutura de um grupo regulatório
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GrupoRegulatorio:
    """Descrição imutável de um grupo regulatório (uma categoria de
    receituário definida pela Portaria 344/98 e RDC 1.000/2025).
    """
    id_grupo: str                # identificador estável (slug)
    nome: str                    # descrição humana
    tipo_receituario: str        # slug do tipo de receituário
    classes: FrozenSet[str]      # classes de controle cobertas
    assinatura_minima: str       # "qualificada" | "avancada" | "nenhuma"
    vias: int                    # número de vias exigidas
    retencao_farmacia: bool      # farmácia retém uma via?
    requer_sncr: bool            # exige numeração SNCR?
    severidade: int              # menor número = mais severo (para ordenação)
    status_implementacao: str = "ativo"   # "ativo" | "pendente_classificacao"
    observacao: Optional[str] = None


# ---------------------------------------------------------------------------
# Definição dos grupos — Portaria 344/98 + RDC 1.000/2025 + RDC 471/2021
# ---------------------------------------------------------------------------
# A semântica detalhada de cada grupo (cor da receita, vias, retenção) vive
# aqui como dados — NÃO espalhar if/elif pelo código consumidor.

GRUPO_A = GrupoRegulatorio(
    id_grupo="notificacao_receita_a",
    nome="Notificação de Receita A (Amarela)",
    tipo_receituario="notificacao_receita_a",
    classes=frozenset({"A1", "A2", "A3"}),
    assinatura_minima=NIVEL_QUALIFICADA,
    vias=3,
    retencao_farmacia=True,
    requer_sncr=True,
    severidade=1,
)

GRUPO_B = GrupoRegulatorio(
    id_grupo="notificacao_receita_b",
    nome="Notificação de Receita B (Azul)",
    tipo_receituario="notificacao_receita_b",
    classes=frozenset({"B1", "B2"}),
    assinatura_minima=NIVEL_QUALIFICADA,
    vias=2,
    retencao_farmacia=True,
    requer_sncr=True,
    severidade=2,
)

# Nota: CLASSES_CONTROLE_ESPECIAL contém C5 mas não C1 (verificado em
# domain/medicamento.py). O ticket cita C1 em Grupo 3, mas o modelo atual
# do PicSaúde não usa C1. Mantemos C5 como única classe do Grupo 3; quando
# C1 for introduzido no modelo, basta adicionar aqui.
GRUPO_C = GrupoRegulatorio(
    id_grupo="receita_controle_especial",
    nome="Receita de Controle Especial (Branca — 2 vias)",
    tipo_receituario="receita_controle_especial",
    classes=frozenset({"C5"}),
    assinatura_minima=NIVEL_QUALIFICADA,
    vias=2,
    retencao_farmacia=True,
    requer_sncr=True,
    severidade=3,
    observacao=(
        "C5 (antimicrobianos/controle especial). C1 não está modelado hoje; "
        "quando adicionado em CLASSES_CONTROLE_ESPECIAL, incluir aqui."
    ),
)

GRUPO_D = GrupoRegulatorio(
    id_grupo="notificacao_receita_especial",
    nome="Notificação de Receita Especial (Retinoides/Talidomida)",
    tipo_receituario="notificacao_receita_especial",
    classes=frozenset({"D1", "D2"}),
    assinatura_minima=NIVEL_QUALIFICADA,
    vias=2,
    retencao_farmacia=True,
    requer_sncr=True,
    severidade=4,
    observacao="RDC 471/2021 — protocolo específico pode exigir termos adicionais.",
)

# Grupo 5 — medicamentos com retenção pela RDC 471/2021 (antimicrobianos +
# agonistas de GLP-1). NÃO está em CLASSES_CONTROLE_ESPECIAL — esses dois
# regimes regulatórios são INDEPENDENTES (Portaria 344 vs RDC 471/2021).
# Itens roteiam para este grupo quando `tipo_retencao` está preenchido
# (ver app/domain/retencao.py).
GRUPO_RETENCAO = GrupoRegulatorio(
    id_grupo="receita_retencao",
    nome="Receita com Retenção (RDC 471/2021)",
    tipo_receituario="receita_retencao",
    classes=frozenset(),   # vazio: roteado por tipo_retencao, não por classe
    assinatura_minima=NIVEL_AVANCADA,
    vias=2,
    retencao_farmacia=True,
    requer_sncr=False,
    severidade=5,
    status_implementacao="ativo",
    observacao=(
        "Antimicrobianos (RDC 471/2021 + IN 83/2021) e agonistas de GLP-1 "
        "(IN 360/2025). Classificados por tipo_retencao, não por "
        "classe_controle da Portaria 344/1998. Ref. SNGPC código '1' "
        "(apenas documentação, não usado na lógica do motor). Exenatida "
        "excluída da IN 360 — sem registro válido no Brasil. "
        "requer_sncr=False é premissa provisória — confirmar quando "
        "ferramenta SNCR para retenção estiver disponível."
    ),
)

GRUPO_SIMPLES = GrupoRegulatorio(
    id_grupo="receita_simples",
    nome="Receita Simples (sem controle regulatório)",
    tipo_receituario="receita_simples",
    classes=frozenset(),   # NULL/'' mapeia aqui via fallback
    assinatura_minima=NIVEL_NENHUMA,
    vias=1,
    retencao_farmacia=False,
    requer_sncr=False,
    severidade=99,
)

# Lista canônica — ordem de severidade crescente (mais severo primeiro).
GRUPOS_REGULATORIOS: tuple[GrupoRegulatorio, ...] = (
    GRUPO_A, GRUPO_B, GRUPO_C, GRUPO_D, GRUPO_RETENCAO, GRUPO_SIMPLES,
)

# Índice classe → grupo (construído a partir da lista canônica).
# Se um dia uma classe aparecer em mais de um grupo, este dict levantará
# ambiguidade no momento da construção (bug de config, preferível a silêncio).
def _construir_mapa_classe_grupo() -> dict[str, GrupoRegulatorio]:
    mapa: dict[str, GrupoRegulatorio] = {}
    for grupo in GRUPOS_REGULATORIOS:
        for classe in grupo.classes:
            if classe in mapa:
                raise RuntimeError(
                    f"Configuração inválida: classe {classe!r} aparece em "
                    f"{mapa[classe].id_grupo!r} e {grupo.id_grupo!r}."
                )
            mapa[classe] = grupo
    return mapa


MAPA_CLASSE_GRUPO: Mapping[str, GrupoRegulatorio] = _construir_mapa_classe_grupo()

# Índice id_grupo (slug) → grupo. FONTE ÚNICA para resolver o NOME humano a partir
# do slug congelado no movimento (R4): a tela nunca hardcoda nomes; pergunta aqui.
MAPA_ID_GRUPO: Mapping[str, GrupoRegulatorio] = {g.id_grupo: g for g in GRUPOS_REGULATORIOS}


def grupo_por_id(id_grupo: Optional[str]) -> Optional[GrupoRegulatorio]:
    """Resolve o grupo regulatório a partir do `id_grupo` (slug) CONGELADO no
    movimento — a fonte única do nome humano para a UI (R4, CLAUDE.md §2a).

    O comprovante/relatório congelam o slug (`grupo_regulatorio_id`); a tela quer
    exibir o nome ("Notificação de Receita B"). Este lookup faz o slug→nome a
    partir do MESMO catálogo `GRUPOS_REGULATORIOS` que define a escrituração —
    sem duplicar nomes no HTML (dois lugares divergiriam).

    NÃO re-resolve `classe_controle`: parte do slug já gravado, preservando R1
    (o nome acompanha o grupo que valeu à saída do produto). Slug desconhecido
    (ex.: grupo renomeado numa versão futura) → `None`, nunca levanta: a UI
    degrada para exibir só o slug, sem quebrar o comprovante."""
    if not id_grupo:
        return None
    return MAPA_ID_GRUPO.get(id_grupo)


# ---------------------------------------------------------------------------
# Lookup: classe_controle → grupo
# ---------------------------------------------------------------------------

def grupo_regulatorio(
    classe_controle: Optional[str],
    tipo_retencao: Optional[str] = None,
) -> GrupoRegulatorio:
    """Retorna o grupo regulatório de um item de prescrição.

    Prioridade (Ticket 18 — dois sistemas regulatórios coexistem):
      1. `classe_controle` ∈ Portaria 344 → grupo da Portaria 344.
         A Portaria 344 é mais restritiva e prevalece quando ambos
         os campos estão preenchidos.
      2. `tipo_retencao` ∈ TIPOS_RETENCAO_VALIDOS → GRUPO_RETENCAO
         (RDC 471/2021).
      3. `classe_controle` desconhecida (não-344 e não-vazia) → `ValueError`.
      4. `tipo_retencao` desconhecido (não-vazio) → `ValueError`. Não
         silenciar: classificar retenção desconhecida como simples
         seria risco regulatório.
      5. Ambos vazios/NULL → GRUPO_SIMPLES.

    Classes da Portaria 344 vivem em `CLASSES_CONTROLE_ESPECIAL`
    (`domain/medicamento.py`). Tipos de retenção vivem em
    `TIPOS_RETENCAO_VALIDOS` (`domain/retencao.py`).
    """
    classe = (str(classe_controle).strip().upper() if classe_controle else "") or None
    retencao = (str(tipo_retencao).strip().lower() if tipo_retencao else "") or None

    # 1. Portaria 344 prevalece (mais restritiva).
    if classe and classe in MAPA_CLASSE_GRUPO:
        return MAPA_CLASSE_GRUPO[classe]

    # Guardrail: classe em CLASSES_CONTROLE_ESPECIAL mas sem grupo mapeado
    # — bug de configuração, não silenciar.
    if classe and classe in CLASSES_CONTROLE_ESPECIAL and classe not in MAPA_CLASSE_GRUPO:
        raise RuntimeError(
            f"Classe {classe!r} está em CLASSES_CONTROLE_ESPECIAL mas não "
            "tem grupo regulatório mapeado em motor_regulatorio.py. "
            "Atualize GRUPOS_REGULATORIOS."
        )

    # 2. RDC 471/2021 — retenção (antimicrobianos / GLP-1).
    if retencao:
        if retencao in TIPOS_RETENCAO_VALIDOS:
            return GRUPO_RETENCAO
        # Valor desconhecido → erro. NÃO classificar como simples.
        raise ValueError(
            f"tipo_retencao desconhecido: {retencao!r}. "
            f"Valores aceitos: {sorted(TIPOS_RETENCAO_VALIDOS)} ou None."
        )

    # 3. Classe desconhecida (não é Portaria 344 nem retenção).
    if classe:
        raise ValueError(
            f"Classe de controle desconhecida: {classe!r}. "
            f"Classes aceitas: {sorted(MAPA_CLASSE_GRUPO)} ou None."
        )

    # 4. Sem classificação → simples.
    return GRUPO_SIMPLES


# ---------------------------------------------------------------------------
# Escrituração regulatória — R4 (CLAUDE.md §2a)
# ---------------------------------------------------------------------------

def escriturar_grupo_regulatorio(
    classe_controle: Optional[str],
    tipo_retencao: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve a **identidade regulatória a congelar no movimento** (R4).

    Devolve `(grupo_regulatorio_id, motor_regulatorio_versao)` para o chamador
    gravar POR VALOR na dispensação — como já se faz com `lote`/`fabricante`.
    Congelar por valor (não FK/derivação ao vivo) é o coração do R4: re-resolver
    na leitura daria a resposta do motor de HOJE; se a regra mudou, o período
    fechado mudaria (feriria R1). O snapshot fixa o que valeu à saída do produto.

    Semântica (decisões marteladas no TICKET-R4):
      - **NULL honesto para não-controlado.** `classe_controle` e `tipo_retencao`
        ambos vazios → grupo `receita_simples` → devolve `(None, None)`. O
        relatório mostra vazio; NUNCA se inventa grupo para um item comum.
      - **Item controlado** → `(id_grupo, MOTOR_REGULATORIO_VERSAO)`: a identidade
        regulatória (slug estável) mais o carimbo de versão da regra.
      - **Falha alta, não NULL silencioso.** Item COM `classe_controle`/
        `tipo_retencao` preenchido que o motor não classifica → `grupo_regulatorio`
        levanta `ValueError`/`RuntimeError` e este helper **propaga**. O chamador
        converte em erro HTTP: nunca se congela NULL para um controlado. Coerência
        com o "não silenciar" do próprio motor.

    Fronteira (§ ticket — sem API ANVISA/SNCR ao vivo): o motor é local e puro;
    nenhuma chamada externa. Congelamos só o que NÓS sabemos dizer do movimento
    (grupo + versão da regra), nunca um dado que dependeria de terceiro.
    """
    grupo = grupo_regulatorio(classe_controle, tipo_retencao)
    if grupo.id_grupo == GRUPO_SIMPLES.id_grupo:
        # Não-controlado: sem escrituração regulatória (NULL honesto).
        return None, None
    return grupo.id_grupo, MOTOR_REGULATORIO_VERSAO


# ---------------------------------------------------------------------------
# Agrupamento de itens em receituários
# ---------------------------------------------------------------------------

@dataclass
class Receituario:
    """Receituário regulatório derivado de uma prescrição.

    Não é persistido por este dataclass; a persistência é feita pelo
    endpoint em `routers/receituarios.py` via o model `Receituario`
    (SQLAlchemy) em `app/models/receituario.py`. Esta dataclass é o
    formato em memória produzido pelo motor.
    """
    tipo: str                            # tipo_receituario (slug)
    grupo_id: str                        # id do grupo regulatório
    grupo_nome: str                      # nome humano do grupo
    prescricao_id: int
    protocolo_prescricao: str
    itens: list[dict]                    # itens do grupo (dicts do banco)
    assinatura_minima: str               # "qualificada" | "avancada" | "nenhuma"
    vias: int
    retencao_farmacia: bool
    requer_sncr: bool
    severidade: int
    numeracao_sncr: Optional[str] = None  # preenchido no Ticket 16
    status: str = "gerado"


def agrupar_por_receituario(
    prescricao: dict,
    itens: list[dict],
) -> list[Receituario]:
    """Agrupa itens de uma prescrição em N receituários regulatórios.

    Uma mesma prescrição clínica pode exigir múltiplos receituários —
    um para cada tipo regulatório distinto envolvido. Cada `classe_controle`
    é roteada para seu grupo via `grupo_regulatorio()`. Itens do mesmo
    grupo permanecem juntos; grupos distintos geram receituários distintos.

    A ordem de saída é por **severidade regulatória crescente** (Grupo A
    primeiro, Receita Simples por último) — mais severo = menor número.

    Requer em `prescricao`: `id`, `protocolo`.
    Requer em cada item: `classe_controle` (pode ser None).

    Levanta `ValueError` se algum item usar classe desconhecida.
    """
    if not itens:
        return []

    prescricao_id = prescricao["id"]
    protocolo = prescricao["protocolo"]

    # Indexa itens por grupo (mantém ordem de entrada dentro de cada grupo).
    agrupados: dict[str, tuple[GrupoRegulatorio, list[dict]]] = {}
    for item in itens:
        grupo = grupo_regulatorio(
            item.get("classe_controle"),
            tipo_retencao=item.get("tipo_retencao"),
        )
        bucket = agrupados.get(grupo.id_grupo)
        if bucket is None:
            agrupados[grupo.id_grupo] = (grupo, [item])
        else:
            bucket[1].append(item)

    # Monta os receituários em ordem de severidade.
    resultado: list[Receituario] = []
    for grupo, itens_grupo in sorted(
        agrupados.values(), key=lambda g: g[0].severidade
    ):
        resultado.append(
            Receituario(
                tipo=grupo.tipo_receituario,
                grupo_id=grupo.id_grupo,
                grupo_nome=grupo.nome,
                prescricao_id=prescricao_id,
                protocolo_prescricao=protocolo,
                itens=itens_grupo,
                assinatura_minima=grupo.assinatura_minima,
                vias=grupo.vias,
                retencao_farmacia=grupo.retencao_farmacia,
                requer_sncr=grupo.requer_sncr,
                severidade=grupo.severidade,
                numeracao_sncr=None,
                status="gerado",
            )
        )
    return resultado


# ---------------------------------------------------------------------------
# Validação de assinatura
# ---------------------------------------------------------------------------

@dataclass
class ResultadoValidacao:
    """Resultado da confrontação entre o nível de assinatura presente na
    prescrição e o nível mínimo exigido pelo grupo regulatório do
    receituário.
    """
    valido: bool
    assinatura_modo: Optional[str]
    nivel_exigido: str
    nivel_presente: str
    motivo_rejeicao: Optional[str] = None


def _nivel_atende(nivel_presente: str, nivel_exigido: str) -> bool:
    """True se o nível presente é igual ou mais forte que o exigido."""
    return _ORDEM_NIVEL[nivel_presente] >= _ORDEM_NIVEL[nivel_exigido]


def validar_assinatura_para_receituario(
    prescricao: dict,
    receituario: Receituario,
) -> ResultadoValidacao:
    """Verifica se a prescrição carrega assinatura forte o suficiente
    para emitir o receituário dado.

    Hierarquia:
      qualificada (ICP-Brasil) > avancada (gov.br) > nenhuma

    A função é **puramente informativa** — não bloqueia nada. O endpoint
    consumidor decide o que fazer com um `valido=False`.

    Requer em `prescricao`: `assinatura_modo` (pode ser None).
    """
    modo = prescricao.get("assinatura_modo")
    nivel_presente = MODO_PARA_NIVEL.get(modo, NIVEL_NENHUMA)
    nivel_exigido = receituario.assinatura_minima

    ok = _nivel_atende(nivel_presente, nivel_exigido)
    motivo: Optional[str] = None
    if not ok:
        motivo = (
            f"Grupo {receituario.grupo_id!r} ({receituario.grupo_nome}) "
            f"exige assinatura {nivel_exigido!r}; "
            f"prescrição tem nível {nivel_presente!r} "
            f"(assinatura_modo={modo!r})."
        )
    return ResultadoValidacao(
        valido=ok,
        assinatura_modo=modo,
        nivel_exigido=nivel_exigido,
        nivel_presente=nivel_presente,
        motivo_rejeicao=motivo,
    )
