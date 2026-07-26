"""
Regression test for two document-quality bugs:
  1. Consistency — name provided in description must appear in ALL sections.
  2. Grammar   — 'I, [name], declare...' must never drop the name/placeholder.

Test A — Police Complaint: user gives real name "Priya Deshmukh".
         Checks: COMPLAINANT DETAILS and SIGNATURE LINE both say "Priya Deshmukh".

Test B — RTI Application: user gives phone+email but NO name.
         Checks: DECLARATION reads "I, [Your Full Name], hereby declare..."
         (not "I, hereby declare...").

Usage: cd backend && python -m scripts.test_doc_quality
"""
import sys, io, logging, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logging.getLogger("app.services.vector_service").setLevel(logging.DEBUG)
for noisy in ("httpx","httpcore","sentence_transformers","faiss","urllib3",
              "groq","datasets","numexpr"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from app.services.vector_service import VectorService
svc = VectorService()

# ── Test A: Priya Deshmukh — name given, must be consistent everywhere ────────
PRIYA_DESC = (
    "My name is Priya Deshmukh. On 20 July 2025, at around 8:00 PM, "
    "my two-wheeler (Honda Activa, MH12-AB-1234) was stolen from the "
    "parking lot outside Phoenix Mall, Pune. I had locked the vehicle "
    "and there were CCTV cameras in the area. I want to register an FIR "
    "for the theft of my vehicle under IPC Section 379."
)

print("=" * 70)
print("  TEST A — Priya Deshmukh (name given → must be consistent)")
print("=" * 70)
res_a = svc.generate_legal_document("police_complaint", PRIYA_DESC)
doc_a = res_a["content"]
print("\nGENERATED DOCUMENT:\n" + "-" * 60)
print(doc_a)
print("-" * 60)

doc_a_lower = doc_a.lower()
# Look for name in complainant details block
# The COMPLAINANT DETAILS section appears before INCIDENT DETAILS
# We'll check that "priya deshmukh" appears before the first mention of the incident
complainant_block_end = doc_a_lower.find("details of incident")
if complainant_block_end == -1:
    complainant_block_end = doc_a_lower.find("4.")  # fallback
complainant_block = doc_a_lower[:complainant_block_end] if complainant_block_end > 0 else doc_a_lower[:500]

name_in_details  = "priya deshmukh" in complainant_block
name_in_doc      = doc_a_lower.count("priya deshmukh") >= 2   # should appear multiple times
no_placeholder   = "[your full name]" not in doc_a_lower       # no placeholder since name was given

print("\nCHECKS TEST A:")
checks_a = {
    "Name 'Priya Deshmukh' in COMPLAINANT DETAILS section" : name_in_details,
    "Name appears in ≥2 sections (details + signature/decl)": name_in_doc,
    "No [Your Full Name] placeholder (name was provided)"  : no_placeholder,
    "No citation warning block"                            : "VERIFICATION NOTICE" not in doc_a,
}
pass_a = True
for lbl, ok in checks_a.items():
    status = "PASS" if ok else "FAIL"
    if not ok: pass_a = False
    print(f"  [{status}] {lbl}")
print(f"\n  TEST A: {'ALL PASS' if pass_a else 'SOME FAILED'}")

# ── Test B: Nashik RTI — name NOT given (placeholder), but phone+email given ──
RTI_DESC = (
    "I want to file an RTI with the Nashik Municipal Corporation, Water "
    "Supply Department. My contact number is 9823456789 and email is "
    "citizen.nashik@gmail.com. I am seeking: (1) total budget sanctioned "
    "for the Nashik Water Supply Improvement Project Phase II for FY 2024-25, "
    "(2) list of contractors awarded and contract amounts, (3) current "
    "completion status of each sub-project, and (4) inspection and quality "
    "reports issued for completed works."
)

print("\n" + "=" * 70)
print("  TEST B — Nashik RTI (no name given → placeholder must be grammatical)")
print("=" * 70)
res_b = svc.generate_legal_document("rti_application", RTI_DESC)
doc_b = res_b["content"]
print("\nGENERATED DOCUMENT:\n" + "-" * 60)
print(doc_b)
print("-" * 60)

doc_b_lower = doc_b.lower()

# Grammar check: "I, [Your Full Name]," must appear (not "I, hereby" or "I, declare")
# We look for "I, [your full name]" pattern in the declaration section
decl_idx = doc_b_lower.find("declaration")
decl_section = doc_b_lower[decl_idx:decl_idx+400] if decl_idx > 0 else doc_b_lower[-400:]

grammatical_decl  = "i, [your full name]" in decl_section or "i, [your full name]" in doc_b_lower
dangling_comma    = bool(re.search(r"\bI,\s+hereby\b", doc_b, re.IGNORECASE))
phone_consistent  = "9823456789" in doc_b   # provided phone must appear
email_consistent  = "citizen.nashik@gmail.com" in doc_b  # provided email must appear
placeholder_name  = "[your full name]" in doc_b_lower  # name NOT given → placeholder expected

print("\nCHECKS TEST B:")
checks_b = {
    "'I, [Your Full Name], hereby declare...' grammatically correct": grammatical_decl,
    "No dangling 'I, hereby declare' (broken grammar)"              : not dangling_comma,
    "[Your Full Name] placeholder present (name not given)"         : placeholder_name,
    "Provided phone 9823456789 appears in document"                 : phone_consistent,
    "Provided email citizen.nashik@gmail.com appears in document"   : email_consistent,
    "No citation warning block"                                     : "VERIFICATION NOTICE" not in doc_b,
}
pass_b = True
for lbl, ok in checks_b.items():
    status = "PASS" if ok else "FAIL"
    if not ok: pass_b = False
    print(f"  [{status}] {lbl}")
print(f"\n  TEST B: {'ALL PASS' if pass_b else 'SOME FAILED'}")

print("\n" + "=" * 70)
overall = pass_a and pass_b
print("OVERALL:", "BOTH TESTS PASS" if overall else "SOME TESTS FAILED")
print("=" * 70)
