from pydantic import BaseModel
from typing import Dict, Any, Optional

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "citizen"   # "citizen" | "lawyer"

class LoginRequest(BaseModel):
    email: str
    password: str

class QuestionRequest(BaseModel):
    question: str

class SimilarityRequest(BaseModel):
    query: str
    k: Optional[int] = 5
    include_strategy: Optional[bool] = True

class DocumentRequest(BaseModel):
    doc_type: str
    fields: Dict[str, Any]
