"""
diag_cheating_retrieval.py — Three-part diagnostic for Test A failure.

Checks:
  (a) Whether _TOPIC_PATTERNS has any keywords matching the query terms
  (b) Whether IPC cheating-provision chunks exist in the FAISS vectorstore at all
  (c) Traces the exact query through retrieval_decision -> hybrid_retrieve ->
      evaluate_relevance, logging doc counts and relevance scores at every stage

Usage: cd backend && python -m scripts.diag_cheating_retrieval
"""
import sys, io, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.citizen_graph import (
    _TOPIC_PATTERNS,
    _STATUTE_PATTERNS,
    _detect_target_statute,
    _is_compound_query,
    retrieval_decision_node,
    hybrid_retrieve_node,
    rerank_node,
    evaluate_relevance_node,
)
from app.services.vector_service import _get_citizen_vectorstore

QUERY = "My business partner cheated me out of money using fake documents, what can I do?"
KEYWORDS = ["cheat", "cheated", "fraud", "fake", "forged", "document", "415", "420"]

SEP = "=" * 72

print(SEP)
print("  diag_cheating_retrieval.py")
print(SEP)
print(f"\nQuery: {QUERY!r}\n")

# ─────────────────────────────────────────────────────────────────────────────
# (a) _TOPIC_PATTERNS keyword check
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("(a) _TOPIC_PATTERNS keyword coverage")
print(SEP)

q_lower = QUERY.lower()
matched_pattern = None
for kw in KEYWORDS:
    hits = []
    for i, (pat, law, excl) in enumerate(_TOPIC_PATTERNS):
        if re.search(re.escape(kw), pat.pattern, re.IGNORECASE):
            hits.append(f"  pattern[{i}] ({law}) contains {kw!r}")
    if hits:
        print(f"\nKeyword {kw!r} found in these patterns:")
        for h in hits: print(h)
    else:
        print(f"Keyword {kw!r} → NOT IN any _TOPIC_PATTERNS entry")

print()
print(f"_detect_target_statute(query) => {_detect_target_statute(QUERY)!r}")
print(f"_is_compound_query(query)     => {_is_compound_query(QUERY)}")

# Also show which TOPIC_PATTERNS the query itself matches
print("\nDirect pattern-match test against the query text:")
for i, (pat, law, excl) in enumerate(_TOPIC_PATTERNS):
    if pat.search(QUERY):
        if excl is None or not excl.search(QUERY):
            print(f"  MATCH: pattern[{i}] ({law}) — pattern={pat.pattern[:80]!r}")
        else:
            print(f"  MATCH (excluded): pattern[{i}] ({law}) excluded by excl={excl.pattern[:60]!r}")
    # else silent

# ─────────────────────────────────────────────────────────────────────────────
# (b) Direct FAISS vectorstore search
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("(b) Direct FAISS vectorstore searches")
print(SEP)

vs = _get_citizen_vectorstore()

search_terms = [
    ("cheating IPC", 6),
    ("Section 415 cheating dishonestly", 6),
    ("Section 420 cheating and dishonestly inducing", 6),
    ("fake documents fraud misrepresentation", 6),
    ("business partner fraud money", 6),
]

for term, k in search_terms:
    results = vs.similarity_search(term, k=k)
    ipc_results = [d for d in results if "Indian Penal Code" in d.metadata.get("law_name", "")]
    print(f"\nSearch: {term!r}  (k={k})")
    print(f"  Total results: {len(results)} | IPC results: {len(ipc_results)}")
    for d in ipc_results[:4]:
        m = d.metadata
        snippet = d.page_content[:120].replace("\n", " ")
        print(f"    page_label={m.get('page_label')}  law={m.get('law_name')!r}")
        print(f"    text: {snippet!r}")

# Text-based scan: which chunks contain "415" or "420" or "cheating"
print("\n--- Text-scan: chunks containing '415' or '420' ---")
all_docs = vs.similarity_search("cheating fraud deception dishonestly", k=30,
                                filter={"law_name": "Indian Penal Code"})
hits_415 = [d for d in all_docs if "415" in d.page_content]
hits_420 = [d for d in all_docs if "420" in d.page_content]
hits_cheat = [d for d in all_docs if "cheating" in d.page_content.lower()]
print(f"  Docs with '415': {len(hits_415)}")
print(f"  Docs with '420': {len(hits_420)}")
print(f"  Docs with 'cheating': {len(hits_cheat)}")
if hits_420:
    d = hits_420[0]
    print(f"  Sample §420 chunk (page_label={d.metadata.get('page_label')}):")
    print(f"    {d.page_content[:300].replace(chr(10), ' ')!r}")

# ─────────────────────────────────────────────────────────────────────────────
# (c) Full pipeline trace
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("(c) Pipeline trace: retrieval_decision -> hybrid_retrieve -> rerank -> evaluate_relevance")
print(SEP)

initial_state = {
    "original_query":   QUERY,
    "rewritten_query":  "",
    "needs_retrieval":  True,
    "is_legal_query":   True,
    "retrieved_docs":   [],
    "reranked_docs":    [],
    "relevant_docs":    [],
    "answer":           "",
    "hallucination_status": "",
    "is_useful":        False,
    "retry_count":      0,
    "rewrite_count":    0,
    "sources":          [],
    "pipeline_log":     [],
    "intent":           "general",
    "instruction":      "Provide a helpful legal answer.",
    "web_search_attempted": False,
}

# Step 1: retrieval_decision_node
print("\n[Step 1] retrieval_decision_node ...")
state1 = {**initial_state, **retrieval_decision_node(initial_state)}
print(f"  needs_retrieval  = {state1.get('needs_retrieval')}")
print(f"  is_legal_query   = {state1.get('is_legal_query')}")
print(f"  rewritten_query  = {state1.get('rewritten_query')!r}")
for e in state1.get("pipeline_log", []):
    if e.get("node") == "retrieval_decision":
        print(f"  elapsed          = {e.get('elapsed_s')}s")

# Step 2: hybrid_retrieve_node
print("\n[Step 2] hybrid_retrieve_node ...")
state2 = {**state1, **hybrid_retrieve_node(state1)}
retrieved = state2.get("retrieved_docs", [])
print(f"  retrieved {len(retrieved)} docs")
for i, d in enumerate(retrieved, 1):
    m = d.metadata
    snippet = d.page_content[:60].replace("\n", " ")
    cheat_flag = " *** HAS CHEATING ***" if any(kw in d.page_content.lower() for kw in ["cheating", "415", "420", "fraud"]) else ""
    print(f"  #{i:2d}  law={m.get('law_name')!r}  page_label={m.get('page_label')}  {snippet!r}{cheat_flag}")

# Step 3: rerank_node
print("\n[Step 3] rerank_node ...")
state3 = {**state2, **rerank_node(state2)}
reranked = state3.get("reranked_docs", [])
print(f"  reranked -> {len(reranked)} docs (after threshold + statute filter)")
for i, d in enumerate(reranked, 1):
    m = d.metadata
    snippet = d.page_content[:60].replace("\n", " ")
    cheat_flag = " *** HAS CHEATING ***" if any(kw in d.page_content.lower() for kw in ["cheating", "415", "420", "fraud"]) else ""
    print(f"  #{i:2d}  law={m.get('law_name')!r}  page_label={m.get('page_label')}  {snippet!r}{cheat_flag}")

# Step 4: evaluate_relevance_node
print("\n[Step 4] evaluate_relevance_node ...")
if reranked:
    state4 = {**state3, **evaluate_relevance_node(state3)}
    relevant = state4.get("relevant_docs", [])
    print(f"  relevant_docs: {len(relevant)} (threshold typically 0.4)")
    for d in relevant:
        m = d.metadata
        print(f"    law={m.get('law_name')!r}  page_label={m.get('page_label')}")
    for e in state4.get("pipeline_log", []):
        if e.get("node") == "evaluate_relevance":
            print(f"  elapsed: {e.get('elapsed_s')}s")
else:
    print("  SKIPPED — no docs in reranked pool")

print()
print(SEP)
print("DIAGNOSTIC DONE")
print(SEP)
