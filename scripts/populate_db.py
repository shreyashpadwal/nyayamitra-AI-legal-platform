import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, CaseMetadata
import os

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Portable paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "backend", "data", "filtered_cases.csv")

def populate_metadata():
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV not found at {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    db = SessionLocal()

    print(f"🔄 Populating {len(df)} cases into database...")
    
    # Clear existing to avoid duplicates if re-running
    db.query(CaseMetadata).delete()

    for _, row in df.iterrows():
        case = CaseMetadata(
            case_name=row.get("original_filename", "Supreme Court Judgment"),
            year=int(row.get("year", 0)),
            case_type=row.get("case_type", "Criminal"),
            pdf_path=row.get("local_path", ""),
            link=row.get("link", "")
        )
        db.add(case)

    db.commit()
    db.close()
    print("✅ Database populated with case metadata.")

if __name__ == "__main__":
    populate_metadata()
