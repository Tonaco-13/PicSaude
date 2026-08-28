"""
importar_snapshot_cbo_encaminhamento.py
========================================
DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §3 — PR `adapter`: snapshot CBO
versionado que substitui a lista local de especialidades do encaminhamento
(`catalogos-encaminhamento.js`, bloco `especialidades`/`especialidadesFonte`).

FERRAMENTA OFFLINE — nunca em runtime, nunca em deploy, nunca com fetch ao
vivo (R4/§2a, CLAUDE.md). Este script não é importado por nenhum caminho de
app/predeploy; roda manualmente, na máquina do desenvolvedor, e escreve o
resultado direto no arquivo do frontend.

A VERIFICAÇÃO CONTRA A PUBLICAÇÃO — "nada entra por memória" (§2 do desenho)
------------------------------------------------------------------------------
Os códigos abaixo foram conferidos em 2026-08-28 contra a Classificação
Brasileira de Ocupações (CBO, Portaria MTE 397/2002), cruzando múltiplas
fontes independentes que precisam estar corretas por motivo próprio (folha de
pagamento, faturamento TISS): ocupacoes.com.br, salario.com.br,
vriconsulting.com.br, numerando.com.br, codigocbo.com.br — todas concordam
nos valores abaixo.

CORREÇÕES AO RASCUNHO DO DESENHO — o §2 já previa a necessidade ("conferir
códigos na importação"); a conferência achou quatro erros reais:
  - 2252 NÃO é odontologia — é "Médicos em especialidades cirúrgicas"
    (cirurgia geral, ginecologia/obstetrícia, oftalmo, orto, otorrino,
    urologia moram AQUI, não em 2251). Odontologia é 2232.
  - Enfermagem NÃO é 2232 — é 2235 (2232 é odontologia).
  - Fisioterapia NÃO é 2231 — é 2236. (2231 "Médicos" é uma família de outro
    subgrupo — 223 "Profissionais da medicina, saúde e afins" — que coexiste
    com 225 "Profissionais da medicina", onde vivem 2251/2252; duas
    numerações de "médicos" no CBO, achado só na conferência.)
  - Fonoaudiologia NÃO é 2236 — é 2238 (2236 é fisioterapia).
  - Nutrição (2237) e psicologia (2515, o caso-guarda do §1) conferem com o
    rascunho — os únicos dois que já estavam certos.

Uso
---
    python3 backend/scripts/importar_snapshot_cbo_encaminhamento.py

Regenera o bloco entre os marcadores `// CBO:GERADO-INICIO` e
`// CBO:GERADO-FIM` em `catalogos-encaminhamento.js`. Idempotente: rodar de
novo sem mudar os dados abaixo produz o mesmo arquivo, byte a byte — é essa
propriedade que prova que o arquivo gerado É o script, não uma cópia que
pode divergir dele.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_CATALOGO_JS = _RAIZ / "catalogos-encaminhamento.js"

_MARCADOR_INICIO = "// CBO:GERADO-INICIO"
_MARCADOR_FIM = "// CBO:GERADO-FIM"

# ---------------------------------------------------------------------------
# FONTE VERIFICADA (ver docstring acima) — mudar a base é editar AQUI e
# rodar o script de novo, nunca editar o arquivo gerado à mão.
# ---------------------------------------------------------------------------

FONTE = "CBO/MTE — Portaria 397/2002"
VERSAO_CBO = "CBO 2002"
DATA_SNAPSHOT = "2026-08-28"

FAMILIAS_INCLUIDAS = {
    "2251": "Médicos clínicos",
    "2252": "Médicos em especialidades cirúrgicas",
    "2232": "Cirurgiões-dentistas",
    "2235": "Enfermeiros e afins",
    "2236": "Fisioterapeutas",
    "2237": "Nutricionistas",
    "2238": "Fonoaudiólogos",
    "2515": "Psicólogos e psicanalistas",
}

# (titulo, codigo, familia, ocupação-fonte — só documentação, não vai pro JS).
# `titulo` idêntico ao da lista local anterior nas 15 especialidades médicas
# já existentes: NUNCA renomear — é o valor que viaja no payload do
# encaminhamento e casa com `DEMO.prescritorDestino.especialidade`
# (config.js) para a demo continuar funcionando (por isso nenhuma tabela de
# alias extra é necessária aqui — ver PR description).
ESPECIALIDADES = [
    ("CARDIOLOGIA",          "2251-20", "2251", "Médico cardiologista"),
    ("CIRURGIA GERAL",       "2252-25", "2252", "Médico cirurgião geral"),
    ("DERMATOLOGIA",         "2251-35", "2251", "Médico dermatologista"),
    ("ENDOCRINOLOGIA",       "2251-55", "2251", "Médico endocrinologista e metabologista"),
    ("ENFERMAGEM",           "2235-05", "2235", "Enfermeiro"),
    ("FISIOTERAPIA",         "2236-05", "2236", "Fisioterapeuta geral"),
    ("FONOAUDIOLOGIA",       "2238-10", "2238", "Fonoaudiólogo geral"),
    ("GASTROENTEROLOGIA",    "2251-65", "2251", "Médico gastroenterologista"),
    ("GINECOLOGIA",          "2252-50", "2252", "Médico ginecologista e obstetra"),
    ("NEUROLOGIA",           "2251-12", "2251", "Médico neurologista"),
    ("NUTRIÇÃO",             "2237-10", "2237", "Nutricionista"),
    ("ODONTOLOGIA",          "2232-08", "2232", "Cirurgião dentista - clínico geral"),
    ("OFTALMOLOGIA",         "2252-65", "2252", "Médico oftalmologista"),
    ("ORTOPEDIA",            "2252-70", "2252", "Médico ortopedista e traumatologista"),
    ("OTORRINOLARINGOLOGIA", "2252-75", "2252", "Médico otorrinolaringologista"),
    ("PEDIATRIA",            "2251-24", "2251", "Médico pediatra"),
    ("PNEUMOLOGIA",          "2251-27", "2251", "Médico pneumologista"),
    ("PSICOLOGIA",           "2515-10", "2515", "Psicólogo clínico"),
    ("PSIQUIATRIA",          "2251-33", "2251", "Médico psiquiatra"),
    ("REUMATOLOGIA",         "2251-36", "2251", "Médico reumatologista"),
    ("UROLOGIA",             "2252-85", "2252", "Médico urologista"),
]


def validar() -> None:
    """As mesmas guardas que a suíte exercita, chamadas aqui para que rodar
    o script sozinho já recuse dado incoerente — sem depender de lembrar de
    rodar pytest antes de commitar."""
    titulos = [t for t, _, _, _ in ESPECIALIDADES]
    assert len(titulos) == len(set(titulos)), "título de especialidade duplicado"

    codigos = [c for _, c, _, _ in ESPECIALIDADES]
    assert len(codigos) == len(set(codigos)), "código CBO duplicado"

    for titulo, codigo, familia, _fonte_ocupacao in ESPECIALIDADES:
        assert codigo, f"{titulo}: sem código (AC1 — nenhuma entrada sem código)"
        assert familia in FAMILIAS_INCLUIDAS, (
            f"{titulo}: família {familia} não está em FAMILIAS_INCLUIDAS"
        )
        assert codigo.startswith(familia), (
            f"{titulo}: código {codigo} não começa com a família declarada {familia}"
        )

    assert "2515" in {f for _, _, f, _ in ESPECIALIDADES}, (
        "AC2 — família 2515 (psicologia) precisa estar presente: é a "
        "regressão do §1, o caso-guarda deste desenho inteiro"
    )


def _gerar_bloco_js() -> str:
    ordenadas = sorted(ESPECIALIDADES, key=lambda e: e[0])
    largura = max(len(f'"{t}",') for t, _, _, _ in ordenadas)

    linhas = [
        f"  {_MARCADOR_INICIO} — NÃO EDITAR À MÃO. Bloco regenerado por",
        "  // backend/scripts/importar_snapshot_cbo_encaminhamento.py (DESENHO-",
        "  // TYPEAHEAD-ENCAMINHAMENTO-CBO.md §3, PR `adapter`). Mudar a base é",
        "  // editar a FONTE VERIFICADA no script e rodá-lo de novo — nunca editar",
        "  // o array abaixo diretamente (drift entre script e arquivo é exatamente",
        '  // o defeito que "importação versionada" existe para evitar).',
        "  especialidades: [",
    ]
    for titulo, codigo, familia, _fonte_ocupacao in ordenadas:
        titulo_js = f'"{titulo}",'.ljust(largura)
        linhas.append(f'    {{ titulo: {titulo_js} codigo: "{codigo}", familia: "{familia}" }},')
    linhas.append("  ],")
    linhas.append("")
    linhas.append("  especialidadesFonte: {")
    linhas.append(f'    fonte: "{FONTE}",')
    linhas.append(f'    versao: "{VERSAO_CBO}",')
    linhas.append('    unidade: "entradas",')
    linhas.append(f'    data_snapshot: "{DATA_SNAPSHOT}",')
    linhas.append("    familias_incluidas: {")
    for familia, descricao in FAMILIAS_INCLUIDAS.items():
        linhas.append(f'      "{familia}": "{descricao}",')
    linhas.append("    },")
    linhas.append("  },")
    linhas.append(f"  {_MARCADOR_FIM}")
    return "\n".join(linhas)


def main() -> None:
    validar()

    texto = _CATALOGO_JS.read_text(encoding="utf-8")
    if _MARCADOR_INICIO not in texto or _MARCADOR_FIM not in texto:
        print(
            f"❌ ABORTANDO: marcadores {_MARCADOR_INICIO}/{_MARCADOR_FIM} "
            f"não encontrados em {_CATALOGO_JS}"
        )
        sys.exit(1)

    antes = texto.split(f"  {_MARCADOR_INICIO}", 1)[0]
    depois = texto.split(f"  {_MARCADOR_FIM}", 1)[1]

    novo_texto = antes + _gerar_bloco_js() + depois
    _CATALOGO_JS.write_text(novo_texto, encoding="utf-8")

    print(f"✅ {len(ESPECIALIDADES)} especialidades escritas em {_CATALOGO_JS}")
    print(f"   Famílias incluídas: {', '.join(FAMILIAS_INCLUIDAS)}")


if __name__ == "__main__":
    main()
