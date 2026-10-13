#!/usr/bin/env python3
"""Serve the real UI with synthetic local history and browser regression checks.

Run: python scripts/test_brief_ui.py
Open http://127.0.0.1:5001/ (or use the screenshot runner on port 5001).
Only serves a test copy in memory; no backend calls, credentials, or app edits.
Browser assertions print PASS/FAIL to the console and a test-only page banner.
Use ?state=expanded or ?state=legacy for additional visual checks.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
FOOTER = (
    "Kein Ersatz für klinische Entscheidungen oder Dosierungsangaben. "
    "Immer Originalquelle und Klinikstandard prüfen."
)
DOSSIER = f"""# Praxis-Check: Synthetische Testfrage

## Kurzantwort

Dieser synthetische Befund prüft ausschließlich die Darstellung von Zitaten, Unsicherheit und aufklappbaren Abschnitten. Er ist keine medizinische Aussage und kein Ergebnis einer Recherche. (PMID 12345678)

- Ein entscheidender Befund bleibt direkt sichtbar. (PMID 12345678)
- Die untersuchte Population und Übertragbarkeit werden knapp eingeordnet.
- Eine wesentliche Einschränkung bleibt auch ohne Aufklappen sichtbar:
  Für diesen Test liegt nur ein synthetischer Abstract-Auszug vor.

## Evidenzlage

DETAIL_ONLY: Dies ist ausführlicher Testtext mit demselben Beleg. (PMID 12345678)

## Was ist Standard

Aus diesem synthetischen Beispiel lässt sich kein klinischer Standard ableiten.

## Wo die Literatur uneins ist

Dieser Abschnitt dient nur der Prüfung, dass keine Inhalte verloren gehen.

## Offene Fragen

Die vollständigen Quellen können unabhängig von der Evidenz geöffnet werden.

## Verwendete Suchanfrage

- `("test population" OR "test intervention") AND SRC:MED`

## Quellen

1. Testquelle A. PMID 12345678
   [Stufe 3] [NUR ABSTRACT]
https://pubmed.ncbi.nlm.nih.gov/12345678

2. Testquelle B. PMID 23456789
   [Stufe 2] [VOLLTEXT]
https://pubmed.ncbi.nlm.nih.gov/23456789

{FOOTER}
"""

CITATIONS = [
    {"pmid": "12345678", "title": "Testquelle A", "study_type": "Review",
     "stufe": 3, "full_text": False, "snippet": "Synthetischer Testauszug.",
     "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345678"},
    {"pmid": "23456789", "title": "Testquelle B", "study_type": "Beobachtungsstudie",
     "stufe": 2, "full_text": True,
     "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/23456789"},
]
DATA = {"dossier": DOSSIER, "queries": ["test AND SRC:MED"],
        "count": 2, "citations": CITATIONS}
HISTORY = [{"id": "test-chat", "title": "Darstellungstest, keine medizinischen Daten",
            "createdAt": 1791885600000, "updatedAt": 1791885600000,
            "messages": [
                {"id": "test-first", "question": "Synthetische Literaturfrage zum Darstellungstest",
                 "status": "complete", "data": DATA},
                {"id": "test-followup", "question": "Synthetische Vertiefung zur Darstellung",
                 "status": "complete", "data": {
                     **DATA, "citations": [{**c, "title": "Folgeantwort: " + c["title"]}
                                          for c in CITATIONS]}},
            ]}]

TESTS = r"""
<script>
(function(){
  const api = window.__briefTest;
  const original = JSON.parse(localStorage.getItem("kustos_conversations_v1"))[0].messages[0].data;
  const failures = [];
  let total = 0;
  function check(ok, name){
    total++;
    if(!ok) failures.push(name);
    console.log((ok ? "PASS " : "FAIL ") + name);
  }
  function render(data){
    const host = document.getElementById("messages");
    host.replaceChildren();
    api.renderDossierInto(data, host, "edge-case");
    return host.querySelector("article");
  }
  function fallback(dossier, name){
    const article = render({...original, dossier});
    check(!article.querySelector(".dossier-brief"), name);
  }
  try{
    const articles = document.querySelectorAll(".dossier");
    check(articles.length === 2, "restored chat and follow-up render");
    check(getComputedStyle(document.querySelector(".hero")).display === "none",
      "intro does not push restored chat below the fold");
    check(articles[0].querySelectorAll("h1").length === 1, "title appears once");
    check(articles[0].querySelectorAll("details").length === 3, "three independent disclosures");
    check([...articles[0].querySelectorAll("details")].every(d => !d.open), "disclosures closed initially");
    check(articles[0].querySelector(".dossier-brief").textContent.includes("Einschränkung"),
      "uncertainty visible in brief");
    check(!articles[0].querySelector(".dossier-brief").textContent.includes("DETAIL_ONLY"),
      "detailed evidence not in brief");
    check(!articles[0].querySelector(".dossier-safety").closest("details"),
      "safety footer outside disclosures");
    check(articles[0].textContent.split(api.canonicalSafetyFooter).length === 2,
      "safety footer occurs once");
    const detail = articles[0].querySelector("details");
    detail.querySelector("summary").click();
    check(detail.open, "summary click expands evidence");
    detail.querySelector("summary").click();
    check(!detail.open, "summary click collapses evidence");
    articles[0].querySelector(".dossier-sources summary").click();
    check(articles[0].querySelector(".dossier-sources").open && !detail.open,
      "sources expand independently");
    const lists = articles[0].querySelectorAll(".source-list");
    check(lists.length === 2 && lists[0].getAttribute("start") === "1" &&
      lists[1].getAttribute("start") === "2", "split source lists keep numbering");
    check(articles[0].querySelector(".dossier-search").textContent.includes("test population"),
      "original search query preserved");
    articles[0].querySelector(".dossier-brief .pmid-citation").click();
    check(!document.getElementById("citationPreview").hidden &&
      document.getElementById("citationPreviewBody").textContent.includes("Testquelle A"),
      "brief citation opens original message source");
    api.closeCitation();
    articles[1].querySelector(".dossier-brief .pmid-citation").click();
    check(document.getElementById("citationPreviewBody").textContent.includes("Folgeantwort:"),
      "same PMID resolves to follow-up metadata");
    api.closeCitation();
    detail.open = true;
    detail.querySelector(".pmid-citation").click();
    check(document.getElementById("citationPreviewBody").textContent.includes("Testquelle A"),
      "expanded evidence citation works");
    api.closeCitation();
    articles[0].querySelector(".source-inspect").click();
    check(!document.getElementById("citationPreview").hidden, "bibliography source inspection works");
    api.closeCitation();
    const legacy = original.dossier.replace(/## Kurzantwort[\s\S]*?(?=## Evidenzlage)/, "");
    const old = render({...original, dossier:legacy});
    check(!old.querySelector("details") && old.textContent.includes("DETAIL_ONLY"),
      "legacy dossier stays fully visible");
    fallback(original.dossier.replace("## Kurzantwort", "## Kurzantwort\n\n## Kurzantwort"),
      "duplicate heading safely falls back");
    fallback(original.dossier.replace(/## Kurzantwort[\s\S]*?(?=## Evidenzlage)/,
      "## Kurzantwort\n\n"), "empty brief safely falls back");
    fallback(original.dossier.replace("## Quellen", "### Quellen"),
      "missing source section safely falls back");
    fallback(original.dossier.replace(api.canonicalSafetyFooter, ""),
      "missing canonical footer safely falls back");
    const noQuery = original.dossier.replace(/## Verwendete Suchanfrage[\s\S]*?(?=## Quellen)/,"");
    const fromPayload = render({...original, dossier:noQuery});
    check(fromPayload.querySelector(".dossier-search").textContent.includes(original.queries[0]),
      "payload search queries available when absent from markdown");
    const attack = render({...original, dossier:original.dossier.replace("Dieser synthetische",
      '<img src=x onerror="window.__xss=true">Dieser synthetische')});
    check(!attack.querySelector("img") && !window.__xss, "untrusted markdown remains escaped");
    check(!Object.prototype.hasOwnProperty.call(JSON.parse(localStorage.getItem("kustos_conversations_v1"))[0],
      "password"), "history contains no credential field");
    check(original.dossier === JSON.parse(localStorage.getItem("kustos_conversations_v1"))[0].messages[0].data.dossier,
      "stored authoritative dossier unchanged");
    const variant = render({...original, dossier:original.dossier.replace("## Kurzantwort",
      "## Kurzantwort (Kernbefund zuerst)")});
    check(Boolean(variant.querySelector(".dossier-brief")), "known emitted brief heading accepted");
    fallback(original.dossier.replace("## Evidenzlage", "## Kurzantwort (Kernbefund zuerst)"),
      "two brief heading variants safely fall back");
    document.getElementById("historyNew").click();
    check(getComputedStyle(document.querySelector(".hero")).display !== "none",
      "new question restores introductory view");
    document.querySelector(".history-item").click();
    check(document.querySelectorAll(".dossier").length === 2,
      "reopening history preserves both answers");
    api.renderConversation();
    if(new URLSearchParams(location.search).get("state") === "expanded"){
      document.querySelectorAll(".dossier details").forEach(d => d.open = true);
    }else if(new URLSearchParams(location.search).get("state") === "legacy"){
      render({...original, dossier:legacy});
    }else if(window.__liveTest){
      const live = render(window.__liveTest);
      check(Boolean(live.querySelector(".dossier-brief")), "fresh live dossier renders brief first");
      check(live.querySelectorAll(".dossier-safety").length === 1,
        "fresh live dossier keeps visible footer");
    }
  }catch(error){
    failures.push(error.stack || String(error));
    console.error(error);
  }
  const banner = document.createElement("div");
  banner.textContent = failures.length ? "FAIL: " + failures.join("; ") :
    "UI test fixture: " + total + " checks passed. Not clinical research.";
  banner.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 10px;font:12px sans-serif;background:" +
    (failures.length ? "#ffd5d5" : "#d8eee4") + ";color:#16352b";
  document.body.appendChild(banner);
  console.log("BRIEF_UI_RESULT " + JSON.stringify({total, failures}));
  window.scrollTo({top:0, behavior:"instant"});
})();
</script>
"""


def page(state=""):
    source = (ROOT / "web/index.html").read_text()
    hook = """
  window.__briefTest = {renderDossierInto, renderConversation, closeCitation,
    canonicalSafetyFooter, dossierSections};
"""
    end = source.rfind("})();")
    if end < 0:
        raise ValueError("Could not locate UI closure for test-only instrumentation")
    source = source[:end] + hook + source[end:]
    seed = "<script>localStorage.setItem('kustos_conversations_v1'," + json.dumps(
        json.dumps(HISTORY)) + ");localStorage.setItem('kustos_active_chat_v1','test-chat');</script>"
    source = source.replace("<script>", seed + "<script>", 1)
    live = ""
    if state == "live":
        live_data = Path("/tmp/kustos-brief-live.json")
        if live_data.exists():
            payload = json.dumps(json.loads(live_data.read_text())).replace("<", "\\u003c")
            live = "<script>window.__liveTest=" + payload + ";</script>"
    return source.replace("</body>", live + TESTS + "</body>").encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        body = page("live" if urlparse(self.path).query == "state=live" else "")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Test-only UI fixture listening on port 5001", flush=True)
    HTTPServer(("0.0.0.0", 5001), Handler).serve_forever()
