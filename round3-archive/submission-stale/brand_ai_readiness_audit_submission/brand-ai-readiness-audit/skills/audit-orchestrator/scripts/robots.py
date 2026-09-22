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

# Agent taxonomy. Conflating "blocks training" with "blocks citation" is the
# worst false positive in this space -- see
# crawl-access-audit/references/bot-taxonomy.md.

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

        Product-token comparison is EXACT (case-insensitive), not substring: a
        group written `User-agent: Claude` matches neither ClaudeBot nor
        Claude-User. Such dead groups are reported as A8.
        """
        agent_l = agent.lower()
        specific = [g for g in self.groups
                    if any(a.lower() != "*" and a.lower() == agent_l for a in g.agents)]
        if specific:
            return specific  # '*' never applies additively
        return [g for g in self.groups if any(a == "*" for a in g.agents)]

    @staticmethod
    def _deciding_rule(groups: list[Group], url_or_path: str) -> Rule | None:
        """Longest match wins; ties go to Allow."""
        path = unquote(urlparse(url_or_path).path or "/")
        best: Rule | None = None
        for group in groups:
            for rule in group.rules:
                if rule.pattern.match(path) and (
                        best is None
                        or rule.specificity > best.specificity
                        or (rule.specificity == best.specificity and rule.allow)):
                    best = rule
        return best

    def explain(self, agent: str, url_or_path: str) -> dict:
        """The deciding robots.txt line, and whether it was aimed at this agent
        by name or merely inherited from the wildcard group."""
        groups = self._match_groups(agent)
        best = self._deciding_rule(groups, url_or_path)
        return {
            "allowed": self.allowed(agent, url_or_path),
            "rule": (f"{'Allow' if best.allow else 'Disallow'}: {best.path}"
                     if best else None),
            "via_wildcard": bool(groups) and all(
                any(a == "*" for a in g.agents) for g in groups),
        }

    def allowed(self, agent: str, url_or_path: str) -> bool:
        if not self.reachable or (self.status and 500 <= self.status < 600):
            return False  # conservative: persistent server error => treat as disallowed
        if self.status and 400 <= self.status < 500:
            return True   # 4xx => allow all
        best = self._deciding_rule(self._match_groups(agent), url_or_path)
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
                verdicts = {p: self.explain(token, p) for p in paths}
                blocked = [p for p, e in verdicts.items() if not e["allowed"]]
                explanations = [verdicts[p] for p in blocked]
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
        """Groups naming a truncated crawler token, e.g. `User-agent: Claude`.

        Matching is exact, so such a group binds no crawler at all. Only a strict
        prefix of a known token is reported: a full token we do not list (such
        as Google-CloudVertexBot) is a real crawler, not a typo.
        """
        known = {t.lower(): t for t in
                 (*RETRIEVAL_AGENTS, *TRAINING_AGENTS, *AMBIGUOUS_AGENTS)}
        out = []
        for g in self.groups:
            for a in g.agents:
                al = a.strip().lower()
                if len(al) < 4 or al in known:
                    continue
                near = sorted(orig for low, orig in known.items() if low.startswith(al))
                if near:
                    out.append({"token": a, "probably_meant": near})
        return out
