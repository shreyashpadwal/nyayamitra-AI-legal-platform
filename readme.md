# ⚖️ AI Legal Assistant for Indian Laws (RAG-Based)

> An AI-powered chatbot that answers legal questions using Retrieval-Augmented Generation (RAG) with Indian law documents.

---

## 📁 Project File Structure

```
legal-assistant/
│
├── backend/                        ← FastAPI Python Backend
│   ├── main.py                     ← FastAPI app entry point
│   ├── rag_pipeline.py             ← Core RAG logic (embed + retrieve + generate)
│   ├── ingest.py                   ← Script to load PDFs and build vector DB
│   ├── requirements.txt            ← Python dependencies
│   ├── .env                        ← API keys (not committed to git)
│   └── data/
│       ├── raw_pdfs/               ← Put downloaded PDFs here
│       └── chroma_db/              ← Auto-created vector database folder
│
├── frontend/                       ← React Frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.jsx                 ← Root component
│   │   ├── main.jsx                ← React entry point
│   │   ├── index.css               ← Global styles
│   │   └── components/
│   │       ├── ChatWindow.jsx      ← Chat UI component
│   │       ├── MessageBubble.jsx   ← Individual message display
│   │       └── SourceCard.jsx      ← Shows cited law sections
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md                       ← This file
```

---

## 🌊 System Flowchart

```
USER TYPES QUESTION
        │
        ▼
  [React Frontend]
  Sends HTTP POST to /ask
        │
        ▼
  [FastAPI Backend]
  Receives question
        │
        ▼
  [Sentence Transformer]
  Converts question → Embedding vector
        │
        ▼
  [ChromaDB Vector Search]
  Finds Top 3-5 most relevant law chunks
        │
        ▼
  [Prompt Builder]
  System prompt + Retrieved chunks + User question
        │
        ▼
  [LLM - Groq API (Free)]
  Generates answer with citations
        │
        ▼
  [FastAPI Response]
  Returns answer + source sections
        │
        ▼
  [React Frontend]
  Displays answer + source cards
```

---

## 📚 Dataset / PDF Downloads

Download these FREE official PDFs and place them in `backend/data/raw_pdfs/`

| Document | Source | Direct Link |
|---|---|---|
| Indian Constitution | India Code | https://www.indiacode.nic.in/bitstream/123456789/15240/1/constitution_of_india.pdf |
| Indian Penal Code (IPC) | India Code | https://www.indiacode.nic.in/bitstream/123456789/2263/1/A1860-45.pdf |
| Consumer Protection Act 2019 | India Code | https://www.indiacode.nic.in/bitstream/123456789/13451/1/consumer_protection_act_2019.pdf |
| RTI Act 2005 | Central Information Commission | https://rti.gov.in/rti-act.pdf |
| Code of Criminal Procedure (CrPC) | India Code | https://www.indiacode.nic.in/bitstream/123456789/1611/3/AAA1974______02.pdf |

> ⚠️ If any link is broken, visit https://www.indiacode.nic.in and search for the act name.

---

## 🔑 Free LLM API - Groq (No Cost)

We use **Groq API** (completely free, fast) instead of paid OpenAI.

1. Go to https://console.groq.com
2. Sign up for free
3. Create an API key
4. Add it to your `.env` file

Groq gives you free access to **Llama 3**, **Mixtral**, and **Gemma** models.

---

## ⚙️ Environment Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

---

### Backend Setup

```bash
# 1. Create project folder
mkdir legal-assistant && cd legal-assistant

# 2. Create backend folder
mkdir backend && cd backend

# 3. Create virtual environment
python -m venv venv

# 4. Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Create .env file and add your Groq API key
# (See .env section below)

# 7. Download PDFs into backend/data/raw_pdfs/

# 8. Run ingestion to build vector DB (ONE TIME ONLY)
python ingest.py

# 9. Start FastAPI server
uvicorn main:app --reload --port 8000
```

---

### Frontend Setup

```bash
# From project root
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Open browser at http://localhost:5173
```

---

## 📦 requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.1
python-dotenv==1.0.1
langchain==0.2.6
langchain-community==0.2.6
langchain-groq==0.1.6
chromadb==0.5.3
sentence-transformers==3.0.1
pypdf==4.2.0
pydantic==2.7.4
```

---

## 🔐 .env File (backend/.env)

```
GROQ_API_KEY=your_groq_api_key_here
```

---

## 💻 All Backend Code

### backend/ingest.py
*(Run once to load PDFs into ChromaDB)*

```python
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

PDF_DIR = "data/raw_pdfs"
CHROMA_DIR = "data/chroma_db"

def ingest():
    print("📄 Loading PDFs...")
    all_docs = []

    for filename in os.listdir(PDF_DIR):
        if filename.endswith(".pdf"):
            path = os.path.join(PDF_DIR, filename)
            loader = PyPDFLoader(path)
            docs = loader.load()
            # Tag each doc with the law name
            for doc in docs:
                doc.metadata["law_name"] = filename.replace(".pdf", "")
            all_docs.extend(docs)
            print(f"  ✅ Loaded: {filename} ({len(docs)} pages)")

    print(f"\n🔪 Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(all_docs)
    print(f"  Total chunks: {len(chunks)}")

    print("\n🧠 Creating embeddings and saving to ChromaDB...")
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )
    vectorstore.persist()
    print(f"\n✅ Done! Vector database saved to {CHROMA_DIR}")

if __name__ == "__main__":
    ingest()
```

---

### backend/rag_pipeline.py

```python
import os
from dotenv import load_dotenv
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate

load_dotenv()

CHROMA_DIR = "data/chroma_db"

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings
)

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama3-8b-8192",
    temperature=0.2
)

PROMPT_TEMPLATE = """
You are a legal assistant specialized in Indian law.
Answer the user's question based ONLY on the provided legal context below.
Always cite the section numbers or article numbers you are referring to.
If the answer is not found in the context, say: "I could not find relevant information in the legal database. Please consult a qualified lawyer."
Add a disclaimer at the end: "⚠️ This is for informational purposes only and not a substitute for professional legal advice."

Legal Context:
{context}

User Question:
{question}

Answer:
"""

def get_answer(question: str):
    # Step 1: Retrieve relevant chunks
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    relevant_docs = retriever.get_relevant_documents(question)

    if not relevant_docs:
        return {
            "answer": "No relevant legal information found. Please consult a lawyer.",
            "sources": []
        }

    # Step 2: Build context
    context = "\n\n---\n\n".join([doc.page_content for doc in relevant_docs])

    # Step 3: Build sources list
    sources = []
    seen = set()
    for doc in relevant_docs:
        law = doc.metadata.get("law_name", "Unknown")
        page = doc.metadata.get("page", "?")
        key = f"{law}-{page}"
        if key not in seen:
            sources.append({
                "law": law,
                "page": page,
                "excerpt": doc.page_content[:300] + "..."
            })
            seen.add(key)

    # Step 4: Generate answer
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": question})

    return {
        "answer": response.content,
        "sources": sources
    }
```

---

### backend/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_pipeline import get_answer

app = FastAPI(title="Legal Assistant API")

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

@app.get("/")
def root():
    return {"message": "Legal Assistant API is running"}

@app.post("/ask")
def ask_question(body: QuestionRequest):
    result = get_answer(body.question)
    return result

@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## 💻 All Frontend Code

### Frontend Setup Commands

```bash
cd legal-assistant
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install axios
```

---

### frontend/src/index.css

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Segoe UI', sans-serif;
  background: #0f1117;
  color: #e8e8e8;
  height: 100vh;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1d27; }
::-webkit-scrollbar-thumb { background: #3d4263; border-radius: 3px; }
```

---

### frontend/src/App.jsx

```jsx
import ChatWindow from './components/ChatWindow'

function App() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#1a1d2e',
        padding: '16px 24px',
        borderBottom: '1px solid #2d3250',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        <span style={{ fontSize: '28px' }}>⚖️</span>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', color: '#7c83f5' }}>
            Indian Legal Assistant
          </h1>
          <p style={{ fontSize: '12px', color: '#6b7280' }}>
            Powered by RAG + Indian Law Documents
          </p>
        </div>
      </header>
      <ChatWindow />
    </div>
  )
}

export default App
```

---

### frontend/src/components/ChatWindow.jsx

```jsx
import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import MessageBubble from './MessageBubble'
import SourceCard from './SourceCard'

const SAMPLE_QUESTIONS = [
  "What are my rights if police arrest me?",
  "How do I file an RTI application?",
  "What is the punishment for theft in IPC?",
  "What to do if a product I bought is defective?",
  "What are Fundamental Rights in Indian Constitution?"
]

export default function ChatWindow() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Namaste! 🙏 I'm your Indian Legal Assistant. Ask me anything about Indian laws — IPC, Constitution, RTI, Consumer Protection Act, and more.",
      sources: []
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async (question) => {
    const q = question || input.trim()
    if (!q) return

    setMessages(prev => [...prev, { role: 'user', content: q, sources: [] }])
    setInput('')
    setLoading(true)

    try {
      const res = await axios.post('http://localhost:8000/ask', { question: q })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources || []
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Error connecting to server. Make sure the backend is running on port 8000.',
        sources: []
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sample questions */}
      <div style={{ padding: '12px 20px', background: '#13151f', borderBottom: '1px solid #1e2235', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {SAMPLE_QUESTIONS.map((q, i) => (
          <button key={i} onClick={() => sendMessage(q)} style={{
            background: '#1e2235', border: '1px solid #2d3250', color: '#9ca3af',
            padding: '6px 12px', borderRadius: '20px', fontSize: '12px', cursor: 'pointer',
            transition: 'all 0.2s'
          }}
            onMouseOver={e => e.target.style.color = '#7c83f5'}
            onMouseOut={e => e.target.style.color = '#9ca3af'}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble role={msg.role} content={msg.content} />
            {msg.sources?.length > 0 && (
              <div style={{ marginTop: '8px', marginLeft: msg.role === 'user' ? 'auto' : '0', maxWidth: '80%' }}>
                <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>📚 Sources:</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {msg.sources.map((src, j) => <SourceCard key={j} source={src} />)}
                </div>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#2d3250', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>⚖️</div>
            <div style={{ background: '#1a1d2e', padding: '12px 16px', borderRadius: '12px', display: 'flex', gap: '6px' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: '8px', height: '8px', borderRadius: '50%', background: '#7c83f5',
                  animation: 'bounce 1.2s infinite', animationDelay: `${i * 0.2}s`
                }} />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '16px 20px', background: '#1a1d2e', borderTop: '1px solid #2d3250', display: 'flex', gap: '12px' }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="Ask about Indian laws... (e.g. What are my arrest rights?)"
          style={{
            flex: 1, background: '#0f1117', border: '1px solid #2d3250', color: '#e8e8e8',
            padding: '12px 16px', borderRadius: '10px', fontSize: '14px', outline: 'none'
          }}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? '#2d3250' : '#7c83f5',
            color: 'white', border: 'none', padding: '12px 20px',
            borderRadius: '10px', cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            fontWeight: '600', fontSize: '14px', transition: 'background 0.2s'
          }}
        >
          {loading ? '...' : 'Ask →'}
        </button>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  )
}
```

---

### frontend/src/components/MessageBubble.jsx

```jsx
export default function MessageBubble({ role, content }) {
  const isUser = role === 'user'
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', alignItems: 'flex-start', gap: '10px' }}>
      {!isUser && (
        <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#2d3250', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '18px' }}>⚖️</div>
      )}
      <div style={{
        maxWidth: '75%',
        background: isUser ? '#3d4499' : '#1a1d2e',
        color: '#e8e8e8',
        padding: '14px 18px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        fontSize: '14px',
        lineHeight: '1.7',
        border: '1px solid ' + (isUser ? '#4d54b5' : '#2d3250'),
        whiteSpace: 'pre-wrap'
      }}>
        {content}
      </div>
      {isUser && (
        <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#3d4499', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>👤</div>
      )}
    </div>
  )
}
```

---

### frontend/src/components/SourceCard.jsx

```jsx
export default function SourceCard({ source }) {
  return (
    <div style={{
      background: '#13151f',
      border: '1px solid #2d3250',
      borderLeft: '3px solid #7c83f5',
      borderRadius: '8px',
      padding: '10px 14px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ fontSize: '12px', fontWeight: '600', color: '#7c83f5' }}>
          📄 {source.law}
        </span>
        <span style={{ fontSize: '11px', color: '#6b7280' }}>Page {source.page}</span>
      </div>
      <p style={{ fontSize: '12px', color: '#9ca3af', lineHeight: '1.5' }}>
        {source.excerpt}
      </p>
    </div>
  )
}
```

---

## 🚀 Step-by-Step: What to Run and When

```
Step 1: Download PDFs → place in backend/data/raw_pdfs/
Step 2: cd backend → pip install -r requirements.txt
Step 3: Create .env → add GROQ_API_KEY
Step 4: python ingest.py      ← ONE TIME, builds ChromaDB
Step 5: uvicorn main:app --reload  ← Start backend
Step 6: cd frontend → npm install → npm run dev  ← Start frontend
Step 7: Open http://localhost:5173
```

---

## ❓ Viva Questions You Must Prepare

**Q: What is RAG?**
> RAG = Retrieval-Augmented Generation. Instead of relying only on LLM's training data, we first retrieve relevant documents from our custom database, then pass them as context to the LLM to generate grounded answers.

**Q: Why RAG instead of fine-tuning?**
> Fine-tuning is expensive, requires large GPU, and the model can still hallucinate. RAG is cheaper, updatable (just add new PDFs), and always cites real source documents.

**Q: How is hallucination reduced?**
> The prompt strictly says "Answer ONLY using the provided context." If the answer isn't in the retrieved chunks, the model is instructed to say "not found."

**Q: Why chunking?**
> LLMs have token limits. We can't pass 500 pages to the LLM. Chunking splits documents into 800-word pieces so we pass only the top relevant chunks.

**Q: How do embeddings work?**
> Sentence Transformers convert text into 384-dimensional vectors. Similar meaning = similar vectors = closer in vector space. ChromaDB finds the closest vectors to the query vector.

---

## 🎓 Project Title Options

- "AI-Powered Legal Assistant for Indian Laws using RAG"
- "LegalGPT India – RAG-Based Legal Information System"
- "Intelligent Legal Chatbot using ChromaDB and Llama 3"

---

## ⚠️ Important Disclaimer

This system is for **educational and informational purposes only**. It is not a substitute for professional legal advice. Always consult a qualified lawyer for legal matters.

---

*Built with: FastAPI + LangChain + ChromaDB + Sentence Transformers + Groq (Llama 3) + React + Vite*