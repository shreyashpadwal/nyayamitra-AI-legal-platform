import json
import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ...db.database import get_db
from ...db.models import User, SimilaritySearch, CaseMetadata
from ...core.auth import get_current_user, require_lawyer
from ...schemas.schemas import SimilarityRequest
from ...services.vector_service import vector_service

router = APIRouter(tags=["Lawyer - Case Similarity"])

# ---------------------------------------------------------------------------
# Stage messages for the streaming endpoint
# Each key maps to a node name emitted by LangGraph's .stream() (or a
# synthetic stage name used by the thread below).
# ---------------------------------------------------------------------------
STAGE_MESSAGES = {
    "query_rewrite":       "🔍 Analysing and refining your query...",
    "hybrid_retrieve":     "📚 Searching case database...",
    "rerank":              "⚖️ Ranking most relevant precedents...",
    "evaluate_relevance":  "🧐 Evaluating precedent relevance...",
    "knowledge_refine":    "🔬 Distilling key legal insights...",
    "generate_strategy":   "✍️ Drafting litigation strategy...",
    "hallucination_check": "🔎 Verifying case citations...",
    "revise_strategy":     "📝 Refining strategy for accuracy...",
    "incorrect_result":    "⚠️ No strong precedents found — generating best-effort response...",
    # Synthetic stages used when the pipeline returns without streaming
    "saving":              "💾 Saving results...",
    "done":                "✅ Done!",
}


def _fix_links(cases: list) -> list:
    """Normalise PDF link fields on a list of case dicts (in-place + return)."""
    for case in cases:
        if case.get("pdf_path"):
            filename = os.path.basename(case["pdf_path"])
            case["link"] = f"/data/judgments/{filename}"
        elif case.get("link") == "N/A":
            case["link"] = None
    return cases


# ---------------------------------------------------------------------------
# Existing non-streaming endpoint (fallback / history re-runs)
# ---------------------------------------------------------------------------

@router.post("/similar-cases")
def similar_cases(body: SimilarityRequest, current_user: User = Depends(require_lawyer), db: Session = Depends(get_db)):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    cases = vector_service.find_similar_cases(body.query, k=body.k)
    _fix_links(cases)

    strategy = None
    if body.include_strategy:
        strategy = vector_service.get_litigation_strategy(body.query, cases)

    db.add(SimilaritySearch(
        user_id=current_user.id,
        query=body.query,
        results_json=json.dumps(cases),
        strategy_text=strategy or None,
    ))
    db.commit()
    return {"query": body.query, "cases": cases, "strategy": strategy}


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/similar-cases-stream")
async def similar_cases_stream(
    request: Request,
    body: SimilarityRequest,
    current_user: User = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """
    SSE endpoint that emits live status messages while the lawyer pipeline runs,
    then emits the final result.

    SSE event format:
        data: {"type": "status", "message": "...human-readable stage text..."}\n\n
        data: {"type": "result", "cases": [...], "strategy": "..."}\n\n
        data: {"type": "error",  "message": "..."}\n\n
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    async def event_generator():
        try:
            # Run the blocking pipeline in a thread so we don't block the event loop
            loop = asyncio.get_event_loop()

            # We'll use the LangGraph .stream() interface in a thread.
            # stream() yields dicts keyed by node name as each node completes.
            # We translate node names → friendly messages via STAGE_MESSAGES.
            from ...services.lawyer_graph import get_lawyer_graph  # noqa: PLC0415

            # Build initial state
            initial_state = {
                "query": body.query,
                "rewritten_query": "",
                "retrieved_docs": [],
                "reranked_docs": [],
                "relevance_verdict": "",
                "refined_docs": [],
                "strategy": "",
                "hallucination_status": "",
                "cases": [],
                "pipeline_log": [],
                "revision_done": False,
            }

            graph = get_lawyer_graph()

            # Stream node updates.  Each item is {node_name: state_delta}.
            # We run this synchronously in a thread and push events via a queue.
            import queue as _queue  # noqa: PLC0415
            event_q: _queue.Queue = _queue.Queue()

            def _run_stream():
                try:
                    for chunk in graph.stream(initial_state):
                        for node_name in chunk:
                            event_q.put(("status", node_name, chunk[node_name]))
                    event_q.put(("done", None, None))
                except Exception as exc:
                    event_q.put(("error", str(exc), None))

            import threading  # noqa: PLC0415
            t = threading.Thread(target=_run_stream, daemon=True)
            t.start()

            # Drain the queue and yield SSE events
            final_state = {}
            while True:
                await asyncio.sleep(0.05)  # yield control every 50 ms
                try:
                    kind, payload, state_delta = event_q.get_nowait()
                except _queue.Empty:
                    continue

                if kind == "status":
                    node_name = payload
                    msg = STAGE_MESSAGES.get(node_name, f"Processing {node_name}...")
                    yield f"data: {json.dumps({'type': 'status', 'message': msg})}\n\n"
                    if state_delta:
                        final_state.update(state_delta)

                elif kind == "done":
                    break

                elif kind == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': payload})}\n\n"
                    return

            t.join(timeout=5)

            # --- Post-process result ---
            import re as _re  # noqa: PLC0415
            strategy = final_state.get("strategy", "")
            _NOTE_RE = _re.compile(r"\(?Note\s*:\s*[Tt]he\s+fabricated\b.*?(?:\n|$)", _re.IGNORECASE | _re.DOTALL)
            strategy = _NOTE_RE.sub("", strategy).strip()

            cases = final_state.get("cases", [])
            _fix_links(cases)

            # Trim to requested k
            cases = cases[:body.k]

            # If no strategy in graph result and user requested it, generate via fallback
            if body.include_strategy and not strategy:
                yield f"data: {json.dumps({'type': 'status', 'message': STAGE_MESSAGES['generate_strategy']})}\n\n"
                strategy = await loop.run_in_executor(
                    None, vector_service.get_litigation_strategy, body.query, cases
                )

            # Save to DB
            yield f"data: {json.dumps({'type': 'status', 'message': STAGE_MESSAGES['saving']})}\n\n"
            try:
                db.add(SimilaritySearch(
                    user_id=current_user.id,
                    query=body.query,
                    results_json=json.dumps(cases),
                    strategy_text=strategy or None,
                ))
                db.commit()
            except Exception:
                db.rollback()

            # Final result
            yield f"data: {json.dumps({'type': 'result', 'cases': cases, 'strategy': strategy or ''})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


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
    history = db.query(SimilaritySearch).filter(SimilaritySearch.user_id == current_user.id).order_by(SimilaritySearch.timestamp.desc()).all()

    # Fix links in results_json for old search results
    out = []
    for item in history:
        results_parsed = []
        if item.results_json:
            try:
                results_parsed = json.loads(item.results_json)
                for case in results_parsed:
                    if case.get("link") == "N/A" and case.get("pdf_path"):
                        filename = os.path.basename(case["pdf_path"])
                        case["link"] = f"/data/judgments/{filename}"
                    elif case.get("link") == "N/A":
                        case["link"] = None
            except Exception:
                results_parsed = []
        out.append({
            "id":            item.id,
            "query":         item.query,
            "results_json":  json.dumps(results_parsed),
            "strategy_text": item.strategy_text,   # None for pre-fix rows
            "timestamp":     item.timestamp.isoformat() if item.timestamp else None,
        })
    return out

@router.delete("/history/{item_id}", status_code=200)
def delete_search_history_item(item_id: int, current_user: User = Depends(require_lawyer), db: Session = Depends(get_db)):
    record = db.query(SimilaritySearch).filter(
        SimilaritySearch.id == item_id,
        SimilaritySearch.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(record)
    db.commit()
    return {"success": True, "deleted_id": item_id}
