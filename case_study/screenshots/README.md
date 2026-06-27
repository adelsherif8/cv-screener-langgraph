# Trace screenshots

Drop your Langfuse captures here, named to match the references in
`../CASE_STUDY.md`. All three come from the real run already pushed to your
Langfuse project (filter traces by tag `profile:baseline` / `profile:optimized`).

| File | What to capture |
| --- | --- |
| `01-scorer-parse-failure.png` | A **baseline** `scorer` generation: open a `profile:baseline` trace, click the scorer span, and screenshot the output panel showing the long free-text prose with no parseable score (this is the 100% parse-failure mode). |
| `02-cost-latency-breakdown.png` | A **baseline** trace overview showing the `gpt-4o` generations with their per-call token usage, latency, and USD cost (the cost/latency driver). |
| `03-optimized-structured-output.png` | _(the "after")_ An **optimized** `scorer` generation: open a `profile:optimized` trace and screenshot the clean structured JSON output (`decision` / `score` / `matched_must_haves` / ...) on `gpt-4o-mini` — the contrast with screenshot 01. |

How to get them:

1. Open [Langfuse](https://cloud.langfuse.com) and go to **Tracing**.
2. Filter by tag `profile:baseline` (for 01, 02) or `profile:optimized` (for 03).
3. Open a trace, expand the `cv-screen -> router -> retriever -> scorer` span
   tree, click the relevant span, and screenshot the input/output + usage panel.
4. Save the PNGs here with the names above.

To regenerate the underlying traces at any time: `python eval/run_eval.py`.
