# Plan: Praxis-Check evidence-quality fixes

Derived from the Amboss vs Kustos head-to-head (2026-08-27). Five cardiac-
anaesthesia questions tested: volatile-vs-TIVA, RIPC, TXA-efficacy, TXA-dose,
heparin/ACT. This is the fix list, prioritized, each tied to the test that
motivated it. Nothing here is built yet.

## What the tests confirmed WORKS (do not change)

- **Dose-as-advice guardrail holds under direct pressure.** On the TXA-dose and
  heparin/ACT questions (both literally asking for a recommended dose), Kustos
  named doses only as attributed evidence ("die OPTIMAL-Studie verglich ...",
  "Leitlinien empfehlen ..."), never as its own prescription; footer intact.
- **Controversy-surfacing + Kernbefund reframe work** (RIPC was exemplary: it
  separated the real AKI signal from the null cardiac/mortality endpoints and
  named the big neutral RCTs ERICCA/RIPHeart).
- **OA-link fix is live** (OA-PDF vs OA-Link, DOI-duplicate suppressed).
- **Retraction + MeSH-negative gates + planner pin**: working.
- **Coverage beats Amboss** (RIPC: Amboss returned "not enough information";
  Kustos produced a full map).
- **Strategic finding:** Kustos owns evidence/controversy/currency questions;
  Amboss owns reference/dosing lookups. Do NOT try to make Kustos a dosing
  reference. Match the tool to the question shape.

## Fixes, prioritized

### 1. Strip phantom / malformed inline PMIDs  [BUG, high]
- **Evidence:** the TXA-dose dossier printed `(PMID 358811121, ...)`, nine
  digits, a duplicated-digit version of the real `35881121`. A non-resolving
  citation reached the rendered output.
- **Now:** `validate_citations` only warns to stderr.
- **Change:** in `praxis_check.py`, upgrade `validate_citations` (or a new step
  before `finalize`) to REMOVE any inline `(PMID ...)` number not in the selected
  set. In a multi-PMID group, strip only the unknown number and keep the valid
  ones; if the group is left empty, drop the whole `(PMID ...)`. Keep the stderr
  warning.
- **Risk:** low. **Verify:** re-run TXA-dose (malformed PMID gone); 7-question
  benchmark still reports 0 phantom.

### 2. Prune Quellen to cited-only  [FIX, high, two-birds]
- **Evidence:** the heparin/ACT dossier's Quellen carried ~6 off-question papers
  the prose never cited (protamine PRODOSE ranked #1, DOACs, fresh frozen plasma,
  VTE prophylaxis, pentastarch priming). "heparin" is too broad a subject term,
  so coagulation-adjacent cardiac papers leak into retrieval.
- **Change:** in `assemble_quellen`, list only papers whose PMID actually appears
  in the finalized prose. Keep them in score order (or first-appearance order).
- **Two wins:** removes off-topic sources (restores trust in the source list)
  AND shortens the artifact (directly addresses the "too much text" signal).
- **Decision (Josh):** this changes the artifact from "top-N considered" to
  "sources actually used." Recommended yes.
- **Risk:** if the model under-cites, Quellen could get thin. Mitigation: a floor
  (if fewer than N cited, append a short "weitere gesichtete Quellen"). Start
  simple (cited-only) and watch the benchmark.
- **Verify:** re-run heparin/ACT; the six off-topic sources drop; benchmark
  Quellen shrink to the cited set with no on-topic loss.

### 3. Format / length for lookup-shaped questions  [PRODUCT, medium]
- **Evidence:** partner UX signal "a bit too much text"; dose/ACT questions are
  reference lookups where Amboss's scannable table wins and Kustos's four-section
  wall mismatches the need. Also the 90s vs 30s latency is inherent to live
  search and cannot be tuned away.
- **Not a bug, a format-fit decision.** Options:
  a. Rely on #2 (cited-only Quellen already trims a lot of length).
  b. Tighten the vertrag length guidance (Kernbefund carries the answer; sections
     only as long as the evidence warrants; cut filler).
  c. Later/optional: detect lookup-shaped questions (dose / target / "what is X")
     and return a terser format, or note that a reference (Amboss/UpToDate) is
     faster for a pure number. Bigger change; defer.
- **Recommend:** do (a)+(b) now, defer (c). Decision needed on how aggressive.

### 4. Evidence-weighting in the Kernbefund  [JUDGMENT, medium, needs validation]
- **Evidence:** volatile-vs-TIVA, Kustos led the Kernbefund with the
  meta-analysis positive signal though the largest RCT (MYRIAD) shows no
  advantage; Amboss led "kein nachgewiesener Vorteil." BUT RIPC and both TXA
  controls were well-weighted, so this is NOT a confirmed systematic bias.
  Levosimendan (the second definitive-negative, the intended tiebreaker) was not
  run.
- **Candidate vertrag change:** (i) anchor the Kernbefund to the highest-weight
  clinical evidence, a large pragmatic RCT outweighs meta-analyses of small
  trials for the bottom line; (ii) frame preclinical/animal findings as mechanism
  only, never as clinical proof.
- **Status:** lower-confidence (one motivating test), but the principle is
  arguably always-correct and would not have hurt RIPC/TXA, so low risk.
- **Recommend:** make the vertrag change, THEN validate by re-running volatile +
  RIPC + TXA (+ levosimendan if run) and confirm the volatile Kernbefund flips to
  the better-weighted wording WITHOUT breaking the ones already fine.

### 5. Human off-context / subject-adjacent leaks  [KNOWN RESIDUAL, low]
- **Evidence:** obstetric/postpartum TXA papers (WOMAN; the postpartum paper at
  #13 in the TXA-efficacy run) in cardiac TXA questions; coagulation-adjacent
  papers in the heparin question. The MeSH-negative gate only catches
  animal/oncology; a human off-specialty or subject-adjacent paper passes the
  subject gate and merely sinks.
- Fix #2 (cited-only Quellen) removes the OUTPUT symptom (uncited leaks drop). A
  retrieval-level fix (obstetric/off-specialty MeSH exclusions, or requiring the
  question-specific focus, not just the drug) is harder and lower ROI.
- **Recommend:** rely on #2 for now; revisit retrieval-level filtering only if
  leaks survive into the prose.

## Suggested order

1 (bug) -> 2 (two-birds) -> 4 (change + validate) -> 3 (format) -> 5 (defer).
After 1+2, re-run `scripts/benchmark_praxis.py` (7 questions) plus the five
Amboss-test questions to confirm no regressions.

## NOT in this plan (separate roadmap, see CLAUDE.md "What's next")

- **MeSH synonym / controlled-vocabulary expansion** (staged inert in
  `profile.md`); independent of these fixes.
- **Per-user quota** (web layer; today's cap is global).
