import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import time

load_dotenv()

# Standardized paths for the restructured project
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(APP_DIR)
CITIZEN_FAISS_DIR = os.path.join(BASE_DIR, "data", "vectors", "citizen")
LAWYER_FAISS_DIR  = os.path.join(BASE_DIR, "data", "judgments_index")

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

def load_vectorstore(path: str, index_name: str = "index"):
    if not os.path.exists(path) or not os.listdir(path):
        print(f"⚠️ Vector store not found at {path}")
        return None
    return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True, index_name=index_name)

class VectorService:
    def __init__(self):
        self.citizen_vs = load_vectorstore(CITIZEN_FAISS_DIR)
        self.lawyer_vs  = load_vectorstore(LAWYER_FAISS_DIR, index_name="lawyer_case_index")
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.6
        )

    def get_citizen_answer(self, question: str, intent: str, instruction: str):
        if not self.citizen_vs:
            return {"answer": "Knowledge base not loaded.", "sources": []}
        
        print(f"DEBUG: Starting citizen search for: {question[:30]}...")
        start = time.time()
        docs = self.citizen_vs.similarity_search(question, k=3)
        print(f"DEBUG: Search took {time.time()-start:.2f}s")
        
        context = "\n\n".join([f"[{d.metadata.get('law_name', 'Law')}, pg {d.metadata.get('page','?')}]\n{d.page_content}" for d in docs])
        
        system_prompt = "You are a friendly Indian legal assistant. Use plain English. Keep it under 200 words."
        prompt = f"Context:\n{context}\n\nUser Intent: {intent}\nInstruction: {instruction}\n\nQuestion: {question}"
        
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        
        print(f"DEBUG: Invoking LLM...")
        start = time.time()
        response = self.llm.invoke(messages)
        print(f"DEBUG: LLM took {time.time()-start:.2f}s")
        
        sources = [{"law": d.metadata.get("law_name"), "page": d.metadata.get("page")} for d in docs]
        return {"answer": response.content, "sources": sources}

    def find_similar_cases(self, query: str, k: int = 5):
        if not self.lawyer_vs:
            return []
        
        docs_with_scores = self.lawyer_vs.similarity_search_with_score(query, k=k)
        results = []
        for doc, score in docs_with_scores:
            case_id = doc.metadata.get("case_id", "Unknown Case")
            results.append({
                "case_name": case_id.replace("_", " ").title(),
                "year": doc.metadata.get("year", "N/A"),
                "excerpt": doc.page_content[:500] + "...",
                "similarity": round(1 - score, 3),
                "pdf_path": doc.metadata.get("pdf_path")
            })
        return results

    def get_litigation_strategy(self, query: str, cases: list):
        context = "\n".join([f"Case: {c['case_name']}\nExcerpt: {c['excerpt']}" for c in cases])
        prompt = f"""
            You are a senior Indian criminal law researcher assisting in litigation strategy.
            
            Task:
            Provide a detailed litigation strategy and analyze actual Indian Supreme Court/High Court precedents based on the provided similar cases for the following situation:
            {query}

            Similar Cases Context:
            {context}

            Instructions for Output:
            1. Analyze the situation considering:
               - Lack of direct evidence
               - No recovery from possession
               - Weak or incomplete chain of circumstantial evidence
               - Mere suspicion or presence at scene

            2. For each relevant case from the context:
               - Case Name
               - Court Name
               - Year
               - Citation (if available in metadata)
               - Brief facts (2-3 lines)
               - Legal principle laid down
               - Exact relevant observation (if possible)
               - Application to present case: Explain how it applies to the fact pattern.

            3. Format strictly as follows for each case:
               CASE [Number]:
               Case Name:
               Court:
               Citation:
               Facts:
               Held:
               Relevant Observation:
               Application to Present Case:

            4. End with:
               Suggested defence argument structure based on above precedents.

            CRITICAL: Do NOT provide placeholder judgments like 'Judgment 119'. Use the real case names provided in the context.
        """
        
        messages = [
            SystemMessage(content="You are a Senior Indian Advocate and criminal law researcher."),
            HumanMessage(content=prompt)
        ]
        print(f"DEBUG: Generating Litigation Strategy for: {query[:30]}...")
        start = time.time()
        strategy = self.llm.invoke(messages).content
        print(f"DEBUG: Strategy generation took {time.time()-start:.2f}s")
        return strategy

    def get_case_specific_answer(self, question: str, case_name: str):
        if not self.lawyer_vs:
            return "Lawyer knowledge base not loaded."
        
        # Search specifically for chunks belonging to this case
        # Note: Filtering in FAISS can be done via metadata if the index facilitates it
        docs = self.lawyer_vs.similarity_search(f"Case: {case_name}. Question: {question}", k=5)
        context = "\n\n".join([d.page_content for d in docs])
        
        prompt = f"Using the following excerpts from the case '{case_name}', answer the question: {question}\n\nContext:\n{context}"
        
        messages = [
            SystemMessage(content="You are a legal research assistant analyzing a specific Indian Supreme Court judgment. Answer based ONLY on the provided context."),
            HumanMessage(content=prompt)
        ]
        return self.llm.invoke(messages).content

    def generate_legal_document(self, doc_type: str, description: str):
        prompts = {
            "police_complaint": """
                Draft a formal Police Complaint (First Information Report - FIR) for the Indian Police.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters for bolding. 
                Use only plain text with standard capitalization for headings.
                
                Include:
                - To: The Station House Officer (SHO), [Police Station Name]
                - Subject: Formal complaint regarding [Topic]
                - Details of Incident: {desc}
                - Legal Sections: Mention relevant IPC sections (e.g., Section 379 for Theft).
                - Request: A request to register an FIR and take necessary action.
                Format it like a professional physical letter.
            """,
            "consumer_complaint": """
                Draft a formal Consumer Complaint under the Consumer Protection Act 2019.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters for bolding. 
                Use only plain text with standard capitalization for headings.
                
                Include:
                - Before the District Consumer Disputes Redressal Commission
                - Subject: Complaint against [Company/Service] for [Deficiency]
                - Facts: {desc}
                - Prayer: Request for refund, compensation, and legal costs.
                Format it strictly like a formal legal petition.
            """,
            "rti_application": """
                Draft a formal RTI Application under the Right to Information Act 2005.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters for bolding. 
                Use only plain text with standard capitalization for headings.
                
                Include:
                - To: The Public Information Officer (PIO), [Department Name]
                - Subject: Request for information under RTI Act 2005
                - Information Sought: {desc}
                - Declaration: A statement that I am a citizen of India.
                Use the standard Government of India RTI format.
            """
        }
        
        template = prompts.get(doc_type, "Draft a professional legal document in plain text (no markdown) based on: {desc}")
        prompt = template.format(desc=description)
        
        messages = [
            SystemMessage(content="You are an expert Legal Draftsman in India. You write documents for physical submission. NEVER use markdown bolding (**) or any other markdown syntax. Use only plain text and standard letter formatting."),
            HumanMessage(content=prompt)
        ]
        return self.llm.invoke(messages).content

    def generate_lawyer_litigation_document(self, doc_type: str, data: dict):
        """Generates professional litigation documents for lawyers with specific prompts."""
        prompts = {
            "bail": f"""
                You are a senior Indian criminal lawyer drafting a professional bail application.
                Structure the document as:
                1. Court heading
                2. Case details
                3. Brief facts
                4. Grounds for bail:
                   - No criminal antecedents
                   - No recovery
                   - No direct evidence
                   - Weak circumstantial chain
                   - Long custody (if applicable)
                5. Legal principles
                6. Prayer clause
                Use formal Indian court format.
                Details: {data.get('details')}
            """,
            "legal_notice": f"""
                You are a professional Indian advocate drafting a legal notice.
                Structure:
                1. Sender details
                2. Recipient details
                3. Facts
                4. Legal breach
                5. Demand
                6. Time limit
                7. Legal consequences
                Use professional legal tone.
                Details: {data.get('details')}
            """,
            "written_arguments": f"""
                You are a senior advocate preparing written arguments.
                Structure:
                1. Brief facts
                2. Issues
                3. Evidence analysis
                4. Contradictions
                5. Relevant legal principles
                6. Benefit of doubt
                7. Prayer
                Use structured court format.
                Details: {data.get('details')}
            """
        }
        
        prompt = prompts.get(doc_type, f"Draft a professional legal document based on: {data.get('details')}")
        
        messages = [
            SystemMessage(content="You are a Senior Indian Advocate. You write high-quality, professional court documents. Use plain text formatting, no markdown stars or bolding."),
            HumanMessage(content=prompt)
        ]
        return self.llm.invoke(messages).content

vector_service = VectorService()
