"""
Item 2 diagnostic: Retrieval consistency across 8 semantically-equivalent
question pairs covering diverse Acts. For each pair, measure chunk-set
overlap between the two phrasings at both hybrid and survivor levels.

Identifies whether retrieval instability is query-specific or systemic
across the embedding model / hybrid fusion / chunking strategy.

Usage: cd backend && python -m scripts.diag_retrieval_consistency
"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

from app.services.vector_service import _get_citizen_retriever, _get_reranker

retriever = _get_citizen_retriever()
reranker  = _get_reranker()

# 8 pairs covering IPC, CrPC, RTI, CPA, Constitution — diverse Acts
PAIRS = [
    {
        "id": "P1",
        "act": "IPC",
        "q_a": "What is the punishment for theft under IPC?",
        "q_b": "What happens if someone commits theft in India?",
    },
    {
        "id": "P2",
        "act": "IPC",
        "q_a": "What is Section 302 IPC punishment for murder?",
        "q_b": "How many years imprisonment for killing someone under Indian Penal Code?",
    },
    {
        "id": "P3",
        "act": "RTI",
        "q_a": "How do I file an RTI application?",
        "q_b": "What is the process to get information from a government office?",
    },
    {
        "id": "P4",
        "act": "RTI",
        "q_a": "How many days does the government have to reply to RTI?",
        "q_b": "What is the time limit for PIO to respond to an RTI request?",
    },
    {
        "id": "P5",
        "act": "CPA",
        "q_a": "What to do if a product is defective?",
        "q_b": "What to do if a product I bought is defective?",
    },
    {
        "id": "P6",
        "act": "CPA",
        "q_a": "What are my rights as a consumer if I am cheated by a seller?",
        "q_b": "Can I sue a shopkeeper for selling me a fake product?",
    },
    {
        "id": "P7",
        "act": "Constitution",
        "q_a": "What are my fundamental rights under the Indian Constitution?",
        "q_b": "What rights does the Constitution of India guarantee to citizens?",
    },
    {
        "id": "P8",
        "act": "CrPC",
        "q_a": "What are my rights if police arrest me without warrant?",
        "q_b": "What should I do if I am illegally arrested by police?",
    },
]

K = 12  # hybrid retrieval pool size
TOP_K = 5  # reranker survivors

print("=" * 70)
print(f"  ITEM 2 — Retrieval consistency across {len(PAIRS)} semantically-equivalent pairs")
print(f"  hybrid k={K}, reranker top_k={TOP_K}, threshold=0.3")
print("=" * 70)

def chunk_key(doc):
    m = doc.metadata
    return f"{m.get('law_name','?')}|p{m.get('page','?')}|{m.get('section','')}"

def retrieve_and_rerank(query):
    hybrid = retriever.retrieve_with_scores(query, k=K)
    docs   = [d for d, _ in hybrid]
    ranked = reranker.rerank(query, docs, top_k=TOP_K)
    hybrid_keys = {chunk_key(d) for d, _ in hybrid}
    # Use all top_k results from reranker as the comparison set
    top_keys    = {chunk_key(d) for d, _ in ranked}
    return hybrid_keys, top_keys


pair_results = []
for pair in PAIRS:
    print(f"\n{'─'*70}")
    print(f"  [{pair['id']}] Act: {pair['act']}")
    print(f"  A: '{pair['q_a']}'")
    print(f"  B: '{pair['q_b']}'")

    hybrid_a, top_a = retrieve_and_rerank(pair["q_a"])
    hybrid_b, top_b = retrieve_and_rerank(pair["q_b"])

    hybrid_overlap  = len(hybrid_a & hybrid_b)
    top_overlap     = len(top_a & top_b)
    hybrid_jaccard  = hybrid_overlap / len(hybrid_a | hybrid_b) if (hybrid_a | hybrid_b) else 0
    top_jaccard     = top_overlap / len(top_a | top_b) if (top_a | top_b) else 0

    a_only_top = top_a - top_b
    b_only_top = top_b - top_a

    stability = "🟢 STABLE" if top_jaccard >= 0.6 else ("🟡 PARTIAL" if top_jaccard >= 0.3 else "🔴 UNSTABLE")

    print(f"\n  Hybrid overlap:   {hybrid_overlap}/{K} chunks  (Jaccard={hybrid_jaccard:.2f})")
    print(f"  Top-{TOP_K} overlap:   {top_overlap}/{TOP_K} chunks  (Jaccard={top_jaccard:.2f})  {stability}")
    if a_only_top:
        print(f"  A-only top-{TOP_K}:   {a_only_top}")
    if b_only_top:
        print(f"  B-only top-{TOP_K}:   {b_only_top}")

    pair_results.append({
        "id": pair["id"],
        "act": pair["act"],
        "hybrid_jaccard": round(hybrid_jaccard, 2),
        "top_jaccard": round(top_jaccard, 2),
        "stability": stability,
    })

print(f"\n\n{'='*70}")
print("  SUMMARY TABLE")
print("=" * 70)
print(f"  {'ID':4} {'Act':12} {'HybridJ':8} {'Top-5J':8} {'Status'}")
print(f"  {'─'*4} {'─'*12} {'─'*8} {'─'*8} {'─'*10}")
unstable = []
for r in pair_results:
    print(f"  {r['id']:4} {r['act']:12} {r['hybrid_jaccard']:.2f}     {r['top_jaccard']:.2f}     {r['stability']}")
    if r["top_jaccard"] < 0.3:
        unstable.append(r["id"])

print(f"\n  Stable (Top-5 Jaccard ≥ 0.6): {sum(1 for r in pair_results if r['top_jaccard'] >= 0.6)}/{len(PAIRS)}")
print(f"  Partial (0.3–0.6):             {sum(1 for r in pair_results if 0.3 <= r['top_jaccard'] < 0.6)}/{len(PAIRS)}")
print(f"  Unstable (< 0.3):              {len(unstable)}/{len(PAIRS)}  {unstable}")

if len(unstable) >= 4:
    print("\n  FINDING: SYSTEMIC instability — affects ≥50% of pairs.")
    print("  Root cause likely: embedding model sensitivity + BM25 lexical mismatch.")
elif len(unstable) >= 2:
    print("\n  FINDING: PARTIAL instability — affects specific Acts, not universal.")
else:
    print("\n  FINDING: ISOLATED — instability is query-specific, not systemic.")
print("=" * 70)
