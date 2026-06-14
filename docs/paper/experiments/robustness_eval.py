#!/usr/bin/env python3
"""Reproduz a Seção de Avaliação de Robustez do paper CEBEB (checks A, B, E).

Rodar (de qualquer cwd, com a venv do backend):
    backend/.venv/bin/python docs/paper/experiments/robustness_eval.py

A — verificação formal exaustiva das 7 máquinas de estado (78 estados / 99 transições).
B — tamper-evidence + determinismo do hash do documento canônico.
E — auditoria de neutralidade dos 5 endpoints GET /public/* (nenhum projeta campo clínico).

C (96 cenários de autorização) e D (divergência dual-DB) rodam via pytest contra
PostgreSQL — ver README do repositório. Não há dado clínico real aqui.
"""
import importlib
import os
import re
import sys

_BACKEND = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
sys.path.insert(0, _BACKEND)


def check_A_state_machines() -> None:
    FAM = {
        "prescricao": ("states", ["PRESCRICAO", "ITEM"]),
        "pedido_exame": ("states_exame", ["PEDIDO_EXAME", "ITEM_EXAME"]),
        "laudo": ("states_laudo", ["LAUDO", "ITEM_LAUDO"]),
        "agendamento": ("states_agendamento", ["AGENDAMENTO"]),
        "circulacao": ("states_circulacao_diagnostica", ["CIRCULACAO_DIAGNOSTICA"]),
        "encaminhamento": ("states_encaminhamento", ["ENCAMINHAMENTO", "ITEM_ENCAMINHAMENTO"]),
        "contrarreferencia": ("states_contrarreferencia", ["CONTRARREFERENCIA"]),
    }
    nm = ns = nt = 0
    v1 = v2 = v3 = v4 = 0
    nao_absorventes = []
    for _, (mod_name, sufs) in FAM.items():
        mod = importlib.import_module(f"app.domain.{mod_name}")
        for suf in sufs:
            E = getattr(mod, f"ESTADOS_{suf}")
            T = getattr(mod, f"ESTADOS_TERMINAIS_{suf}")
            Tr = getattr(mod, f"TRANSICOES_{suf}")
            nm += 1
            ns += len(E)
            nt += sum(len(d) for d in Tr.values())
            v1 += sum(1 for de in Tr for p in Tr[de] if p not in E)
            for t in T:
                if Tr.get(t):
                    v2 += 1
                    nao_absorventes.append(f"{suf}:{t}->{sorted(Tr[t])}")
                if t not in E:
                    v3 += 1
            v4 += sum(1 for s in E if s not in T and not Tr.get(s))
    print("== A: verificação formal das máquinas de estado ==")
    print(f"   máquinas={nm}  estados={ns}  transições={nt}")
    print(f"   P1 destino-válido: {'OK' if not v1 else v1}  "
          f"P2 terminal-absorvente: {'OK' if not v2 else f'{v2} achados'}  "
          f"P3 terminais⊆estados: {'OK' if not v3 else v3}  "
          f"P4 sem-becos: {'OK' if not v4 else v4}")
    for x in nao_absorventes:
        print(f"   [P2 achado] {x}")
    assert (ns, nt, v1, v3, v4) == (78, 99, 0, 0, 0)


def check_B_hash() -> None:
    from app.domain.documento_canonico import montar_documento
    base = dict(protocolo="proto-EXP", data_emissao="2026-06-14", tipo_emissao="novo",
                assinatura_modo="stub", cns_prescritor="111111111111111",
                nome_prescritor="DR X", cpf_paciente="44455566677", nome_paciente="PAC Y",
                itens=[{"nome_medicamento": "AMOX", "concentracao": "500mg", "quantidade": 10,
                        "unidade_quantidade": "comprimido", "posologia": "1x8h"}])
    h0 = montar_documento(**base).hash_sha256
    det = all(montar_documento(**base).hash_sha256 == h0 for _ in range(1000))
    topo = ["protocolo", "data_emissao", "tipo_emissao", "cns_prescritor",
            "nome_prescritor", "cpf_paciente", "nome_paciente"]
    mud = sum(1 for c in topo if montar_documento(**{**base, c: base[c] + "_X"}).hash_sha256 != h0)
    itc = ["nome_medicamento", "concentracao", "quantidade", "unidade_quantidade", "posologia"]
    mit = 0
    for c in itc:
        it = {**base["itens"][0], c: str(base["itens"][0][c]) + "_X"}
        if montar_documento(**{**base, "itens": [it]}).hash_sha256 != h0:
            mit += 1
    print("\n== B: integridade do documento (hash) ==")
    print(f"   determinismo (1000x): {'idêntico' if det else 'DIVERGIU'}")
    print(f"   tamper-evidence: {mud + mit}/{len(topo) + len(itc)} campos alteram o digest")
    assert det and (mud + mit) == 12


def check_E_public_neutrality() -> None:
    src = open(os.path.join(_BACKEND, "app", "routers", "publico.py")).read()
    clin = ["medicamento", "nome_medicamento", "concentracao", "dose", "nome_exame",
            "codigo_tuss", "conclusao", "especialidade", "procedimento",
            "conteudo_clinico", "cid", "justificativa", "resultado", "prioridade"]
    blocks = re.findall(r'def (consulta_publica\w*)\(.*?\n(.*?)(?=\n@router|\Z)', src, re.S)
    vaza = 0
    print("\n== E: neutralidade dos endpoints /public/* ==")
    for nome, corpo in blocks:
        corpo = re.sub(r'""".*?"""', '', corpo, flags=re.S)  # remove docstring
        sql_ret = "\n".join(l for l in corpo.splitlines()
                            if re.search(r'SELECT|FROM|return|".*":', l, re.I))
        hit = [c for c in clin if re.search(rf'\b{c}\b', sql_ret)]
        print(f"   {nome:<36} {'projeta:'+str(hit) if hit else 'NEUTRO'}")
        vaza += bool(hit)
    print(f"   endpoints que projetam clínica: {vaza}/{len(blocks)}")
    assert vaza == 0 and len(blocks) == 5


if __name__ == "__main__":
    check_A_state_machines()
    check_B_hash()
    check_E_public_neutrality()
    print("\nOK — resultados conferem com a Table III do paper.")
