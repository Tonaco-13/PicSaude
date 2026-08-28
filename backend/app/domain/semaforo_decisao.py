"""
semaforo_decisao.py — motor do semáforo de apoio à decisão (VALIDADOR).
=====================================================================

Confere a ESCOLHA do prescritor (fármaco) contra a INDICAÇÃO (CID) e devolve um
sinal discreto e NÃO-BLOQUEANTE:

    🟢 verde    — fármaco é tratamento reconhecido para o CID (consta no PCDT)
    🟡 amarelo  — sem base para afirmar (CID sem PCDT, ou fármaco não-listado)
    🔴 vermelho — contraindicação/perigo real  (FASE 2 — ainda não nesta v1)

PRINCÍPIOS (ver docs/ARQUITETURA_DECISAO_CLINICA.md)
---------------------------------------------------
- DETERMINÍSTICO, baseado em lookup. SEM LLM, SEM ML. "Por que este sinal?" tem
  resposta exata e rastreável à fonte (o PCDT).
- O sistema VALIDA e SINALIZA — nunca recomenda fármaco, nunca bloqueia.
- A inteligência mora no DADO CURADO (regras do PCDT), não no algoritmo.
- Anti-fadiga-de-alerta: incerteza → 🟡 (honesto). 🔴 reservado a perigo real.

A v1 acende 🟢/🟡. O 🔴 (contraindicações) é a Fase 2.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

SINAL_VERDE = "verde"
SINAL_AMARELO = "amarelo"
SINAL_VERMELHO = "vermelho"   # reservado — Fase 2
SINAL_NEUTRO = "neutro"       # sem julgamento — o semáforo se cala (sem ponto na UI)

# Causa da decisão — código ESTÁVEL e legível por máquina (não-prosa). Distingue,
# em especial, os DOIS neutros (entrada incompleta vs. condição não-exaustiva) sem
# depender de texto livre. Útil à UI, aos testes e à futura trilha de auditoria.
CAUSA_VERDE = "consta_lista_exaustiva"          # 🟢 (cid, ativo) na lista validada
CAUSA_AMARELO = "ausente_lista_exaustiva"       # 🟡 condição exaustiva, ativo fora
CAUSA_ENTRADA_INCOMPLETA = "entrada_incompleta"  # neutro: falta CID ou fármaco
CAUSA_NAO_EXAUSTIVA = "condicao_nao_exaustiva"   # neutro: lei da exaustividade


@dataclass(frozen=True)
class Proveniencia:
    """De onde veio a regra que produziu o sinal — a 'cadeia de custódia' da
    decisão. Toda regra 🟢/🟡 carrega a condição, a base curada, quem assinou e
    a versão. É o que torna o sinal auditável e reproduzível."""
    condicao: str             # condicao_nome (ex.: "Hipertensão arterial")
    fonte: str                # base curada (ex.: "RENAME 2024 + Diretrizes...")
    validado_por: str         # responsável clínico que assinou a curadoria
    versao: str               # versão da lista curada


def _significado_do_sinal(sinal: str) -> str:
    """Texto anti-overclaim, sinal a sinal. Blinda a ficha (camada 2) contra a
    leitura 'errado/perigoso' — sem depender do dossiê (camada 1). Espelha
    docs/EXPLICABILIDADE_DECISAO_CLINICA.md (validador, não recomendador)."""
    if sinal == SINAL_VERDE:
        return ("🟢 Coerente: o fármaco consta na lista validada para esta "
                "condição. Confirme dose, via e contraindicações.")
    if sinal == SINAL_AMARELO:
        return ("🟡 Atenção: o fármaco NÃO consta na lista validada desta "
                "condição — confira. NÃO significa errado, perigoso ou "
                "proibido; só que requer conferência clínica.")
    return ("Sem avaliação: o motor não julgou esta combinação (entrada "
            "incompleta ou condição sem lista validada). Ausência de sinal "
            "não é aprovação nem reprovação.")


@dataclass(frozen=True)
class Avaliacao:
    sinal: str                # verde | amarelo | vermelho | neutro
    motivo: str               # explicação curta e legível
    fonte: Optional[str]      # condição (ex.: "Hipertensão arterial") ou None
    # --- ficha de explicabilidade (camada 2) -------------------------------
    # Campos opcionais: defaults preservam compatibilidade com chamadas antigas.
    cid_recebido: Optional[str] = None    # CID CRU recebido (antes de normalizar)
    ativo_recebido: Optional[str] = None  # fármaco CRU recebido (antes de normalizar)
    cid_avaliado: Optional[str] = None    # CID canônico (ex.: "I10.0")
    cid_casado: Optional[str] = None      # CID da cadeia que casou a regra ("I10")
    ativo_canonico: Optional[str] = None  # princípio ativo sem sal/acento/caixa
    exaustiva: Optional[bool] = None      # a condição tem lista 🟢 COMPLETA?
                                          #   None = não apurado (entrada incompleta)
    causa: Optional[str] = None           # código ESTÁVEL da decisão (CAUSA_*)
    regra: Optional[str] = None           # qual regra disparou (legível)
    proveniencia: Optional[Proveniencia] = None

    def to_ficha(self) -> dict:
        """Ficha de explicabilidade — tudo que justifica o sinal, num dicionário
        serializável. O endpoint devolve isto; a UI mostra no 'por quê?'.

        Garantia: a ficha é AUTOSSUFICIENTE — quem a lê reconstrói a decisão sem
        olhar o código (entrada bruta + normalizada + regra + proveniência)."""
        p = self.proveniencia
        return {
            "sinal": self.sinal,
            "motivo": self.motivo,
            "fonte": self.fonte,
            "explicabilidade": {
                "entrada": {
                    "cid_recebido": self.cid_recebido,
                    "cid": self.cid_avaliado,
                    "cid_casado": self.cid_casado,
                    "principio_ativo_recebido": self.ativo_recebido,
                    "principio_ativo_canonico": self.ativo_canonico,
                },
                "causa": self.causa,
                "condicao_exaustiva": self.exaustiva,
                "regra": self.regra,
                "significado": _significado_do_sinal(self.sinal),
                "proveniencia": (
                    {
                        "condicao": p.condicao,
                        "fonte": p.fonte,
                        "validado_por": p.validado_por,
                        "versao": p.versao,
                    }
                    if p
                    else None
                ),
                "determinismo": (
                    "Resultado determinístico (busca em lista curada, sem IA "
                    "generativa). Mesma entrada + mesma versão de curadoria → "
                    "sempre o mesmo sinal."
                ),
                "nao_bloqueante": (
                    "Sinal de apoio à decisão. Não bloqueia nem altera a "
                    "prescrição — o prescritor é o responsável final."
                ),
            },
        }


# ---------------------------------------------------------------------------
# Canonicalização do princípio ativo (remove sal/acento/caixa)
# ---------------------------------------------------------------------------

# Prefixos de sal "X de <ativo>" (a parte antes do ativo). Conservador.
_SAIS_PREFIXO = (
    "cloridrato de", "bromidrato de", "oxalato de", "sulfato de", "fosfato de",
    "maleato de", "besilato de", "mesilato de", "succinato de", "tartarato de",
    "acetato de", "nitrato de", "citrato de", "fumarato de", "hemifumarato de",
    "pamoato de", "lactato de", "gluconato de", "carbonato de", "valerato de",
    "dipropionato de", "estearato de", "propionato de", "dicloridrato de",
)
# Sufixos de sal (adjetivos após o ativo).
_SAIS_SUFIXO = (
    "sodico", "potassico", "potassica", "calcico", "calcica", "magnesico",
    "de sodio", "de potassio", "de calcio", "dihidratado", "monoidratado",
    "anidro", "trihidratado",
)

# TICKET-CANON-ATIVO-DOSE-SUFFIX — strip de dose ("Losartana 50mg" → "losartana").
# Sem isso, o lookup exato por dict-key perde a chave e vira amarelo falso
# (ver docs/tickets/TICKET-CANON-ATIVO-DOSE-SUFFIX.md).
_DOSE_RE = re.compile(
    r"\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ui|ufc|mmol|meq"
    r"|miligrama[s]?|micrograma[s]?|grama[s]?|unidade[s]?\s+internacional(?:is|es)?)\b",
    flags=re.IGNORECASE,
)


def _strip_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canon_ativo(nome: str) -> str:
    """Chave canônica do princípio ativo (sem sal/dose/acento/caixa/espaço extra).

    "Oxalato de Escitalopram"    → "escitalopram"
    "Losartana Potássica"        → "losartana"
    "Losartana 50mg"             → "losartana"
    "Losartana Potássica 50mg"   → "losartana"

    A dose é removida ANTES do sal (não depois, como no rascunho original do
    ticket): "losartana potassica 50mg" só bate o sufixo " potassica" se a
    dose que o segue já tiver saído — senão a string termina em "50mg", não
    em "potassica", e o strip de sal nunca dispara.
    """
    s = _strip_acentos((nome or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    s = _DOSE_RE.sub("", s).strip()
    for pref in _SAIS_PREFIXO:
        if s.startswith(pref + " "):
            s = s[len(pref) + 1:]
            break
    for suf in _SAIS_SUFIXO:
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)]
            break
    return s.strip()


# ---------------------------------------------------------------------------
# Canonicalização e hierarquia do CID-10
# ---------------------------------------------------------------------------

def canon_cid(codigo: str) -> str:
    """Normaliza o código CID (maiúsculo, sem espaço). 'i10.0' → 'I10.0'."""
    return re.sub(r"\s+", "", (codigo or "").upper())


def cadeia_cid(codigo: str) -> list[str]:
    """Cadeia do mais específico ao mais amplo, para casar regra indexada num
    CID mais geral. 'I10.0' → ['I10.0', 'I10'].

    (Blocos DATASUS, ex.: I10-I15, ficam para uma versão futura — aqui usamos a
    derivação por categoria, suficiente para a v1.)
    """
    c = canon_cid(codigo)
    cadeia = [c]
    if "." in c:
        categoria = c.split(".", 1)[0]
        if categoria and categoria != c:
            cadeia.append(categoria)
    return cadeia


# ---------------------------------------------------------------------------
# Avaliação (a decisão — cadeia de regras por prioridade)
# ---------------------------------------------------------------------------

def avaliar_semaforo(
    codigo_cid: Optional[str],
    principio_ativo: Optional[str],
    aprovados: dict[tuple[str, str], "Proveniencia"],
    cids_exaustivos: set[str],
    cond_prov: Optional[dict[str, "Proveniencia"]] = None,
) -> Avaliacao:
    """Avalia a coerência fármaco ↔ CID e devolve o sinal.

    LEI DA EXAUSTIVIDADE (decisão Fabiano 2026-06-21): o semáforo só JULGA uma
    condição cuja lista 🟢 é EXAUSTIVA em relação ao PCDT. Numa condição não
    exaustiva, o sinal seria viés — então o semáforo se CALA (neutro). Assim ele
    é autoritativo quando fala e honesto quando se cala.

    Parâmetros
    ----------
    aprovados        : índice {(cid_canônico, ativo_canônico): fonte} — regras 🟢
                       curadas/assinadas (do PCDT).
    cids_exaustivos  : CIDs (canônicos) cuja curadoria é COMPLETA. Só nesses a
                       ausência de um fármaco tem significado (🟡).

    Regras (Fase 1 — sem 🔴):
      1. (CID, ativo) aprovado            → 🟢
      2. CID exaustivo, ativo não consta  → 🟡 (fora do protocolo — confira)
      3. caso contrário (não exaustivo)   → neutro (sem julgamento, sem ponto)
    """
    cond_prov = cond_prov or {}

    # Canonizar ANTES do guard: assim "" / None / "   " (só-espaço) / um CID que
    # colapsa para vazio caem TODOS em "entrada incompleta" (neutro honesto), e
    # nunca num 🟡 com fármaco fantasma. O guard testa o valor CANÔNICO, não o cru.
    cid_k0 = canon_cid(codigo_cid or "")
    ativo_k = canon_ativo(principio_ativo or "")

    if not cid_k0 or not ativo_k:
        return Avaliacao(
            SINAL_NEUTRO, "indicação ou fármaco ausente", None,
            cid_recebido=codigo_cid, ativo_recebido=principio_ativo,
            cid_avaliado=cid_k0 or None, ativo_canonico=ativo_k or None,
            exaustiva=None,   # nada foi apurado — não afirmar exaustividade
            causa=CAUSA_ENTRADA_INCOMPLETA,
            regra="entrada incompleta → semáforo não julga (neutro)",
        )

    cadeia = cadeia_cid(cid_k0)

    # PORTÃO DA EXAUSTIVIDADE (primeiro!). Se a condição não tem lista COMPLETA,
    # o semáforo não julga NADA — nem 🟢. Mostrar 🟢 só para os fármacos que
    # curamos privilegiaria-os sobre os válidos que faltam (o viés que Fabiano
    # apontou). Então: condição não-exaustiva → neutro (silêncio).
    cid_exaustivo = next((c for c in cadeia if c in cids_exaustivos), None)
    if cid_exaustivo is None:
        return Avaliacao(
            SINAL_NEUTRO, "sem curadoria exaustiva para esta condição", None,
            cid_recebido=codigo_cid, ativo_recebido=principio_ativo,
            cid_avaliado=cid_k0, ativo_canonico=ativo_k, exaustiva=False,
            causa=CAUSA_NAO_EXAUSTIVA,
            regra=(
                "condição sem lista exaustiva curada → semáforo não julga "
                "(neutro, lei da exaustividade)"
            ),
        )

    # Condição EXAUSTIVA → o semáforo pode julgar.
    # 1) Aprovado (🟢) — busca subindo a hierarquia do CID.
    for cid_k in cadeia:
        prov = aprovados.get((cid_k, ativo_k))
        if prov:
            return Avaliacao(
                SINAL_VERDE, "tratamento reconhecido para a condição", prov.condicao,
                cid_recebido=codigo_cid, ativo_recebido=principio_ativo,
                cid_avaliado=cid_k0, cid_casado=cid_k, ativo_canonico=ativo_k,
                exaustiva=True, causa=CAUSA_VERDE, proveniencia=prov,
                regra=(
                    f"({cid_k}, {ativo_k}) consta na lista exaustiva validada "
                    f"da condição"
                ),
            )

    # 2) Fármaco fora da lista completa do protocolo → 🟡 (informação honesta).
    prov = cond_prov.get(cid_exaustivo)
    return Avaliacao(
        SINAL_AMARELO,
        "fármaco fora do protocolo desta condição — confira",
        prov.condicao if prov else None,
        cid_recebido=codigo_cid, ativo_recebido=principio_ativo,
        cid_avaliado=cid_k0, cid_casado=cid_exaustivo, ativo_canonico=ativo_k,
        exaustiva=True, causa=CAUSA_AMARELO, proveniencia=prov,
        regra=(
            f"{cid_exaustivo} tem lista exaustiva e {ativo_k} NÃO consta nela "
            f"→ fora do protocolo (confira)"
        ),
    )


# ---------------------------------------------------------------------------
# Carregamento das regras curadas (só serve o que está `validado`)
# ---------------------------------------------------------------------------

import csv as _csv          # noqa: E402  (import local ao bloco de loading)
import os as _os            # noqa: E402

_STATUS_VALIDADO = "validado"


def _resolver_csv() -> str:
    """Caminho do CSV curado. Env `PICSAUDE_SEMAFORO_CSV` tem prioridade
    (empacotamento Docker); senão, layout de dev (data/ na raiz do repo)."""
    override = _os.getenv("PICSAUDE_SEMAFORO_CSV")
    if override:
        return override
    return _os.path.normpath(
        _os.path.join(
            _os.path.dirname(__file__), "..", "..", "..",
            "data", "decisao_semaforo.csv",
        )
    )


_VALORES_VERDADE = ("true", "sim", "1", "verdadeiro")


def carregar_regras(
    caminho: str,
) -> tuple[dict[tuple[str, str], Proveniencia], set[str], dict[str, Proveniencia]]:
    """Lê o CSV curado → (aprovados, cids_exaustivos, cond_prov).

    INVARIANTES:
    - só entram regras com `status_curadoria == 'validado'` (linha vermelha);
    - `cids_exaustivos` = CIDs marcados `exaustivo` (lista 🟢 COMPLETA). Só nesses
      o semáforo julga a ausência (🟡); senão se cala (lei da exaustividade).

    Estruturas:
    - `aprovados[(cid, ativo)] = Proveniencia` — regra 🟢 e sua proveniência;
    - `cond_prov[cid] = Proveniencia` — proveniência no nível da CONDIÇÃO (todas
      as linhas de um CID partilham condição/fonte/validado_por/versão). Serve ao
      🟡, em que não há fármaco aprovado mas a condição tem proveniência.
    """
    aprovados: dict[tuple[str, str], Proveniencia] = {}
    cids_exaustivos: set[str] = set()
    cond_prov: dict[str, Proveniencia] = {}
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                if (row.get("status_curadoria") or "").strip() != _STATUS_VALIDADO:
                    continue
                cid_k = canon_cid(row.get("codigo_cid") or "")
                ativo_k = canon_ativo(row.get("principio_ativo") or "")
                if not cid_k or not ativo_k:
                    continue
                prov = Proveniencia(
                    condicao=(row.get("condicao_nome") or "").strip() or cid_k,
                    fonte=(row.get("fonte") or "").strip(),
                    validado_por=(row.get("validado_por") or "").strip(),
                    versao=(row.get("versao") or "").strip(),
                )
                aprovados[(cid_k, ativo_k)] = prov
                cond_prov[cid_k] = prov
                if (row.get("exaustivo") or "").strip().lower() in _VALORES_VERDADE:
                    cids_exaustivos.add(cid_k)
    except FileNotFoundError:
        pass   # sem CSV → sem regras → tudo neutro (degrada seguro)
    return aprovados, cids_exaustivos, cond_prov


_REGRAS_CACHE: Optional[tuple[dict, set, dict]] = None


def _regras() -> tuple[dict, set, dict]:
    global _REGRAS_CACHE
    if _REGRAS_CACHE is None:
        _REGRAS_CACHE = carregar_regras(_resolver_csv())
    return _REGRAS_CACHE


def avaliar(codigo_cid: Optional[str], principio_ativo: Optional[str]) -> Avaliacao:
    """Avalia usando as regras curadas carregadas (cacheadas)."""
    aprovados, cids, cond_prov = _regras()
    return avaliar_semaforo(codigo_cid, principio_ativo, aprovados, cids, cond_prov)


def total_regras() -> int:
    """Número de regras 🟢 validadas carregadas (para health/diagnóstico)."""
    return len(_regras()[0])
