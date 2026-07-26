"""
Regression test: confirm consumer_complaint no longer fabricates a specific
day when the user only provides month/year or an approximate timeframe.

Usage: cd backend && python -m scripts.test_date_precision
"""
import sys, io, logging, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("app.services.vector_service").setLevel(logging.DEBUG)
for noisy in ("httpx", "httpcore", "sentence_transformers", "faiss", "urllib3",
              "groq", "datasets", "numexpr"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from app.services.vector_service import VectorService

# ── Travel-agency case: only "May 2026" given — no specific day ──────────────
TRAVEL_DESC = (
    "In May 2026, I booked a holiday package to Goa through Sunrise Travels, "
    "Pune for Rs. 45,000 (inclusive of hotel, transport, and meals). The agency "
    "confirmed the booking via email but cancelled it without notice one week "
    "before departure, citing 'operational reasons'. Despite repeated follow-ups, "
    "they have neither provided an alternative package nor refunded my money. "
    "I seek a full refund of Rs. 45,000 plus compensation of Rs. 10,000."
)

print("=" * 70)
print("  test_date_precision.py — travel agency (month/year only)")
print("=" * 70)

svc = VectorService()
result = svc.generate_legal_document("consumer_complaint", TRAVEL_DESC)
doc    = result["content"]
verif  = result["verification"]

print("\n" + "=" * 70)
print("GENERATED DOCUMENT:")
print("=" * 70)
print(doc)

print("\n" + "=" * 70)
print("VERIFICATION RESULT:")
print("=" * 70)
print(f"  has_unverified       : {verif['has_unverified']}")
print(f"  unverified_citations : {verif['unverified_citations']}")

doc_lower = doc.lower()

# Detect fabricated specific-day patterns ONLY for the user's stated month.
# The user said "May 2026" — we check whether the model invented a day number
# before "May 2026" (e.g. "02 May 2026"), which was not in the input.
# We deliberately do NOT flag today's date ("25 July 2026") which is legitimately
# injected via {today} into the filing-date line, limitation check, and signature block.
USER_MONTH = "may"   # lowercase — the month stated in the user's description
fabricated_day_pattern = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])\s+" + USER_MONTH + r"\s+2026\b",
    re.IGNORECASE,
)
fabricated_matches = fabricated_day_pattern.findall(doc_lower)

print()
checks = {
    "Contains 'May 2026' (user's actual phrasing)"        : "may 2026" in doc_lower,
    "No fabricated specific day (e.g. '02 May 2026')"    : len(fabricated_matches) == 0,
    "Limitation: within 2 years noted"                    : "limitation" in doc_lower or "section 69" in doc_lower,
    "District Commission (Rs 45k < Rs 50L)"               : "district" in doc_lower,
    "Section 35 cited"                                    : "section 35" in doc_lower,
    "Verification/affidavit clause"                       : "affirm" in doc_lower or "verification" in doc_lower,
    "No citation warning block"                           : "VERIFICATION NOTICE" not in doc,
}

if fabricated_matches:
    print(f"  [INFO] Fabricated day matches found: {fabricated_matches}")

all_pass = True
for label, passed in checks.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label}")

print()
print("OVERALL:", "ALL CHECKS PASS" if all_pass else "SOME CHECKS FAILED")
print("=" * 70)
