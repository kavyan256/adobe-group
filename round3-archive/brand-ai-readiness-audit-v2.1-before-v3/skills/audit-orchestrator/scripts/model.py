"""Finding model + the severity decision table.

Severity is a published lookup table, not a formula, and the arithmetic is
printed into every finding as ``severity_rationale`` so a reader can audit it.

Rules
-----
base            declared per check, justified by mechanism in
                references/severity-rationale.md (never by a percentile)
x blast_radius  site_wide 1.0 | template 0.8 | single_page 0.5   (banded, never a raw float)
caps            measurement_basis == static_heuristic -> at most medium
                confidence        == heuristic        -> may never reach critical
                coverage below floor                  -> no blast-radius escalation
                status            == latent           -> at most low
                status            == confirm_intent   -> at most low
                (precedence: latent > confirm_intent > active)
"""
from __future__ import annotations

from dataclasses import dataclass, field

ORDER = ["info", "low", "medium", "high", "critical"]
COVERAGE_FLOOR = 3  # pages; below this, blast radius is not trusted


def _idx(s: str) -> int:
    return ORDER.index(s) if s in ORDER else 0


def _clamp(s: str, ceiling: str) -> str:
    return ORDER[min(_idx(s), _idx(ceiling))]


# ---------------------------------------------------------------------------
# The table. Every base severity is defended in references/severity-rationale.md
# ---------------------------------------------------------------------------
SEVERITY_TABLE: dict[str, dict] = {
    # -- Gate 1: access -----------------------------------------------------
    "A1_retrieval_agent_blocked":  {"base": "critical", "gate": "access",         "mechanism": "A"},
    "A2_snippet_suppressed":       {"base": "high",     "gate": "access",         "mechanism": "B"},
    "A3_noindex":                  {"base": "critical", "gate": "access",         "mechanism": "A"},
    "A4_redirect_chain":           {"base": "low",      "gate": "access",         "mechanism": "A"},
    "A5_canonical_problem":        {"base": "medium",   "gate": "access",         "mechanism": "A"},
    "A6_sitemap_missing":          {"base": "low",      "gate": "access",         "mechanism": "A"},
    "A7_site_unreadable":          {"base": "critical", "gate": "access",         "mechanism": "A"},
    "A3_noindex_utility":          {"base": "medium",   "gate": "access",         "mechanism": "A"},
    "A8_robots_token_unrecognised": {"base": "medium",  "gate": "access",         "mechanism": "A"},
    # -- Gate 2: extractability ---------------------------------------------
    "B1_fact_absent":              {"base": "high",     "gate": "extractability", "mechanism": "C"},
    "B1_fact_script_only":         {"base": "medium",   "gate": "extractability", "mechanism": "C"},
    "B4_empty_shell":              {"base": "high",     "gate": "extractability", "mechanism": "C"},
    "B6_filler_heavy":             {"base": "low",      "gate": "extractability", "mechanism": "F"},
    # -- Gate 3: interpretability -------------------------------------------
    "C1_structured_data_invalid":  {"base": "high",     "gate": "interpretability", "mechanism": "C"},
    "C1_structured_data_absent":   {"base": "medium",   "gate": "interpretability", "mechanism": "C"},
    "C2_markup_text_contradiction": {"base": "high",    "gate": "interpretability", "mechanism": "D"},
    "C3_entity_unanchored":        {"base": "medium",   "gate": "interpretability", "mechanism": "D"},
    "C5_faq_content_unmarked":     {"base": "medium",   "gate": "interpretability", "mechanism": "B"},
    "C6_entity_name_conflict":     {"base": "medium",   "gate": "interpretability", "mechanism": "D"},
    "X1_low_quotability":          {"base": "medium",   "gate": "interpretability", "mechanism": "B"},
    "X2_no_citation_anchor":       {"base": "low",      "gate": "interpretability", "mechanism": "B"},
    # -- Freshness / corroboration ------------------------------------------
    "D1_no_date_signals":          {"base": "medium",   "gate": "freshness", "mechanism": "D"},
    "D2_stale_copyright":          {"base": "low",      "gate": "freshness", "mechanism": "D"},
    "D3_content_stale":            {"base": "medium",   "gate": "freshness", "mechanism": "D"},
    "D4_internal_contradiction":   {"base": "high",     "gate": "freshness", "mechanism": "D"},
    "D5_no_corroboration_hooks":   {"base": "medium",   "gate": "freshness", "mechanism": "D"},
    # -- Engagement ----------------------------------------------------------
    "E1_form_friction":            {"base": "medium",   "gate": "engagement", "mechanism": "on-site"},
    "E2_vague_link_text":          {"base": "low",      "gate": "engagement", "mechanism": "on-site"},
    "E3_unnamed_controls":         {"base": "medium",   "gate": "engagement", "mechanism": "on-site"},
    "E4_images_missing_alt":       {"base": "medium",   "gate": "engagement", "mechanism": "C"},
    "E5_no_lang":                  {"base": "low",      "gate": "engagement", "mechanism": "on-site"},
    "E6_heading_structure":        {"base": "low",      "gate": "engagement", "mechanism": "on-site"},
    "E7_zoom_disabled":            {"base": "medium",   "gate": "engagement", "mechanism": "on-site"},
    "E9_promise_payoff_mismatch":  {"base": "medium",   "gate": "engagement", "mechanism": "B"},
    "E10_no_next_step":            {"base": "medium",   "gate": "engagement", "mechanism": "on-site"},
}

# What a finding hurts, for a reader who does not think in gates: engagement
# checks cost visitors who already arrived, every other gate costs being found
# and cited. Alt text, filler and a promise/payoff mismatch cost both.
HURTS_BOTH = {"B6_filler_heavy", "E4_images_missing_alt", "E9_promise_payoff_mismatch"}


def hurts_for(check_id: str, gate: str) -> str:
    if check_id in HURTS_BOTH:
        return "both"
    return "user_retention" if gate == "engagement" else "ai_discoverability"


BLAST = {"site_wide": 1.0, "template": 0.8, "single_page": 0.5}


@dataclass
class Finding:
    check_id: str
    title: str
    evidence: str
    suggested_action: dict
    affected_urls: list = field(default_factory=list)
    blast_radius: str = "single_page"
    confidence: str = "deterministic"        # deterministic | heuristic
    measurement_basis: str = "static_fact"   # static_fact | static_heuristic
    status: str = "active"                   # active | latent | confirm_intent
    blocked_by: dict | None = None
    # Why this looks like a deliberate configuration rather than a defect.
    # Populated only by the skill that owns the evidence, never by the orchestrator.
    intent_signals: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    # populated by finalise()
    id: str = ""
    severity: str = ""
    severity_rationale: str = ""
    gate: str = ""
    mechanism: str = ""
    hurts: str = ""

    def finalise(self, index: int, coverage_pages: int) -> "Finding":
        spec = SEVERITY_TABLE.get(self.check_id, {"base": "low", "gate": "unknown",
                                                  "mechanism": "unspecified"})
        self.gate, self.mechanism = spec["gate"], spec["mechanism"]
        self.hurts = hurts_for(self.check_id, self.gate)
        base = spec["base"]
        steps = [f"base={base} ({self.gate}/{self.check_id})"]

        sev = base
        if coverage_pages < COVERAGE_FLOOR:
            steps.append(f"coverage={coverage_pages}<{COVERAGE_FLOOR}: no blast escalation")
        else:
            mult = BLAST.get(self.blast_radius, 0.5)
            steps.append(f"blast={self.blast_radius} x{mult}")
            if mult < 0.7 and _idx(sev) > 0:
                sev = ORDER[_idx(sev) - 1]
                steps.append(f"-> demoted to {sev}")

        if self.measurement_basis == "static_heuristic":
            before = sev
            sev = _clamp(sev, "medium")
            if sev != before:
                steps.append(f"cap(static_heuristic)-> {sev}")
        if self.confidence == "heuristic":
            before = sev
            sev = _clamp(sev, "high")
            if sev != before:
                steps.append(f"cap(heuristic)-> {sev}")
        # Precedence: latent > confirm_intent > active. Both clamp to low; a
        # confirm-intent finding that is ALSO behind a blocker is reported as
        # latent and keeps its intent_signals alongside blocked_by.
        if self.status == "latent":
            before = sev
            sev = _clamp(sev, "low")
            if sev != before:
                steps.append(f"cap(latent)-> {sev}")
        elif self.status == "confirm_intent":
            before = sev
            sev = _clamp(sev, "low")
            if sev != before:
                steps.append(f"cap(confirm_intent)-> {sev}")

        self.severity = sev
        self.severity_rationale = "; ".join(steps) + f" => {sev}"
        self.id = f"F-{index:03d}"
        return self

    def to_report(self) -> dict:
        """Required fields first, then our superset."""
        out = {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
            # -- superset --
            "check_id": self.check_id,
            "hurts": self.hurts,
            "gate": self.gate,
            "mechanism": self.mechanism,
            "status": self.status,
            "confidence": self.confidence,
            "measurement_basis": self.measurement_basis,
            "blast_radius": self.blast_radius,
            "severity_rationale": self.severity_rationale,
            "affected_urls": sorted(self.affected_urls)[:25],
            "affected_url_count": len(self.affected_urls),
        }
        if self.blocked_by:
            out["blocked_by"] = self.blocked_by
        if self.intent_signals:
            out["intent_signals"] = self.intent_signals
        if self.detail:
            out["detail"] = self.detail
        return out
