---
type: Ghost
status: ghost
kind: unbuilt personalization
hub: surface
---
# Real Instantiation

The per-physician real configuration the product exists to deliver: each clinician's own subspecialty topics and trusted journals, in a private instance (`journal-watch-privat`), replacing the demo. It is referenced everywhere and built nowhere. `profil/profile.md` says the real profile lives in the private repo and replaces the demo file there; the README calls it the private instantiation. Yet the deployed app serves all three physicians on the single Dr. Demo cardiac-anaesthesia [[Profile]] through one shared login. For any user who is not a cardiac anaesthetist, the feed is the wrong subspecialty. The personalization, her literature rather than a demo's, is the load-bearing absence, and now that real people use the app, the absence is being felt, not just planned.

personalizes [[Profile]] . serves [[The Clinician]] . blocked-on [[Per-User Quota]] . withheld-by [[The Maintainer]] . contested-by [[Demo vs Real Instantiation]]

- **Hits:** the entire value proposition, and what each of the three physicians actually receives each week. Two of them may be getting a subspecialty that is not theirs.
- **Does not hit:** the pipeline code, which runs fine on any [[Profile]]. This is a config-and-identity gap (one profile, one login, no per-user split), not an engine bug.

Source: profil/profile.md:1-5 ("real profile lives in journal-watch-privat and replaces this file there"); conversation with the maintainer 2026-09-02 (one shared password, one profile, no other profile known); README.md ("real instantiation lives in a separate private repo").
