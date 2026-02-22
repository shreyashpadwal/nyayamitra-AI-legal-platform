import os
import re
from dotenv import load_dotenv
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

FAISS_DIR = "data/faiss_db"

print("🔄 Loading embedding model...")
embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

print("🔄 Loading FAISS index...")
vectorstore = FAISS.load_local(
    FAISS_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0.7,
    max_tokens=1024
)


# ============================================================
# STEP 2: INTENT DETECTION
# Classifies what the user actually wants before answering.
# Prevents the bot from giving definitions when the user wants
# a process, or punishments when they want to file a complaint.
# ============================================================

def detect_intent(question: str) -> str:
    q = question.lower()

    if any(w in q for w in ["what is", "define", "meaning of", "what does", "what are"]):
        return "definition"
    elif any(w in q for w in ["punishment", "sentence", "jail", "prison", "fine", "years", "penalty"]):
        return "punishment"
    elif any(w in q for w in ["how to", "how do i", "steps", "process", "procedure", "file", "apply", "register"]):
        return "procedure"
    elif any(w in q for w in ["my rights", "can i", "am i allowed", "is it legal", "right to"]):
        return "rights"
    elif any(w in q for w in ["arrested", "police", "fir", "complaint", "case against"]):
        return "enforcement"
    else:
        return "general"


# Maps each intent to a focused instruction injected into the prompt.
# This tells the LLM exactly what the user is looking for — not just the topic.
INTENT_INSTRUCTIONS = {
    "definition":  "The user wants to understand what something means. Explain it simply in 2-3 sentences. Don't list laws or punishments unless they asked.",
    "punishment":  "The user wants to know the consequence or penalty. Lead with the practical outcome — how many years, what kind of offence. Keep it short and direct.",
    "procedure":   "The user wants to know what steps to take. Give them a clear, practical sequence of actions. Make it feel like friendly advice, not a legal manual.",
    "rights":      "The user wants to know what they're entitled to. Be empowering and clear. Tell them what they CAN do, not just what the law says abstractly.",
    "enforcement": "The user is dealing with police or a legal complaint. Be calm and practical. Focus on what they should do right now, step by step.",
    "general":     "Answer naturally and helpfully. Focus on what's most useful and actionable for this person to know.",
}


# ============================================================
# STEP 4: POST-PROCESSING REWRITE CHECK
# After the LLM generates an answer, scan it for academic/formal
# language. If too many patterns are found, send a rewrite request.
# This is how production legal AI systems refine tone automatically.
# ============================================================

ACADEMIC_PATTERNS = [
    r"\bhereby\b",
    r"\bshall be liable\b",
    r"\bwherein\b",
    r"\baforesaid\b",
    r"\bnotwithstanding\b",
    r"\bpursuant to\b",
    r"\bthe said\b",
    r"\bin accordance with\b",
    r"\bsubject to the provisions\b",
    r"\bSection \d+\s+(IPC|CrPC|RTI|IEA)",  # catches "Section 503 IPC" style openings
]

def needs_rewrite(text: str) -> bool:
    """Returns True if the response contains 2+ formal/legal language patterns."""
    matches = sum(1 for p in ACADEMIC_PATTERNS if re.search(p, text, re.IGNORECASE))
    return matches >= 2

def rewrite_response(original: str) -> str:
    """Sends a focused rewrite request to simplify overly formal output."""
    messages = [
        SystemMessage(content=(
            "You are a plain-language editor. Rewrite legal text to sound warm, "
            "conversational, and simple for someone with no legal background. "
            "Keep all the facts intact. Remove all formal legal phrasing like "
            "'hereby', 'shall be liable', 'wherein', 'pursuant to'. "
            "Keep it under 220 words. End with one helpful follow-up question."
        )),
        HumanMessage(content=f"Rewrite this in simple, friendly language:\n\n{original}")
    ]
    response = llm.invoke(messages)
    return response.content


# ============================================================
# SYSTEM PROMPT — behavior control
# ============================================================

SYSTEM_PROMPT = """You are a friendly, knowledgeable Indian legal assistant helping everyday people — not lawyers — understand their legal rights and options.

YOUR PERSONALITY:
- Warm, approachable, and supportive — like a trusted friend who happens to know Indian law well
- Patient and empathetic — users are often stressed or confused about their situation
- Clear and confident — you give real answers, not vague hedges

HOW TO WRITE YOUR RESPONSES:

1. SOUND LIKE A HUMAN, NOT A DOCUMENT
   - Write in natural, flowing sentences — no rigid sections or headings
   - NEVER use headers like "Direct Answer", "Relevant Law", "How It Applies", "Related Sections"
   - NEVER open with a bold title or label
   - Weave legal references naturally into sentences, never list them

2. MENTION SECTION NUMBERS SPARINGLY
   - Maximum 1-2 section references per response
   - Always explain what the section means in plain English right after mentioning it

3. USE THE CONTEXT — DON'T COPY IT
   - The retrieved legal text is raw and formal — do NOT copy it directly
   - Translate it into simple language that a non-lawyer can understand

4. KEEP RESPONSES FOCUSED
   - 3 to 5 short paragraphs at most
   - Under 220 words unless the question genuinely needs more

5. ALWAYS END WITH A FOLLOW-UP OFFER
   - One natural, helpful closing question
   - Examples: "Want me to walk you through the steps?", "Should I explain what happens next?"

BANNED PHRASES (never use these):
- "hereby", "shall be liable", "wherein", "aforesaid", "pursuant to", "the said"
- "Direct Answer", "Relevant Law", "How It Applies", "Related Sections"
- "I may be able to...", "It depends on the situation...", "I would need more context..."

Always end with this disclaimer on a new line:
*This is general legal information, not professional legal advice. Please consult a qualified lawyer for your specific situation.*"""


HUMAN_PROMPT = """Use the following legal context to answer. Do not copy it directly — explain everything in simple, plain language.

Context:
{context}

User Intent: {intent}
What the user is looking for: {intent_instruction}

User's Question: {question}

Reply conversationally — no headings, plain English, end with one helpful follow-up question."""


# ============================================================
# MAIN RAG FUNCTION
# ============================================================

def get_answer(question: str) -> dict:

    # Step 1: Detect what the user actually wants
    intent = detect_intent(question)
    intent_instruction = INTENT_INSTRUCTIONS[intent]
    print(f"🎯 Intent detected: {intent}")

    # Step 2: Retrieve relevant chunks from FAISS
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3}
    )
    relevant_docs = retriever.invoke(question)

    if not relevant_docs:
        return {
            "answer": "Hmm, I wasn't able to find specific information about that in my legal database. For this one, I'd strongly recommend speaking with a qualified lawyer who can give you advice tailored to your exact situation.\n\nIs there anything else I can try to help you with?",
            "sources": []
        }

    # Step 3: Build context string (truncated to keep prompt lean)
    context_parts = []
    for i, doc in enumerate(relevant_docs):
        law = doc.metadata.get("law_name", "Unknown Law")
        page = doc.metadata.get("page", "?")
        excerpt = doc.page_content[:400]
        context_parts.append(f"[{law}, Page {page}]\n{excerpt}")
    context = "\n\n".join(context_parts)

    # Step 4: Build sources list for frontend display
    sources = []
    seen = set()
    for doc in relevant_docs:
        law = doc.metadata.get("law_name", "Unknown Law")
        page = doc.metadata.get("page", "?")
        key = f"{law}-{page}"
        if key not in seen:
            sources.append({
                "law": law,
                "page": page,
                "excerpt": doc.page_content[:350] + "..."
            })
            seen.add(key)

    # Step 5: Generate answer with intent-aware prompt
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=HUMAN_PROMPT.format(
            context=context,
            question=question,
            intent=intent,
            intent_instruction=intent_instruction
        ))
    ]
    response = llm.invoke(messages)
    answer = response.content

    # Step 6: Post-processing rewrite check
    # If formal legal language is detected in the output, rewrite it automatically
    if needs_rewrite(answer):
        print(f"⚠️  Formal language detected — running rewrite pass...")
        answer = rewrite_response(answer)
    else:
        print("✅ Tone check passed — no rewrite needed")

    return {
        "answer": answer,
        "sources": sources
    }