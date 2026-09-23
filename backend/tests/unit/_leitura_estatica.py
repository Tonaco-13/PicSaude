"""
_leitura_estatica.py — o helper que as guardas estáticas de frontend dividem.

POR QUE ELE EXISTE AGORA, E NÃO ANTES
-------------------------------------
`_corpo_da_funcao` nasceu copiado em `test_frontend_receita_viva.py` e foi
copiado de novo no exame e no encaminhamento — deliberadamente, e cada cópia
dizia por quê: promover um helper de leitura estática com dois chamadores
acoplaria arquivos de guarda que valem justamente por poder ser lidos
sozinhos. A nota do terceiro foi explícita: *"se um quarto aparecer, a conta
muda"*.

O quarto apareceu (ENG-024, o atestado). Quatro cópias de um recortador de
chaves não são mais quatro decisões locais — são quatro lugares onde o mesmo
defeito de parsing pode viver com idades diferentes. A conta mudou, e o
prefixo `_` mantém o arquivo fora da coleta do pytest.
"""
from __future__ import annotations


def corpo_da_funcao(texto: str, assinatura: str) -> str:
    """Recorta o corpo de uma função pelo balanço de chaves.

    `assinatura` é o trecho literal que abre a função (ex.:
    `"function novoEncaminhamento()"`). Levanta `AssertionError` com o nome
    procurado quando a função não fecha — erro de guarda tem de dizer o que
    procurava, não só que falhou.
    """
    ini = texto.index(assinatura)
    abriu = texto.index("{", ini)
    prof = 0
    for i in range(abriu, len(texto)):
        if texto[i] == "{":
            prof += 1
        elif texto[i] == "}":
            prof -= 1
            if prof == 0:
                return texto[abriu : i + 1]
    raise AssertionError(f"função não fecha: {assinatura!r}")
