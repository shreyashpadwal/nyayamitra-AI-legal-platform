from pydantic import BaseModel, field_validator, model_validator
from typing import Dict, Any, Optional, List


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "citizen"          # "citizen" | "lawyer"
    bar_council_id: Optional[str] = None     # kept for backward compat, not required


class LoginRequest(BaseModel):
    email: str
    password: str


class QuestionRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    k: Optional[int] = 5
    # Last 1-2 completed Q&A turns for follow-up context.
    # Each item: {"question": str, "answer": str}
    history: Optional[List[dict]] = None


class SimilarityRequest(BaseModel):
    query: str
    k: Optional[int] = 5
    include_strategy: Optional[bool] = True


class DocumentRequest(BaseModel):
    doc_type: str
    fields: Dict[str, Any]
