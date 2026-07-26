"""
Item 1 diagnostic: Test cross-section attribution discipline across
sections NOT in the original bug report: §302 murder, §354 assault
on women, §406 criminal breach of trust.

For each, run the full citizen pipeline and check whether the answer:
  (a) correctly attributes facts to the right section only
  (b) avoids merging adjacent-chunk provisions into the primary section
  (c) correctly states the v6 prompt is active

Usage: cd backend && python -m scripts.diag_attribution_discipline
"""
import sys, io, asyncio, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

from app.services.vector_service import VectorService

vs = VectorService()

TEST_QUERIES = [
    {
        "label": "§302 IPC (murder)",
        "query": "What is the punishment for murder under IPC Section 302?",
        # Known: §302 = death or life imprisonment + fine
        # Adjacent chunk risk: §303 (life convict murder), §304 (culpable homicide)
        "expected_section": "302",
        "forbidden_sections": ["303", "304"],
        "known_fact": "death",
    },
    {
        "label": "§354 IPC (assault on woman)",
        "query": "What is the punishment for assault on a woman under IPC?",
        # Known: §354 = up to 2 years or fine or both
        # Adjacent chunk risk: §354A (sexual harassment), §354B, §354C, §354D
        "expected_section": "354",
        "forbidden_sections": ["354A", "354B", "354C", "354D"],
        "known_fact": "two year",
    },
    {
        "label": "§406 IPC (criminal breach of trust)",
        "query": "What is the punishment under IPC Section 406 for criminal breach of trust?",
        # Known: §406 = up to 3 years or fine or both
        # Adjacent chunk risk: §407 (carrier), §408 (clerk/servant), §409 (public servant)
        "expected_section": "406",
        "forbidden_sections": ["407", "408", "409"],
        "known_fact": "three year",
    },
]

print("=" * 70)
print("  ITEM 1 — Cross-section attribution discipline test")
print("  Prompt active version check + 3 novel queries")
print("=" * 70)

# Confirm active prompt version
from app.services.prompts.prompt_registry import get_prompt
prompt_text = get_prompt("citizen_answer")
if "CROSS-ACT ATTRIBUTION RULE" in prompt_text:
    print("\n  [✅] citizen_answer active version contains CROSS-ACT ATTRIBUTION RULE (v6)")
elif "SECTION NUMBER IN SENTENCE RULE" in prompt_text:
    print("\n  [⚠️ ] citizen_answer active = v5 (v6 not loaded — backend may not have restarted)")
else:
    print("\n  [❌] citizen_answer active version UNKNOWN — check prompt registry")

results = []
for tc in TEST_QUERIES:
    print(f"\n{'─'*70}")
    print(f"  Query [{tc['label']}]: '{tc['query']}'")

    try:
        result = asyncio.run(vs.get_citizen_answer(
                tc["query"],
                intent="legal_information",
                instruction="Provide a clear answer citing the relevant IPC section and its exact punishment."
            ))
        answer = result.get("answer", "")
        sources = result.get("sources", [])

        # Check: does the expected section appear?
        has_expected = tc["expected_section"] in answer
        # Check: do any forbidden sections appear WITHOUT their own label?
        contamination = []
        for fs in tc["forbidden_sections"]:
            if fs in answer:
                # Only flag if it's presented as a property of the primary section
                # (rough heuristic: the forbidden section appears but without "Section X" prefix)
                contamination.append(fs)

        # Check: known fact present
        has_fact = tc["known_fact"].lower() in answer.lower()

        print(f"\n  ANSWER (truncated to 500 chars):")
        print(f"  {answer[:500].replace(chr(10), chr(10)+'  ')}")
        print(f"\n  CHECKS:")
        print(f"    [{'✅' if has_expected else '❌'}] Expected §{tc['expected_section']} mentioned")
        print(f"    [{'✅' if has_fact else '❌'}] Known fact ('{tc['known_fact']}') present")
        print(f"    [{'✅' if not contamination else '❌'}] Contamination check — forbidden sections in answer: {contamination or 'none'}")
        src_labels = [f"{s.get('law_name','?')} p{s.get('page','?')}" for s in sources]
        print(f"    Sources cited: {src_labels}")

        results.append({
            "label": tc["label"],
            "pass": has_expected and has_fact,
            "contamination": contamination,
        })

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"label": tc["label"], "pass": False, "contamination": [], "error": str(e)})

print(f"\n{'='*70}")
print("  SUMMARY")
print("=" * 70)
for r in results:
    status = "✅ PASS" if r["pass"] and not r["contamination"] else "❌ FAIL"
    print(f"  {status} | {r['label']} | contamination={r['contamination'] or 'none'}")
print("=" * 70)
