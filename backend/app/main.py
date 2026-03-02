import faiss
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from .db.database import engine
from .db.models import Base
from .api.endpoints import auth_routes, citizen_routes, lawyer_routes, lawyer_documents

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="⚖️ NyayaMitra API",
    description="Professional Indian Legal AI - Platform Backend",
    version="3.1.0"
)

# Deployment Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAISS_PATH = os.path.join(BASE_DIR, "data", "judgments_index", "lawyer_case_index.faiss")

# Global index storage
lawyer_index = None

@app.on_event("startup")
def load_faiss():
    global lawyer_index
    if os.path.exists(FAISS_PATH):
        try:
            lawyer_index = faiss.read_index(FAISS_PATH)
            logger.info(f"✅ FAISS Index loaded successfully from {FAISS_PATH}")
        except Exception as e:
            logger.error(f"❌ Failed to load FAISS index: {e}")
    else:
        logger.warning(f"⚠️ FAISS Index not found at {FAISS_PATH}")

# CORS Configuration - Updated for Production (Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "https://nyayamitra.vercel.app",  # Example Vercel URL
        "https://nyaya-mitra.vercel.app" # Alternate
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular Routers
app.include_router(auth_routes.router, prefix="/api/auth")
app.include_router(citizen_routes.router, prefix="/api/citizen")
app.include_router(lawyer_routes.router, prefix="/api/lawyer")
app.include_router(lawyer_documents.router, prefix="/api/lawyer/documents")

# Mounting Static Files for Judgments
judgments_path = os.path.join(BASE_DIR, "data", "pdfs")
if os.path.exists(judgments_path):
    app.mount("/data/judgments", StaticFiles(directory=judgments_path), name="judgments")
else:
    logger.warning(f"⚠️ Judgments PDF directory not found at {judgments_path}")

@app.get("/")
def health_check():
    return {
        "status": "online", 
        "message": "⚖️ NyayaMitra API is operational", 
        "faiss_loaded": lawyer_index is not None
    }
