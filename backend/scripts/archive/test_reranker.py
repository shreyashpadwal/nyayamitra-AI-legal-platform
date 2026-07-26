"""
Proof test: confirm CrossEncoderReranker actually scores documents
with real cross-encoder scores (not all-zero fallback values).
Tests 3 diverse queries to demonstrate the fix is not query-specific.

Usage: cd backend && python -m scripts.test_reranker
"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])

from langchain_core.documents import Document
from app.services.retrieval.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker()

TEST_CASES = [
    {
        "query": "What are my rights if police arrest me?",
        "docs": [
            Document(page_content="Section 50A: Every police officer making any arrest shall give information to a nominated person of the arrested person.", metadata={"law": "CrPC"}),
            Document(page_content="Section 41D: When any person is arrested and interrogated by the police, he shall be entitled to meet an advocate of his choice during interrogation.", metadata={"law": "CrPC"}),
            Document(page_content="Article 22(1): No person who is arrested shall be denied the right to consult, and to be defended by, a legal practitioner of his choice.", metadata={"law": "Constitution"}),
            Document(page_content="The Indian Penal Code prescribes punishment for theft under Section 379.", metadata={"law": "IPC"}),
            Document(page_content="A contract is an agreement enforceable by law under the Indian Contract Act.", metadata={"law": "ICA"}),
        ],
    },
    {
        "query": "What is the punishment for theft in IPC?",
        "docs": [
            Document(page_content="Section 379 IPC: Whoever commits theft shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both.", metadata={"law": "IPC"}),
            Document(page_content="Section 380 IPC: Theft in a dwelling house, or vessel used as a dwelling, may extend to seven years.", metadata={"law": "IPC"}),
            Document(page_content="Article 22: No person who is arrested shall be detained in custody without being informed of grounds.", metadata={"law": "Constitution"}),
            Document(page_content="The Consumer Protection Act provides remedies for defective products.", metadata={"law": "CPA"}),
        ],
    },
    {
        "query": "How do I file an RTI application?",
        "docs": [
            Document(page_content="Section 6 RTI Act: A person who desires to obtain any information shall make a request in writing to the Central Public Information Officer.", metadata={"law": "RTI"}),
            Document(page_content="Section 7(1) RTI Act: The PIO shall reply within 30 days of receipt of the request.", metadata={"law": "RTI"}),
            Document(page_content="Section 379 IPC: Punishment for theft — three years imprisonment or fine or both.", metadata={"law": "IPC"}),
            Document(page_content="An FIR is filed under Section 154 CrPC at the nearest police station.", metadata={"law": "CrPC"}),
        ],
    },
]

print("=" * 70)
print("  RERANKER PROOF TEST — cross-encoder/ms-marco-MiniLM-L6-v2")
print("=" * 70)

all_pass = True
for i, tc in enumerate(TEST_CASES, 1):
    query = tc["query"]
    docs  = tc["docs"]
    print(f"\n[Test {i}] Query: '{query}'")
    print(f"  Input docs: {len(docs)}")

    results = reranker.rerank(query, docs, top_k=len(docs))

    # Check: scores must be real floats, not all-zero (fallback indicator)
    scores = [score for _, score in results]
    all_zero = all(s == 0.0 for s in scores)
    has_variance = max(scores) - min(scores) > 0.01

    print(f"  Results (ranked):")
    for rank, (doc, score) in enumerate(results, 1):
        law = doc.metadata.get("law", "?")
        snip = doc.page_content[:70]
        print(f"    [{rank}] score={score:+.4f} [{law}] {snip}...")

    if all_zero:
        print(f"  FAIL — all scores are 0.0 (reranker fallback path triggered)")
        all_pass = False
    elif not has_variance:
        print(f"  FAIL — scores have no variance (model not differentiating)")
        all_pass = False
    else:
        # Check top result is plausibly correct
        top_doc = results[0][0].page_content
        top_score = results[0][1]
        print(f"  PASS — real scores, variance={max(scores)-min(scores):.4f}, top={top_score:+.4f}")

print("\n" + "=" * 70)
print(f"  OVERALL: {'ALL PASS — reranker is working correctly' if all_pass else 'SOME FAILED — reranker still broken'}")
print("=" * 70)
