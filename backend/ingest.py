import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS

PDF_DIR = "data/raw_pdfs"
FAISS_DIR = "data/faiss_db"

def ingest():
    # Create dirs if they don't exist
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(FAISS_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"❌ No PDFs found in {PDF_DIR}/")
        print("   Please download the Indian law PDFs and place them there.")
        print("   Check README.md for download links.")
        return

    print("📄 Loading PDFs...")
    all_docs = []

    for filename in pdf_files:
        path = os.path.join(PDF_DIR, filename)
        loader = PyPDFLoader(path)
        docs = loader.load()
        # Tag each doc with the law name
        law_name = filename.replace(".pdf", "").replace("_", " ").title()
        for doc in docs:
            doc.metadata["law_name"] = law_name
        all_docs.extend(docs)
        print(f"  ✅ Loaded: {filename} ({len(docs)} pages)")

    print(f"\n🔪 Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(all_docs)
    print(f"  Total chunks created: {len(chunks)}")

    print("\n🧠 Creating embeddings (this may take a few minutes)...")
    print("   Using free local model: all-MiniLM-L6-v2")
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    print("\n💾 Saving to FAISS...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(FAISS_DIR)
    print(f"\n✅ Done! FAISS database saved to '{FAISS_DIR}'")
    print(f"   Total vectors stored: {len(chunks)}")
    print("\n🚀 You can now start the backend: uvicorn main:app --reload")

if __name__ == "__main__":
    ingest()