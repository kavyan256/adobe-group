# ChatGPT check on cleartax.in — protocol (written 2026-09-25, before running)

**Question:** Does ClearTax's noindexed pricing page stop an assistant from citing it,
while its ordinary indexed pages still get cited? This is the field-research
observation Part 1 is missing: what separates a page assistants cite from one they
don't, on the same site.

**Known before running**
- `cleartax.in/s/pricing` is the only pricing page (clear.in redirects to it). It
  carries `noindex,nofollow` and a self-canonical.
- Its raw HTML has **no plan prices**, only marketing figures (Avg. ₹26,686 refund,
  etc.). The plan prices must load with JavaScript.
- Control page `cleartax.in/s/what-is-credit-transfer-document-in-gst` is
  `index,follow`.

## Step 0: the true answer
Open https://cleartax.in/s/pricing in a normal browser. Write down each plan name
and price shown, and take a screenshot. Without this we can't judge ChatGPT's answer.

## Steps
New chat for each question. Web search ON. Screenshot the full answer *with its
source list*.

- **Q1 (pricing, the noindexed page):** "How much does ClearTax charge for
  CA-assisted ITR filing right now? Cite your sources."
- **Q2 (pricing, plans):** "What are ClearTax's ITR filing plans and their current
  prices? Cite your sources."
- **Q3 (control, an indexed ClearTax page):** "What is a Credit Transfer Document
  (CTD) under GST transition? Cite your sources."

Record for each one: date and time, the model ChatGPT shows, the answer, every
cited URL, and whether `cleartax.in/s/pricing` appears among them.

## What each outcome means (decided now, not after)
| Result | What it means | What we may say in the video |
|---|---|---|
| Q1/Q2 don't cite `/s/pricing`; prices come from third parties, are out of date, or ChatGPT says it can't confirm them. Q3 cites ClearTax | **Supports the finding.** Same site, cited for an indexed page, not for the noindexed one | "We asked ChatGPT. It cited ClearTax for a GST question, but not for ClearTax's own prices." |
| Q1/Q2 cite `/s/pricing` but give no plan prices, or wrong ones | Partly supports it. The page was reached, but its prices aren't in what the fetcher reads | "Even when ChatGPT found the page, it couldn't read the prices." |
| Q1/Q2 cite `/s/pricing` and give the correct current prices | **Weakens the finding.** noindex didn't stop this assistant | Nothing about impact. Keep the finding as measured, drop the claim |
| Q3 doesn't cite ClearTax either | The control failed, so the test says nothing about noindex | Nothing |

Keep every screenshot, whatever the outcome.
