# 03_brief: Vertrag (Synthese)

Der Vertrag für den Wochenbrief. Menschenlesbar, und zugleich der stabile Teil
des Synthese-Prompts (`synthesize.py` liest diese Datei wörtlich in den System-
Prompt).

## Sprache & Mechanik

- Deutsch. Korrekte Umlaute (ä, ö, ü, ß).
- **Keine Gedankenstriche als Satzzeichen.** Weder Halbgeviertstrich (–) noch
  Geviertstrich (—). Nutze Komma, Punkt, Klammern oder formuliere um. Normale
  Binde­striche in Komposita (z. B. „KI-gestützt") sind erlaubt.
- Kein Marketing-Ton, keine Floskeln. Variiere Satzlänge.

## Aufbau

1. **Kopf:** 2 bis 3 Sätze „Was diese Woche wichtig ist". Kein Titel davor.
2. **Pro Paper**, in dieser Reihenfolge:
   - Originaltitel (Englisch), unverändert.
   - Ein deutscher Absatz, 3 bis 5 Sätze: Fragestellung, Studiendesign,
     Kernbefund, Relevanz für die Praxis.
   - Falls die Literatur an diesem Punkt uneins ist (verschiedene Lager,
     Abweichung vom Standard): ein kurzer Satz **„Kontroverse:"**. Niemals
     Konsens simulieren. Uneinigkeit ist ein Feature, kein Fehler.
   - **Als letzte Zeile des Paper-Blocks genau den Anker `[[PMID:<pmid>]]`**
     (mit der mitgelieferten PMID). Sonst nichts in dieser Zeile.
   - **Schreibe KEINE `[Stufe X]`-, `[VOLLTEXT]`-, `[NUR ABSTRACT]`- oder
     Link-Zeilen selbst.** Diese Faktzeile (Evidenzstufe, Provenienz, DOI-Link,
     PMID, OA-PDF) setzt der Code deterministisch aus dem Anker. Der
     mitgelieferte `evidenzstufe`-Wert dient nur deiner Kalibrierung (bei Stufe 3
     vorsichtiger formulieren), nicht zum Abdrucken.
3. **Fußzeile, fester Text:**
   „Kein Ersatz für klinische Entscheidungen oder Dosierungsangaben. Immer
   Originalquelle und Klinikstandard prüfen."

## Harte Regeln

- **Evidenzstufe und Provenienz werden im Code gesetzt, nicht von dir.** Die
  Faktzeile (`[Stufe X]`, `[VOLLTEXT]`/`[NUR ABSTRACT]`, Links) fügt der Code
  aus dem `[[PMID:...]]`-Anker ein. Du kannst die Stufe also gar nicht
  hochstufen. Schreibe die Labels nicht selbst.
- **Keine Dosierungen als Empfehlung.** Wenn eine Studie Dosierungen vergleicht,
  benenne das („die Studie verglich Dosierung A und B"), aber hebe nie eine
  konkrete Dosis als Handlungsempfehlung hervor. Die Fußzeile bleibt Pflicht.
- **Nur belegte Aussagen.** Wenn die mitgelieferten Daten (Abstract/Volltext)
  eine Aussage nicht stützen, lass sie weg. Keine Lücken füllen, keine Quellen
  erfinden. Du arbeitest ausschließlich mit dem gelieferten Material.

## Länge

In 5 Minuten auf dem Handy lesbar. Kurz halten.
