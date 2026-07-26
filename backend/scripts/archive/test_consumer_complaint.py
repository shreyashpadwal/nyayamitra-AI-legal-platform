"""
Regression test for upgraded consumer_complaint template.
Tests: forum jurisdiction, limitation check, verification/affidavit clause.

Usage: cd backend && python -m scripts.test_consumer_complaint
"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Enable DEBUG only for our service so citation distances are visible
logging.getLogger("app.services.vector_service").setLevel(logging.DEBUG)
for noisy in ("httpx", "httpcore", "sentence_transformers", "faiss", "urllib3",
              "groq", "datasets", "numexpr"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from app.services.vector_service import VectorService

# ── Test case A: amount given (₹35,000 → District Commission) + recent date ──
FRIDGE_DESC = (
    "I purchased a Samsung Double Door Refrigerator (Model: RT42M5538BS) "
    "from Reliance Digital, Koramangala, Bengaluru on 10 March 2024 for "
    "Rs. 35,000. Within 3 months of purchase, the cooling stopped working "
    "completely. I raised a complaint on 15 June 2024 (complaint no. SVC-8821). "
    "A Samsung technician visited but said the compressor is faulty and cannot "
    "be repaired under warranty without paying Rs. 8,000 extra, which is "
    "contrary to the 1-year comprehensive warranty promised at the time of sale. "
    "I have called the customer care 5 times but received no resolution. "
    "I seek a full refund of Rs. 35,000 plus compensation of Rs. 15,000 "
    "for mental agony and litigation costs."
)

print("=" * 70)
print("  TEST A — Refrigerator (Rs 35,000 → District; recent date)")
print("=" * 70)

svc = VectorService()
result = svc.generate_legal_document("consumer_complaint", FRIDGE_DESC)
doc   = result["content"]
verif = result["verification"]

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
checks_a = {
    "Forum: District Commission selected"   : "district" in doc_lower,
    "Forum: NOT State/National (35k < 50L)" : "state commission" not in doc_lower and "national commission" not in doc_lower,
    "Sec 35 (filing basis) cited"           : "section 35" in doc_lower or "sec. 35" in doc_lower,
    "Sec 69 (limitation) cited"             : "section 69" in doc_lower or "69" in doc,
    "Limitation: within 2 years noted"      : ("within" in doc_lower and "2 year" in doc_lower) or "limitation" in doc_lower,
    "No LIMITATION NOTE (recent date)"      : "LIMITATION NOTE" not in doc,
    "Prayer with refund amount"             : "35,000" in doc or "refund" in doc_lower,
    "Verification/affidavit clause"         : "affirm" in doc_lower or "verification" in doc_lower or "affidavit" in doc_lower,
    "Complainant signature block"           : "signature" in doc_lower,
    "No warning block"                      : "VERIFICATION NOTICE" not in doc,
}

all_pass = True
for label, passed in checks_a.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label}")
print("\nTEST A:", "ALL PASS" if all_pass else "SOME FAILED")

# ── Test case B: old date (should trigger LIMITATION NOTE) ──
OLD_DESC = (
    "I purchased a laptop from HP India online store on 5 January 2022 "
    "for Rs. 75,000. The laptop developed a motherboard failure in March 2022 "
    "but HP refused to replace or refund. I want to file a complaint now."
)

print("\n" + "=" * 70)
print("  TEST B — Old laptop issue (Jan 2022, >2 years → LIMITATION NOTE expected)")
print("=" * 70)

result_b = svc.generate_legal_document("consumer_complaint", OLD_DESC)
doc_b    = result_b["content"]

print(doc_b)
print("\n" + "=" * 70)
print("CHECKS TEST B:")
doc_b_lower = doc_b.lower()
checks_b = {
    # Rs. 75,000 < Rs. 50 lakh → District Commission is correct
    "Forum: District Commission (75k < 50 lakh)" : "district" in doc_b_lower,
    "Forum: NOT State/National (75k < 50L)"      : "state commission" not in doc_b_lower and "national commission" not in doc_b_lower,
    "LIMITATION NOTE appears (2022 date = >2yr)" : (
        "LIMITATION NOTE" in doc_b
        or "time-barred" in doc_b_lower
        or "condonation" in doc_b_lower
    ),
    "Section 69(2) condonation mentioned"        : "69(2)" in doc_b or "condonation" in doc_b_lower,
    "Verification/affidavit clause"              : "affirm" in doc_b_lower or "verification" in doc_b_lower,
}
all_b = True
for label, passed in checks_b.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_b = False
    print(f"  [{status}] {label}")
print("\nTEST B:", "ALL PASS" if all_b else "SOME FAILED")
print("=" * 70)
