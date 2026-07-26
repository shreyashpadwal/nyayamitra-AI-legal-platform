"""
Item 1 diagnostic: Find the exact chunk cited as "Indian Penal Code, Page 96"
in the theft-punishment answer. Print full raw text and metadata.

Also scan nearby pages (94-98) to show full neighbourhood context.

Usage: cd backend && python -m scripts.diag_gujarat_theft
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.services.vector_service import _get_citizen_vs

vs = _get_citizen_vs()
docstore   = vs.docstore
index_to_id = vs.index_to_docstore_id

print("=" * 70)
print("  ITEM 1 DIAGNOSTIC — IPC Page 96 chunk(s)")
print("=" * 70)

TARGET_LAW   = "indian penal code"
TARGET_PAGES = range(93, 100)   # pages 93-99 to get full neighbourhood

hits = []
for idx in sorted(index_to_id.keys()):
    doc_id = index_to_id[idx]
    doc    = docstore.search(doc_id)
    if doc is None:
        continue
    law  = doc.metadata.get("law_name", "").lower()
    page = doc.metadata.get("page", -1)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = -1

    if TARGET_LAW in law and page in TARGET_PAGES:
        hits.append((page, idx, doc))

hits.sort(key=lambda x: x[0])

print(f"\nFound {len(hits)} IPC chunk(s) on pages 93-99:\n")
for page, idx, doc in hits:
    meta = doc.metadata
    print(f"\n{'─'*60}")
    print(f"  law_name : {meta.get('law_name')}")
    print(f"  page     : {meta.get('page')}")
    print(f"  section  : {meta.get('section', 'N/A')}")
    print(f"  FAISS idx: {idx}")
    print(f"\n  FULL RAW TEXT ({len(doc.page_content)} chars):")
    print("  " + doc.page_content.replace("\n", "\n  "))

# Also run a similarity search for "Gujarat theft punishment" to see what
# the LLM actually retrieved during the theft query
print(f"\n\n{'='*70}")
print("  SIMILARITY SEARCH — 'punishment theft Gujarat Act 6 2019 IPC 379'")
print("=" * 70)
results = vs.similarity_search_with_score(
    "punishment theft Gujarat Act 6 2019 IPC section 379", k=5
)
for doc, score in results:
    law  = doc.metadata.get("law_name", "?")
    page = doc.metadata.get("page", "?")
    sec  = doc.metadata.get("section", "")
    snip = doc.page_content[:200].replace("\n", " ")
    print(f"\n  [{law} | p{page}{' | §'+sec if sec else ''} | dist={score:.4f}]")
    print(f"  {snip}...")

print("\n" + "=" * 70)
