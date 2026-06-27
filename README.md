# Multi-Agent CV Screener — LangGraph + Langfuse

A small **multi-agent system** that screens candidate CVs against engineering
job rubrics, built as a **LangGraph** pipeline and fully instrumented with
**Langfuse** tracing. The repo ships with an interactive **Gradio** demo, a
labeled evaluation harness, and a written **[optimization case study](case_study/CASE_STUDY.md)**
that uses the traces to find and fix real failure modes.

> The case study is the centerpiece: baseline metrics, the failure modes the
> traces exposed, the prompt/agent-config fixes, and before/after numbers
> (accuracy up, latency down, cost down).

---

## Architecture

```
        +----------+        +-------------+        +----------+
  CV -> |  ROUTER  |  --->  |  RETRIEVER  |  --->  |  SCORER  | -> advance / reject
        |  (agent) |        | (retriever) |        |  (agent) |    + score + reasoning
        +----------+        +-------------+        +----------+
```

| Node | Type | What it does |
| --- | --- | --- |
| Router | LLM agent | Classifies the CV into a track (`backend`/`frontend`/`ml`/`data`) + seniority |
| Retriever | retriever | Embeds the CV, fetches the matching job rubric, cross-checks the router |
| Scorer | LLM agent | Scores the CV against the rubric, returns a decision with reasoning |

Each node is a Langfuse-observed span; each LLM call is an auto-captured
generation with token usage and cost. One screening run = one trace with a
clean `router -> retriever -> scorer` tree.

---

## Stack

- **LangGraph** — graph orchestration and typed state
- **Langfuse** (v4, OpenTelemetry-based) — tracing, cost, and tag-based
  before/after comparison
- **OpenAI** — `gpt-4o` (baseline) / `gpt-4o-mini` (optimized) + embeddings
- **Gradio** — interactive demo UI
- Deterministic **mock mode** so everything runs offline with no keys

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: real models + live traces (otherwise runs in offline mock mode)
cp .env.example .env   # add OPENAI_API_KEY + LANGFUSE_* keys

# interactive demo
python app.py

# evaluation: runs both profiles over the labeled set, prints the comparison
python eval/run_eval.py

# regenerate the case study tables from the latest run
python eval/build_case_study.py
```

With no keys set, the system runs in **mock mode** (deterministic, no network,
no cost) so the demo and eval still work — useful for a quick look. Real
metrics and Langfuse screenshots require the keys.

---

## What's in here

```
src/            graph, nodes, state, prompts, config, LLM layer
data/           labeled candidates + job rubrics
eval/           evaluation harness + case-study generator + results
case_study/     CASE_STUDY.md (the deliverable) + trace screenshots
app.py          Gradio demo
```

---

## Demo

The Gradio app lets you paste a CV (or pick a sample), choose the **baseline**
or **optimized** profile, and see each node's decision, a per-node token/cost
breakdown, and a deep link to the Langfuse trace for that run.

Deploy it for a public link with Hugging Face Spaces (Gradio SDK) — add the
`OPENAI_API_KEY` and `LANGFUSE_*` keys as Space secrets.

---

## Case study

See **[case_study/CASE_STUDY.md](case_study/CASE_STUDY.md)** for the full
optimization writeup: how the traces exposed router misrouting, scorer
parse failures, and an over-powered model, and how targeted config changes
improved accuracy while cutting latency and cost.
