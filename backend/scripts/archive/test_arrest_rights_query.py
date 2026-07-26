"""
Live end-to-end test: confirms the arrest-rights answer now includes
Section 41D (right to meet advocate) and Section 50A (right to inform
nominated person) alongside the previously-present §49, §50, Article 22.

Usage: cd backend && python -m scripts.test_arrest_rights_query
"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])

from app.services.vector_service import VectorService
svc = VectorService()

QUERY = "What are my rights if police arrest me?"

print("=" * 70)
print(f"  ARREST-RIGHTS E2E TEST")
print(f"  Query: '{QUERY}'")
print("=" * 70)

result = svc.get_citizen_answer(
        QUERY,
        intent="general_legal_query",
        instruction="",
    )
answer = result.get("answer", "")
print("\nANSWER:\n" + "-" * 60)
print(answer)
print("-" * 60)

print("\nCHECKS:")
checks = {
    "Section 49 mentioned  (limits on restraint)"         : "49" in answer,
    "Section 50 mentioned  (grounds of arrest)"           : "50" in answer,
    "Section 41D mentioned (right to meet advocate)"      : "41D" in answer or "41-D" in answer,
    "Section 50A mentioned (right to inform family)"      : "50A" in answer or "50-A" in answer,
    "Article 22 mentioned  (Constitutional protection)"   : "22" in answer,
    "Legal practitioner / advocate / lawyer mentioned"    : any(w in answer.lower() for w in
                                                             ["legal practitioner","advocate","lawyer"]),
    "Nominated person / family / relative mentioned"      : any(w in answer.lower() for w in
                                                             ["nominated","relative","friend","family"]),
}

all_pass = True
for label, ok in checks.items():
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] {label}")

print(f"\nOVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")
print("=" * 70)
