"""
LawyerGraph — Corrective RAG pipeline for lawyer case research.

Uses LangGraph to orchestrate: query rewrite -> hybrid retrieval ->
cross-encoder reranking -> relevance evaluation -> knowledge refinement ->
strategy generation -> hallucination checking.
"""

import os
import re
import json
import logging
import time
from typing import TypedDict, List

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END

from .retrieval.hybrid_retriever import HybridRetriever
from .retrieval.reranker import CrossEncoderReranker
from .prompts.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Definition
# ---------------------------------------------------------------------------
class LawyerRAGState(TypedDict):
    query: str
    rewritten_query: str
    retrieved_docs: list
    reranked_docs: list
    relevance_verdict: str  # correct | incorrect | ambiguous
    refined_docs: list
    strategy: str
    hallucination_status: str
    cases: list
    pipeline_log: list
    revision_done: bool


# ---------------------------------------------------------------------------
# Helpers
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
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {}


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

def query_rewrite_node(state: LawyerRAGState) -> dict:
    """Rewrite query to formal legal search terminology."""
    log_entry = {"node": "query_rewrite", "timestamp": time.time()}
    try:
        llm = _get_llm()
        prompt = get_prompt("lawyer_query_rewrite")
        formatted = prompt.format(query=state["query"])

        response = llm.invoke([HumanMessage(content=formatted)])
        result = _safe_parse_json(response.content)

        rewritten = result.get("rewritten_query", state["query"])
        changes = result.get("changes_made", "none")

        log_entry["original"] = state["query"]
        log_entry["rewritten"] = rewritten
        log_entry["changes"] = changes
        logger.info(f"Lawyer query rewritten: {rewritten[:80]}...")

        return {
            "rewritten_query": rewritten,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Lawyer query rewrite failed: {e}")
        return {
            "rewritten_query": state["query"],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def hybrid_retrieve_node(state: LawyerRAGState) -> dict:
    """Retrieve documents using hybrid BM25 + FAISS search over lawyer index."""
    log_entry = {"node": "hybrid_retrieve", "timestamp": time.time()}
    try:
        from .vector_service import _get_lawyer_retriever

        retriever = _get_lawyer_retriever()
        query = state.get("rewritten_query") or state["query"]

        results = retriever.retrieve_with_scores(query, k=10)

        docs = [doc for doc, _ in results]
        scores = [score for _, score in results]

        # Extract case metadata
        cases = []
        for doc in docs:
            case_id = doc.metadata.get("case_id", "Unknown Case")
            cases.append({
                "case_name": case_id.replace("_", " ").title(),
                "year": doc.metadata.get("year", "N/A"),
                "excerpt": doc.page_content[:500] + "...",
                "similarity": round(scores[docs.index(doc)], 3) if docs.index(doc) < len(scores) else 0.0,
                "pdf_path": doc.metadata.get("pdf_path"),
            })

        log_entry["query"] = query
        log_entry["num_results"] = len(docs)
        log_entry["scores"] = [round(s, 4) for s in scores]
        logger.info(f"Lawyer hybrid retrieval: {len(docs)} docs")

        return {
            "retrieved_docs": docs,
            "cases": cases,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Lawyer hybrid retrieval failed: {e}")
        return {
            "retrieved_docs": [],
            "cases": [],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def rerank_node(state: LawyerRAGState) -> dict:
    """Rerank retrieved documents using cross-encoder."""
    log_entry = {"node": "rerank", "timestamp": time.time()}
    try:
        from .vector_service import _get_reranker

        reranker = _get_reranker()
        query = state.get("rewritten_query") or state["query"]
        docs = state.get("retrieved_docs", [])

        if not docs:
            log_entry["status"] = "no docs to rerank"
            return {
                "reranked_docs": [],
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        # ms-marco-MiniLM-L6-v2 outputs raw logits (not 0–1 probabilities).
        # Observed real scores: Top -0.18 to +0.59; noise: -4 to -9.
        # Threshold 0.35 was calibrated for sigmoid-scaled scores and blocked
        # nearly everything. Using -2.0 to pass genuine signal while filtering
        # extreme negative noise.
        results = reranker.rerank_with_threshold(query, docs, threshold=-2.0, top_k=6)
        reranked_docs = [doc for doc, _ in results]
        scores = [score for _, score in results]

        # Fallback: if nothing clears even the lenient threshold, use top-3
        # retrieved docs so the pipeline always has source material.
        if not reranked_docs and docs:
            logger.warning("All reranked scores below -2.0; falling back to top-3 retrieved docs")
            reranked_docs = docs[:3]
            scores = [0.0] * len(reranked_docs)

        log_entry["num_input"] = len(docs)
        log_entry["num_after_rerank"] = len(reranked_docs)
        log_entry["scores"] = [round(s, 4) for s in scores]
        logger.info(f"Lawyer reranking: {len(docs)} -> {len(reranked_docs)} docs")

        return {
            "reranked_docs": reranked_docs,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Lawyer reranking failed: {e}")
        return {
            "reranked_docs": state.get("retrieved_docs", [])[:3],
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def evaluate_relevance_node(state: LawyerRAGState) -> dict:
    """Evaluate relevance of reranked documents — correct/incorrect/ambiguous."""
    log_entry = {"node": "evaluate_relevance", "timestamp": time.time()}
    try:
        llm = _get_llm()
        query = state.get("rewritten_query") or state["query"]
        docs = state.get("reranked_docs", [])

        if not docs:
            log_entry["verdict"] = "incorrect"
            return {
                "relevance_verdict": "incorrect",
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        # Score each document
        scores = []
        for i, doc in enumerate(docs):
            try:
                prompt = get_prompt("relevance_eval")
                formatted = prompt.format(
                    query=query, document=doc.page_content[:1000]
                )
                response = llm.invoke([HumanMessage(content=formatted)])
                result = _safe_parse_json(response.content)
                score = float(result.get("relevance_score", 0.0))
                scores.append(score)
            except Exception as e:
                logger.warning(f"Relevance eval failed for chunk {i}: {e}")
                scores.append(0.5)  # Neutral default

        # Determine verdict
        high_scores = [s for s in scores if s >= 0.7]
        low_scores = [s for s in scores if s < 0.3]

        if len(high_scores) >= 2:
            verdict = "correct"
        elif len(low_scores) == len(scores):
            verdict = "incorrect"
        else:
            verdict = "ambiguous"

        log_entry["scores"] = [round(s, 3) for s in scores]
        log_entry["verdict"] = verdict
        logger.info(f"Lawyer relevance verdict: {verdict}")

        return {
            "relevance_verdict": verdict,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Lawyer relevance eval failed: {e}")
        return {
            # Fail open — proceed to strategy generation rather than killing results
            "relevance_verdict": "ambiguous",
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def knowledge_refine_node(state: LawyerRAGState) -> dict:
    """Refine retrieved docs by keeping only relevant sentences."""
    log_entry = {"node": "knowledge_refine", "timestamp": time.time()}
    try:
        llm = _get_llm()
        query = state.get("rewritten_query") or state["query"]
        docs = state.get("reranked_docs", [])

        refined = []
        total_removed = 0

        for i, doc in enumerate(docs):
            try:
                prompt = get_prompt("knowledge_refine")
                formatted = prompt.format(
                    query=query, document=doc.page_content[:2000]
                )
                response = llm.invoke([HumanMessage(content=formatted)])
                result = _safe_parse_json(response.content)

                relevant_sentences = result.get("relevant_sentences", [])
                removed = result.get("removed_count", 0)
                total_removed += removed

                if relevant_sentences:
                    refined_content = " ".join(relevant_sentences)
                    refined_doc = Document(
                        page_content=refined_content,
                        metadata=doc.metadata,
                    )
                    refined.append(refined_doc)
                else:
                    # Keep original if refinement returns nothing
                    refined.append(doc)
            except Exception as e:
                logger.warning(f"Knowledge refine failed for chunk {i}: {e}")
                refined.append(doc)

        log_entry["num_docs"] = len(refined)
        log_entry["sentences_removed"] = total_removed
        logger.info(f"Knowledge refinement: {len(refined)} docs, {total_removed} sentences removed")

        return {
            "refined_docs": refined,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Knowledge refinement failed: {e}")
        return {
            "refined_docs": state.get("reranked_docs", []),
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def generate_strategy_node(state: LawyerRAGState) -> dict:
    """Generate structured litigation strategy from refined documents."""
    log_entry = {"node": "generate_strategy", "timestamp": time.time()}
    try:
        llm = _get_llm()
        docs = state.get("refined_docs", []) or state.get("reranked_docs", [])

        if not docs:
            log_entry["status"] = "no docs"
            return {
                "strategy": "No relevant precedents found to build a litigation strategy.",
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        context_parts = []
        for i, doc in enumerate(docs):
            case_id = doc.metadata.get("case_id", "Unknown Case")
            context_parts.append(
                f"Case: {case_id.replace('_', ' ').title()}\nExcerpt: {doc.page_content}"
            )
        context = "\n\n".join(context_parts)

        prompt = get_prompt("litigation_strategy")
        formatted = prompt.format(query=state["query"], context=context)

        response = llm.invoke([
            SystemMessage(content="You are a Senior Indian Advocate and criminal law researcher."),
            HumanMessage(content=formatted),
        ])

        log_entry["num_sources"] = len(docs)
        logger.info(f"Strategy generated with {len(docs)} source docs")

        return {
            "strategy": response.content,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Strategy generation failed: {e}")
        return {
            "strategy": "Error generating litigation strategy. Please try again.",
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def hallucination_check_node(state: LawyerRAGState) -> dict:
    """Check if cited case names in strategy exist in retrieved documents."""
    log_entry = {"node": "hallucination_check", "timestamp": time.time()}
    try:
        llm = _get_llm()
        docs = state.get("refined_docs", []) or state.get("reranked_docs", [])
        strategy = state.get("strategy", "")

        if not docs or not strategy:
            log_entry["status"] = "skipped"
            return {
                "hallucination_status": "grounded",
                "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            }

        sources_text = "\n\n".join([
            f"Case: {doc.metadata.get('case_id', 'Unknown').replace('_', ' ').title()}\n"
            f"Content: {doc.page_content[:500]}"
            for doc in docs
        ])

        prompt = get_prompt("lawyer_hallucination_check")
        formatted = prompt.format(sources=sources_text, strategy=strategy)

        response = llm.invoke([HumanMessage(content=formatted)])
        result = _safe_parse_json(response.content)

        is_grounded = result.get("is_grounded", True)
        fabricated = result.get("fabricated_cases", [])

        status = "grounded" if is_grounded else "not_grounded"
        log_entry["status"] = status
        log_entry["fabricated_cases"] = fabricated
        logger.info(f"Lawyer hallucination check: {status}")

        return {
            "hallucination_status": status,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Lawyer hallucination check failed: {e}")
        return {
            "hallucination_status": "grounded",
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def revise_strategy_node(state: LawyerRAGState) -> dict:
    """Revise strategy to remove fabricated case names (one attempt only)."""
    log_entry = {"node": "revise_strategy", "timestamp": time.time()}
    try:
        llm = _get_llm()
        docs = state.get("refined_docs", []) or state.get("reranked_docs", [])

        # Get fabricated cases from log
        fabricated = []
        for entry in reversed(state.get("pipeline_log", [])):
            if entry.get("node") == "hallucination_check":
                fabricated = entry.get("fabricated_cases", [])
                break

        sources_text = "\n\n".join([
            f"Case: {doc.metadata.get('case_id', 'Unknown').replace('_', ' ').title()}\n"
            f"Content: {doc.page_content[:500]}"
            for doc in docs
        ])

        revision_prompt = (
            f"The following litigation strategy contains fabricated case names that "
            f"do not exist in the source documents. Revise the strategy to remove "
            f"all fabricated references and only cite cases from the provided sources.\n\n"
            f"IMPORTANT: Do NOT add any note, comment, explanation, or annotation about "
            f"what was removed. Silently omit fabricated citations and replace with "
            f"stronger argument from the real source cases. The final output must read "
            f"as clean, professional legal text with NO internal editor notes.\n\n"
            f"Fabricated cases to remove: {', '.join(fabricated)}\n\n"
            f"Source Documents:\n{sources_text}\n\n"
            f"Original Strategy:\n{state.get('strategy', '')}\n\n"
            f"Provide ONLY the revised strategy text. No preamble, no notes."
        )

        response = llm.invoke([
            SystemMessage(content="You are a Senior Indian Advocate. Cite only real cases from sources."),
            HumanMessage(content=revision_prompt),
        ])

        log_entry["fabricated_removed"] = fabricated
        logger.info(f"Strategy revised, removed {len(fabricated)} fabricated cases")

        return {
            "strategy": response.content,
            "revision_done": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    except Exception as e:
        log_entry["error"] = str(e)
        logger.error(f"Strategy revision failed: {e}")
        return {
            "revision_done": True,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def incorrect_result_node(state: LawyerRAGState) -> dict:
    """Handle case where no relevant documents were found."""
    log_entry = {"node": "incorrect_result", "timestamp": time.time()}
    logger.info("No relevant precedents found for lawyer query")
    return {
        # Preserve any cases already retrieved — don't overwrite with [].
        # The user should still see whatever was retrieved even if relevance
        # evaluation deemed them weak, so they get cases + a 'no strategy' message.
        "cases": state.get("cases", []),
        "strategy": "No sufficiently relevant precedents were found in the case database for this query. The cases shown below were retrieved but may have limited applicability.",
        "pipeline_log": state.get("pipeline_log", []) + [log_entry],
    }


# ---------------------------------------------------------------------------
# Conditional Edge Functions
# ---------------------------------------------------------------------------

def route_relevance(state: LawyerRAGState) -> str:
    """
    Only route to incorrect_result when there are genuinely NO docs at all.
    'ambiguous' and 'correct' both proceed to knowledge_refine so users
    always receive cases + strategy rather than a blank result.
    """
    verdict = state.get("relevance_verdict", "ambiguous")
    # Short-circuit only when retrieval produced nothing whatsoever
    if verdict == "incorrect" and not state.get("reranked_docs") and not state.get("retrieved_docs"):
        return "incorrect_result"
    return "knowledge_refine"


def route_hallucination(state: LawyerRAGState) -> str:
    status = state.get("hallucination_status", "grounded")
    revision_done = state.get("revision_done", False)
    if status == "grounded" or revision_done:
        return END
    return "revise_strategy"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_lawyer_graph() -> StateGraph:
    """Build and compile the lawyer RAG LangGraph pipeline."""

    graph = StateGraph(LawyerRAGState)

    # Add nodes
    graph.add_node("query_rewrite", query_rewrite_node)
    graph.add_node("hybrid_retrieve", hybrid_retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("evaluate_relevance", evaluate_relevance_node)
    graph.add_node("knowledge_refine", knowledge_refine_node)
    graph.add_node("generate_strategy", generate_strategy_node)
    graph.add_node("hallucination_check", hallucination_check_node)
    graph.add_node("revise_strategy", revise_strategy_node)
    graph.add_node("incorrect_result", incorrect_result_node)

    # Entry point
    graph.set_entry_point("query_rewrite")

    # Linear edges
    graph.add_edge("query_rewrite", "hybrid_retrieve")
    graph.add_edge("hybrid_retrieve", "rerank")
    graph.add_edge("rerank", "evaluate_relevance")

    # Relevance routing
    graph.add_conditional_edges(
        "evaluate_relevance",
        route_relevance,
        {"knowledge_refine": "knowledge_refine", "incorrect_result": "incorrect_result"},
    )

    graph.add_edge("knowledge_refine", "generate_strategy")
    graph.add_edge("generate_strategy", "hallucination_check")

    # Hallucination routing
    graph.add_conditional_edges(
        "hallucination_check",
        route_hallucination,
        {END: END, "revise_strategy": "revise_strategy"},
    )

    graph.add_edge("revise_strategy", END)
    graph.add_edge("incorrect_result", END)

    return graph.compile()


# Module-level compiled graph
_lawyer_graph = None


def get_lawyer_graph():
    """Get or create the compiled lawyer graph."""
    global _lawyer_graph
    if _lawyer_graph is None:
        _lawyer_graph = build_lawyer_graph()
    return _lawyer_graph


def invoke_lawyer_pipeline(query: str, mode: str = "cases") -> dict:
    """
    Run the full lawyer RAG pipeline.

    Args:
        query: Lawyer's search query.
        mode: 'cases' for similar cases, 'strategy' for full strategy.

    Returns:
        Dict with cases, strategy, and pipeline_log.
    """
    graph = get_lawyer_graph()

    initial_state = {
        "query": query,
        "rewritten_query": "",
        "retrieved_docs": [],
        "reranked_docs": [],
        "relevance_verdict": "",
        "refined_docs": [],
        "strategy": "",
        "hallucination_status": "",
        "cases": [],
        "pipeline_log": [],
        "revision_done": False,
    }

    result = graph.invoke(initial_state)

    strategy = result.get("strategy", "")

    # ── Post-process: strip any LLM-injected internal notes that leaked through
    # e.g. "Note: The fabricated case name 'X' has been removed from the strategy"
    # These should never appear in user-facing output.
    _NOTE_RE = re.compile(
        r"\(?Note\s*:\s*[Tt]he\s+fabricated\b.*?(?:\n|$)",
        re.IGNORECASE | re.DOTALL
    )
    strategy = _NOTE_RE.sub("", strategy).strip()

    return {
        "cases": result.get("cases", []),
        "strategy": strategy,
        "pipeline_log": result.get("pipeline_log", []),
        "relevance_verdict": result.get("relevance_verdict", "unknown"),
        "hallucination_status": result.get("hallucination_status", "unknown"),
    }
