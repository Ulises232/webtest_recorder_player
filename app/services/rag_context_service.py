"""Service responsible for indexing historical outputs and retrieving RAG context."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Dict, List, Tuple

from app.daos.card_ai_output_dao import CardAIOutputDAO, CardAIOutputDAOError
from app.dtos.card_ai_dto import CardAIContextDocumentDTO

logger = logging.getLogger(__name__)


class RAGContextServiceError(RuntimeError):
    """Raised when the semantic retrieval layer cannot complete its duties."""


class RAGContextService:
    """Provide lightweight semantic lookups using a TF-IDF similarity index."""

    MAX_FRAGMENT_LENGTH = 2000

    def __init__(self, output_dao: CardAIOutputDAO) -> None:
        """Store dependencies and initialize the in-memory index containers."""

        self._output_dao = output_dao
        self._documents: List[str] = []
        self._metadatas: List[Dict[str, object]] = []
        self._vectors: List[Dict[str, float]] = []
        self._idf: Dict[str, float] = {}
        self._token_pattern = re.compile(r"\b\w+\b", re.UNICODE)

    def index_from_database(self, limit: int = 500) -> int:
        """Load the latest outputs from SQL Server and build a TF-IDF index."""

        try:
            documents = self._output_dao.list_recent_outputs_for_context(limit=limit)
        except CardAIOutputDAOError as exc:
            raise RAGContextServiceError(str(exc)) from exc

        indexed = self._prepare_index(documents)
        logger.info("Indexados %s documentos para contexto RAG", indexed)
        return indexed

    def search_context(self, query: str, limit: int = 3) -> Tuple[str, List[str]]:
        """Return the concatenated context and titles matching the provided query."""

        if not query.strip() or not self._vectors:
            return "", []

        tokens = self._tokenize(query)
        if not tokens:
            return "", []

        query_vector = self._build_vector(Counter(tokens))
        if not query_vector:
            return "", []

        scored: List[Tuple[float, int]] = []
        for index, vector in enumerate(self._vectors):
            similarity = self._cosine_similarity(query_vector, vector)
            if similarity > 0:
                scored.append((similarity, index))

        if not scored:
            return "", []

        scored.sort(key=lambda item: item[0], reverse=True)
        top_matches = scored[: max(1, limit)]

        context_fragments: List[str] = []
        context_titles: List[str] = []
        for _score, idx in top_matches:
            fragment = self._documents[idx][: self.MAX_FRAGMENT_LENGTH]
            metadata = self._metadatas[idx]
            if not fragment.strip():
                continue
            context_fragments.append(fragment)
            title = str(
                metadata.get("document_title")
                or metadata.get("card_title")
                or metadata.get("titulo")
                or ""
            )
            context_titles.append(title)

        if not context_fragments:
            return "", []

        combined_context = "\n\n---\n\n".join(context_fragments)
        return combined_context, context_titles

    def _prepare_index(self, documents: List[CardAIContextDocumentDTO]) -> int:
        """Transform raw documents into normalized TF-IDF vectors."""

        texts: List[str] = []
        metadatas: List[Dict[str, object]] = []
        counters: List[Counter[str]] = []
        document_frequencies: Counter[str] = Counter()

        for document in documents:
            text = self._build_document_text(document)
            if not text:
                continue
            tokens = self._tokenize(text)
            if not tokens:
                continue
            counter = Counter(tokens)
            counters.append(counter)
            document_frequencies.update(counter.keys())
            texts.append(text)
            metadatas.append(
                {
                    "output_id": document.outputId,
                    "card_id": document.cardId,
                    "card_title": document.cardTitle,
                    "document_title": str(document.content.get("titulo", "")),
                }
            )

        if not texts:
            self._documents = []
            self._metadatas = []
            self._vectors = []
            self._idf = {}
            return 0

        total_documents = len(texts)
        self._idf = {
            token: math.log((1 + total_documents) / (1 + frequency)) + 1.0
            for token, frequency in document_frequencies.items()
        }

        self._documents = texts
        self._metadatas = metadatas
        self._vectors = [self._build_vector(counter) for counter in counters]
        return len(texts)

    def _build_document_text(self, document: CardAIContextDocumentDTO) -> str:
        """Compose a descriptive text for the document to feed the vector index."""

        content = document.content or {}
        sections = [
            f"Título de la tarjeta: {document.cardTitle}".strip(),
            str(content.get("titulo", "")).strip(),
            str(content.get("descripcion", "")).strip(),
            str(content.get("que_necesitas", "")).strip(),
            str(content.get("para_que_lo_necesitas", "")).strip(),
            str(
                content.get("como_lo_necesitas")
                or content.get("como_necesitas")
                or ""
            ).strip(),
            "\n".join(
                str(item).strip()
                for item in content.get("requerimientos_funcionales", [])
                if str(item).strip()
            ),
            "\n".join(
                str(item).strip()
                for item in content.get("criterios_aceptacion", [])
                if str(item).strip()
            ),
        ]
        cleaned = [segment for segment in sections if segment]
        return "\n".join(cleaned)

    def _tokenize(self, text: str) -> List[str]:
        """Split the provided text into normalized lowercase tokens."""

        return [match.group(0).lower() for match in self._token_pattern.finditer(text)]

    def _build_vector(self, counts: Counter[str]) -> Dict[str, float]:
        """Convert raw token counts into a normalized TF-IDF vector."""

        total_terms = sum(counts.values())
        if total_terms == 0:
            return {}

        vector: Dict[str, float] = {}
        norm = 0.0
        for token, occurrences in counts.items():
            idf = self._idf.get(token)
            if idf is None:
                continue
            tf = occurrences / total_terms
            value = tf * idf
            vector[token] = value
            norm += value * value

        if not vector or norm == 0:
            return {}

        norm = math.sqrt(norm)
        for token in list(vector.keys()):
            vector[token] /= norm
        return vector

    @staticmethod
    def _cosine_similarity(vector_a: Dict[str, float], vector_b: Dict[str, float]) -> float:
        """Return the cosine similarity between two sparse vectors."""

        if not vector_a or not vector_b:
            return 0.0

        if len(vector_a) > len(vector_b):
            vector_a, vector_b = vector_b, vector_a

        return sum(value * vector_b.get(token, 0.0) for token, value in vector_a.items())
