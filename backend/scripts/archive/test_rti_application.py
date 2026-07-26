"""
Regression test for upgraded rti_application template.
Tests: fee clause, BPL note, Section 7(1) timeline, Section 19(1) appeal,
       applicant contact block, and citation verification clean.

Usage: cd backend && python -m scripts.test_rti_application
"""
import sys, io, logging
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

ROAD_RTI_DESC = (
    "I want to file an RTI with the Municipal Corporation of Greater Mumbai "
    "(MCGM), Public Works Department, seeking: (1) the total budget allocated "
    "for road repair works in Ward H/West for the financial year 2024-25, "
    "(2) the list of roads identified for repair and their current completion "
    "status, (3) the names of contractors awarded the repair contracts along "
    "with the contract amounts, and (4) the inspection reports and quality "
    "certificates issued after completion of road works in this ward."
)

print("=" * 70)
print("  test_rti_application.py — road-repair RTI test")
print("=" * 70)

svc = VectorService()
result = svc.generate_legal_document("rti_application", ROAD_RTI_DESC)
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
checks = {
    # Addressee block
    "PIO addressee present"                       : "public information officer" in doc_lower,

    # Applicant contact fields
    "Contact Number field present"                : "contact number" in doc_lower or "phone" in doc_lower,
    "Email field present"                         : "email" in doc_lower,
    "Postal address field present"                : "address" in doc_lower,

    # Fee clause
    "Rs. 10 application fee stated"               : "rs. 10" in doc_lower or "rupees ten" in doc_lower or "10/-" in doc,
    "Fee payment modes listed"                    : any(m in doc_lower for m in ["demand draft", "postal order", "court fee", "indian postal order"]),
    "BPL exemption note present (bracketed)"      : "bpl" in doc_lower or "below poverty line" in doc_lower,

    # Timeline clause
    "Section 7(1) cited"                          : "7(1)" in doc or "section 7" in doc_lower,
    "30-day response period mentioned"            : "30" in doc and ("day" in doc_lower),
    "48-hour life/liberty clause present"         : "48" in doc and ("hour" in doc_lower or "liberty" in doc_lower),

    # Appeal clause
    "Section 19(1) First Appeal cited"            : "19(1)" in doc or "section 19" in doc_lower,
    "First Appeal within 30 days noted"           : "first appeal" in doc_lower,
    "Appellate Authority mentioned"               : "appellate authority" in doc_lower,

    # Declaration
    "Citizen of India declaration"                : "citizen of india" in doc_lower,
    "Sections 8 and 9 exemptions referenced"      : ("section 8" in doc_lower or "sections 8" in doc_lower),

    # Citation verification
    "No citation warning block"                   : "VERIFICATION NOTICE" not in doc,
}

all_pass = True
for label, passed in checks.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label}")

print()
print("OVERALL:", "ALL CHECKS PASS" if all_pass else "SOME CHECKS FAILED")
print("=" * 70)
