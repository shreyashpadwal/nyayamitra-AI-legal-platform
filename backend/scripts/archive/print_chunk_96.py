"""Print all IPC chunks at page_label == '96' from the citizen FAISS index."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings

vs = FAISS.load_local(
    "data/vectors/citizen",
    SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2"),
    allow_dangerous_deserialization=True,
)

hits = [
    doc for doc in vs.docstore._dict.values()
    if str(doc.metadata.get("page_label", "")) == "96"
    and doc.metadata.get("law_name") == "Indian Penal Code"
]

print(f"Found {len(hits)} chunk(s) with page_label='96', law_name='Indian Penal Code'\n")
for i, doc in enumerate(hits, 1):
    print(f"=== Chunk {i} ===")
    print("METADATA:", doc.metadata)
    print("CONTENT:")
    print(doc.page_content)
    print()
