#!/usr/bin/env python3
"""Conta estados e transições das 7 famílias de objeto sanitário — fonte do
número "78 estados / 99 transições" da §VI do paper CEBEB.

Rodar com a venv do backend (de qualquer diretório):
    backend/.venv/bin/python docs/paper/count_states.py

Conta SOMENTE as máquinas de objeto e de item das 7 famílias. Exclui o conjunto
auxiliar ESTADOS_SOLICITACAO_RENOVACAO (solicitação de renovação não é uma das 7
famílias e não tem dict de transições — incluí-lo daria o par assimétrico 82/99).
"""
import importlib
import os
import sys

# torna `app.domain.*` importável a partir de qualquer cwd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

MODULES = {
    "prescricao": "states",
    "pedido_exame": "states_exame",
    "laudo": "states_laudo",
    "agendamento": "states_agendamento",
    "circulacao": "states_circulacao_diagnostica",
    "encaminhamento": "states_encaminhamento",
    "contrarreferencia": "states_contrarreferencia",
}

# conjuntos de estado que NÃO são máquina de objeto/item das 7 famílias
EXCLUIR = {"ESTADOS_SOLICITACAO_RENOVACAO"}


def main() -> None:
    total_estados = total_transicoes = 0
    for nome, mod_name in MODULES.items():
        mod = importlib.import_module(f"app.domain.{mod_name}")
        estados = transicoes = 0
        for k, v in vars(mod).items():
            if (isinstance(v, frozenset) and k.startswith("ESTADOS_")
                    and "TERMINAIS" not in k and k not in EXCLUIR):
                estados += len(v)
            if isinstance(v, dict) and k.startswith("TRANSICOES_"):
                transicoes += sum(len(d) for d in v.values())
        print(f"{nome:<18} estados={estados:>3}  transicoes={transicoes:>3}")
        total_estados += estados
        total_transicoes += transicoes
    print("-" * 44)
    print(f"{'TOTAL':<18} estados={total_estados:>3}  transicoes={total_transicoes:>3}")
    assert total_estados == 78, total_estados
    assert total_transicoes == 99, total_transicoes
    print("\nOK — confere com o paper (78 estados / 99 transições).")


if __name__ == "__main__":
    main()
