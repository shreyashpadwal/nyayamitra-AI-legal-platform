"""
CrossEncoderReranker — Reranks retrieved documents using a cross-encoder model.

Uses `cross-encoder/ms-marco-MiniLM-L6-v2` for high-quality relevance scoring
of (query, document) pairs. The model is lazy-loaded on first use.

Root-cause note (2025-07-25): CrossEncoder() without an explicit device= argument
can trigger accelerate's meta-device path when accelerate is installed, loading
model weights onto a virtual placeholder device. Any call to .predict() on a
meta-device model raises "Cannot copy out of meta tensor; no data!".
Fix: always pass device="cpu" to CrossEncoder so weights are materialized
immediately onto real CPU memory, bypassing the meta-device init path entirely.
"""

import logging
import time
from typing import List, Tuple

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Reranks documents using a cross-encoder model. Model loaded lazily."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """
        Lazy-load the cross-encoder model on first use.

        Passes device="cpu" explicitly to sentence_transformers.CrossEncoder so
        that model weights are materialized onto real CPU memory immediately.
        Without this, accelerate (when installed) may load weights onto a meta
        device — a virtual placeholder with no real memory — causing every
        subsequent .predict() call to raise:
            "Cannot copy out of meta tensor; no data!"
        """
        if self._model is None:
            logger.info(f"Loading cross-encoder model: {self.model_name} (device=cpu)...")
            load_start = time.time()
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, device="cpu")
            # Post-load smoke test: catch meta-device or other init failures
            # at load time rather than silently during real inference.
            try:
                _ = self._model.predict([("test", "test")])
                logger.info(
                    f"Cross-encoder loaded and verified in {time.time() - load_start:.2f}s"
                )
            except Exception as smoke_err:
                logger.error(f"Cross-encoder smoke test failed after load: {smoke_err}")
                self._model = None
                raise

    def rerank(
        self, query: str, documents: List[Document], top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Rerank documents by cross-encoder relevance score."""
        if not documents:
            return []

        self._load_model()
        start_time = time.time()

        pairs = [(query, doc.page_content) for doc in documents]
        try:
            scores = self._model.predict(pairs)
            scored_docs = sorted(
                zip(documents, [float(s) for s in scores]),
                key=lambda x: x[1],
                reverse=True,
            )
            results = scored_docs[:top_k]
            elapsed = time.time() - start_time
            logger.info(
                f"Reranking {len(documents)} docs took {elapsed:.3f}s | "
                f"Top: {results[0][1]:.4f} | Bottom: {results[-1][1]:.4f}"
            )
            return results
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Return docs in original order with 0.0 score so caller still gets
            # something useful rather than triggering an empty-result fallback.
            return [(doc, 0.0) for doc in documents[:top_k]]

    def rerank_with_threshold(
        self, query: str, documents: List[Document],
        threshold: float = 0.3, top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """Rerank and filter documents below score threshold."""
        if not documents:
            return []

        all_reranked = self.rerank(query, documents, top_k=len(documents))
        filtered = [(doc, score) for doc, score in all_reranked if score >= threshold]

        if not filtered:
            best = all_reranked[0][1] if all_reranked else 0.0
            logger.warning(f"No docs passed threshold {threshold}. Best: {best:.4f}")
            return []

        results = filtered[:top_k]
        logger.info(f"Threshold filter: {len(filtered)}/{len(documents)} passed (>={threshold})")
        return results
