---
type: Capability
status: live
kind: semantic layer
hub: retrieval-layer
---
# Gate Layer

The deterministic semantic layer that makes the Praxis-Check trustworthy without embeddings. Four gates plus guards: a subject-actor gate (require the intervention term, not just context), a retraction gate (drop Retracted/Retraction records), a MeSH negative gate (hard-drop animal/oncology with no cardiac MeSH, ~150 dropped across 7 questions with zero per-question tuning), and a cardiac-MeSH ranking bonus (+40). Tuned on the cardiac benchmark, held on 4 untuned questions.

held-by [[The Maintainer]] . depends-on [[MeSH Thesaurus]] . governed-by [[No Embeddings]] . would-be-strengthened-by [[Abbrev-MeSH Expansion]]

- **Hits:** [[Praxis-Check]] dossier quality. The [[Cardiac Benchmark]] scores (offsub 0/20 after the gates). Which papers survive to synthesis.
- **Does not hit:** the weekly [[Rank]]. The gates are Praxis-only; the weekly Wochenbrief does not run them. A human off-specialty paper (e.g. the WOMAN obstetric TXA trial) still passes the subject gate and merely sinks.

Source: scripts/praxis_check.py (gate functions); CLAUDE.md 'Current state'.
