"""
CitizenGraph — Self-RAG + Corrective RAG pipeline for citizen legal queries.

Uses LangGraph to orchestrate: retrieval decision -> query rewrite -> hybrid
retrieval -> cross-encoder reranking -> relevance evaluation -> generation ->
hallucination checking -> answer revision -> usefulness checking.
"""

import os
import json
import logging
import time
from typing import TypedDict, List, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END

from .retrieval.hybrid_retriever import HybridRetriever
from .retrieval.reranker import CrossEncoderReranker
from .prompts.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Definition
# ---------------------------------------------------------------------------
class CitizenRAGState(TypedDict):
    original_query: str
    rewritten_query: str
    needs_retrieval: bool
    is_legal_query: bool  # False for off-topic (non-Indian-law) queries
    retrieved_docs: list
    reranked_docs: list
    relevant_docs: list
    answer: str
    hallucination_status: str  # fully_supported | partially_supported | not_supported | not_applicable
    is_useful: bool
    retry_count: int
    rewrite_count: int
    sources: list
    pipeline_log: list
    intent: str
    instruction: str
    web_search_attempted: bool  # True once web_search_fallback has fired — prevents re-entry
    conversation_history: list  # last 1-2 prior Q&A turns [{"question": str, "answer": str}]


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

def _get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
    )


def _safe_parse_json(text: str) -> dict:
    """Parse JSON from LLM output, handling common formatting issues."""
    text = text.strip()
    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {}


# ---------------------------------------------------------------------------
# Fix 1 helper: Statute-aware retrieval filter (no LLM call)
# ---------------------------------------------------------------------------

import re as _re  # private alias so local 're' imports in nodes are unaffected

# Maps regex patterns to their exact law_name strings in the vectorstore
# metadata. Ordered most-specific first to avoid false positives.
_STATUTE_PATTERNS: list[tuple[str, str]] = [
    (r"\bIPC\b|indian penal code|penal code",        "Indian Penal Code"),
    (r"\bCrPC\b|criminal procedure|cr\.p\.c",        "Crpc Act"),
    (r"\bRTI\b|right to information",                "Rti Act"),
    (r"consumer protection|consumer complaint",      "Consumer Protection Act"),
    (r"constitution|fundamental rights|article \d",  "Constitution Of India"),
]

# Secondary (topic-keyword) patterns used when no explicit statute name appears.
# These map unambiguous domain terms to a statute, enabling the statute-boost
# for natural-language queries that never name the statute explicitly.
#
# Coverage cross-referenced against the IPC PDF in the vectorstore (4010 chunks).
# Each entry: (compiled_pattern, law_name, exclude_pattern_or_None)
# The optional exclusion pattern prevents false positives.
_TOPIC_PATTERNS: list[tuple["_re.Pattern[str]", str, Optional["_re.Pattern[str]"]]] = [
    # ── IPC property offences ──────────────────────────────────────────────
    # Theft, robbery, dacoity, snatching (§378-395) + weapon-use aggravated
    # offences (§397 — robbery/dacoity with deadly weapon, mandatory 7yr min)
    (
        _re.compile(
            r"\btheft\b|\bstealing\b|\bstolen\b|\brobbery\b|\bdacoity\b|\bdacoit\b|\bsnatching\b"
            r"|\bdeadly weapon\b|\bweapon\b.{0,30}\brobbery\b|\brobbery\b.{0,30}\bweapon\b"
            r"|\barmed.{0,20}\brobbery\b|\bweapon.{0,20}\bused\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Cheating and fraud (§415-420)
    (
        _re.compile(
            r"\bcheat\w*\b|\bfraud\b|\bfraudulent\b|\bdeception\b"
            r"|\bmisrepresentation\b|\bdishonestly\b"
            r"|\bfake.{0,15}document\b|\bforged.{0,15}document\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        # Don't fire for consumer fraud — let consumer pattern take it
        _re.compile(r"consumer|product|service|refund", _re.IGNORECASE),
    ),
    # Criminal breach of trust and misappropriation (§405-409)
    (
        _re.compile(
            r"criminal breach of trust|\bmisappropriat\w*\b|\bembezzle\w*\b"
            r"|\bentrusted\b.{0,30}\bproperty\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Forgery and counterfeiting (§463-477A)
    (
        _re.compile(
            r"\bforgery\b|\bforged\b|\bforgeries\b|\bcounterfeit\b"
            r"|\bfalse document\b|\bfabricated document\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Defamation (§499-502)
    (
        _re.compile(
            r"\bdefamation\b|\bdefamatory\b|\blibel\b|\bslander\b"
            r"|\breputation\b.{0,30}\bdamage\b|\bdamage.{0,30}\breputation\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Criminal intimidation and threat (§503-506)
    (
        _re.compile(
            r"criminal intimidation|\bthreaten\w*\b|\bthreat to\b|\bintimidation\b"
            r"|\bmenace\b|\bblackmail\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Hurt and grievous hurt (§319-338)
    (
        _re.compile(
            r"\b(?:grievous\s+)?hurt\b|\bgrevious hurt\b|\bacid attack\b"
            r"|\bbodily injury\b|\bvoluntary causing hurt\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Murder and homicide (§299-304B)
    (
        _re.compile(
            r"\bmurder\b|\bhomicide\b|\bculpable homicide\b|\bdowry death\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Assault and criminal force (§351-358)
    (
        _re.compile(
            r"\bassault\b|\bcriminal force\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Kidnapping and abduction (§359-374)
    (
        _re.compile(
            r"\bkidnapping\b|\bkidnapped\b|\babduction\b|\babducted\b"
            r"|\bhostage\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Rape and sexual offences (§375-376E) — sensitivity-aware wording
    (
        _re.compile(
            r"\brape\b|sexual assault|outraging.*modesty|\bmolestation\b"
            r"|sexual harassment.*IPC|\b376\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Criminal trespass and housebreaking (§441-462)
    # CAUTION: "house" alone is too broad and caused a BM25 false-positive
    # earlier. Require "trespass" or "housebreaking" explicitly.
    (
        _re.compile(
            r"criminal trespass|\bhousebreaking\b|\bhouse-breaking\b"
            r"|\blurking house\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Dowry-related offences (§498A IPC — NOT Dowry Prohibition Act 1961
    # which is a separate statute NOT in this vectorstore)
    (
        _re.compile(
            r"\bdowry\b|\b498.?A\b|cruelty by husband|matrimonial cruelty",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Abetment and criminal conspiracy (§107-120B)
    (
        _re.compile(
            r"\babetment\b|\babet\b|\bcriminal conspiracy\b"
            r"|\bconspiracy to commit\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # Extortion and bribery (§383-389, §171B)
    (
        _re.compile(
            r"\bextortion\b|\bbribery\b|\bbribe\b",
            _re.IGNORECASE,
        ),
        "Indian Penal Code",
        None,
    ),
    # ── CrPC procedural terms ──────────────────────────────────────────────
    (
        _re.compile(
            r"\bFIR\b|\bfirst information report\b|\bbail\b|\bremand\b"
            r"|\bchargesheet\b|\bsummons\b|\bwarrant\b"
            r"|\bmagistrate\b|\bsessions court\b|\bcustody\b.{0,20}\bpolice\b",
            _re.IGNORECASE,
        ),
        "Crpc Act",
        # IPC-named offences take priority over procedural terms
        _re.compile(
            r"\btheft\b|\bmurder\b|\bassault\b|\bkidnapping\b|\brape\b"
            r"|\bdacoity\b|\bcheating\b|\bforgery\b",
            _re.IGNORECASE,
        ),
    ),
    # ── RTI-specific terms ─────────────────────────────────────────────────
    (
        _re.compile(
            r"\bpublic information officer\b|\bPIO\b|\bgovernment information\b"
            r"|\bRTI application\b",
            _re.IGNORECASE,
        ),
        "Rti Act",
        None,
    ),
    # ── Consumer Protection ────────────────────────────────────────────────
    (
        _re.compile(
            r"\bconsumer forum\b|\bdistrict commission\b|\bdeficiency.{0,20}service\b"
            r"|\bproduct liability\b|\bconsumer complaint\b",
            _re.IGNORECASE,
        ),
        "Consumer Protection Act",
        None,
    ),
]


def _detect_target_statute(query: str) -> Optional[str]:
    """
    Rule-based statute detector — zero LLM calls.

    First checks for explicit statute identifiers ("IPC", "CrPC", etc.).
    If none found, falls back to topic-keyword inference ("theft" → IPC,
    "bail" → CrPC, etc.) to handle natural-language queries that never name
    the statute explicitly but clearly target one.

    Returns the exact law_name as stored in FAISS metadata, or None when
    the query spans multiple statutes or targets none specifically.
    """
    if not query:
        return None
    # Pass 1: explicit statute names (high confidence)
    for pattern, law_name in _STATUTE_PATTERNS:
        if _re.search(pattern, query, _re.IGNORECASE):
            return law_name
    # Pass 2: topic-keyword inference (medium confidence — natural-language queries)
    for compiled_pat, law_name, exclude_pat in _TOPIC_PATTERNS:
        if compiled_pat.search(query):
            if exclude_pat is None or not exclude_pat.search(query):
                return law_name
    return None


def _is_compound_query(query: str) -> bool:
    """
    Heuristic: returns True when the query asks about multiple scenarios
    (e.g. "punishment for theft… does it differ if in someone's house?").

    Signals: conjunction word ("and", "or", "also") combined with a
    comparison/difference word ("differ", "different", "compare",
    "versus", "between", "distinction", "vary").

    Used to bump rerank top_k so both halves of the question are served.
    """
    q = query.lower()
    has_conjunction = bool(_re.search(r"\b(and|or|also|both|as well)\b", q))
    has_comparison  = bool(_re.search(r"\b(differ|different|difference|distinguish|compare|comparison|versus|vs\.?|between|vary|variation|distinct)\b", q))
    return has_conjunction and has_comparison


def _is_multi_right_query(query: str) -> bool:
    """
    Heuristic: returns True when the query asks about rights/protections
    for a person in a legal situation (e.g. arrest, detention, consumer dispute).

    These questions inherently span multiple sections and articles — a single
    top-k=5 window risks being dominated by the single highest-scoring chunk.
    Raising to top_k=8 ensures all relevant rights (e.g. §49, §50, §41D, §50A,
    Article 22) have room to survive reranking.
    """
    q = query.lower()
    rights_signal  = bool(_re.search(
        r"\b(right|rights|protection|entitle|entitlement|remedy|remedies|recourse|"
        r"legal protection|fundamental right|constitutional right)\b", q
    ))
    context_signal = bool(_re.search(
        r"\b(arrest|arrested|detain|detained|detention|police|custody|accused|"
        r"consumer|buyer|defective|employer|employee|tenant|landlord)\b", q
    ))
    return rights_signal and context_signal


def retrieval_decision_node(state: CitizenRAGState) -> dict:
    """
    OPTIMISATION: Fused decision + rewrite node.

    Calls the combined 'retrieval_decision_and_rewrite' prompt which returns
    needs_retrieval, is_legal_query, AND a rewritten_query all in one Groq
    round-trip. When that succeeds and needs_retrieval=True, the rewritten
    query is stored in state so query_rewrite_node is skipped entirely.

    Falls back to the original two-step path (separate retrieval_decision
    prompt, then a separate query_rewrite call) if the combined call fails
    or returns malformed JSON.
    """
    node_start = time.time()
    log_entry = {"node": "retrieval_decision", "timestamp": node_start}
    try:
        llm = _get_llm()
        prompt = get_prompt("retrieval_decision_and_rewrite")  # combined prompt

        # Build history block for follow-up resolution
        history = state.get("conversation_history") or []
        if history:
            turns = history[-2:]  # cap at last 2 turns
            lines = ["PREVIOUS CONVERSATION:"]
            for t in turns:
                lines.append(f"Q: {t.get('question', '').strip()}")
                # Truncate long answers to keep the prompt compact
                ans = t.get('answer', '').strip()
                lines.append(f"A: {ans[:400]}{'...' if len(ans) > 400 else ''}")
            history_block = "\n".join(lines)
        else:
            history_block = ""

        formatted = prompt.format(
            question=state["original_query"],
            history_block=history_block,
        )

        response = llm.invoke([HumanMessage(content=formatted)])
        result = _safe_parse_json(response.content)

        needs    = result.get("needs_retrieval", True)
        is_legal = result.get("is_legal_query", True)
        reason   = result.get("reason", "defaulting to retrieval")
        rewritten = result.get("rewritten_query", "").strip() or state["original_query"]

        # Guard: detect truncated rewrites.
        # The combined LLM JSON output sometimes gets cut off mid-sentence when the
        # rewritten_query is long (Groq token limits, JSON string escaping, etc.).
        # A truncated rewrite drops sub-clauses — for a compound query like
        # "...how does it differ for robbery, and what if a weapon is used?" the
        # weapon clause may be silently removed, causing §397 to score near zero.
        # Heuristic: if the original query is compound AND the rewrite is shorter
        # than 80% of the original AND doesn't end with proper punctuation,
        # treat it as truncated and fall back to the original query for safety.
        original = state["original_query"]
        is_compound_orig = _is_compound_query(original)
        # Guard: detect truncated rewrites.
        # The LLM JSON for compound queries sometimes gets cut off mid-sentence
        # (Groq token limits, JSON string escaping, etc.), silently dropping
        # sub-clauses (e.g. '...and what if a weapon is used?' disappears).
        #
        # NOTE: do NOT use a length check here. The rewrite often STARTS longer
        # than the original (formal legal phrasing) before being cut off, so
        # len(rewrite) < 0.8*len(original) is false even for clearly-truncated output.
        # The reliable signal is terminal punctuation: a complete formal legal
        # rewrite of a compound query will always end with '.', '?', '"', or "'".
        _looks_truncated = (
            bool(rewritten)
            and is_compound_orig
            and not rewritten.rstrip().endswith((".", "?", "!", "\"", "'"))
        )
        if _looks_truncated:
            logger.warning(
                f"[retrieval_decision] rewrite appears truncated (no terminal "
                f"punctuation on compound query, len={len(rewritten)}) — "
                f"falling back to original query"
            )
            rewritten = original

        elapsed = time.time() - node_start
        log_entry.update({
            "decision": needs,
            "is_legal_query": is_legal,
            "reason": reason,
            "rewritten_query": rewritten,
            "elapsed_s": round(elapsed, 3),
            "mode": "combined",
        })
        logger.info(
            f"[retrieval_decision] combined call: needs_retrieval={needs}, "
            f"is_legal_query={is_legal}, rewrite='{rewritten[:60]}...' | "
            f"{elapsed:.3f}s"
        )

        return {
            "needs_retrieval": needs,
            "is_legal_query": is_legal,
            # Store the already-produced rewritten query so query_rewrite_node
            # can be skipped when routing to hybrid_retrieve directly.
            "rewritten_query": rewritten,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }

    except Exception as e:
        # Combined call failed — fall back to the original separate decision prompt.
        elapsed = time.time() - node_start
        log_entry["error"] = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        log_entry["mode"] = "fallback_separate"
        logger.warning(
            f"[retrieval_decision] combined prompt failed ({e}), "
            f"falling back to separate decision prompt"
        )
        try:
            llm = _get_llm()
            prompt = get_prompt("retrieval_decision")  # original v2 prompt
            formatted = prompt.format(question=state["original_query"])
            response = llm.invoke([HumanMessage(content=formatted)])
            result = _safe_parse_json(response.content)
            needs    = result.get("needs_retrieval", True)
            is_legal = result.get("is_legal_query", True)
            reason   = result.get("reason", "defaulting to retrieval")
            log_entry["fallback_decision"] = needs
            logger.info(
                f"[retrieval_decision] fallback decision: needs_retrieval={needs}, "
                f"is_legal_query={is_legal}"
            )
            return {
                "needs_retrieval": needs,
                "is_legal_query": is_legal,
                "rewritten_query": "",  # query_rewrite_node will fill this
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }
        except Exception as e2:
            log_entry["fallback_error"] = str(e2)
            logger.error(f"[retrieval_decision] fallback also failed: {e2}, using safe defaults")
            return {
                "needs_retrieval": True,
                "is_legal_query": True,
                "rewritten_query": "",
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }


def query_rewrite_node(state: CitizenRAGState) -> dict:
    """
    Rewrite casual citizen query to formal legal terminology.

    This node is now SKIPPED for the common case where retrieval_decision_node
    already produced a rewritten_query via the combined prompt. It is still
    invoked as a fallback (combined prompt failed) and on the retry loop
    (route_usefulness -> query_rewrite).
    """
    node_start = time.time()
    log_entry = {"node": "query_rewrite", "timestamp": node_start}

    # If retrieval_decision_node already filled rewritten_query (combined path),
    # skip the extra LLM call and reuse it — but only on the first pass.
    existing = state.get("rewritten_query", "").strip()
    rewrite_count = state.get("rewrite_count", 0)
    if existing and rewrite_count == 0:
        elapsed = time.time() - node_start
        log_entry.update({
            "rewritten": existing,
            "skipped": True,
            "reason": "reused rewritten_query from combined decision node",
            "elapsed_s": round(elapsed, 3),
        })
        logger.info(
            f"[query_rewrite] skipped (reuse from combined node): '{existing[:60]}...' | "
            f"{elapsed:.3f}s"
        )
        return {
            "rewritten_query": existing,
            "rewrite_count": 1,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }

    # Full rewrite call — used on retry loops or when combined node failed.
    try:
        llm = _get_llm()
        prompt = get_prompt("query_rewrite")
        formatted = prompt.format(question=state["original_query"])

        response = llm.invoke([HumanMessage(content=formatted)])
        result = _safe_parse_json(response.content)

        rewritten = result.get("rewritten_query", state["original_query"])
        changes   = result.get("changes_made", "none")
        elapsed   = time.time() - node_start

        log_entry.update({
            "original": state["original_query"],
            "rewritten": rewritten,
            "changes": changes,
            "elapsed_s": round(elapsed, 3),
        })
        logger.info(f"[query_rewrite] rewritten: '{rewritten[:60]}...' | {elapsed:.3f}s")

        return {
            "rewritten_query": rewritten,
            "rewrite_count": rewrite_count + 1,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"] = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[query_rewrite] failed: {e} | {elapsed:.3f}s")
        return {
            "rewritten_query": state["original_query"],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def hybrid_retrieve_node(state: CitizenRAGState) -> dict:
    """
    Retrieve documents using hybrid BM25 + FAISS search.

    When the original query names a specific statute (e.g. "IPC"), an extra
    FAISS similarity search is run restricted to that statute's chunks and the
    results are injected into the candidate pool before reranking. This prevents
    BM25 term-frequency bias (e.g. the CrPC First Schedule drowning IPC chunks)
    from eliminating the correct statute entirely before the cross-encoder sees it.
    """
    node_start = time.time()
    log_entry = {"node": "hybrid_retrieve", "timestamp": node_start}
    try:
        from .vector_service import _get_citizen_retriever, _get_citizen_vectorstore

        retriever = _get_citizen_retriever()
        query = state.get("rewritten_query") or state["original_query"]

        results = retriever.retrieve_with_scores(query, k=8)
        docs   = [doc   for doc,   _ in results]
        scores = [score for _, score in results]

        # ── Statute-aware retrieval boost ──────────────────────────────────
        # Detect target statute from the ORIGINAL query (user-typed, always
        # has the statute name or topic keyword). If found, run supplementary
        # FAISS searches filtered to that statute and inject new docs into pool.
        #
        # For compound/multi-scenario queries (e.g. "punishment for theft, and
        # does it differ if in someone's house?") the full-query embedding is
        # "diluted" across both sub-clauses, so §380 may not appear in the
        # top-6 IPC results. We therefore also split the query on conjunctions
        # and run a SEPARATE FAISS boost for each sub-clause — "punishment for
        # theft" brings §379, "differs if in someone's house" brings §380.
        original_query = state.get("original_query", "")
        target_statute = _detect_target_statute(original_query)
        is_compound    = _is_compound_query(query) or _is_compound_query(original_query)
        statute_boost_count = 0
        if target_statute:
            try:
                vs = _get_citizen_vectorstore()
                existing_keys = {d.page_content[:200] for d in docs}

                # --- Primary boost: full query ---
                boost_k = 8 if is_compound else 6
                boosted = vs.similarity_search(
                    query,
                    k=boost_k,
                    filter={"law_name": target_statute},
                )
                new_docs = [d for d in boosted if d.page_content[:200] not in existing_keys]
                docs.extend(new_docs)
                existing_keys.update(d.page_content[:200] for d in new_docs)
                statute_boost_count += len(new_docs)

                # --- Original-query boost (runs when rewrite diverges from user intent) ---
                # The query rewriter often adds cross-statute terms ("Companies Act",
                # "Consumer Protection") that shift the embedding away from the target
                # statute. Re-searching with the original user query ensures we still
                # reach the correct IPC chunks (e.g. §415-420 for "cheated... fake docs").
                if original_query and original_query != query:
                    try:
                        orig_boosted = vs.similarity_search(
                            original_query,
                            k=6,
                            filter={"law_name": target_statute},
                        )
                        orig_new = [d for d in orig_boosted
                                    if d.page_content[:200] not in existing_keys]
                        docs.extend(orig_new)
                        existing_keys.update(d.page_content[:200] for d in orig_new)
                        statute_boost_count += len(orig_new)
                        if orig_new:
                            logger.info(
                                f"[hybrid_retrieve] original-query boost: injected "
                                f"{len(orig_new)} docs using original user query"
                            )
                    except Exception as orig_err:
                        logger.warning(
                            f"[hybrid_retrieve] original-query boost failed (non-fatal): {orig_err}"
                        )

                # --- Sub-clause boosts for compound queries ---
                if is_compound:
                    # Split on "and", "or", ",", "?" to get sub-clauses.
                    # CAP AT 2 to prevent FAISS overhead on 3-clause queries
                    # (stress-test showed 3 sub-clauses → 8s hybrid_retrieve).
                    parts = _re.split(r"\band\b|\bor\b|,|\?", query, flags=_re.IGNORECASE)
                    sub_clauses = [p.strip() for p in parts if len(p.strip()) > 12]
                    sub_clauses = sub_clauses[:2]  # hard cap: max 2 sub-clause boosts
                    for sub_q in sub_clauses:
                        try:
                            sub_boosted = vs.similarity_search(
                                sub_q,
                                k=4,
                                filter={"law_name": target_statute},
                            )
                            sub_new = [d for d in sub_boosted
                                       if d.page_content[:200] not in existing_keys]
                            docs.extend(sub_new)
                            existing_keys.update(d.page_content[:200] for d in sub_new)
                            statute_boost_count += len(sub_new)
                            if sub_new:
                                logger.info(
                                    f"[hybrid_retrieve] sub-clause boost: injected "
                                    f"{len(sub_new)} docs for '{sub_q[:40]}...'"
                                )
                        except Exception as sub_err:
                            logger.warning(
                                f"[hybrid_retrieve] sub-clause boost failed (non-fatal): {sub_err}"
                            )

                logger.info(
                    f"[hybrid_retrieve] statute boost: injected {statute_boost_count} "
                    f"'{target_statute}' docs total "
                    f"({'compound+sub-clause' if is_compound else 'primary'} mode)"
                )
            except Exception as boost_err:
                logger.warning(
                    f"[hybrid_retrieve] statute boost failed (non-fatal): {boost_err}"
                )
        # ──────────────────────────────────────────────────────────────────


        elapsed = time.time() - node_start
        log_entry.update({
            "query":              query,
            "num_results":        len(docs),
            "scores":             [round(s, 4) for s in scores],
            "statute_boost":      target_statute,
            "statute_boost_count": statute_boost_count,
            "elapsed_s":          round(elapsed, 3),
        })
        logger.info(
            f"[hybrid_retrieve] {len(docs)} docs retrieved"
            f"{f' (+{statute_boost_count} statute-boost)' if statute_boost_count else ''}"
            f" | {elapsed:.3f}s"
        )

        return {
            "retrieved_docs": docs,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"] = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[hybrid_retrieve] failed: {e} | {elapsed:.3f}s")
        return {
            "retrieved_docs": [],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }



def rerank_node(state: CitizenRAGState) -> dict:
    """Rerank retrieved documents using cross-encoder, then apply statute-aware filtering."""
    node_start = time.time()
    log_entry = {"node": "rerank", "timestamp": node_start}
    try:
        from .vector_service import _get_reranker

        reranker = _get_reranker()
        original_query = state.get("original_query", "")
        rewritten_q    = state.get("rewritten_query") or original_query
        is_compound_q  = _is_compound_query(rewritten_q) or _is_compound_query(original_query)

        # Cross-encoder scoring: ALWAYS use the original user query.
        # Rationale: the rewrite improves FAISS/BM25 recall by adding legal
        # terminology, but it is an unreliable scoring signal because:
        #   (a) Compound rewrites are prone to mid-sentence truncation, which
        #       silently drops sub-clauses (e.g. '...what if a weapon is used?')
        #       causing correctly-retrieved chunks (§397) to score below threshold.
        #   (b) Rewrites add cross-statute terms ('Companies Act', 'CrPC') that
        #       shift the embedding away from the target statute.
        # The original query preserves all sub-clauses and reflects the user's
        # exact intent — which is what the cross-encoder should measure.
        query = original_query
        logger.debug("[rerank] scoring against original_query")
        # Compound queries (e.g. "X and does it differ if Y?") need a higher
        # top_k so both the general-case and specific-case chunks survive the
        # cross-encoder threshold cut.
        effective_top_k = (
            8 if (
                _is_compound_query(query) or _is_compound_query(original_query)
                or _is_multi_right_query(query) or _is_multi_right_query(original_query)
            ) else 5
        )
        if effective_top_k != 5:
            logger.info(f"[rerank] broad rights/compound query — top_k raised to {effective_top_k}")
        docs  = state.get("retrieved_docs", [])

        if not docs:
            log_entry["status"]    = "no docs to rerank"
            log_entry["elapsed_s"] = round(time.time() - node_start, 3)
            return {
                "reranked_docs": [],
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        # For multi-right queries (e.g. "What are my rights if arrested?"),
        # the ms-marco cross-encoder underscores supplementary statute chunks
        # (§41-D, §50-A) due to their dense non-Q&A phrasing — they score
        # 0.0–0.3, below the normal threshold. Use threshold=0.0 for these
        # queries to keep all cross-encoder-ranked docs (ordering preserved).
        is_multi_right   = _is_multi_right_query(query) or _is_multi_right_query(original_query)
        rerank_threshold = 0.0 if is_multi_right else 0.3
        if is_multi_right:
            logger.info("[rerank] multi-right query — threshold=0.0 (keep all scored docs)")
        results = reranker.rerank_with_threshold(query, docs, threshold=rerank_threshold, top_k=effective_top_k)

        reranked_docs = [doc   for doc,   _ in results]
        scores        = [score for _, score in results]

        # ── Statute-boost failsafe ─────────────────────────────────────────
        # The ms-marco cross-encoder was trained on web-search query-document
        # pairs. Dense legal statute text (e.g. IPC §415-420) often scores
        # below 0.3 even when it IS the correct answer, because the model
        # doesn't see a surface-level "question answered by this passage"
        # pattern in formal legal language.
        #
        # When: (a) threshold cut returned 0 docs, AND (b) the original query
        # matches a statute topic (meaning hybrid_retrieve deliberately
        # injected statute-specific chunks), we fail open by returning the
        # top-3 statute-matching docs ranked by raw cross-encoder score
        # instead of by threshold. This is better than returning empty and
        # triggering a useless Tavily fallback.
        if not reranked_docs:
            target_statute_early = (
                _detect_target_statute(state.get("original_query", ""))
                or _detect_target_statute(state.get("rewritten_query", ""))
            )
            if target_statute_early:
                # Re-rank ALL docs without threshold, pick top-N from target statute
                all_scored = reranker.rerank_with_scores(query, docs)
                statute_fallback = [
                    doc for doc, _sc in all_scored
                    if doc.metadata.get("law_name", "") == target_statute_early
                ][:3]
                if statute_fallback:
                    reranked_docs = statute_fallback
                    scores = [sc for doc, sc in all_scored
                              if doc.metadata.get("law_name", "") == target_statute_early][:3]
                    logger.info(
                        f"[rerank] threshold-fail statute-fallback: returning top-"
                        f"{len(statute_fallback)} '{target_statute_early}' docs "
                        f"(best cross-encoder: {max(scores):.4f})"
                    )


        # ── Fix 1: Statute-aware post-rerank filter ───────────────────────
        # Detect whether the query targets a specific statute. If so, keep
        # only chunks from that statute — provided at least one hit exists.
        # Fail open: if the target statute has no hits in the top-k, skip
        # filtering and keep the mixed results rather than returning empty.
        #
        # IMPORTANT: scan BOTH original and rewritten query (OR logic).
        # The original query is always typed by the user and typically
        # contains the explicit statute name ("IPC", "RTI", etc.).
        # The rewrite LLM often paraphrases it away (e.g. "IPC theft" →
        # "punishment for theft under Section 379 Indian Penal Code"),
        # so relying only on the rewritten query causes silent filter misses.
        original_query  = state.get("original_query", "")
        rewritten_query = state.get("rewritten_query", "")
        target_statute  = (
            _detect_target_statute(original_query)
            or _detect_target_statute(rewritten_query)
        )
        statute_filtered = False
        if target_statute:
            matching = [
                doc for doc in reranked_docs
                if doc.metadata.get("law_name", "") == target_statute
            ]
            if matching:
                dropped        = len(reranked_docs) - len(matching)
                reranked_docs  = matching
                statute_filtered = True
                logger.info(
                    f"[rerank] statute filter: kept {len(matching)} '{target_statute}' "
                    f"docs, dropped {dropped} cross-statute docs"
                )
            else:
                logger.info(
                    f"[rerank] statute filter skipped: target='{target_statute}' "
                    f"not present in top-k — keeping mixed results"
                )
        # ─────────────────────────────────────────────────────────────────


        elapsed = time.time() - node_start
        log_entry.update({
            "num_input":        len(docs),
            "num_after_rerank": len(reranked_docs),
            "scores":           [round(s, 4) for s in scores],
            "statute_filter":   target_statute,
            "statute_filtered": statute_filtered,
            "elapsed_s":        round(elapsed, 3),
        })
        logger.info(
            f"[rerank] {len(docs)} -> {len(reranked_docs)} docs"
            f"{f' (statute={target_statute})' if statute_filtered else ''}"
            f" | {elapsed:.3f}s"
        )

        return {
            "reranked_docs": reranked_docs,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[rerank] failed: {e} | {elapsed:.3f}s")
        return {
            "reranked_docs": state.get("retrieved_docs", [])[:5],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }



def evaluate_relevance_node(state: CitizenRAGState) -> dict:
    """
    OPTIMISATION: Batch relevance evaluation in a single LLM call.

    Sends all reranked docs in one prompt instead of one call per doc.
    Falls back to including all docs if the batch call fails or returns
    malformed JSON (same fail-open behaviour as the old per-doc loop).
    """
    node_start = time.time()
    log_entry = {"node": "evaluate_relevance", "timestamp": node_start}
    try:
        llm   = _get_llm()
        query = state.get("rewritten_query") or state["original_query"]
        docs  = state.get("reranked_docs", [])

        if not docs:
            log_entry["status"]    = "no docs to evaluate"
            log_entry["elapsed_s"] = round(time.time() - node_start, 3)
            return {
                "relevant_docs": [],
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        # ── Attempt 1: single batched call ─────────────────────────────────
        try:
            # Build a numbered document block (600 chars each to stay within context)
            doc_blocks = "\n\n".join(
                f"[Document {i}]:\n{doc.page_content[:600]}"
                for i, doc in enumerate(docs)
            )
            batch_prompt = get_prompt("relevance_eval_batch")
            formatted = batch_prompt.format(query=query, documents=doc_blocks)

            response = llm.invoke([HumanMessage(content=formatted)])
            parsed   = _safe_parse_json(response.content)
            scores_raw = parsed.get("scores", [])

            if not isinstance(scores_raw, list) or len(scores_raw) == 0:
                raise ValueError(f"Batch response missing/empty 'scores': {response.content[:200]}")

            # Build a chunk→score map (robust to out-of-order responses)
            score_map: dict[int, float] = {}
            for entry in scores_raw:
                try:
                    chunk_idx = int(entry.get("chunk", -1))
                    score_val = float(entry.get("score", 0.0))
                    if 0 <= chunk_idx < len(docs):
                        score_map[chunk_idx] = score_val
                except (TypeError, ValueError):
                    continue

            relevant   = []
            scores_log = []
            for i, doc in enumerate(docs):
                score = score_map.get(i, None)
                if score is None:
                    # Chunk missing from response — fail open, include it
                    logger.warning(
                        f"[evaluate_relevance] batch response missing chunk {i}, including doc"
                    )
                    relevant.append(doc)
                    scores_log.append({"chunk": i, "score": "missing"})
                else:
                    scores_log.append({"chunk": i, "score": round(score, 3)})
                    if score >= 0.4:
                        relevant.append(doc)

            elapsed = time.time() - node_start
            log_entry.update({
                "mode": "batch",
                "scores": scores_log,
                "num_relevant": len(relevant),
                "elapsed_s": round(elapsed, 3),
            })
            logger.info(
                f"[evaluate_relevance] batch: {len(relevant)}/{len(docs)} relevant "
                f"| {elapsed:.3f}s (1 LLM call)"
            )
            return {
                "relevant_docs": relevant,
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        except Exception as batch_err:
            # ── Attempt 2: per-doc fallback (original sequential loop) ──────
            elapsed_batch = time.time() - node_start
            logger.warning(
                f"[evaluate_relevance] batch call failed ({batch_err}) after "
                f"{elapsed_batch:.3f}s, falling back to per-doc loop"
            )
            log_entry["batch_error"] = str(batch_err)

            relevant   = []
            scores_log = []
            for i, doc in enumerate(docs):
                try:
                    prompt    = get_prompt("relevance_eval")  # original single-doc prompt
                    formatted = prompt.format(query=query, document=doc.page_content[:1000])
                    response  = llm.invoke([HumanMessage(content=formatted)])
                    result    = _safe_parse_json(response.content)
                    score     = float(result.get("relevance_score", 0.0))
                    scores_log.append({"chunk": i, "score": round(score, 3)})
                    if score >= 0.4:
                        relevant.append(doc)
                except Exception as inner_e:
                    logger.warning(
                        f"[evaluate_relevance] per-doc fallback failed for chunk {i}: {inner_e}"
                    )
                    relevant.append(doc)  # fail open

            elapsed = time.time() - node_start
            log_entry.update({
                "mode": "per_doc_fallback",
                "scores": scores_log,
                "num_relevant": len(relevant),
                "elapsed_s": round(elapsed, 3),
            })
            logger.info(
                f"[evaluate_relevance] per-doc fallback: {len(relevant)}/{len(docs)} relevant "
                f"| {elapsed:.3f}s ({len(docs)} LLM calls)"
            )
            return {
                "relevant_docs": relevant,
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[evaluate_relevance] outer failure: {e} | {elapsed:.3f}s")
        return {
            "relevant_docs": state.get("reranked_docs", []),
            "pipeline_log":  state.get("pipeline_log", []) + [log_entry],
        }


def web_search_fallback_node(state: CitizenRAGState) -> dict:
    """
    Use Tavily API for external search when internal retrieval finds no relevant docs.

    LOOP-SAFETY: This node feeds directly into generate_node (not back through
    rerank/evaluate_relevance). When Tavily is unavailable, we gracefully fall
    back to the already-reranked docs so the pipeline can still produce an answer.
    """
    node_start = time.time()
    log_entry  = {"node": "web_search_fallback", "timestamp": node_start}
    try:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            # Tavily not configured — fall back to whatever reranked docs we
            # already have so generate_node can still produce an answer.
            # Set relevant_docs from reranked_docs to avoid returning empty.
            fallback_docs = state.get("reranked_docs", [])[:3]
            log_entry["status"]    = "no TAVILY_API_KEY — using reranked_docs as fallback"
            log_entry["elapsed_s"] = round(time.time() - node_start, 3)
            logger.warning(
                "[web_search_fallback] Tavily not configured; "
                f"falling back to {len(fallback_docs)} reranked doc(s)"
            )
            return {
                "relevant_docs": fallback_docs,
                "web_search_attempted": True,
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        llm = _get_llm()
        rewrite_prompt = get_prompt("web_search_rewrite")
        formatted  = rewrite_prompt.format(question=state["original_query"])
        response   = llm.invoke([HumanMessage(content=formatted)])
        web_query  = response.content.strip()

        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        search_results = client.search(
            query=web_query,
            search_depth="advanced",
            max_results=5,
            include_domains=["indiankanoon.org", "legislative.gov.in", "legalserviceindia.com"],
        )

        docs = []
        for result in search_results.get("results", []):
            doc = Document(
                page_content=result.get("content", ""),
                metadata={
                    "source": result.get("url", "web"),
                    "title":  result.get("title", "Web Result"),
                    "law_name": "Web Search",
                    "page": "N/A",
                },
            )
            docs.append(doc)

        elapsed = time.time() - node_start
        log_entry.update({
            "web_query":          web_query,
            "num_results":        len(docs),
            "web_search_attempted": True,
            "elapsed_s":          round(elapsed, 3),
        })
        logger.info(
            f"[web_search_fallback] {len(docs)} results for '{web_query[:50]}...' | {elapsed:.3f}s"
        )
        # Set as relevant_docs so generate_node picks them up directly
        return {
            "relevant_docs":       docs,
            "web_search_attempted": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[web_search_fallback] failed: {e} | {elapsed:.3f}s")
        fallback_docs = state.get("reranked_docs", [])[:3]
        return {
            "relevant_docs":       fallback_docs,
            "web_search_attempted": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def off_topic_response_node(state: CitizenRAGState) -> dict:
    """Return a fixed refusal for queries not related to Indian law.

    No LLM call is made — the response is static to avoid any hallucination.
    """
    node_start = time.time()
    log_entry  = {
        "node": "off_topic_response",
        "timestamp": node_start,
        "reason": "Query classified as non-Indian-law topic",
    }
    logger.info("[off_topic_response] canned refusal (no LLM call)")
    log_entry["elapsed_s"] = round(time.time() - node_start, 3)
    return {
        "answer": (
            "I'm NyayaMitra, an Indian legal assistant. "
            "I can only help with questions about Indian law, legal rights, and procedures. "
            "Could you rephrase your question as a legal query?"
        ),
        "sources": [],
        "hallucination_status": "not_applicable",
        "is_useful": True,
        "pipeline_log": state.get("pipeline_log", []) + [log_entry],
    }


def direct_generate_node(state: CitizenRAGState) -> dict:
    """Generate answer directly without retrieval for simple legal queries."""
    node_start = time.time()
    log_entry  = {"node": "direct_generate", "timestamp": node_start}
    try:
        llm = _get_llm()
        prompt    = get_prompt("citizen_direct_answer")
        formatted = prompt.format(question=state["original_query"])

        response = llm.invoke([HumanMessage(content=formatted)])
        elapsed  = time.time() - node_start

        log_entry["method"]    = "direct_parametric"
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.info(f"[direct_generate] done | {elapsed:.3f}s")

        return {
            "answer": response.content,
            "sources": [],
            "hallucination_status": "fully_supported",
            "is_useful": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[direct_generate] failed: {e} | {elapsed:.3f}s")
        return {
            "answer": "I'm sorry, I couldn't generate an answer. Please try again.",
            "sources": [],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def generate_node(state: CitizenRAGState) -> dict:
    """Generate citation-grounded answer from relevant documents."""
    node_start = time.time()
    log_entry  = {"node": "generate", "timestamp": node_start}
    try:
        llm  = _get_llm()
        docs = state.get("relevant_docs", []) or state.get("reranked_docs", [])

        if not docs:
            # Distinguish between two failure modes so the user gets an honest
            # message rather than an opaque "I cannot find reliable information."
            web_attempted  = state.get("web_search_attempted", False)
            tavily_missing = not os.getenv("TAVILY_API_KEY")

            if web_attempted and tavily_missing:
                # Pipeline reached the web-search fallback but Tavily wasn't configured,
                # so the fallback silently returned empty. This is an infrastructure gap,
                # not a "this topic doesn't exist in law" situation.
                answer_text = (
                    "I couldn't find a matching answer in my internal legal database, "
                    "and web search isn't currently configured to help fill the gap. "
                    "Please consult a lawyer or try rephrasing your question with "
                    "specific section numbers (e.g., \"IPC Section 420\")."
                )
            else:
                answer_text = "I cannot find reliable information on this in the legal database."

            log_entry["status"]    = "no docs available"
            log_entry["elapsed_s"] = round(time.time() - node_start, 3)
            return {
                "answer": answer_text,
                "sources": [],
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        context_parts = []
        sources       = []
        for i, doc in enumerate(docs):
            law = doc.metadata.get("law_name", "Law")

            # Fix 2: Use page_label (1-indexed, matches what the LLM cites
            # inline) so the source card page equals the inline citation.
            # Fallback chain: page_label -> page+1 -> raw page -> "?"
            raw_page   = doc.metadata.get("page")
            page_label = doc.metadata.get("page_label")
            if page_label is not None:
                display_page = page_label          # already the human-readable label
            elif raw_page is not None:
                try:
                    display_page = int(raw_page) + 1   # 0-indexed -> 1-indexed
                except (TypeError, ValueError):
                    display_page = raw_page
            else:
                display_page = "?"

            context_parts.append(
                f"[Source {i+1}] ({law}, pg {display_page}):\n{doc.page_content}"
            )
            sources.append({
                "law":         law,
                "page":        display_page,
                "chunk_index": i + 1,
            })

        context   = "\n\n".join(context_parts)
        prompt    = get_prompt("citizen_answer")
        formatted = prompt.format(
            context=context,
            intent=state.get("intent", "general"),
            instruction=state.get("instruction", "Provide a helpful legal answer."),
            question=state["original_query"],
        )

        response = llm.invoke([
            SystemMessage(content="You are NyayaMitra, a trusted Indian legal assistant."),
            HumanMessage(content=formatted),
        ])
        elapsed = time.time() - node_start

        log_entry.update({"num_sources": len(sources), "elapsed_s": round(elapsed, 3)})
        logger.info(f"[generate] {len(sources)} sources | {elapsed:.3f}s")

        return {
            "answer": response.content,
            "sources": sources,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[generate] failed: {e} | {elapsed:.3f}s")
        return {
            "answer": "I encountered an error while generating your answer. Please try again.",
            "sources": [],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def hallucination_check_node(state: CitizenRAGState) -> dict:
    """Check if generated answer is grounded in retrieved sources."""
    node_start = time.time()
    log_entry  = {"node": "hallucination_check", "timestamp": node_start}
    try:
        llm    = _get_llm()
        docs   = state.get("relevant_docs", []) or state.get("reranked_docs", [])
        answer = state.get("answer", "")

        if not docs or not answer:
            log_entry["status"]    = "skipped (no docs or answer)"
            log_entry["elapsed_s"] = round(time.time() - node_start, 3)
            return {
                "hallucination_status": "fully_supported",
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        sources_text = "\n\n".join([
            f"[Source {i+1}]: {doc.page_content[:800]}"
            for i, doc in enumerate(docs)
        ])

        prompt    = get_prompt("hallucination_check")
        formatted = prompt.format(sources=sources_text, answer=answer)
        response  = llm.invoke([HumanMessage(content=formatted)])
        result    = _safe_parse_json(response.content)

        verdict     = result.get("verdict", "fully_supported")
        unsupported = result.get("unsupported_claims", [])
        elapsed     = time.time() - node_start

        log_entry.update({
            "verdict": verdict,
            "unsupported_claims": unsupported,
            "elapsed_s": round(elapsed, 3),
        })
        logger.info(f"[hallucination_check] {verdict} | {elapsed:.3f}s")

        return {
            "hallucination_status": verdict,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[hallucination_check] failed: {e} | {elapsed:.3f}s")
        return {
            "hallucination_status": "fully_supported",
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def answer_revision_node(state: CitizenRAGState) -> dict:
    """Revise answer to remove unsupported claims."""
    node_start = time.time()
    log_entry  = {"node": "answer_revision", "timestamp": node_start}
    try:
        llm  = _get_llm()
        docs = state.get("relevant_docs", []) or state.get("reranked_docs", [])

        sources_text = "\n\n".join([
            f"[Source {i+1}]: {doc.page_content[:800]}"
            for i, doc in enumerate(docs)
        ])

        unsupported = []
        for entry in reversed(state.get("pipeline_log", [])):
            if entry.get("node") == "hallucination_check":
                unsupported = entry.get("unsupported_claims", [])
                break

        prompt    = get_prompt("answer_revision")
        formatted = prompt.format(
            sources=sources_text,
            answer=state.get("answer", ""),
            unsupported_claims="\n".join(unsupported) if unsupported else "None specified",
        )
        response = llm.invoke([HumanMessage(content=formatted)])

        retry_count = state.get("retry_count", 0) + 1
        elapsed     = time.time() - node_start
        log_entry.update({"retry_count": retry_count, "elapsed_s": round(elapsed, 3)})
        logger.info(f"[answer_revision] retry {retry_count} | {elapsed:.3f}s")

        return {
            "answer": response.content,
            "retry_count": retry_count,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[answer_revision] failed: {e} | {elapsed:.3f}s")
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def usefulness_check_node(state: CitizenRAGState) -> dict:
    """Check if final answer actually addresses the original question."""
    node_start = time.time()
    log_entry  = {"node": "usefulness_check", "timestamp": node_start}
    try:
        llm       = _get_llm()
        prompt    = get_prompt("usefulness_check")
        formatted = prompt.format(
            question=state["original_query"],
            answer=state.get("answer", ""),
        )

        response  = llm.invoke([HumanMessage(content=formatted)])
        result    = _safe_parse_json(response.content)
        is_useful = result.get("is_useful", True)
        gap       = result.get("gap", "")
        elapsed   = time.time() - node_start

        log_entry.update({"is_useful": is_useful, "gap": gap, "elapsed_s": round(elapsed, 3)})
        logger.info(f"[usefulness_check] is_useful={is_useful} | {elapsed:.3f}s")

        return {
            "is_useful": is_useful,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        elapsed = time.time() - node_start
        log_entry["error"]     = str(e)
        log_entry["elapsed_s"] = round(elapsed, 3)
        logger.error(f"[usefulness_check] failed: {e} | {elapsed:.3f}s")
        return {
            "is_useful": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


# ---------------------------------------------------------------------------
# Conditional Edge Functions
# ---------------------------------------------------------------------------

def route_retrieval_decision(state: CitizenRAGState) -> str:
    # First gate: reject queries not related to Indian law entirely
    if not state.get("is_legal_query", True):
        return "off_topic_response"
    # Second gate: legal query — choose retrieval vs. parametric path
    if state.get("needs_retrieval", True):
        # When the combined node already produced a rewritten_query, route
        # directly to hybrid_retrieve to skip the separate query_rewrite call.
        # When rewritten_query is empty (combined node failed), fall back to
        # query_rewrite_node which will do the rewrite as before.
        if state.get("rewritten_query", "").strip():
            return "hybrid_retrieve"  # skip query_rewrite — already done
        return "query_rewrite"       # fallback: combined node failed
    return "direct_generate"


def route_relevance(state: CitizenRAGState) -> str:
    if state.get("relevant_docs"):
        return "generate"
    return "web_search_fallback"


def route_hallucination(state: CitizenRAGState) -> str:
    status = state.get("hallucination_status", "fully_supported")
    if status == "fully_supported":
        return "usefulness_check"
    return "answer_revision"


def route_revision(state: CitizenRAGState) -> str:
    if state.get("retry_count", 0) < 2:
        return "hallucination_check"
    return "usefulness_check"


def route_usefulness(state: CitizenRAGState) -> str:
    is_useful = state.get("is_useful", True)
    rewrite_count = state.get("rewrite_count", 0)
    if is_useful or rewrite_count >= 2:
        return END
    return "query_rewrite"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_citizen_graph() -> StateGraph:
    """Build and compile the citizen RAG LangGraph pipeline."""

    graph = StateGraph(CitizenRAGState)

    # Add nodes
    graph.add_node("retrieval_decision", retrieval_decision_node)
    graph.add_node("off_topic_response", off_topic_response_node)
    graph.add_node("query_rewrite", query_rewrite_node)
    graph.add_node("hybrid_retrieve", hybrid_retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("evaluate_relevance", evaluate_relevance_node)
    graph.add_node("web_search_fallback", web_search_fallback_node)
    graph.add_node("direct_generate", direct_generate_node)
    graph.add_node("generate", generate_node)
    graph.add_node("hallucination_check", hallucination_check_node)
    graph.add_node("answer_revision", answer_revision_node)
    graph.add_node("usefulness_check", usefulness_check_node)

    # Set entry point
    graph.set_entry_point("retrieval_decision")

    # Conditional edges — is_legal_query checked first, then needs_retrieval.
    # route_retrieval_decision may jump directly to hybrid_retrieve (skipping
    # query_rewrite) when the combined node already produced a rewritten_query.
    graph.add_conditional_edges(
        "retrieval_decision",
        route_retrieval_decision,
        {
            "off_topic_response": "off_topic_response",
            "hybrid_retrieve":    "hybrid_retrieve",   # fast path: rewrite already done
            "query_rewrite":      "query_rewrite",      # fallback path
            "direct_generate":    "direct_generate",
        },
    )

    # Off-topic: static refusal, routes directly to END
    graph.add_edge("off_topic_response", END)

    # query_rewrite always feeds into hybrid_retrieve
    graph.add_edge("query_rewrite", "hybrid_retrieve")
    graph.add_edge("hybrid_retrieve", "rerank")
    graph.add_edge("rerank", "evaluate_relevance")

    # Relevance routing
    graph.add_conditional_edges(
        "evaluate_relevance",
        route_relevance,
        {"generate": "generate", "web_search_fallback": "web_search_fallback"},
    )

    graph.add_edge("web_search_fallback", "generate")  # skip rerank+evaluate to break loop
    graph.add_edge("generate", "hallucination_check")

    graph.add_conditional_edges(
        "hallucination_check",
        route_hallucination,
        {"usefulness_check": "usefulness_check", "answer_revision": "answer_revision"},
    )

    graph.add_conditional_edges(
        "answer_revision",
        route_revision,
        {"hallucination_check": "hallucination_check", "usefulness_check": "usefulness_check"},
    )

    graph.add_conditional_edges(
        "usefulness_check",
        route_usefulness,
        {END: END, "query_rewrite": "query_rewrite"},
    )

    graph.add_edge("direct_generate", END)

    return graph.compile()


# Module-level compiled graph (lazy init via function in vector_service)
_citizen_graph = None


def get_citizen_graph():
    """Get or create the compiled citizen graph."""
    global _citizen_graph
    if _citizen_graph is None:
        _citizen_graph = build_citizen_graph()
    return _citizen_graph


def invoke_citizen_pipeline(
    question: str,
    intent: str = "general",
    instruction: str = "Provide a helpful legal answer.",
    history: list = None,
) -> dict:
    """
    Run the full citizen RAG pipeline.

    Returns dict with answer, sources, pipeline_log, retrieval_method,
    hallucination_status, confidence, and total_elapsed_s.
    """
    pipeline_start = time.time()
    graph = get_citizen_graph()

    initial_state = {
        "original_query":       question,
        "rewritten_query":      "",
        "needs_retrieval":      True,
        "is_legal_query":       True,  # assumed legal until retrieval_decision_node says otherwise
        "retrieved_docs":       [],
        "reranked_docs":        [],
        "relevant_docs":        [],
        "answer":               "",
        "hallucination_status": "",
        "is_useful":            False,
        "retry_count":          0,
        "rewrite_count":        0,
        "sources":              [],
        "pipeline_log":         [],
        "intent":               intent,
        "instruction":          instruction,
        "conversation_history": history or [],
    }

    result = graph.invoke(initial_state)
    total_elapsed = time.time() - pipeline_start

    # Determine retrieval method from pipeline log
    nodes_fired = [entry.get("node") for entry in result.get("pipeline_log", [])]
    if "direct_generate" in nodes_fired:
        retrieval_method = "direct"
    elif "web_search_fallback" in nodes_fired:
        retrieval_method = "web_fallback"
    elif "off_topic_response" in nodes_fired:
        retrieval_method = "off_topic"
    else:
        retrieval_method = "hybrid"

    # Calculate confidence from reranker scores
    confidence = 0.0
    for entry in result.get("pipeline_log", []):
        if entry.get("node") == "rerank" and entry.get("scores"):
            scores = entry["scores"]
            confidence = sum(scores) / len(scores) if scores else 0.0
            break

    # Per-node timing summary for easy log scanning
    timing_summary = [
        f"{e['node']}={e.get('elapsed_s', '?')}s"
        for e in result.get("pipeline_log", [])
        if "elapsed_s" in e
    ]
    logger.info(
        f"[citizen_pipeline] TOTAL {total_elapsed:.2f}s | "
        f"nodes: {', '.join(timing_summary) or 'none'}"
    )

    return {
        "answer":               result.get("answer", ""),
        "sources":              result.get("sources", []),
        "pipeline_log":         result.get("pipeline_log", []),
        "retrieval_method":     retrieval_method,
        "hallucination_status": result.get("hallucination_status", "unknown"),
        "confidence":           round(confidence, 4),
        "total_elapsed_s":      round(total_elapsed, 2),
    }


# Human-readable stage labels shown to the user as the pipeline progresses.
STAGE_MESSAGES: dict[str, str] = {
    "retrieval_decision": "Understanding your question...",
    "query_rewrite":      "Refining the legal search...",
    "hybrid_retrieve":    "Searching the legal database...",
    "rerank":             "Ranking the most relevant sources...",
    "evaluate_relevance": "Checking source relevance...",
    "web_search_fallback":"Searching the web for more context...",
    "off_topic_response": "Responding to your query...",
    "direct_generate":    "Generating your answer...",
    "generate":           "Drafting a grounded answer...",
    "hallucination_check":"Verifying the answer against sources...",
    "answer_revision":    "Correcting unsupported claims...",
    "usefulness_check":   "Making sure this answers your question...",
}


def stream_citizen_pipeline(
    question: str,
    intent: str = "general",
    instruction: str = "Provide a helpful legal answer.",
    history: list = None,
):
    """
    Streaming generator version of invoke_citizen_pipeline.

    Yields Server-Sent Event (SSE) formatted strings:
      • ``data: {"type": "status", "message": "..."}\n\n``  — one per node as it completes
      • ``data: {"type": "final",  "answer": "...", "sources": [...]}\n\n``  — once done
      • ``data: {"type": "error",  "message": "..."}\n\n``  — on unexpected failure

    The non-streaming ``invoke_citizen_pipeline`` is left untouched.
    """
    import json as _json

    pipeline_start = time.time()
    graph = get_citizen_graph()

    initial_state: dict = {
        "original_query":       question,
        "rewritten_query":      "",
        "needs_retrieval":      True,
        "is_legal_query":       True,
        "retrieved_docs":       [],
        "reranked_docs":        [],
        "relevant_docs":        [],
        "answer":               "",
        "hallucination_status": "",
        "is_useful":            False,
        "retry_count":          0,
        "rewrite_count":        0,
        "sources":              [],
        "pipeline_log":         [],
        "intent":               intent,
        "instruction":          instruction,
        "web_search_attempted": False,
        "conversation_history": history or [],
    }

    seen_nodes: set[str] = set()
    last_state: dict = {}

    try:
        # LangGraph .stream() with stream_mode="updates" yields dicts of the
        # form  {node_name: {state_key: value, ...}}  after each node completes.
        for chunk in graph.stream(initial_state, stream_mode="updates"):
            for node_name, state_update in chunk.items():
                # Emit a status event the first time each node fires
                if node_name not in seen_nodes:
                    seen_nodes.add(node_name)
                    msg = STAGE_MESSAGES.get(node_name)
                    if msg:
                        yield f"data: {_json.dumps({'type': 'status', 'message': msg})}\n\n"
                # Accumulate the latest state values
                last_state.update(state_update)

        total_elapsed = time.time() - pipeline_start

        # Build final answer payload
        answer  = last_state.get("answer", "")
        sources = last_state.get("sources", [])
        h_status = last_state.get("hallucination_status", "unknown")

        # Determine retrieval method from seen nodes
        if "direct_generate" in seen_nodes:
            retrieval_method = "direct"
        elif "web_search_fallback" in seen_nodes:
            retrieval_method = "web_fallback"
        elif "off_topic_response" in seen_nodes:
            retrieval_method = "off_topic"
        else:
            retrieval_method = "hybrid"

        yield f"data: {_json.dumps({'type': 'final', 'answer': answer, 'sources': sources, 'hallucination_status': h_status, 'retrieval_method': retrieval_method, 'total_elapsed_s': round(total_elapsed, 2)})}\n\n"

    except Exception as exc:
        logger.error(f"[stream_citizen_pipeline] error: {exc}")
        yield f"data: {_json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
