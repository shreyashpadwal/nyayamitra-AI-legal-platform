---
title: NyayaMitra Backend
emoji: ⚖️
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# NyayaMitra — AI Legal Platform Backend

FastAPI backend for NyayaMitra, an AI-powered Indian legal information platform.

## Stack
- **FastAPI** + **LangGraph** Self-RAG pipeline
- **FAISS** + **BM25** hybrid retrieval over Indian legal corpus (IPC, CrPC, RTI, Consumer Protection Act, Constitution)
- **Cross-encoder reranking** (ms-marco-MiniLM-L6-v2)
- **Groq LLaMA** for generation
- **PostgreSQL** (Neon/Supabase free tier) for user accounts and history

## Environment Variables (set in HF Spaces Settings → Variables)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon/Supabase Postgres connection string |
| `GROQ_API_KEY` | Groq API key for LLaMA inference |
| `SECRET_KEY` | JWT signing secret |
| `FRONTEND_URL` | Vercel deployment URL (for CORS) — e.g. `https://nyayamitra.vercel.app` |
| `TAVILY_API_KEY` | *(optional)* Tavily web search fallback |

## API
The API is available at `https://<your-space-name>.hf.space/api/...`

Health check: `GET /`
