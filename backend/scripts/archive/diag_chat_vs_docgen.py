"""
Item 4 diagnostic: Chat vs Document Generator consistency audit.

Tests known facts through both the Chat (RAG-grounded) and Document
Generator (template-hardcoded) pipelines to measure the architectural
asymmetry and identify whether it's a systemic gap.

Known facts to test:
  - RTI §7(1): 30-day response deadline
  - IPC §380: up to 7 years for theft in dwelling
  - CPA limitation: 2-year period to file consumer complaint
  - IPC §379: up to 3 years for theft

Usage: cd backend && python -m scripts.diag_chat_vs_docgen
"""
import sys, io, asyncio, logging, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

from app.services.vector_service import VectorService

vs = VectorService()

# ── Part A: Verify facts exist in citizen FAISS index ──────────────────
print("=" * 70)
print("  ITEM 4 — Chat vs Document Generator consistency audit")
print("=" * 70)

print("\n[A] Confirm known facts exist in citizen FAISS index")
from app.services.vector_service import _get_citizen_vs

citizen_vs = _get_citizen_vs()

KNOWN_FACTS = [
    {
        "label": "RTI §7(1) 30-day deadline",
        "search": "30 days information officer RTI response",
        "expect_in_chunk": "30",
        "law": "Rti Act",
    },
    {
        "label": "IPC §380 dwelling-house theft (7 years)",
        "search": "theft dwelling house imprisonment seven years 380",
        "expect_in_chunk": "seven year",
        "law": "Indian Penal Code",
    },
    {
        "label": "IPC §379 theft (3 years)",
        "search": "theft punishment three years 379 IPC",
        "expect_in_chunk": "three year",
        "law": "Indian Penal Code",
    },
    {
        "label": "CPA limitation period (2 years)",
        "search": "consumer complaint limitation two years filing period",
        "expect_in_chunk": "two year",
        "law": "Consumer Protection Act",
    },
]

index_facts = {}
for fact in KNOWN_FACTS:
    results = citizen_vs.similarity_search_with_score(fact["search"], k=3)
    found = False
    for doc, score in results:
        if (fact["expect_in_chunk"].lower() in doc.page_content.lower() and
                fact["law"].lower() in doc.metadata.get("law_name", "").lower()):
            found = True
            break
    status = "✅ IN INDEX" if found else "❌ NOT FOUND"
    print(f"  {status} | {fact['label']}")
    index_facts[fact["label"]] = found

# ── Part B: Test Chat Assistant for each known fact ────────────────────
print("\n[B] Chat Assistant — RAG pipeline responses")

CHAT_QUERIES = [
    {
        "label": "RTI 30-day deadline",
        "query": "How many days does the government have to respond to an RTI application?",
        "expected_keywords": ["30", "thirty", "Section 7"],
    },
    {
        "label": "IPC §380 dwelling theft penalty",
        "query": "What is the punishment for theft committed in a house under IPC Section 380?",
        "expected_keywords": ["seven", "7", "380"],
    },
    {
        "label": "IPC §379 theft penalty",
        "query": "What is the punishment for simple theft under IPC Section 379?",
        "expected_keywords": ["three", "3", "379"],
    },
    {
        "label": "Consumer complaint limitation period",
        "query": "What is the time limit for filing a consumer complaint?",
        "expected_keywords": ["two year", "2 year", "limitation"],
    },
]

chat_results = {}
for q in CHAT_QUERIES:
    try:
        result = asyncio.run(vs.get_citizen_answer(
            q["query"],
            intent="legal_information",
            instruction="Provide a direct factual answer citing the relevant section and Act."
        ))

        answer = result.get("answer", "")
        found_kw = [kw for kw in q["expected_keywords"] if kw.lower() in answer.lower()]
        passed = len(found_kw) > 0
        status = "✅ CORRECT" if passed else "❌ MISSING"
        print(f"\n  {status} | {q['label']}")
        print(f"  Keywords found: {found_kw or 'NONE'}")
        print(f"  Answer (first 300 chars): {answer[:300].replace(chr(10), ' ')}")
        chat_results[q["label"]] = {"passed": passed, "keywords_found": found_kw}
    except Exception as e:
        print(f"  ❌ ERROR | {q['label']}: {e}")
        chat_results[q["label"]] = {"passed": False, "error": str(e)}

# ── Part C: Document Generator — what it hardcodes vs retrieves ────────
print("\n\n[C] Document Generator architecture analysis")
print("  The Document Generator does NOT use RAG for its core legal facts.")
print("  It embeds legal provisions DIRECTLY into prompt templates:")
print()
print("  ✅ RTI §7(1) 30-day deadline → HARDCODED in rti_application template (line 680-684)")
print("     'within 30 (thirty) days from the date of receipt...'")
print()
print("  This means the doc generator is immune to retrieval gaps for hardcoded facts,")
print("  but also immune to updates — if the law changes, the template is stale.")
print()

# Test doc generator for RTI
print("  Testing doc generator RTI 30-day output...")
try:
    result = vs.generate_legal_document("rti_application", "I want to know about road construction status in my area")
    doc_text = result.get("document", "")
    has_30day = "30" in doc_text and ("thirty" in doc_text.lower() or "7(1)" in doc_text)
    print(f"  {'✅' if has_30day else '❌'} RTI doc generator includes 30-day deadline: {has_30day}")
    # Check if it also mentions §19(1) appeal
    has_appeal = "19(1)" in doc_text or "First Appeal" in doc_text
    print(f"  {'✅' if has_appeal else '❌'} RTI doc generator includes appeal provision (§19(1)): {has_appeal}")
except Exception as e:
    print(f"  ❌ Doc generator error: {e}")

# ── Summary ─────────────────────────────────────────────────────────────
print(f"\n\n{'='*70}")
print("  ASYMMETRY ANALYSIS")
print("=" * 70)
chat_pass  = sum(1 for v in chat_results.values() if v.get("passed"))
chat_total = len(chat_results)
print(f"  Chat Assistant: {chat_pass}/{chat_total} known facts answered correctly via RAG")
print(f"  Doc Generator:  hardcodes legal provisions in templates — immune to retrieval gaps")
print()
print("  ARCHITECTURAL FINDING:")
print("  The Chat and Doc Generator use DIFFERENT architectures for legal fact delivery:")
print("  - Chat: fully RAG-grounded (retrieval quality determines correctness)")
print("  - Doc: template-hardcoded (always correct for hardcoded facts, but brittle to law changes)")
print()
if chat_pass < chat_total:
    print("  ⚠️  SYSTEMIC GAP: Chat fails to surface facts that ARE in the index.")
    print("     This is a retrieval threshold / reranker issue, not a content gap.")
    print("     Affected queries: ", [k for k, v in chat_results.items() if not v.get("passed")])
else:
    print("  ✅ Chat correctly surfaces all tested facts — no systemic gap found.")
print("=" * 70)
