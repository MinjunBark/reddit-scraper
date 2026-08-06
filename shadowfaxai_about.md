# Shadowfax AI — company reference

Compiled from shadowfax.ai (homepage, /features, /use-cases, /about) to give the filtering step
concrete grounding. `config.PAIN_POINTS` should be traceable to something in this document.

> Note: `docs.shadowfax.ai` and `trust.shadowfax.ai` render client-side and returned no readable
> content when fetched. Anything in the product docs is therefore **not** reflected here.

---

## What the product is

An **AI-native analytics platform** that turns messy data into repeatable, auditable analyses
without requiring Python. Positioned against four incumbents, each framed as a compromise:

| Incumbent | Shadowfax's framing |
|---|---|
| BI tools | accessible but inflexible |
| Spreadsheets | versatile but lack governance |
| Visual pipelines | user-friendly but limited |
| Code notebooks | powerful but opaque to non-technical teams |

## Founding thesis — the sharpest signal for filtering

> "The grind never disappeared; it just changed form."

Their claim is that AI copilots bolted onto legacy tools didn't remove analyst toil — analysts now
spend **hours auditing AI outputs instead of producing them**. The stated adoption gap: 70%+ of
software teams use AI-assisted workflows, but **under 10% of business analysts** have, and the
reason given is **trust**.

This matters for triage: a post expressing *distrust of AI-generated analysis*, or the burden of
**checking** an AI's work, is a strong Shadowfax signal even when it never mentions data prep.

## Who they build for

- Business analysts
- **FP&A managers** ← one of the two target subreddits
- **Data analysts** ← the other
- Retail strategists
- Consultants

Common thread: needs sophisticated analytics, **lacks or doesn't want to use coding skills**, and
demands transparency and reproducibility. Positioned as "analyst-in-the-loop" — the human
orchestrates and validates rather than doing grunt work.

## Core capabilities

| Capability | The pain it targets |
|---|---|
| **Graph framework** | Atomic, persistent transformations → "verifiable and reproduceable artifacts" |
| **Deep context awareness** | Knowledge files so the agent speaks your org's acronyms/shorthand |
| **Data understanding & profiling** | "Say goodbye to spending hours untangling data relationships and data quality issues" — auto schema discovery, metadata profiling |
| **Flexible visualization** | Describe the insight, get presentation-ready visuals; no manual chart wrangling |
| **AI tables** | Row-level operations needing judgment: classification, taxonomy creation, enrichment |
| **Flexible prompt patterns** | Declarative *or* procedural requests; no syntax to learn |
| **Analyst workflow support** | Reactive inputs, scoped changes, cascading and grouped logic |

## Named use cases

These are the concrete workflows they advertise — a Reddit post describing any of these by name is
a high-value match:

- **Data prep & cleaning** — finds issues, proposes fixes, validates transparently
- **SaaS bookings forecasting** — blends pipeline and historicals
- **Sales pipeline progression** — compares snapshots, flags at-risk deals
- **RFM analysis** — advertised as 1–2 weeks reduced to minutes
- **Cohort analysis**
- **Revenue diagnosis**
- **Supplier analytics**
- **SG&A benchmarking**
- **Multi-tool report consolidation**
- **Methodology standardization** via knowledge files

## Company

Founded by veterans of **Snowflake, Palantir, and Rubrik**. Backed by **Khosla Ventures** and the
**Snowflake Startup Accelerator**. Team has scaled data/analytics products past $1B ARR.

---

## Implications for post filtering

Derived from the above, these are the signals worth matching — including several the original
`BUILD-INSTRUCTIONS.md` pain-point list omitted:

**Already covered by the original list**
- data prep / data cleaning
- forecasting
- automation tooling
- agentic tools with auditability
- reducing manual operations

**Missing from the original list, but central to their positioning**
1. **Distrust of AI output / the burden of verifying it** — their founding thesis, and absent from
   the original list entirely
2. **Reproducibility and repeatability** — re-running an analysis, version drift, "how did we get
   this number last quarter"
3. **Spreadsheet pain at scale** — Excel breaking, fragility, no governance
4. **BI tool rigidity** — waiting on engineering to change a dashboard
5. **The coding barrier** — wanting Python/SQL capability without being a programmer
6. **Data profiling / exploration toil** — untangling relationships and quality issues by hand
7. **Ad-hoc request backlog** — being the bottleneck for stakeholder questions
8. **Manual reporting cycles** — rebuilding the same deck or report every month
9. **Manual charting / presentation prep**

**Deliberately NOT signals** — these dominate both subreddits by volume and are the main source of
false positives:
- career advice, job hunting, résumé review, salary questions
- certification and course questions (CFA, FP&A cert, CompTIA Data+)
- "how do I break into this field", "which degree should I take"
- someone wanting to **leave** the profession — venting about the job is not buying intent
