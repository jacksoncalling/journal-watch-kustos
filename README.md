# Kustos

A quiet weekly companion for staying current with medical research. Kustos watches a clinician's subspecialty literature, ranks what is new by evidence strength, and delivers a short German-language digest (a "Wochenbrief") to their phone via Telegram. Once a week, readable in five minutes, no dashboard to check.

This is the public method repository. It ships a fictional demo profile ("Dr. Demo") and no real data. The real instantiation, with an actual clinician's topics, lives in a separate private repo.

## Why it exists

OpenEvidence withdrew from the EU and UK in April 2026 over the EU AI Act, which left a gap for clinicians here. Kustos does not try to fill all of it. It covers one job: keeping up with new research in a few chosen topics. It does not answer clinical questions, and it never looks up drug dosages. Those are deliberate non-goals, not missing features.

## How it works

The folder is the database. Configuration, memory, and every generated brief live as Markdown and JSON files in the repo. There is no server and no database to keep alive. A weekly GitHub Actions job runs one pipeline:

1. **Fetch**: query Europe PMC for each topic since the last run.
2. **Enrich**: add open-access links (Unpaywall) and full text where a legal OA copy exists.
3. **Rank**: assign an evidence level from the publication type, then score by topic match, journal trust, and recency. Pure code, no model.
4. **Synthesize**: one LLM call writes the German brief from the selected papers.
5. **Send**: deliver it to Telegram, split cleanly at paper boundaries.

Judgment is used exactly once, in synthesis. Everything around it is deterministic code, so the guardrails below hold regardless of what the model does.

## Guardrails

- Evidence level and provenance are set in code, not by the model. Each paper carries `[Stufe 1/2/3]` and either `[VOLLTEXT]` or `[NUR ABSTRACT]`, plus its DOI and PMID. The model cannot inflate a level or invent a link.
- No dosage recommendations. If a study compares doses, the brief may note that, but it always points back to the clinic standard and the Fachinformation.
- No paywall circumvention. Every item carries its DOI. The clinician opens it with their own institutional access.
- No patient data anywhere, in queries, files, or messages.
- Where the literature disagrees, the brief says so plainly. Consensus is never simulated.

## Regulatory boundary

This is a personal tool for one clinician, not a product placed on the market. If it ever became an offering to a hospital, it would enter exactly the EU AI Act high-risk category, clinical decision support, that made OpenEvidence leave Europe. That step would need a deliberate decision and the institution's data protection officer. It is out of scope here.

## Not medical advice

Kustos is a research digest. It is not a clinical reference and not a medical device, and it comes with no warranty of any kind. Always check the original source and your clinic standard before acting on anything it surfaces.

## Running it

Requires Python 3.11+ and a few API keys (see `.env.example`). To run the whole pipeline once:

```bash
python scripts/run_weekly.py            # full run: fetch through send
python scripts/run_weekly.py --dry-run  # everything except the Telegram send
```

The individual stages under `scripts/` also run on their own. The demo configuration lives in `profil/profile.md`.

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

Built out loud as part of [Step Into More](https://stepintomore.co).
