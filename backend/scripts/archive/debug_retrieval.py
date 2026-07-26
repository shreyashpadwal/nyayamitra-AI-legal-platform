"""
Quick diagnostic: show exactly which chunks the hybrid retriever
returns for the arrest-rights query, before reranking.
This tells us whether Article 22 + Section 49 are in the top-8 pool.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.services.vector_service import _get_citizen_retriever

QUERY = "What are my rights if police arrest me?"

retriever = _get_citizen_retriever()
results = retriever.retrieve_with_scores(QUERY, k=10)

print("=" * 70)
print(f"  RETRIEVAL DEBUG — top-10 hybrid RRF results")
print(f"  Query: '{QUERY}'")
print("=" * 70)
for rank, (doc, score) in enumerate(results, 1):
    law  = doc.metadata.get("law_name", "?")
    page = doc.metadata.get("page", "?")
    sec  = doc.metadata.get("section", "")
    supp = " [SUPP]" if doc.metadata.get("supplementary") else ""
    snip = doc.page_content[:120].replace("\n", " ")
    print(f"\n  [{rank}] {law} | p{page}{' | §'+sec if sec else ''}{supp} | RRF={score:.5f}")
    print(f"      {snip}...")
print("\n" + "=" * 70)
