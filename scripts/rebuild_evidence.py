#!/usr/bin/env python3
"""Rebuild `<dossier>.evidence.json` for a dossier written before praxis_check.py
saved its evidence (before 2026-10-15), so check_claims.py can run on it.

Reads the PMIDs and the code-set provenance ([VOLLTEXT] / [NUR ABSTRACT]) from
the dossier's own `## Quellen`, re-fetches each record from Europe PMC, and
rebuilds `evidence_basis` the same way the pipeline does (full-text excerpt for
papers that had one, abstract otherwise). No model call.

The result is marked `"reconstructed": true`: the records may have changed
since the run (an updated abstract, a full-text fetch that fails today), and the
raw model prose is not recoverable. Good enough to check numbers; not a replay.

  python scripts/rebuild_evidence.py <dossier.md> [<dossier.md> ...]
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

import enrich
import fetch_europepmc as fetch
import praxis_check as pc

UA = "journal-watch/0.1 (rebuild-evidence)"


def quellen_entries(dossier: str) -> list[tuple[str, str]]:
    """[(pmid, provenance)] in Quellen order."""
    quellen = dossier.split("## Quellen", 1)[1] if "## Quellen" in dossier else ""
    out = []
    for block in re.split(r"\n(?=\d+\.\s)", quellen):
        m = re.search(r"PMID\s+(\d+)", block)
        if m:
            prov = "[VOLLTEXT]" if "[VOLLTEXT]" in block else "[NUR ABSTRACT]"
            out.append((m.group(1), prov))
    return out


def fetch_records(pmids: list[str]) -> dict[str, dict]:
    q = "(" + " OR ".join(f"EXT_ID:{p}" for p in pmids) + ") AND SRC:MED"
    url = fetch.BASE + "?" + urllib.parse.urlencode(
        {"query": q, "resultType": "core", "format": "json", "pageSize": 100})
    data = fetch.fetch_json(url, UA, timeout=60)
    recs = data.get("resultList", {}).get("result", [])
    return {str(r.get("pmid")): fetch.normalise(r, []) for r in recs}


def rebuild(path: Path) -> Path:
    dossier = path.read_text(encoding="utf-8")
    entries = quellen_entries(dossier)
    recs = fetch_records([p for p, _ in entries])
    papers, drift = [], []
    for pmid, prov in entries:
        c = recs.get(pmid, {"pmid": pmid})
        if prov == "[VOLLTEXT]" and c.get("pmcid"):
            try:
                c["fullTextExcerpt"] = enrich.fulltext_excerpt(c["pmcid"], UA)
            except Exception as e:  # noqa: BLE001
                print(f"  fulltext error {pmid}: {e}", file=sys.stderr)
        if prov == "[VOLLTEXT]" and not c.get("fullTextExcerpt"):
            drift.append(pmid)
        if prov == "[NUR ABSTRACT]":
            c["fullTextExcerpt"] = None       # match what the model got then
        papers.append({**pc.synth.paper_payload(c), "provenance": prov,
                       "rebuilt_provenance": pc.synth.provenance(c)})
    title = re.search(r"^# Praxis-Check:\s*(.+)$", dossier, re.M)
    record = {
        "schema_version": pc.EVIDENCE_SCHEMA_VERSION,
        "created": None,
        "reconstructed": True,
        "reconstruction_note": (
            "re-fetched from Europe PMC after the run; synthesis_raw unavailable"
            + (f"; full text unavailable today for {', '.join(drift)}" if drift else "")),
        "question": {"title": title.group(1) if title else None,
                     "frage": None, "kontext": None},
        "queries": re.findall(r"^- `(.+)`$", dossier, re.M),
        "synthesis_raw": None,
        "papers": papers,
    }
    out = pc.evidence_path(path)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [p for p, _ in entries if p not in recs]
    print(f"{path.name}: {len(papers)} papers"
          + (f", {len(missing)} not found {missing}" if missing else "")
          + (f", full-text drift {drift}" if drift else "") + f" -> {out.name}")
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for a in argv:
        rebuild(Path(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
