"""Service responsible for indexing historical outputs and retrieving RAG context."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.daos.card_ai_output_dao import CardAIOutputDAO, CardAIOutputDAOError
from app.dtos.card_ai_dto import CardAIContextDocumentDTO

logger = logging.getLogger(__name__)

try:  # pragma: no cover - dependency optional during some tests
    import chromadb
    from chromadb.api.collection import Collection
    from chromadb.utils import embedding_functions
except ModuleNotFoundError:  # pragma: no cover - handled gracefully at runtime
    chromadb = None
    Collection = Any  # type: ignore[assignment]
    embedding_functions = None


class RAGContextServiceError(RuntimeError):
    """Raised when the semantic retrieval layer cannot complete its duties."""


class RAGContextService:
    """Manage the ChromaDB index backed by SQL Server outputs."""

    DEFAULT_COLLECTION_NAME = "cards_ai_outputs_context"
    DEFAULT_STORAGE_PATH = Path("embeddings/index")

    def __init__(
        self,
        output_dao: CardAIOutputDAO,
        storage_path: Optional[Path] = None,
        collection_name: Optional[str] = None,
        embedding_function: Optional[Any] = None,
    ) -> None:
        """Store dependencies and bootstrap the ChromaDB collection."""

        if chromadb is None:  # pragma: no cover - depende de la instalación opcional
            raise RAGContextServiceError(
                "La dependencia 'chromadb' no está instalada. Instálala con 'pip install chromadb'."
            )

        self._output_dao = output_dao
        self._storage_path = (storage_path or self.DEFAULT_STORAGE_PATH).expanduser()
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._collection_name = collection_name or self.DEFAULT_COLLECTION_NAME
        embedding = embedding_function
        if embedding is None:
            if embedding_functions is None:  # pragma: no cover - depende de instalación
                raise RAGContextServiceError(
                    "No fue posible cargar la función de embeddings predeterminada de ChromaDB."
                )
            embedding = embedding_functions.DefaultEmbeddingFunction()

        self._client = chromadb.PersistentClient(path=str(self._storage_path))
        self._collection: Collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=embedding,
        )

    def index_from_database(self, limit: int = 500) -> int:
        """Load the latest outputs from SQL Server and upsert them into ChromaDB."""

        try:
            documents = self._output_dao.list_recent_outputs_for_context(limit=limit)
        except CardAIOutputDAOError as exc:
            raise RAGContextServiceError(str(exc)) from exc

        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[dict] = []

        for document in documents:
            text = self._build_document_text(document)
            if not text:
                continue
            ids.append(str(document.outputId))
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
            return 0

        self._collection.upsert(documents=texts, metadatas=metadatas, ids=ids)
        logger.info("Indexados %s documentos en ChromaDB", len(texts))
        return len(texts)

    def search_context(self, query: str, limit: int = 3) -> Tuple[str, List[str]]:
        """Return the concatenated context and the titles used for the given query."""

        if not query.strip():
            return "", []

        try:
            results = self._collection.query(query_texts=[query], n_results=limit)
        except Exception as exc:  # pragma: no cover - depende de la librería externa
            raise RAGContextServiceError("No fue posible consultar el índice semántico.") from exc

        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        if not documents or not documents[0]:
            return "", []

        context_fragments: List[str] = []
        context_titles: List[str] = []
        for raw_text, metadata in zip(documents[0], metadatas[0]):
            if not raw_text:
                continue
            fragment = str(raw_text)[:2000]
            if fragment.strip():
                context_fragments.append(fragment)
            title = ""
            if isinstance(metadata, dict):
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
            "\n".join(str(item).strip() for item in content.get("requerimientos_funcionales", []) if str(item).strip()),
            "\n".join(str(item).strip() for item in content.get("criterios_aceptacion", []) if str(item).strip()),
        ]
        cleaned = [segment for segment in sections if segment]
        return "\n".join(cleaned)
