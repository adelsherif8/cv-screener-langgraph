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

## 3. Baseline trace analysis — the failure modes

Reading the baseline traces in Langfuse surfaced three distinct problems.
(Screenshots below; replace the placeholders with your own captures.)

### Failure mode A — the router misclassifies ambiguous CVs
The router span on ambiguous candidates shows the model latching onto surface
keywords. A full-stack engineer whose CV says *"core is server-side APIs and
databases"* gets routed to `frontend` because the CV also mentions React. The
**retriever's agreement flag goes false** in exactly these traces — the
embedding top-match disagrees with the router — which is the signal that
caught it. A wrong track means the scorer grades against the wrong rubric.

> ![Router misroute trace](screenshots/01-router-misroute.png)
> _Langfuse trace: router output `frontend` while the retriever's embedding
> top-match is `backend` (agreement flag = false)._

### Failure mode B — the scorer's free-text output is unparseable
The baseline scorer is asked to "give your assessment" and returns prose with
no fixed format. The graph then regexes a score and decision out of that prose,
which fails whenever the model omits a `NN/100` or hedges ("could be a fit,
but..."). Failed parses default to `reject`, silently dropping good candidates.
The `parse_failure_rate` metric quantifies this.

> ![Scorer parse failure trace](screenshots/02-scorer-parse-failure.png)
> _Langfuse generation: verbose free-text scorer output with no parseable
> score; the run defaults to reject._

### Failure mode C — `gpt-4o` everywhere is the cost and latency driver
The trace's generation breakdown shows both LLM nodes on `gpt-4o`, dominating
latency and cost. Routing and rubric-scoring are bounded, well-specified tasks
that do not need a frontier model — visible directly in the per-generation
cost on each span.

> ![Cost breakdown trace](screenshots/03-cost-breakdown.png)
> _Langfuse trace: per-generation token usage and USD cost, baseline `gpt-4o`._

---

## 4. The fixes (driven by the traces)

| Failure mode | Fix | Mechanism |
| --- | --- | --- |
| A — misrouting | Explicit track definitions + a "route by primary/core focus" disambiguation rule; structured JSON output; temperature 0 | Removes the ambiguity the model was guessing through; the schema forces a valid track |
| B — parse failures | Schema-constrained scorer output (`response_format` JSON schema): `decision`, `score`, `matched_must_haves`, `reasoning` | Eliminates post-hoc parsing entirely; no more silent reject-defaults |
| C — cost/latency | Move both nodes from `gpt-4o` to `gpt-4o-mini` | The tasks are bounded; the smaller model holds accuracy at a fraction of cost/latency |

All three are prompt/agent-config changes — no change to the task, the data, or
the graph topology. That isolation is what lets the before/after numbers be
attributed to the fixes.

---

## 5. Results — before / after

<!-- METRICS:START -->
| Metric | Baseline | Optimized | Change |
| --- | --- | --- | --- |
| Decision accuracy | 88.9% | 88.9% | no change |
| Routing accuracy | 83.3% | 94.4% | up 13% (improved) |
| Parse-failure rate | 0.0% | 0.0% | no change |
| Mean latency / screen | 0.001 s | 0.001 s | no change |
| Mean cost / screen | $0.001153 | $0.000071 | down 94% (improved) |
| Cost / 1,000 screens | $1.15 | $0.07 | down 94% (improved) |
| Mean tokens / screen | 281 | 297 | up 5% (regressed) |

_Computed over 18 labeled candidate runs per profile (`data/candidates.json`)._
<!-- METRICS:END -->

### Concrete baseline errors the optimized profile corrected

<!-- FAILURES:START -->
- **c05** — misrouted `frontend` -> `backend` (gold `backend`)
- **c10** — misrouted `frontend` -> `data` (gold `data`)
<!-- FAILURES:END -->

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
