# ── NyayaMitra Backend — Hugging Face Spaces Docker SDK ──────────────────────
# Free CPU tier | Port 7860 (HF Spaces required)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

# System deps needed by psycopg2-binary, faiss-cpu, sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy static data (FAISS indices + judgment PDFs).
# These ship inside the image because HF Spaces free tier has no
# guaranteed persistent disk — the container filesystem is the source of truth.
COPY data/ ./data/

# HF Spaces runs the container as a non-root user (uid 1000).
# Give that user ownership of the working directory.
RUN useradd -m -u 1000 hfuser && chown -R hfuser:hfuser /app
USER hfuser

# HF Spaces expects the app to listen on port 7860
EXPOSE 7860

# Start the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
