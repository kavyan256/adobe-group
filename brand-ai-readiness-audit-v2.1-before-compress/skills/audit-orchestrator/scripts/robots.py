"""RFC 9309 robots.txt parsing + AI-agent taxonomy.

Python's stdlib ``urllib.robotparser`` is NOT RFC 9309-conformant: it mishandles
wildcard expansion and Allow/Disallow precedence. Since a Gate-1 blocking finding
is only as trustworthy as its parser, we implement the specified semantics here.

RFC 9309 rules implemented:
  * user-agent tokens match case-insensitively on the product token
  * ALL matching groups are merged; the "*" group applies only when no specific
    group matches (never additively)
  * Allow/Disallow resolve by LONGEST match after '*'/'$' expansion; ties -> Allow
  * an empty Disallow value means "allow everything"
  * paths are case-sensitive; percent-encoding is normalised before comparison
  * 4xx on robots.txt  => allow all
  * persistent 5xx/unreachable => treat as full disallow (conservative)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import unquote, urlparse

# --------------------------------------------------------------------------
# Agent taxonomy.
#
# This is the single most important table in the audit. Conflating "blocks
# training" with "blocks citation" produces a high-severity false positive
# against publishers who deliberately allow retrieval while refusing training —
# exactly the sophisticated operators a reviewer is most likely to spot-check.
# --------------------------------------------------------------------------

RETRIEVAL_AGENTS = {
    # These fetch/index pages in order to ANSWER a user. Blocking them is what
    # actually removes a site from an assistant's answer.
    "OAI-SearchBot":   "ChatGPT search index",
    "ChatGPT-User":    "ChatGPT live user-initiated fetch",
    "Claude-SearchBot": "Claude search index",
    "Claude-User":     "Claude live user-initiated fetch",
    "PerplexityBot":   "Perplexity index",
    "Perplexity-User": "Perplexity live user-initiated fetch",
    "Applebot":        "Apple / Siri retrieval",
    "Googlebot":       "Google index (also serves AI Overviews)",
    "Bingbot":         "Bing index (also serves Copilot)",
}

TRAINING_AGENTS = {
    # These gather corpora for model TRAINING. Blocking them is a licensing
    # posture, not a discoverability defect. Reported without severity.
    "GPTBot":             "OpenAI model training",
    "ClaudeBot":          "Anthropic model training",
    "CCBot":              "Common Crawl corpus",
    "Google-Extended":    "Gemini training (does NOT affect Google Search or AI Overviews)",
    "Applebot-Extended":  "Apple model training",
    "Bytespider":         "ByteDance training",
}

AMBIGUOUS_AGENTS = {
    "meta-externalagent": "Meta; documentation does not cleanly separate training from retrieval",
}


def classify_agent(token: str) -> str:
    """Return 'retrieval' | 'training' | 'ambiguous' | 'unknown'."""
    for table, label in ((RETRIEVAL_AGENTS, "retrieval"),
                         (TRAINING_AGENTS, "training"),
                         (AMBIGUOUS_AGENTS, "ambiguous")):
        for known in table:
            if known.lower() == token.lower():
                return label
    return "unknown"


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

@dataclass
class Rule:
    allow: bool
    path: str
    pattern: re.Pattern = field(init=False)

    def __post_init__(self) -> None:
        self.pattern = _compile(self.path)

    @property
    def specificity(self) -> int:
        # RFC 9309: longest path wins. '*' and '$' are not counted as length.
        return len(self.path.replace("*", "").replace("$", ""))


def _compile(path: str) -> re.Pattern:
    out, i = [], 0
    while i < len(path):
        ch = path[i]
        if ch == "*":
            out.append(".*")
        elif ch == "$" and i == len(path) - 1:
            out.append("$")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out))


@dataclass
class Group:
    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    crawl_delay: float | None = None


class Robots:
    """Parsed robots.txt with RFC 9309 group-matching and precedence."""

    def __init__(self, text: str = "", status: int = 200, reachable: bool = True):
        self.status = status
        self.reachable = reachable
        self.raw = text
        self.groups: list[Group] = []
        self.sitemaps: list[str] = []
        self._parse(text)

    # -- parsing -------------------------------------------------------
    def _parse(self, text: str) -> None:
        current: Group | None = None
        expecting_agent = False
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field_name, _, value = line.partition(":")
            key = field_name.strip().lower()
            value = value.strip()

            if key == "user-agent":
                if current is None or not expecting_agent:
                    current = Group()
                    self.groups.append(current)
                    expecting_agent = True
                current.agents.append(value)
            elif key in ("allow", "disallow"):
                if current is None:
                    continue
                expecting_agent = False
                # An empty Disallow means "allow all" -> no constraint recorded.
                if key == "disallow" and value == "":
                    continue
                current.rules.append(Rule(allow=(key == "allow"), path=value))
            elif key == "crawl-delay":
                if current is not None:
                    expecting_agent = False
                    try:
                        current.crawl_delay = float(value)
                    except ValueError:
                        pass
            elif key == "sitemap":
                self.sitemaps.append(value)

    # -- querying ------------------------------------------------------
    def _match_groups(self, agent: str) -> list[Group]:
        """Groups that apply to this agent, per RFC 9309 section 2.2.1.

        Product-token comparison is EXACT (case-insensitive), not substring.
        v2.0 used substring containment, so a group written `User-agent: Claude`
        captured both ClaudeBot (training) and Claude-User (retrieval) -- which
        could turn a deliberate training-only block into a critical
        retrieval-blocked finding. A token that matches no crawler exactly
        matches nothing at all; that silence is itself reported, as
        A8_robots_agent_token_unrecognised.
        """
        agent_l = agent.lower()
        specific = [g for g in self.groups
                    if any(a.lower() != "*" and a.lower() == agent_l for a in g.agents)]
        if specific:
            return specific  # '*' never applies additively
        return [g for g in self.groups if any(a == "*" for a in g.agents)]

    def explain(self, agent: str, url_or_path: str) -> dict:
        """Why this agent is or is not allowed here -- the deciding rule itself.

        Lets a finding quote the exact robots.txt line responsible instead of
        asserting a verdict the reader has to take on trust, and tells the
        intent classifier whether a block was aimed at this agent by name or
        merely inherited from the wildcard group.
        """
        groups = self._match_groups(agent)
        via_wildcard = bool(groups) and all(
            any(a == "*" for a in g.agents) for g in groups)
        path = unquote(urlparse(url_or_path).path or "/")
        best: Rule | None = None
        for g in groups:
            for rule in g.rules:
                if rule.pattern.match(path):
                    if (best is None
                            or rule.specificity > best.specificity
                            or (rule.specificity == best.specificity and rule.allow)):
                        best = rule
        return {
            "allowed": self.allowed(agent, url_or_path),
            "rule": (f"{'Allow' if best.allow else 'Disallow'}: {best.path}"
                     if best else None),
            "group_agents": sorted({a for g in groups for a in g.agents}),
            "via_wildcard": via_wildcard,
            "matched_a_group": bool(groups),
        }

    def allowed(self, agent: str, url_or_path: str) -> bool:
        if not self.reachable or (self.status and 500 <= self.status < 600):
            return False  # conservative: persistent server error => treat as disallowed
        if self.status and 400 <= self.status < 500:
            return True   # 4xx => allow all

        path = urlparse(url_or_path).path or "/"
        path = unquote(path)

        best: Rule | None = None
        for group in self._match_groups(agent):
            for rule in group.rules:
                if rule.pattern.match(path):
                    if (best is None
                            or rule.specificity > best.specificity
                            or (rule.specificity == best.specificity and rule.allow)):
                        best = rule
        return True if best is None else best.allow

    def crawl_delay(self, agent: str) -> float | None:
        for group in self._match_groups(agent):
            if group.crawl_delay is not None:
                return group.crawl_delay
        return None

    def agent_report(self, sample_paths: Iterable[str]) -> dict:
        """Per-agent access summary over representative paths, split by class."""
        paths = list(sample_paths) or ["/"]
        out: dict[str, dict] = {}
        for table in (RETRIEVAL_AGENTS, TRAINING_AGENTS, AMBIGUOUS_AGENTS):
            for token, purpose in table.items():
                blocked = [p for p in paths if not self.allowed(token, p)]
                explanations = [self.explain(token, p) for p in paths
                                if not self.allowed(token, p)]
                out[token] = {
                    "class": classify_agent(token),
                    "purpose": purpose,
                    "blocked_paths": sorted(blocked),
                    "fully_blocked": len(blocked) == len(paths),
                    "partially_blocked": 0 < len(blocked) < len(paths),
                    # Was this agent named in a group of its own, or did it just
                    # inherit the wildcard group? That is the difference between
                    # a deliberate policy and collateral damage.
                    "blocked_via_wildcard": bool(explanations) and all(
                        e["via_wildcard"] for e in explanations),
                    "deciding_rules": sorted({e["rule"] for e in explanations if e["rule"]}),
                }
        return out

    def unrecognised_agent_tokens(self) -> list[dict]:
        """Groups naming a token that matches no real crawler exactly.

        Now that matching is exact, `User-agent: Claude` matches nothing at all
        -- the rule the operator wrote has no effect on any crawler. Silence is
        worse than a wrong answer here, so it is surfaced as a finding.
        """
        known = {t.lower(): t for t in
                 (*RETRIEVAL_AGENTS, *TRAINING_AGENTS, *AMBIGUOUS_AGENTS)}
        out = []
        for g in self.groups:
            for a in g.agents:
                al = a.strip().lower()
                if al == "*" or al in known:
                    continue
                near = sorted(orig for low, orig in known.items()
                              if len(al) >= 4 and (low.startswith(al) or al.startswith(low[:4])))
                if near:
                    out.append({"token": a, "probably_meant": near})
        return out
