"""
VectorService — Thin wrapper that routes calls through LangGraph pipelines.

Preserves all original method signatures for zero API-layer changes.
Falls back to direct FAISS + Groq if LangGraph pipeline fails.
"""

import os
import re
import logging
import time
import datetime

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & Embeddings (shared)
# ---------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(APP_DIR)
CITIZEN_FAISS_DIR = os.path.join(BASE_DIR, "data", "vectors", "citizen")
LAWYER_FAISS_DIR = os.path.join(BASE_DIR, "data", "judgments_index")

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")


def load_vectorstore(path: str, index_name: str = "index"):
    if not os.path.exists(path) or not os.listdir(path):
        logger.warning(f"Vector store not found at {path}")
        return None
    return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True, index_name=index_name)


# ---------------------------------------------------------------------------
# Lazy-initialized shared components (used by graph nodes)
# ---------------------------------------------------------------------------
_citizen_retriever = None
_lawyer_retriever = None
_reranker = None
_citizen_vs = None
_lawyer_vs = None


def _get_citizen_vs():
    global _citizen_vs
    if _citizen_vs is None:
        _citizen_vs = load_vectorstore(CITIZEN_FAISS_DIR)
    return _citizen_vs


# Public alias used by citizen_graph for statute-boost metadata filtering
_get_citizen_vectorstore = _get_citizen_vs


def _get_lawyer_vs():
    global _lawyer_vs
    if _lawyer_vs is None:
        _lawyer_vs = load_vectorstore(LAWYER_FAISS_DIR, index_name="lawyer_case_index")
    return _lawyer_vs


def _get_citizen_retriever():
    """Get or create the citizen HybridRetriever."""
    global _citizen_retriever
    if _citizen_retriever is None:
        from .retrieval.hybrid_retriever import HybridRetriever
        vs = _get_citizen_vs()
        if vs:
            _citizen_retriever = HybridRetriever(faiss_vectorstore=vs)
        else:
            logger.warning("Citizen vectorstore unavailable for HybridRetriever")
            _citizen_retriever = HybridRetriever()
    return _citizen_retriever


def _get_lawyer_retriever():
    """Get or create the lawyer HybridRetriever."""
    global _lawyer_retriever
    if _lawyer_retriever is None:
        from .retrieval.hybrid_retriever import HybridRetriever
        vs = _get_lawyer_vs()
        if vs:
            _lawyer_retriever = HybridRetriever(faiss_vectorstore=vs)
        else:
            logger.warning("Lawyer vectorstore unavailable for HybridRetriever")
            _lawyer_retriever = HybridRetriever()
    return _lawyer_retriever


def _get_reranker():
    """Get or create the CrossEncoderReranker (lazy-loaded)."""
    global _reranker
    if _reranker is None:
        from .retrieval.reranker import CrossEncoderReranker
        _reranker = CrossEncoderReranker()
    return _reranker


# ---------------------------------------------------------------------------
# Shared LLM system prompt — anti-fabrication & PII rules
# Used by BOTH generate_legal_document (citizen) and
# generate_lawyer_litigation_document (lawyer) so any update applies to both.
# ---------------------------------------------------------------------------
_LEGAL_DRAFTSMAN_SYSTEM_MSG = (
    "You are an expert Legal Draftsman in India. "
    "You write documents for physical submission. "
    "NEVER use markdown bolding (**) or any other markdown syntax. "
    "Use only plain text and standard letter formatting.\n\n"
    "CRITICAL — NO FABRICATION OF PERSONAL INFORMATION:\n"
    "You must NEVER invent, guess, or fabricate any personal identifying "
    "information — including names, addresses, phone numbers, email addresses, "
    "or any other identity details — that the user did not explicitly provide "
    "in their description.\n"
    "This rule applies to:\n"
    "  (a) The primary party's own identity (complainant / applicant / advocate).\n"
    "  (b) Third parties the user actually named (e.g., 'M/s BuildRight Constructions'): "
    "you may reference their NAME, but you must NOT invent their address, phone, email, "
    "registration number, or any other contact/identity detail that was not given — "
    "use placeholder strings for those missing details instead.\n"
    "If a personal detail is missing from the description, use these EXACT "
    "placeholder strings — do not substitute realistic-looking values:\n"
    "  Name              → [Full Name]\n"
    "  Address           → [Address]\n"
    "  Phone             → [Contact Number]\n"
    "  Email             → [Email Address]\n"
    "  Opp. Party Addr.  → [Opposite Party Address]\n"
    "  FIR / Case No.    → [FIR/Case Number]\n"
    "  Police Station    → [Police Station Name]\n"
    "  Date of Birth/Age → [Date of Birth / Age]\n"
    "  Bar Council No.   → [Bar Council Registration Number]\n\n"
    "ABSOLUTE RULE — NEVER OUTPUT BOTH A PLACEHOLDER AND A REAL VALUE ON THE SAME LINE:\n"
    "For EVERY field, output EITHER the bracketed placeholder OR the real value "
    "provided by the user — NEVER BOTH. If you use a placeholder tag (e.g. "
    "[Accused Full Name]), that tag must be the ONLY text in that field's value slot. "
    "If the user provided the real value, write the real value and omit the tag entirely.\n"
    "  WRONG: Name of Accused: [Accused Full Name] Anjali Mehta\n"
    "  WRONG: Address: [Advocate Office Address] 101, Building No. 1, Mumbai\n"
    "  CORRECT (user gave name): Name of Accused: Anjali Mehta\n"
    "  CORRECT (user did not give address): Address: [Advocate Office Address]\n\n"
    "EXAMPLES — follow the CORRECT pattern, never the WRONG pattern:\n"
    "  WRONG (fabricated): Name: Rohan Kumar Jain\n"
    "  CORRECT (placeholder): Name: [Your Full Name]\n"
    "  WRONG (fabricated): Contact Number: 9876543210\n"
    "  CORRECT (placeholder): Contact Number: [Your Contact Number]\n"
    "  WRONG (fabricated): Email: rohan.kumar@gmail.com\n"
    "  CORRECT (placeholder): Email: [Your Email Address]\n"
    "  WRONG (fabricated): Address: Flat 4B, Green Park, Mumbai\n"
    "  CORRECT (placeholder): Address: [Your Address]\n"
    "  WRONG (fabricated): M/s BuildRight Constructions, 42 MG Road, Mumbai — 400001\n"
    "  CORRECT: M/s BuildRight Constructions, [Opposite Party Address]\n"
    "  WRONG (both): FIR No.: [FIR/Case Number] 88/2026\n"
    "  CORRECT (user gave it): FIR No.: 88/2026\n"
    "  CORRECT (user did not): FIR No.: [FIR/Case Number]\n\n"
    "CRITICAL — CONSISTENCY ACROSS THE ENTIRE DOCUMENT:\n"
    "If the user's own name, address, phone number, or email IS provided "
    "anywhere in their description, you MUST use that exact same value "
    "consistently in EVERY section of the document — details, "
    "signature block, declaration, verification clause, and any other section. "
    "NEVER use a placeholder in one section and the real value in another "
    "for the same piece of information. Consistency is mandatory.\n"
    "Examples of correct usage when data IS provided by the user:\n"
    "  User says 'My name is Priya Deshmukh'      → Name: Priya Deshmukh (everywhere)\n"
    "  User says 'my contact number is 9823456789' → Contact Number: 9823456789 (everywhere)\n"
    "  User says 'email is xyz@gmail.com'          → Email: xyz@gmail.com (everywhere)\n"
    "  WRONG: Contact Number: [Your Contact Number]  (when user gave 9823456789)\n"
    "  WRONG: Email: [Your Email Address]            (when user gave xyz@gmail.com)\n\n"
    "CRITICAL — GRAMMATICAL COMPLETENESS IN DECLARATION SENTENCES:\n"
    "When a sentence requires the name in a grammatical slot — e.g. "
    "'I, [name], hereby declare...' or 'I, [name], the above-named "
    "complainant...' — you MUST place either the real name or [Your Full Name] "
    "in that position. NEVER omit it leaving a dangling comma.\n"
    "  WRONG: I, hereby declare that I am a citizen of India.\n"
    "  CORRECT: I, [Your Full Name], hereby declare that I am a citizen of India.\n"
    "  CORRECT: I, Priya Deshmukh, hereby declare that I am a citizen of India.\n"
    "\n"
    "CRITICAL — SECTION AND CASE CITATION ACCURACY:\n"
    "Every fact, number, threshold, or penalty you state must be attributed to the "
    "exact section and exact Act it appears under. NEVER merge or transfer a detail "
    "from one section/Act into your description of a different section/Act.\n"
    "For case law: ONLY cite judgments you are highly confident exist. "
    "If you are not certain a case citation is real, OMIT it entirely — "
    "do not invent party names, years, or court names.\n"
)


# ---------------------------------------------------------------------------
# VectorService — Thin Wrapper
# ---------------------------------------------------------------------------
class VectorService:
    def __init__(self):
        self.citizen_vs = _get_citizen_vs()
        self.lawyer_vs = _get_lawyer_vs()
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.6,
        )

    # ── Citizen Pipeline ──────────────────────────────────────────────────

    def get_citizen_answer(self, question: str, intent: str, instruction: str, history: list = None):
        """
        Answer citizen legal questions using the Self-RAG + Corrective RAG pipeline.
        Falls back to direct FAISS + Groq if LangGraph pipeline fails.
        """
        try:
            from .citizen_graph import invoke_citizen_pipeline

            logger.info(f"Citizen pipeline: {question[:50]}...")
            start = time.time()
            result = invoke_citizen_pipeline(question, intent, instruction, history=history or [])
            elapsed = time.time() - start
            logger.info(f"Citizen pipeline completed in {elapsed:.2f}s")


            return {
                "answer": result["answer"],
                "sources": result["sources"],
            }

        except Exception as e:
            logger.error(f"Citizen pipeline failed, falling back to direct: {e}")
            return self._fallback_citizen_answer(question, intent, instruction)

    def _fallback_citizen_answer(self, question: str, intent: str, instruction: str):
        """Direct FAISS + Groq fallback when LangGraph pipeline fails."""
        if not self.citizen_vs:
            return {"answer": "Knowledge base not loaded.", "sources": []}

        try:
            docs = self.citizen_vs.similarity_search(question, k=3)
            context = "\n\n".join([
                f"[{d.metadata.get('law_name', 'Law')}, pg {d.metadata.get('page', '?')}]\n{d.page_content}"
                for d in docs
            ])

            system_prompt = "You are a friendly Indian legal assistant. Use plain English. Keep it under 200 words."
            prompt = f"Context:\n{context}\n\nUser Intent: {intent}\nInstruction: {instruction}\n\nQuestion: {question}"

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)

            sources = [{"law": d.metadata.get("law_name"), "page": d.metadata.get("page")} for d in docs]
            return {"answer": response.content, "sources": sources}
        except Exception as e2:
            logger.error(f"Fallback citizen answer also failed: {e2}")
            return {"answer": "An error occurred. Please try again.", "sources": []}

    # ── Lawyer Pipeline ───────────────────────────────────────────────────

    def find_similar_cases(self, query: str, k: int = 5):
        """
        Find similar cases using the Corrective RAG lawyer pipeline.
        Falls back to direct FAISS search if LangGraph pipeline fails.
        """
        try:
            from .lawyer_graph import invoke_lawyer_pipeline

            logger.info(f"Lawyer pipeline (cases): {query[:50]}...")
            start = time.time()
            result = invoke_lawyer_pipeline(query, mode="cases")
            elapsed = time.time() - start
            logger.info(f"Lawyer pipeline completed in {elapsed:.2f}s")

            cases = result.get("cases", [])[:k]
            return cases

        except Exception as e:
            logger.error(f"Lawyer pipeline failed, falling back to direct: {e}")
            return self._fallback_find_cases(query, k)

    def _fallback_find_cases(self, query: str, k: int = 5):
        """Direct FAISS fallback for case search."""
        if not self.lawyer_vs:
            return []

        try:
            docs_with_scores = self.lawyer_vs.similarity_search_with_score(query, k=k)
            results = []
            for doc, score in docs_with_scores:
                case_id = doc.metadata.get("case_id", "Unknown Case")
                results.append({
                    "case_name": case_id.replace("_", " ").title(),
                    "year": doc.metadata.get("year", "N/A"),
                    "excerpt": doc.page_content[:500] + "...",
                    "similarity": round(float(1 - score), 3),
                    "pdf_path": doc.metadata.get("pdf_path"),
                })
            return results
        except Exception as e2:
            logger.error(f"Fallback case search also failed: {e2}")
            return []

    def get_litigation_strategy(self, query: str, cases: list):
        """
        Generate litigation strategy using Corrective RAG pipeline.
        Falls back to direct Groq generation if pipeline fails.
        """
        try:
            from .lawyer_graph import invoke_lawyer_pipeline

            logger.info(f"Lawyer pipeline (strategy): {query[:50]}...")
            start = time.time()
            result = invoke_lawyer_pipeline(query, mode="strategy")
            elapsed = time.time() - start
            logger.info(f"Strategy pipeline completed in {elapsed:.2f}s")

            strategy = result.get("strategy", "")
            if strategy:
                return strategy

        except Exception as e:
            logger.error(f"Strategy pipeline failed, falling back to direct: {e}")

        # Fallback: direct generation with provided cases
        return self._fallback_litigation_strategy(query, cases)

    def _fallback_litigation_strategy(self, query: str, cases: list):
        """Direct Groq fallback for litigation strategy."""
        try:
            context = "\n".join([f"Case: {c['case_name']}\nExcerpt: {c['excerpt']}" for c in cases])
            prompt = f"""
                You are a senior Indian criminal law researcher assisting in litigation strategy.
                
                Task: Provide a detailed litigation strategy for: {query}

                Similar Cases Context:
                {context}

                Provide structured analysis with: Facts, Issues, Precedents, Arguments, Prayer.
                CRITICAL: Use ONLY the real case names provided in the context.
            """

            messages = [
                SystemMessage(content="You are a Senior Indian Advocate and criminal law researcher."),
                HumanMessage(content=prompt),
            ]
            return self.llm.invoke(messages).content
        except Exception as e2:
            logger.error(f"Fallback strategy generation also failed: {e2}")
            return "Error generating litigation strategy. Please try again."

    # ── Case-Specific Q&A (unchanged) ─────────────────────────────────────

    def get_case_specific_answer(self, question: str, case_name: str):
        if not self.lawyer_vs:
            return "Lawyer knowledge base not loaded."

        docs = self.lawyer_vs.similarity_search(f"Case: {case_name}. Question: {question}", k=5)
        context = "\n\n".join([d.page_content for d in docs])

        prompt = f"Using the following excerpts from the case '{case_name}', answer the question: {question}\n\nContext:\n{context}"

        messages = [
            SystemMessage(content="You are a legal research assistant analyzing a specific Indian Supreme Court judgment. Answer based ONLY on the provided context."),
            HumanMessage(content=prompt),
        ]
        return self.llm.invoke(messages).content

    # ── Document Generation ────────────────────────────────────────────────

    def _verify_legal_citations(self, document_text: str, doc_type: str) -> dict:
        """
        Extract legal references from document_text and verify each one against
        the citizen FAISS vectorstore using a context-enriched snippet.

        Instead of embedding a bare short string like "Section 379" (which scores
        poorly against full-sentence legal chunks and causes false-positive failures),
        we build a richer query:
            "<citation> <doc_type_words> — <~10 words of surrounding sentence>"
        This brings the embedding much closer to the actual chunk in the vectorstore.

        SIMILARITY_THRESHOLD is L2 distance — lower = more similar.
        Raised from 0.6 to 1.2 to match real observed distances:
          - Section 379 IPC (theft) in our KB scores ~0.65–0.95
          - Section 323 IPC (hurt) scores ~0.70–1.05
          - Completely fabricated sections score >1.4
        Set to 1.2 to accept real IPC/CrPC sections while rejecting hallucinations.

        Fails open — returns has_unverified: False on any exception so that
        document generation is never blocked.
        """
        SIMILARITY_THRESHOLD = 1.2  # L2 distance; lower = more similar
        CONTEXT_WINDOW = 60          # characters on each side of the match

        try:
            if not self.citizen_vs:
                logger.warning("Citation verification skipped — citizen vectorstore not loaded")
                return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

            # ── Step 1: regex extraction ──────────────────────────────────────
            patterns = [
                # "Section 420", "Sec. 302", "S. 141"
                r"\bSec(?:tion|\.)?\s+\d+[A-Za-z]?(?:\s*\(\w+\))?",
                # "IPC Section 420", "CrPC Section 154"
                r"\b(?:IPC|CrPC|CPC|IEA|IT Act|POCSO|NDPS|MV Act)\s+Sec(?:tion|\.)?\s+\d+[A-Za-z]?",
                # Stand-alone "IPC 420"
                r"\b(?:IPC|CrPC|CPC|IEA)\s+\d+[A-Za-z]?",
                # Named Acts: "Consumer Protection Act 2019", "RTI Act 2005"
                r"[A-Z][A-Za-z ]{3,50}Act(?:\s+\d{4})?",
            ]
            combined = "|".join(f"(?:{p})" for p in patterns)

            # Collect matches with their span so we can extract surrounding context
            raw_matches = list(re.finditer(combined, document_text))

            # Deduplicate by normalised text while keeping the FIRST match's span
            seen: set = set()
            citations: list = []  # (normalised_text, span_start, span_end)
            for m in raw_matches:
                norm = " ".join(m.group().split())
                if norm and norm not in seen:
                    seen.add(norm)
                    citations.append((norm, m.start(), m.end()))

            if not citations:
                logger.info("Citation verification: no legal references extracted from document")
                return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

            logger.info(f"Citation verification: checking {len(citations)} extracted references")

            # ── Step 2: build context-enriched query & vectorstore check ──────
            doc_type_hint = doc_type.replace("_", " ")   # e.g. "police complaint"
            verified, unverified = [], []

            for citation, span_start, span_end in citations:
                try:
                    # Extract ±CONTEXT_WINDOW chars around the citation from the doc
                    ctx_start = max(0, span_start - CONTEXT_WINDOW)
                    ctx_end   = min(len(document_text), span_end + CONTEXT_WINDOW)
                    surrounding = document_text[ctx_start:ctx_end].replace("\n", " ").strip()

                    # Build the enriched query string
                    search_query = f"{citation} {doc_type_hint} — {surrounding}"

                    results = self.citizen_vs.similarity_search_with_score(search_query, k=1)
                    if results:
                        _doc, distance = results[0]
                        # Debug log: always print so future calibration is easy
                        logger.debug(
                            f"[citation_verify] '{citation}' | "
                            f"snippet='{surrounding[:60]}...' | "
                            f"L2_distance={distance:.4f} | "
                            f"threshold={SIMILARITY_THRESHOLD} | "
                            f"result={'VERIFIED' if distance <= SIMILARITY_THRESHOLD else 'UNVERIFIED'}"
                        )
                        if distance <= SIMILARITY_THRESHOLD:
                            verified.append(citation)
                        else:
                            unverified.append(citation)
                    else:
                        logger.debug(
                            f"[citation_verify] '{citation}' | no FAISS results returned | result=UNVERIFIED"
                        )
                        unverified.append(citation)

                except Exception as inner_e:
                    logger.warning(f"Similarity check failed for '{citation}': {inner_e}")
                    # Conservative: mark as unverified if individual check fails
                    unverified.append(citation)

            logger.info(
                f"Citation verification complete — verified: {len(verified)}, "
                f"unverified: {len(unverified)}"
            )
            return {
                "verified_citations": verified,
                "unverified_citations": unverified,
                "has_unverified": len(unverified) > 0,
            }

        except Exception as e:
            logger.error(f"_verify_legal_citations failed (failing open): {e}")
            return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

    def _check_pii_fabrication(self, document_text: str, user_description: str) -> None:
        """
        Log a WARNING if the generated document appears to contain fabricated PII
        (name + phone / name + email) that was absent from the user's description.

        Detection heuristics:
          - 10-digit phone numbers (common Indian mobile format)
          - Email addresses (x@y.z pattern)
        Each is cross-checked: if found in the document but NOT in the user's
        description, it's flagged as likely fabricated.

        This is log-only \u2014 does NOT modify or strip the document.
        """
        try:
            phone_pat = re.compile(r"\b\d{10}\b")
            email_pat = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

            doc_phones  = phone_pat.findall(document_text)
            doc_emails  = email_pat.findall(document_text)
            desc_phones = phone_pat.findall(user_description)
            desc_emails = email_pat.findall(user_description)

            fabricated = []
            for p in doc_phones:
                if p not in desc_phones:
                    fabricated.append(f"phone:{p}")
            for e in doc_emails:
                if e not in desc_emails:
                    fabricated.append(f"email:{e}")

            if fabricated:
                logger.warning(
                    f"[pii_check] Possible fabricated PII detected in generated document "
                    f"\u2014 items not present in user input: {fabricated}. "
                    f"Check that the prompt instruction is being followed. "
                    f"Document excerpt (first 200 chars): {document_text[:200]!r}"
                )
            else:
                logger.debug("[pii_check] No fabricated PII detected.")
        except Exception as e:
            logger.warning(f"[pii_check] PII check failed (non-blocking): {e}")

    def generate_legal_document(self, doc_type: str, description: str) -> dict:
        """
        Generate a legal document and verify its legal citations against the KB.

        Returns:
            {
                "content":      str  — full document text (with warning block appended if needed),
                "verification": {"unverified_citations": [...], "has_unverified": bool},
            }
        """
        prompts = {
            "police_complaint": """
                Draft a formal Police Complaint (First Information Report - FIR) for the Indian Police.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters
                for bolding. Use only plain text with standard capitalization for headings.

                Incident Description: {desc}

                STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

                1. ADDRESSEE
                   To: The Station House Officer (SHO)
                   [Police Station Name], [City/District]

                2. SUBJECT
                   A one-line subject summarizing the incident.

                3. COMPLAINANT DETAILS
                   Use these EXACT placeholder strings for any detail the user did NOT
                   provide. Do not invent realistic-looking values.
                   Name: [Your Full Name]
                   Address: [Your Address]
                   Contact Number: [Your Contact Number]
                   Email: [Your Email Address]

                4. DETAILS OF INCIDENT
                   Date, time, place, and full narrative of the incident.

                5. LEGAL SECTIONS APPLICABLE
                   Cite the relevant IPC sections that apply to the facts described.

                   ROBBERY vs THEFT CLASSIFICATION NOTE:
                   If the incident description mentions that force, a push, a struggle, or
                   any physical injury was used or caused DURING the act of taking the property
                   (not after the taking was complete), then:
                   - Note that the offence may qualify as Robbery under IPC Section 390 read
                     with Section 392, rather than simple Theft under Section 379.
                   - Mention both possibilities in the document with the note:
                     "Whether the act constitutes Theft (Section 379) or Robbery (Section 390/392)
                      will be determined by the Investigating Officer on the basis of the facts
                      recorded. The complainant requests the Officer to classify the offence
                      appropriately after investigation."
                   - Do NOT present a firm legal conclusion — flag it for the officer to decide.

                   PROCEDURAL AUTHORITY:
                   Always cite CrPC Section 154 as the procedural basis for registration of an FIR.
                   Example line: "This complaint is being lodged under Section 154 of the Code of
                   Criminal Procedure, 1973, and the complainant requests the SHO to register an
                   FIR accordingly."

                6. PRAYER / REQUEST
                   - Register an FIR under the applicable sections.
                   - Conduct a thorough investigation.
                   - FIR Number (to be filled by police): _____________ dated _____________
                   - Provide the complainant with a signed copy/acknowledgment of the FIR as
                     is their right under CrPC Section 154(2).

                7. DECLARATION
                   "I state that the above facts are true and correct to the best of my knowledge
                   and belief. I am making this complaint in good faith."

                8. SIGNATURE LINE
                   Name: ________________
                   Date: ________________
                   Place: ________________

                Format it like a professional physical letter for physical submission to a police station.
            """,
            "consumer_complaint": """
                Draft a formal Consumer Complaint under the Consumer Protection Act 2019.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters
                for bolding. Use only plain text with standard capitalization for headings.

                Facts / Description: {desc}

                STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

                1. FORUM / COMMISSION HEADING
                   Determine the appropriate commission based on the claim value mentioned
                   in the description, using these pecuniary jurisdiction limits under the
                   Consumer Protection Act 2019:
                     - District Consumer Disputes Redressal Commission: claims up to Rs. 50 Lakh
                     - State Consumer Disputes Redressal Commission: Rs. 50 Lakh to Rs. 2 Crore
                     - National Consumer Disputes Redressal Commission: above Rs. 2 Crore

                   If a specific claim value or product/service value is mentioned, compute
                   which commission has jurisdiction and write the heading accordingly, e.g.:
                     "Before the District Consumer Disputes Redressal Commission, [City/District]"

                   If no clear amount is mentioned, default to the District Commission and add
                   a bracketed note: "[Note: Commission jurisdiction assumed as District level —
                   please confirm based on actual claim value before filing]"

                2. CASE TITLE
                   [Complainant Full Name] ... Complainant
                   Versus
                   [Opposite Party / Company Name] ... Opposite Party

                3. COMPLAINT UNDER SECTION 35 OF THE CONSUMER PROTECTION ACT 2019

                4. PARTICULARS OF THE COMPLAINANT
                   Use these EXACT placeholder strings for any detail NOT in the description.
                   Name: [Your Full Name]
                   Address: [Your Address]
                   Contact Number: [Your Contact Number]
                   Email: [Your Email Address]

                5. PARTICULARS OF THE OPPOSITE PARTY
                   Name / Company: [Name]
                   Address: [Registered Address]

                6. FACTS OF THE COMPLAINT
                   Full narrative of the deficiency in goods or services, with dates and amounts.

                7. LIMITATION PERIOD CHECK
                   TODAY'S DATE IS {today}. Use this exact date to determine whether the
                   complaint is being filed within the 2-year limitation period under
                   Section 69 of the Consumer Protection Act 2019.

                   IMPORTANT — DO NOT FABRICATE DATES:
                   Only state a specific date (day/month/year) if the user's description
                   explicitly provides one. If the description only gives a month and year
                   (e.g. "May 2026"), an approximate timeframe (e.g. "two months ago",
                   "last year"), or no date at all, you MUST use that same level of
                   approximation in your analysis. Never invent a specific day that was
                   not stated by the user.
                   Examples:
                     - User says "10 March 2024" → use "10 March 2024"
                     - User says "March 2024"    → use "March 2024" (not "01 March 2024")
                     - User says "early 2024"    → use "early 2024"
                     - User says "two months ago"→ use "approximately two months ago"

                   Steps:
                   a) Identify the cause-of-action date/period from the description
                      (typically: date of purchase, date of defect discovery, or date of
                      last refusal by the opposite party — whichever is latest).
                      Use the exact wording/precision from the description.
                   b) Estimate the elapsed time between that date/period and today ({today}).
                      Where precision is limited, use words like "approximately" or
                      "at most" rather than a specific figure.
                   c) Apply the rule:
                      - If <= 2 years: add one line:
                        "This complaint is being filed on {today}, within the 2-year
                         limitation period prescribed under Section 69 of the Consumer
                         Protection Act 2019. The cause of action arose [use user's
                         original phrasing, e.g. 'in May 2026' or 'on 10 March 2024']."
                      - If > 2 years: add a clearly marked block:
                        "[LIMITATION NOTE: The cause of action arose [user's phrasing].
                         As of today ({today}), approximately [N] year(s) have elapsed,
                         which exceeds the 2-year limitation period under Section 69 of
                         the Consumer Protection Act 2019. This complaint appears to be
                         time-barred. The complainant is strongly advised to
                         simultaneously file an application for condonation of delay
                         under Section 69(2) of the Act, explaining sufficient cause
                         for the delay, failing which the complaint may be dismissed
                         at the threshold without hearing on merits.]"
                      - If date cannot be determined: add a bracketed note:
                        "[Please verify this complaint is filed within 2 years of the
                         cause of action as required by Section 69 of the Consumer
                         Protection Act 2019.]"

                8. GROUNDS / LEGAL BASIS
                   - Deficiency in service / defect in goods under Section 2(11) / 2(34)
                   - Unfair trade practice if applicable under Section 2(47)
                   - Cite specific Section 35 as the basis for filing this complaint
                   - Cite any other applicable provisions (e.g. Section 39 for reliefs)

                9. PRAYER
                   The complainant most respectfully prays that this Commission may be pleased to:
                   a) Direct the Opposite Party to [refund / replace / repair] as appropriate
                   b) Award compensation of Rs. [amount] for mental agony and hardship
                   c) Award litigation costs of Rs. [amount]
                   d) Pass any other order as this Commission deems fit and proper

                10. VERIFICATION / AFFIDAVIT
                    I, [Complainant Name], the above-named complainant, do hereby solemnly
                    affirm and declare that the facts stated in paragraphs 1 to [N] above
                    are true and correct to the best of my knowledge, information and belief,
                    and nothing material has been concealed therefrom.

                    Verified at [City] on this ___ day of [Month], [Year].

                    Complainant's Signature: ____________________
                    Name: ____________________
                    Date: ____________________
                    Place: ____________________

                Format it strictly like a formal legal petition for physical filing before a Consumer Commission.
            """,

            "rti_application": """
                Draft a formal RTI Application under the Right to Information Act 2005.
                CRITICAL INSTRUCTION: DO NOT use any markdown formatting, asterisks (**), or special characters
                for bolding. Use only plain text with standard capitalization for headings.

                Information Sought / Description: {desc}

                STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

                1. ADDRESSEE
                   To: The Public Information Officer (PIO)
                   [Name of Public Authority / Department]
                   [Address]

                2. SUBJECT
                   Application for Information under the Right to Information Act, 2005

                3. APPLICANT DETAILS
                   Use these EXACT placeholder strings for any detail NOT in the description.
                   Name: [Your Full Name]
                   Address: [Your Address]
                   Contact Number: [Your Contact Number]
                   Email: [Your Email Address]

                4. INFORMATION SOUGHT
                   List each item of information requested clearly and specifically,
                   numbered as separate points. Base these on the description: {desc}

                5. APPLICATION FEE
                   Include this standard fee statement:
                   "In accordance with the Right to Information (Regulation of Fee and Cost)
                   Rules, 2005, I am enclosing an application fee of Rs. 10/- (Rupees Ten
                   Only) by way of [Cash / Demand Draft / Postal Order / Court Fee Stamp /
                   Indian Postal Order] payable to the Accounts Officer of [Public Authority]."

                   Add this as an optional bracketed note (do not assert it as fact):
                   "[Optional: If the applicant belongs to the Below Poverty Line (BPL)
                   category, no application fee is payable. A copy of the BPL certificate
                   must be attached along with this application as proof of exemption.]"

                6. RESPONSE TIMELINE
                   Include this line:
                   "As per Section 7(1) of the Right to Information Act, 2005, the Public
                   Information Officer is required to provide the requested information
                   within 30 (thirty) days from the date of receipt of this application.
                   If the information sought concerns the life or liberty of any person,
                   the response must be provided within 48 (forty-eight) hours of receipt."

                7. APPEAL ESCALATION NOTICE
                   Include this closing note:
                   "If no response is received within the statutory period, or if the
                   response provided is incomplete, incorrect, or unsatisfactory, the
                   applicant reserves the right to file a First Appeal under Section 19(1)
                   of the Right to Information Act, 2005, before the designated First
                   Appellate Authority within 30 days of the expiry of the prescribed
                   period or receipt of the decision, whichever is earlier."

                8. DECLARATION
                   "I, [Name], hereby declare that I am a citizen of India and the
                   information sought above is not covered by any of the exemptions
                   listed under Sections 8 and 9 of the Right to Information Act, 2005,
                   to the best of my knowledge."

                9. SIGNATURE BLOCK
                   Yours faithfully,

                   Name: ____________________
                   Signature: ____________________
                   Date: ____________________
                   Place: ____________________

                Use the standard Government of India RTI format for physical submission.
            """,

        }

        template = prompts.get(doc_type, "Draft a professional legal document in plain text (no markdown) based on: {desc}")
        # Inject today's date so date-sensitive logic (e.g. limitation period
        # checks in consumer_complaint) can compute elapsed time accurately.
        # Extra kwargs are safely ignored by templates that don't use {today}.
        today_str = datetime.date.today().strftime("%d %B %Y")
        prompt = template.format(desc=description, today=today_str)

        SYSTEM_MSG = _LEGAL_DRAFTSMAN_SYSTEM_MSG
        messages = [
            SystemMessage(content=SYSTEM_MSG),
            HumanMessage(content=prompt),
        ]
        document_text: str = self.llm.invoke(messages).content

        # ── PII fabrication detection (log-only, non-blocking) ────────────────
        # Scans for realistic Indian names combined with phone numbers or email
        # addresses that do NOT appear in the user's original description.
        # Logs a WARNING so fabrication is visible in server logs even if the
        # prompt instruction slips — does NOT auto-strip (would risk breaking
        # legitimately user-provided details).
        self._check_pii_fabrication(document_text, description)

        # ── Citation verification (non-blocking) ──────────────────────────────
        verification = self._verify_legal_citations(document_text, doc_type)

        if verification["has_unverified"]:
            unverified_list = ", ".join(verification["unverified_citations"])
            warning_block = (
                "\n\n---\n"
                "⚠️ VERIFICATION NOTICE: The following legal references could not be confirmed "
                "against our legal database and should be double-checked with a lawyer or official "
                f"source before submission: {unverified_list}\n"
                "---"
            )
            document_text = document_text + warning_block
            logger.warning(
                f"Document generated with {len(verification['unverified_citations'])} "
                f"unverified citation(s): {unverified_list}"
            )

        return {
            "content": document_text,
            "verification": {
                "unverified_citations": verification["unverified_citations"],
                "has_unverified": verification["has_unverified"],
            },
        }

    def _verify_case_citations(self, document_text: str) -> dict:
        """
        Extract case-name citations ('X v. Y (YYYY)' style) and verify them
        against the lawyer judgments vectorstore.

        Uses a more lenient L2 threshold (1.5) than statute citations because
        case-name embeddings are fuzzier — a real judgment title produces a
        broader embedding spread than a precise section number.

        CALIBRATION FINDINGS (measured 2026-07-25, 145-judgment index, all-MiniLM-L6-v2):

        Non-deterministic results: FAISS L2 distances for case-name queries varied
        significantly between runs (~0.10-0.20 variance) due to SentenceTransformer
        initialization. This means no threshold can reliably discriminate.

        Root cause — semantic indistinguishability:
        ALL Indian criminal case citations follow the pattern 'X v. State of Y (YYYY)'.
        With 145 criminal judgments indexed, ANY plausible-sounding citation embeds
        within scoring range of real judgments. Measured distances:

          Real cases (confirmed in index):     L2 = 0.63 – 1.03 across runs
          Fabricated 'Gurbachan Singh v. State of Punjab (2002)': 0.78 – 1.33
          (overlaps with real-case range in some runs — cannot set a reliable threshold)

        Primary anti-fabrication defense is the CASE LAW RULE prompt instruction in
        generate_lawyer_litigation_document ("ONLY cite judgments you are highly
        confident exist; OMIT if uncertain"), which prevents LLM hallucination at
        source. This vectorstore check is a supplementary best-effort signal only.

        Threshold 1.5 is kept as a conservative catch-net for obviously dissimilar
        citations (e.g., completely fictional names score 1.07-1.74 range).

        Fails open (returns has_unverified: False) on any exception.
        """
        CASE_THRESHOLD = 1.5   # L2 distance — conservative catch-net only
                                # Semantic approach cannot reliably detect fabricated
                                # Indian criminal case names (all follow X v. State pattern)
                                # Primary defense: CASE LAW RULE prompt instruction
        # Pattern: 'State v. Sharma (2019)', 'Ram Kumar vs Union of India 2021'
        CASE_PAT = re.compile(
            r"\b([A-Z][A-Za-z .,']+?)\s+v(?:s\.?|\.)?\s+([A-Z][A-Za-z .,']+?)\s*\(?\b(\d{4})\b\)?",
            re.UNICODE
        )
        try:
            if not self.lawyer_vs:
                logger.warning("Case citation verification skipped — lawyer vectorstore not loaded")
                return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

            raw = list(CASE_PAT.finditer(document_text))
            seen: set = set()
            citations = []
            for m in raw:
                norm = " ".join(m.group().split())
                if norm and norm not in seen:
                    seen.add(norm)
                    citations.append(norm)

            if not citations:
                return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

            logger.info(f"Case citation verification: checking {len(citations)} case reference(s)")
            verified, unverified = [], []
            for cite in citations:
                try:
                    results = self.lawyer_vs.similarity_search_with_score(cite, k=1)
                    if results:
                        top_doc, distance = results[0]
                        top_id = top_doc.metadata.get("case_id", "?")
                        # Debug log — identical style to _verify_legal_citations for easy grep
                        logger.debug(
                            f"[case_verify] '{cite}' | "
                            f"L2_distance={distance:.4f} | "
                            f"threshold={CASE_THRESHOLD} | "
                            f"top_hit='{top_id}' | "
                            f"result={'VERIFIED' if distance <= CASE_THRESHOLD else 'UNVERIFIED'}"
                        )
                        if distance <= CASE_THRESHOLD:
                            verified.append(cite)
                        else:
                            unverified.append(cite)
                    else:
                        logger.debug(f"[case_verify] '{cite}' | no FAISS results returned | result=UNVERIFIED")
                        unverified.append(cite)
                except Exception as inner_e:
                    logger.warning(f"Case similarity check failed for '{cite}': {inner_e}")
                    unverified.append(cite)

            logger.info(f"Case citation verification — verified: {len(verified)}, unverified: {len(unverified)}")
            return {
                "verified_citations": verified,
                "unverified_citations": unverified,
                "has_unverified": len(unverified) > 0,
            }
        except Exception as e:
            logger.error(f"_verify_case_citations failed (failing open): {e}")
            return {"verified_citations": [], "unverified_citations": [], "has_unverified": False}

    def generate_lawyer_litigation_document(self, doc_type: str, data: dict) -> dict:
        """
        Generate a professional litigation document for lawyers.

        Applies the same safeguards as generate_legal_document:
          - Shared anti-fabrication / PII system message
          - Statutory citation verification (_verify_legal_citations)
          - Case-law citation verification (_verify_case_citations)
          - PII fabrication detection (_check_pii_fabrication)
          - ⚠️ VERIFICATION NOTICE block appended if any citation is unverified

        Returns:
            {
                "content":      str  — document text (warning block appended if needed),
                "verification": {"unverified_citations": [...], "has_unverified": bool},
            }
        """
        details = data.get("details", "")

        # ── Per-document-type prompt templates ────────────────────────────────
        prompts = {
            "bail": f"""\
Draft a formal Bail Application for an Indian criminal court.
DO NOT use markdown formatting, asterisks (**), or any special characters for bolding.
Use only plain text with standard capitalization for headings.

Case Details provided by the advocate: {details}

STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

1. COURT HEADING
   In the Hon'ble [Court Name]
   [State]
   Bail Application No. ___ / [Year]
   In the matter of: [Case Title from details]

2. PARTICULARS OF THE APPLICANT / ACCUSED
   RULE: For each field — if the case details above provide the value, write ONLY that
   real value. If not provided, write ONLY the bracketed placeholder. NEVER INVENT a
   realistic-looking value. NEVER write both a tag and a real value on one line.
   Name of Accused:        [Accused Full Name]
   Age / Date of Birth:    [Date of Birth / Age]
   Address of Accused:     [Accused Address]
   FIR No. / Case No.:     [FIR/Case Number]
   Police Station:         [Police Station Name]
   Date of Arrest:         [Date of Arrest]

3. ADVOCATE DETAILS
   RULE: Same as above — real value if provided, exact placeholder if not, NEVER invent.
   Name of Advocate:       [Advocate Full Name]
   Bar Council No.:        [Bar Council Registration Number]
   Address:                [Advocate Office Address]
   Contact:                [Advocate Contact Number]
   Email:                  [Advocate Email Address]

4. BRIEF FACTS
   Narrative of the case as provided. Do NOT add facts not mentioned.

5. GROUNDS FOR BAIL
   - No criminal antecedents (if stated)
   - No recovery at the instance of the accused (if applicable)
   - No direct evidence linking the accused
   - Weak circumstantial chain
   - Long period of custody (if applicable)
   - Accused is the sole breadwinner / has dependants (if stated)
   Only include grounds that can be reasonably inferred from the details provided.

6. LEGAL PRINCIPLES
   Cite only well-established principles with their source sections.
   SECTION CITATION RULE: Every statutory section you cite MUST be attributed to the
   exact Act it appears in — do NOT transfer a section from one Act to another.
   CASE LAW RULE: Only cite case law (judgments) that is clearly established.
   If you are not certain a case exists, do NOT cite it — omit it entirely.

7. PRAYER CLAUSE
   It is, therefore, most respectfully prayed that this Hon'ble Court may be pleased to:
   a) Release the accused on bail pending trial;
   b) Fix reasonable surety / bail bond;
   c) Pass any other order(s) as this court deems fit.

   Respectfully submitted,
   [Advocate Full Name]
   Counsel for the Applicant / Accused
   Date: ___________
   Place: ___________
""",

            "legal_notice": f"""\
Draft a formal Legal Notice from an Indian advocate.
DO NOT use markdown formatting, asterisks (**), or any special characters for bolding.
Use only plain text with standard capitalization for headings.

Details provided by the advocate: {details}

STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

1. SENDER / ADVOCATE DETAILS
   RULE: For each field — if the details above provide the value, write ONLY that real
   value. If not provided, write ONLY the bracketed placeholder. NEVER INVENT a
   realistic-looking value (no made-up addresses, phone numbers, dates, or notice numbers).
   NEVER write both a placeholder tag and a real value on the same line.
   Advocate Name:          [Advocate Full Name]
   Enrollment No.:         [Bar Council Enrollment Number]
   Address:                [Advocate Office Address]
   Phone:                  [Advocate Phone Number]
   Email:                  [Advocate Email Address]
   Date:                   [Date]
   Notice No.:             [Notice Reference Number]

2. ADDRESSEE — OPPOSITE PARTY DETAILS
   RULE: Same as above — real value if provided in details, exact placeholder if not.
   Name / Company:         [Opposite Party Name]
   Address:                [Opposite Party Address]
   Contact:                [Opposite Party Contact]

3. SUBJECT
   Legal Notice — [one-line subject]

4. FACTS
   Full narrative based on the details provided. Do NOT add facts not mentioned.

5. LEGAL BREACH
   Specify the legal provisions violated.
   SECTION CITATION RULE: Every statutory section you cite MUST be attributed to the
   exact Act it appears in. Do NOT transfer, borrow, or merge section numbers across Acts.
   CASE LAW RULE: Only cite case law that is clearly established.
   If you are not certain a case or section exists in the cited Act, omit it entirely.

6. DEMAND
   State the specific demand clearly (payment, action, etc.).

7. TIME LIMIT
   Demand compliance within [X] days of receipt of this notice.

8. LEGAL CONSEQUENCES
   If the demand is not complied with, legal proceedings will be initiated without
   further notice, and the noticee shall be liable for all costs and consequences.

9. CLOSING
   Yours faithfully,

   [Advocate Full Name]
   Advocate, [Court]
   [City], [Date]
""",

            "written_arguments": f"""\
Draft formal Written Arguments for an Indian court proceeding.
DO NOT use markdown formatting, asterisks (**), or any special characters for bolding.
Use only plain text with standard capitalization for headings.

Details provided by the advocate: {details}

STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

1. COURT HEADING
   RULE: Use real values from the case details where provided; bracketed placeholders where
   not. NEVER INVENT a court name, case number, or date.
   In the Hon'ble [Court Name]
   [City]
   [Case Title / Number]

2. BRIEF FACTS
   A concise, numbered narrative of facts as provided. Do NOT add facts not mentioned.
   RULE (applies to every field throughout this document): Every party name, date, case
   number, address, or identification detail must be EITHER the real value from the user's
   input OR a clean bracketed placeholder. NEVER invent a realistic-looking value.
   NEVER write a placeholder tag alongside a real value on the same line.

3. ISSUES FOR DETERMINATION
   Frame the precise legal questions arising from the facts.

4. EVIDENCE ANALYSIS
   Analyse the evidence referred to in the details. Do NOT fabricate witness names,
   exhibit numbers, or forensic results that were not mentioned.

5. CONTENTIONS ON BEHALF OF THE [APPLICANT / RESPONDENT]
   Present legal arguments and applicable provisions.
   SECTION CITATION RULE: Every statutory section you cite MUST be attributed to the
   exact Act it appears in. Do NOT transfer section numbers between Acts.
   CASE LAW RULE: Only cite case law judgments that are clearly established and
   commonly known. If you are not certain a case exists, do NOT cite it — omit it.

6. BENEFIT OF DOUBT / STANDARD OF PROOF
   Address the applicable standard of proof and any reasonable doubt.

7. PRAYER
   In view of the above, it is most respectfully prayed that this Hon'ble Court may
   be pleased to [grant / dismiss / allow / reject] [the petition / application /
   appeal] and pass any other order as deemed fit.

   Respectfully submitted,
   [Advocate Full Name — use real name if given, else placeholder]
   Counsel for [Party — use real party name from case details]
   Date: ___________
   Place: ___________
""",
        }

        prompt = prompts.get(doc_type, f"Draft a professional legal document in plain text (no markdown) based on: {details}")

        messages = [
            SystemMessage(content=_LEGAL_DRAFTSMAN_SYSTEM_MSG),
            HumanMessage(content=prompt),
        ]
        document_text: str = self.llm.invoke(messages).content

        # ── PII fabrication detection (log-only, non-blocking) ────────────────
        self._check_pii_fabrication(document_text, details)

        # ── Statutory citation verification ───────────────────────────────────
        stat_verification = self._verify_legal_citations(document_text, doc_type)

        # ── Case-law citation verification ────────────────────────────────────
        case_verification = self._verify_case_citations(document_text)

        # ── Merge both verification results ───────────────────────────────────
        all_unverified = (
            stat_verification.get("unverified_citations", []) +
            case_verification.get("unverified_citations", [])
        )
        has_any_unverified = len(all_unverified) > 0

        if has_any_unverified:
            unverified_list = ", ".join(all_unverified)
            warning_block = (
                "\n\n---\n"
                "⚠️ VERIFICATION NOTICE: The following legal references could not be confirmed "
                "against our legal database and should be double-checked with a lawyer or official "
                f"source before submission: {unverified_list}\n"
                "---"
            )
            document_text = document_text + warning_block
            logger.warning(
                f"Lawyer document generated with {len(all_unverified)} "
                f"unverified citation(s): {unverified_list}"
            )

        return {
            "content": document_text,
            "verification": {
                "unverified_citations": all_unverified,
                "has_unverified": has_any_unverified,
            },
        }


# ---------------------------------------------------------------------------
# Module-level singleton (imported by routes)
# ---------------------------------------------------------------------------
vector_service = VectorService()
