# Upwork portfolio — paste-ready

**Where to add it:** Upwork → your profile → Portfolio section → "+ Add" →
"Create a project from scratch."

---

**Project title**
Multi-Agent CV Screener — LangGraph + Langfuse, with a trace-driven optimization case study

**Your role**
AI / LLM Engineer — designed, built, instrumented, and optimized the system end to end

**Completion date**
June 2026

**Project URL** (the "Add a website link" field)
https://cv-screener-langgraph.vercel.app

**Skills (add up to 5)**
- LangGraph
- LLM Agent Development
- Langfuse / LLM Observability
- Prompt Engineering
- Python (OpenAI API)

**Project description**
Built a three-agent LLM pipeline (router → retriever → scorer) in LangGraph that
screens CVs against job rubrics, fully instrumented with Langfuse tracing. I then
ran a real optimization loop: read the production traces, identified the failure
modes, and fixed them with prompt and agent-config changes — then measured the
impact on a labeled evaluation set.

Results (measured live through Langfuse): decision accuracy +7%, latency −37%,
cost −95% (≈$4.40 → $0.21 per 1,000 screens), and scorer output-parse failures
eliminated (100% → 0%). Deliverables include a written case study, a reproducible
eval harness, and an interactive demo.

- Live project page: https://cv-screener-langgraph.vercel.app
- Code + case study: https://github.com/adelsherif8/cv-screener-langgraph

**Images to upload (in this order — folder: `upwork/`)**
1. 01-cover.png        (thumbnail — title + stats)
2. 02-architecture.png (the pipeline diagram)
3. 03-live-demo.png    (the app running)
4. 04-results.png      (before/after metrics)
   (add your Langfuse trace screenshots here once captured)
