"""
Step 2: Add three supplementary chunks to the citizen FAISS index for:
  - CrPC Section 41D  (right to meet advocate during interrogation)
  - CrPC Section 50A  (obligation to inform nominated person of arrest)
  - Constitution Article 22(1)  (right to consult and be defended by legal practitioner)

Source note: Texts obtained from search-engine grounding snippets cross-referencing
indiacode.nic.in, indiankanoon.org, kanoongpt.in, and devgan.in on 25 July 2026.
Neither indiacode.nic.in nor legislative.gov.in was reachable by direct static fetch
(JS-rendered / timeout). Provenance confidence is LOWER than the rest of the corpus.

Usage: cd backend && python -m scripts.add_arrest_rights_chunks
"""
import sys, io, os, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.documents import Document

CITIZEN_INDEX = os.path.join("data", "vectors", "citizen")
TODAY = datetime.date.today().isoformat()

SOURCE_NOTE = (
    f"Supplementary chunk added {TODAY}. Text sourced from search-engine grounding "
    "snippets cross-referencing indiacode.nic.in, indiankanoon.org, kanoongpt.in, "
    "and devgan.in. Direct static fetch of indiacode.nic.in and legislative.gov.in "
    "failed (JS-rendered/timeout) on two attempts. Provenance confidence is LOWER "
    "than the rest of the corpus which came from complete official PDFs. "
    "Verify against official PDF when indiacode.nic.in becomes accessible."
)

# ── Verbatim texts (cross-referenced across 3+ search-grounding sources) ──────

CHUNKS = [
    Document(
        page_content=(
            "41D. Right of arrested person to meet an advocate of his choice "
            "during interrogation. — When any person is arrested and interrogated "
            "by the police, he shall be entitled to meet an advocate of his choice "
            "during interrogation, though not throughout interrogation."
        ),
        metadata={
            "law_name"    : "Crpc Act",
            "section"     : "41D",
            "page"        : 40,          # consistent with surrounding pages in existing index
            "source_note" : SOURCE_NOTE,
            "supplementary": True,
        },
    ),
    Document(
        page_content=(
            "50A. Obligation of person making arrest to inform about the arrest, "
            "etc., to a nominated person. — (1) Every police officer or other person "
            "making any arrest under this Code shall forthwith give the information "
            "regarding such arrest and place where the arrested person is being held "
            "to any of his friends, relatives or such other person as may be disclosed "
            "or nominated by the arrested person for the purpose of giving such information. "
            "(2) The police officer shall inform the arrested person of his rights under "
            "sub-section (1) as soon as he is brought to the police station. "
            "(3) An entry of the information given under sub-section (1) shall be made "
            "in the book to be kept in the police station in such form as may be prescribed "
            "in this behalf by the State Government. "
            "(4) It shall be the duty of the Magistrate before whom such arrested person "
            "is produced, to satisfy himself that the requirements of sub-section (2) have "
            "been complied with in respect of such arrested person."
        ),
        metadata={
            "law_name"    : "Crpc Act",
            "section"     : "50A",
            "page"        : 42,          # between Section 50 (p42) and Section 51 (p43)
            "source_note" : SOURCE_NOTE,
            "supplementary": True,
        },
    ),
    Document(
        page_content=(
            "Rights of arrested person under the Constitution — "
            "22. Protection against arrest and detention in certain cases. — "
            "(1) No person who is arrested shall be detained in custody without "
            "being informed, as soon as may be, of the grounds for such arrest "
            "nor shall he be denied the right to consult, and to be defended by, "
            "a legal practitioner of his choice. "
            "(2) Every person who is arrested and detained in custody shall be "
            "produced before the nearest magistrate within a period of twenty-four "
            "hours of such arrest excluding the time necessary for the journey from "
            "the place of arrest to the court of the magistrate and no such person "
            "shall be detained in custody beyond the said period without the authority "
            "of a magistrate."
        ),
        metadata={
            "law_name"    : "Constitution Of India",
            "section"     : "Article 22",
            "page"        : 42,          # Part III Fundamental Rights section
            "source_note" : SOURCE_NOTE,
            "supplementary": True,
        },
    ),
]

print("=" * 70)
print("  STEP 2 — Adding arrest-rights chunks to citizen FAISS index")
print("=" * 70)

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

print("\n[1] Loading existing citizen index...")
vs = FAISS.load_local(CITIZEN_INDEX, embeddings, allow_dangerous_deserialization=True)
before_count = len(vs.index_to_docstore_id)
print(f"    Chunks before: {before_count}")

# ── Idempotent removal of any existing supplementary chunks ──────────────────
# FAISS doesn't support in-place deletion, so we rebuild the index from all
# non-supplementary documents and re-embed just the three canonical chunks.
print("\n[2] Removing any existing supplementary chunks (idempotent)...")
docstore = vs.docstore
index_to_id = vs.index_to_docstore_id

keep_docs = []
removed = 0
for idx in sorted(index_to_id.keys()):
    doc_id = index_to_id[idx]
    doc = docstore.search(doc_id)
    if doc is None:
        continue
    if doc.metadata.get("supplementary"):
        removed += 1
    else:
        keep_docs.append(doc)

print(f"    Removed {removed} existing supplementary chunk(s).")
print(f"    Rebuilding index from {len(keep_docs)} base chunks...")

# Rebuild FAISS from the kept documents, then add the 3 canonical chunks
if keep_docs:
    vs = FAISS.from_documents(keep_docs, embeddings)
else:
    # Edge case: nothing to keep — create fresh from the 3 chunks directly
    vs = FAISS.from_documents(CHUNKS, embeddings)
    CHUNKS = []  # already added

print(f"\n[3] Embedding and adding {len(CHUNKS)} canonical supplementary chunks...")
if CHUNKS:
    vs.add_documents(CHUNKS)
after_count = len(vs.index_to_docstore_id)
print(f"    Chunks after : {after_count}  (base {len(keep_docs)} + {len(CHUNKS)} supplementary)")

print("\n[4] Saving updated index back to disk...")
vs.save_local(CITIZEN_INDEX)
print("    Saved.")

print("\n[5] Verification — similarity search for the three new concepts:")
VERIFY_QUERIES = [
    ("right to consult lawyer arrested person advocate his choice", "Article 22(1) / §41-D"),
    ("inform family relative nominated person of arrest police", "§50-A"),
    ("Section 41D meet advocate interrogation", "§41-D direct"),
    ("Section 50A obligation inform friend relative arrested", "§50-A direct"),
]
for query, label in VERIFY_QUERIES:
    results = vs.similarity_search_with_score(query, k=3)
    print(f"\n  Query ({label}): '{query[:60]}...'")
    for doc, score in results:
        law  = doc.metadata.get("law_name", "?")
        sec  = doc.metadata.get("section", "?")
        supp = " [SUPPLEMENTARY]" if doc.metadata.get("supplementary") else ""
        snip = doc.page_content[:80].replace("\n", " ")
        print(f"    [{law} | §{sec} | dist={score:.4f}]{supp} {snip}...")

print("\n" + "=" * 70)
print("DONE — index updated. Re-run diagnose_arrest_rights.py to confirm.")
print("=" * 70)
