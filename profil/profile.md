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

## Domain-Gate (nur Praxis-Check)

Nur der Praxis-Check nutzt diese Listen (05_praxis-check). Sie arbeiten auf den
MeSH-Schlagworten, die Europe PMC pro Paper vergibt (Deckung ~75 %; Paper ohne
MeSH werden nicht geMeSH-gegatet, sondern fallen auf den String-Subjektfilter
zurück). Jeder Eintrag ist ein Teilstring, der gegen die MeSH-Deskriptoren
(kleingeschrieben) geprüft wird. Domänenweit und fix, also für jede
Kardioanästhesie-Frage gültig, nicht pro Frage getunt.

### Cardiac-context MeSH (Bonus)

Paper, die per MeSH klar im Feld liegen, bekommen einen kleinen Ranking-Bonus
(kein Filter, damit die MeSH-losen 25 % nicht fälschlich fallen).
- cardiac surg
- cardiopulmonary bypass
- coronary artery bypass
- cardioplegi
- heart arrest, induced
- extracorporeal circulation
- myocardial reperfusion
- heart valve
- cardiovascular surgical

### Negative MeSH (Drop)

Reine Tierstudien und Onkologie ohne Herzbezug werden deterministisch verworfen,
bevor gerankt wird (nur wenn KEIN Cardiac-context-MeSH vorliegt, damit ein
humanes Mehrorgan-Paper mit Nieren-/Leber-MeSH nicht mitgerissen wird).
- animals
- mice
- rats
- neoplasm
- carcinoma

## Controlled Vocabulary (nur Praxis-Check)

Die kontrollierte-Vokabular-Schicht (Ontology-Pipeline, erste Stufe). Jede Zeile
ist EIN Konzept: bevorzugter Begriff links vom `:`, gleichwertige Schreibweisen,
Abkürzungen und Markennamen rechts, mit `|` getrennt (analog MeSH preferred term
+ entry terms). Kommt eine dieser Oberflächenformen in einer geplanten Query vor,
expandiert der Code sie deterministisch zur ODER-Gruppe aller Formen
(Mehrwortphrasen werden dabei in Anführungszeichen gesetzt). Zweck: Recall (Paper
die ausschreiben vs. abkürzen) und Determinismus (die Expansion ist fix, nicht
dem Planer überlassen). Britische und amerikanische Schreibweisen bewusst beide
gelistet. Von Hand gepflegt, das IST die Vokabulararbeit; MeSH liefert die Belege,
kein Graph nötig.

Noch inert: aktiv erst, wenn der Planer-Expansionsschritt gebaut ist (siehe
CLAUDE.md Current State, nächster Schritt). Ergänzungen willkommen, das ist ihr
Fachvokabular.

**Verfahren & Narkosetiefe**
- total intravenous anaesthesia : TIVA | total intravenous anesthesia
- target-controlled infusion : TCI | target controlled infusion
- inhalational anaesthetic : volatile anaesthetic | volatile anesthetic | inhalational anesthetic | inhaled anaesthetic
- bispectral index : BIS

**Substanzen**
- propofol : Diprivan
- dexmedetomidine : Precedex | Dexdor
- remifentanil : Ultiva

**Neuromuskuläre Antagonisierung**
- sugammadex : Bridion
- neostigmine : Prostigmin
- neuromuscular blockade reversal : reversal of neuromuscular blockade | NMB reversal | decurarization

**Herzchirurgie & HLM**
- cardiopulmonary bypass : CPB | heart-lung machine | HLM | extracorporeal circulation
- coronary artery bypass : CABG | coronary artery bypass grafting
- aortic cross-clamp : aortic cross-clamping | aortic cross clamp | aortic clamping | aortic unclamping | aortic clamp release
- del Nido cardioplegia : del Nido solution | del Nido
- reperfusion : reperfusion injury | ischaemia-reperfusion | ischemia-reperfusion

**Gerinnung**
- tranexamic acid : TXA | Cyklokapron

**Zerebrales Monitoring**
- near-infrared spectroscopy : NIRS | cerebral oximetry | rSO2 | regional cerebral oxygen saturation

**Outcomes**
- postoperative atrial fibrillation : POAF | new-onset atrial fibrillation | post-operative atrial fibrillation
- postoperative delirium : POD | post-operative delirium
- acute kidney injury : AKI | acute renal failure
- systemic inflammatory response syndrome : SIRS

**Perioperative Programme**
- enhanced recovery after surgery : ERAS | fast-track surgery
- remote ischaemic preconditioning : RIPC | remote ischemic preconditioning

**Gewichtsmaße (Dosierungsfragen)**
- total body weight : TBW
- adjusted body weight : ABW | corrected body weight
- ideal body weight : IBW
- lean body weight : LBW | fat-free mass
