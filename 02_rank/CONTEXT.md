# 02_rank: Vertrag (Ranking)

Die zweite Stufe. Weist jedem Kandidaten eine Evidenzstufe zu, bewertet ihn und
wählt die besten N aus. **Kein LLM, reiner deterministischer Code.** Die hier
gesetzte Evidenzstufe ist autoritativ: die Synthese (03) darf sie nie hochstufen.

## Eingaben

- `01_fetch/output/candidates.json`: die angereicherten Kandidaten aus 01.
- `profil/profile.md`: `max_items` (Standard 7) und die Journal-Trust-Liste
  (kleiner Ranking-Bonus für benannte Zeitschriften).
- `profil/kanon.md`: gelernte Vorlieben. Slice 1: einfacher Keyword-Overlap,
  keine Embeddings. Im Methoden-Repo leer (Demo).

## Prozess

**`scripts/rank.py`**:

1. **Evidenzstufe** aus den Europe-PMC-`pubTypes` (`evidence_level`, importierbar
   und in `test_rank.py` getestet):
   - Stufe 1: Meta-Analyse, Systematic Review, oder multizentrische RCT.
   - Stufe 2: RCT, Kohorte/Observational, Leitlinie.
   - Stufe 3: Case Report, Letter, Editorial, narrativer Review, alles Übrige.
2. **Score**, bewusst einfach und lesbar:
   `score = Evidenzgewicht (dominant) + Themen-Treffer + Journal-Trust-Bonus
   + Aktualität + kanon.md-Keyword-Overlap`.
   - Journal-Match über normalisierte Gleichheit (kleingeschrieben,
     Interpunktion entfernt), nicht über fragiles Substring-Matching.
   - Aktualität boostet nur die letzten ~30 Tage; ältere Paper werden nicht
     bestraft.
3. Sortiert absteigend, nimmt die obersten `max_items`. Bei weniger als 2
   Treffern: `quiet_week = true`. Der Brief sagt das ehrlich, füllt nie auf.

## Ausgabe

`02_rank/output/selected.json` (`schema_version`, `window`, `count`,
`quiet_week`, `selected[]`). Jedes Item ist der Kandidat plus `stufe`, `score`
und `score_breakdown`. Wird von 03 gelesen. Interne Felder (`score`, `stufe`)
gehen nie roh an das Modell: 03 baut daraus eine schlanke `paper_payload`.

## Menschliche Kontrolle

Keine im Regelbetrieb. Das Mapping `pubType -> Stufe` ist die einzige heikle
Stelle und ist durch `test_rank.py` (12/12) abgedeckt. Änderungen am Mapping
brauchen einen neuen Test.

## Grenzen

- Die Evidenzstufe ist eine grobe, transparente Heuristik aus Publikationstypen,
  kein methodisches Qualitätsurteil. Sie steuert Kalibrierung und Sortierung,
  ersetzt keine kritische Lektüre. Die Fußzeile in 03 bleibt Pflicht.
- Keine Embeddings, keine Datenbank (Slice 1). `kanon.md` wächst langsam und von
  Hand.
