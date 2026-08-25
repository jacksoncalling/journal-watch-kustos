#!/usr/bin/env python3
"""01_fetch: Europe PMC stage.

Reads profil/profile.md, runs one Europe PMC search per topic over the window
[last_run_date .. today], dedupes across topics and against the committed
seen.json ledger, and writes 01_fetch/output/candidates.json.

Stdlib only (urllib). RSS, Unpaywall enrichment and OA full-text fetch are
separate steps (build-plan.md 5.1, build order step 5) and are NOT done here.

Fails loudly (nonzero exit) on persistent API errors so the GitHub Action
reports red instead of sending an empty brief.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profil" / "profile.md"
OUT_DIR = ROOT / "01_fetch" / "output"
SEEN = ROOT / "01_fetch" / "output" / "seen.json"

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE = 50
BOOTSTRAP_DAYS = 30          # first-ever run window when no seen.json exists
DEFAULT_WEEKLY_DAYS = 7      # fallback if last_run_date is unreadable
REQUEST_SPACING_S = 0.25     # stay well under ~5 req/s


# --------------------------------------------------------------------------- #
# profile.md parsing (single source of truth; keep it human-readable)
# --------------------------------------------------------------------------- #
def parse_profile(text: str) -> dict:
    email_m = re.search(r"`contact_email`\s*:\s*([^\s`]+@[^\s`]+)", text)
    contact_email = email_m.group(1) if email_m else None

    topics = []
    current = None
    for line in text.splitlines():
        h = re.match(r"^###\s+(thema_\S+)", line)
        if h:
            current = {"id": h.group(1), "label": None, "query": None}
            topics.append(current)
            continue
        if current is None:
            continue
        lab = re.match(r"^-\s+`label`\s*:\s*(.+?)\s*$", line)
        if lab:
            current["label"] = lab.group(1)
            continue
        q = re.match(r"^-\s+`query`\s*:\s*`(.+)`\s*$", line)
        if q:
            current["query"] = q.group(1)

    topics = [t for t in topics if t["query"]]
    for t in topics:                       # a query without a label must not crash
        t["label"] = t["label"] or t["id"]
    return {"contact_email": contact_email, "topics": topics}


# --------------------------------------------------------------------------- #
# ledger
# --------------------------------------------------------------------------- #
def load_seen() -> dict:
    if SEEN.exists():
        return json.loads(SEEN.read_text(encoding="utf-8"))
    return {"last_run_date": None, "seen_ids": []}


def window_start(seen: dict) -> str:
    if seen.get("last_run_date"):
        try:
            datetime.strptime(seen["last_run_date"], "%Y-%m-%d")
            return seen["last_run_date"]
        except ValueError:
            pass
        return (date.today() - timedelta(days=DEFAULT_WEEKLY_DAYS)).isoformat()
    return (date.today() - timedelta(days=BOOTSTRAP_DAYS)).isoformat()


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def fetch_json(url: str, ua: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    last_err = None
    for attempt in range(2):  # one retry
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            code = getattr(e, "code", None)
            # Retry only on transient server-side failures / network blips.
            if code is not None and not (500 <= code < 600):
                raise
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Europe PMC request failed after retry: {last_err}\n{url}")


def search_topic(query: str, start: str, end: str, ua: str,
                 sort: str | None = None, page_size: int | None = None) -> list[dict]:
    """Europe PMC search over [start .. end].

    `sort` and `page_size` are optional and default to the weekly behaviour:
    with sort=None no sort param is sent (Europe PMC then orders by date, which
    is fine inside a 7-day window). The Praxis-Check passes sort="CITED desc" so
    an all-time search surfaces the most-cited landmark papers instead of just
    the newest 50. Weekly callers omit both, so their behaviour is unchanged.
    """
    dated = f"({query}) AND FIRST_PDATE:[{start} TO {end}]"
    params = {
        "query": dated,
        "format": "json",
        "resultType": "core",
        "pageSize": str(page_size if page_size is not None else PAGE_SIZE),
    }
    if sort:
        params["sort"] = sort
    url = BASE + "?" + urllib.parse.urlencode(params)
    data = fetch_json(url, ua)
    return data.get("resultList", {}).get("result", [])


# --------------------------------------------------------------------------- #
# record normalisation
# --------------------------------------------------------------------------- #
def first_last_authors(author_string: str | None) -> list[str]:
    if not author_string:
        return []
    parts = [p.strip() for p in author_string.split(",") if p.strip()]
    if len(parts) <= 2:
        return parts
    return [parts[0], parts[-1]]


def journal_title(rec: dict) -> str | None:
    j = rec.get("journalInfo", {}).get("journal", {})
    return j.get("title") or j.get("medlineAbbreviation") or j.get("isoabbreviation")


def journal_abbrev(rec: dict) -> str | None:
    j = rec.get("journalInfo", {}).get("journal", {})
    return j.get("medlineAbbreviation") or j.get("isoabbreviation")


def dedupe_key(rec: dict) -> str:
    return (rec.get("doi") or rec.get("pmid") or rec.get("id") or "").lower()


def normalise(rec: dict, matched: list[str]) -> dict:
    return {
        "id": rec.get("id"),
        "pmid": rec.get("pmid"),
        "doi": rec.get("doi"),
        "title": rec.get("title"),
        "journal": journal_title(rec),
        "journalAbbrev": journal_abbrev(rec),
        "date": rec.get("firstPublicationDate"),
        "authors": first_last_authors(rec.get("authorString")),
        "pubTypes": rec.get("pubTypeList", {}).get("pubType", []),
        "abstract": rec.get("abstractText"),
        "isOpenAccess": rec.get("isOpenAccess") == "Y",
        "pmcid": rec.get("pmcid"),
        "fullTextExcerpt": None,   # 01_fetch step 5
        "oaUrl": None,             # 01_fetch step 5 (Unpaywall)
        "matchedTopics": matched,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    if not PROFILE.exists():
        print(f"profile not found: {PROFILE}", file=sys.stderr)
        return 1
    profile = parse_profile(PROFILE.read_text(encoding="utf-8"))
    if not profile["topics"]:
        print("no topics with queries found in profile.md", file=sys.stderr)
        return 1
    contact = profile["contact_email"] or "unknown@example.com"
    ua = f"journal-watch/0.1 (+{contact})"

    seen = load_seen()
    already = set(seen.get("seen_ids", []))
    start = window_start(seen)
    end = date.today().isoformat()

    print(f"window: {start} .. {end}  |  topics: {len(profile['topics'])}")

    by_key: dict[str, dict] = {}
    for t in profile["topics"]:
        results = search_topic(t["query"], start, end, ua)
        print(f"  {t['id']:<10} {t['label'][:44]:<44} -> {len(results)} hits")
        for rec in results:
            key = dedupe_key(rec)
            if not key or key in already:
                continue
            if key in by_key:
                if t["label"] not in by_key[key]["matchedTopics"]:
                    by_key[key]["matchedTopics"].append(t["label"])
            else:
                by_key[key] = normalise(rec, [t["label"]])
        time.sleep(REQUEST_SPACING_S)

    candidates = list(by_key.values())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "candidates.json"
    out.write_text(
        json.dumps(
            {"schema_version": "1.0",
             "window": {"start": start, "end": end}, "count": len(candidates),
             "candidates": candidates},
            ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"wrote {len(candidates)} new candidates -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
