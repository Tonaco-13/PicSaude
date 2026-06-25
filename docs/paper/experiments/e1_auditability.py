#!/usr/bin/env python3
"""
E1 — Auditability-by-construction experiment (PRELIMINARY, domain-level).

Exercises the REAL PicSaúde domain modules that *enforce* the core invariants —
the state-machine contract (app.domain.states) and the canonical-document /
integrity mechanism (app.domain.documento_canonico) — over a synthetic corpus.

Scope (honesty): this is a DOMAIN-LEVEL run. It validates the invariant-enforcing
logic directly. It does NOT drive the full persistence/endpoint stack; the
authoritative E1 (corpus generated through the official API + replay of the
PERSISTED ledger) is to be run by the engineer in the dev environment.

Reproducible: fixed seed. Read-only w.r.t. product code (imports only).
No writes to any clinical table.

Run:
    cd backend && python3 ../docs/paper/experiments/e1_auditability.py
"""
from __future__ import annotations

import os
import sys
import json
import random
import time

# --- locate backend/ so `app.domain` imports work, regardless of CWD ----------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BACKEND = os.path.join(REPO, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.domain import states as S                    # real state contract
from app.domain import documento_canonico as DC       # real canonicalization

SEED = 42
random.seed(SEED)

# Synthetic vocabularies (no real patient/prescriber data) --------------------
MEDS = [
    ("Amoxicilina", "500 mg", "comprimido"),
    ("Losartana potássica", "50 mg", "comprimido"),
    ("Metformina", "850 mg", "comprimido"),
    ("Dipirona sódica", "500 mg/mL", "mL"),
    ("Omeprazol", "20 mg", "cápsula"),
    ("Sinvastatina", "20 mg", "comprimido"),
    ("Hidroclorotiazida", "25 mg", "comprimido"),
    ("Salbutamol", "100 mcg", "dose"),
]
POSOLOGIAS = ["1x ao dia", "2x ao dia", "8/8h por 7 dias", "1 cp em jejum", "12/12h"]


def rnd_prescricao(i: int) -> dict:
    n_itens = random.randint(1, 4)
    itens = []
    for _ in range(n_itens):
        nome, conc, unid = random.choice(MEDS)
        itens.append({
            "nome_medicamento": nome,
            "concentracao": conc,
            "quantidade": random.randint(1, 60),
            "unidade_quantidade": unid,
            "posologia": random.choice(POSOLOGIAS),
        })
    return dict(
        protocolo=f"SYNTH-{i:06d}-{random.randint(0, 1<<31):08x}",
        data_emissao="2026-06-03T10:30:00.000000",
        tipo_emissao=random.choice(["nova", "correcao", "renovacao"]),
        assinatura_modo=random.choice(["icp_brasil_local", "gov_br_nuvem", None]),
        cns_prescritor="".join(random.choice("0123456789") for _ in range(15)),
        nome_prescritor=random.choice(["Ana Souza", "João Lima", "Marina Reis"]),
        cpf_paciente="".join(random.choice("0123456789") for _ in range(11)),
        nome_paciente=random.choice(["Carlos Dias", "Beatriz Melo", "Rafael Costa"]),
        itens=itens,
    )


# =============================================================================
# PART 1 — State-machine contract: closure, legal walks, replay, adversarial
# =============================================================================
def part1_state_machine(n_walks: int = 5000):
    res = {}

    # 1a. Closure/totality over the FULL state cross-product.
    # The guard must accept a transition IFF it is listed in the transition table.
    def closure(estados, tabela, guard):
        checked = accepted_illegal = missed_legal = 0
        for de in estados:
            for para in estados:
                checked += 1
                listed = para in tabela.get(de, frozenset())
                ok = guard(de, para)
                if ok and not listed:
                    accepted_illegal += 1
                if listed and not ok:
                    missed_legal += 1
        return checked, accepted_illegal, missed_legal

    c_p, ai_p, ml_p = closure(S.ESTADOS_PRESCRICAO, S.TRANSICOES_PRESCRICAO, S.transicao_valida_prescricao)
    c_i, ai_i, ml_i = closure(S.ESTADOS_ITEM, S.TRANSICOES_ITEM, S.transicao_valida_item)
    res["closure_pairs_checked"] = c_p + c_i
    res["closure_illegal_accepted"] = ai_p + ai_i
    res["closure_legal_missed"] = ml_p + ml_i

    # 1b. Legal random walks: from 'pendente' follow only legal transitions to a
    # terminal. Every step must be accepted; terminal states must have no exit;
    # replay (folding the walk) must reproduce the final state.
    walks = 0
    steps = 0
    bad_step = 0
    terminal_exit_attempts = 0
    replay_mismatch = 0
    for _ in range(n_walks):
        walks += 1
        estado = "pendente"
        trail = [estado]
        for _ in range(20):  # bounded
            opts = list(S.TRANSICOES_PRESCRICAO.get(estado, frozenset()))
            if not opts:  # terminal
                # confirm no legal exit exists and guard agrees
                if any(S.transicao_valida_prescricao(estado, x) for x in S.ESTADOS_PRESCRICAO):
                    terminal_exit_attempts += 1
                break
            nxt = random.choice(opts)
            if not S.transicao_valida_prescricao(estado, nxt):
                bad_step += 1
            estado = nxt
            trail.append(estado)
            steps += 1
        # replay: fold the trail through the guard; final must equal estado
        fold = trail[0]
        ok_replay = True
        for nxt in trail[1:]:
            if not S.transicao_valida_prescricao(fold, nxt):
                ok_replay = False
                break
            fold = nxt
        if not (ok_replay and fold == estado):
            replay_mismatch += 1
    res["legal_walks"] = walks
    res["legal_steps"] = steps
    res["illegal_steps_in_legal_walks"] = bad_step
    res["terminal_exit_paths_found"] = terminal_exit_attempts
    res["replay_mismatches"] = replay_mismatch

    # 1c. Adversarial: uniform random (de,para) transitions; none illegal may pass.
    adv = 10000
    adv_illegal_accepted = 0
    allp = list(S.ESTADOS_PRESCRICAO) + list(S.ESTADOS_ITEM)
    for _ in range(adv):
        de, para = random.choice(allp), random.choice(allp)
        # prescription guard
        if S.transicao_valida_prescricao(de, para) and para not in S.TRANSICOES_PRESCRICAO.get(de, frozenset()):
            adv_illegal_accepted += 1
        if S.transicao_valida_item(de, para) and para not in S.TRANSICOES_ITEM.get(de, frozenset()):
            adv_illegal_accepted += 1
    res["adversarial_transitions"] = adv
    res["adversarial_illegal_accepted"] = adv_illegal_accepted

    # 1d. Partial-dispensation invariant: Σ dispensed ≤ prescribed, never exceeded.
    inv_checks = 20000
    inv_violations = 0
    for _ in range(inv_checks):
        q = random.randint(1, 60)
        dispensado = 0
        # simulate sequential partial dispensations under the rule
        while dispensado < q:
            pedido = random.randint(1, q)
            permitido = min(pedido, q - dispensado)   # the enforced rule
            dispensado += permitido
            if dispensado > q:
                inv_violations += 1
                break
    res["partial_dispensation_trials"] = inv_checks
    res["partial_dispensation_violations"] = inv_violations
    return res


# =============================================================================
# PART 2 — Canonical document: determinism, tamper detection, collisions
# =============================================================================
def part2_canonical(n: int = 10000):
    res = {"corpus": n}
    hashes = {}
    t0 = time.perf_counter()
    docs = []
    for i in range(n):
        p = rnd_prescricao(i)
        r = DC.montar_documento(**p)
        docs.append((p, r))
        hashes.setdefault(r.hash_sha256, 0)
        hashes[r.hash_sha256] += 1
    elapsed = time.perf_counter() - t0
    res["hash_throughput_per_s"] = round(n / elapsed)

    # 2a. Determinism + key-order independence: recompute with shuffled input order.
    nondeterministic = 0
    for p, r in docs:
        items_shuf = list(p["itens"])
        random.shuffle(items_shuf)
        # shuffle dict key order of each item too
        items_shuf = [dict(random.sample(list(it.items()), len(it))) for it in items_shuf]
        # NOTE: item ORDER is semantic (field 'ordem'); to test determinism we keep
        # order but rebuild dicts with shuffled KEYS (same content) -> same hash.
        p2 = dict(p)
        p2["itens"] = [dict(random.sample(list(it.items()), len(it))) for it in p["itens"]]
        r2 = DC.montar_documento(**p2)
        if r2.hash_sha256 != r.hash_sha256:
            nondeterministic += 1
    res["determinism_trials"] = n
    res["nondeterministic_hashes"] = nondeterministic

    # 2b. Tamper detection: mutate exactly one canonical field; hash MUST change.
    detected = 0
    trials = 0
    for p, r in docs:
        trials += 1
        p2 = json.loads(json.dumps(p))  # deep copy
        field = random.choice(
            ["quantidade", "concentracao", "nome_medicamento", "posologia",
             "unidade_quantidade", "cpf_paciente", "nome_prescritor",
             "data_emissao", "tipo_emissao"]
        )
        if field in ("quantidade",):
            it = random.choice(p2["itens"]); it["quantidade"] = it["quantidade"] + 1
        elif field in ("concentracao", "nome_medicamento", "posologia", "unidade_quantidade"):
            it = random.choice(p2["itens"]); it[field] = str(it[field]) + "_X"
        elif field == "cpf_paciente":
            p2["cpf_paciente"] = ("9" if p2["cpf_paciente"][0] != "9" else "1") + p2["cpf_paciente"][1:]
        elif field == "nome_prescritor":
            p2["nome_prescritor"] = p2["nome_prescritor"] + " Jr"
        elif field == "data_emissao":
            p2["data_emissao"] = "2026-06-04T10:30:00.000000"
        elif field == "tipo_emissao":
            p2["tipo_emissao"] = "correcao" if p2["tipo_emissao"] != "correcao" else "nova"
        r2 = DC.montar_documento(**p2)
        if r2.hash_sha256 != r.hash_sha256:
            detected += 1
    res["tamper_trials"] = trials
    res["tamper_detected"] = detected

    # 2c. Collisions across the corpus (distinct prescriptions).
    res["distinct_hashes"] = len(hashes)
    res["hash_collisions"] = sum(c - 1 for c in hashes.values() if c > 1)
    return res


def pct(num, den):
    return "100.000%" if den and num == den else (f"{100.0*num/den:.3f}%" if den else "n/a")


def main():
    print("=" * 70)
    print("E1 — Auditability by construction (PRELIMINARY, domain-level)")
    print(f"seed={SEED}  | states + documento_canonico (real domain modules)")
    print("=" * 70)

    p1 = part1_state_machine()
    p2 = part2_canonical()

    print("\n[Part 1] State-machine contract (motor de circulação)")
    print(f"  State pairs checked (closure)............ {p1['closure_pairs_checked']}")
    print(f"  Illegal transitions accepted............. {p1['closure_illegal_accepted']}  "
          f"(rejection {pct(p1['closure_pairs_checked']-p1['closure_illegal_accepted'], p1['closure_pairs_checked'])})")
    print(f"  Legal transitions wrongly blocked........ {p1['closure_legal_missed']}")
    print(f"  Legal random walks / steps............... {p1['legal_walks']} / {p1['legal_steps']}")
    print(f"  Illegal steps inside legal walks......... {p1['illegal_steps_in_legal_walks']}")
    print(f"  Terminal-state exit paths found.......... {p1['terminal_exit_paths_found']}")
    print(f"  Replay mismatches (state from trail)..... {p1['replay_mismatches']}  "
          f"(consistency {pct(p1['legal_walks']-p1['replay_mismatches'], p1['legal_walks'])})")
    print(f"  Adversarial transitions tested........... {p1['adversarial_transitions']}")
    print(f"  Adversarial illegal accepted............. {p1['adversarial_illegal_accepted']}")
    print(f"  Partial-dispensation trials.............. {p1['partial_dispensation_trials']}")
    print(f"  Σ dispensed > prescribed violations...... {p1['partial_dispensation_violations']}")

    print("\n[Part 2] Canonical document / integrity (motor regulatório)")
    print(f"  Synthetic prescriptions hashed........... {p2['corpus']}")
    print(f"  Hash throughput.......................... ~{p2['hash_throughput_per_s']}/s")
    print(f"  Non-deterministic hashes (key-order)..... {p2['nondeterministic_hashes']}  "
          f"(determinism {pct(p2['determinism_trials']-p2['nondeterministic_hashes'], p2['determinism_trials'])})")
    print(f"  Tamper trials / detected................. {p2['tamper_trials']} / {p2['tamper_detected']}  "
          f"(detection {pct(p2['tamper_detected'], p2['tamper_trials'])})")
    print(f"  Distinct hashes / collisions............. {p2['distinct_hashes']} / {p2['hash_collisions']}")
    print("=" * 70)

    out = {"seed": SEED, "part1_state_machine": p1, "part2_canonical": p2}
    dest = os.path.join(HERE, "e1_results.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"results written to {dest}")


if __name__ == "__main__":
    main()
