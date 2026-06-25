# A Transparent, Explainable Regulatory Engine for Digital Prescription Authorization in Primary Care

*Working draft v1 — CBEB 2026 (Trabalho B, "regulatory engine" cut). English. IEEE format target (full paper, 4–8 pp). Submission deadline 30/06/2026.*

> **Drafting notes (remove before submission):**
> - Scope is the **regulatory engine** only. The immutable ledger / custody chain appear as *substrate*, never as the claimed contribution. The auditability-and-anti-commercialization argument is reserved for the companion architecture paper (ICSA) — do not develop it here beyond a one-line pointer.
> - Honesty guards (from the canonical narrative): signature/ICP-Brasil = *declared design / open work* (never "validated"); reference bases = *MVP synthetic subset*; evaluation = *executable conformance*, not clinical field validation. Never write "decentralized/blockchain" — the engine is *stateless and deterministic*.
> - `[TODO]` marks where Fabiano/team must supply real data (author block, formalized interview consent/quotes, final reference list).

---

**Authors:** `[TODO: author line — Bruno Henrique Aragão Konig; Nicole Leise Andrade Serra; Heloisa Pessoa Tseng; Fabiano Tonaco Borges; + co-authors. IEEE 5-line affiliation block per author. No titles (Dr./Prof.).]`

Affiliation: Universidade Federal de Pernambuco (UFPE), Recife, Brazil.

---

## Abstract

Digital prescribing is spreading rapidly across public health systems, yet the dominant model — static PDF documents — provides neither verifiable authorization nor an explanation of the rules a prescription was checked against. This weakens pharmacovigilance, complicates auditing, and leaves room for fraud such as the reuse of a single digital document across multiple pharmacies. We present a transparent, explainable regulatory engine that authorizes digital prescriptions as they are emitted, operating over an immutable trail of clinical-operational events. The engine is stateless and deterministic: it applies a sequence of six independent validation layers — structural, integrity, professional-council conformance (CFM Resolution 2.299/2021), signature metadata, certificate verification, and prescriber-identity cross-checking against the national health-establishment registry (CNES) — and every check returns a structured, human-readable justification rather than an opaque verdict. Clinical terminology (medications, diagnoses, exams) is resolved through a deterministic exact–alias–fuzzy pipeline with defensive thresholds that surface low-confidence matches as explicit alerts. We instantiate the engine in PicSaúde, an open reference implementation running on synthetic data, and evaluate it through executable conformance over scenario-based test suites aligned with Brazilian pharmaceutical-control regulation. We position the system as an auditable reference implementation, not a production clinical platform, and we declare its open boundaries, including end-to-end ICP-Brasil signing.

*Keywords—* digital prescription; clinical decision support; explainable validation; primary health care; regulatory compliance; health informatics

---

## I. Introduction

`[Para 1 — broader area]` Primary health care is the entry point of most public health systems and the setting where the largest volume of prescriptions is issued. As prescribing moves from paper to digital media, the clinical and regulatory stakes of getting the digital workflow right rise accordingly: a prescription is simultaneously a clinical instruction, a legal document, and an event that must be traceable for pharmacovigilance and auditing.

`[Para 2 — the gap]` The prevailing digital model, however, reproduces paper as a static artifact: a signed PDF that is emailed or sent over messaging apps. This model offers no machine-verifiable authorization (was the prescriber entitled to prescribe this?), no explanation of which rules were applied, and no built-in traceability of what later happened to the document. Two consequences follow. First, the same PDF can be presented at several pharmacies, enabling duplicate dispensing of controlled substances. Second, the rules that should govern a prescription — controlled-substance classes, signature requirements, prescriber eligibility — are either absent or buried in opaque, per-system application logic that neither the clinician nor an auditor can inspect. Semi-structured interviews we conducted with primary-care professionals `[TODO: formalize — Danilo (UBS); Bianca Carvalho de Assis, family physician, USF+ Vila Arraes]` corroborated both: practitioners reported duplicate-document risk through PDF sharing, persistent fragmentation across non-interoperable systems, and the absence of any feedback loop from dispensing back to the prescriber.

`[Para 3 — proposed work]` We address the authorization-and-explainability gap with a regulatory engine that validates a digital prescription at the moment of emission and at the point of dispensing, operating over an immutable event trail. The engine is transparent by design: each decision is decomposed into independent checks, and each check returns a structured justification. It is instantiated in PicSaúde, an open reference implementation that runs entirely on synthetic data. We frame the system explicitly as an auditable reference implementation — not a production clinical platform — and we declare its open boundaries.

**Research objectives.**

- To make prescription *authorization* machine-verifiable and *explainable*, rather than implicit in a static document.
- To align the validation rules with current Brazilian pharmaceutical-control regulation in an inspectable form.
- To resolve clinical terminology robustly while surfacing uncertainty as explicit, auditable alerts.

**Major contributions.**

- A stateless, deterministic **six-layer validation engine** in which every check yields a structured, human-readable justification, making authorization decisions auditable rather than opaque.
- A **prescriber-identity verification by name** against the national CNES registry (not by national-ID number), anchored to an immutable identity string, with graded hard/soft failures.
- An **explainable terminology-resolution pipeline** (exact → alias → fuzzy) with defensive thresholds and structured low-confidence alerts, and a reported design correction motivated by false positives.
- An **open reference implementation** over synthetic data, evaluated by executable conformance against regulation-aligned scenarios.

`[Organization paragraph]` Section II reviews regulatory context and related work. Section III describes the engine. Section IV reports the conformance evaluation. Section V discusses limitations, and Section VI concludes.

## II. Background and Related Work

`[TODO: expand into critical comparison; CBEB does not mandate the 12–15-reference count that some venues do, but a solid 10–15 grounded references strengthen the paper.]`

**Regulatory context.** Brazilian digital prescribing is governed by CFM Resolution 2.299/2021 (requirements and signature levels for digital prescriptions) and by a tightening control regime for special-control substances: Ordinance SVS/MS 344/1998 and its lists, RDC Anvisa 471/2021 (systemic retinoids), and, most recently, RDC Anvisa 1.000/2025, which establishes the National Prescription Control System (SNCR) with a compliance horizon in 2026. Qualified electronic signatures rest on the ICP-Brasil public-key infrastructure. This regulatory density is precisely what an opaque PDF cannot express and what an explainable engine can.

**Explainable clinical decision support.** `[TODO: 3–5 refs — rule-based vs ML CDSS; the case for transparency/explainability in safety-critical health software; alert fatigue and the value of justified alerts.]`

**Terminology resolution.** `[TODO: 2–3 refs — approximate string matching in clinical terminology normalization; rapidfuzz/Levenshtein-family methods; risks of false positives.]`

**Event-sourced clinical records (substrate).** The engine operates over an append-only event trail; event sourcing as a substrate for traceable records is treated, with the system's auditability and anti-commercialization properties, in a companion architecture paper. Here it is background, not contribution. `[TODO: 1–2 refs on event sourcing / immutable audit logs.]`

## III. Materials and Methods

### A. System context

PicSaúde models clinical documents as *sanitary objects* with a global identifier, an explicit state machine, an append-only event ledger, and a custody chain. Objects are immutable after emission; corrections and renewals are new derived objects. The regulatory engine described here consumes this substrate but does not modify it: it reads the prescription and its canonical representation and returns a validation report. Implementation is in Python (FastAPI, SQLAlchemy); all data are synthetic and the system runs in an enforced demonstration mode.

### B. The six-layer validation engine

A prescription is validated by six independent layers; each layer produces a set of checks, and each check is a record of the form `(ok, detail, applicable)`, where *detail* is a human-readable justification and *applicable* marks checks that do not apply to a given prescription type (e.g., integrity checks on a paper-only emission). The engine is stateless and deterministic: identical inputs yield identical reports.

1. **Structural** — existence of the prescription, recognized prescription and item states, presence of at least one item.
2. **Integrity** — recomputation of the SHA-256 hash of the *canonical document* and comparison against the stored hash (digital emissions only).
3. **Professional-council conformance (CFM 2.299/2021)** — real (non-sentinel) patient identifier, mandatory per-item fields (quantity, unit, posology), and a signature mode admissible under CFM.
4. **Signature metadata** — presence and coherence of signature records and their document hash.
5. **Certificate verification (ICP-Brasil)** — *declared design; current open boundary.* This layer is specified but not yet integrated end-to-end (see Section V); it is reported transparently rather than asserted as functional.
6. **Prescriber identity (CNES cross-check)** — described in §III-D.

The report aggregates these into a graded overall result (e.g., structurally valid, valid with CNES-confirmed identity, invalid on a hard failure), making the *level* of assurance explicit rather than reducing validation to a single pass/fail bit.

### C. Explainable terminology resolution

Free-text medication, diagnosis (ICD-10), and exam entries are resolved through a deterministic pipeline: (i) exact match on a normalized index; (ii) alias match; (iii) approximate match using a weighted-ratio fuzzy score (`rapidfuzz`) above a threshold; otherwise (iv) no match. Approximate matches are never applied silently — they are returned as structured alerts asking the prescriber to confirm.

Thresholds are deliberately conservative. We report a concrete design correction: the medication fuzzy threshold was raised from 0.82 to 0.88 after short dosage tokens (e.g., "N mg") produced spurious high-confidence matches, and a minimum-length guard was added for short queries. This illustrates the engine's stance: when terminology resolution is uncertain, the system makes the uncertainty visible rather than hiding it behind a confident-looking match.

### D. Prescriber identity by name, not by national ID

Prescriber eligibility is verified against a national CNES registry snapshot by **name**, not by national-ID number. Identity is anchored to an immutable validation string composed of the certificate-derived identifier, the professional-council registration with its state, and the national health card; the prescriber's national-ID number is extracted locally and is never transmitted to the server. The CNES layer performs graded checks: name consistency (string similarity above a fixed threshold), prescriptive occupation code, an enabled professional council, and at least one active institutional link. A name/occupation/council divergence is a *hard* failure (possible misuse of another professional's credentials); a registry miss is a *soft* failure attributed to snapshot staleness, not to the prescriber.

### E. Regulatory grouping of controlled substances

The engine maps medications to control groups derived from Ordinance 344/1998, RDC 471/2021, and the SNCR regime (RDC 1.000/2025), determining the number of prescription copies, retention, and special-control handling. These mappings are expressed in inspectable code rather than hidden configuration, consistent with the transparency objective.

### F. Reference data (MVP, synthetic)

The current reference bases are deliberately scoped MVP subsets, not the full official tables: 81 medications (a curated formulary table), an ICD-10 subset of roughly 240 codes (reported to cover the large majority of primary-care cases), and 35 diagnostic procedures. We report these sizes honestly; expansion and synchronization with official sources are future work.

## IV. Results: Evaluation by Executable Conformance

We evaluate the engine by *executable conformance* rather than by clinical field metrics: the system has no classifier and we make no accuracy/F1 claim. Validation consists of scenario-based test suites exercising each layer and the regulatory grouping over synthetic prescriptions `[TODO: report exact test counts/files, e.g., receituario grouping suite, validation suite, CNES catalog suite; state pass status from a clean run]`.

`[Table I — TODO]` *Scenario → checks exercised → expected report → test status.* Suggested rows: digital emission with valid signature metadata; paper-only emission (integrity checks marked non-applicable); CFM mandatory-field violation; controlled-substance grouping; CNES name divergence (hard failure); CNES registry miss (soft failure); low-confidence terminology match (structured alert).

What this establishes and what it does not: the suite demonstrates that the engine's decisions are *reproducible, layered, and individually justified*, and that regulatory groupings behave as specified. It does **not** establish clinical effectiveness or real-world safety, which would require field study.

## V. Discussion and Limitations

The engine's value is that authorization becomes inspectable: an auditor or clinician can see not only *that* a prescription was accepted or rejected but *why*, check by check. Several boundaries are stated explicitly and by design.

- **End-to-end ICP-Brasil signing is declared design, not validated.** Signature integrity is anchored on a canonical-document SHA-256 hash, but cross-runtime canonical serialization and full certificate-chain verification remain open; we therefore report the certificate layer as specified-but-not-integrated rather than functional.
- **Reference bases are MVP subsets** on synthetic data; no real patient or prescriber data are used, and the system runs in an enforced demonstration mode.
- **No clinical field validation.** Evaluation is conformance-based.
- The system's broader **auditability and anti-commercialization properties** — which arise from the immutable trail and the absence of bulk egress — are the subject of a companion architecture paper and are intentionally out of scope here.

## VI. Conclusion

We presented a transparent, explainable regulatory engine that authorizes digital prescriptions over an immutable event trail, decomposing each decision into independently justified checks aligned with Brazilian pharmaceutical-control regulation, verifying prescriber identity by name against the national registry, and resolving clinical terminology with defensive, uncertainty-surfacing thresholds. Instantiated in an open, synthetic-data reference implementation and evaluated by executable conformance, it shows that prescription authorization can be made auditable rather than opaque. Future work includes end-to-end ICP-Brasil signature integration, expansion and synchronization of the reference bases with official sources, and a field pilot in a municipal primary-care unit.

## References

`[TODO: complete in IEEE numerical style — full author names (et al. only for 6+), DOIs/URLs, first-word-only title capitalization. Starter anchors below.]`

- [ ] CFM, Resolução nº 2.299/2021 (prescrição digital).
- [ ] Anvisa, RDC nº 1.000/2025 (SNCR — Sistema Nacional de Controle de Receituários).
- [ ] Brasil, Portaria SVS/MS nº 344/1998 (substâncias sob controle especial).
- [ ] Anvisa, RDC nº 471/2021 (retinoides sistêmicos).
- [ ] ICP-Brasil / MP 2.200-2/2001 (infraestrutura de chaves públicas).
- [ ] Lei nº 13.787/2018 (digitalização e guarda de prontuário).
- [ ] rapidfuzz library — approximate string matching `[cite software]`.
- [ ] `[3–5 refs]` explainable clinical decision support / transparency in safety-critical health software.
- [ ] `[2–3 refs]` approximate string matching for clinical terminology normalization.
- [ ] `[1–2 refs]` event sourcing / immutable audit logs (substrate).
