"""
Regression test for vector_service fixes:
  1. Citation verification no longer false-positives §379 / §323
  2. Police complaint includes CrPC §154 + robbery/theft note

Usage: cd backend && python -m scripts.test_doc_gen_fixes
"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

# Enable DEBUG logging so we see the per-citation distance lines
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(name)s:%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Quieten noisy third-party loggers
for noisy in ("httpx", "httpcore", "sentence_transformers", "faiss"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from app.services.vector_service import VectorService

PHONE_SNATCH_DESC = (
    "On 15 July 2025 at around 9:30 PM, I was walking on MG Road, "
    "Bengaluru. A man on a motorcycle came from behind, grabbed my "
    "phone from my hand, pushed me hard causing me to fall and injure "
    "my knee, and sped away. My phone (Samsung Galaxy S22, IMEI: "
    "123456789012345) was stolen. I also suffered a knee bruise."
)

print("=" * 68)
print("  test_doc_gen_fixes.py — citation verify + police complaint")
print("=" * 68)
print()

svc = VectorService()
result = svc.generate_legal_document("police_complaint", PHONE_SNATCH_DESC)

doc = result["content"]
verif = result["verification"]

print("\n" + "=" * 68)
print("GENERATED DOCUMENT:")
print("=" * 68)
print(doc)

print("\n" + "=" * 68)
print("VERIFICATION RESULT:")
print("=" * 68)
print(f"  has_unverified       : {verif['has_unverified']}")
print(f"  unverified_citations : {verif['unverified_citations']}")

print()
checks = {
    "CrPC Section 154 present"    : "Section 154" in doc or "154" in doc,
    "Robbery/theft note present"  : ("Section 390" in doc or "390" in doc) or ("robbery" in doc.lower()),
    "No warning block appended"   : "VERIFICATION NOTICE" not in doc,
    "FIR number placeholder"      : "FIR Number" in doc or "FIR No" in doc or "____________" in doc,
    "Acknowledgment right"        : "154(2)" in doc or "copy" in doc.lower() or "acknowledgment" in doc.lower(),
}
all_pass = True
for label, passed in checks.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label}")

print()
print("OVERALL:", "ALL CHECKS PASS" if all_pass else "SOME CHECKS FAILED")
print("=" * 68)
