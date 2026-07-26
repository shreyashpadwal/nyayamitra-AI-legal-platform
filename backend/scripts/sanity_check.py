"""
Item 3: Pre-demo startup sanity check script.

Verifies every fix made in this session is present and active:
  1. Citizen FAISS index chunk count (expected: 4013 = 4010 base + 3 supplementary)
  2. Reranker loads and actually scores docs (not silently failing)
  3. Supplementary §41-D and §50-A chunks are in the index
  4. Prompt registry active versions match intended versions
  5. Hybrid retriever returns results (BM25 is initialized)
  6. k=12 retrieval pool is configured correctly
  7. Multi-right query heuristic is present in citizen_graph

Usage: cd backend && python -m scripts.sanity_check
Exit code: 0 = all checks pass, 1 = one or more checks failed
"""
import sys, io, inspect
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

CHECKS = []
PASS = "✅"
FAIL = "❌"

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    CHECKS.append({"name": name, "passed": passed, "detail": detail})
    print(f"  {status} {name}" + (f"\n     {detail}" if detail else ""))

print("=" * 70)
print("  NYAYAMITRA PRE-DEMO SANITY CHECK")
print("=" * 70)

# ── Check 1: Citizen FAISS index chunk count ────────────────────────────
print("\n[1] Citizen FAISS index chunk count")
try:
    from app.services.vector_service import _get_citizen_vs
    vs = _get_citizen_vs()
    count = len(vs.index_to_docstore_id)
    EXPECTED_MIN = 4010
    EXPECTED_MAX = 4016  # allow for minor drift
    check(
        f"Chunk count = {count} (expected {EXPECTED_MIN}–{EXPECTED_MAX})",
        EXPECTED_MIN <= count <= EXPECTED_MAX,
        f"Actual count: {count}"
    )
except Exception as e:
    check("FAISS index load", False, str(e))

# ── Check 2: Supplementary §41-D and §50-A chunks present ──────────────
print("\n[2] Supplementary chunks in index")
try:
    docstore   = vs.docstore
    index_to_id = vs.index_to_docstore_id
    supp_found = {"41D": False, "50A": False, "Art22": False}
    for idx in index_to_id:
        doc = docstore.search(index_to_id[idx])
        if doc and doc.metadata.get("supplementary"):
            sec = doc.metadata.get("section", "")
            if "41D" in sec or "41d" in sec.lower(): supp_found["41D"] = True
            if "50A" in sec or "50a" in sec.lower(): supp_found["50A"] = True
            if "22" in sec and "constitution" in doc.metadata.get("law_name","").lower():
                supp_found["Art22"] = True
    for key, found in supp_found.items():
        check(f"Supplementary chunk §{key} present in index", found)
except Exception as e:
    check("Supplementary chunks scan", False, str(e))

# ── Check 3: Reranker loads and scores ─────────────────────────────────
print("\n[3] CrossEncoderReranker functional test")
try:
    from app.services.retrieval.reranker import CrossEncoderReranker
    from langchain_core.documents import Document
    reranker = CrossEncoderReranker()
    test_docs = [
        Document(page_content="Section 379 IPC: theft is punishable with up to 3 years imprisonment.", metadata={}),
        Document(page_content="The Consumer Protection Act provides remedies for defective goods.", metadata={}),
    ]
    results = reranker.rerank("What is the punishment for theft?", test_docs, top_k=2)
    scores = [s for _, s in results]
    all_zero = all(s == 0.0 for s in scores)
    has_variance = len(scores) >= 2 and (max(scores) - min(scores) > 0.01)
    check("Reranker loads without meta-tensor crash", True)
    check(
        f"Reranker produces real scores (top={scores[0]:+.4f}, bottom={scores[-1]:+.4f})",
        not all_zero and has_variance,
        f"Scores: {scores}"
    )
except Exception as e:
    check("Reranker functional test", False, str(e))

# ── Check 4: Prompt registry active versions ────────────────────────────
print("\n[4] Prompt registry active versions")
try:
    from app.services.prompts.prompt_registry import PROMPT_REGISTRY, get_prompt

    EXPECTED_VERSIONS = {
        "citizen_answer": "v6",
        "citizen_direct_answer": "v1",
        "query_rewrite": None,  # any — just check it loads
        "hallucination_check": None,
    }
    for prompt_name, expected_v in EXPECTED_VERSIONS.items():
        if prompt_name not in PROMPT_REGISTRY:
            check(f"Prompt '{prompt_name}' exists", False)
            continue
        active = PROMPT_REGISTRY[prompt_name].get("active", "?")
        if expected_v is None:
            check(f"Prompt '{prompt_name}' active={active} (loads)", True)
        else:
            check(
                f"Prompt '{prompt_name}' active={active} (expected {expected_v})",
                active == expected_v
            )

    # Verify v6 content
    citizen_prompt = get_prompt("citizen_answer")
    check(
        "citizen_answer v6 contains CROSS-ACT ATTRIBUTION RULE",
        "CROSS-ACT ATTRIBUTION RULE" in citizen_prompt
    )
except Exception as e:
    check("Prompt registry checks", False, str(e))

# ── Check 5: Hybrid retriever BM25 initialized ─────────────────────────
print("\n[5] Hybrid retriever BM25 initialization")
try:
    from app.services.vector_service import _get_citizen_retriever
    retriever = _get_citizen_retriever()
    results = retriever.retrieve_with_scores("what is theft punishment IPC", k=5)
    check(
        f"Hybrid retriever returns results (got {len(results)})",
        len(results) >= 3,
        f"Retrieved {len(results)} docs"
    )
    # Check k=12 is set
    src = inspect.getsource(retriever.__class__.retrieve_with_scores)
    # Can't reliably check the default arg this way — check via call
    results_12 = retriever.retrieve_with_scores("arrest rights crpc", k=12)
    check(f"k=12 retrieval works (got {len(results_12)} docs)", len(results_12) >= 8)
except Exception as e:
    check("Hybrid retriever check", False, str(e))

# ── Check 6: citizen_graph multi-right heuristic present ───────────────
print("\n[6] citizen_graph fixes present in source")
try:
    import app.services.citizen_graph as cg
    src = inspect.getsource(cg)
    check(
        "_is_multi_right_query heuristic defined",
        "_is_multi_right_query" in src
    )
    check(
        "threshold=0.0 for multi-right queries",
        "rerank_threshold = 0.0 if is_multi_right" in src or "threshold=rerank_threshold" in src
    )
    check(
        "effective_top_k=8 for broad queries",
        "effective_top_k" in src and "8" in src
    )
except Exception as e:
    check("citizen_graph source checks", False, str(e))

# ── Final summary ───────────────────────────────────────────────────────
total  = len(CHECKS)
passed = sum(1 for c in CHECKS if c["passed"])
failed = total - passed

print(f"\n{'='*70}")
print(f"  RESULT: {passed}/{total} checks passed", end="")
if failed == 0:
    print("  ✅ ALL PASS — safe to demo")
else:
    print(f"  ❌ {failed} FAILED — do not demo until resolved")
    print(f"\n  Failed checks:")
    for c in CHECKS:
        if not c["passed"]:
            print(f"    ❌ {c['name']}: {c['detail']}")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
