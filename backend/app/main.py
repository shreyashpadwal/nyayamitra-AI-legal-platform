import os
import logging
import faiss
from dotenv import load_dotenv

load_dotenv()  # no-op on HF Spaces (vars are injected); needed for local dev

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db.database import engine
from .db.models import Base
from .api.endpoints import (
    auth_routes,
    citizen_routes,
    lawyer_routes,
    lawyer_documents
)

# ---------------------------------------------------
# Logging Configuration
# ---------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------
app = FastAPI(
    title="⚖️ NyayaMitra API",
    description="Professional Indian Legal AI - Platform Backend",
    version="3.2.0"
)

# ---------------------------------------------------
# Deployment Paths
# ---------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAISS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "judgments_index",
    "lawyer_case_index.faiss"
)

# Global FAISS index storage
lawyer_index = None


# ---------------------------------------------------
# Startup Event (SAFE FOR RENDER)
# ---------------------------------------------------
@app.on_event("startup")
def startup_event():
    global lawyer_index

    logger.info("🚀 Starting NyayaMitra Backend...")

    # ✅ Safe Database Initialization
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables ready")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

    # ✅ Safe FAISS Load
    if os.path.exists(FAISS_PATH):
        try:
            lawyer_index = faiss.read_index(FAISS_PATH)
            logger.info(f"✅ FAISS Index loaded from {FAISS_PATH}")
        except Exception as e:
            logger.error(f"❌ Failed to load FAISS index: {e}")
    else:
        logger.warning(f"⚠️ FAISS index not found at {FAISS_PATH}")

    # ✅ Preload citizen retriever (HybridRetriever: FAISS + BM25 embeddings)
    #    Prevents cold-start latency on the first citizen query.
    try:
        from .services.vector_service import _get_citizen_retriever
        _get_citizen_retriever()
        logger.info("✅ Citizen HybridRetriever preloaded")
    except Exception as e:
        logger.error(f"❌ Citizen retriever preload failed (non-fatal): {e}")

    # ✅ Preload cross-encoder reranker (sentence-transformers model)
    #    The cross-encoder download/load is the single biggest cold-start cost.
    try:
        from .services.vector_service import _get_reranker
        _get_reranker()
        logger.info("✅ CrossEncoderReranker preloaded")
    except Exception as e:
        logger.error(f"❌ Reranker preload failed (non-fatal): {e}")


# FRONTEND_URL is set as an env var on HF Spaces after the Vercel deploy URL is known.
# Falls back to localhost for local development.
_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        _FRONTEND_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------
# Include Routers
# ---------------------------------------------------
app.include_router(auth_routes.router, prefix="/api/auth")
app.include_router(citizen_routes.router, prefix="/api/citizen")
app.include_router(lawyer_routes.router, prefix="/api/lawyer")
app.include_router(lawyer_documents.router, prefix="/api/lawyer/documents")


# ---------------------------------------------------
# Static Files (Judgments PDFs)
# ---------------------------------------------------
judgments_path = os.path.join(BASE_DIR, "data", "pdfs")

if os.path.exists(judgments_path):
    app.mount(
        "/data/judgments",
        StaticFiles(directory=judgments_path),
        name="judgments"
    )
else:
    logger.warning(f"⚠️ Judgments directory not found at {judgments_path}")


# ---------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------
@app.get("/")
def health_check():
    return {
        "status": "online",
        "message": "⚖️ NyayaMitra API is operational",
        "faiss_loaded": lawyer_index is not None
    }