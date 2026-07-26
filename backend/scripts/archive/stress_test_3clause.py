"""
Stress test: 3-clause compound query through the full citizen pipeline.
Measures latency and counts sub-clause splits.
Usage: cd backend && python -m scripts.stress_test_3clause
"""
import sys, io, time, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

# Load .env so GROQ_API_KEY is set when running standalone
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.citizen_graph import invoke_citizen_pipeline, _detect_target_statute, _is_compound_query

QUERY = "What is the punishment for theft, how does it differ for robbery, and what if a weapon is used?"

print(f"Query: {QUERY}")
print(f"_detect_target_statute: {_detect_target_statute(QUERY)!r}")
print(f"_is_compound_query: {_is_compound_query(QUERY)}")

parts = re.split(r"\band\b|\bor\b|,|\?", QUERY, flags=re.IGNORECASE)
sub_clauses = [p.strip() for p in parts if len(p.strip()) > 12]
print(f"\nSub-clauses ({len(sub_clauses)} detected, cap is 2):")
for i, s in enumerate(sub_clauses, 1):
    print(f"  {i}: {s!r}")

print("\nRunning pipeline (this may take 30-90s)...")
t0 = time.time()
result = invoke_citizen_pipeline(QUERY)
elapsed = time.time() - t0

print(f"\nTotal elapsed: {elapsed:.2f}s")
print(f"Hallucination: {result.get('hallucination_status')}")
print(f"Sources ({len(result['sources'])}):")
for s in result["sources"]:
    print(f"  law={s.get('law')!r}  page={s.get('page')}")

print("\nAnswer (first 600 chars):")
print(result["answer"][:600])

print("\nNode timing:")
for entry in result.get("pipeline_log", []):
    if "elapsed_s" in entry:
        print(f"  {entry['node']:25s} {entry['elapsed_s']:.3f}s")
