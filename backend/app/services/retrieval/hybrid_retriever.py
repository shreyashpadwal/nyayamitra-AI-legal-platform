"""
HybridRetriever — BM25 + FAISS vector search with Reciprocal Rank Fusion (RRF).

Combines lexical keyword matching (BM25) with semantic vector search (FAISS)
to improve retrieval quality across both exact-match legal terms and
semantically similar passages.
"""

import logging
import time
from typing import List, Tuple, Optional, Dict, Any

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid retrieval combining BM25 keyword search and FAISS semantic search.
    Merges results using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        faiss_vectorstore: Optional[FAISS] = None,
        documents: Optional[List[Document]] = None,
        rrf_k: int = 60,
    ):
        """
        Initialize HybridRetriever.

        Args:
            faiss_vectorstore: Pre-built FAISS vectorstore for semantic search.
            documents: Optional list of documents to build BM25 index from.
                       If not provided, will extract from FAISS docstore.
            rrf_k: Constant for RRF formula (default 60, standard value).
        """
        self.faiss_vs = faiss_vectorstore
        self.rrf_k = rrf_k
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_docs: List[Document] = []

        # Build BM25 index
        if documents:
            self._build_bm25(documents)
        elif faiss_vectorstore:
            self._build_bm25_from_faiss(faiss_vectorstore)

    def _build_bm25(self, documents: List[Document]) -> None:
        """Build BM25 index from a list of LangChain Documents."""
        try:
            self.bm25_docs = documents
            tokenized_corpus = [
                doc.page_content.lower().split() for doc in documents
            ]
            self.bm25_index = BM25Okapi(tokenized_corpus)
            logger.info(f"✅ BM25 index built with {len(documents)} documents")
        except Exception as e:
            logger.error(f"❌ Failed to build BM25 index: {e}")
            self.bm25_index = None

    def _build_bm25_from_faiss(self, faiss_vectorstore: FAISS) -> None:
        """
        Extract documents from an existing FAISS vectorstore's docstore
        and build a BM25 index. Avoids re-embedding.
        """
        try:
            docstore = faiss_vectorstore.docstore
            index_to_id = faiss_vectorstore.index_to_docstore_id

            documents = []
            for idx in sorted(index_to_id.keys()):
                doc_id = index_to_id[idx]
                doc = docstore.search(doc_id)
                if doc and hasattr(doc, "page_content"):
                    documents.append(doc)

            if documents:
                self._build_bm25(documents)
            else:
                logger.warning("⚠️ No documents extracted from FAISS docstore for BM25")
        except Exception as e:
            logger.error(f"❌ Failed to extract docs from FAISS for BM25: {e}")
            self.bm25_index = None

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize a list of scores to 0-1 range."""
        if not scores:
            return []
        min_s = min(scores)
        max_s = max(scores)
        if max_s == min_s:
            return [1.0] * len(scores)
        return [(s - min_s) / (max_s - min_s) for s in scores]

    def _bm25_search(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """
        Run BM25 keyword search.

        Returns list of (document, normalized_score) tuples.
        """
        if not self.bm25_index or not self.bm25_docs:
            return []

        tokenized_query = query.lower().split()
        raw_scores = self.bm25_index.get_scores(tokenized_query)

        # Get top-k indices by score
        scored_indices = sorted(
            enumerate(raw_scores), key=lambda x: x[1], reverse=True
        )[:k]

        if not scored_indices:
            return []

        docs_and_scores = []
        scores_only = [s for _, s in scored_indices]
        normalized = self._normalize_scores(scores_only)

        for (idx, _raw_score), norm_score in zip(scored_indices, normalized):
            if idx < len(self.bm25_docs):
                docs_and_scores.append((self.bm25_docs[idx], norm_score))

        return docs_and_scores

    def _faiss_search(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """
        Run FAISS semantic search.

        Returns list of (document, normalized_score) tuples.
        FAISS returns distances (lower = more similar), so we invert for scoring.
        """
        if not self.faiss_vs:
            return []

        try:
            results = self.faiss_vs.similarity_search_with_score(query, k=k)

            if not results:
                return []

            # FAISS returns L2 distances — lower is better
            # Convert to similarity scores: score = 1 / (1 + distance)
            docs_and_distances = [(doc, 1.0 / (1.0 + dist)) for doc, dist in results]
            scores = [s for _, s in docs_and_distances]
            normalized = self._normalize_scores(scores)

            return [
                (doc, norm_score)
                for (doc, _), norm_score in zip(docs_and_distances, normalized)
            ]
        except Exception as e:
            logger.error(f"❌ FAISS search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Tuple[Document, float]],
        faiss_results: List[Tuple[Document, float]],
        k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Merge BM25 and FAISS results using Reciprocal Rank Fusion.

        RRF score = sum over all lists of: 1 / (rank_in_list + rrf_k)
        """
        # Map document content to RRF score and document object
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        # Process BM25 results
        for rank, (doc, _score) in enumerate(bm25_results):
            doc_key = doc.page_content[:200]  # Use first 200 chars as dedup key
            rrf_score = 1.0 / (rank + 1 + self.rrf_k)
            doc_scores[doc_key] = doc_scores.get(doc_key, 0.0) + rrf_score
            doc_map[doc_key] = doc

        # Process FAISS results
        for rank, (doc, _score) in enumerate(faiss_results):
            doc_key = doc.page_content[:200]
            rrf_score = 1.0 / (rank + 1 + self.rrf_k)
            doc_scores[doc_key] = doc_scores.get(doc_key, 0.0) + rrf_score
            doc_map[doc_key] = doc

        # Sort by combined RRF score and return top k
        sorted_keys = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        return [
            (doc_map[key], doc_scores[key])
            for key in sorted_keys[:k]
        ]

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """
        Retrieve top-k documents using hybrid BM25 + FAISS search with RRF fusion.

        Args:
            query: Search query string.
            k: Number of documents to return.

        Returns:
            List of top-k documents sorted by combined RRF score.
        """
        results = self.retrieve_with_scores(query, k=k)
        return [doc for doc, _score in results]

    def retrieve_with_scores(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        Retrieve top-k documents with their combined RRF scores.

        Falls back to FAISS-only if BM25 fails.

        Args:
            query: Search query string.
            k: Number of documents to return.

        Returns:
            List of (document, combined_rrf_score) tuples sorted by score descending.
        """
        start_time = time.time()

        # Run BM25 search
        bm25_results = []
        try:
            bm25_results = self._bm25_search(query, k=12)
            logger.info(f"📖 BM25 returned {len(bm25_results)} results")
        except Exception as e:
            logger.warning(f"⚠️ BM25 search failed, falling back to FAISS-only: {e}")

        # Run FAISS search
        faiss_results = self._faiss_search(query, k=12)
        logger.info(f"🔍 FAISS returned {len(faiss_results)} results")

        # If BM25 failed, return FAISS-only results
        if not bm25_results:
            logger.info("📌 Using FAISS-only results (BM25 unavailable)")
            elapsed = time.time() - start_time
            logger.info(f"⏱️ Hybrid retrieval took {elapsed:.3f}s (FAISS-only fallback)")
            return faiss_results[:k]

        # Merge using RRF
        merged = self._reciprocal_rank_fusion(bm25_results, faiss_results, k=k)

        elapsed = time.time() - start_time
        logger.info(f"⏱️ Hybrid retrieval took {elapsed:.3f}s ({len(merged)} results)")

        return merged


def build_bm25_from_faiss(faiss_vectorstore: FAISS) -> Optional[BM25Okapi]:
    """
    Standalone helper: extract documents from a FAISS vectorstore
    and build a BM25 index. Returns the BM25 index or None on failure.
    """
    try:
        docstore = faiss_vectorstore.docstore
        index_to_id = faiss_vectorstore.index_to_docstore_id

        documents = []
        for idx in sorted(index_to_id.keys()):
            doc_id = index_to_id[idx]
            doc = docstore.search(doc_id)
            if doc and hasattr(doc, "page_content"):
                documents.append(doc)

        if not documents:
            logger.warning("⚠️ No documents found in FAISS docstore")
            return None

        tokenized = [doc.page_content.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized)
        logger.info(f"✅ Standalone BM25 index built with {len(documents)} documents")
        return bm25
    except Exception as e:
        logger.error(f"❌ build_bm25_from_faiss failed: {e}")
        return None
