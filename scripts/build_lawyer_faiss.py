"""
Build FAISS index for the LAWYER module from Supreme Court judgment PDFs.
Run this from the project root:
    python scripts/build_lawyer_faiss.py
"""

import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS

# Relative paths from project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR  = os.path.join(BASE_DIR, "backend", "data", "pdfs")
FAISS_DIR = os.path.join(BASE_DIR, "backend", "data", "judgments_index")

def build():
    os.makedirs(FAISS_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"❌ No PDFs in {PDF_DIR}")
        return

    print(f"📄 Loading {len(pdf_files)} judgment PDFs...")
    all_docs = []
    skipped = 0

    for filename in pdf_files:
        path = os.path.join(PDF_DIR, filename)
        try:
            loader = PyPDFLoader(path)
            docs = loader.load()
            if not docs:
                skipped += 1
                continue
            case_id = filename.replace(".pdf", "")
            for doc in docs:
                doc.metadata["case_id"] = case_id
                doc.metadata["source"] = filename
            all_docs.extend(docs)
            print(f"  ✅ {filename} ({len(docs)} pages)")
        except Exception as e:
            print(f"  ❌ Skipped {filename}: {e}")
            skipped += 1

    if not all_docs:
        print("❌ No valid documents loaded. Cannot build FAISS index.")
        return

    print(f"\n📊 Loaded {len(all_docs)} pages from {len(pdf_files)-skipped} PDFs (skipped {skipped})")
    
    print("\n🔪 Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(all_docs)
    print(f"  Total chunks: {len(chunks)}")

    print("\n🧠 Creating embeddings (this takes a few minutes)...")
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    print("\n💾 Building + saving FAISS index...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(FAISS_DIR)

    print(f"\n✅ Lawyer FAISS index saved to: {FAISS_DIR}")
    print(f"   Vectors stored: {len(chunks)}")

if __name__ == "__main__":
    build()
