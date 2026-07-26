"""
Post-fix end-to-end test for the weapon/robbery compound query via the streaming endpoint.
Reads SSE chunks and assembles the final answer + sources.
Usage: cd backend && python -m scripts.test_weapon_query
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.citizen_graph import (
    retrieval_decision_node,
    hybrid_retrieve_node,
    rerank_node,
)

QUERY = "What is the punishment for theft, how does it differ for robbery, and what if a weapon is used?"

print("=" * 68)
print("  test_weapon_query.py — post-fix pipeline trace")
print(f"  Query: {QUERY}")
print("=" * 68)

initial_state = {
    "original_query": QUERY,
    "rewritten_query": "",
    "retrieved_docs": [],
    "reranked_docs": [],
    "relevant_docs": [],
    "answer": "",
    "sources": [],
    "hallucination_status": "",
    "web_search_attempted": False,
    "needs_retrieval": True,
    "is_legal_query": True,
    "rewrite_count": 0,
    "usefulness_retry_count": 0,
    "pipeline_log": [],
    "intent": "punishment",
    "instruction": "Explain punishments under IPC for theft, robbery, weapon use.",
}

print("\n[Step 1] retrieval_decision_node ...")
state = {**initial_state}
rd = retrieval_decision_node(state)
state.update(rd)
print(f"  rewritten_query = {state.get('rewritten_query', '')[:100]!r}")

print("\n[Step 2] hybrid_retrieve_node ...")
hr = hybrid_retrieve_node(state)
state.update(hr)
docs = state.get("retrieved_docs", [])
print(f"  retrieved {len(docs)} docs")
for i, d in enumerate(docs[:20], 1):
    flag = ""
    if "397" in d.page_content: flag += " *** §397 ***"
    if "deadly weapon" in d.page_content.lower(): flag += " *** DEADLY WPN ***"
    if any(x in d.page_content for x in ["theft", "robbery", "dacoity"]):
        flag += " [theft/rob]"
    print(f"  #{i:2d}  law={d.metadata.get('law_name')!r}  page={d.metadata.get('page_label')}  {d.page_content[:80].replace(chr(10),' ')!r}{flag}")

print("\n[Step 3] rerank_node ...")
rr_out = rerank_node(state)
state.update(rr_out)
reranked = state.get("reranked_docs", [])
print(f"  reranked -> {len(reranked)} docs")
for i, d in enumerate(reranked, 1):
    flag = ""
    if "397" in d.page_content: flag += " *** §397 ***"
    if "deadly weapon" in d.page_content.lower(): flag += " *** DEADLY WPN ***"
    print(f"  #{i}  law={d.metadata.get('law_name')!r}  page={d.metadata.get('page_label')}  {d.page_content[:100].replace(chr(10),' ')!r}{flag}")

print()
print("DIAGNOSTIC DONE")
print("=" * 68)
