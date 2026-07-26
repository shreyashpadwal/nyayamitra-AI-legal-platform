"""
Item 4 diagnostic: Run Q4 and Q5 (near-identical product-defect queries)
through the hybrid retriever and reranker back-to-back.
Log retrieved chunks, rerank scores, and final top_k for each.

Q4: "What to do if a product is defective?"
Q5: "What to do if a product I bought is defective?"

Usage: cd backend && python -m scripts.diag_q4_q5
"""
import sys, io, time, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(level=logging.WARNING)

from app.services.vector_service import _get_citizen_retriever, _get_reranker

retriever = _get_citizen_retriever()
reranker  = _get_reranker()

QUERIES = {
    "Q4": "What to do if a product is defective?",
    "Q5": "What to do if a product I bought is defective?",
}

print("=" * 70)
print("  ITEM 4 DIAGNOSTIC — Q4 vs Q5 retrieval instability")
print("=" * 70)

results_by_q = {}

for label, query in QUERIES.items():
    print(f"\n{'─'*70}")
    print(f"  {label}: '{query}'")
    print(f"{'─'*70}")

    # Step 1: Hybrid retrieval (k=12)
    hybrid = retriever.retrieve_with_scores(query, k=12)
    print(f"\n  [HYBRID top-12 by RRF score]")
    for rank, (doc, score) in enumerate(hybrid, 1):
        law  = doc.metadata.get("law_name", "?")
        page = doc.metadata.get("page", "?")
        sec  = doc.metadata.get("section", "")
        snip = doc.page_content[:100].replace("\n", " ")
        print(f"    [{rank:2d}] RRF={score:.5f} | {law} p{page}{' §'+sec if sec else ''}")
        print(f"         {snip}...")

    # Step 2: Rerank
    hybrid_docs = [doc for doc, _ in hybrid]
    reranked = reranker.rerank(query, hybrid_docs, top_k=len(hybrid_docs))

    print(f"\n  [RERANKER scores — all {len(reranked)} docs]")
    for rank, (doc, score) in enumerate(reranked, 1):
        law  = doc.metadata.get("law_name", "?")
        page = doc.metadata.get("page", "?")
        sec  = doc.metadata.get("section", "")
        passed = "✅ PASS" if score >= 0.3 else "❌ <0.3"
        snip = doc.page_content[:80].replace("\n", " ")
        print(f"    [{rank:2d}] score={score:+.4f} {passed} | {law} p{page}{' §'+sec if sec else ''}")
        print(f"         {snip}...")

    # Step 3: What survives threshold (these reach the LLM)
    survivors = [(d, s) for d, s in reranked if s >= 0.3]
    print(f"\n  [SURVIVORS (score >= 0.3) → reach LLM: {len(survivors)} doc(s)]")
    for doc, score in survivors:
        law  = doc.metadata.get("law_name", "?")
        page = doc.metadata.get("page", "?")
        sec  = doc.metadata.get("section", "")
        print(f"    score={score:+.4f} | {law} p{page}{' §'+sec if sec else ''}")

    results_by_q[label] = {
        "hybrid": [(d.metadata.get("law_name","?"), d.metadata.get("page","?"),
                    d.metadata.get("section",""), s) for d, s in hybrid],
        "survivors": [(d.metadata.get("law_name","?"), d.metadata.get("page","?"),
                       d.metadata.get("section",""), s) for d, s in survivors],
    }

print(f"\n\n{'='*70}")
print("  OVERLAP ANALYSIS")
print("=" * 70)

def key(law, page, sec): return f"{law}|p{page}|{sec}"

q4_hybrid  = {key(*x[:3]) for x in results_by_q["Q4"]["hybrid"]}
q5_hybrid  = {key(*x[:3]) for x in results_by_q["Q5"]["hybrid"]}
q4_surv    = {key(*x[:3]) for x in results_by_q["Q4"]["survivors"]}
q5_surv    = {key(*x[:3]) for x in results_by_q["Q5"]["survivors"]}

print(f"  Hybrid overlap   : {len(q4_hybrid & q5_hybrid)}/12 chunks shared")
print(f"  Survivor overlap : {len(q4_surv & q5_surv)} chunks shared")
print(f"\n  Q4-only hybrid   : {q4_hybrid - q5_hybrid}")
print(f"  Q5-only hybrid   : {q5_hybrid - q4_hybrid}")
print(f"\n  Q4-only survivors: {q4_surv - q5_surv}")
print(f"  Q5-only survivors: {q5_surv - q4_surv}")
print("\n" + "=" * 70)
