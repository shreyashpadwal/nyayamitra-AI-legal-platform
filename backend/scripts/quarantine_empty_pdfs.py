"""
quarantine_empty_pdfs.py
────────────────────────
One-off maintenance script for NyayaMitra.

What it does
────────────
1. Scans backend/data/pdfs/ for 0-byte or unreadable PDF files.
2. Moves any bad files to backend/data/pdfs/_quarantine/ (never deletes).
3. Cross-checks each bad filename against:
   a. CaseMetadata rows in the SQLite database (pdf_path column).
   b. FAISS lawyer judgment index metadata (lawyer_case_index).
   Logs a WARNING for every match — those index entries now reference
   content that doesn't exist.

Usage
─────
    cd backend
    python -m scripts.quarantine_empty_pdfs          # from backend/ dir
  or
    python backend/scripts/quarantine_empty_pdfs.py  # from repo root

Requirements: the normal backend venv (sqlalchemy, faiss-cpu, etc.)
"""

import os
import sys
import shutil
import logging
import struct

# ── path setup so relative imports work when run directly ────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR  = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────────────
PDF_DIR        = os.path.join(BACKEND_DIR, "data", "pdfs")
QUARANTINE_DIR = os.path.join(PDF_DIR, "_quarantine")
DB_PATH        = os.path.join(BACKEND_DIR, "legal_db.sqlite")   # adjust if different
FAISS_DIR      = os.path.join(BACKEND_DIR, "data", "judgments_index")

PDF_MAGIC = b"%PDF"  # first 4 bytes of a valid PDF


def is_bad_pdf(path: str) -> tuple[bool, str]:
    """Return (bad, reason) — bad=True when the file should be quarantined."""
    size = os.path.getsize(path)
    if size == 0:
        return True, "0 bytes"
    # Try reading the PDF magic bytes
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        if header != PDF_MAGIC:
            return True, f"invalid PDF header ({header!r})"
    except OSError as e:
        return True, f"unreadable ({e})"
    return False, ""


def quarantine_files() -> list[str]:
    """Scan PDF_DIR, move bad files to QUARANTINE_DIR, return list of bad filenames."""
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    bad_files: list[str] = []

    entries = [
        f for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(PDF_DIR, f))
    ]
    log.info(f"Scanning {len(entries)} PDF files in {PDF_DIR} …")

    for filename in sorted(entries):
        filepath = os.path.join(PDF_DIR, filename)
        bad, reason = is_bad_pdf(filepath)
        if bad:
            dest = os.path.join(QUARANTINE_DIR, filename)
            shutil.move(filepath, dest)
            log.warning(f"QUARANTINED  {filename}  ({reason})  →  {dest}")
            bad_files.append(filename)

    if bad_files:
        log.info(f"{len(bad_files)} file(s) moved to quarantine.")
    else:
        log.info("No bad PDFs found — nothing to quarantine.")

    return bad_files


def check_database(bad_filenames: list[str]) -> None:
    """Check whether any bad filename appears in CaseMetadata.pdf_path."""
    if not bad_filenames:
        return

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        with engine.connect() as conn:
            for filename in bad_filenames:
                # pdf_path may be an absolute path or just a filename — check both
                rows = conn.execute(
                    text(
                        "SELECT id, case_name, pdf_path FROM case_metadata "
                        "WHERE pdf_path LIKE :pattern"
                    ),
                    {"pattern": f"%{filename}%"},
                ).fetchall()
                if rows:
                    for row in rows:
                        log.warning(
                            f"DB REFERENCE  CaseMetadata id={row[0]} "
                            f"case='{row[1]}' has pdf_path='{row[2]}' "
                            f"but {filename} was quarantined — index entry is now stale!"
                        )
                else:
                    log.info(f"DB: no CaseMetadata row references {filename}")
    except Exception as e:
        log.error(f"Could not check database ({DB_PATH}): {e}")


def check_faiss_metadata(bad_filenames: list[str]) -> None:
    """Check whether any bad filename appears in the FAISS index docstore metadata."""
    if not bad_filenames:
        return

    try:
        from langchain_community.vectorstores import FAISS
        from langchain_community.embeddings import SentenceTransformerEmbeddings

        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        vs = FAISS.load_local(
            FAISS_DIR,
            embeddings,
            allow_dangerous_deserialization=True,
            index_name="lawyer_case_index",
        )

        # Walk the docstore
        hits: dict[str, list] = {f: [] for f in bad_filenames}
        for doc_id, doc in vs.docstore._dict.items():
            pdf_path = doc.metadata.get("pdf_path", "") or ""
            filename  = doc.metadata.get("case_id", "")   # some loaders use case_id
            for bad in bad_filenames:
                if bad in pdf_path or bad in filename:
                    hits[bad].append({"doc_id": doc_id, "metadata": doc.metadata})

        for bad_file, matched_docs in hits.items():
            if matched_docs:
                log.warning(
                    f"FAISS REFERENCE  {len(matched_docs)} vector chunk(s) reference "
                    f"{bad_file} which was quarantined — "
                    f"first hit metadata: {matched_docs[0]['metadata']}"
                )
            else:
                log.info(f"FAISS: no chunks reference {bad_file}")

    except Exception as e:
        log.error(f"Could not check FAISS index ({FAISS_DIR}): {e}")


def main() -> None:
    log.info("=" * 60)
    log.info("NyayaMitra — PDF Quarantine Script")
    log.info("=" * 60)

    bad_files = quarantine_files()

    log.info("\n── Cross-checking database ──────────────────────────────────")
    check_database(bad_files)

    log.info("\n── Cross-checking FAISS index ───────────────────────────────")
    check_faiss_metadata(bad_files)

    log.info("\n── Done. ────────────────────────────────────────────────────")
    if bad_files:
        log.info(
            "Quarantined files are in:\n"
            f"  {QUARANTINE_DIR}\n\n"
            "Next steps:\n"
            "  1. Re-download the missing judgments and replace the quarantined copies.\n"
            "  2. Re-run the FAISS indexing pipeline to rebuild the vector store.\n"
            "  3. Remove stale CaseMetadata rows from the database if the judgments\n"
            "     cannot be recovered."
        )


if __name__ == "__main__":
    main()
