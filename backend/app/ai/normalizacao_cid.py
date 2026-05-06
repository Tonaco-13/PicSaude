"""
normalizacao_cid.py
===================
Normalização leve de texto clínico livre para busca CID — Ticket 33.

A linguagem diagnóstica é mais caótica que a farmacêutica ou de exames:
o médico (e o sistema) recebe "pressao alta", "dor barriga", "acucar alto".
Este módulo converte linguagem coloquial em vocabulário clínico pesquisável.

PIPELINE
--------
    1. Lowercase
    2. Remoção de acentos
    3. Remoção de pontuação/ruído (preserva hífen — usado no CID)
    4. Expansão coloquial → termos clínicos
    5. Normalização de espaços

⚠️  Este módulo NÃO classifica nem escolhe CID.
    Apenas melhora a qualidade da busca subsequente.
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Mapeamentos coloquial → clínico
# ---------------------------------------------------------------------------
# Cada tupla: (padrão_regex, expansão_clínica)
# Aplicados em sequência — ordem importa para padrões mais específicos primeiro.
# ---------------------------------------------------------------------------

_EXPANSOES: list[tuple[str, str]] = [
    # ── Cardiovascular ────────────────────────────────────────────────────
    (r"\bpressao\s+alta\b",           "hipertensao arterial"),
    (r"\bpress[ao]+\s+alta\b",        "hipertensao arterial"),
    (r"\bhta\b",                      "hipertensao arterial"),
    (r"\bhas\b",                      "hipertensao arterial sistemica"),
    (r"\bpressao\s+baixa\b",          "hipotensao arterial"),
    (r"\bpress[ao]+\s+baixa\b",       "hipotensao arterial"),
    (r"\binfarto\b",                  "infarto agudo miocardio"),
    (r"\biam\b",                      "infarto agudo miocardio"),
    (r"\bderrame\b",                  "acidente vascular cerebral"),
    (r"\bavc\b",                      "acidente vascular cerebral"),
    (r"\bave\b",                      "acidente vascular cerebral"),
    (r"\bic\b",                       "insuficiencia cardiaca"),
    (r"\bicf[ec]?\b",                 "insuficiencia cardiaca"),
    (r"\bcorao\b",                    "coracao"),
    (r"\barritmia\b",                 "arritmia cardiaca"),
    (r"\bfibrilacao\s+atrial\b",      "fibrilacao atrial"),
    (r"\bfa\b",                       "fibrilacao atrial"),
    (r"\bangina\b",                   "angina pectoris"),
    (r"\bdoenca\s+coronar[ia]+na\b",  "doenca arterial coronariana"),
    (r"\bdac\b",                      "doenca arterial coronariana"),

    # ── Endócrino / Metabólico ───────────────────────────────────────────
    (r"\bacucar\s+alto\b",            "diabetes mellitus hiperglicemia"),
    (r"\bacucar\s+elevado\b",         "diabetes mellitus hiperglicemia"),
    (r"\bglicose\s+alta\b",           "diabetes mellitus hiperglicemia"),
    (r"\bdiabete\b",                  "diabetes mellitus"),
    (r"\bdm\s*1\b",                   "diabetes mellitus tipo 1"),
    (r"\bdm\s*2\b",                   "diabetes mellitus tipo 2"),
    (r"\bdiabetes\s+tipo\s*1\b",      "diabetes mellitus tipo 1"),
    (r"\bdiabetes\s+tipo\s*2\b",      "diabetes mellitus tipo 2"),
    (r"\btiroid[e]?\b",               "tireoide"),
    (r"\bhipo\s*tiroid[e]?\b",        "hipotireoidismo"),
    (r"\bhiper\s*tiroid[e]?\b",       "hipertireoidismo"),
    (r"\bgordo\s+demais\b",           "obesidade"),
    (r"\bobesidad[e]?\b",             "obesidade"),
    (r"\bcolesterol\s+alto\b",        "hiperlipidemia dislipidemia hipercolesterolemia"),
    (r"\bdislipidemia\b",             "hiperlipidemia dislipidemia"),
    (r"\bgota\b",                     "gota hiperuricemia"),

    # ── Respiratório ────────────────────────────────────────────────────
    (r"\bfalta\s+ar\b",               "dispneia"),
    (r"\bfalta\s+de\s+ar\b",          "dispneia"),
    (r"\bfalta\s+de\s+folego\b",      "dispneia"),
    (r"\bchiadeira\b",                "sibilancia asma"),
    (r"\bfalta\s+de\s+ar\b",          "dispneia"),
    (r"\bdpoc\b",                     "doenca pulmonar obstrutiva cronica"),
    (r"\benfisema\b",                 "doenca pulmonar obstrutiva cronica enfisema"),
    (r"\bbronquit[e]?\b",             "bronquite"),
    (r"\bcovid\b",                    "covid-19 coronavirus"),
    (r"\bcoronavirus\b",              "covid-19 coronavirus"),
    (r"\bgrippe?\b",                  "influenza gripe"),
    (r"\bgrip[e]?\b",                 "influenza gripe"),
    (r"\brinit[e]?\b",                "rinite"),
    (r"\bsinusit[e]?\b",              "sinusite"),
    (r"\btosse\b",                    "tosse"),
    (r"\bpneuomonia\b",               "pneumonia"),
    (r"\btuberculose\b",              "tuberculose"),
    (r"\btb\b",                       "tuberculose"),

    # ── Digestivo ───────────────────────────────────────────────────────
    (r"\bdor\s+barriga\b",            "dor abdominal"),
    (r"\bdor\s+de\s+barriga\b",       "dor abdominal"),
    (r"\bdor\s+estomago\b",           "dor abdominal epigastrica"),
    (r"\bdor\s+no\s+estomago\b",      "dor abdominal epigastrica"),
    (r"\bdor\s+na\s+barriga\b",       "dor abdominal"),
    (r"\bbarriga\s+inchada\b",        "distensao abdominal"),
    (r"\bgastrit[e]?\b",              "gastrite"),
    (r"\bulcer[a]?\b",                "ulcera peptica"),
    (r"\bulcera\s+estomago\b",        "ulcera peptica gastrica"),
    (r"\bdiarre[ia]+\b",              "diarreia"),
    (r"\bvomit[o]+\b",                "vomito"),
    (r"\bnause[a]+\b",                "nausea"),
    (r"\bhemorroid[a]+\b",            "hemorroida doenca hemorroidaria"),
    (r"\bintestino\s+preso\b",        "constipacao intestinal"),
    (r"\bprisao\s+de\s+ventre\b",     "constipacao intestinal"),
    (r"\bfigado\b",                   "hepatica hepatite figado"),
    (r"\bhepatit[e]?\b",              "hepatite"),
    (r"\bcalculo\s+biliares?\b",      "colelitiase calculo biliar"),
    (r"\bpedra\s+vesic[ula]+\b",      "colelitiase calculo vesicular"),
    (r"\bapendicit[e]?\b",            "apendicite"),
    (r"\bcrohn\b",                    "doenca crohn"),
    (r"\bretocol[it]+e\b",            "retocolite ulcerativa"),
    (r"\bpancreatit[e]?\b",           "pancreatite"),

    # ── Genitourinário / Renal ──────────────────────────────────────────
    (r"\binfeccao\s+urina\b",         "infeccao trato urinario"),
    (r"\binfeccao\s+de\s+urina\b",    "infeccao trato urinario"),
    (r"\bitu\b",                      "infeccao trato urinario"),
    (r"\bpedra\s+rim\b",              "cálculo renal nefrolitiase"),
    (r"\bpedra\s+no\s+rim\b",         "calculose renal nefrolitiase"),
    (r"\bcalculo\s+renal\b",          "calculose renal nefrolitiase"),
    (r"\birc\b",                      "insuficiencia renal cronica"),
    (r"\bdrc\b",                      "doenca renal cronica"),
    (r"\brim\b",                      "renal rim nefropatia"),
    (r"\bprostata\b",                 "prostata"),
    (r"\bhiperplasia\s+prostata\b",   "hiperplasia prostatica benigna"),
    (r"\bhpb\b",                      "hiperplasia prostatica benigna"),

    # ── Musculoesquelético ───────────────────────────────────────────────
    (r"\bdor\s+coluna\b",             "dorsalgia lombalgia"),
    (r"\bdor\s+nas\s+costas\b",       "dorsalgia lombalgia"),
    (r"\bdor\s+lombar\b",             "lombalgia dorsalgia"),
    (r"\bdor\s+cervical\b",           "cervicalgia"),
    (r"\bdor\s+no\s+pescoco\b",       "cervicalgia"),
    (r"\bcoluna\b",                   "coluna vertebral"),
    (r"\bartrit[e]?\b",               "artrite"),
    (r"\bartros[e]?\b",               "artrose osteoartrose"),
    (r"\bosteoporose\b",              "osteoporose"),
    (r"\bfibromialgia\b",             "fibromialgia"),
    (r"\bciatic[a]?\b",               "ciatica"),
    (r"\btendenit[e]?\b",             "tendinite"),

    # ── Neurológico ─────────────────────────────────────────────────────
    (r"\bdor\s+cabeca\b",             "cefaleia"),
    (r"\bdor\s+de\s+cabeca\b",        "cefaleia"),
    (r"\benxaqueca\b",                "enxaqueca migranea cefaleia"),
    (r"\bmigraen[a]?\b",              "migranea cefaleia"),
    (r"\btontura\b",                  "vertigem tontura"),
    (r"\bvertigem\b",                 "vertigem"),
    (r"\bdesmaio\b",                  "sincope desmaio"),
    (r"\bconvulsao\b",                "epilepsia convulsao"),
    (r"\bepileps[ia]+\b",             "epilepsia"),
    (r"\bparkinson\b",                "doenca parkinson"),
    (r"\balzheimer\b",                "doenca alzheimer demencia"),
    (r"\bdemenci[a]?\b",              "demencia"),
    (r"\bdormencia\b",                "parestesia dormencia"),
    (r"\bformigamento\b",             "parestesia formigamento"),

    # ── Saúde mental ────────────────────────────────────────────────────
    (r"\bdepressao\b",                "depressao transtorno depressivo"),
    (r"\bansiedad[e]?\b",             "ansiedade transtorno ansioso"),
    (r"\bpanico\b",                   "transtorno panico ansiedade"),
    (r"\binsonia\b",                  "insonia disturbio sono"),
    (r"\bdisturbio\s+sono\b",         "insonia disturbio sono"),
    (r"\bpsicose\b",                  "psicose esquizofrenia"),
    (r"\besquizofrenia\b",            "esquizofrenia"),
    (r"\bbipolar\b",                  "transtorno bipolar"),
    (r"\btoc\b",                      "transtorno obsessivo compulsivo"),

    # ── Pele ────────────────────────────────────────────────────────────
    (r"\bcoci[ei]ra\b",               "prurido"),
    (r"\bcoceira\b",                  "prurido"),
    (r"\becze[m]+a\b",                "eczema dermatite"),
    (r"\bpsorias[e]?\b",              "psoriase"),
    (r"\bacne\b",                     "acne"),
    (r"\bmancha\s+pele\b",            "lesao pele dermatose"),
    (r"\bcandidias[e]?\b",            "candidose candidiase"),
    (r"\bherpes\b",                   "herpes"),
    (r"\bverrug[a]+\b",               "verruga"),

    # ── Infectologia / Tropical ─────────────────────────────────────────
    (r"\bdengue\b",                   "dengue"),
    (r"\bzika\b",                     "infeccao zika"),
    (r"\bchikungunya\b",              "febre chikungunya"),
    (r"\besquistoss[o]+m[o]+se\b",    "esquistossomose"),
    (r"\bleishmani[ao]+se\b",         "leishmaniose"),
    (r"\bhiv\b",                      "infeccao hiv aids"),
    (r"\baids\b",                     "infeccao hiv aids"),
    (r"\bsifilis\b",                  "sifilis"),
    (r"\bleptospirose\b",             "leptospirose"),
    (r"\bhans[e]+niase\b",            "hanseniase lepra"),
    (r"\blepra\b",                    "hanseniase lepra"),
    (r"\bmalaria\b",                  "malaria"),
    (r"\bfebre\s+amarela\b",          "febre amarela"),

    # ── Gineco / Obstétrico ──────────────────────────────────────────────
    (r"\bgestant[e]?\b",              "gravidez gestacao"),
    (r"\bgravida\b",                  "gestacao gravidez"),
    (r"\bgravidez\b",                 "gestacao gravidez"),
    (r"\bgestacao\b",                 "gestacao gravidez"),
    (r"\bpre.eclampsia\b",            "pre-eclampsia hipertensao gestacional"),
    (r"\bprematurid[a]+de\b",         "parto prematuro"),
    (r"\baborto\b",                   "aborto perda gestacional"),
    (r"\bmenopausa\b",                "menopausa climaterio"),
    (r"\bendomet[r]+ios[e]?\b",       "endometriose"),
    (r"\bovario\s+policistic[o]?\b",  "ovarios policisticos sop"),
    (r"\bsop\b",                      "ovarios policisticos sop"),
    (r"\bcancer\s+mama\b",            "neoplasia maligna mama"),
    (r"\bcancer\s+colo\b",            "neoplasia maligna colo utero"),

    # ── Sintomas gerais ──────────────────────────────────────────────────
    (r"\bfebre\b",                    "febre hipertermia"),
    (r"\bcancer\b",                   "neoplasia maligna"),
    (r"\btumor\b",                    "neoplasia tumor"),
    (r"\balergia\b",                  "alergia reacao alergica"),
    (r"\banemia\b",                   "anemia"),
    (r"\bfraqueza\b",                 "astenia fraqueza"),
    (r"\bcansaco\b",                  "fadiga astenia"),
    (r"\bperda\s+peso\b",             "emagrecimento perda peso"),
    (r"\bedema\b",                    "edema"),
    (r"\binchaco\b",                  "edema inchaço"),
    (r"\binchaço\b",                  "edema"),
    (r"\bsangramento\b",              "hemorragia sangramento"),
    (r"\bhemorragia\b",               "hemorragia"),
    (r"\bdor\s+peito\b",              "dor toracica precordial"),
    (r"\bdor\s+no\s+peito\b",         "dor toracica precordial"),
]


def normalizar_texto_clinico(texto: str) -> str:
    """
    Normaliza texto clínico livre para busca CID.

    Mais agressivo que normalização de TUSS/Exames — linguagem diagnóstica
    é mais caótica (coloquial, regional, abreviada).

    Pipeline:
        1. Lowercase
        2. Remoção de acentos
        3. Remoção de pontuação (preserva hífen — usado em CID: R10.4)
        4. Expansão coloquial → termos clínicos
        5. Normalização de espaços

    Returns:
        Texto normalizado para lookup na base CID.
    """
    if not texto:
        return ""

    t = texto.lower().strip()

    # Remoção de acentos
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")

    # Remove pontuação preservando hífen (ex: "R10.4" vira "R10 4" — ok para busca)
    t = re.sub(r"[^\w\s\-]", " ", t)

    # Expansão coloquial → clínico
    for padrao, expansao in _EXPANSOES:
        t = re.sub(padrao, expansao, t)

    # Normaliza espaços
    t = re.sub(r"\s+", " ", t).strip()

    return t
