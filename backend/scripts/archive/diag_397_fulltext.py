"""Print full text of IPC chunks at page_label 98 and 99 to see §397 text."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.vector_service import _get_citizen_vectorstore
vs = _get_citizen_vectorstore()

print("=== All IPC chunks at page_label 98 ===")
r = vs.similarity_search("robbery dacoity deadly weapon", k=40,
                         filter={"law_name": "Indian Penal Code"})
for d in r:
    pl = str(d.metadata.get("page_label", ""))
    if pl in ("98", "99"):
        print(f"\n--- page_label={pl} ---")
        print(d.page_content)

print("\n=== Direct 'deadly weapon' text-match ===")
r2 = vs.similarity_search("armed with any deadly weapon", k=20,
                          filter={"law_name": "Indian Penal Code"})
for d in r2:
    flag = "*** DEADLY WEAPON ***" if "deadly weapon" in d.page_content.lower() else ""
    pl = d.metadata.get("page_label", "?")
    snippet = d.page_content[:120].replace("\n", " ")
    print(f"  page_label={pl}  {flag}  {snippet!r}")
