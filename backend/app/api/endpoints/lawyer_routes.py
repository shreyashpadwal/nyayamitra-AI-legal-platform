import json
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.database import get_db
from ...db.models import User, SimilaritySearch, CaseMetadata
from ...core.auth import get_current_user, require_lawyer
from ...schemas.schemas import SimilarityRequest
from ...services.vector_service import vector_service

router = APIRouter(tags=["Lawyer - Case Similarity"])

@router.post("/similar-cases")
def similar_cases(body: SimilarityRequest, current_user: User = Depends(require_lawyer), db: Session = Depends(get_db)):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")
    
    cases = vector_service.find_similar_cases(body.query, k=body.k)
    
    # Ensure PDF links are properly mapped for the frontend
    for case in cases:
        if case.get("pdf_path"):
            filename = os.path.basename(case["pdf_path"])
            case["link"] = f"/data/judgments/{filename}"
        elif case.get("link") == "N/A":
            case["link"] = None

    strategy = None
    if body.include_strategy:
        strategy = vector_service.get_litigation_strategy(body.query, cases)
    
    db.add(SimilaritySearch(
        user_id=current_user.id,
        query=body.query,
        results_json=json.dumps(cases)
    ))
    db.commit()
    return {"query": body.query, "cases": cases, "strategy": strategy}

@router.get("/cases")
def list_cases(current_user: User = Depends(require_lawyer), db: Session = Depends(get_db)):
    cases = db.query(CaseMetadata).all()
    results = []
    for c in cases:
        link = c.link
        if c.pdf_path:
            filename = os.path.basename(c.pdf_path)
            link = f"/data/judgments/{filename}"
        
        if link == "N/A":
            link = None
            
        results.append({
            "id": c.id,
            "case_name": c.case_name,
            "year": c.year,
            "case_type": c.case_type,
            "pdf_path": c.pdf_path,
            "link": link
        })
    return results

@router.get("/history")
def get_search_history(current_user: User = Depends(require_lawyer), db: Session = Depends(get_db)):
    history = db.query(SimilaritySearch).filter(SimilaritySearch.user_id == current_user.id).all()
    # Fix links in results_json for old search results
    for item in history:
        if item.results_json:
            try:
                results = json.loads(item.results_json)
                fixed = False
                for case in results:
                    if case.get("link") == "N/A" and case.get("pdf_path"):
                        filename = os.path.basename(case["pdf_path"])
                        case["link"] = f"/data/judgments/{filename}"
                        fixed = True
                    elif case.get("link") == "N/A":
                        case["link"] = None
                        fixed = True
                if fixed:
                    item.results_json = json.dumps(results) # Don't commit yet to avoid heavy DB writes, but it serves correctly
            except:
                continue
    return history

@router.post("/ask-case")
def ask_case_specific(body: dict, current_user: User = Depends(require_lawyer)):
    question = body.get("question")
    case_name = body.get("case_name")
    if not question or not case_name:
        raise HTTPException(status_code=400, detail="Missing question or case_name")
    
    answer = vector_service.get_case_specific_answer(question, case_name)
    return {"answer": answer}
