---
title: Multi-Agent CV Screener
emoji: 🧭
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
short_description: LangGraph router-retriever-scorer pipeline traced with Langfuse
---

# Multi-Agent CV Screener — LangGraph + Langfuse

Interactive demo of a traced multi-agent CV-screening pipeline.
Code, eval harness, and the full optimization case study:
https://github.com/adelsherif8/cv-screener-langgraph

This Space runs in **mock mode** by default (deterministic, no API cost). To run
it against real models and push live Langfuse traces, add these as **Space
secrets** (Settings → Variables and secrets):

- `OPENAI_API_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (e.g. `https://cloud.langfuse.com`)
