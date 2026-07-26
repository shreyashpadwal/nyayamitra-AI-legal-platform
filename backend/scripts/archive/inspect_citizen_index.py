"""
inspect_citizen_index.py
------------------------
Diagnostic script — READ ONLY, no writes to the index.

What it checks
--------------
1. Loads the citizen FAISS vectorstore from backend/data/vectors/citizen/
   using the exact same call as vector_service.load_vectorstore().

2. Searches all documents for chunks containing "379" or "theft"
   (case-insensitive) and prints content + full metadata for each hit.

3. Prints a full law_name distribution (chunk count per unique law_name)
   to surface any broad mislabeling pattern.

4. For each law_name, prints the page-number distribution so we can spot
   off-by-one ingestion bugs (e.g. IPC pages tagged as CrPC).

Usage
-----
    cd backend
    python -m scripts.inspect_citizen_index
"""

import os
import sys
import io
import re

# Force UTF-8 stdout so Unicode in law_name values doesn't crash on Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from collections import Counter, defaultdict

# ── path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── paths (match vector_service.py exactly) ───────────────────────────────────
APP_DIR           = os.path.join(BACKEND_DIR, "app")
CITIZEN_FAISS_DIR = os.path.join(BACKEND_DIR, "data", "vectors", "citizen")

SEARCH_TERMS = ["379", "380", "theft"]   # look for IPC theft sections


def load_vectorstore(path: str, index_name: str = "index"):
    """Identical to vector_service.load_vectorstore()."""
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import SentenceTransformerEmbeddings

    if not os.path.exists(path) or not os.listdir(path):
        raise FileNotFoundError(f"Vectorstore not found at {path}")

    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    return FAISS.load_local(
        path,
        embeddings,
        allow_dangerous_deserialization=True,
        index_name=index_name,
    )


def hr(char="-", width=72):
    print(char * width)


def main():
    print()
    hr("=")
    print("  NyayaMitra - Citizen Index Diagnostic")
    print(f"  Index path : {CITIZEN_FAISS_DIR}")
    hr("=")

    # -- 1. Load ---------------------------------------------------------------
    print("\nLoading vectorstore ...")
    vs = load_vectorstore(CITIZEN_FAISS_DIR)
    all_docs = list(vs.docstore._dict.values())
    total    = len(all_docs)
    print(f"Total chunks in docstore: {total}")

    # -- 2. Search for theft / 379 / 380 --------------------------------------
    hr()
    pattern = re.compile("|".join(SEARCH_TERMS), re.IGNORECASE)
    hits    = [doc for doc in all_docs if pattern.search(doc.page_content)]

    print(f"\nChunks matching {SEARCH_TERMS}: {len(hits)}\n")

    for i, doc in enumerate(hits, 1):
        meta    = doc.metadata
        snippet = doc.page_content[:300].replace("\n", " ")
        print(f"  [{i}] law_name : {meta.get('law_name', '<missing>')}")
        print(f"       page     : {meta.get('page', '<missing>')}")
        print(f"       source   : {meta.get('source', '<missing>')}")
        print(f"       metadata : {meta}")
        print(f"       content  : {snippet!r}")
        print()

    # -- 3. Law-name distribution (all chunks) ---------------------------------
    hr()
    law_counter: Counter = Counter()
    pages_by_law: defaultdict = defaultdict(list)

    for doc in all_docs:
        law  = doc.metadata.get("law_name", "<missing>")
        page = doc.metadata.get("page", None)
        law_counter[law] += 1
        if page is not None:
            try:
                pages_by_law[law].append(int(page))
            except (ValueError, TypeError):
                pages_by_law[law].append(str(page))

    print("\nlaw_name distribution (all chunks):\n")
    for law, count in law_counter.most_common():
        print(f"  {count:>5}  chunks  -  {law!r}")

    # -- 4. Page-number range per law ------------------------------------------
    hr()
    print("\nPage-number range per law_name:\n")
    for law, pages in sorted(pages_by_law.items()):
        int_pages = [p for p in pages if isinstance(p, int)]
        if int_pages:
            print(
                f"  {law!r:40s}  "
                f"pages {min(int_pages):>4} - {max(int_pages):<4}  "
                f"({len(int_pages)} chunks)"
            )
        else:
            print(f"  {law!r:40s}  (no integer page numbers, {len(pages)} chunks)")

    # -- 5. Check for CrPC chunks containing IPC section numbers ---------------
    hr()
    ipc_pattern = re.compile(r"\b(37[0-9]|38[0-9]|302|420|498)\b")
    crpc_chunks_with_ipc_refs = [
        doc for doc in all_docs
        if str(doc.metadata.get("law_name", "")).lower() in ("crpc act", "crpc", "cr.p.c")
        and ipc_pattern.search(doc.page_content)
    ]
    print(
        f"\nCrPC-tagged chunks that reference IPC section numbers "
        f"(302/379/380/420/498/etc.): {len(crpc_chunks_with_ipc_refs)}"
    )
    for doc in crpc_chunks_with_ipc_refs[:5]:   # show up to 5
        print(f"  page={doc.metadata.get('page')}  preview: "
              f"{doc.page_content[:200].replace(chr(10),' ')!r}")

    # -- 6. Check for IPC chunks containing CrPC procedure references ----------
    crpc_pattern = re.compile(r"\b(section\s+1[56][0-9]|cognizable|FIR|bailable)\b", re.IGNORECASE)
    ipc_chunks_with_crpc_refs = [
        doc for doc in all_docs
        if str(doc.metadata.get("law_name", "")).lower() in ("indian penal code", "ipc")
        and crpc_pattern.search(doc.page_content)
    ]
    print(
        f"\nIPC-tagged chunks that contain CrPC-like procedure language "
        f"(FIR/cognizable/bailable): {len(ipc_chunks_with_crpc_refs)}"
    )
    for doc in ipc_chunks_with_crpc_refs[:5]:
        print(f"  page={doc.metadata.get('page')}  preview: "
              f"{doc.page_content[:200].replace(chr(10),' ')!r}")

    # -- 7. Spot-check: what law_name do sections 379/380 chunks carry? ---------
    hr()
    print("\nSummary: law_name assigned to chunks mentioning 'Section 379' or 'Section 380':\n")
    sec_pattern = re.compile(r"Section\s+3[78][0-9]", re.IGNORECASE)
    sec_hits = [doc for doc in all_docs if sec_pattern.search(doc.page_content)]
    sec_law_counter: Counter = Counter(
        doc.metadata.get("law_name", "<missing>") for doc in sec_hits
    )
    for law, count in sec_law_counter.most_common():
        print(f"  {count:>4}  chunks  -  {law!r}")

    hr("=")
    print("")
    print("Diagnostic complete. No changes were made to the index.")
    print("")


if __name__ == "__main__":
    main()
