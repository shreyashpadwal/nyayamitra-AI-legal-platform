"""
diag_compound_query.py — Compound-query retrieval diagnostic.

PURPOSE
-------
Traces how a compound/multi-clause query flows through the citizen RAG
pipeline's retrieval stages, so that future regressions can be quickly
located at the correct stage (hybrid BM25+FAISS, statute boost, reranker,
or statute filter) rather than requiring full end-to-end debugging.

HOW TO RUN
----------
  cd backend
  python -m scripts.diag_compound_query

ARCHITECTURE NOTE — updated to reflect production code
-------------------------------------------------------
This script now calls the ACTUAL hybrid_retrieve_node() and rerank_node()
functions from citizen_graph.py directly (by constructing a fake state dict)
so that results here always mirror what the live /citizen/ask-stream endpoint
produces.  Earlier versions (before 2026-07-24) manually reimplemented the
boost logic inline, which caused them to fall behind the production code.

If you update hybrid_retrieve_node or rerank_node, this script stays
accurate automatically — no manual sync required.
"""

import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.citizen_graph import (
    hybrid_retrieve_node,
    rerank_node,
    _detect_target_statute,
    _is_compound_query,
)

# ── Queries to diagnose ─────────────────────────────────────────────────────
QUERIES: list[tuple[str, str]] = [
    # (label, query_text)
    ("CONTROL  ", "What is the punishment for theft in IPC?"),
    ("ORIGINAL ", "What is the punishment for theft, and does it differ if it happens in someone's house?"),
]


def label(doc) -> str:
    m = doc.metadata
    chunk50 = doc.page_content[:50].replace("\n", " ")
    return (
        f"  law={m.get('law_name','?')!r}  "
        f"page_label={m.get('page_label','?')}  "
        f"page={m.get('page','?')}  "
        f"chunk50={chunk50!r}"
    )


def has_section(docs: list, section: str) -> bool:
    return any(section in d.page_content for d in docs)


print("=" * 72)
print("  diag_compound_query — citizen RAG retrieval diagnostic")
print("=" * 72)

for run_label, original_query in QUERIES:
    print()
    print("=" * 72)
    print(f"QUERY [{run_label}]: {original_query}")
    print("=" * 72)

    print(f"\n[Stage 0] _detect_target_statute => {_detect_target_statute(original_query)!r}")
    print(f"[Stage 0] _is_compound_query     => {_is_compound_query(original_query)}")

    # ── Stage 1: Call actual hybrid_retrieve_node ────────────────────────
    # Build the minimal state dict expected by the node function.
    # rewritten_query is intentionally blank so the node falls back to
    # original_query (same as production when query_rewrite_node is skipped).
    state_in = {
        "original_query":   original_query,
        "rewritten_query":  "",
        "retrieved_docs":   [],
        "reranked_docs":    [],
        "relevant_docs":    [],
        "pipeline_log":     [],
        "sources":          [],
    }

    hybrid_state = hybrid_retrieve_node(state_in)
    retrieved = hybrid_state.get("retrieved_docs", [])

    print(f"\n[Stage 1] hybrid_retrieve_node: {len(retrieved)} docs")
    for i, d in enumerate(retrieved, 1):
        print(f"  #{i}{label(d)}")

    # ── Stage 2: Call actual rerank_node ─────────────────────────────────
    state_after_retrieve = {**state_in, **hybrid_state}
    rerank_state = rerank_node(state_after_retrieve)
    reranked = rerank_state.get("reranked_docs", [])

    print(f"\n[Stage 2] rerank_node: {len(reranked)} docs after cross-encoder + threshold")
    for i, d in enumerate(reranked, 1):
        print(f"  #{i}{label(d)}")

    # ── Coverage check ────────────────────────────────────────────────────
    print("\n[Coverage check]")
    print(f"  Stage 1 hybrid+boost : §379={'YES' if has_section(retrieved, '379') else 'NO ':3}  "
          f"§380={'YES' if has_section(retrieved, '380') else 'NO '}")
    print(f"  Stage 2 reranked     : §379={'YES' if has_section(reranked, '379') else 'NO ':3}  "
          f"§380={'YES' if has_section(reranked, '380') else 'NO '}")

print("\nDONE.")
