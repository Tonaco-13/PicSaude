"""
tuss_base.py
============
Base local TUSS (Tabela Unificada de Procedimentos) para normalização
diagnóstica assistida — Ticket 31.

Fonte de referência: Tabela TUSS ANS (Grupo 4 — Procedimentos Diagnósticos).
Esta é uma base curada local para o MVP. Cobre os exames mais frequentes
na atenção primária e especializada.

⚠️  AVISO MVP — BASE CURADA, NÃO FONTE OFICIAL COMPLETA
---------------------------------------------------------
Esta base é uma seleção curada de 35 procedimentos diagnósticos frequentes.
Não é a tabela TUSS oficial completa da ANS.
Na v2, migrar para:
  - CSV/tabela local com versionamento explícito
  - Expansão progressiva dos registros
  - Mapeamento TUSS ↔ SIGTAP para integração com SUS
Até lá, acréscimos devem ser feitos aqui em _BASE_RAW, com revisão clínica.

ESTRUTURA DE CADA REGISTRO
---------------------------
  codigo_tuss:    código TUSS (str, 8 dígitos)
  nome_padrao:    nome completo padronizado TUSS
  nome_busca:     versão normalizada para lookup (sem acentos, lowercase)
  aliases:        variações comuns aceitas (lista, já normalizadas)
  categoria:      hematologia | bioquimica | imunologia | hormonal | imagem |
                  cardiologia | neurologia | urina_fezes | microbiologia |
                  anatomia_patologica | genetica
  preparo:        instruções básicas de preparo (str | None)
  alertas_base:   alertas que sempre acompanham o exame (lista)

CARREGAMENTO
------------
  Base carregada uma vez em memória no import do módulo (singleton).
  Completamente readonly — sem mutação em runtime.
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Base curada (MVP — ampliar com base real TUSS na v2)
# ---------------------------------------------------------------------------

_BASE_RAW: list[dict] = [
    # ── Hematologia ──────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40301079",
        "nome_padrao": "Hemograma completo com contagem de plaquetas",
        "nome_busca":  "hemograma completo com contagem de plaquetas",
        "aliases":     ["hemograma", "hemograma completo", "hemo completo", "eritrograma leucograma plaquetas"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302264",
        "nome_padrao": "Reticulócitos",
        "nome_busca":  "reticulocitos",
        "aliases":     ["reticulocito", "contagem de reticulocitos"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40306150",
        "nome_padrao": "Velocidade de Hemossedimentação (VHS)",
        "nome_busca":  "velocidade de hemossedimentacao",
        "aliases":     ["vhs", "velocidade hemossedimentacao", "hemossedimentacao"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40306117",
        "nome_padrao": "Coagulograma (TAP + TTPa + Fibrinogênio)",
        "nome_busca":  "coagulograma",
        "aliases":     ["coagulograma completo", "tap ttpa fibrinogenio", "hemostasia"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Bioquímica ───────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40302019",
        "nome_padrao": "Glicose (Glicemia de Jejum)",
        "nome_busca":  "glicose glicemia de jejum",
        "aliases":     ["glicemia", "glicose", "glicemia jejum", "glicemia de jejum", "glicemia em jejum"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum mínimo de 8 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302523",
        "nome_padrao": "Hemoglobina Glicada (HbA1c)",
        "nome_busca":  "hemoglobina glicada",
        "aliases":     ["hba1c", "a1c", "hemoglobina glicada hba1c", "glico hemoglobina"],
        "categoria":   "bioquimica",
        "preparo":     "Sem jejum necessário.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302272",
        "nome_padrao": "Creatinina",
        "nome_busca":  "creatinina",
        "aliases":     ["creatinina serica", "crea"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302434",
        "nome_padrao": "Ureia",
        "nome_busca":  "ureia",
        "aliases":     ["ureia serica", "nitrogenio ureico", "bun"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302280",
        "nome_padrao": "Ácido Úrico",
        "nome_busca":  "acido urico",
        "aliases":     ["acido urico serico", "uricemia"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 4 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302132",
        "nome_padrao": "Aspartato Aminotransferase (TGO/AST)",
        "nome_busca":  "aspartato aminotransferase",
        "aliases":     ["tgo", "ast", "aspartato aminotransferase tgo", "tgo ast"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302140",
        "nome_padrao": "Alanina Aminotransferase (TGP/ALT)",
        "nome_busca":  "alanina aminotransferase",
        "aliases":     ["tgp", "alt", "alanina aminotransferase tgp", "tgp alt"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302027",
        "nome_padrao": "Colesterol Total",
        "nome_busca":  "colesterol total",
        "aliases":     ["colesterol", "col total", "ct"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302035",
        "nome_padrao": "HDL Colesterol",
        "nome_busca":  "hdl colesterol",
        "aliases":     ["hdl", "colesterol hdl", "hdl-c"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302043",
        "nome_padrao": "LDL Colesterol",
        "nome_busca":  "ldl colesterol",
        "aliases":     ["ldl", "colesterol ldl", "ldl-c"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302485",
        "nome_padrao": "Triglicerídeos",
        "nome_busca":  "triglicerides",
        "aliases":     ["triglicerideos", "tg", "trig", "triglicerides"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302450",
        "nome_padrao": "Sódio",
        "nome_busca":  "sodio",
        "aliases":     ["sodio serico", "natremia"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302388",
        "nome_padrao": "Potássio",
        "nome_busca":  "potassio",
        "aliases":     ["potassio serico", "caliemia", "k+"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Imunologia / Proteína C Reativa ──────────────────────────────────────
    {
        "codigo_tuss": "40308030",
        "nome_padrao": "Proteína C Reativa (PCR)",
        "nome_busca":  "proteina c reativa",
        "aliases":     ["pcr", "pcr quantitativo", "proteina c reativa quantitativa"],
        "categoria":   "imunologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Hormonal / Tireóide ──────────────────────────────────────────────────
    {
        "codigo_tuss": "40302671",
        "nome_padrao": "TSH (Hormônio Tireoestimulante)",
        "nome_busca":  "tireoestimulante",
        "aliases":     ["tsh", "hormonio tireoestimulante", "tsh ultrassensivel"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302590",
        "nome_padrao": "T4 Livre (Tiroxina Livre)",
        "nome_busca":  "tiroxina livre",
        "aliases":     ["t4l", "t4 livre", "ft4", "tiroxina livre"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302663",
        "nome_padrao": "T3 (Triiodotironina)",
        "nome_busca":  "triiodotironina",
        "aliases":     ["t3", "t3 total", "triiodotironina"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Imagem — Radiografia ─────────────────────────────────────────────────
    {
        "codigo_tuss": "40901060",
        "nome_padrao": "Radiografia do Tórax (2 incidências)",
        "nome_busca":  "radiografia do torax",
        "aliases":     ["rx torax", "radiografia torax", "raio x torax", "rx de torax", "radiografia do torax pa e perfil"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos da região torácica.",
        "alertas_base": [],
    },
    # ── Imagem — Ultrassonografia ─────────────────────────────────────────────
    {
        "codigo_tuss": "40801019",
        "nome_padrao": "Ultrassonografia do Abdome Total",
        "nome_busca":  "ultrassonografia do abdome total",
        "aliases":     ["us abd", "usg abdome", "ultrassonografia abdome", "eco abdome", "us abdome total",
                        "ultrassonografia abdome total", "usg de abdome total", "us de abdome"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 horas. Bexiga cheia (ingerir 1 litro de água 1 hora antes sem urinar).",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40801027",
        "nome_padrao": "Ultrassonografia do Abdome Superior",
        "nome_busca":  "ultrassonografia do abdome superior",
        "aliases":     ["us abdome superior", "usg abdome superior", "ultrassonografia hepatica"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 a 6 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40901337",
        "nome_padrao": "Ultrassonografia Obstétrica (Morfológica)",
        "nome_busca":  "ultrassonografia obstetrica",
        "aliases":     ["us obstetrico", "usg obstetrica", "morfologico", "eco obstetrico", "ultrassonografia morfologica"],
        "categoria":   "imagem",
        "preparo":     "Bexiga cheia no 1º trimestre. Sem preparo especial no 2º e 3º trimestres.",
        "alertas_base": [],
    },
    # ── Cardiologia ──────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40311012",
        "nome_padrao": "Eletrocardiograma (ECG)",
        "nome_busca":  "eletrocardiograma",
        "aliases":     ["ecg", "ekg", "eletrocardiograma em repouso", "eletro"],
        "categoria":   "cardiologia",
        "preparo":     "Sem preparo especial. Não realizar exercícios imediatamente antes.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40801124",
        "nome_padrao": "Ecocardiograma Transtorácico",
        "nome_busca":  "ecocardiograma transtorácico",
        "aliases":     ["eco cardiaco", "ecocardiograma", "ecott", "eco tt", "ecocardiograma transtorácico"],
        "categoria":   "cardiologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40311071",
        "nome_padrao": "Holter 24 Horas",
        "nome_busca":  "holter 24 horas",
        "aliases":     ["holter", "monitoramento holter", "eletrocardiograma holter"],
        "categoria":   "cardiologia",
        "preparo":     "Manter atividades normais. Não banhar durante o exame. Trazer anotações de sintomas.",
        "alertas_base": [],
    },
    # ── Tomografia Computadorizada ────────────────────────────────────────────
    {
        "codigo_tuss": "40403090",
        "nome_padrao": "Tomografia Computadorizada do Crânio",
        "nome_busca":  "tomografia computadorizada do cranio",
        "aliases":     ["tc cranio", "tc de cranio", "tomografia cranio", "tc cabeca", "tac de cranio"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos. Informar uso de contraste com médico.",
        "alertas_base": ["Verificar indicação de contraste com o médico solicitante."],
    },
    {
        "codigo_tuss": "40403082",
        "nome_padrao": "Tomografia Computadorizada do Tórax",
        "nome_busca":  "tomografia computadorizada do torax",
        "aliases":     ["tc torax", "tc de torax", "tomografia torax"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos. Informar uso de contraste com médico.",
        "alertas_base": ["Verificar indicação de contraste com o médico solicitante."],
    },
    {
        "codigo_tuss": "40403104",
        "nome_padrao": "Tomografia Computadorizada do Abdome",
        "nome_busca":  "tomografia computadorizada do abdome",
        "aliases":     ["tc abdome", "tc de abdome", "tomografia abdome", "tac de abdome"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 horas. Uso de contraste oral pode ser necessário — verificar com médico.",
        "alertas_base": ["Verificar indicação de contraste e preparo oral com o médico solicitante."],
    },
    # ── Ressonância Magnética ─────────────────────────────────────────────────
    {
        "codigo_tuss": "40601078",
        "nome_padrao": "Ressonância Magnética do Crânio",
        "nome_busca":  "ressonancia magnetica do cranio",
        "aliases":     ["rm cranio", "rm de cranio", "ressonancia cranio", "rmn cranio"],
        "categoria":   "imagem",
        "preparo":     "Remover objetos metálicos. Informar implantes, marca-passo ou clipes metálicos.",
        "alertas_base": ["Verificar contraindicação a campos magnéticos (marca-passo, implantes metálicos)."],
    },
    {
        "codigo_tuss": "40601086",
        "nome_padrao": "Ressonância Magnética da Coluna Lombossacra",
        "nome_busca":  "ressonancia magnetica da coluna lombossacra",
        "aliases":     ["rm lombar", "rm de lombar", "ressonancia lombar", "rm coluna lombar", "rmn lombar"],
        "categoria":   "imagem",
        "preparo":     "Remover objetos metálicos. Informar implantes ou cirurgias prévias na coluna.",
        "alertas_base": ["Verificar contraindicação a campos magnéticos (marca-passo, implantes metálicos)."],
    },
    # ── Neurologia ───────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40311020",
        "nome_padrao": "Eletroencefalograma (EEG)",
        "nome_busca":  "eletroencefalograma",
        "aliases":     ["eeg", "eletroencefalografia"],
        "categoria":   "neurologia",
        "preparo":     "Lavar o cabelo sem produtos (gel, creme). Não ingerir cafeína nas 8h anteriores.",
        "alertas_base": [],
    },
    # ── Urina / Fezes ────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40201030",
        "nome_padrao": "Urina Tipo I (EAS — Elementos Anormais e Sedimento)",
        "nome_busca":  "urina tipo i",
        "aliases":     ["eas", "urina i", "urina tipo 1", "exame de urina", "urina rotina", "sumario de urina"],
        "categoria":   "urina_fezes",
        "preparo":     "Coletar jato médio da primeira urina da manhã em frasco estéril.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40205128",
        "nome_padrao": "Exame Parasitológico de Fezes",
        "nome_busca":  "parasitologico de fezes",
        "aliases":     ["parasitologico", "coprológico", "fezes parasitologico", "exame de fezes"],
        "categoria":   "urina_fezes",
        "preparo":     "Coletar em 3 dias alternados em frascos fornecidos pelo laboratório.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40205020",
        "nome_padrao": "Coprocultura com Antibiograma",
        "nome_busca":  "coprocultura",
        "aliases":     ["cultura de fezes", "coprocultura com antibiograma"],
        "categoria":   "microbiologia",
        "preparo":     "Coletar em frasco estéril sem contato com água ou vaso sanitário.",
        "alertas_base": [],
    },
    # ── Microbiologia ─────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40201048",
        "nome_padrao": "Urocultura com Antibiograma",
        "nome_busca":  "urocultura",
        "aliases":     ["cultura de urina", "urocultura com antibiograma", "urinocultura"],
        "categoria":   "microbiologia",
        "preparo":     "Coletar jato médio da primeira urina da manhã em frasco estéril.",
        "alertas_base": [],
    },
]


# ---------------------------------------------------------------------------
# Índices para lookup eficiente
# ---------------------------------------------------------------------------

class _BaseTUSS:
    def __init__(self, registros: list[dict]) -> None:
        self._registros = registros
        # Índice por nome_busca
        self._por_nome: dict[str, dict] = {r["nome_busca"]: r for r in registros}
        # Índice por alias
        self._por_alias: dict[str, dict] = {}
        for r in registros:
            for alias in r["aliases"]:
                self._por_alias[alias] = r
        # Lista de nomes para fuzzy
        self._nomes_fuzzy: list[str] = list(self._por_nome.keys()) + list(self._por_alias.keys())

    def buscar_exato(self, nome_normalizado: str) -> Optional[dict]:
        return self._por_nome.get(nome_normalizado) or self._por_alias.get(nome_normalizado)

    def buscar_fuzzy(
        self,
        nome_normalizado: str,
        threshold: float = 0.88,   # 2026-05-25 JULES-AUDIT — subido de 0.80
                                    # apos bug WRatio "rx" -> 40901060
                                    # (Radiografia Torax) score=0.90.
                                    # Mesmo padrao c548be5.
    ) -> tuple[Optional[dict], float]:
        """
        Retorna (registro, score) ou (None, 0.0) se abaixo do threshold.
        """
        try:
            from rapidfuzz import fuzz, process as rfprocess
        except ImportError:
            return None, 0.0

        result = rfprocess.extractOne(
            nome_normalizado,
            self._nomes_fuzzy,
            scorer=fuzz.WRatio,
        )
        if not result:
            return None, 0.0

        melhor_nome, score_raw, _ = result
        score = score_raw / 100.0

        if score < threshold:
            return None, score

        registro = self._por_nome.get(melhor_nome) or self._por_alias.get(melhor_nome)
        return registro, score

    @property
    def total(self) -> int:
        return len(self._registros)

    @property
    def versao(self) -> str:
        return "tuss_local_v1"


# Singleton — carregado uma vez no import
BASE_TUSS = _BaseTUSS(_BASE_RAW)
