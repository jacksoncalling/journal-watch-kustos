# Frage: Kortikosteroide und Medikamenten-Timing um das Lösen der Aortenklemme

> Demo-Frage im Methoden-Repo (die Pilotfrage aus Interview 1, Situation A).
> Enthält keine personenbezogenen Daten. Echte Fragen leben im privaten Repo.

## Frage

Rund um das Lösen der Aortenklemme in der Herzchirurgie machen es verschiedene
Anästhesist:innen unterschiedlich: Kortikosteroid-Gabe und die Wahl und das
Timing der Medikamente variieren („jeder macht sein eigenes Ding"). Was sagt die
aktuelle Evidenz zu Strategien, Medikamentenwahl und Timing rund um Abklemmen
und Reperfusion? Was gilt als Standard, und wo ist die Fachgemeinschaft uneins?

## Kontext

Anlass: Übergang in die Kardioanästhesie, beobachtete Praxisvarianz im OP. Die
Frage zielt auf die Evidenz hinter den Varianten (Gewohnheit vs. Studienlage),
nicht auf konkrete Dosierungen am Patienten.

max_items: 20

## Query

<!-- Optional. Steht hier ein ```query-Block, wird er wörtlich benutzt und der
     LLM-Übersetzungsschritt entfällt. Für die Demo ist eine explizite Query
     gesetzt, damit der Lauf voll deterministisch reproduzierbar ist. Zum Testen
     des Hybrid-Übersetzungspfads diesen Block leeren. -->

```query
(corticosteroid* OR steroid* OR methylprednisolone OR dexamethasone) AND ("aortic cross-clamp" OR "aortic cross clamp" OR "aortic unclamping" OR reperfusion OR "cardiopulmonary bypass") AND ("cardiac surgery" OR "cardiac anaesthesia" OR "cardiac anesthesia") AND SRC:MED
```
