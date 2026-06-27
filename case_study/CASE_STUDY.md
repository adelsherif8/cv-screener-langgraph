# Optimizing a Multi-Agent CV Screener with Langfuse Trace Analysis

**A case study in finding and fixing failure modes in an LLM agent pipeline using observability.**

This document walks through a real optimization loop on a small LangGraph
multi-agent system: establish a baseline, read the Langfuse traces, identify
the concrete failure modes the traces expose, apply targeted prompt/agent-config
fixes, and measure the before/after impact on accuracy, latency, and cost.

---

## 1. The system

A three-node LangGraph pipeline that screens a candidate CV against a set of
engineering job rubrics:

```
        +----------+        +-------------+        +----------+
  CV -> |  ROUTER  |  --->  |  RETRIEVER  |  --->  |  SCORER  | -> decision
        |  (agent) |        | (retriever) |        |  (agent) |   + score
        +----------+        +-------------+        +----------+
         classify the        embed CV, fetch        score CV vs the
         CV into a track      the matching job       rubric -> advance
         + seniority          rubric; cross-         / reject + reasoning
                              check the router
```

- **Router** (LLM agent): classifies the CV into one of four tracks
  (`backend`, `frontend`, `ml`, `data`) and estimates seniority.
- **Retriever**: embeds the CV, retrieves the best-matching job rubric by
  cosine similarity, and flags whether that agrees with the router's track
  (a cheap cross-check that surfaces routing errors at scale).
- **Scorer** (LLM agent): scores the CV against the retrieved rubric and
  returns an `advance` / `reject` decision with reasoning.

Every node is wrapped with Langfuse's `@observe` decorator (semantic types
`agent` / `retriever`), and every LLM call is auto-captured as a generation
via the `langfuse.openai` drop-in wrapper, so each screening run produces one
trace with three child spans, their generations, and full token/cost usage.

---

## 2. Method

The same graph runs under two **profiles** that differ only in model choice,
prompt clarity, and output format — never the task:

| | Baseline | Optimized |
| --- | --- | --- |
| Router model | `gpt-4o`, temp 0.7 | `gpt-4o-mini`, temp 0.0 |
| Router prompt | vague, no track definitions | explicit definitions + disambiguation rules |
| Router output | free text (keyword-parsed) | structured JSON (schema-constrained) |
| Scorer model | `gpt-4o`, temp 0.7 | `gpt-4o-mini`, temp 0.0 |
| Scorer prompt | "tell me if they're a good fit" | strict rubric + decision policy |
| Scorer output | free-text prose (regex-parsed) | structured JSON (`decision`/`score`/...) |

Metrics are computed over a labeled set of 18 candidates
(`data/candidates.json`), including deliberately ambiguous CVs (full-stack,
applied scientist, analytics engineer) that probe routing, and weak candidates
(bootcamp, career-changer) that probe decision strictness.

---

## 3. Baseline trace analysis — what the traces actually showed

Reading the baseline traces in Langfuse surfaced two clear failure modes — and,
just as usefully, *disconfirmed* a third I had expected going in. Writing down
the non-problem matters as much as the problems: it changed what the fix had to
do.

### Failure mode A — the scorer emits no machine-readable output (100% parse failure)
The baseline scorer is asked to "give your assessment" with no format
constraint. In the traces, every scorer generation is several paragraphs of
markdown prose ("Based on the provided job description, here is an
assessment...") and **none** contain a cleanly parseable score. The graph's
regex fallback fails on **18 / 18** runs and defaults the score (70 for an
inferred advance, 0 for reject); the decision itself is only recoverable by
keyword-sniffing the prose, which silently collapses to `reject` whenever the
wording hedges. This is the biggest reliability problem and is invisible without
reading the raw generation output — exactly what the trace surfaces.

> ![Scorer parse failure trace](screenshots/01-scorer-parse-failure.png)
> _Langfuse generation: verbose free-text scorer output, no parseable score;
> the run falls back to a defaulted value._

### Failure mode B — `gpt-4o` on every node drives cost and latency
The per-generation view shows both LLM nodes on `gpt-4o`. Routing and
rubric-scoring are bounded, well-specified tasks that do not need a frontier
model, yet on `gpt-4o` the baseline costs **~$4.40 / 1,000 screens** and adds
**~5.8 s/screen** — visible directly in each span's token usage and USD cost.

> ![Cost and latency breakdown](screenshots/02-cost-latency-breakdown.png)
> _Langfuse trace: per-generation token usage, latency, and USD cost on the
> baseline `gpt-4o` nodes._

### Non-problem confirmed — routing was already correct
What the traces did **not** show is as informative. Routing accuracy was
**100%** on the baseline: the vague router prompt on `gpt-4o` classified all 18
CVs correctly, including the deliberately ambiguous full-stack and
applied-scientist cases, and the retriever's embedding-agreement flag stayed
true throughout. So the optimization's job for the router was not to *repair*
routing but to *protect* it — the real risk was that downgrading the router to
the cheaper `gpt-4o-mini` would introduce misroutes.

---

## 4. The fixes (driven by the traces)

| Finding | Fix | Mechanism / result |
| --- | --- | --- |
| A — unparseable scorer output | Schema-constrained JSON output (`response_format`): `decision`, `score`, `matched_must_haves`, `missing_must_haves`, `reasoning` | Eliminates post-hoc parsing entirely — parse-failure 100% → 0%, real scores instead of defaults |
| B — cost / latency | Move both LLM nodes from `gpt-4o` to `gpt-4o-mini` | Cost down ~95%, latency down ~37% |
| Protect routing while downgrading | Explicit track definitions + a "route by primary/core focus" disambiguation rule + structured output + temperature 0 | Routing held at 100% on the cheaper model — no regression |

The decision-accuracy gain comes from grounding the scorer in the rubric and
removing the parse-default behaviour. All changes are prompt/agent-config only —
no change to the task, the data, or the graph topology — which is what lets the
before/after numbers be attributed to the fixes.

---

## 5. Results — before / after

<!-- METRICS:START -->
| Metric | Baseline | Optimized | Change |
| --- | --- | --- | --- |
| Decision accuracy | 83.3% | 88.9% | up 7% (improved) |
| Routing accuracy | 100.0% | 100.0% | no change |
| Parse-failure rate | 100.0% | 0.0% | down 100% (improved) |
| Mean latency / screen | 5.834 s | 3.667 s | down 37% (improved) |
| Mean cost / screen | $0.004399 | $0.000211 | down 95% (improved) |
| Cost / 1,000 screens | $4.40 | $0.21 | down 95% (improved) |
| Mean tokens / screen | 671 | 946 | up 41% (regressed) |

_Computed over 18 labeled candidate runs per profile (`data/candidates.json`)._
<!-- METRICS:END -->

### Concrete baseline errors the optimized profile corrected

<!-- FAILURES:START -->
- **c06** — decision `reject` -> `advance` (gold `advance`)
- **c07** — decision `advance` -> `reject` (gold `reject`)
- **c12** — decision `advance` -> `reject` (gold `reject`)
<!-- FAILURES:END -->

### Two honest caveats

- **Tokens went up 41%, cost still fell 95%.** The optimized scorer injects the
  full rubric and a JSON schema, so it sends *more* tokens per screen — but cost
  is `tokens x model price`, and `gpt-4o-mini` is ~20-40x cheaper per token than
  `gpt-4o`. Token count and cost are not the same axis; the trace cost figures
  make that concrete.
- **The optimized profile is not strictly dominant.** It corrected c06/c07/c12
  but newly over-rejected **c10** and **c11** — a data scientist moving into
  data engineering and an ML researcher with limited production experience.
  The stricter rubric policy judges these senior-but-nontraditional candidates
  too harshly. Net decision accuracy still improved (83.3% → 88.9%), but this
  edge-case over-rejection is the clearest target for the next iteration.

---

## 6. Reproduce it

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. add keys (or skip for offline mock mode)
cp .env.example .env   # fill OPENAI_API_KEY + LANGFUSE_* 

# 3. run the eval for both profiles (writes eval/results/*.json + Langfuse traces)
python eval/run_eval.py

# 4. regenerate this doc's tables from the real run
python eval/build_case_study.py

# 5. capture the three trace screenshots into case_study/screenshots/
```

In Langfuse, filter traces by tag `profile:baseline` vs `profile:optimized`
to compare the two side by side, and open any single run to see the
router -> retriever -> scorer span tree with per-node cost.

---

## 7. What this demonstrates

- Building a **multi-agent pipeline in LangGraph** with clean state and
  semantic node types.
- **Instrumenting an LLM system with Langfuse** end to end (spans +
  generations + cost + tags).
- **Reading traces to diagnose failure modes** rather than guessing.
- Translating those findings into **prompt and agent-config fixes**, and
  proving the impact with a reproducible **accuracy / latency / cost** eval.
