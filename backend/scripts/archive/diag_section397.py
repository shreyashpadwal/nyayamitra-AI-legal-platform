"""
diag_section397.py — Probe whether Section 397 chunks exist in the vectorstore
and why they don't surface for weapon-related robbery queries.

Usage: cd backend && python -m scripts.diag_section397
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.vector_service import _get_citizen_vectorstore
from app.services.citizen_graph import _detect_target_statute

vs = _get_citizen_vectorstore()

print("=" * 68)
print("  diag_section397.py — §397 vectorstore probe")
print("=" * 68)

# 1. Text-scan for §397 in top-50 IPC docs by semantic search
print("\n--- Semantic searches most likely to surface §397 ---")
probe_queries = [
    "robbery with deadly weapon dacoity grievous hurt death",
    "Section 397 robbery dacoity",
    "weapon used in robbery punishment",
    "armed robbery deadly weapon IPC",
]
for q in probe_queries:
    results = vs.similarity_search(q, k=8, filter={"law_name": "Indian Penal Code"})
    has_397 = [d for d in results if "397" in d.page_content]
    print(f"\nQuery: {q!r}")
    print(f"  k=8 IPC results | §397 present in {len(has_397)} docs")
    for d in results[:5]:
        m = d.metadata
        flag = " *** §397 ***" if "397" in d.page_content else ""
        print(f"    page_label={m.get('page_label')}  text={d.page_content[:80].replace(chr(10),' ')!r}{flag}")

# 2. Broad scan for any chunk containing "397"
print("\n--- Broad scan: ANY IPC chunk containing '397' ---")
broad = vs.similarity_search("robbery dacoity weapon hurt death IPC", k=50,
                             filter={"law_name": "Indian Penal Code"})
hits = [d for d in broad if "397" in d.page_content]
print(f"Found {len(hits)} chunks with '397' in top-50:")
for d in hits:
    m = d.metadata
    print(f"  page_label={m.get('page_label')}  text={d.page_content[:160].replace(chr(10),' ')!r}")

# 3. Detection check for the original 3-clause query
q3 = "What is the punishment for theft, how does it differ for robbery, and what if a weapon is used?"
print(f"\n--- _detect_target_statute for 3-clause query ---")
print(f"  query: {q3!r}")
print(f"  result: {_detect_target_statute(q3)!r}")
print()
