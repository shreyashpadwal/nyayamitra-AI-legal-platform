import os, sys
# Add current directory to path
sys.path.append(os.getcwd())

from app.db.database import SessionLocal, engine
from app.db.models import Base, CaseMetadata

# Standardized paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "data", "pdfs")

def populate_from_files():
    db = SessionLocal()
    try:
        # Clear existing
        db.query(CaseMetadata).delete()
        
        files = [f for f in os.listdir(PDF_DIR) if f.startswith("judgment_") and f.endswith(".pdf")]
        print(f"📄 Found {len(files)} judgments. Populating metadata...")
        
        for f in sorted(files):
            # judgment_000.pdf -> "Judgment 000"
            case_id = f.replace(".pdf", "").replace("_", " ").title()
            
            case = CaseMetadata(
                case_name=case_id,
                year=2024, # Default year
                case_type="Criminal",
                pdf_path=os.path.join("data", "pdfs", f), # Relative path for predictability
                link="N/A"
            )
            db.add(case)
        
        db.commit()
        print(f"✅ Successfully populated {len(files)} cases into PostgreSQL.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_from_files()
