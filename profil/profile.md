# Profil — "Dr. Demo" (Demo-Profil im Methoden-Repo)

> Dies ist das **fiktive Demo-Profil** für das Methoden-Repo (`~/journal-watch/`).
> Es enthält keine echten personenbezogenen Daten. Das echte Profil lebt nur im
> privaten Repo (`~/journal-watch-privat/`) und ersetzt diese Datei dort.
> Plausibles Feld: Kardioanästhesie (Herzchirurgie), passend zum Slice-1-Build.

---

## Kontakt (API-Etikette)

- `contact_email`: joshua@stepintomore.co
  (User-Agent für Europe PMC + Unpaywall. Wird nie im Brief angezeigt.)

## Synthese (Modellwahl)

Der Synthese-Schritt ist der einzige LLM-Aufruf. Das Modell ist austauschbar,
die Sicherheitslogik (Evidenzstufe, Provenienz, Fußzeile, Gedankenstrich-Regel)
liegt im Code, nicht im Modell.

- `synthese_provider`: gemini            # erste Wahl: gemini | anthropic
- `synthese_fallback`: anthropic         # bei Fehler/Refusal; leer = kein Fallback
- `synthese_model_gemini`: gemini-2.5-flash
- `synthese_model_anthropic`: claude-sonnet-4-6

## Sprache & Zustellung

- `sprache`: de
- `umlaute`: true
- `keine_gedankenstriche`: true   # keine Halbgeviert-/Geviertstriche als Satzzeichen
- `kanal`: telegram
- `tag`: freitag
- `uhrzeit`: "06:00 Europe/Berlin"
- `max_items`: 7

## Themen

Jedes Thema hat eine explizite Europe-PMC-Query. `SRC:MED` beschränkt auf
PubMed/MEDLINE. Das Datumsfenster (`FIRST_PDATE`) setzt der Fetch-Schritt zur
Laufzeit aus `last_run_date`, nicht hier.

### thema_1
- `label`: Aortenklemme / Reperfusion (Timing & Strategie)
- `query`: `("aortic cross-clamp" OR "aortic cross clamp" OR "aortic unclamping" OR reperfusion) AND ("cardiac surgery" OR "cardiac anaesthesia" OR "cardiac anesthesia") AND SRC:MED`

### thema_2
- `label`: Kortikosteroide in der Herzchirurgie
- `query`: `(corticosteroid* OR steroid* OR methylprednisolone OR dexamethasone) AND ("cardiac surgery" OR "cardiopulmonary bypass") AND SRC:MED`

### thema_3
- `label`: Medikamentenwahl Einleitung/Aufrechterhaltung (Herzanästhesie)
- `query`: `(induction OR maintenance OR anaesthetic OR anesthetic) AND ("cardiac anaesthesia" OR "cardiac anesthesia" OR "cardiac surgery") AND (etomidate OR propofol OR sevoflurane OR "volatile anaesthetic" OR "total intravenous") AND SRC:MED`

## Journals (RSS)

> Feed-URLs werden zur Build-Zeit gegen die Live-Quelle geprüft (siehe
> build-plan.md 5.1) und erst dann eingetragen. Platzhalter bis dahin:

- BJA (British Journal of Anaesthesia): TBD
- Anesthesiology: TBD
- Anaesthesia: TBD
- Anesthesia & Analgesia: TBD

## Journal-Trust-Bonus (Ranking)

Zeitschriften, die im Ranking einen kleinen Bonus bekommen (02_rank):
- "Br J Anaesth"
- "Anesthesiology"
- "Anaesthesia"
- "Anesth Analg"
- "J Cardiothorac Vasc Anesth"
