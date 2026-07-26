"""
Regression test: confirm all three doc types use [Your Full Name] / [Your Address] /
[Your Contact Number] / [Your Email Address] placeholders when the user provides
no personal identity information.

Test cases:
  A — Phone-snatching robbery (Police Complaint)
  B — Travel agency refund (Consumer Complaint)
  C — Nashik water project RTI (RTI Application)

Usage: cd backend && python -m scripts.test_pii_fix
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
svc = VectorService()

CASES = [
    (
        "police_complaint",
        "A — Phone-snatching robbery (Police Complaint)",
        (
            "On 15 July 2025 at around 9:30 PM, I was walking on MG Road, Bengaluru. "
            "A man on a motorcycle came from behind, grabbed my phone from my hand, "
            "pushed me hard causing me to fall and injure my knee, and sped away. "
            "My phone (Samsung Galaxy S22, IMEI: 123456789012345) was stolen. "
            "I also suffered a knee bruise."
        ),
    ),
    (
        "consumer_complaint",
        "B — Travel agency refund (Consumer Complaint)",
        (
            "In May 2026, I booked a holiday package to Goa through Sunrise Travels, "
            "Pune for Rs. 45,000. The agency confirmed the booking via email but "
            "cancelled it without notice one week before departure, citing 'operational "
            "reasons'. Despite repeated follow-ups, they have neither provided an "
            "alternative package nor refunded my money. I seek a full refund of "
            "Rs. 45,000 plus compensation of Rs. 10,000."
        ),
    ),
    (
        "rti_application",
        "C — Nashik water project RTI (RTI Application)",
        (
            "I want to file an RTI with the Nashik Municipal Corporation, Water "
            "Supply Department, seeking: (1) total budget sanctioned for the Nashik "
            "Water Supply Improvement Project Phase II for FY 2024-25, (2) list of "
            "contractors awarded and contract amounts, (3) current completion status "
            "of each sub-project, and (4) inspection and quality reports issued for "
            "completed works."
        ),
    ),
]

# Fabricated PII detectors
PHONE_PAT = re.compile(r"\b\d{10}\b")
EMAIL_PAT  = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Real-name pattern: two or more capitalised words that are NOT placeholder brackets
REAL_NAME_PAT = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

PLACEHOLDERS = ["[Your Full Name]", "[Your Address]", "[Your Contact Number]", "[Your Email Address]"]

overall_pass = True

for doc_type, label, desc in CASES:
    print("\n" + "=" * 70)
    print(f"  TEST {label}")
    print("=" * 70)

    result = svc.generate_legal_document(doc_type, desc)
    doc    = result["content"]

    print("\nGENERATED DOCUMENT:\n" + "-" * 60)
    print(doc)
    print("-" * 60)

    # Check placeholders present
    ph_present = {ph: ph in doc for ph in PLACEHOLDERS}

    # Check no fabricated phone/email
    fab_phones = [p for p in PHONE_PAT.findall(doc) if p not in PHONE_PAT.findall(desc)]
    fab_emails = [e for e in EMAIL_PAT.findall(doc) if e not in EMAIL_PAT.findall(desc)]

    print("\nCHECKS:")
    checks = {
        "[Your Full Name] placeholder used"     : ph_present["[Your Full Name]"],
        "[Your Address] placeholder used"        : ph_present["[Your Address]"],
        "[Your Contact Number] placeholder used" : ph_present["[Your Contact Number]"],
        "[Your Email Address] placeholder used"  : ph_present["[Your Email Address]"],
        "No fabricated phone number"             : len(fab_phones) == 0,
        "No fabricated email address"            : len(fab_emails) == 0,
        "No citation warning block"              : "VERIFICATION NOTICE" not in doc,
    }

    if fab_phones: print(f"  [INFO] Fabricated phones: {fab_phones}")
    if fab_emails: print(f"  [INFO] Fabricated emails: {fab_emails}")

    case_pass = True
    for lbl, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            case_pass = False
            overall_pass = False
        print(f"  [{status}] {lbl}")

    print(f"\n  TEST {label[0]}: {'ALL PASS' if case_pass else 'SOME FAILED'}")

print("\n" + "=" * 70)
print("OVERALL:", "ALL THREE TESTS PASS" if overall_pass else "SOME TESTS FAILED")
print("=" * 70)
