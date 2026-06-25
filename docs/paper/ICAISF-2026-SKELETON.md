# ICAISF 2026 — Paper skeleton + abstract (working scaffold)

> **Status:** draft scaffold for review · **Language:** English (IEEE Xplore target)
> **Format:** IEEE short paper, 5 pages, two-column · **Deadline:** 10 Jun 2026
> **Framing (locked):** auditable *reference architecture* / proof-of-concept — NOT a production platform, NOT a SUS product, NOT "medical AI".
> **Author note:** this file is a strategic scaffold from the architecture advisor, not the manuscript. It fixes the thesis, the claim boundaries, and the page budget before drafting prose.

---

## 0. Title — DECIDED

Review is **single-blind** (ICAISF site: "at least 2 independent reviewers"; no anonymization instruction; authors are told to put names + affiliations in the PDF). So we keep the brand and name the artifact:

**Chosen title:**
*PicSaúde: An Auditable Event-Sourced Architecture for Regulatory-Aware Digital Health Workflows*

**Neutral alternative (if we later want idea-first):**
*Transparent Sanitary Rules over Immutable Event Trails: A Reference Architecture for Auditable Digital Health Workflows*

> ICAISF rule: title must not contain symbols/special characters/math. "PicSaúde" with the accent is fine in body text; confirm the CMT title field accepts the "á" — if it mangles it, fall back to "PicSaude".

---

## 1. Thesis (one sentence — the spine of the whole paper)

> **Transparent, verifiable sanitary rules operating over an immutable trail of clinical-operational events yield digital health workflows that are auditable by construction — and we demonstrate this with an open reference implementation running on synthetic data.**

Everything in the paper either (a) explains a mechanism that makes this true, or (b) shows evidence that it holds. If a paragraph does neither, it gets cut for space.

---

## 2. Claimable contributions (what we *assert*)

1. **A reference architecture** pairing two decoupled engines: a *circulation engine* (state machine + immutable ledger + explicit custody chain) and a *regulatory engine* (explicit, verifiable, explainable rules).
2. **A generalizable model of "sanitary objects"** — prescriptions, exam orders, reports, schedules — sharing one contract (identity, states, ledger, custody) rather than bespoke per-object logic.
3. **Auditability by construction**: every business-relevant transition is an append-only event; no destructive update path exists on clinical objects or on the ledger.
4. **An open, synthetic-data artifact** (DEMO_MODE enforced in architecture, not just labeled) that lets third parties inspect and reproduce the workflows.
5. **Ethical/operational guard-rails as code** (anti-monetization tripwire, anti-mass-export tripwire) that raise the floor and make violations conspicuous.

> Advisor note: contributions 1–4 are the technical core. #5 is differentiating for a CFP that explicitly names "ethical/regulatory challenges in AI-powered healthcare" — keep it, but frame honestly (see §Limits).

---

## 3. Claim boundary — the line we DO NOT cross

This table is the guardrail for the whole draft. **Left column = allowed. Right column = forbidden phrasing.**

| ✅ Allowed (defensible) | ❌ Forbidden (overclaim — attack surface) |
|---|---|
| "We *design* an ICP-Brasil signature flow; canonical-document hashing is specified." | "Signatures are validated / working end-to-end." |
| "Cross-runtime canonical serialization (WebCrypto↔Python) is identified as **open work (R6)**." | (any silence implying the signature chain closes today) |
| "Validated scenarios run green on PostgreSQL: emission, custody transfer, partial dispensation, physical emission, ownership authorization." | "The platform is production-ready / piloted in a health unit." |
| "Synthetic data only; no real patient data; DEMO_MODE enforced in the architecture." | "Evaluated with real clinical data." |
| "Guard-rails raise the floor and make misuse conspicuous." | "Guard-rails prevent malicious forks / guarantee no resale." |
| "Reference implementation / proof of concept." | "Product", "SaaS", "deployed system in the SUS". |

> R6 is an **absolute pilot blocker** and stays open. The paper turns this into *declared scope*, not a hidden gap. Honesty here is the credibility engine of the whole submission.

---

## 4. Section-by-section skeleton (5-page budget, ICAISF layout)

> **Important:** ICAISF prescribes a section layout (see §7 below) built for *empirical ML papers* (Dataset → Methodology → Experimental Results with Accuracy/F1/ROC-AUC). Ours is a **systems/architecture paper** — we adapt their headings honestly rather than fake metrics we don't have. The mapping below keeps their expected skeleton while filling it with architecture content.

Total ≈ 5 pages, two-column IEEE **A4**. Budget is in **columns** (≈ 0.5 page each) so it's easy to police.

### I. Introduction — budget: ~1 column · (ICAISF: no subheadings, 3 paragraphs + 2 bulleted lists + organization)
- **Para 1:** broader area — digital health mediates high-stakes clinical/regulatory decisions; trust needs traceability + explainability.
- **Para 2:** the gap — auditability is bolted on (logs, after-the-fact reports), rules are buried in opaque application logic; existing work falls short.
- **Para 3:** our proposal — make auditability *structural* via immutable events + explicit rules; instantiated as PicSaúde (open, synthetic).
- **Bulleted Research Objectives** (ICAISF requires this list).
- **Bulleted Major Contributions** (mirror §2, 4–5 bullets).
- One-sentence **paper organization** paragraph.
- Fold the scope statement (reference architecture, synthetic data, not a clinical platform) into Para 3 — honesty up front disarms the reviewer.

### II. Related Work — budget: ~1 column · (ICAISF: 12–15 papers, critical, NO subheadings)
- Critically compare, don't just summarize: event sourcing / append-only ledgers; EHR audit logging; blockchain-for-health (contrast: we are *internally* event-sourced — no distributed ledger, no token economics); digital-signature/PKI in health; regulatory traceability (ICP-Brasil, CFM 2.299/2021).
- **Compact comparison table** (Reference | Method | Domain | Contribution | Limitation) — ICAISF explicitly invites this and it saves prose.
- ⚠️ **This is the biggest pre-deadline lift:** 12–15 *real, complete, non-AI-generated* references with DOIs. Start the bibliography now (see §6 task).

### III. Materials and Methods → "Architecture & Methodology" — budget: ~2 columns (THE CORE)
ICAISF allows subsections here. Map:
- **A. Sanitary-object contract** (their "Dataset/inputs" analogue) — identity (global UUID `protocolo`), states, ledger, custody; one contract across object types; describe the **synthetic dataset** (objects, scenarios) here to satisfy their "Dataset Description" expectation.
- **B. Proposed architecture** — circulation engine (state machine + immutable ledger + custody) and regulatory engine (explicit/verifiable/explainable rules). **Block diagram = Fig. 1.**
- **C. State machine** — physical vs digital flows, terminal states, immutability after emission (corrections = new derived object, never UPDATE). **State diagram = Fig. 2.**
- **D. Ledger & custody** — append-only `*_eventos`; no DELETE/UPDATE path; granular custody transitions.
- **E. Regulatory rules + pseudocode** — partial dispensation as worked example (Σ dispensed ≤ prescribed preserves validity). ICAISF asks for **algorithm/pseudocode** — give one short boxed algorithm here.
- **F. Canonical document & signature (declared design)** — canonical JSON + SHA-256; ICP-Brasil flow *as designed*; **R6 named as open work in-text.**
- **Implementation details** (their required subsection) — FastAPI / SQLAlchemy / PostgreSQL; open repo; AGPL; DEMO_MODE enforced architecturally.

> Two figures max (block diagram + state machine). Resist a third — pages vanish fast.

### IV. Experimental Results → "Validation by Scenario" — budget: ~0.75 column
- Reframe honestly: we have no classifier, so **no Accuracy/F1**. Our "evaluation" is **executable conformance**: validated scenarios run green on PostgreSQL (e.g., 22-test authorization + regression run).
- **Setup:** PostgreSQL test environment, scenario suite.
- **Results table:** scenario → events emitted → invariant preserved → test status. Scenarios: digital emission → custody → partial dispensation; physical-only emission (fire-and-forget trade-off, stated honestly); custody transfer; ownership authorization (404→403→422 anti-leak ordering).
- **Discussion / "Error Analysis":** what the green suite does and does NOT prove — it is structural conformance, not clinical field validation.

### V. Conclusion — budget: ~0.5 column · (ICAISF: ONE compact paragraph, future work folded IN — no separate section)
- Restate thesis: rules-over-trails as a reusable pattern for auditable digital health.
- Fold future work into the same paragraph: resolve R6 (cross-runtime canonical signing), build G4A event-publishing layer, then a municipal pilot.

### References — budget: remaining space · IEEE numerical style, full author names (et al. only for 6+), DOIs/URLs
- 12–15 entries to satisfy Related Work. Anchors: CFM 2.299/2021; ICP-Brasil / MP 2.200-2; LGPD; event-sourcing; EHR audit logging; health interoperability; blockchain-for-health (as contrast).

---

## 4a. ICAISF section map (quick reference)

| ICAISF expected section | Our adaptation |
|---|---|
| Introduction (3 para + objectives + contributions) | Same, scope honesty in para 3 |
| Related Work (12–15 papers, table) | Same — biggest lift |
| Materials and Methods (Dataset, Methodology, Algorithm, Implementation) | Architecture & Methodology (contract, engines, state machine, pseudocode, impl) |
| Experimental Results (metrics, comparison) | Validation by Scenario (executable conformance, not ML metrics) |
| Conclusion (1 paragraph, future work inside) | Same |
| Limitations/Ethics | **No separate section in their template** — weave into Validation discussion + Conclusion. Keep R6 / G4A / synthetic-only / guard-rail honesty, just distributed. |

---

## 5. Abstract (draft — ~200 words, English)

> Digital health systems increasingly mediate high-stakes clinical and regulatory decisions, yet two properties critical to trust are usually weak or absent: end-to-end **traceability** of what happened, and **explainability** of the rules that governed it. Auditability is typically bolted on through application logs and after-the-fact reports rather than guaranteed by the system's structure. We present a **reference architecture** in which auditability is structural by construction. The design pairs a *circulation engine* — a state machine over immutable, append-only event trails with an explicit, granular custody chain — with a *regulatory engine* of explicit, verifiable, and explainable rules. Clinical objects are immutable after emission: every correction, renewal, or transfer is recorded as a new derived object and a new event, with no destructive update path. We generalize this to a single contract for heterogeneous "sanitary objects" (prescriptions, exam orders, reports, schedules). We instantiate the architecture as **PicSaúde**, an open, synthetic-data reference implementation, and demonstrate validated workflows — digital and physical prescription emission, custody transfer, and partial dispensation — together with ethical guard-rails enforced as code. We position the system explicitly as an auditable proof of concept, not a production clinical platform, and we declare its open boundaries, including cross-runtime canonical signing.

> Advisor note: 207 words. Trim "increasingly" and one clause if the template caps at 150–200. Last sentence is the honesty anchor — do not cut it.

---

## 6. Open decisions before drafting prose (for Fabiano)

**Resolved:** title (named, §0) · review model (single-blind → keep brand) · authorship (Fabiano + UFPE extensionists).

Still open:
1. **Co-author roster** — which of the 7 extensionists go on the author line, and in what order? ICAISF wants final, correctly-ordered names (no titles like Dr./Prof.), each with the 5-line affiliation block. Confirm everyone consents and their work warrants authorship (vs. acknowledgment) before 10 Jun.
2. **Figures** — we ship exactly two: block diagram (Fig. 1) + state machine (Fig. 2). Do we have clean source, or do they need to be drawn? (300 dpi TIFF/EPS for camera-ready; A4 template.)
3. **Bibliography** — start now: 12–15 complete IEEE references with DOIs. This is the critical-path item, not the prose.
4. **CBIS/SBIS parallel** — PT translation track in parallel, or fully commit this round to ICAISF? (Reminder: same work can't be under review at two venues simultaneously — ICAISF requires unpublished + not-under-review-elsewhere.)

---

## 7. Venue conformance checklist (ICAISF 2026)

**Hard constraints:**
- Format: **IEEE conference template, A4, two-column**. Word: ieee A4 .docx · LaTeX: Overleaf IEEE template. Do NOT alter margins/columns/spacing/fonts.
- Length: **max 5 pages** (extra pages incur charge). No manual page numbers.
- Abstract: run-in head "*Abstract—*", **no citations / equations / special characters**.
- Keywords: one line, 4–6 terms ("*Keywords—*").
- Conclusion: **single paragraph, future work inside** (no separate Future Work section).
- References: IEEE numerical, full author names (et al. only for 6+), DOIs/URLs, first-word-only title capitalization. **No AI-generated/incomplete refs** — verify every one.
- Plagiarism report **≤ 15%**.
- Original, unpublished, not under review elsewhere.

**Process & dates:**
- Submission: **Microsoft CMT** (cmt3.research.microsoft.com/ICAISF2025) — create account; submit PDF.
- **Paper submission deadline: 10 Jun 2026** · Notification: 30 Jun · Registration: 10 Jul · Camera-ready: 20 Jul · Conference: **24–25 Jul 2026** (hybrid, online option).
- Camera-ready (only if accepted): IEEE PDF eXpress validation, **Conference ID 70757**; IEEE Copyright Transfer Form via CMT.
- Review: ≥ 2 independent reviewers; criteria = originality, significance, technical soundness, clarity.

**Cost reminder (from registration page, for the go/no-go after acceptance):** online author ~US$300/350; student online ~US$200/250. Decide who registers before committing.

> ⚠️ **Honest risk to weigh:** ICAISF's technical-paper template is built for empirical ML work (datasets, accuracy/F1, error analysis). A systems/architecture paper is *admissible* (CFP scope includes architecture, ethics, decision-making) but you may draw a reviewer expecting quantitative ML metrics. Mitigation: lean hard on "executable conformance" as our evaluation, make the figures and pseudocode carry the technical weight, and keep the honesty framing tight. If a reviewer rejects on "no metrics," that's a venue-fit miss, not a paper flaw — which is exactly why we don't abandon CBIS/SBIS.
