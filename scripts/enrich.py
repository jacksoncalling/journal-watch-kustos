#!/usr/bin/env python3
"""01_fetch enrichment: Unpaywall OA links + Europe PMC OA full text.

Runs after fetch_europepmc.py, mutates 01_fetch/output/candidates.json in place:
  - oaUrl:           legal OA copy from Unpaywall (url_for_pdf, else landing url)
  - fullTextExcerpt: abstract + results + conclusion, plain text, capped, for OA
                     items with a PMCID (drives [VOLLTEXT] vs [NUR ABSTRACT])

Stdlib only. Endpoints verified live:
  Unpaywall:  https://api.unpaywall.org/v2/<doi>?email=<contact>
  Full text:  https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML
              (single path segment, PMCID keeps its "PMC" prefix)
Both are best-effort per paper: a miss (404, not OA, no PDF) just leaves the
field null; it never fails the run.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profil" / "profile.md"
CANDIDATES = ROOT / "01_fetch" / "output" / "candidates.json"

FULLTEXT_CAP = 8000
SPACING_S = 0.2


def contact_email() -> str:
    m = re.search(r"`contact_email`\s*:\s*([^\s`]+@[^\s`]+)",
                  PROFILE.read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown@example.com"


def _get(url: str, ua: str, parse_json: bool):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if parse_json else raw


# --------------------------------------------------------------------------- #
# Unpaywall
# --------------------------------------------------------------------------- #
def unpaywall_oa_url(doi: str, email: str, ua: str) -> str | None:
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={email}"
    try:
        data = _get(url, ua, True)
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            return None
        raise
    if not data.get("is_oa"):
        return None
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")


# --------------------------------------------------------------------------- #
# Europe PMC full text
# --------------------------------------------------------------------------- #
def _strip_tags(xml_fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", xml_fragment)
    return re.sub(r"\s+", " ", text).strip()


def _section(xml: str, *sec_types: str) -> str:
    for st in sec_types:
        m = re.search(rf'sec-type="{st}"[^>]*>(.*?)</sec>', xml, re.S | re.I)
        if m:
            return _strip_tags(m.group(1))
    return ""


def fulltext_excerpt(pmcid: str, ua: str) -> str | None:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    try:
        xml = _get(url, ua, False)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    ab = re.search(r"<abstract[^>]*>(.*?)</abstract>", xml, re.S | re.I)
    abstract = _strip_tags(ab.group(1)) if ab else ""
    results = _section(xml, "results")
    concl = _section(xml, "conclusions", "conclusion")
    parts = [p for p in (abstract, results, concl) if p]
    if not parts:                       # fall back to body text
        body = re.search(r"<body[^>]*>(.*?)</body>", xml, re.S | re.I)
        if body:
            parts = [_strip_tags(body.group(1))]
    excerpt = " ".join(parts).strip()
    return excerpt[:FULLTEXT_CAP] if excerpt else None


# --------------------------------------------------------------------------- #
def main() -> int:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    email = contact_email()
    ua = f"journal-watch/0.1 (+{email})"

    oa_added = ft_added = 0
    for c in cands:
        if c.get("doi") and not c.get("oaUrl"):
            try:
                oa = unpaywall_oa_url(c["doi"], email, ua)
            except Exception as e:
                print(f"  unpaywall error for {c['doi']}: {e}", file=sys.stderr)
                oa = None
            if oa:
                c["oaUrl"] = oa
                oa_added += 1
            time.sleep(SPACING_S)

        if c.get("pmcid") and not c.get("fullTextExcerpt"):
            try:
                ft = fulltext_excerpt(c["pmcid"], ua)
            except Exception as e:
                print(f"  fulltext error for {c['pmcid']}: {e}", file=sys.stderr)
                ft = None
            if ft:
                c["fullTextExcerpt"] = ft
                ft_added += 1
            time.sleep(SPACING_S)

    CANDIDATES.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"enriched {len(cands)} candidates: +{oa_added} OA links, "
          f"+{ft_added} full-text excerpts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
