# Deliberate configuration vs. defect

Some findings describe a setting the site owner chose on purpose. Reporting
those as defects, and ranking them above real breakage, is the fastest way for
an audit to lose a reader's trust — the first thing they read is an instruction
to undo a decision they remember making.

These findings are still reported, with the same evidence. What changes is the
posture: `status: "confirm_intent"`, a question instead of an instruction, and a
severity cap of `low` so they cannot outrank a real blocker or become the
report's headline.

This is a judgement the audit makes explicitly and shows its work for, in
`intent_signals`. A reader who disagrees can see exactly which signals drove it.

## noindex

`A3_noindex_utility` instead of `A3_noindex` when **all** of:

1. noindex is not site-wide, and
2. it covers at most 34% of crawled pages, and
3. every affected page is on a `legal`, `utility` or `search` template, and
4. no affected page is on `home`, `product`, `pricing`, `about`, `blog` or `contact`.

Keeping terms of service, a login screen or a search-results page out of an
index is routine. Keeping the pricing page out is not — that stays `critical`.

## AI crawler blocks

`A1_retrieval_agent_blocked` becomes `confirm_intent` when **all** of:

1. every blocking rule comes from a group naming that agent explicitly, not from
   the wildcard group, and
2. robots.txt names at least two AI agents by token, or explicitly allows another
   retrieval agent, and
3. the blocks are path-scoped rather than a whole-site `Disallow: /` against
   every retrieval agent.

A retrieval agent caught by a bare `User-agent: *  Disallow: /` is almost never a
decision about AI citation — that rule usually predates the question. A
retrieval agent named in a group of its own, on a site that names several AI
agents, is a policy someone wrote deliberately.

Blocking retrieval agents is a coherent licensing position. The cost is that
assistants cannot cite you. That is a business decision, and the report says so
rather than calling it a bug.

## What this is not

This is not a way to soften findings generally. The classifier has to
discriminate, and the test suite proves it does: noindex confined to legal pages
is `confirm_intent` at `low`; noindex on the homepage and pricing page stays
`active` at `critical`.
