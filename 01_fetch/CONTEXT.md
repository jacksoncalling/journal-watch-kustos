# 01_fetch: Vertrag (Fetch + Enrich)

Die erste Stufe der Pipeline. Sammelt Kandidaten-Paper aus Europe PMC und
reichert sie an (OA-Links, Volltext-Auszug). Kein LLM, reiner Code.

## Eingaben

- `profil/profile.md`: die Themen (`### thema_N` mit `label` und `query`), die
  Kontakt-E-Mail (User-Agent-Etikette) und `max_items` (erst in 02 genutzt).
- `01_fetch/output/seen.json`: das Ledger bereits gelieferter Paper. Setzt das
  Startdatum des Suchfensters (`last_run_date`) und filtert schon Gesehenes
  heraus. Fehlt es, gilt ein Bootstrap-Fenster von 30 Tagen.

## Prozess

1. **`scripts/fetch_europepmc.py`** liest die Themen, sucht pro Thema einmal in
   Europe PMC über das Fenster `[last_run_date .. heute]`
   (`FIRST_PDATE:[start TO end]`), dedupliziert über Themen hinweg und gegen
   `seen.json`, und schreibt `output/candidates.json`.
   - Nur Stdlib (`urllib`). Kein API-Key nötig. User-Agent trägt die
     Kontakt-E-Mail. Ein Retry bei 5xx, sonst lauter Abbruch (Exit != 0), damit
     die GitHub Action rot meldet statt einen leeren Brief zu senden.
2. **`scripts/enrich.py`** mutiert `candidates.json` an Ort und Stelle:
   - `oaUrl`: legale OA-Kopie via Unpaywall (`url_for_pdf`, sonst Landing-URL).
   - `fullTextExcerpt`: Abstract + Results + Conclusion als Klartext, gekappt
     (~8000 Zeichen), nur für OA-Paper mit PMCID. Steuert `[VOLLTEXT]` vs.
     `[NUR ABSTRACT]` in 03. Jeder Treffer ist Best-Effort: ein Fehlschlag (404,
     nicht OA, kein PDF) lässt das Feld einfach `null`, bricht den Lauf nie ab.

## Ausgabe

`01_fetch/output/candidates.json` (`schema_version`, `window`, `count`,
`candidates[]`). Ein Datensatz pro Paper: id, pmid, doi, title, journal,
journalAbbrev, date, authors (nur erster + letzter), pubTypes, abstract,
fullTextExcerpt (nullable), oaUrl (nullable), matchedTopics. Wird von 02 gelesen.

`seen.json` wird hier **nicht** geschrieben. Nur der Orchestrator
(`run_weekly.py`) schreibt es, und erst nach bestätigtem Versand. So bleibt die
Dedup-Garantie an einer Stelle.

## Menschliche Kontrolle

Keine im Regelbetrieb (deterministisch). Beim Bau geprüft: die Europe-PMC- und
Unpaywall-Endpunkte live verifiziert, nie aus dem Gedächtnis übernommen. Wenn
Themen-Queries zu breit greifen (Grundlagenforschung statt Anästhesie-Praxis),
werden sie in `profile.md` geschärft, nicht im Code.

## Grenzen

- **Kein Bezahlschranken-Umgehen.** Jedes Paper trägt seine DOI; sie öffnet es
  mit eigenem Zugang. `oaUrl` ist nur eine legale OA-Kopie, wo Unpaywall eine
  findet.
- **Keine Patientendaten** in Queries oder Ausgaben.
- Volltext-Extraktion ist regex-basiertes Tag-Stripping, kein echtes
  JATS-Parsing (Best-Effort, siehe HANDOFF.md). Für Slice 1 ausreichend.
