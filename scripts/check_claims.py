#!/usr/bin/env python3
"""Claim checker for a Praxis-Check dossier: do the numbers trace back?

THIS IS A SCREEN, NOT PROOF. A FAIL is worth reading; a clean result does not
mean the numbers are right. Matching is pool-based: a claim number counts as
backed if the same value (and unit) appears anywhere in the cited evidence
text, not tied to the words around it. Three cold-review rounds (2026-10-15/16)
showed what slips through; the open holes are kept as expected failures in
`test_check_claims.py` (`known_failures`). The fix for that class is matching
in context, not more patterns.

`verify_dossier.py` proves the safety layer survived (footer, no dashes, every
PMID backed by a Quellen entry). It cannot see whether a sentence says what its
paper says: a real PMID can carry a wrong number. This script checks that,
deterministically, against the evidence the synthesis call actually saw
(`<dossier>.evidence.json`, written by praxis_check.py since 2026-10-15).

A claim is a sentence segment ending in a citation group (`(PMID ...)`,
`[PMID ...]`, `(vgl. PMID ...)`); numbers inside the bracket belong to it. A
sentence with numbers and no citation leans on the citation of the sentence
before or after it and must be backed by one of them; only with neither is it
left unchecked.

  FAIL  number    a claim number is not in the cited papers' evidence text.
                  Rounding and a/b -> percent are allowed. Numbers with a dose
                  unit (mg, mg/kg, mg/kg/h, g, ml, IU ...), mmHg or % must stand
                  in the source with the SAME unit (spelling variants such as
                  mg kg-1 h-1, mg/kg/hr, mm Hg, U = IE = units are normalised);
                  time units are not bound.
  FAIL  pctden    a percentage that the source derives as a/b ("46/49", "46 of
                  the 49", "46 (94%) of 49") is tied by the claim's wording
                  ("von/bei/unter 43 Patienten") to a count that is neither a nor
                  b and smaller than b: the CHOOSE-ON case. A larger count is
                  read as the trial's total N.
  FAIL  phantom   a number after a PMID label anywhere in the prose is not in
                  the evidence
  WARN  pairing   a percentage is in the source but never near the other numbers
                  of its (single-source) claim
  WARN  brief     a Kurzantwort number the detailed sections never repeat for
                  any PMID of the same claim
  WARN  abstract  the Kurzantwort rests on abstract-only papers, never says so
  WARN  thin      a paper labelled [VOLLTEXT] whose text reaching the model is a
                  stub (e.g. "available as a PDF")
  WARN  unit      a dose value (above 10 or with decimals) is in the source, but
                  only next to a unit spelling this script does not recognise
  WARN  uncited   numbers with no citation in the sentence or either neighbour
  WARN  nobrief   a new-format dossier without a ## Kurzantwort heading
  INFO            length, abstract-only share, how many numbers were checked
                  and how many were skipped as structure

Skipped on purpose (counted in the coverage line, never silently): integers up
to 10 without a dose unit or % ("3 Studien", "Typ 2", "1 Jahr"), plain four-digit
years without a count noun, identifiers glued to letters (IL-6, COVID-19).

What this does NOT do: judge whether a claim's wording, population or setting
matches its source. A number that is in the paper can still be attached to the
wrong conclusion. Those need a reader (or a calibrated judge), not this script.

Usage:
  python scripts/check_claims.py <dossier.md>             # evidence next to it
  python scripts/check_claims.py <dossier.md> --evidence <file.json>
  python scripts/check_claims.py <dossier.md> --json      # machine-readable
Exit 1 if any FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Any bracket group that mentions a PMID: (PMID 1, 2), (PMIDs 1; 2),
# (vgl. PMID 1), [PMID 1], (Studie, PMID: 1).
PMID_GROUP = re.compile(r"[(\[][^()\[\]]*?\bPMIDs?\b[^()\[\]]*[)\]]")
PMID_NUM = re.compile(r"\d{5,9}")
PMID_FREE = re.compile(r"\bPMIDs?\s*:?\s*((?:\d{5,9}[\s,;]*(?:PMID\s*:?\s*)?)+)")
NUM_TOKEN = re.compile(r"\d+(?:[.,]\d+)*")
# Source side also reads "P = .003" (leading-dot decimal), "41 021" (thin or
# no-break space as thousands separator) and "0·87" (Lancet middle-dot decimal).
SRC_NUM_TOKEN = re.compile(r"\d+·\d+|\d{1,3}(?:[  \xa0]\d{3})+|(?<![\d.])\.\d+|\d+(?:[.,]\d+)*")
LETTER = re.compile(r"[A-Za-zÄÖÜäöüß]")

# Unit right after a number. Dose units may be compound (mg/kg/h, mg kg-1 h-1,
# mg.kg-1.h-1, mg/kg per hour, mg/kgKG, mg pro kg). `%` also as Prozent /
# percent. Time units are recognised but not bound (30 Tage vs "30-day" vs "one
# month" is wording, not a finding).
_PER_UNIT = r"(?:kilograms?|kg(?:\s?kg)?|m2|m²|min|ml|dl|hours?|hr|h|d|l)"
_PER = (r"(?:\s?(?:/|·|\*|\.|\s?\bper\b|\s?\bpro\b|\s)\s?" + _PER_UNIT + r"(?![a-zäöü])"
        r"(?:\s?\(?[-−–]\s?1\)?|⁻¹)?)")
UNIT = re.compile(
    r"^\s?-?\s?(?:"
    r"(?P<pct>%|prozent\b|percent\b|per\s?cent\b)"
    r"|(?P<mmhg>mm\s?hg\b)"
    r"|(?P<base>mmol|µmol|micrograms?|microg|mcg|μg|µg|ug|milligrams?|mg|ng|ml|"
    r"units?|einheiten|ie|iu|g|l|u)(?P<per>" + _PER + r"*)(?![a-zäöü])"
    r"|(?P<time>h|hrs?|hours?|std|stunden?|min|minutes?|minuten?|d|days?|tagen?|tage?"
    r"|weeks?|wochen?|months?|monaten?|monate?|years?|jahren?|jahre?)(?![a-zäöü])"
    r")", re.I)
# Between a number and its unit only further numbers of a range or list:
# "15 bis 30 mg/kg", "250 and 250 mg", "4.6 ± 1.2 %". Never "/" or "(", so the
# 46 in "46/49 (94%)" does not become a percent; never ",", so the 0,70 in
# "RR 0,70, 95 % CI" does not either.
GAP = re.compile(
    r"^(?:\s?(?:[-–−]|±|bis|und|oder|bzw\.?|vs\.?|to|and|or|versus)\s?\d[\d.,]*)*",
    re.I)
COUNT_NOUN = re.compile(
    r"^\s?(?:Patient|Teilnehm|Proband|Kinder|Erwachsene|Fälle|Frauen|Männer|"
    r"participants|patients|subjects|children|adults)", re.I)
# a/b in the source: "46/49", "46 of 49", "46 of the 49", "46 (94%) of 49".
RATIO = re.compile(
    r"(\d[\d.,]*)\s*(?:\(\s*\d[\d.,]*\s*%\s*\)\s*)?(?:/|of|out of|von|aus)\s*"
    r"(?:the\s+|all\s+|den\s+|insgesamt\s+)?(\d[\d.,]*)", re.I)
# A cohort count in a claim: followed by a count noun (also "HIT-Patienten"),
# reached from a linking word ("94 % von 43 Patienten", "bei den 43 Patienten").
COUNT_AFTER = re.compile(
    r"^\s?(?:[\w-]+\s){0,2}?[\w-]*(?:Patient|Teilnehm|Proband|Kinder|Erwachsene|"
    r"Fälle|Frauen|Männer|participants|patients|subjects|children|adults)", re.I)
COUNT_LINK = re.compile(
    r"(?:\b(?:von|bei|unter|aus|der|mit|in|of|among)\s+"
    r"(?:den\s+|insgesamt\s+|the\s+|all\s+)?|\bn\s*=\s*)$", re.I)
# A source number with no recognised unit is a candidate for "unit spelled in
# a way this script does not know" only if a unit-like word follows it
# ("40 Milligramm", "5 Einheiten"). A count ("30 children"), a score ("BIS 40")
# or anything else is not, so it can never soften a wrong dose to WARN.
UNITISH = re.compile(
    r"^\s?[A-Za-zµμ]*(?:gram|gramm|mol|liter|litre|unit|einheit|kilo)[A-Za-z]*", re.I)
ABBREV = re.compile(
    r"\b(?:vs|bzw|ca|ggf|inkl|evtl|vgl|Abb|Tab|Dr|Prof|Nr|mind|etc|resp|"
    r"z\.\s?B|d\.\s?h|u\.\s?a|i\.\s?v|s\.\s?c|p\.\s?o)\.", re.I)
DOT = "\u0000"
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\"„(\[*])")
SRC_SENT_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(\[])")
BRIEF = "Kurzantwort"
STOP_HEADINGS = ("Verwendete Suchanfrage", "Quellen")
THIN_CHARS = 400


# --------------------------------------------------------------------------- #
# numbers
# --------------------------------------------------------------------------- #
THOUSANDS = re.compile(r"[1-9]\d{0,2}([.,]\d{3})+")


def claim_values(tok: str, count_follows: bool = False) -> list[tuple[float, int]]:
    """German claim token -> candidate (value, decimal places). A single
    separator before exactly three digits is ambiguous (German `4.494` or
    `1,125`, English `7,507` or `1.125`), so both readings are kept, except
    when a count noun follows ("2.000 Patienten") or the fraction ends in 0
    ("1.500"): then it is thousands only, so a stray 2 or 1.5 in the source
    cannot back a wrong sample size."""
    if "." in tok and "," in tok:
        dec = "." if tok.rfind(".") > tok.rfind(",") else ","
        other = "," if dec == "." else "."
        t = tok.replace(other, "").replace(dec, ".")
        return [(float(t), len(t.split(".")[1]))] if t.count(".") == 1 else []
    if THOUSANDS.fullmatch(tok):
        cands = [(float(re.sub(r"[.,]", "", tok)), 0)]
        if (len(re.findall(r"[.,]", tok)) == 1 and not count_follows
                and not tok.endswith("0")):
            cands.append((float(tok.replace(",", ".")), 3))
        return cands
    t = tok.replace(",", ".")
    if t.count(".") > 1:
        return []
    return [(float(t), len(t.split(".")[1]) if "." in t else 0)]


def source_value(tok: str) -> float | None:
    """English source token: `,` before three-digit groups is thousands, `.` is
    the decimal point. A lone `,` before other digits is a German decimal.
    A middle dot between digits is the Lancet decimal point (0·87)."""
    tok = re.sub(r"(?<=\d)·(?=\d)", ".", tok)
    tok = re.sub(r"[  \xa0]", "", tok)
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", tok):
        return float(tok.replace(",", ""))
    t = tok.replace(",", ".") if "." not in tok else tok
    if t.count(".") > 1:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def unit_after(text: str, end: int) -> tuple[str | None, str | None]:
    """(normalised unit, kind) for the number ending at `end`; kind is
    dose / pct / mmhg / time / None."""
    rest = text[end:end + 60]
    rest = rest[GAP.match(rest).end():]
    m = UNIT.match(rest)
    if not m:
        return None, None
    if m.group("pct"):
        return "%", "pct"
    if m.group("mmhg"):
        return "mmhg", "mmhg"
    if m.group("base"):
        base = m.group("base").lower()
        base = re.sub(r"^(?:micrograms?|microg|mcg|μg|ug)$", "µg", base)
        base = re.sub(r"^milligrams?$", "mg", base)
        base = re.sub(r"^(?:units?|einheiten|ie|u)$", "iu", base)
        pers = []
        per = re.sub(r"\b(?:per|pro)\b", " ", m.group("per") or "", flags=re.I)
        for p in re.findall(r"(kilograms?|kg|m2|m²|min|ml|dl|hours?|hr|h|d|l)", per, re.I):
            p = p.lower().replace("m²", "m2")
            p = "h" if p in ("hr", "hour", "hours") else p
            p = "kg" if p.startswith("kilogram") else p
            if not pers or pers[-1] != p:          # "mg/kg KG" is mg/kg
                pers.append(p)
        return "/".join([base] + pers), "dose"
    return "time", "time"


@dataclass
class Num:
    tok: str
    cands: list[tuple[float, int]]
    unit: str | None
    kind: str | None
    start: int
    end: int

    count: bool = False          # a cohort count: "43 Patienten", "43 HIT-Patienten"


def claim_numbers(text: str) -> tuple[list[Num], int]:
    """(numbers to check, numbers skipped as structure)."""
    out, skipped = [], 0
    for m in NUM_TOKEN.finditer(text):
        tok, start = m.group(0), m.start()
        prev = text[start - 1] if start else " "
        prev2 = text[start - 2] if start > 1 else " "
        if LETTER.match(prev) or (prev == "-" and LETTER.match(prev2)):
            continue                                  # IL-6, COVID-19, CD4
        if re.fullmatch(r"\d{5,9}", tok) and re.search(r"PMIDs?\s*:?\s*$", text[:start]):
            continue
        count_follows = bool(COUNT_AFTER.match(text[m.end():]))
        cands = claim_values(tok, count_follows)
        if not cands:
            continue
        unit, kind = unit_after(text, m.end())
        bound = kind in ("dose", "pct", "mmhg")
        v0 = cands[0][0]
        if (re.fullmatch(r"\d{4}", tok) and 1900 <= v0 <= 2035 and not bound
                and not COUNT_NOUN.match(text[m.end():])):
            skipped += 1
            continue
        if all(v.is_integer() and v <= 10 for v, _ in cands) and not bound:
            skipped += 1
            continue
        n_eq = bool(re.search(r"\bn\s*=\s*$", text[:start], re.I))
        is_count = (kind is None and (count_follows or n_eq) and
                    any(v.is_integer() and v > 10 for v, p in cands if p == 0))
        out.append(Num(tok, cands, unit, kind, start, m.end(), is_count))
    return out, skipped


@dataclass
class Source:
    """Numbers of one evidence text, indexed for matching."""
    text: str
    values: list[float] = field(default_factory=list)
    by_unit: dict[str, list[float]] = field(default_factory=dict)
    unitless: list[float] = field(default_factory=list)
    ratios: list[tuple[float, float, float]] = field(default_factory=list)

    @classmethod
    def of(cls, text: str) -> "Source":
        s = cls(text)
        for m in SRC_NUM_TOKEN.finditer(text):
            v = source_value(m.group(0))
            if v is None:
                continue
            s.values.append(v)
            unit, kind = unit_after(text, m.end())
            if kind in ("dose", "pct", "mmhg"):
                s.by_unit.setdefault(unit, []).append(v)
            elif kind is None and UNITISH.match(text[m.end():m.end() + 30]):
                s.unitless.append(v)
        for a, b in RATIO.findall(text):
            va, vb = source_value(a), source_value(b)
            if va is not None and vb and va <= vb:
                s.ratios.append((va, vb, 100.0 * va / vb))
        return s

    def other_dose(self, n: Num) -> list[float]:
        """Values carrying a recognised dose unit different from the claim's."""
        return [v for u, vs in self.by_unit.items()
                if u not in (n.unit, "%", "mmhg") for v in vs]

    def pool(self, n: Num) -> list[float]:
        if n.kind in ("dose", "mmhg"):
            return self.by_unit.get(n.unit, [])
        if n.kind == "pct":
            return self.by_unit.get("%", []) + [r[2] for r in self.ratios]
        return self.values + [r[2] for r in self.ratios]


def matches(n: Num, vals: list[float]) -> bool:
    """Exact, or the claim is a rounding of a source value (94 for 93.9, 1,13
    for 1.125). Half-up window [v - h, v + h) with h half a unit in the
    claim's last place, so float rounding (round(1.125, 2) == 1.12) cannot cause
    a false FAIL, and 1.5 rounds to 2, never to 1."""
    eps = 1e-9
    return any(v - 0.5 * 10 ** -p - eps <= s < v + 0.5 * 10 ** -p - eps
               for v, p in n.cands for s in vals)


# --------------------------------------------------------------------------- #
# dossier -> claims
# --------------------------------------------------------------------------- #
@dataclass
class Claim:
    section: str
    text: str
    pmids: list[str]
    numbers: list[Num]
    forward: bool = False        # numbers bound to a neighbouring sentence's citation


def _section_name(head: str) -> str:
    return BRIEF if re.match(rf"\**{BRIEF}\b", head, re.I) else head


def prose_sections(dossier: str) -> list[tuple[str, str]]:
    """(heading, body) pairs of the model prose, stopping at the code-built
    Suchanfrage/Quellen blocks. Text before the first `##` is section ''.
    A drifted `## Kurzantwort:` still counts as the brief."""
    sections, head, buf = [], "", []
    for line in dossier.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            sections.append((head, "\n".join(buf)))
            head, buf = _section_name(m.group(1)), []
            if head.startswith(STOP_HEADINGS):
                return [s for s in sections if s[1].strip()]
            continue
        if line.startswith("# "):
            continue
        buf.append(line)
    sections.append((head, "\n".join(buf)))
    return [s for s in sections if s[1].strip()]


def sentences(body: str) -> list[str]:
    """Sentences, not split after abbreviations (vs., z. B., ca., bzw. ...)."""
    out = []
    for line in body.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
        if not line:
            continue
        line = ABBREV.sub(lambda m: m.group(0).replace(".", DOT), line)
        out.extend(s.replace(DOT, ".") for s in SENT_SPLIT.split(line) if s.strip())
    return out


def group_pmids(group: str) -> list[str]:
    """PMIDs of one bracket group: only numbers after a PMID label, so
    "(n = 14590; PMID 1)" yields 1, not 14590."""
    return [p for lst in PMID_FREE.findall(group) for p in PMID_NUM.findall(lst)]


def _segments(section: str, sentence: str) -> list[Claim]:
    """Split one cited sentence at its groups. Text before a group belongs to
    that group; text after the last group belongs to every group."""
    groups = list(PMID_GROUP.finditer(sentence))
    claims, pos, all_pmids = [], 0, []
    for g in groups:
        pmids = group_pmids(g.group(0))
        all_pmids += pmids
        # "(99 %, PMID 1)": numbers inside the bracket belong to the claim
        inner = PMID_FREE.sub(" ", g.group(0)[1:-1])
        seg = sentence[pos:g.start()] + " " + inner
        claims.append(Claim(section, seg, pmids, claim_numbers(seg)[0]))
        pos = g.end()
    tail = sentence[pos:]
    nums = claim_numbers(tail)[0]
    if nums:
        claims.append(Claim(section, tail, sorted(set(all_pmids)), nums))
    return claims


def parse_claims(dossier: str) -> tuple[list[Claim], list[tuple[str, list[Num]]], int]:
    """(claims, uncited (sentence, numbers), numbers skipped as structure)."""
    claims, uncited, skipped = [], [], 0
    for head, body in prose_sections(dossier):
        sents = sentences(body)
        for i, s in enumerate(sents):
            skipped += claim_numbers(PMID_GROUP.sub(" ", s))[1]
            if PMID_GROUP.search(s):
                claims += _segments(head, s)
                continue
            nums = claim_numbers(s)[0]
            if not nums:
                continue
            # A number may lean on the citation of the sentence before
            # ("SIRS ... (PMID A). Die Mortalitaet lag bei 4,6 %.") or after
            # ("Die Rate lag bei 9 %. Das zeigte SIRS (PMID A)."). It must be in
            # one of them; only with neither is it left unchecked.
            near = [sents[j] for j in (i - 1, i + 1) if 0 <= j < len(sents)]
            pmids = sorted({p for t in near for g in PMID_GROUP.findall(t)
                            for p in group_pmids(g)})
            if pmids:
                claims.append(Claim(head, s, pmids, nums, forward=True))
            else:
                uncited.append((s, nums))
    return claims, uncited, skipped


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
@dataclass
class Finding:
    level: str                   # FAIL / WARN / INFO
    kind: str
    message: str
    excerpt: str = ""


def _short(text: str, n: int = 150) -> str:
    text = re.sub(r"\s+", " ", PMID_GROUP.sub("", text)).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _together(nums: list[Num], src: str) -> bool:
    """All numbers occur within one source sentence or two adjacent ones."""
    sents = [s for s in SRC_SENT_SPLIT.split(src) if s.strip()]
    for i in range(max(1, len(sents))):
        w = Source.of(" ".join(sents[i:i + 2]))
        if all(matches(n, w.values + [r[2] for r in w.ratios]) for n in nums):
            return True
    return False


def linked_counts(c: Claim) -> list[Num]:
    """Cohort counts the claim's wording ties a result to: a count noun after
    the number and a linking word before it ("94 % von 43 Patienten", "bei den
    43 HIT-Patienten lag der Erfolg bei 94 %"). "In SIRS (7507 Patienten)" is
    not linked: no linking word."""
    return [n for n in c.numbers
            if n.count and COUNT_LINK.search(c.text[max(0, n.start - 30):n.start])]


def check(dossier: str, evidence: dict) -> list[Finding]:
    papers = {str(p.get("pmid")): p for p in evidence.get("papers", [])}
    sources = {k: Source.of(p.get("evidence_basis") or "") for k, p in papers.items()}
    findings: list[Finding] = []
    sections = prose_sections(dossier)
    prose = "\n".join(b for _, b in sections)
    claims, uncited, skipped = parse_claims(dossier)

    # phantom PMIDs: every PMID-looking number in the prose, however it is set
    cited = {p for c in claims for p in c.pmids}
    anywhere = set()
    for grp in PMID_FREE.findall(prose):
        anywhere |= set(PMID_NUM.findall(grp))
    for p in sorted((cited | anywhere) - set(papers)):
        findings.append(Finding("FAIL", "phantom",
                                f"PMID {p} is cited but was not in the evidence"))

    for s, nums in uncited:
        findings.append(Finding(
            "WARN", "uncited",
            f"number(s) {', '.join(n.tok for n in nums)} with no citation "
            f"(this or a neighbouring sentence); not checked", _short(s)))

    n_checked = 0
    for c in claims:
        srcs = [sources[p] for p in c.pmids if p in sources]
        if not srcs or not c.numbers:
            continue
        where = f"PMID {', '.join(c.pmids)} [{c.section or 'Kopf'}]"
        if c.forward:
            where += " (citation in a neighbouring sentence)"
        found = []
        for n in c.numbers:
            n_checked += 1
            if any(matches(n, s.pool(n)) for s in srcs):
                found.append(n)
                continue
            unit = f" {n.unit}" if n.kind in ("dose", "pct", "mmhg") else ""
            # A dose value that stands in the source only WITHOUT a recognised
            # unit may be a spelling this script does not know: WARN. If it
            # stands there only with a different dose unit, or not at all: FAIL.
            # Not for small integers: a bare "2" ("2 groups") is in almost every
            # abstract and must not back "2 mg/kg".
            small = all(v.is_integer() and v <= 10 for v, _ in n.cands)
            if (n.kind == "dose" and not small
                    and any(matches(n, s.unitless) for s in srcs)
                    and not any(matches(n, s.other_dose(n)) for s in srcs)):
                findings.append(Finding("WARN", "unit",
                                        f"{n.tok}{unit}: value is in {where}, unit not "
                                        f"confirmed", _short(c.text)))
                continue
            findings.append(Finding("FAIL", "number",
                                    f"{n.tok}{unit} not found in {where}", _short(c.text)))

        # CHOOSE-ON: 94 % is 46/49 in the source; the claim ties it to 43
        # A count larger than every denominator is read as the trial's total N
        # ("bei 7507 Patienten ... 4,6 %" for 173/3755), not as an error.
        counts = linked_counts(c)
        for p in (n for n in found if n.kind == "pct"):
            ratios = [r for s in srcs for r in s.ratios if matches(p, [r[2]])]
            if not ratios or not counts:
                continue
            denoms = {x for r in ratios for x in r[:2]}
            top = max(r[1] for r in ratios)
            ok_count = any(abs(v - d) < 1e-9 or v > top
                           for n in counts for v, _ in n.cands for d in denoms)
            if not ok_count:
                shown = ", ".join(f"{r[0]:g}/{r[1]:g}" for r in ratios)
                findings.append(Finding(
                    "FAIL", "pctden",
                    f"{p.tok} % is {shown} in the source, but the claim ties it to "
                    f"{', '.join(n.tok for n in counts)} ({where})", _short(c.text)))

        # pairing: a percentage near none of its claim's other numbers
        if len(c.pmids) == 1 and len(found) >= 2:
            src = srcs[0].text
            for n in (x for x in found if x.kind == "pct"):
                others = [m for m in found if m is not n]
                if not any(_together([n, m], src) for m in others):
                    findings.append(Finding(
                        "WARN", "pairing",
                        f"{n.tok} % never occurs near "
                        f"{', '.join(m.tok for m in others)} in {where}", _short(c.text)))

    # brief vs detail
    has_brief = any(h == BRIEF for h, _ in sections)
    if has_brief:
        brief = [c for c in claims if c.section == BRIEF]
        detail = [c for c in claims if c.section not in (BRIEF, "")]
        for c in brief:
            same = [d for d in detail if set(d.pmids) & set(c.pmids)]
            reported = [x.cands[0][0] for d in same for x in d.numbers]
            for n in c.numbers:
                if not matches(n, reported):
                    findings.append(Finding(
                        "WARN", "brief",
                        f"Kurzantwort number {n.tok} (PMID {', '.join(c.pmids)}) is "
                        f"not repeated in the detailed sections", _short(c.text)))
        brief_text = next(b for h, b in sections if h == BRIEF)
        brief_pmids = {p for c in brief for p in c.pmids}
        abstract_only = sorted(p for p in brief_pmids
                               if papers.get(p, {}).get("provenance") == "[NUR ABSTRACT]")
        if abstract_only and not re.search(r"abstract", brief_text, re.I):
            findings.append(Finding(
                "WARN", "abstract",
                f"Kurzantwort cites {len(abstract_only)} abstract-only paper(s) "
                f"({', '.join(abstract_only)}) but never says the evidence is "
                f"abstract-only"))
        words = len(re.findall(r"\w+", PMID_GROUP.sub("", brief_text)))
        findings.append(Finding("INFO", "length",
                                f"Kurzantwort {words} words (target 120 to 180)"))
    elif evidence.get("reconstructed"):
        findings.append(Finding("INFO", "nobrief",
                                "no ## Kurzantwort (older dossier); brief checks skipped"))
    else:
        findings.append(Finding("WARN", "nobrief",
                                "no ## Kurzantwort heading; brief checks did not run"))

    for p in sorted(cited):
        pp = papers.get(p, {})
        basis = (pp.get("evidence_basis") or "").strip()
        if pp.get("provenance") == "[VOLLTEXT]" and len(basis) < THIN_CHARS:
            findings.append(Finding(
                "WARN", "thin",
                f"PMID {p} is labelled [VOLLTEXT] but only {len(basis)} characters "
                f"reached the model", _short(basis, 80)))

    ab = [p for p in cited if papers.get(p, {}).get("provenance") == "[NUR ABSTRACT]"]
    findings.append(Finding("INFO", "provenance",
                            f"{len(ab)} of {len(cited)} cited papers are abstract-only"))
    n_unc = sum(len(n) for _, n in uncited)
    findings.append(Finding(
        "INFO", "coverage",
        f"{len(claims)} cited claims, {n_checked} numbers checked, {n_unc} uncited "
        f"(not checked), {skipped} skipped as structure (small counts, years)"))
    return findings


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check dossier numbers against their evidence.")
    ap.add_argument("dossier")
    ap.add_argument("--evidence", help="evidence JSON (default: <dossier>.evidence.json)")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    args = ap.parse_args(argv)

    path = Path(args.dossier)
    ev_path = Path(args.evidence) if args.evidence else path.with_suffix(".evidence.json")
    if not ev_path.exists():
        print(f"no evidence file: {ev_path}\n(dossiers written before 2026-10-15 have "
              f"none; rebuild one with scripts/rebuild_evidence.py)", file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    evidence = json.loads(ev_path.read_text(encoding="utf-8"))
    findings = check(path.read_text(encoding="utf-8"), evidence)
    fails = sum(f.level == "FAIL" for f in findings)

    if args.json:
        print(json.dumps({"dossier": path.name, "evidence": ev_path.name,
                          "reconstructed": evidence.get("reconstructed", False),
                          "fails": fails,
                          "findings": [f.__dict__ for f in findings]},
                         ensure_ascii=False, indent=2))
        return 1 if fails else 0

    print(f"checking {path.name} against {ev_path.name}")
    if evidence.get("reconstructed"):
        print("  NOTE: evidence was RECONSTRUCTED after the run (re-fetched from "
              "Europe PMC); it may differ slightly from what the model saw.")
    print()
    for level in ("FAIL", "WARN", "INFO"):
        for f in findings:
            if f.level == level:
                print(f"  [{f.level}] {f.kind:<10} {f.message}")
                if f.excerpt:
                    print(f"             \"{f.excerpt}\"")
    warns = sum(f.level == "WARN" for f in findings)
    print(f"\n{fails} FAIL, {warns} WARN.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
