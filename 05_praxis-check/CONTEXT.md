# 05_praxis-check: Vertrag (Praxis-Check, die Suchfunktion)

Der **zweite Artefakt-Typ**. Nicht wöchentlich, sondern anlassbezogen: eine
Frage der Form „Für Prozedur/Entscheidung X: Was ist die aktuelle Evidenz, was
ist Standard, wo ist die Kontroverse?" Ergebnis ist **ein Dossier pro Frage**,
kein Newsletter-Item. Herkunft und Pilotfrage: Interview 1, Situation A
(`../step-into-more/projects/journal-watch/interview-notes/2026-08-16-interview-1.md`,
Lesart Punkt 2). Spec: `build-plan.md` §7.

Diese Stufe **baut die Slice-1-Pipeline nicht neu**. `scripts/praxis_check.py`
importiert die geprüften Funktionen aus 01 bis 03 und komponiert sie neu: eine
tiefere, **nicht gefensterte** Suche pro Frage, ein Dossier-Prompt statt des
Wochenbrief-Prompts. Die Wochenbrief-Skripte werden dabei nicht angefasst.

## Eingaben

- `fragen/*.md`: eine Markdown-Frage pro Datei (Format unten). Die neueste Datei
  wird per Default verarbeitet, oder gezielt via `--frage <pfad>`.
- `profil/profile.md`: Kontakt-E-Mail, Provider-Wahl (Synthese), Journal-Trust.
- `profil/kanon.md`: gelernte Vorlieben (Keyword-Overlap im Ranking).
- `dossier-vertrag.md`: der Synthese-Vertrag für das Dossier (wird wörtlich in
  den System-Prompt gelesen, analog zu `03_brief/CONTEXT.md` beim Wochenbrief).

### Format einer Frage-Datei (`fragen/<datum>-<slug>.md`)

```markdown
# Frage: <kurzer Titel>

## Frage

<Die Frage in ihren eigenen Worten, Deutsch. Diese Prosa rahmt das Dossier und
wird, falls unten keine Query steht, in eine Suchquery übersetzt.>

## Kontext

<Optional: klinischer Anlass, was sie schon weiß, warum jetzt.>

## Query

<Optional. Wenn hier ein Europe-PMC-Query-Block steht, wird er WÖRTLICH benutzt
(deterministisch, kein Übersetzungsschritt). Bleibt er leer, übersetzt ein
LLM-Schritt die Frage oben in ein bis drei Queries.>

```query
("aortic cross-clamp" OR reperfusion) AND (corticosteroid* OR steroid*) AND SRC:MED
```
```

Der `max_items`-Wert kann pro Frage überschrieben werden mit einer Zeile
`max_items: <N>` im Kontext-Abschnitt (Default 20).

## Prozess (`scripts/praxis_check.py`)

1. **Frage lesen** (Titel, Prosa-Frage, Kontext, optionale Query).
2. **Query bestimmen (Hybrid).** Explizite Query vorhanden -> wörtlich nutzen.
   Sonst **ein** LLM-Schritt (Query-Planung) übersetzt die deutsche Frage in ein
   bis drei Europe-PMC-Booleans. Dieser Schritt erzeugt nur Suchstrings, nie
   klinische Aussagen; die Provenienz-Garantien bleiben unberührt. Die
   verwendeten Queries werden geloggt und ins Dossier übernommen (Transparenz).
3. **Fetch (all-time).** Reuse `fetch_europepmc.search_topic`, aber mit
   Startdatum `1900-01-01`, also **ohne** Wochenfenster, und mit
   `sort="CITED desc"` plus einem tiefen Pool (`page_size=200`). Grund: der
   Europe-PMC-Default sortiert nach Datum, ein 50er-Fenster lieferte also nur die
   50 **neuesten** Paper und die alten Landmark-Studien nie. Zitations-Sortierung
   plus tiefer Pool holt sie herein. Kein `seen.json`: der Praxis-Check will
   bewusst auch Gesehenes zeigen. (`search_topic` bekam dafür zwei optionale
   Parameter mit Default `None`, der Wochenlauf ruft es unverändert auf.)
4. **Rank (all-time).** Reuse `rank.evidence_level` + `rank.score`, plus ein
   **Praxis-eigener Titel-Relevanz-Bonus**: Zitations-Sortierung schwemmt sonst
   hochzitierte, aber fachfremde Paper nach oben (die breiten OR-Terme matchen
   berühmte Reviews aus anderen Feldern). Der Bonus zählt, wie viele Query-
   Begriffe im **Titel** stehen, und hebt so on-topic-Studien über fachfremde.
   Aktualität bleibt nur ein Bonus, kein Filter. Nimm die obersten `max_items`
   (Default 20).
5. **Enrich der Top-N.** Erst nach dem Ranking (der Korpus ist groß): OA-Link +
   Volltext-Auszug via `enrich`-Funktionen nur für die ausgewählten Paper.
6. **Synthese (der eine LLM-Aufruf pro Dossier).** System-Prompt =
   `dossier-vertrag.md` + Profil + die Prosa-Frage. User = die gerankten Paper.
   Ein Aufruf, gleiche Provider-Wahl wie der Wochenbrief (Gemini Flash zuerst).
7. **Quellen deterministisch.** Der Code hängt eine `## Quellen`-Sektion an: pro
   Paper Stufe, `[VOLLTEXT]`/`[NUR ABSTRACT]`, DOI/PubMed/OA-Links (reuse
   `synthesize.fact_line`). Das Modell zitiert im Fließtext nur mit `(PMID …)`
   und schreibt keine Labels selbst. Danach Gedankenstrich-Strip und Fußzeile.
8. **Zustellen + ablegen.** Dossier nach `output/<datum>-<slug>.md`, Versand per
   Telegram (reuse `send_telegram`-Funktionen), Commit erledigt die Action.

## Ausgabe

`05_praxis-check/output/<datum>-<slug>.md`: ein Dossier mit Kopf (die Frage),
den Abschnitten Evidenzlage / Was ist Standard / Wo die Literatur uneins ist /
Offene Fragen, der verwendeten Suchquery, einer `## Quellen`-Liste und der
Fußzeile. Struktur und harte Regeln: `dossier-vertrag.md`.

## Menschliche Kontrolle

Sie (via Josh) formuliert die Frage und triggert den Lauf (`workflow_dispatch`
oder lokal). Sie liest das Dossier und öffnet Quellen mit eigenem Zugang. Die
generierten Suchqueries stehen im Dossier, damit sie nachvollziehen kann, wonach
gesucht wurde. Das Dossier ersetzt keine klinische Entscheidung.

## Grenzen (wie Slice 1, plus)

- **Keine Dosierung als Empfehlung.** Situation A berührt Medikamente und Timing.
  Die Linie: zusammenfassen, was Studien über Strategien, Medikamentenwahl und
  Timing berichten; nie eine konkrete Dosis als Handlungsempfehlung herausheben.
- **Kontroverse ist Pflicht, nicht Kür.** Konsens wird nie simuliert. Wo die
  Fachgemeinschaft uneins ist, sagt das Dossier es plain.
- Evidenzstufe und Provenienz setzt der Code, nie das Modell. Keine
  Patientendaten, kein Bezahlschranken-Umgehen, keine Gedankenstriche.
- **Kein interaktiver Chat.** Ein Dossier pro Frage-Datei, ein Lauf. Der
  interaktive Bot (Slice 2) ist bewusst nachrangig und evtl. nie nötig.
