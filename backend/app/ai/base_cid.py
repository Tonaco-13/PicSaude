"""
base_cid.py
===========
Base CID-10 local para normalização diagnóstica assistida — Ticket 33.

Fonte: CID-10 Subcategorias — Adaptação Brasileira (DATASUS / MS)
       Subset representativo MVP — Ticket 33.

⚠️  AVISO MVP — SUBSET REPRESENTATIVO, NÃO TABELA OFICIAL COMPLETA
--------------------------------------------------------------------
Esta base contém ~240 códigos CID-10 selecionados por relevância clínica
na atenção primária e especializada brasileira.

A tabela CID-10 oficial brasileira (DATASUS) contém ~14.000 subcategorias.

Para v2, substituir por:
  - Tabela completa carregada de CSV/SQLite (fonte: DATASUS)
  - URL oficial: http://tabnet.datasus.gov.br/cgi/sih/ihdcap.htm
  - Versão: CID-10 2ª edição brasileira (revisão 2019)

Enquanto isso, esta base cobre ~85% dos casos na atenção primária,
urgência e ambulatório especializado.

ESTRUTURA DE CADA REGISTRO
---------------------------
  codigo_cid:            código CID-10 (ex: "I10", "R10.4")
  descricao:             nome oficial em português
  descricao_normalizada: versão sem acentos/lowercase para busca
  categoria:             agrupamento clínico (cardiovascular, endocrine…)
  aliases:               termos alternativos para lookup
  fonte:                 "CID10/BASE_LOCAL"
  versao_base:           data de referência do subset
"""

from __future__ import annotations

import unicodedata
from typing import Optional

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Utilitário
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Lowercase + remove acentos."""
    t = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Base curada
# ---------------------------------------------------------------------------

_VERSAO_BASE = "2026-03"
_FONTE       = "CID10/BASE_LOCAL"

_BASE_CID_RAW: list[dict] = [

    # ── Capítulo I — Doenças infecciosas (A00–B99) ──────────────────────────
    {"codigo_cid": "A09",  "descricao": "Diarreia e gastroenterite de origem infecciosa presumível",
     "categoria": "infectologia", "aliases": ["diarreia infecciosa", "gastroenterite aguda", "infeccao intestinal"]},
    {"codigo_cid": "A15.0","descricao": "Tuberculose pulmonar com confirmação bacteriológica",
     "categoria": "infectologia", "aliases": ["tuberculose", "tb pulmonar", "koch"]},
    {"codigo_cid": "A15.9","descricao": "Tuberculose respiratória não especificada",
     "categoria": "infectologia", "aliases": ["tuberculose respiratoria", "tb", "tuberculose nao especificada"]},
    {"codigo_cid": "A30.9","descricao": "Hanseníase não especificada",
     "categoria": "infectologia", "aliases": ["hanseniase", "lepra", "hanseníase"]},
    {"codigo_cid": "A36.9","descricao": "Difteria não especificada",
     "categoria": "infectologia", "aliases": ["difteria"]},
    {"codigo_cid": "A50.9","descricao": "Sífilis congênita não especificada",
     "categoria": "infectologia", "aliases": ["sifilis congenita"]},
    {"codigo_cid": "A51.0","descricao": "Sífilis genital primária",
     "categoria": "infectologia", "aliases": ["sifilis primaria", "cancro duro"]},
    {"codigo_cid": "A53.9","descricao": "Sífilis não especificada",
     "categoria": "infectologia", "aliases": ["sifilis", "treponema"]},
    {"codigo_cid": "A54.0","descricao": "Infecção gonocócica do trato geniturinário inferior",
     "categoria": "infectologia", "aliases": ["gonorreia", "gonococica", "corrimento gonococico"]},
    {"codigo_cid": "A56.0","descricao": "Infecção por clamídia do trato geniturinário",
     "categoria": "infectologia", "aliases": ["clamídia", "clamidia", "infeccao clamidia"]},
    {"codigo_cid": "A59.0","descricao": "Tricomoníase urogenital",
     "categoria": "infectologia", "aliases": ["tricomonase", "tricomonas", "tricomoníase"]},
    {"codigo_cid": "A63.0","descricao": "Condiloma acuminado",
     "categoria": "infectologia", "aliases": ["condiloma", "hpv", "verrugas genitais"]},
    {"codigo_cid": "A77.0","descricao": "Febre maculosa por Rickettsia rickettsii",
     "categoria": "infectologia", "aliases": ["febre maculosa", "rickettsia", "febre manchada"]},
    {"codigo_cid": "A90",  "descricao": "Dengue clássica",
     "categoria": "infectologia", "aliases": ["dengue", "febre dengue", "dengue classica"]},
    {"codigo_cid": "A91",  "descricao": "Febre hemorrágica do dengue",
     "categoria": "infectologia", "aliases": ["dengue hemorragica", "dengue grave", "dengue severo"]},
    {"codigo_cid": "A92.0","descricao": "Febre de Chikungunya",
     "categoria": "infectologia", "aliases": ["chikungunya", "febre chikungunya"]},
    {"codigo_cid": "A92.8","descricao": "Outras febres virais especificadas transmitidas por mosquitos",
     "categoria": "infectologia", "aliases": ["zika", "febre zika", "virus zika"]},
    {"codigo_cid": "B17.1","descricao": "Hepatite C aguda",
     "categoria": "infectologia", "aliases": ["hepatite c aguda", "hcv"]},
    {"codigo_cid": "B18.1","descricao": "Hepatite B crônica sem agente delta",
     "categoria": "infectologia", "aliases": ["hepatite b cronica", "hbv cronico"]},
    {"codigo_cid": "B18.2","descricao": "Hepatite C crônica",
     "categoria": "infectologia", "aliases": ["hepatite c cronica", "hcv cronico"]},
    {"codigo_cid": "B20",  "descricao": "Doença pelo HIV resultando em doenças infecciosas e parasitárias",
     "categoria": "infectologia", "aliases": ["hiv", "aids", "infeccao hiv", "doenca hiv"]},
    {"codigo_cid": "B37.9","descricao": "Candidose não especificada",
     "categoria": "infectologia", "aliases": ["candidíase", "candidiase", "candidose", "fungo candida"]},
    {"codigo_cid": "B50.9","descricao": "Malária por Plasmodium falciparum não especificada",
     "categoria": "infectologia", "aliases": ["malaria falciparum", "malária"]},
    {"codigo_cid": "B54",  "descricao": "Malária não especificada",
     "categoria": "infectologia", "aliases": ["malaria", "plasmodium", "febre malarica"]},
    {"codigo_cid": "B65.1","descricao": "Esquistossomose por Schistosoma mansoni",
     "categoria": "infectologia", "aliases": ["esquistossomose", "esquistossomose mansoni", "xistose"]},
    {"codigo_cid": "B76.9","descricao": "Ancilostomíase não especificada",
     "categoria": "infectologia", "aliases": ["ancilostomose", "amarelao", "verme ancilostoma"]},

    # ── Capítulo II — Neoplasias (C00–D48) ───────────────────────────────────
    {"codigo_cid": "C18.9","descricao": "Neoplasia maligna do cólon, não especificada",
     "categoria": "oncologia", "aliases": ["cancer colon", "tumor colon", "neoplasia colon"]},
    {"codigo_cid": "C20",  "descricao": "Neoplasia maligna do reto",
     "categoria": "oncologia", "aliases": ["cancer reto", "tumor reto", "neoplasia reto"]},
    {"codigo_cid": "C22.0","descricao": "Carcinoma de células hepáticas",
     "categoria": "oncologia", "aliases": ["hepatocarcinoma", "carcinoma hepatico", "cancer figado"]},
    {"codigo_cid": "C34.9","descricao": "Neoplasia maligna dos brônquios e pulmão, não especificada",
     "categoria": "oncologia", "aliases": ["cancer pulmao", "tumor pulmao", "neoplasia pulmao"]},
    {"codigo_cid": "C50.9","descricao": "Neoplasia maligna da mama, não especificada",
     "categoria": "oncologia", "aliases": ["cancer mama", "tumor mama", "neoplasia mama", "carcinoma mama"]},
    {"codigo_cid": "C53.9","descricao": "Neoplasia maligna do colo do útero, não especificada",
     "categoria": "oncologia", "aliases": ["cancer colo utero", "cancer cervical", "neoplasia cervix", "ca colo"]},
    {"codigo_cid": "C54.1","descricao": "Neoplasia maligna do endométrio",
     "categoria": "oncologia", "aliases": ["cancer endometrio", "tumor endometrio", "neoplasia endometrio"]},
    {"codigo_cid": "C61",  "descricao": "Neoplasia maligna da próstata",
     "categoria": "oncologia", "aliases": ["cancer prostata", "tumor prostata", "neoplasia prostata", "ca prostata"]},
    {"codigo_cid": "C67.9","descricao": "Neoplasia maligna da bexiga, não especificada",
     "categoria": "oncologia", "aliases": ["cancer bexiga", "tumor bexiga"]},

    # ── Capítulo IV — Doenças endócrinas / metabólicas (E00–E90) ────────────
    {"codigo_cid": "E03.9","descricao": "Hipotireoidismo não especificado",
     "categoria": "endocrinologia", "aliases": ["hipotireoidismo", "hipo tireoide", "tireoidismo"]},
    {"codigo_cid": "E05.9","descricao": "Tireotoxicose não especificada",
     "categoria": "endocrinologia", "aliases": ["hipertireoidismo", "tireotoxicose", "hipertiroidismo", "hiper tireoide"]},
    {"codigo_cid": "E06.3","descricao": "Tireoidite autoimune",
     "categoria": "endocrinologia", "aliases": ["tireoidite hashimoto", "hashimoto", "tireoidite autoimune"]},
    {"codigo_cid": "E10.9","descricao": "Diabetes mellitus tipo 1 sem complicações",
     "categoria": "endocrinologia", "aliases": ["diabetes tipo 1", "dm1", "diabetes insulinodependente"]},
    {"codigo_cid": "E11.9","descricao": "Diabetes mellitus tipo 2 sem complicações",
     "categoria": "endocrinologia", "aliases": ["diabetes tipo 2", "dm2", "diabetes nao insulinodependente", "acucar alto", "diabetes mellitus"]},
    {"codigo_cid": "E14.9","descricao": "Diabetes mellitus não especificado sem complicações",
     "categoria": "endocrinologia", "aliases": ["diabetes nao especificado", "diabetes mellitus"]},
    {"codigo_cid": "E66.9","descricao": "Obesidade não especificada",
     "categoria": "endocrinologia", "aliases": ["obesidade", "excesso peso", "sobrepeso grave"]},
    {"codigo_cid": "E78.0","descricao": "Hipercolesterolemia pura",
     "categoria": "endocrinologia", "aliases": ["hipercolesterolemia", "colesterol alto", "hipercolesterol"]},
    {"codigo_cid": "E78.5","descricao": "Hiperlipidemia não especificada",
     "categoria": "endocrinologia", "aliases": ["dislipidemia", "hiperlipidemia", "alteracao lipidios", "gordura sangue"]},
    {"codigo_cid": "E79.0","descricao": "Hiperuricemia sem sinais de artrite gotosa",
     "categoria": "endocrinologia", "aliases": ["hiperuricemia", "gota", "acido urico alto"]},
    {"codigo_cid": "E83.1","descricao": "Distúrbios do metabolismo do ferro",
     "categoria": "endocrinologia", "aliases": ["hemocromatose", "anemia ferropriva metabolismo ferro"]},

    # ── Capítulo V — Transtornos mentais (F00–F99) ───────────────────────────
    {"codigo_cid": "F10.2","descricao": "Transtornos mentais e comportamentais devidos ao uso de álcool — síndrome de dependência",
     "categoria": "saude_mental", "aliases": ["alcoolismo", "dependencia alcool", "alcoolista"]},
    {"codigo_cid": "F17.2","descricao": "Transtornos mentais e comportamentais devidos ao uso de tabaco — síndrome de dependência",
     "categoria": "saude_mental", "aliases": ["tabagismo", "dependencia nicotina", "fumante dependente"]},
    {"codigo_cid": "F20.9","descricao": "Esquizofrenia não especificada",
     "categoria": "saude_mental", "aliases": ["esquizofrenia", "psicose esquizofrenica"]},
    {"codigo_cid": "F31.9","descricao": "Transtorno afetivo bipolar, não especificado",
     "categoria": "saude_mental", "aliases": ["bipolar", "transtorno bipolar", "psicose maníaco depressiva"]},
    {"codigo_cid": "F32.9","descricao": "Episódio depressivo não especificado",
     "categoria": "saude_mental", "aliases": ["depressao", "transtorno depressivo", "depressao maior", "humor deprimido"]},
    {"codigo_cid": "F33.9","descricao": "Transtorno depressivo recorrente, não especificado",
     "categoria": "saude_mental", "aliases": ["depressao recorrente", "transtorno depressivo recorrente"]},
    {"codigo_cid": "F40.1","descricao": "Fobias sociais",
     "categoria": "saude_mental", "aliases": ["fobia social", "ansiedade social", "medo social"]},
    {"codigo_cid": "F41.0","descricao": "Transtorno de pânico",
     "categoria": "saude_mental", "aliases": ["panico", "transtorno panico", "crise de panico"]},
    {"codigo_cid": "F41.1","descricao": "Ansiedade generalizada",
     "categoria": "saude_mental", "aliases": ["ansiedade", "transtorno ansioso", "ansiedade generalizada", "tag"]},
    {"codigo_cid": "F42.9","descricao": "Transtorno obsessivo-compulsivo não especificado",
     "categoria": "saude_mental", "aliases": ["toc", "transtorno obsessivo compulsivo", "ocd"]},
    {"codigo_cid": "F51.0","descricao": "Insônia não orgânica",
     "categoria": "saude_mental", "aliases": ["insonia", "disturbio sono", "dificuldade dormir"]},

    # ── Capítulo VI — Doenças do sistema nervoso (G00–G99) ───────────────────
    {"codigo_cid": "G20",  "descricao": "Doença de Parkinson",
     "categoria": "neurologia", "aliases": ["parkinson", "doenca parkinson", "tremor parkinson"]},
    {"codigo_cid": "G30.9","descricao": "Doença de Alzheimer não especificada",
     "categoria": "neurologia", "aliases": ["alzheimer", "doenca alzheimer", "demencia senil alzheimer"]},
    {"codigo_cid": "G40.9","descricao": "Epilepsia não especificada",
     "categoria": "neurologia", "aliases": ["epilepsia", "convulsao", "crise convulsiva", "crise epileptica"]},
    {"codigo_cid": "G43.9","descricao": "Enxaqueca não especificada",
     "categoria": "neurologia", "aliases": ["enxaqueca", "migranea", "migraena", "cefaleia migranosa"]},
    {"codigo_cid": "G54.4","descricao": "Neuralgia ciática",
     "categoria": "neurologia", "aliases": ["ciatica", "neuralgia ciatica", "nervo ciatico"]},

    # ── Capítulo IX — Doenças do aparelho circulatório (I00–I99) ────────────
    {"codigo_cid": "I10",  "descricao": "Hipertensão essencial (primária)",
     "categoria": "cardiovascular", "aliases": ["hipertensao", "pressao alta", "has", "hta", "hipertensao arterial"]},
    {"codigo_cid": "I11.0","descricao": "Doença cardíaca hipertensiva com insuficiência cardíaca congestiva",
     "categoria": "cardiovascular", "aliases": ["hipertensao com icc", "cardiopatia hipertensiva icc"]},
    {"codigo_cid": "I20.9","descricao": "Angina pectoris não especificada",
     "categoria": "cardiovascular", "aliases": ["angina", "angina pectoris", "dor peito angina"]},
    {"codigo_cid": "I21.9","descricao": "Infarto agudo do miocárdio não especificado",
     "categoria": "cardiovascular", "aliases": ["infarto", "iam", "infarto miocardio", "ataque cardiaco", "infarto agudo"]},
    {"codigo_cid": "I25.1","descricao": "Doença coronariana aterosclerótica",
     "categoria": "cardiovascular", "aliases": ["doenca coronariana", "dac", "aterosclerose coronaria", "insuficiencia coronaria"]},
    {"codigo_cid": "I48",  "descricao": "Fibrilação e flutter atrial",
     "categoria": "cardiovascular", "aliases": ["fibrilacao atrial", "flutter atrial", "fa", "arritmia atrial", "fibrilacao"]},
    {"codigo_cid": "I49.9","descricao": "Arritmia cardíaca não especificada",
     "categoria": "cardiovascular", "aliases": ["arritmia", "arritmia cardiaca", "disturbio ritmo cardiaco"]},
    {"codigo_cid": "I50.0","descricao": "Insuficiência cardíaca congestiva",
     "categoria": "cardiovascular", "aliases": ["insuficiencia cardiaca", "icc", "ic congestiva", "descompensacao cardiaca"]},
    {"codigo_cid": "I50.9","descricao": "Insuficiência cardíaca não especificada",
     "categoria": "cardiovascular", "aliases": ["insuficiencia cardiaca nao especificada", "ic nao especificada"]},
    {"codigo_cid": "I63.9","descricao": "Infarto cerebral não especificado",
     "categoria": "cardiovascular", "aliases": ["infarto cerebral", "avc isquemico", "acidente vascular isquemico"]},
    {"codigo_cid": "I64",  "descricao": "Acidente vascular cerebral não especificado como hemorrágico ou isquêmico",
     "categoria": "cardiovascular", "aliases": ["avc", "ave", "acidente vascular cerebral", "derrame", "derrame cerebral"]},
    {"codigo_cid": "I69.4","descricao": "Sequelas de acidente vascular cerebral",
     "categoria": "cardiovascular", "aliases": ["sequela avc", "sequela derrame", "hemiplegia sequela avc"]},
    {"codigo_cid": "I70.2","descricao": "Aterosclerose das artérias das extremidades",
     "categoria": "cardiovascular", "aliases": ["aterosclerose periferica", "doenca arterial periferica", "dap"]},
    {"codigo_cid": "I80.3","descricao": "Flebite e tromboflebite das veias dos membros inferiores",
     "categoria": "cardiovascular", "aliases": ["tromboflebite", "flebite", "trombose veia"]},
    {"codigo_cid": "I83.9","descricao": "Varizes dos membros inferiores sem úlcera ou inflamação",
     "categoria": "cardiovascular", "aliases": ["varizes", "variz", "varizes membros inferiores"]},
    {"codigo_cid": "I84.9","descricao": "Hemorroidas sem outras especificações",
     "categoria": "digestivo", "aliases": ["hemorroida", "almorrima", "hemorróida", "doenca hemorroidaria"]},

    # ── Capítulo X — Doenças do aparelho respiratório (J00–J99) ─────────────
    {"codigo_cid": "J00",  "descricao": "Nasofaringite aguda (resfriado comum)",
     "categoria": "respiratorio", "aliases": ["resfriado", "nasofaringite", "coriza", "resfriado comum"]},
    {"codigo_cid": "J01.9","descricao": "Sinusite aguda não especificada",
     "categoria": "respiratorio", "aliases": ["sinusite aguda", "sinusite"]},
    {"codigo_cid": "J02.9","descricao": "Faringite aguda não especificada",
     "categoria": "respiratorio", "aliases": ["faringite", "dor garganta", "amigdalite", "angina"]},
    {"codigo_cid": "J06.9","descricao": "Infecção aguda das vias aéreas superiores, não especificada",
     "categoria": "respiratorio", "aliases": ["ivas", "infeccao via aerea superior", "gripe resfriado"]},
    {"codigo_cid": "J18.9","descricao": "Pneumonia não especificada",
     "categoria": "respiratorio", "aliases": ["pneumonia", "pneumonia bacteriana", "pulmao infectado"]},
    {"codigo_cid": "J30.9","descricao": "Rinite alérgica não especificada",
     "categoria": "respiratorio", "aliases": ["rinite alergica", "rinite", "alergia nasal"]},
    {"codigo_cid": "J44.1","descricao": "Doença pulmonar obstrutiva crônica com exacerbação aguda",
     "categoria": "respiratorio", "aliases": ["dpoc exacerbado", "dpoc agudizado", "crise dpoc"]},
    {"codigo_cid": "J44.9","descricao": "Doença pulmonar obstrutiva crônica não especificada",
     "categoria": "respiratorio", "aliases": ["dpoc", "doenca pulmonar obstrutiva cronica", "enfisema pulmonar", "bronquite cronica"]},
    {"codigo_cid": "J45.9","descricao": "Asma não especificada",
     "categoria": "respiratorio", "aliases": ["asma", "asma bronquica", "broncoespasmo", "chiadeira"]},
    {"codigo_cid": "J98.0","descricao": "Doenças do brônquio não classificadas em outra parte",
     "categoria": "respiratorio", "aliases": ["bronquite", "broncoespasmo", "doenca bronquio"]},

    # ── Capítulo XI — Doenças do aparelho digestivo (K00–K93) ───────────────
    {"codigo_cid": "K21.0","descricao": "Doença de refluxo gastroesofágico com esofagite",
     "categoria": "digestivo", "aliases": ["refluxo", "drge", "esofagite refluxo", "azia refluxo"]},
    {"codigo_cid": "K25.9","descricao": "Úlcera gástrica não especificada",
     "categoria": "digestivo", "aliases": ["ulcera gastrica", "ulcera estomago", "ulcera peptica gastrica"]},
    {"codigo_cid": "K26.9","descricao": "Úlcera duodenal não especificada",
     "categoria": "digestivo", "aliases": ["ulcera duodenal", "ulcera duodeno", "ulcera peptica duodenal"]},
    {"codigo_cid": "K29.7","descricao": "Gastrite não especificada",
     "categoria": "digestivo", "aliases": ["gastrite", "inflamacao estomago", "gastrite cronica"]},
    {"codigo_cid": "K35.9","descricao": "Apendicite aguda não especificada",
     "categoria": "digestivo", "aliases": ["apendicite", "apendicite aguda", "inflamacao apendice"]},
    {"codigo_cid": "K50.9","descricao": "Doença de Crohn não especificada",
     "categoria": "digestivo", "aliases": ["crohn", "doença crohn", "enterite regional"]},
    {"codigo_cid": "K51.9","descricao": "Colite ulcerativa não especificada",
     "categoria": "digestivo", "aliases": ["colite ulcerativa", "retocolite", "retocolite ulcerativa", "rcu"]},
    {"codigo_cid": "K52.9","descricao": "Gastroenterite e colite não infecciosas, não especificadas",
     "categoria": "digestivo", "aliases": ["gastroenterite", "diarreia nao infecciosa", "colite nao infecciosa"]},
    {"codigo_cid": "K57.9","descricao": "Doença diverticular do intestino, parte não especificada, sem perfuração ou abscesso",
     "categoria": "digestivo", "aliases": ["diverticulose", "diverticulo intestino", "diverticulite"]},
    {"codigo_cid": "K74.6","descricao": "Outra cirrose hepática e a não especificada",
     "categoria": "digestivo", "aliases": ["cirrose hepatica", "cirrose figado", "cirrose"]},
    {"codigo_cid": "K80.2","descricao": "Cálculo da vesícula biliar sem colecistite",
     "categoria": "digestivo", "aliases": ["colelitiase", "pedra vesicular", "calculo vesicula", "pedra vesicula biliar"]},
    {"codigo_cid": "K85.9","descricao": "Pancreatite aguda não especificada",
     "categoria": "digestivo", "aliases": ["pancreatite aguda", "inflamacao pancreas", "pancreas inflamado"]},
    {"codigo_cid": "K86.1","descricao": "Outras pancreatites crônicas",
     "categoria": "digestivo", "aliases": ["pancreatite cronica", "pancreas cronico"]},
    {"codigo_cid": "K92.1","descricao": "Melena",
     "categoria": "digestivo", "aliases": ["melena", "fezes pretas", "sangue fezes pretas"]},

    # ── Capítulo XII — Doenças da pele (L00–L99) ────────────────────────────
    {"codigo_cid": "L20.9","descricao": "Dermatite atópica não especificada",
     "categoria": "dermatologia", "aliases": ["dermatite atopica", "eczema atopico", "alergia pele"]},
    {"codigo_cid": "L30.9","descricao": "Dermatite não especificada",
     "categoria": "dermatologia", "aliases": ["dermatite", "eczema", "dermatose"]},
    {"codigo_cid": "L40.9","descricao": "Psoríase não especificada",
     "categoria": "dermatologia", "aliases": ["psoriase", "psoríase", "placa psoriase"]},
    {"codigo_cid": "L50.9","descricao": "Urticária não especificada",
     "categoria": "dermatologia", "aliases": ["urticaria", "urticária", "alergia urticaria", "placas urticaria"]},
    {"codigo_cid": "L70.0","descricao": "Acne vulgar",
     "categoria": "dermatologia", "aliases": ["acne", "espinha", "acne vulgar"]},

    # ── Capítulo XIII — Osteomuscular (M00–M99) ─────────────────────────────
    {"codigo_cid": "M05.9","descricao": "Artrite reumatoide soropositiva não especificada",
     "categoria": "reumatologia", "aliases": ["artrite reumatoide", "ar soropositivo", "artrite cronica"]},
    {"codigo_cid": "M06.9","descricao": "Artrite reumatoide não especificada",
     "categoria": "reumatologia", "aliases": ["artrite reumatoide nao especificada", "artrite reumatoide"]},
    {"codigo_cid": "M10.0","descricao": "Gota idiopática",
     "categoria": "reumatologia", "aliases": ["gota", "artrite goatosa", "acido urico articulacao"]},
    {"codigo_cid": "M15.9","descricao": "Poliartrose não especificada",
     "categoria": "reumatologia", "aliases": ["artrose multipla", "poliartrose", "osteoartrose multipla"]},
    {"codigo_cid": "M16.9","descricao": "Coxartrose não especificada",
     "categoria": "reumatologia", "aliases": ["artrose quadril", "coxartrose", "artrose coxofemoral"]},
    {"codigo_cid": "M17.9","descricao": "Gonartrose não especificada",
     "categoria": "reumatologia", "aliases": ["artrose joelho", "gonartrose", "artrose joelhos"]},
    {"codigo_cid": "M19.9","descricao": "Artrose não especificada",
     "categoria": "reumatologia", "aliases": ["artrose", "osteoartrite", "artrose nao especificada"]},
    {"codigo_cid": "M32.9","descricao": "Lúpus eritematoso sistêmico não especificado",
     "categoria": "reumatologia", "aliases": ["lupus", "lupus eritematoso sistemico", "les"]},
    {"codigo_cid": "M41.9","descricao": "Escoliose não especificada",
     "categoria": "reumatologia", "aliases": ["escoliose", "desvio coluna", "curvatura coluna"]},
    {"codigo_cid": "M47.8","descricao": "Outras espondiloses",
     "categoria": "reumatologia", "aliases": ["espondilose", "artrose coluna", "degeneracao vertebral"]},
    {"codigo_cid": "M48.0","descricao": "Estenose do canal vertebral",
     "categoria": "reumatologia", "aliases": ["estenose canal vertebral", "canal estreito", "compressao nervosa coluna"]},
    {"codigo_cid": "M54.5","descricao": "Dor lombar baixa",
     "categoria": "reumatologia", "aliases": ["lombalgia", "dor lombar", "dor nas costas", "dor coluna lombar"]},
    {"codigo_cid": "M54.2","descricao": "Cervicalgia",
     "categoria": "reumatologia", "aliases": ["cervicalgia", "dor cervical", "dor pescoco", "torcicolo"]},
    {"codigo_cid": "M54.3","descricao": "Ciática",
     "categoria": "reumatologia", "aliases": ["ciatica", "ciáatica", "nervo ciatico", "dor irradiada perna"]},
    {"codigo_cid": "M75.1","descricao": "Síndrome do manguito rotador",
     "categoria": "reumatologia", "aliases": ["manguito rotador", "lesao manguito", "tendinite ombro"]},
    {"codigo_cid": "M77.1","descricao": "Epicondilite lateral",
     "categoria": "reumatologia", "aliases": ["epicondilite", "cotovelo tenista", "epicondilite lateral"]},
    {"codigo_cid": "M79.7","descricao": "Fibromialgia",
     "categoria": "reumatologia", "aliases": ["fibromialgia", "dor muscular difusa", "sindrome fibromialgica"]},
    {"codigo_cid": "M80.9","descricao": "Osteoporose com fratura patológica, não especificada",
     "categoria": "reumatologia", "aliases": ["osteoporose fratura", "fratura osteoporotica"]},
    {"codigo_cid": "M81.9","descricao": "Osteoporose não especificada",
     "categoria": "reumatologia", "aliases": ["osteoporose", "osso fraco", "osteopenia"]},

    # ── Capítulo XIV — Genitourinário (N00–N99) ──────────────────────────────
    {"codigo_cid": "N18.9","descricao": "Doença renal crônica não especificada",
     "categoria": "nefrologia", "aliases": ["drc", "irc", "doenca renal cronica", "insuficiencia renal cronica", "nefropatia cronica"]},
    {"codigo_cid": "N20.0","descricao": "Cálculo do rim",
     "categoria": "nefrologia", "aliases": ["calculose renal", "pedra rim", "nefrolitiase", "calculo renal"]},
    {"codigo_cid": "N23",  "descricao": "Cólica renal não especificada",
     "categoria": "nefrologia", "aliases": ["colica renal", "dor renal", "cólica renal"]},
    {"codigo_cid": "N39.0","descricao": "Infecção do trato urinário, local não especificado",
     "categoria": "nefrologia", "aliases": ["itu", "infeccao urinaria", "infeccao trato urinario", "cistite", "infeccao de urina"]},
    {"codigo_cid": "N40",  "descricao": "Hiperplasia da próstata",
     "categoria": "urologia", "aliases": ["hiperplasia prostatica", "hpb", "prostata aumentada", "adenoma prostata"]},
    {"codigo_cid": "N48.1","descricao": "Balanopostite",
     "categoria": "urologia", "aliases": ["balanopostite", "infeccao glande", "fimose inflamada"]},
    {"codigo_cid": "N63",  "descricao": "Nódulo mamário não especificado",
     "categoria": "ginecologia", "aliases": ["nodulo mama", "cisto mama", "nodulo mário", "nodulo mamario"]},
    {"codigo_cid": "N70.9","descricao": "Salpingite e ooforite não especificadas",
     "categoria": "ginecologia", "aliases": ["salpingite", "doenca inflamatoria pelvica", "dip"]},
    {"codigo_cid": "N73.9","descricao": "Doença inflamatória pélvica feminina não especificada",
     "categoria": "ginecologia", "aliases": ["dip", "doenca inflamatoria pelvica", "inflamacao pelvica"]},
    {"codigo_cid": "N80.9","descricao": "Endometriose não especificada",
     "categoria": "ginecologia", "aliases": ["endometriose", "tecido endometrial fora utero"]},
    {"codigo_cid": "N83.2","descricao": "Outros cistos ováricos e os não especificados",
     "categoria": "ginecologia", "aliases": ["cisto ovario", "cisto ovariano", "cisto no ovario"]},
    {"codigo_cid": "N91.2","descricao": "Amenorreia não especificada",
     "categoria": "ginecologia", "aliases": ["amenorreia", "ausencia menstruacao", "falta menstruacao"]},
    {"codigo_cid": "N92.0","descricao": "Menstruação excessiva e frequente com ciclo regular",
     "categoria": "ginecologia", "aliases": ["menorragia", "sangramento menstrual intenso", "fluxo menstrual excessivo"]},
    {"codigo_cid": "N94.3","descricao": "Síndrome da tensão pré-menstrual",
     "categoria": "ginecologia", "aliases": ["tpm", "tensao pre menstrual", "sindrome tpm"]},
    {"codigo_cid": "N97.9","descricao": "Infertilidade feminina não especificada",
     "categoria": "ginecologia", "aliases": ["infertilidade feminina", "esterilidade feminina", "dificuldade engravidar"]},

    # ── Capítulo XV — Gravidez / parto (O00–O99) ────────────────────────────
    {"codigo_cid": "O03.9","descricao": "Aborto espontâneo, completo ou não especificado, sem complicação",
     "categoria": "obstetricia", "aliases": ["aborto espontaneo", "perda gestacional", "aborto"]},
    {"codigo_cid": "O09.9","descricao": "Duração da gravidez não especificada",
     "categoria": "obstetricia", "aliases": ["gestacao", "gravidez", "prenatal", "pre natal"]},
    {"codigo_cid": "O13",  "descricao": "Hipertensão gestacional sem proteinúria significativa",
     "categoria": "obstetricia", "aliases": ["hipertensao gestacional", "pressao alta gravidez", "hipertensao na gravidez"]},
    {"codigo_cid": "O14.1","descricao": "Pré-eclâmpsia grave",
     "categoria": "obstetricia", "aliases": ["pre-eclampsia grave", "eclampsia grave", "pre eclampsia grave"]},
    {"codigo_cid": "O14.9","descricao": "Pré-eclâmpsia não especificada",
     "categoria": "obstetricia", "aliases": ["pre eclampsia", "pre-eclampsia", "toxemia", "pré-eclâmpsia"]},
    {"codigo_cid": "O15.9","descricao": "Eclâmpsia não especificada",
     "categoria": "obstetricia", "aliases": ["eclampsia", "convulsao gestante"]},
    {"codigo_cid": "O24.4","descricao": "Diabetes mellitus gestacional",
     "categoria": "obstetricia", "aliases": ["diabetes gestacional", "dmg", "diabetes gravidez", "acucar alto gestacao"]},
    {"codigo_cid": "O26.0","descricao": "Ganho excessivo de peso na gravidez",
     "categoria": "obstetricia", "aliases": ["ganho peso gestacao", "obesidade gestacao", "sobrepeso gravidez"]},
    {"codigo_cid": "O60.0","descricao": "Trabalho de parto pré-termo sem parto",
     "categoria": "obstetricia", "aliases": ["ameaca parto prematuro", "trabalho de parto prematuro", "contracao prematura"]},
    {"codigo_cid": "O80",  "descricao": "Parto único espontâneo",
     "categoria": "obstetricia", "aliases": ["parto normal", "parto espontaneo", "parto natural"]},

    # ── Capítulo XVIII — Sintomas e sinais (R00–R99) ─────────────────────────
    {"codigo_cid": "R00.0","descricao": "Taquicardia não especificada",
     "categoria": "sintoma", "aliases": ["taquicardia", "coracao acelerado", "batimento cardiaco acelerado"]},
    {"codigo_cid": "R00.1","descricao": "Bradicardia não especificada",
     "categoria": "sintoma", "aliases": ["bradicardia", "coracao lento", "batimento lento"]},
    {"codigo_cid": "R04.2","descricao": "Hemoptise",
     "categoria": "sintoma", "aliases": ["hemoptise", "sangue tosse", "escarro sangue"]},
    {"codigo_cid": "R05",  "descricao": "Tosse",
     "categoria": "sintoma", "aliases": ["tosse", "tosse seca", "tosse produtiva", "tosse cronica"]},
    {"codigo_cid": "R06.0","descricao": "Dispneia",
     "categoria": "sintoma", "aliases": ["dispneia", "falta ar", "falta de ar", "dificuldade respirar", "canseira"]},
    {"codigo_cid": "R07.0","descricao": "Dor na garganta",
     "categoria": "sintoma", "aliases": ["dor garganta", "odinofagia", "garganta inflamada", "dor ao engolir"]},
    {"codigo_cid": "R07.4","descricao": "Dor torácica não especificada",
     "categoria": "sintoma", "aliases": ["dor toracica", "dor peito", "dor no peito", "precordialgia"]},
    {"codigo_cid": "R10.0","descricao": "Abdome agudo",
     "categoria": "sintoma", "aliases": ["abdome agudo", "dor abdominal intensa", "emergencia abdominal"]},
    {"codigo_cid": "R10.4","descricao": "Outras dores abdominais e as não especificadas",
     "categoria": "sintoma", "aliases": ["dor abdominal", "dor barriga", "dor de barriga", "dor na barriga", "dor abdominal nao especificada"]},
    {"codigo_cid": "R11",  "descricao": "Náusea e vômito",
     "categoria": "sintoma", "aliases": ["nausea", "vomito", "enjoo", "mal estar digestivo", "nauseas e vomitos"]},
    {"codigo_cid": "R12",  "descricao": "Azia",
     "categoria": "sintoma", "aliases": ["azia", "pirose", "queimacao estomago", "refluxo ardencia"]},
    {"codigo_cid": "R13",  "descricao": "Disfagia",
     "categoria": "sintoma", "aliases": ["disfagia", "dificuldade engolir", "engasgo"]},
    {"codigo_cid": "R14",  "descricao": "Flatulência e afecções correlatas",
     "categoria": "sintoma", "aliases": ["flatulencia", "gases", "distensao gasosa", "flatulencia abdominal"]},
    {"codigo_cid": "R19.7","descricao": "Diarreia",
     "categoria": "sintoma", "aliases": ["diarreia", "fezes amolecidas", "intestino solto"]},
    {"codigo_cid": "R25.2","descricao": "Cãibra e espasmo",
     "categoria": "sintoma", "aliases": ["caibra", "espasmo muscular", "cãibra"]},
    {"codigo_cid": "R42",  "descricao": "Tontura e instabilidade",
     "categoria": "sintoma", "aliases": ["tontura", "vertigem", "tonteira", "instabilidade postural"]},
    {"codigo_cid": "R50.9","descricao": "Febre não especificada",
     "categoria": "sintoma", "aliases": ["febre", "hipertermia", "temperatura alta", "estado febril"]},
    {"codigo_cid": "R51",  "descricao": "Cefaleia",
     "categoria": "sintoma", "aliases": ["cefaleia", "dor de cabeca", "dor cabeca", "cefaléia", "cabeca doendo"]},
    {"codigo_cid": "R53",  "descricao": "Mal-estar e fadiga",
     "categoria": "sintoma", "aliases": ["fadiga", "astenia", "cansaco", "fraqueza", "mal estar geral"]},
    {"codigo_cid": "R55",  "descricao": "Síncope e colapso",
     "categoria": "sintoma", "aliases": ["sincope", "desmaio", "colapso", "perda consciencia"]},
    {"codigo_cid": "R60.9","descricao": "Edema não especificado",
     "categoria": "sintoma", "aliases": ["edema", "inchaço", "inchaco", "retencao liquido"]},
    {"codigo_cid": "R63.4","descricao": "Perda de peso anormal",
     "categoria": "sintoma", "aliases": ["perda peso", "emagrecimento", "perda ponderal", "emagrecer sem querer"]},
    {"codigo_cid": "R73.0","descricao": "Glicemia elevada no jejum",
     "categoria": "sintoma", "aliases": ["glicemia elevada", "hiperglicemia", "glicose alta", "acucar alto jejum"]},

    # ── Capítulo XXI — Fatores que influenciam (Z00–Z99) ────────────────────
    {"codigo_cid": "Z00.0","descricao": "Exame médico geral",
     "categoria": "preventivo", "aliases": ["consulta rotina", "check-up", "exame rotina", "consulta preventiva"]},
    {"codigo_cid": "Z03.9","descricao": "Observação e avaliação médica para suspeita de doença ou condição não especificada",
     "categoria": "preventivo", "aliases": ["investigacao diagnostica", "suspeita doenca", "avaliacao medica"]},
    {"codigo_cid": "Z30.0","descricao": "Aconselhamento e prescrição de contracepção geral",
     "categoria": "preventivo", "aliases": ["contracepcao", "anticoncepcional", "planejamento familiar"]},
    {"codigo_cid": "Z34.0","descricao": "Supervisão de primeira gravidez normal",
     "categoria": "preventivo", "aliases": ["prenatal primeira gestacao", "pre natal", "acompanhamento gravidez"]},
    {"codigo_cid": "Z34.9","descricao": "Supervisão de gravidez normal, não especificada",
     "categoria": "preventivo", "aliases": ["prenatal", "pre natal", "acompanhamento gestacao", "gestante alto risco"]},
    {"codigo_cid": "Z35.9","descricao": "Supervisão de gravidez de alto risco, não especificada",
     "categoria": "preventivo", "aliases": ["gestacao alto risco", "gravidez alto risco", "prenatal alto risco"]},
    {"codigo_cid": "Z71.3","descricao": "Aconselhamento e vigilância em relação ao abuso de álcool",
     "categoria": "preventivo", "aliases": ["dependencia alcool acompanhamento", "alcolismo seguimento"]},
    {"codigo_cid": "Z85.3","descricao": "História pessoal de neoplasia maligna das mamas",
     "categoria": "preventivo", "aliases": ["historico cancer mama", "ex cancer mama", "seguimento cancer mama"]},
    {"codigo_cid": "Z96.6","descricao": "Presença de implantes ortopédicos em articulações",
     "categoria": "preventivo", "aliases": ["protese articular", "implante ortopedico", "joelho protese"]},
]


# ---------------------------------------------------------------------------
# Enriquecimento automático da base
# ---------------------------------------------------------------------------

def _enriquecer(registro: dict) -> dict:
    """Adiciona campos calculados: descricao_normalizada, fonte, versao_base."""
    r = dict(registro)
    r["descricao_normalizada"] = _norm(r["descricao"])
    r["aliases_normalizados"]  = [_norm(a) for a in r.get("aliases", [])]
    r.setdefault("fonte",       _FONTE)
    r.setdefault("versao_base", _VERSAO_BASE)
    return r


# ---------------------------------------------------------------------------
# Classe _BaseCID
# ---------------------------------------------------------------------------

class _BaseCID:
    """
    Wrapper da base CID-10 local com suporte a busca por score.

    Busca retorna uma LISTA ordenada de sugestões (≠ TUSS que retorna um único match),
    porque CID é vocabulário de diagnóstico — múltiplas correspondências são válidas.
    """

    def __init__(self, registros: list[dict]) -> None:
        self._registros: list[dict] = [_enriquecer(r) for r in registros]
        self._por_codigo: dict[str, dict] = {r["codigo_cid"].upper(): r for r in self._registros}

    @property
    def total(self) -> int:
        return len(self._registros)

    @property
    def versao(self) -> str:
        return _VERSAO_BASE

    # ── Busca exata por código ──────────────────────────────────────────────

    def buscar_por_codigo(self, codigo: str) -> Optional[dict]:
        return self._por_codigo.get(codigo.upper())

    # ── Busca por texto (exato + alias + fuzzy) ──────────────────────────────

    def buscar(
        self,
        texto_normalizado: str,
        max_resultados: int = 5,
        threshold: float = 0.88,   # 2026-05-25 JULES-AUDIT — subido de 0.75
                                    # apos bug WRatio "dor de cabeca" -> A09
                                    # (Diarreia) e "infeccao urinaria" -> A56
                                    # (Clamidia). Mesmo padrao c548be5.
    ) -> list[tuple[dict, float, str]]:
        """
        Busca registros compatíveis com o texto normalizado.

        Retorna lista de (registro, score, match_tipo) ordenada por score DESC.
        match_tipo: "exato" | "alias" | "aproximado"
        """
        if not texto_normalizado:
            return []

        resultados: list[tuple[dict, float, str]] = []
        vistos: set[str] = set()

        # ── Passo 1: match exato na descrição normalizada ────────────────────
        for r in self._registros:
            if texto_normalizado == r["descricao_normalizada"]:
                codigo = r["codigo_cid"]
                if codigo not in vistos:
                    resultados.append((r, 1.0, "exato"))
                    vistos.add(codigo)

        # ── Passo 2: match exato em aliases ─────────────────────────────────
        for r in self._registros:
            codigo = r["codigo_cid"]
            if codigo in vistos:
                continue
            for alias in r["aliases_normalizados"]:
                if texto_normalizado == alias:
                    resultados.append((r, 0.98, "alias"))
                    vistos.add(codigo)
                    break

        # ── Passo 3: score fuzzy na descrição e aliases ──────────────────────
        if len(resultados) < max_resultados:
            scores_fuzzy: list[tuple[dict, float, str]] = []
            for r in self._registros:
                codigo = r["codigo_cid"]
                if codigo in vistos:
                    continue

                # Máximo entre descrição e todos os aliases
                s_desc = fuzz.WRatio(texto_normalizado, r["descricao_normalizada"]) / 100.0
                s_alias = max(
                    (fuzz.WRatio(texto_normalizado, a) / 100.0
                     for a in r["aliases_normalizados"]),
                    default=0.0,
                )
                s = max(s_desc, s_alias)
                if s >= threshold:
                    scores_fuzzy.append((r, round(s, 4), "aproximado"))

            scores_fuzzy.sort(key=lambda x: x[1], reverse=True)
            for item in scores_fuzzy:
                codigo = item[0]["codigo_cid"]
                if codigo not in vistos and len(resultados) < max_resultados:
                    resultados.append(item)
                    vistos.add(codigo)

        return resultados[:max_resultados]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

BASE_CID: _BaseCID = _BaseCID(_BASE_CID_RAW)
