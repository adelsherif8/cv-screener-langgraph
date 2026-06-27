# Deploy the interactive demo to Hugging Face Spaces

This gives you a permanent, public, *interactive* demo URL (the Gradio app).
It is free. Vercel can't host this app (it's a persistent Python/Gradio server),
so Spaces is the right home for the live app; the Vercel page is the project
landing page.

## One-time login

```bash
hf auth login        # paste a token from https://huggingface.co/settings/tokens (write scope)
```

## Create + push the Space (from the repo root)

```bash
# 1. create the Space (Gradio SDK)
hf repo create cv-screener-langgraph --repo-type space --space_sdk gradio -y

# 2. use the Space-flavored README (has the required YAML frontmatter)
cp deploy/README_SPACE.md README_SPACE.tmp     # keep your project README intact

# 3. push app.py, src/, data/, requirements.txt and the Space README
hf upload cv-screener-langgraph app.py app.py --repo-type space
hf upload cv-screener-langgraph src   src   --repo-type space
hf upload cv-screener-langgraph data  data  --repo-type space
hf upload cv-screener-langgraph requirements.txt requirements.txt --repo-type space
hf upload cv-screener-langgraph deploy/README_SPACE.md README.md --repo-type space
```

Your demo will build at `https://huggingface.co/spaces/<your-username>/cv-screener-langgraph`.

## Make it fully live (optional)

By default the Space runs in mock mode (free, no keys). To run real models and
push live Langfuse traces, add these in the Space's **Settings → Variables and
secrets**: `OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_HOST`. Set a small OpenAI usage cap so public traffic can't run up cost.
