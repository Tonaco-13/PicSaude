"""
tuss_base.py
============
Base local de exames para normalização diagnóstica assistida — Ticket 31,
v2 em TICKET-FILA-7-SIGTAP-EXAMES.md (fila 7, 29/08/2026).

FONTE: SIGTAP OFICIAL + CURADORIA TUSS SOBREPOSTA (legenda MVP corrigida)
----------------------------------------------------------------------------
A base era uma seleção curada de 35 procedimentos (`_BASE_RAW`) — o
`⚠️ AVISO MVP` original prometia uma v2 com "CSV/tabela local com
versionamento explícito"; é esta. A FONTE de códigos/nomes passa a ser
`data/sigtap_exames.csv` (Tabela Unificada do DATASUS, grupo "Procedimentos
com finalidade diagnóstica", ~1.100 procedimentos — gerado offline pelo
script de import em `backend/scripts/`, nunca chamado por este módulo). A
curadoria de 35 itens SOBREVIVE por cima, intocada: aliases clínicos,
preparo do paciente e alertas que o CSV oficial não carrega.

TUSS (ANS) e SIGTAP (DATASUS/SUS) são sistemas de codificação DIFERENTES,
sem chave de código em comum publicada de forma simples (o `rl_procedimento
_tuss.txt` do próprio dump SIGTAP está vazio nesta competência — ver
MANIFEST.md). Ao contrário do CID-10 (join por código, mesmo sistema nos
dois lados — `base_cid.py`), o join aqui é por NOME NORMALIZADO: quando o
`nome_busca` de uma entrada curada bate com o de uma linha SIGTAP, os dois
se fundem — o registro fica com `codigo_tuss` (da curadoria) E
`codigo_sigtap` (do CSV) juntos. Sem bater, os dois catálogos coexistem
lado a lado: a curadoria sozinha (só `codigo_tuss`) e o SIGTAP sozinho (só
`codigo_sigtap`, sem aliases/preparo/alertas — ninguém curou aquele ainda).
Nenhum código sai da base por não ter par — a régua do catálogo suave
(desconhecido ≠ inválido, a mesma lição do CID) vale aqui igual.

ESTRUTURA DE CADA REGISTRO
---------------------------
  codigo_tuss:    código TUSS/ANS (str | None) — só nas entradas curadas
  codigo_sigtap:  código SIGTAP/DATASUS (str | None) — 10 dígitos
                  GGSSFFPPP-D (grupo·subgrupo·forma·sequencial·dígito)
  nome_padrao:    nome completo padronizado (curado, ou oficial SIGTAP)
  nome_busca:     versão normalizada para lookup (sem acentos, lowercase) —
                  mesma função de `app/ai/normalizacao_exame.py` usada no
                  lookup do usuário, para o join por nome ser consistente
  aliases:        variações comuns aceitas (lista, já normalizadas) —
                  vazio nas entradas só-SIGTAP, sem curadoria ainda
  categoria:      vocabulário interno curado (hematologia | bioquimica |
                  ...) — None nas entradas só-SIGTAP (usam `subgrupo` do
                  SIGTAP como classificação, não a taxonomia interna)
  subgrupo:       subgrupo SIGTAP (str | None) — só nas entradas SIGTAP
  preparo:        instruções básicas de preparo (str | None) — curado
  alertas_base:   alertas que sempre acompanham o exame (lista) — curado
  fonte:          proveniência LEGÍVEL POR LINHA (nunca mente — mesma
                  disciplina do CID/RDC/CBO): "TUSS/BASE_LOCAL" (só
                  curado), "SIGTAP/DATASUS {competência}" (só SIGTAP), ou
                  os dois concatenados quando o registro é fusão dos dois

CARREGAMENTO
------------
  Base carregada uma vez em memória no import do módulo (singleton).
  Completamente readonly — sem mutação em runtime. Se `sigtap_exames.csv`
  não existir (empacotamento sem o arquivo), degrada graciosamente para só
  a curadoria — nunca quebra (mesmo padrão de `base_cid.py`).
"""

from __future__ import annotations

import csv
import os
from typing import Optional

from app.ai.normalizacao_exame import normalizar_nome_exame


# ---------------------------------------------------------------------------
# Base curada (MVP — ampliar com base real TUSS na v2)
# ---------------------------------------------------------------------------

_BASE_RAW: list[dict] = [
    # ── Hematologia ──────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40304361",
        "termo_oficial": "Hemograma com contagem de plaquetas ou frações (eritrograma, leucograma, plaquetas)",
        "nome_padrao": "Hemograma completo com contagem de plaquetas",
        "nome_busca":  "hemograma completo com contagem de plaquetas",
        "aliases":     ["hemograma", "hemograma completo", "hemo completo", "eritrograma leucograma plaquetas"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40304558",
        "termo_oficial": "Reticulócitos, contagem",
        "nome_padrao": "Reticulócitos",
        "nome_busca":  "reticulocitos",
        "aliases":     ["reticulocito", "contagem de reticulocitos"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40304370",
        "termo_oficial": "Hemossedimentação, (VHS) - pesquisa e/ou dosagem",
        "nome_padrao": "Velocidade de Hemossedimentação (VHS)",
        "nome_busca":  "velocidade de hemossedimentacao",
        "aliases":     ["vhs", "velocidade hemossedimentacao", "hemossedimentacao"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40304922",
        "termo_oficial": "Coagulograma (TS, TC, prova do laço, retração do coágulo, contagem de plaquetas, tempo de protombina, tempo de tromboplastina, parcial ativado) - pesquisa e/ou dosagem",
        "nome_padrao": "Coagulograma (TAP + TTPa + Fibrinogênio)",
        "nome_busca":  "coagulograma",
        "aliases":     ["coagulograma completo", "tap ttpa fibrinogenio", "hemostasia"],
        "categoria":   "hematologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [
            "O coagulograma oficial (TUSS 40304922) cobre TS, TC, prova do laço, retração do coágulo, plaquetas, TAP e TTPa — NÃO inclui fibrinogênio, que é item próprio (TUSS 40304264) e fatura à parte.",
        ],
    },
    # ── Bioquímica ───────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40302040",
        "termo_oficial": "Glicose - pesquisa e/ou dosagem",
        "nome_padrao": "Glicose (Glicemia de Jejum)",
        "nome_busca":  "glicose glicemia de jejum",
        "aliases":     ["glicemia", "glicose", "glicemia jejum", "glicemia de jejum", "glicemia em jejum"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum mínimo de 8 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302075",
        "termo_oficial": "Hemoglobina glicada (A1 total) - pesquisa e/ou dosagem",
        "nome_padrao": "Hemoglobina Glicada (HbA1c)",
        "nome_busca":  "hemoglobina glicada",
        "aliases":     ["hba1c", "a1c", "hemoglobina glicada hba1c", "glico hemoglobina"],
        "categoria":   "bioquimica",
        "preparo":     "Sem jejum necessário.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40301630",
        "termo_oficial": "Creatinina - pesquisa e/ou dosagem",
        "nome_padrao": "Creatinina",
        "nome_busca":  "creatinina",
        "aliases":     ["creatinina serica", "crea"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302580",
        "termo_oficial": "Uréia - pesquisa e/ou dosagem",
        "nome_padrao": "Ureia",
        "nome_busca":  "ureia",
        "aliases":     ["ureia serica", "nitrogenio ureico", "bun"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40301150",
        "termo_oficial": "Ácido úrico - pesquisa e/ou dosagem",
        "nome_padrao": "Ácido Úrico",
        "nome_busca":  "acido urico",
        "aliases":     ["acido urico serico", "uricemia"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 4 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302504",
        "termo_oficial": "Transaminase oxalacética (amino transferase aspartato) - pesquisa e/ou dosagem",
        "nome_padrao": "Aspartato Aminotransferase (TGO/AST)",
        "nome_busca":  "aspartato aminotransferase",
        "aliases":     ["tgo", "ast", "aspartato aminotransferase tgo", "tgo ast"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302512",
        "termo_oficial": "Transaminase pirúvica (amino transferase de alanina) - pesquisa e/ou dosagem",
        "nome_padrao": "Alanina Aminotransferase (TGP/ALT)",
        "nome_busca":  "alanina aminotransferase",
        "aliases":     ["tgp", "alt", "alanina aminotransferase tgp", "tgp alt"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40301605",
        "termo_oficial": "Colesterol total - pesquisa e/ou dosagem",
        "nome_padrao": "Colesterol Total",
        "nome_busca":  "colesterol total",
        "aliases":     ["colesterol", "col total", "ct"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40301583",
        "termo_oficial": "Colesterol (HDL) - pesquisa e/ou dosagem",
        "nome_padrao": "HDL Colesterol",
        "nome_busca":  "hdl colesterol",
        "aliases":     ["hdl", "colesterol hdl", "hdl-c"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40301591",
        "termo_oficial": "Colesterol (LDL) - pesquisa e/ou dosagem",
        "nome_padrao": "LDL Colesterol",
        "nome_busca":  "ldl colesterol",
        "aliases":     ["ldl", "colesterol ldl", "ldl-c"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302547",
        "termo_oficial": "Triglicerídeos - pesquisa e/ou dosagem",
        "nome_padrao": "Triglicerídeos",
        "nome_busca":  "triglicerides",
        "aliases":     ["triglicerideos", "tg", "trig", "triglicerides"],
        "categoria":   "bioquimica",
        "preparo":     "Jejum de 12 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302423",
        "termo_oficial": "Sódio - pesquisa e/ou dosagem",
        "nome_padrao": "Sódio",
        "nome_busca":  "sodio",
        "aliases":     ["sodio serico", "natremia"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40302318",
        "termo_oficial": "Potássio - pesquisa e/ou dosagem",
        "nome_padrao": "Potássio",
        "nome_busca":  "potassio",
        "aliases":     ["potassio serico", "caliemia", "k+"],
        "categoria":   "bioquimica",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Imunologia / Proteína C Reativa ──────────────────────────────────────
    {
        "codigo_tuss": "40308391",
        "termo_oficial": "Proteína C reativa, quantitativa - pesquisa e/ou dosagem",
        "nome_padrao": "Proteína C Reativa (PCR)",
        "nome_busca":  "proteina c reativa",
        "aliases":     ["pcr", "pcr quantitativo", "proteina c reativa quantitativa"],
        "categoria":   "imunologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Hormonal / Tireóide ──────────────────────────────────────────────────
    {
        "codigo_tuss": "40316521",
        "termo_oficial": "Tireoestimulante, hormônio (TSH) - pesquisa e/ou dosagem",
        "nome_padrao": "TSH (Hormônio Tireoestimulante)",
        "nome_busca":  "tireoestimulante",
        "aliases":     ["tsh", "hormonio tireoestimulante", "tsh ultrassensivel"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40316491",
        "termo_oficial": "T4 livre - pesquisa e/ou dosagem",
        "nome_padrao": "T4 Livre (Tiroxina Livre)",
        "nome_busca":  "tiroxina livre",
        "aliases":     ["t4l", "t4 livre", "ft4", "tiroxina livre"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40316556",
        "termo_oficial": "Triiodotironina (T3) - pesquisa e/ou dosagem",
        "nome_padrao": "T3 (Triiodotironina)",
        "nome_busca":  "triiodotironina",
        "aliases":     ["t3", "t3 total", "triiodotironina"],
        "categoria":   "hormonal",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    # ── Imagem — Radiografia ─────────────────────────────────────────────────
    {
        "codigo_tuss": "40805026",
        "termo_oficial": "RX - Tórax - 2 incidências",
        "nome_padrao": "Radiografia do Tórax (2 incidências)",
        "nome_busca":  "radiografia do torax",
        "aliases":     ["rx torax", "radiografia torax", "raio x torax", "rx de torax", "radiografia do torax pa e perfil"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos da região torácica.",
        "alertas_base": [],
    },
    # ── Imagem — Ultrassonografia ─────────────────────────────────────────────
    {
        "codigo_tuss": "40901122",
        "termo_oficial": "US - Abdome total (abdome superior, rins, bexiga, aorta, veia cava inferior e adrenais)",
        "nome_padrao": "Ultrassonografia do Abdome Total",
        "nome_busca":  "ultrassonografia do abdome total",
        "aliases":     ["us abd", "usg abdome", "ultrassonografia abdome", "eco abdome", "us abdome total",
                        "ultrassonografia abdome total", "usg de abdome total", "us de abdome"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 horas. Bexiga cheia (ingerir 1 litro de água 1 hora antes sem urinar).",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40901130",
        "termo_oficial": "US - Abdome superior (fígado, vias biliares, vesícula, pâncreas e baço)",
        "nome_padrao": "Ultrassonografia do Abdome Superior",
        "nome_busca":  "ultrassonografia do abdome superior",
        "aliases":     ["us abdome superior", "usg abdome superior", "ultrassonografia hepatica"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 a 6 horas.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40901262",
        "termo_oficial": "US - Obstétrica morfológica",
        "nome_padrao": "Ultrassonografia Obstétrica (Morfológica)",
        "nome_busca":  "ultrassonografia obstetrica",
        "aliases":     ["us obstetrico", "usg obstetrica", "morfologico", "eco obstetrico", "ultrassonografia morfologica"],
        "categoria":   "imagem",
        "preparo":     "Bexiga cheia no 1º trimestre. Sem preparo especial no 2º e 3º trimestres.",
        "alertas_base": [],
    },
    # ── Cardiologia ──────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40101010",
        "termo_oficial": "ECG convencional de até 12 derivações",
        "nome_padrao": "Eletrocardiograma (ECG)",
        "nome_busca":  "eletrocardiograma",
        "aliases":     ["ecg", "ekg", "eletrocardiograma em repouso", "eletro"],
        "categoria":   "cardiologia",
        "preparo":     "Sem preparo especial. Não realizar exercícios imediatamente antes.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40901106",
        "termo_oficial": "Ecodopplercardiograma transtorácico",
        "nome_padrao": "Ecocardiograma Transtorácico",
        "nome_busca":  "ecocardiograma transtorácico",
        "aliases":     ["eco cardiaco", "ecocardiograma", "ecott", "eco tt", "ecocardiograma transtorácico"],
        "categoria":   "cardiologia",
        "preparo":     "Sem preparo especial.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "20102020",
        "termo_oficial": "Holter de 24 horas - 3 canais - digital",
        "nome_padrao": "Holter 24 Horas",
        "nome_busca":  "holter 24 horas",
        "aliases":     ["holter", "monitoramento holter", "eletrocardiograma holter"],
        "categoria":   "cardiologia",
        "preparo":     "Manter atividades normais. Não banhar durante o exame. Trazer anotações de sintomas.",
        "alertas_base": [],
    },
    # ── Tomografia Computadorizada ────────────────────────────────────────────
    {
        "codigo_tuss": "41001010",
        "termo_oficial": "TC - Crânio ou sela túrcica ou órbitas",
        "nome_padrao": "Tomografia Computadorizada do Crânio",
        "nome_busca":  "tomografia computadorizada do cranio",
        "aliases":     ["tc cranio", "tc de cranio", "tomografia cranio", "tc cabeca", "tac de cranio"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos. Informar uso de contraste com médico.",
        "alertas_base": ["Verificar indicação de contraste com o médico solicitante."],
    },
    {
        "codigo_tuss": "41001079",
        "termo_oficial": "TC - Tórax",
        "nome_padrao": "Tomografia Computadorizada do Tórax",
        "nome_busca":  "tomografia computadorizada do torax",
        "aliases":     ["tc torax", "tc de torax", "tomografia torax"],
        "categoria":   "imagem",
        "preparo":     "Remover adornos metálicos. Informar uso de contraste com médico.",
        "alertas_base": ["Verificar indicação de contraste com o médico solicitante."],
    },
    {
        "codigo_tuss": "41001095",
        "termo_oficial": "TC - Abdome total (abdome superior, pelve e retroperitônio)",
        "nome_padrao": "Tomografia Computadorizada do Abdome",
        "nome_busca":  "tomografia computadorizada do abdome",
        "aliases":     ["tc abdome", "tc de abdome", "tomografia abdome", "tac de abdome"],
        "categoria":   "imagem",
        "preparo":     "Jejum de 4 horas. Uso de contraste oral pode ser necessário — verificar com médico.",
        "alertas_base": ["Verificar indicação de contraste e preparo oral com o médico solicitante."],
    },
    # ── Ressonância Magnética ─────────────────────────────────────────────────
    {
        "codigo_tuss": "41101014",
        "termo_oficial": "RM - Crânio (encéfalo)",
        "nome_padrao": "Ressonância Magnética do Crânio",
        "nome_busca":  "ressonancia magnetica do cranio",
        "aliases":     ["rm cranio", "rm de cranio", "ressonancia cranio", "rmn cranio"],
        "categoria":   "imagem",
        "preparo":     "Remover objetos metálicos. Informar implantes, marca-passo ou clipes metálicos.",
        "alertas_base": ["Verificar contraindicação a campos magnéticos (marca-passo, implantes metálicos)."],
    },
    {
        "codigo_tuss": "41101227",
        "termo_oficial": "RM - Coluna cervical ou dorsal ou lombar",
        "nome_padrao": "Ressonância Magnética da Coluna Lombossacra",
        "nome_busca":  "ressonancia magnetica da coluna lombossacra",
        "aliases":     ["rm lombar", "rm de lombar", "ressonancia lombar", "rm coluna lombar", "rmn lombar"],
        "categoria":   "imagem",
        "preparo":     "Remover objetos metálicos. Informar implantes ou cirurgias prévias na coluna.",
        "alertas_base": ["Verificar contraindicação a campos magnéticos (marca-passo, implantes metálicos)."],
    },
    # ── Neurologia ───────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40103170",
        "termo_oficial": "EEG de rotina",
        "nome_padrao": "Eletroencefalograma (EEG)",
        "nome_busca":  "eletroencefalograma",
        "aliases":     ["eeg", "eletroencefalografia"],
        "categoria":   "neurologia",
        "preparo":     "Lavar o cabelo sem produtos (gel, creme). Não ingerir cafeína nas 8h anteriores.",
        "alertas_base": [],
    },
    # ── Urina / Fezes ────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40311210",
        "termo_oficial": "Rotina de urina (caracteres físicos, elementos anormais e sedimentoscopia)",
        "nome_padrao": "Urina Tipo I (EAS — Elementos Anormais e Sedimento)",
        "nome_busca":  "urina tipo i",
        "aliases":     ["eas", "urina i", "urina tipo 1", "exame de urina", "urina rotina", "sumario de urina"],
        "categoria":   "urina_fezes",
        "preparo":     "Coletar jato médio da primeira urina da manhã em frasco estéril.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40303110",
        "termo_oficial": "Parasitológico - nas fezes",
        "nome_padrao": "Exame Parasitológico de Fezes",
        "nome_busca":  "parasitologico de fezes",
        "aliases":     ["parasitologico", "coprológico", "fezes parasitologico", "exame de fezes"],
        "categoria":   "urina_fezes",
        "preparo":     "Coletar em 3 dias alternados em frascos fornecidos pelo laboratório.",
        "alertas_base": [],
    },
    {
        "codigo_tuss": "40310183",
        "termo_oficial": "Cultura, fezes: salmonella, shigella e escherichia coli enteropatogênicas (sorologia incluída)",
        "nome_padrao": "Coprocultura com Antibiograma",
        "nome_busca":  "coprocultura",
        "aliases":     ["cultura de fezes", "coprocultura com antibiograma"],
        "categoria":   "microbiologia",
        "preparo":     "Coletar em frasco estéril sem contato com água ou vaso sanitário.",
        "alertas_base": [
            "A cultura de fezes oficial (TUSS 40310183) NÃO inclui o antibiograma, que é item próprio (TUSS 40310418) e fatura à parte.",
        ],
    },
    # ── Microbiologia ─────────────────────────────────────────────────────────
    {
        "codigo_tuss": "40310213",
        "termo_oficial": "Cultura, urina com contagem de colônias",
        "nome_padrao": "Urocultura com Antibiograma",
        "nome_busca":  "urocultura",
        "aliases":     ["cultura de urina", "urocultura com antibiograma", "urinocultura"],
        "categoria":   "microbiologia",
        "preparo":     "Coletar jato médio da primeira urina da manhã em frasco estéril.",
        "alertas_base": [
            "A urocultura oficial (TUSS 40310213) é a cultura com contagem de colônias e NÃO inclui o antibiograma, que é item próprio (TUSS 40310418) e fatura à parte.",
        ],
    },
]


# ---------------------------------------------------------------------------
# SIGTAP oficial — carregamento + fusão com a curadoria (TICKET-FILA-7)
# ---------------------------------------------------------------------------

def _resolver_sigtap_csv() -> str:
    """Caminho do CSV SIGTAP (gerado offline pelo script de import).

    Prioriza `PICSAUDE_SIGTAP_CSV` (empacotamento: caminho estável fora de
    /data); senão usa o layout de dev (raiz do repo / data/sigtap_exames.csv).
    Mesmo padrão de `base_cid.py::_resolver_cid_csv`.
    """
    override = os.getenv("PICSAUDE_SIGTAP_CSV")
    if override:
        return override
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "data", "sigtap_exames.csv",
        )
    )


def _carregar_csv_sigtap(caminho: str) -> list[dict]:
    """Lê o CSV SIGTAP e devolve registros no formato interno de `_BaseTUSS`
    — bare, sem curadoria (aliases/preparo/alertas vazios; `codigo_tuss`
    ausente). `nome_busca` usa `normalizar_nome_exame`, a MESMA função do
    lookup do usuário — é essa consistência que faz o join por nome (contra
    a curadoria, abaixo) funcionar."""
    registros: list[dict] = []
    try:
        with open(caminho, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                codigo = (row.get("codigo_sigtap") or "").strip()
                nome = (row.get("nome") or "").strip()
                if not codigo or not nome:
                    continue
                competencia = (row.get("competencia") or "").strip()
                registros.append({
                    "codigo_tuss":  None,
                    "codigo_sigtap": codigo,
                    "nome_padrao":  nome,
                    "nome_busca":   normalizar_nome_exame(nome),
                    "aliases":      [],
                    "categoria":    None,
                    "subgrupo":     (row.get("subgrupo") or "").strip() or None,
                    "preparo":      None,
                    "alertas_base": [],
                    "fonte":        f"SIGTAP/DATASUS {competencia}" if competencia else "SIGTAP/DATASUS",
                })
    except FileNotFoundError:
        pass
    return registros


def _construir_base() -> list[dict]:
    """Curadoria TUSS (`_BASE_RAW`) sobreposta ao SIGTAP oficial (CSV).

    Join por NOME NORMALIZADO (não há chave de código comum entre TUSS e
    SIGTAP — ver docstring do módulo). Colisão de nome → FUSÃO: o registro
    final carrega os dois códigos, mais aliases/preparo/alertas/categoria
    da curadoria. Sem colisão, os dois catálogos coexistem como entradas
    separadas — nenhum código sai da base por falta de par (catálogo
    suave). Se o CSV não existir, degrada para só a curadoria — nunca
    quebra (mesmo padrão de `base_cid.py::_construir_base`).
    """
    sigtap_regs = _carregar_csv_sigtap(_resolver_sigtap_csv())
    if not sigtap_regs:
        return [{**r, "codigo_sigtap": None, "subgrupo": None, "fonte": "TUSS/BASE_LOCAL"}
                for r in _BASE_RAW]

    por_nome: dict[str, dict] = {r["nome_busca"]: r for r in sigtap_regs}
    for cur in _BASE_RAW:
        registro = {**cur, "codigo_sigtap": None, "subgrupo": None, "fonte": "TUSS/BASE_LOCAL"}
        chave = registro["nome_busca"]
        alvo_sigtap = por_nome.get(chave)
        if alvo_sigtap is not None:
            registro["codigo_sigtap"] = alvo_sigtap["codigo_sigtap"]
            registro["subgrupo"] = alvo_sigtap["subgrupo"]
            registro["fonte"] = f"{registro['fonte']} + {alvo_sigtap['fonte']}"
        por_nome[chave] = registro  # funde (se havia par) ou adiciona a curadoria

    # ENG-027 — o mapeamento OFICIAL preenche o `codigo_tuss` das linhas que
    # só tinham SIGTAP. Antes disto, 1.105 procedimentos de exame nasciam com
    # `codigo_tuss: None` e o faturamento pelo código da saúde suplementar não
    # tinha de onde sair. Só entra par UNÍVOCO: onde a ANS mapeia o mesmo
    # SIGTAP para vários TUSS, escolher um seria inventar precisão que a fonte
    # não tem — fica None, e o relatório conta quantos são.
    mapa = _carregar_mapa_tuss_sigtap(_resolver_tuss_mapa_csv())
    if mapa:
        for registro in por_nome.values():
            if registro.get("codigo_tuss") or not registro.get("codigo_sigtap"):
                continue
            pares = mapa.get(registro["codigo_sigtap"], [])
            codigos = {p["codigo_tuss"] for p in pares}
            if len(codigos) != 1:
                continue
            registro["codigo_tuss"] = pares[0]["codigo_tuss"]
            registro["fonte"] = (
                f"{registro['fonte']} + TUSS/ANS (mapeamento oficial 2017-04, "
                f"grau {pares[0]['grau_equivalencia'] or 'não atribuído'})"
            )
    return list(por_nome.values())


# ---------------------------------------------------------------------------
# TUSS oficial — a base que faltava (ENG-027 §2)
# ---------------------------------------------------------------------------
#
# Até 28/09/2026 os códigos TUSS desta casa eram os ~38 de `_BASE_RAW`,
# digitados à mão, SEM FONTE. O despacho ENG-027 chamou isso de "a única perna
# sem fonte oficial", e tinha razão: a conferência contra a Tabela 22 da ANS
# mostrou que **36 dos 38 não existem** na terminologia oficial, e que os
# códigos certos são outros (hemograma completo é 40304361, não 40301079).
# Ver `docs/tickets/RELATORIO-TUSS-RECONCILIACAO.md`.
#
# O que este bloco faz — e o que ele DELIBERADAMENTE não faz:
#   • carrega a Tabela 22 oficial (`data/tuss_procedimentos.csv`) e o
#     mapeamento TUSS x SIGTAP oficial (`data/tuss_sigtap_mapeamento.csv`);
#   • usa o mapeamento para dar `codigo_tuss` OFICIAL às linhas que hoje só
#     têm SIGTAP — e só quando o mapeamento é UNÍVOCO (um TUSS para aquele
#     SIGTAP). Ambíguo fica sem par, e entra no relatório;
#   • **não corrige** os códigos de `_BASE_RAW`. Trocar código que vai para
#     faturamento é decisão de curadoria, não de engenharia — a divergência
#     está medida, nomeada e travada por guarda, e a caneta é do Fabiano.


def _resolver_tuss_csv() -> str:
    """Caminho da Tabela 22 oficial. Mesmo padrão do SIGTAP/CID."""
    override = os.getenv("PICSAUDE_TUSS_CSV")
    if override:
        return override
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "tuss_procedimentos.csv"))


def _resolver_tuss_mapa_csv() -> str:
    """Caminho do mapeamento oficial TUSS x SIGTAP."""
    override = os.getenv("PICSAUDE_TUSS_MAPA_CSV")
    if override:
        return override
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data",
        "tuss_sigtap_mapeamento.csv"))


def _carregar_csv_tuss(caminho: str) -> dict[str, dict]:
    """Tabela 22 oficial → {codigo_tuss: {termo, fonte, versao}}.

    Degrada para vazio se o arquivo não existir — a base continua de pé com
    o que já tinha (mesma régua do SIGTAP: catálogo suave, nunca quebra)."""
    registros: dict[str, dict] = {}
    try:
        with open(caminho, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                codigo = (row.get("codigo_tuss") or "").strip()
                termo = (row.get("termo") or "").strip()
                if not codigo or not termo:
                    continue
                registros[codigo] = {
                    "termo": termo,
                    "nome_busca": normalizar_nome_exame(termo),
                    "versao_snapshot": (row.get("versao_snapshot") or "").strip(),
                    "fonte": (row.get("fonte") or "").strip(),
                }
    except FileNotFoundError:
        pass
    return registros


def _carregar_mapa_tuss_sigtap(caminho: str) -> dict[str, list[dict]]:
    """Mapeamento oficial → {codigo_sigtap: [pares]}.

    A ANS mapeia de um ou vários TUSS para um ou vários SIGTAP (metodologia,
    item 3), então a chave aponta para LISTA — quem consome decide o que
    fazer com a ambiguidade, e aqui a decisão é não escolher."""
    por_sigtap: dict[str, list[dict]] = {}
    try:
        with open(caminho, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                sigtap = (row.get("codigo_sigtap") or "").strip()
                tuss = (row.get("codigo_tuss") or "").strip()
                if not sigtap or not tuss:
                    continue
                por_sigtap.setdefault(sigtap, []).append({
                    "codigo_tuss": tuss,
                    "grau_equivalencia": (row.get("grau_equivalencia") or "").strip(),
                    "grau_descricao": (row.get("grau_descricao") or "").strip(),
                })
    except FileNotFoundError:
        pass
    return por_sigtap


def _competencia_sigtap() -> Optional[str]:
    """Competência do CSV SIGTAP carregado, para compor `versao` — lida do
    próprio arquivo, nunca declarada à mão (mesma disciplina anti-lenda do
    `base_cid.py`: uma string escrita à mão envelhece em silêncio)."""
    try:
        with open(_resolver_sigtap_csv(), encoding="utf-8", newline="") as f:
            primeira = next(csv.DictReader(f), None)
            return (primeira.get("competencia") or "").strip() or None if primeira else None
    except FileNotFoundError:
        return None


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
        # Prefixo "tuss_local" preservado — a curadoria continua na base
        # mesmo com o SIGTAP acoplado. Sufixo entra SÓ quando o CSV existe
        # (lido do arquivo, nunca declarado à mão — TICKET-FILA-7).
        competencia = _competencia_sigtap()
        if competencia:
            return f"tuss_local_v2+sigtap_{competencia}"
        return "tuss_local_v1"


# Singleton — carregado uma vez no import
BASE_TUSS = _BaseTUSS(_construir_base())
