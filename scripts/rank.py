#!/usr/bin/env python3
"""02_rank: deterministic ranking. No LLM.

Reads 01_fetch/output/candidates.json, assigns each paper an evidence level
(Stufe 1/2/3) from its Europe PMC publication types, scores it, and writes the
top N to 02_rank/output/selected.json.

Evidence level is derived here in code and is authoritative: the synthesis step
must never upgrade it (build-plan.md 5.3 post-processing check).

Scoring is intentionally simple and legible (build-plan.md 5.2):
  score = evidence_weight (dominant) + topic matches + journal-trust bonus
          + recency + kanon.md keyword overlap
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profil" / "profile.md"
KANON = ROOT / "profil" / "kanon.md"
CANDIDATES = ROOT / "01_fetch" / "output" / "candidates.json"
OUT = ROOT / "02_rank" / "output" / "selected.json"

DEFAULT_MAX_ITEMS = 7


# --------------------------------------------------------------------------- #
# evidence level: the core deterministic mapping (importable + tested)
# --------------------------------------------------------------------------- #
def evidence_level(pub_types: list[str]) -> int:
    """Map Europe PMC pubTypes to an evidence tier. 1 = strongest, 3 = weakest.

    Stufe 1: Meta-Analysis, Systematic Review, or multicenter RCT
    Stufe 2: RCT, Cohort/Observational, Guideline
    Stufe 3: Case Reports, Letters, Editorials, narrative Review, everything else
    """
    types = [p.lower() for p in (pub_types or [])]

    def has(*subs: str) -> bool:
        return any(any(sub in t for sub in subs) for t in types)

    is_rct = has("randomized controlled trial", "randomised controlled trial")
    is_multicenter = has("multicenter", "multicentre")

    if has("meta-analysis", "systematic review") or (is_rct and is_multicenter):
        return 1
    if is_rct or has("observational study", "cohort", "guideline"):
        return 2
    return 3


EVIDENCE_WEIGHT = {1: 3, 2: 2, 3: 1}


def _norm_journal(name: str | None) -> str:
    """Lowercase, drop punctuation, collapse spaces, for exact journal matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())).strip()


def score(cand: dict, stufe: int, trust: list[str], kanon_kw: set[str],
          today: date) -> tuple[float, dict]:
    weight = EVIDENCE_WEIGHT[stufe] * 100  # dominant term

    topics = len(cand.get("matchedTopics", [])) * 5

    # Match the journal abbreviation against the trust list by normalised
    # equality (lowercased, punctuation stripped). Substring matching was
    # fragile: a short trust entry like "med" would match "n engl j med".
    abbr_n = _norm_journal(cand.get("journalAbbrev"))
    trusted = 10 if abbr_n and any(_norm_journal(t) == abbr_n for t in trust) else 0

    recency = 0.0
    d = cand.get("date")
    if d:
        try:
            age = (today - datetime.strptime(d, "%Y-%m-%d").date()).days
            recency = max(0.0, 30 - age) * 0.5
        except ValueError:
            pass

    hay = f"{cand.get('title','')} {cand.get('abstract','')}".lower()
    kanon = min(9, sum(3 for kw in kanon_kw if kw in hay))

    total = weight + topics + trusted + recency + kanon
    return total, {"evidence": weight, "topics": topics, "journal_trust": trusted,
                   "recency": round(recency, 1), "kanon": kanon}


# --------------------------------------------------------------------------- #
# profile / kanon parsing
# --------------------------------------------------------------------------- #
def parse_profile(text: str) -> dict:
    mi = re.search(r"`max_items`\s*:\s*(\d+)", text)
    max_items = int(mi.group(1)) if mi else DEFAULT_MAX_ITEMS

    trust: list[str] = []
    in_trust = False
    for line in text.splitlines():
        if line.strip().startswith("## Journal-Trust-Bonus"):
            in_trust = True
            continue
        if in_trust:
            if line.startswith("## "):
                break
            m = re.match(r'^-\s+"([^"]+)"', line.strip())
            if m:
                trust.append(m.group(1))
    return {"max_items": max_items, "trust": trust}


def kanon_keywords(path: Path) -> set[str]:
    """Slice-1 kanon: keyword overlap only, no embeddings. Reads bullet lines
    like `- keyword: ...` or bare `- keyword` from kanon.md."""
    if not path.exists():
        return set()
    kws: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^-\s+(.+)$", line.strip())
        if m:
            token = m.group(1).split(":")[0].strip().lower()
            if len(token) >= 4:
                kws.add(token)
    return kws


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    prof = parse_profile(PROFILE.read_text(encoding="utf-8"))
    kanon_kw = kanon_keywords(KANON)
    today = date.today()

    ranked = []
    for c in cands:
        stufe = evidence_level(c.get("pubTypes", []))
        total, breakdown = score(c, stufe, prof["trust"], kanon_kw, today)
        item = dict(c)
        item["stufe"] = stufe
        item["score"] = round(total, 1)
        item["score_breakdown"] = breakdown
        ranked.append(item)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    selected = ranked[: prof["max_items"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"schema_version": "1.0",
             "window": data.get("window"), "count": len(selected),
             "quiet_week": len(selected) < 2, "selected": selected},
            ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"ranked {len(cands)} candidates, selected top {len(selected)}"
          + (f"  (max {prof['max_items']})" if len(ranked) > len(selected) else ""))
    for s in selected:
        print(f"  Stufe {s['stufe']}  score {s['score']:>6}  "
              f"{(s['journalAbbrev'] or '?')[:26]:<26}  {s['title'][:44]}")
    if len(selected) < 2:
        print("  NOTE: quiet week (<2 items). Brief will say so, not pad.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
