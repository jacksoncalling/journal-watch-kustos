# 04_feedback: Vertrag (Feedback -> Kanon)

> **Status: noch nicht gebaut (Slice 1.5).** Dies ist der Entwurfsvertrag für die
> langsame Lernschleife, damit die Stufe walkbar ist und ein späterer Lauf sie
> nach Plan bauen kann. Der **aktuelle Workaround** ist bewusst menschlich: sie
> textet Josh, was nützlich war, und Josh trägt es von Hand in `profil/kanon.md`
> ein. Das hält den Menschen in der Schleife und genügt, bis der erste Brief
> gelaufen ist. Nicht bauen, bevor Slice 1 live bei ihr läuft.

Die vierte Stufe schließt den Kreis: aus ihrer Reaktion auf Briefe und aus
Papern, die sie selbst speichert, wächst `profil/kanon.md`. Der Kanon fließt in
02_rank zurück (Keyword-Overlap-Bonus), sodass das Ranking mit der Zeit ihre
Vorlieben spiegelt. Bewusst langsam, bewusst klein, bewusst mit Mensch im Loop.

## Eingaben (geplant)

- **`pdf-inbox/`**: PDFs, die sie persönlich gespeichert hat und für relevant
  hält. Ein starkes, ehrliches Signal („das war mir wichtig genug zum Ablegen").
- **Telegram-Reaktionen** auf Brief-Items (Slice 1.5). Bis dahin: freie Nachricht
  an Josh.

## Prozess (geplant)

1. **PDF-Ingestion.** Aus jedem neuen PDF Metadaten (Titel, DOI/PMID) und ein paar
   tragende Stichworte ziehen, daraus eine `kanon.md`-Zeile vorschlagen
   (`- stichwort: kurze Notiz`). Der Vorschlag geht an einen Menschen, der ihn
   bestätigt oder verwirft, bevor er in den Kanon wandert.
2. **Reaktions-Capture.** Eine 👍/„nützlich"-Reaktion auf ein Item wird auf dessen
   Paper zurückgeführt und schlägt ebenfalls eine Kanon-Zeile vor.
3. **Kanon-Schreiben bleibt kuratiert.** Der Kanon ist Wahrheit, nicht Ansicht:
   er wächst nur durch bestätigte Einträge, nie automatisch geflutet. Ein Eintrag
   pro Zeile, damit 02_rank ihn als Keyword liest.

## Ausgabe

Ergänzte Zeilen in `profil/kanon.md`. Das ist die einzige Wirkung dieser Stufe;
sie schreibt sonst nichts. 02_rank liest den Kanon beim nächsten Lauf
(`rank.kanon_keywords`) und boostet passende Paper leicht.

## Menschliche Kontrolle

**Zentral, nicht optional.** Kein Kanon-Eintrag ohne menschliche Bestätigung.
Das hält die Lernschleife ehrlich (kein Feedback-Loop, der sich selbst verstärkt)
und die Kuratierung bei ihr und Josh. Der aktuelle Handbetrieb ist die
Minimalform genau dieses Prinzips.

## Grenzen

- **Keine Patientendaten.** PDFs können klinische Notizen enthalten; es werden nur
  bibliografische Metadaten und Fach-Stichworte extrahiert, nie Patienteninhalte,
  und die `pdf-inbox/` ist gitignored (siehe `.gitignore`).
- **Kein Auto-Lernen.** Slice 1 nutzt nur Keyword-Overlap, keine Embeddings, keine
  Datenbank. Der Kanon wächst langsam und von Hand bestätigt.
- **Kein Bezahlschranken-Umgehen.** Sie legt eigene PDFs ab; das System lädt keine
  Volltexte hinter Schranken.
