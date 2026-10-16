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
   Danach, für geplante UND explizite Queries: **mehrdeutige Abkürzungen**
   (`profile.md`, „Mehrdeutige Abkürzungen", z. B. HIT, ACT, MAP) werden ohne
   Anführungszeichen nie gesucht, der Code ersetzt sie durch die ausgeschriebene
   Phrase. Europe PMC sucht ohne Groß-/Kleinschreibung; ein nacktes `HIT` fand
   jedes „hit" (Benchmark 2026-10-16). **Nur geplante Queries** (nie die
   explizite einer Frage-Datei) bekommen zusätzlich eine deterministische
   Bereinigung (`clean_planned_query`): Mehrwort-Begriffe in ODER-Gruppen werden
   in Anführungszeichen gesetzt (Europe PMC verknüpft lose Wörter sonst mit UND),
   und Facetten nur aus Debattenwörtern („controversy OR debate OR
   uncertainty") fallen weg, weil sie nach Papern filtern, die diese Wörter
   benutzen, nicht nach Papern zur Frage. Der Planer läuft ohne Gemini-Denken
   (`planer_thinking_gemini: 0`), schneller, aber schlampiger; der Code fängt das.
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
   Aktualität bleibt nur ein Bonus, kein Filter. Auswahl
   (`select_papers`, seit 2026-10-16, `PLAN-retrieval-relevance.md`): **nur
   Paper, die das Subjekt der Suche nennen** (Bindestriche und Leerzeichen
   angeglichen), höchstens `max_items` (Default 20). **Kein Auffüllen** mit
   fachfremden Papern. Ausnahme: bis zu 3 **Kontext-Leitlinien** (Leitlinie,
   Herz-MeSH, Titel nennt einen Query-Begriff), dem Modell als Kontext markiert,
   nie als Beleg. Kein einziges passendes Paper: **kein Dossier** (Fehler statt
   einer selbstsicheren Antwort aus fremden Papern). Unter 5 passenden: der Code
   setzt unter den Titel einen Hinweis auf dünne Evidenz.
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
einer belegten Kurzantwort, den Abschnitten Evidenzlage / Was ist Standard / Wo die Literatur uneins ist /
Offene Fragen, der verwendeten Suchquery, einer `## Quellen`-Liste und der
Fußzeile. Struktur und harte Regeln: `dossier-vertrag.md`.

### Evidenz-Datei und Claim-Check

Neben jedem Dossier schreibt der CLI-Lauf `<datum>-<slug>.evidence.json`: die
Frage, die Suchqueries, die rohe Modell-Prosa vor `finalize` und pro Paper genau
das `evidence_basis`, das die Synthese gesehen hat, mit Provenienz aus dem Code
(`praxis_check.evidence_record`). Ohne diese Datei lässt sich kein Dossier
nachprüfen oder wiederholen.

`scripts/check_claims.py <dossier.md>` ist ein **Screen, kein Beweis**: ein
FAIL lohnt das Nachlesen, ein sauberes Ergebnis heißt nicht, dass die Zahlen
stimmen. Es prüft deterministisch, ob die Zahlen zurückführbar sind, und zwar
gegen alle Zahlen im zitierten Text, nicht gebunden an die Worte um die Zahl
herum. Die bekannten Lücken stehen als erwartete Fehler in
`scripts/test_check_claims.py` (`known_failures`). Eine Zahl gehört zum Beleg ihres Satzes (auch innerhalb der
Klammer); hat der Satz keinen, muss der Beleg des Satzes davor oder danach sie
tragen. FAIL, wenn eine Zahl nicht im Text des zitierten Papers steht (Rundung
und a/b als Prozent erlaubt; Dosis-Einheiten inklusive mg/kg/h, mmHg und %
müssen mit derselben Einheit dort stehen, gängige Schreibweisen werden
angeglichen, Zeiteinheiten nicht gebunden), wenn eine Prozentzahl, die die
Quelle als a/b herleitet, sprachlich an eine kleinere andere Fallzahl gebunden
ist („94 % von 43 Patienten" statt 46/49), oder wenn eine PMID gar nicht in der
Evidenz war. WARN, wenn ein Dosiswert nur neben einer unbekannten
Einheiten-Schreibweise steht, für Kurzantwort-Zahlen, die der
ausführliche Teil nicht wiederholt, für Prozentzahlen fern der übrigen Zahlen
ihrer Aussage, für Zahlen ohne Beleg, für eine Kurzantwort, die auf Abstracts
ruht, ohne es zu sagen, und für [VOLLTEXT]-Paper, bei denen nur ein Stummel
ankam. Der CLI-Lauf zeigt nur eine Warnzeile, blockiert nichts.

**Zitat-Anker (seit 2026-10-16, `PLAN-quote-anchoring.md`).** Das Modell belegt
jede tragende Aussage mit `(PMID ...: "wörtliches Zitat")` (Vertrag, „Belege mit
wörtlichem Zitat"). Der Code trennt die Zitate direkt nach der Synthese ab, noch
vor Prüfung, Web-Stream und Gedankenstrich-Strip; gezeigt wird nur
`(PMID ...)`, die Rohfassung mit Zitaten steht in `synthesis_raw` und `anchors`
der Evidenz-Datei. Für zitierte Aussagen prüft `check_claims.py`, ob das Zitat
im Paper steht und ob jede Zahl der Aussage in IHREM Zitat steht, nicht irgendwo
im Paper. Das schließt die Pool-Lücken für diese Aussagen. Aussagen ohne Zitat
laufen weiter durch den Pool-Screen (WARN `unanchored`). Ob die Zitate verlässlich
genug kommen, entscheidet der Benchmark (Schwelle: 95 % der Aussagen zitiert,
90 % der Zitate wörtlich); darunter folgt Claude Citations (Option B).

Grenzen: geprüft werden Zahlen, nicht Bedeutung. Ob Population, Setting oder
Schlussfolgerung zum Paper passen, sieht das Skript nicht. Absichtlich
übersprungen und in der Abdeckungszeile gezählt: ganze Zahlen bis 10 ohne
Dosis-Einheit oder %, vierstellige Jahreszahlen ohne Zählwort, an Buchstaben
geklebte Kennungen (IL-6). Zahlwörter („drei", „one year") sieht es nicht. Ältere Dossiers
bekommen ihre Evidenz-Datei mit `scripts/rebuild_evidence.py` (neu von Europe
PMC geholt, als `reconstructed` markiert). Tests mit gesetzten Fehlern:
`scripts/test_check_claims.py`. Die Web-App speichert die Datei noch nicht.

### Zwei Lesetiefen, eine autoritative Synthese

Die Kurzantwort beantwortet eine Literaturfrage direkt, ohne allgemeine
Einleitung. Ziel sind 120 bis 180 Wörter und höchstens drei belegte Stichpunkte.
Sie nennt relevante Unsicherheit und Abstract-only-Grenzen schon im kurzen
Text. Die ausführliche Evidenz bleibt zum Nachlesen erhalten.

Beide Teile entstehen im vorhandenen Synthese-Aufruf aus denselben gelieferten
Quellen. Keine zweite Zusammenfassung durch einen unabhängigen Web-LLM und
keine Änderung von Retrieval, Ranking oder deterministischer Quellenmontage.
Die ausführlichen Schreibregeln stehen nur in `dossier-vertrag.md`.

Die Web-Darstellung zeigt die Kurzantwort zuerst, das ausführliche Dossier
aufklappbar und die Quellen unabhängig erreichbar. Suchanfragen bleiben
einsehbar, die feste Fußzeile bleibt außerhalb der aufklappbaren Bereiche
sichtbar. Ältere Dossiers ohne gültige Kurzantwort bleiben vollständig lesbar.
CLI und Telegram behalten das vollständige Dossier.

Die Zweckgrenze aus `README.md`, Abschnitt „Regulatory boundary", bleibt
maßgeblich: bibliografische Recherche und Evidenzzusammenfassung, keine
patientenspezifische Entscheidungsunterstützung. Dieser Vertrag ersetzt keine
regulatorische Klassifizierung oder Konformitätsprüfung.

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
- **CLI und Web unterscheiden.** Im dateibasierten Ablauf ein Dossier pro
  Frage-Datei und Lauf. Die Web-Oberfläche bietet inzwischen browserlokalen
  Verlauf und Vertiefungsfragen. Jede Vertiefung ist ein neuer geschützter
  Praxis-Check, kein unabhängiger klinischer Chatbot. Keine Patientendaten
  eingeben, auch nicht in Verlauf oder Vertiefungen.
