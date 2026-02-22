from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_pipeline import get_answer

app = FastAPI(
    title="Indian Legal Assistant API",
    description="RAG-based legal chatbot for Indian laws",
    version="1.0.0"
)

# Allow React frontend (port 5173) to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

class SourceItem(BaseModel):
    law: str
    page: int | str
    excerpt: str

class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceItem]

@app.get("/")
def root():
    return {
        "message": "⚖️ Indian Legal Assistant API is running",
        "docs": "Visit /docs for API documentation"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask", response_model=AnswerResponse)
def ask_question(body: QuestionRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    if len(body.question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 characters)")

    result = get_answer(body.question)
    return result