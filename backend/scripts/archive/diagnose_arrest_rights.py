"""
Diagnostic: search citizen FAISS index for arrest-rights content
that should appear in response to "What are my rights if police arrest me?"
but is currently missing: Section 50-A / D.K. Basu (right to inform family)
and Article 22(1) / Section 41-D (right to consult a lawyer).

For each term we do:
  1. Embedding similarity search (top-5) — shows whether semantically
     similar chunks exist in the index.
  2. Raw metadata scan — iterates all stored chunks and checks whether
     the exact string appears in chunk text for the target law_names.

Usage: cd backend && python -m scripts.diagnose_arrest_rights
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings

CITIZEN_INDEX = os.path.join("data", "vectors", "citizen")
TARGET_LAWS   = {"crpc act", "constitution of india"}

print("=" * 70)
print("  ARREST-RIGHTS DIAGNOSTIC — citizen FAISS index")
print("=" * 70)

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
vs = FAISS.load_local(CITIZEN_INDEX, embeddings, allow_dangerous_deserialization=True)

# ── 1. Raw scan across ALL stored documents ───────────────────────────────────
print("\n[1] RAW TEXT SCAN — searching all chunk texts for target strings")
print("    (law_name filter: crpc act | constitution of india)")
print("-" * 70)

SEARCH_TERMS = [
    "50-A", "50A", "50 A",
    "legal practitioner", "lawyer of his choice", "consult",
    "41-D", "41D", "D.K. Basu", "DK Basu",
    "Article 22(1)", "22(1)",
]

# Access the underlying docstore
docstore   = vs.docstore
index_to_id = vs.index_to_docstore_id   # dict {int → doc_id_str}

hits_by_term = {t: [] for t in SEARCH_TERMS}
total_chunks = len(index_to_id)
target_law_chunks = 0

for idx, doc_id in index_to_id.items():
    doc = docstore.search(doc_id)
    if doc is None:
        continue
    law = (doc.metadata.get("law_name") or "").strip().lower()
    if law not in TARGET_LAWS:
        continue
    target_law_chunks += 1
    text = doc.page_content or ""
    for term in SEARCH_TERMS:
        if term.lower() in text.lower():
            hits_by_term[term].append({
                "law" : doc.metadata.get("law_name"),
                "page": doc.metadata.get("page", "?"),
                "text": text[:200].replace("\n", " "),
            })

print(f"  Total chunks in index      : {total_chunks}")
print(f"  Chunks from target laws    : {target_law_chunks}")
print()

any_hit = False
for term, hits in hits_by_term.items():
    if hits:
        any_hit = True
        print(f"  FOUND '{term}' — {len(hits)} chunk(s):")
        for h in hits[:3]:   # show up to 3
            print(f"    [{h['law']} | page {h['page']}] {h['text'][:150]}...")
        print()
    else:
        print(f"  NOT FOUND: '{term}'")

if not any_hit:
    print("\n  >>> CONCLUSION: None of the target strings exist in the index")
    print("  >>> for the target law_names. This is a DOCUMENT COVERAGE gap.")
    print("  >>> Retrieval fixes will not help — source PDFs lack this content.")

# ── 2. Embedding similarity search ───────────────────────────────────────────
print("\n" + "=" * 70)
print("[2] EMBEDDING SIMILARITY SEARCH — top-5 chunks per query")
print("    (no law_name filter — checking if semantically close chunks exist)")
print("-" * 70)

QUERIES = [
    "right to inform family about arrest Section 50-A CrPC",
    "right to consult lawyer of choice arrested person Article 22",
    "Section 41-D legal practitioner arrested person",
    "D.K. Basu guidelines arrest rights",
]

for query in QUERIES:
    print(f"\n  Query: '{query}'")
    results = vs.similarity_search_with_score(query, k=5)
    if not results:
        print("    (no results)")
        continue
    for doc, score in results:
        law  = doc.metadata.get("law_name", "?")
        page = doc.metadata.get("page", "?")
        snippet = doc.page_content[:120].replace("\n", " ")
        print(f"    [{law} | p{page} | dist={score:.4f}] {snippet}...")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
