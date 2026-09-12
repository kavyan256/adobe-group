#!/usr/bin/env python3
"""Entrypoint: fetch once, invoke each sub-skill, compose one audit report.

Usage
-----
    python3 audit.py https://example.com [-o report.json] [--bundle b.json]
    python3 audit.py --replay b.json -o report.json     # deterministic re-run

Composition model
-----------------
1. Build a site bundle (one polite, read-only crawl).
2. Invoke each sub-skill's check script as a separate process, passing the bundle.
   Sub-skills never import from each other or from here -- each skill folder stays
   independently installable and runnable.
3. Merge their findings, mark blocked-but-real findings as `latent`, derive
   severity from the published table, prioritise, and emit a single report.

Determinism
-----------
The analysis layer is deterministic given a fixed bundle: every collection is
sorted by an explicit key, severity consumes only banded values, and `--replay`
re-runs the whole decision layer over a saved bundle. Network observation itself
is not deterministic, and we say so rather than claiming otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Importing our sibling modules must not leave __pycache__ inside the
# marketplace: a submission zip has to stay clean, and the packaging gate
# treats build junk as a hard failure.
sys.dont_write_bytecode = True
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from model import Finding                     # noqa: E402
import bundle as bundle_mod                   # noqa: E402

SKILLS_DIR = Path(__file__).resolve().parents[2]

SUB_SKILLS = [
    ("crawl-access-audit",            "scripts/check_access.py"),
    ("fact-extractability-audit",     "scripts/check_extractability.py"),
    ("freshness-corroboration-audit", "scripts/check_freshness.py"),
    ("engagement-audit",              "scripts/check_engagement.py"),
]

SEV_WEIGHT = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
EFFORT_WEIGHT = {"low": 1.0, "medium": 1.6, "high": 2.4}

# Proactive recommendations are conditioned on the site. Each carries an
# `applies(bundle, check_ids)` test; ones the site already satisfies are listed
# under `already_in_place` rather than recommended again. A recommendation the
# site has already implemented is not "beyond the problem" -- it is noise.
# These read the crawl layer's normalised JSON-LD, exactly as the sub-skills do.
# v2.0 ran raw regexes over the whole page here, which is how a report could
# claim "no Organization sameAs" in a finding and "sameAs already published" in
# already_in_place, in the same document, about the same site.


def _ok_derived(b: dict):
    return [p["derived"] for p in b["pages"]
            if 200 <= p["status"] < 300 and p["html"] and isinstance(p.get("derived"), dict)]


def _has_llms_txt(b, _):
    return bool(b.get("probes", {}).get("llms_txt", {}).get("present"))


def _names_ai_agents(b, _):
    return bool(b.get("probes", {}).get("ai_agents_named_in_robots"))


def _has_faq_markup(b, _):
    return any("faqpage" in d["jsonld"]["types_present"] for d in _ok_derived(b))


def _has_sameas(b, _):
    return any(d["jsonld"]["sameas"] for d in _ok_derived(b))


def _is_hydrated_app(b, _):
    return any(d["payload_islands"] for d in _ok_derived(b))


PROACTIVE = [
    {"title": "Publish an llms.txt describing your site for AI clients",
     "rationale": "An emerging convention: a short, stable, plain-text map of what your site "
                  "covers and where the authoritative pages are. Cheap to add, and it gives "
                  "retrieval agents an unambiguous starting point.",
     "effort": "low",
     "applies": lambda b, c: not _has_llms_txt(b, c),
     "applies_because": "GET /llms.txt did not return a plain-text document",
     "in_place_because": "/llms.txt is present"},
    {"title": "Decide your AI-crawler policy deliberately, and write it down",
     "rationale": "Training access and retrieval access are separate decisions. Blocking training "
                  "crawlers while explicitly allowing retrieval agents is a coherent, defensible "
                  "position - but it has to be configured on purpose, per user-agent.",
     "effort": "low",
     "applies": lambda b, c: not _names_ai_agents(b, c),
     "applies_because": "robots.txt names no AI retrieval or training agent, so the current "
                        "policy is whatever the wildcard group happens to say",
     "in_place_because": "robots.txt already addresses AI agents by name"},
    {"title": "Add a machine-readable FAQ layer shaped for quotation",
     "rationale": "FAQPage structured data pairs a question with a self-contained answer. That is "
                  "exactly the shape an assistant wants to lift, and it survives text extraction.",
     "effort": "medium",
     "applies": lambda b, c: not _has_faq_markup(b, c),
     "applies_because": "no crawled page carries FAQPage JSON-LD",
     "in_place_because": "FAQPage JSON-LD found on at least one crawled page"},
    {"title": "Publish a stable, citable facts page",
     "rationale": "Founding date, leadership, HQ, product line, pricing - in one durable URL that "
                  "third parties can cite verbatim. Corroboration across independent sources is "
                  "what makes a claim credible to a machine, and you can seed it.",
     "effort": "medium",
     "applies": lambda b, c: not _has_sameas(b, c),
     "applies_because": "no crawled page declares Organization sameAs links, so there is no "
                        "anchor for third parties to corroborate against",
     "in_place_because": "Organization sameAs links are already published"},
    {"title": "Server-render your most-quoted facts even inside a SPA",
     "rationale": "You do not have to abandon client-side rendering. Server-render the handful of "
                  "facts you most want cited - price, what you do, how to contact you - and let "
                  "the rest hydrate.",
     "effort": "high",
     # Only relevant to a hydrated app; and if B1/B4 already fired, the finding
     # carries this exact fix and repeating it here would be padding.
     "applies": lambda b, c: _is_hydrated_app(b, c)
                             and not ({"B1_fact_script_only", "B4_empty_shell", "B1_fact_absent"} & c),
     "applies_because": "the site ships a client-side hydration payload; its key facts currently "
                        "extract fine, so this is about keeping it that way as the app grows",
     "in_place_because": "not a client-rendered app, or a specific finding already covers it"},
]


def proactive_for(b: dict, findings: list) -> tuple[list[dict], list[dict]]:
    check_ids = {f.check_id for f in findings}
    applies, in_place = [], []
    for rec in PROACTIVE:
        public = {k: v for k, v in rec.items() if k not in ("applies", "applies_because", "in_place_because")}
        if rec["applies"](b, check_ids):
            applies.append({**public, "applies_because": rec["applies_because"]})
        else:
            in_place.append({"title": rec["title"], "because": rec["in_place_because"]})
    return applies, in_place


def run_sub_skill(folder: str, script: str, bundle_path: Path,
                  timeout_s: float) -> tuple[list, list]:
    path = SKILLS_DIR / folder / script
    if not path.exists():
        return [], [{"check": folder, "reason": f"skill script not found at {path}",
                     "impact": "this concern was not audited"}]
    if timeout_s <= 0:
        return [], [{"check": folder, "reason": "runtime budget exhausted before this skill ran",
                     "impact": "this concern was not audited"}]
    try:
        proc = subprocess.run([sys.executable, str(path), str(bundle_path)],
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return [], [{"check": folder, "reason": f"sub-skill timed out after {timeout_s:.0f}s",
                     "impact": "this concern was not audited"}]
    if proc.returncode != 0:
        return [], [{"check": folder,
                     "reason": f"sub-skill exited {proc.returncode}: {proc.stderr.strip()[:200]}",
                     "impact": "this concern was not audited"}]
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], [{"check": folder, "reason": "sub-skill emitted invalid JSON",
                     "impact": "this concern was not audited"}]
    if isinstance(data, dict):
        return data.get("findings", []), data.get("checks_skipped", [])
    return data, []


def mark_latent(raw: list[dict]) -> list[dict]:
    """Downstream findings on unreachable URLs are demoted, never suppressed.

    Suppressing them would mean the operator fixes the blocker, re-audits, and
    meets a wave of findings nobody warned them about. Robots is also per-agent,
    so a page blocked to one crawler may be wide open to another -- the blocker
    names which agents it actually affects.
    """
    blockers = [f for f in raw if f["check_id"] in ("A1_retrieval_agent_blocked", "A3_noindex")]
    if not blockers:
        return raw
    blocked_urls, agents, blocked_paths = set(), set(), set()
    for b in blockers:
        if b["check_id"] == "A3_noindex":
            blocked_urls |= set(b.get("affected_urls", []))
            agents |= {"all indexing agents"}
        else:
            # A1 names agents, not URLs. Its blocked paths are what downstream
            # findings sit behind; in v2.0 A1 contributed no URLs at all, so a
            # fully robots-blocked site marked nothing latent.
            agents |= set(b.get("detail", {}).get("blocked_retrieval_agents", []))
            for path in b.get("detail", {}).get("blocked_paths", []):
                blocked_paths.add(path)
    for f in raw:
        # Access findings are never latent behind another access finding: they
        # ARE the blocker, or they describe the same robots.txt. Load-bearing --
        # without it a blocker would mark itself unobservable.
        if f["check_id"].startswith("A"):
            continue
        urls = set(f.get("affected_urls", []))
        if urls and blocked_paths and not (urls <= blocked_urls):
            # Every affected URL sits under a robots-blocked path prefix.
            if all(any(urlparse(u).path.startswith(bp) for bp in blocked_paths) for u in urls):
                blocked_urls |= urls
        if urls and urls <= blocked_urls:
            f["status"] = "latent"
            f["blocked_by"] = {
                "finding_check": blockers[0]["check_id"],
                "agents_affected": sorted(agents),
                "note": "Real, but unobservable by the blocked agents until the blocker is fixed.",
            }
    return raw


def priority_score(f: Finding) -> float:
    sev = SEV_WEIGHT.get(f.severity, 1)
    conf = 1.0 if f.confidence == "deterministic" else 0.7
    effort = EFFORT_WEIGHT.get(f.suggested_action.get("effort", "medium"), 1.6)
    # A finding the owner may have configured on purpose ranks below an equally
    # severe real defect, and above one that is not yet observable.
    status_weight = {"latent": 0.35, "confirm_intent": 0.5}.get(f.status, 1.0)
    return round(sev * conf * status_weight / effort, 3)


# The Round-2 mechanisms, and what this marketplace does about each. Generated
# from SEVERITY_TABLE below so the check lists cannot drift from what actually
# runs. Two mechanisms are deliberately not covered, and saying so plainly is
# more honest -- and more useful -- than inventing a score for them.
MECHANISMS = {
    "A": ("How search visibility works",
          "the crawler must be let in before anything else can matter", None),
    "B": ("How assistants use sources",
          "a page is cited when a machine can reach it, read it and quote a clear fact from it",
          None),
    "C": ("How machines read a page",
          "a fact only counts if it survives bot-grade text extraction", None),
    "D": ("Why agreement across the web matters",
          "claims that only one place makes are fragile, and names that collide get confused",
          None),
    "E": ("Personalization and prior context", None,
          "Personalization happens inside the assistant, from context the user carries into "
          "the conversation. Nothing in a site's HTML determines it, so any site-side "
          "'personalization score' would be fabricated. The site-side lever is that each page "
          "state a self-contained, unambiguous fact, so the page answers whatever slice of "
          "context the assistant happens to hold -- which is what X1_low_quotability and the "
          "extraction-tier checks measure."),
    "F": ("Why machines drop content from emails", None,
          "Email summarisation is not observable from a website. The transferable mechanism -- "
          "substance carried in non-text, or buried under filler -- is audited on-page as "
          "B5_fact_locked_in_image and B6_filler_heavy."),
    "on-site": ("On-site engagement",
                "a visitor who arrives from an AI answer has to be able to act", None),
}


def mechanism_coverage() -> list[dict]:
    from model import SEVERITY_TABLE
    by_mech: dict[str, list[str]] = {}
    for check_id, spec in SEVERITY_TABLE.items():
        by_mech.setdefault(spec["mechanism"], []).append(check_id)
    out = []
    for key, (name, why, instead) in MECHANISMS.items():
        checks = sorted(by_mech.get(key, []))
        entry = {"mechanism": key, "name": name,
                 "status": "covered" if checks else "not_auditable_from_a_site_crawl",
                 "checks": checks}
        if why:
            entry["why"] = why
        if instead:
            entry["what_we_do_instead"] = instead
        out.append(entry)
    return out


def build_report(b: dict, findings: list[Finding], skipped: list[dict],
                 checks_run: list[str]) -> dict:
    active = [f for f in findings if f.status == "active"]
    latent = [f for f in findings if f.status == "latent"]
    confirm = [f for f in findings if f.status == "confirm_intent"]
    proactive, in_place = proactive_for(b, findings)
    counts = {s: sum(1 for f in active if f.severity == s)
              for s in ("critical", "high", "medium", "low", "info")}
    ordered = sorted(findings, key=lambda f: (-priority_score(f), f.check_id))

    return {
        # ---- required by the specification ----
        "site": b["site"],
        "audited_at": b["audited_at"],
        "summary": {
            # total_findings == len(findings[]) so any external validator agrees
            # with the array; severity counts cover active findings only, since
            # latent ones are capped at "low" and not yet observable.
            "total_findings": len(findings),
            **{k: v for k, v in counts.items() if k != "info"},
            # ---- superset ----
            "active_findings": len(active),
            "latent_findings": len(latent),
            "confirm_intent_findings": len(confirm),
            "info": counts["info"],
            "by_hurts": {h: sum(1 for f in active if f.hurts == h)
                         for h in ("ai_discoverability", "user_retention", "both")},
            "run_status": b["run_status"],
            "headline": _headline(active, b),
        },
        "findings": [f.to_report() for f in ordered],
        # ---- superset ----
        "site_profile": {
            "start_url": b["start_url"],
            "pages_crawled": b["coverage"]["pages_ok"],
            "roles_seen": sorted({p["role"] for p in b["pages"]}),
            "robots_present": b["robots"]["present"],
            "ai_policy": _ai_policy(b),
            "user_agent_used": b["user_agent"],
        },
        "coverage": b["coverage"],
        "mechanism_coverage": mechanism_coverage(),
        "checks_run": sorted(checks_run),
        "checks_skipped": sorted(skipped, key=lambda s: s["check"]),
        "prioritized_actions": [
            {"rank": i + 1, "finding_id": f.id, "title": f.title,
             "priority_score": priority_score(f),
             "severity": f.severity, "status": f.status, "hurts": f.hurts,
             "effort": f.suggested_action.get("effort", "medium"),
             "action": f.suggested_action["summary"]}
            for i, f in enumerate(ordered[:15])
        ],
        "proactive_recommendations": proactive,
        "already_in_place": in_place,
        "limits": [
            "Findings are derived from the raw HTTP response with no JavaScript executed - "
            "which is what non-rendering AI retrieval agents also see.",
            "Facts fetched by client-side XHR after load, with no server-rendered payload, "
            "cannot be detected by this method and may be false negatives.",
            "Engagement findings are structural risk factors inferred from markup, never "
            "observed user behaviour; they are capped at medium severity for that reason.",
            "The analysis layer is deterministic for a fixed bundle; network observation is not. "
            "Use --replay against a saved bundle for a byte-stable re-run.",
        ],
        "notes": b.get("notes", []),
    }


def _ai_policy(b: dict) -> dict:
    agents = b["robots"]["agents"]
    return {
        "retrieval_agents_blocked": sorted(t for t, d in agents.items()
                                           if d["class"] == "retrieval" and d["fully_blocked"]),
        "training_agents_blocked": sorted(t for t, d in agents.items()
                                          if d["class"] == "training" and d["fully_blocked"]),
        "interpretation": "Blocking training agents is a licensing choice and does not affect "
                          "whether assistants can cite you. Only retrieval agents gate citation.",
    }


def _headline(active: list[Finding], b: dict) -> str:
    if b["run_status"] in ("blocked", "failed"):
        return "The site could not be read by an automated client - fix access before anything else."
    if not active:
        return "No blocking problems detected in the checks that ran; see proactive recommendations."
    worst = min(active, key=lambda f: -SEV_WEIGHT.get(f.severity, 0))
    return f"{len(active)} finding(s); most severe: {worst.title}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a site for AI discoverability and engagement.")
    ap.add_argument("url", nargs="?", help="site URL to audit")
    ap.add_argument("--replay", metavar="BUNDLE", help="re-run analysis over a saved bundle")
    ap.add_argument("-o", "--out", help="write report JSON here (default: stdout)")
    ap.add_argument("--bundle", help="also save the fetched bundle here")
    ap.add_argument("--max-pages", type=int, default=bundle_mod.DEFAULT_MAX_PAGES)
    args = ap.parse_args()
    t_start = time.monotonic()

    if args.replay:
        b = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        bundle_path = Path(args.replay)
        tmp = None
    elif args.url:
        b = json.loads(bundle_mod.build(args.url, max_pages=args.max_pages).to_json())
        tmp = Path(args.bundle) if args.bundle else Path(".audit-bundle.json")
        tmp.write_text(json.dumps(b, indent=2, sort_keys=True, ensure_ascii=False),
                       encoding="utf-8")
        bundle_path = tmp
    else:
        ap.error("provide a URL or --replay BUNDLE")
        return 2

    # Analysis shares whatever the crawl left of the total budget, so the whole
    # audit is bounded inside the 5-minute limit rather than per-stage.
    raw, skipped, checks_run = [], [], []
    for folder, script in SUB_SKILLS:
        remaining = bundle_mod.TOTAL_BUDGET_S - (time.monotonic() - t_start)
        f, s = run_sub_skill(folder, script, bundle_path, min(30.0, remaining))
        raw += f
        skipped += s
        checks_run.append(folder)

    raw = mark_latent(raw)
    raw.sort(key=lambda f: (f["check_id"], sorted(f.get("affected_urls", []))[:1]))

    findings: list[Finding] = []
    for i, r in enumerate(raw, start=1):
        findings.append(Finding(
            check_id=r["check_id"], title=r["title"], evidence=r["evidence"],
            suggested_action=r["suggested_action"],
            affected_urls=r.get("affected_urls", []),
            blast_radius=r.get("blast_radius", "single_page"),
            confidence=r.get("confidence", "deterministic"),
            measurement_basis=r.get("measurement_basis", "static_fact"),
            status=r.get("status", "active"),
            intent_signals=r.get("intent_signals", []),
            blocked_by=r.get("blocked_by"),
            detail=r.get("detail", {}),
        ).finalise(i, b["coverage"]["pages_ok"]))

    report = build_report(b, findings, skipped, checks_run)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}  ({report['summary']['active_findings']} active, "
              f"{report['summary']['latent_findings']} latent, "
              f"run_status={report['summary']['run_status']})")
    else:
        print(text)
    if tmp and not args.bundle:
        tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
