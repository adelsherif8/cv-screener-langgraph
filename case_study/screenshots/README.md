# Trace screenshots

Drop your Langfuse captures here, named to match the references in
`../CASE_STUDY.md`:

| File | What to capture |
| --- | --- |
| `01-router-misroute.png` | A baseline trace where the router span's track disagrees with the retriever's embedding top-match (agreement flag = false) on an ambiguous CV (e.g. candidate `c05` or `c10`). |
| `02-scorer-parse-failure.png` | A baseline scorer generation with verbose free-text output and no clean `NN/100`, where the run defaulted to reject. |
| `03-cost-breakdown.png` | A baseline trace's generation view showing per-call `gpt-4o` token usage and USD cost, next to the optimized `gpt-4o-mini` equivalent. |

How to get them:

1. Set your keys in `.env`, then run `python eval/run_eval.py`.
2. Open [Langfuse](https://cloud.langfuse.com), filter traces by tag
   `profile:baseline` and `profile:optimized`.
3. Open the relevant trace, screenshot the span tree / generation, and save here.
