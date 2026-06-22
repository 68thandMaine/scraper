"""Ollama-backed content agent with ChromaDB vector memory."""

from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, cast

import httpx

from .prompts import (
    CLEAN_SYSTEM_PROMPT,
    CLEAN_USER_PROMPT,
    CONSOLIDATE_SYSTEM_PROMPT,
    CONSOLIDATE_USER_PROMPT,
    DECIDE_SYSTEM_PROMPT,
    DECIDE_USER_PROMPT,
    SIMILAR_SECTION_TEMPLATE,
)
from .constants import (
    DEFAULT_CHROMA_MAX_RETRIES,
    DEFAULT_CHROMA_RETRY_BACKOFF,
    DEFAULT_CHROMA_TIMEOUT,
    DEFAULT_MAX_EMBED_INPUT_CHARS,
    DEFAULT_MAX_LLM_INPUT_CHARS,
    DEFAULT_OLLAMA_CONNECT_TIMEOUT,
    DEFAULT_OLLAMA_EMBED_MODEL,
    DEFAULT_OLLAMA_MAX_RETRIES,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_NUM_PREDICT,
    DEFAULT_OLLAMA_RETRY_BACKOFF,
    DEFAULT_OLLAMA_TIMEOUT,
)
from .logging_config import log_step
from .utils import clean_filename, create_output_directory

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _truncate_for_llm(text: str, label: str) -> str:
    """Cap text sent to Ollama so CPU inference finishes in reasonable time."""
    max_chars = int(os.getenv("MAX_LLM_INPUT_CHARS", str(DEFAULT_MAX_LLM_INPUT_CHARS)))
    if len(text) <= max_chars:
        return text
    logger.warning(
        "Truncating %s from %d to %d chars for LLM",
        label,
        len(text),
        max_chars,
    )
    return text[:max_chars] + "\n\n[... content truncated for processing ...]"


class AgentDecision(str, Enum):
    """Actions the agent can take for a scraped page."""

    SAVE = "SAVE"
    CONSOLIDATE = "CONSOLIDATE"
    SKIP = "SKIP"


@dataclass
class AgentStats:
    """Counters for agent processing outcomes."""

    saved: int = 0
    consolidated: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class ProcessResult:
    """Outcome of processing a single scraped document."""

    decision: AgentDecision
    doc_id: Optional[str] = None
    file_path: Optional[Path] = None
    reason: str = ""


@dataclass
class SimilarDocument:
    """A document retrieved from vector memory."""

    doc_id: str
    url: str
    title: str
    content: str
    distance: float


class OllamaClient:
    """Thin HTTP client for Ollama generate and embed APIs."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        embed_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.embed_model = embed_model or os.getenv(
            "OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_EMBED_MODEL
        )
        if timeout is None:
            timeout = float(os.getenv("OLLAMA_TIMEOUT", str(DEFAULT_OLLAMA_TIMEOUT)))
        self.timeout = timeout
        self.max_embed_input_chars = int(
            os.getenv("MAX_EMBED_INPUT_CHARS", str(DEFAULT_MAX_EMBED_INPUT_CHARS))
        )
        self.max_retries = int(
            os.getenv("OLLAMA_MAX_RETRIES", str(DEFAULT_OLLAMA_MAX_RETRIES))
        )
        self.retry_backoff = float(
            os.getenv("OLLAMA_RETRY_BACKOFF", str(DEFAULT_OLLAMA_RETRY_BACKOFF))
        )
        self._client = httpx.Client(
            base_url=self.host,
            timeout=httpx.Timeout(
                connect=DEFAULT_OLLAMA_CONNECT_TIMEOUT,
                read=self.timeout,
                write=30.0,
                pool=DEFAULT_OLLAMA_CONNECT_TIMEOUT,
            ),
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        )

    def list_models(self) -> List[str]:
        """Return model names reported by Ollama."""
        response = self._client.get("/api/tags")
        response.raise_for_status()
        return [entry["name"] for entry in response.json().get("models", [])]

    @staticmethod
    def _model_matches(requested: str, available: List[str]) -> bool:
        """True if requested model is present (exact or tagged variant)."""
        for name in available:
            if name == requested or name.startswith(f"{requested}:"):
                return True
        return False

    def ensure_models(self) -> None:
        """
        Verify generation and embedding models exist before scraping.

        Raises:
            ConnectionError: Ollama is not reachable.
            ValueError: One or more models are not pulled.
        """
        try:
            available = self.list_models()
        except httpx.HTTPError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.host}. "
                "Start Ollama or set OLLAMA_HOST correctly."
            ) from exc

        logger.info(
            "Ollama at %s has %d model(s): %s",
            self.host,
            len(available),
            ", ".join(available) if available else "(none)",
        )

        missing: List[str] = []
        if not self._model_matches(self.model, available):
            missing.append(self.model)
        if not self._model_matches(self.embed_model, available):
            missing.append(self.embed_model)

        if missing:
            pull_lines = "\n".join(f"  ollama pull {name}" for name in missing)
            raise ValueError(
                f"Ollama at {self.host} is missing model(s): {', '.join(missing)}\n"
                f"Pull them on the host serving {self.host}:\n{pull_lines}"
            )

    def _post_with_retry(
        self, path: str, payload: dict, operation: str
    ) -> httpx.Response:
        last_exc: Exception = RuntimeError("unreachable")
        total = self.max_retries + 1
        for attempt in range(1, total + 1):
            try:
                return self._client.post(path, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < total:
                    delay = self.retry_backoff * attempt
                    logger.warning(
                        "Ollama %s POST failed (attempt %d/%d): %r; retrying in %.1fs",
                        operation,
                        attempt,
                        total,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
        raise last_exc

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        detail = response.text
        try:
            detail = response.json().get("error", detail)
        except Exception:
            pass
        if response.status_code == 404:
            raise ValueError(
                f"Ollama {operation} failed: model '{self.model}' not found at "
                f"{self.host}. Run: ollama pull {self.model}\n"
                f"Detail: {detail}"
            ) from None
        response.raise_for_status()

    def generate(self, system: str, prompt: str) -> str:
        """Run a chat-style generation and return assistant text."""
        logger.info(
            "Ollama generate: model=%s prompt_chars=%d host=%s",
            self.model,
            len(prompt),
            self.host,
        )
        started = time.perf_counter()
        num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", str(DEFAULT_OLLAMA_NUM_PREDICT)))
        response = self._post_with_retry(
            "/api/generate",
            {
                "model": self.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": num_predict},
            },
            "generate",
        )
        self._raise_for_status(response, "generate")
        data = response.json()
        logger.info(
            "Ollama generate finished in %.1fs (response_chars=%d)",
            time.perf_counter() - started,
            len(data.get("response") or ""),
        )
        return (data.get("response") or "").strip()

    def _chunk_for_embed(self, text: str) -> List[str]:
        """Split text into chunks no longer than max_embed_input_chars."""
        if len(text) <= self.max_embed_input_chars:
            stripped = text.strip()
            return [stripped] if stripped else [text]

        chunks: List[str] = []
        remaining = text
        limit = self.max_embed_input_chars

        while remaining:
            if len(remaining) <= limit:
                chunk = remaining.strip()
                if chunk:
                    chunks.append(chunk)
                break

            slice_candidate = remaining[:limit]
            split_pos = slice_candidate.rfind("\n\n")
            if split_pos == -1:
                split_pos = slice_candidate.rfind("\n")
            if split_pos == -1:
                split_pos = slice_candidate.rfind(" ")
            if split_pos <= 0:
                split_pos = limit

            chunk = remaining[:split_pos].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[split_pos:].lstrip()

        return chunks if chunks else [text.strip() or text]

    def _mean_pool_and_normalize(self, vectors: List[List[float]]) -> List[float]:
        """Element-wise mean of vectors, then L2-normalize."""
        dim = len(vectors[0])
        pooled = [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in pooled))
        if norm == 0.0:
            return pooled
        return [x / norm for x in pooled]

    def embed(self, text: str) -> List[float]:
        """Generate an embedding vector for the given text."""
        logger.info(
            "Ollama embed: model=%s input_chars=%d host=%s",
            self.embed_model,
            len(text),
            self.host,
        )
        started = time.perf_counter()
        chunks = self._chunk_for_embed(text)

        if len(chunks) > 1:
            logger.info(
                "Embedding in %d chunks (total_chars=%d)", len(chunks), len(text)
            )
            input_payload: Any = chunks
        else:
            input_payload = chunks[0]

        response = self._post_with_retry(
            "/api/embed",
            {
                "model": self.embed_model,
                "input": input_payload,
            },
            "embed",
        )
        if not response.is_success:
            detail = response.text
            try:
                detail = response.json().get("error", detail)
            except Exception:
                pass
            if response.status_code == 404:
                raise ValueError(
                    f"Ollama embed failed: model '{self.embed_model}' not found at "
                    f"{self.host}. Run: ollama pull {self.embed_model}\n"
                    f"Detail: {detail}"
                ) from None
            response.raise_for_status()
        data = response.json()
        logger.info("Ollama embed finished in %.1fs", time.perf_counter() - started)

        if len(chunks) == 1:
            embeddings = data.get("embeddings") or []
            if embeddings:
                return list(embeddings[0])
            embedding = data.get("embedding")
            if embedding:
                return list(embedding)
            raise ValueError("Ollama embed response contained no embedding vector")

        embeddings = data.get("embeddings") or []
        if not embeddings:
            raise ValueError("Ollama embed batch response contained no embeddings")
        dim = len(embeddings[0])
        if any(len(v) != dim for v in embeddings):
            raise ValueError("Ollama embed batch returned vectors of inconsistent dimension")
        return self._mean_pool_and_normalize([list(v) for v in embeddings])

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class DocumentMemory:
    """ChromaDB-backed vector store for scraped document memory."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: str = "scraped_documents",
    ) -> None:
        self._host = host or os.getenv("CHROMA_HOST", "localhost")
        self._port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None
        self._timeout = float(os.getenv("CHROMA_TIMEOUT", str(DEFAULT_CHROMA_TIMEOUT)))
        self._max_retries = int(
            os.getenv("CHROMA_MAX_RETRIES", str(DEFAULT_CHROMA_MAX_RETRIES))
        )
        self._retry_backoff = float(
            os.getenv("CHROMA_RETRY_BACKOFF", str(DEFAULT_CHROMA_RETRY_BACKOFF))
        )

    def _ensure_connected(self) -> None:
        if self._collection is not None:
            return
        import chromadb
        from chromadb.config import Settings

        logger.info(
            "Connecting to ChromaDB at %s:%s collection=%s",
            self._host,
            self._port,
            self._collection_name,
        )
        started = time.perf_counter()
        self._client = chromadb.HttpClient(
            host=self._host,
            port=self._port,
            settings=Settings(
                chroma_http_max_keepalive_connections=0,
                chroma_http_max_connections=10,
            ),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB connected in %.1fs (documents=%d)",
            time.perf_counter() - started,
            self._collection.count(),
        )

    def _reset_connection(self) -> None:
        self._client = None
        self._collection = None

    def _run_with_timeout(self, label: str, fn: Callable[[], _T]) -> _T:
        total = self._max_retries + 1
        last_error: Exception = RuntimeError("unreachable")

        for attempt in range(1, total + 1):
            _result: Dict[str, Any] = {}

            def _target(r: Dict[str, Any] = _result) -> None:
                try:
                    r["value"] = fn()
                except Exception as exc:
                    r["error"] = exc

            thread = threading.Thread(target=_target, daemon=True)
            thread.start()
            thread.join(self._timeout)

            if thread.is_alive():
                last_error = TimeoutError(
                    f"ChromaDB {label} timed out after {self._timeout}s"
                )
                self._reset_connection()
            elif "error" in _result:
                exc = _result["error"]
                if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
                    last_error = exc
                    self._reset_connection()
                else:
                    raise exc
            else:
                return cast(_T, _result["value"])

            if attempt < total:
                delay = self._retry_backoff * attempt
                logger.warning(
                    "ChromaDB %s failed (attempt %d/%d): %r; retrying in %.1fs",
                    label,
                    attempt,
                    total,
                    last_error,
                    delay,
                )
                time.sleep(delay)

        raise last_error

    def query_similar(
        self,
        embedding: List[float],
        top_k: int = 5,
    ) -> List[SimilarDocument]:
        """Find similar documents by embedding."""

        def _op() -> List[SimilarDocument]:
            self._ensure_connected()
            if self._collection.count() == 0:
                return []
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, self._collection.count()),
                include=["documents", "metadatas", "distances"],
            )
            similar: List[SimilarDocument] = []
            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            for doc_id, content, metadata, distance in zip(
                ids, documents, metadatas, distances
            ):
                meta = metadata or {}
                similar.append(
                    SimilarDocument(
                        doc_id=doc_id,
                        url=str(meta.get("url", "")),
                        title=str(meta.get("title", "")),
                        content=content or "",
                        distance=float(distance),
                    )
                )
            return similar

        return self._run_with_timeout("query", _op)

    def upsert(
        self,
        doc_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        """Add or update a document in the collection."""

        def _op() -> None:
            self._ensure_connected()
            self._collection.upsert(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[metadata],
            )

        self._run_with_timeout("upsert", _op)

    def delete(self, doc_id: str) -> None:
        """Remove a document from the collection."""

        def _op() -> None:
            self._ensure_connected()
            self._collection.delete(ids=[doc_id])

        self._run_with_timeout("delete", _op)

    def get(self, doc_id: str) -> Optional[SimilarDocument]:
        """Fetch a document by id."""

        def _op() -> Optional[SimilarDocument]:
            self._ensure_connected()
            results = self._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
            ids = results.get("ids") or []
            if not ids:
                return None
            documents = results.get("documents") or [""]
            metadatas = results.get("metadatas") or [{}]
            meta = metadatas[0] or {}
            return SimilarDocument(
                doc_id=ids[0],
                url=str(meta.get("url", "")),
                title=str(meta.get("title", "")),
                content=documents[0] or "",
                distance=0.0,
            )

        return self._run_with_timeout("get", _op)


class ContentAgent:
    """Processes scraped pages through clean, recall, decide, and store."""

    DECISION_PATTERN = re.compile(
        r"DECISION:\s*(SAVE|CONSOLIDATE|SKIP)\s*\n"
        r"(?:TARGET_ID:\s*(.+?)\s*\n)?"
        r"REASON:\s*(.+)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(
        self,
        output_dir: str,
        ollama: Optional[OllamaClient] = None,
        memory: Optional[DocumentMemory] = None,
        similarity_threshold: Optional[float] = None,
        top_k: int = 5,
    ) -> None:
        self.output_dir = Path(output_dir)
        create_output_directory(self.output_dir)
        self.ollama = ollama or OllamaClient()
        self._memory = memory
        self.similarity_threshold = similarity_threshold or float(
            os.getenv("SIMILARITY_THRESHOLD", "0.85")
        )
        self.top_k = top_k
        self.stats = AgentStats()
        self._file_index = self._next_file_index()

    @property
    def memory(self) -> DocumentMemory:
        """Lazy ChromaDB connection on first use."""
        if self._memory is None:
            self._memory = DocumentMemory()
        return self._memory

    def _next_file_index(self) -> int:
        """Determine the next numeric index from existing output files."""
        indices = []
        for path in self.output_dir.glob("*.txt"):
            if path.stem[:3].isdigit():
                indices.append(int(path.stem[:3]))
        return max(indices, default=-1) + 1

    def _make_doc_id(self, title: str) -> str:
        """Create a stable document id and filename stem."""
        stem = f"{self._file_index:03d}_{clean_filename(title)}"
        self._file_index += 1
        return stem

    def process_document(self, scraped_data: Dict[str, str]) -> ProcessResult:
        """
        Run the full agent pipeline for one scraped page.

        Args:
            scraped_data: Dict with url, title, content keys.

        Returns:
            ProcessResult describing the action taken.
        """
        url = scraped_data["url"]
        title = scraped_data["title"]
        raw_content = scraped_data["content"]

        logger.info(
            "Agent processing: url=%s title=%r raw_chars=%d",
            url,
            title,
            len(raw_content),
        )

        try:
            with log_step("CLEAN", logger=logger, url=url):
                cleaned = self._clean_content(url, title, raw_content)
            if not cleaned.strip():
                self.stats.skipped += 1
                logger.info("SKIP %s: no body content after cleaning", url)
                return ProcessResult(
                    decision=AgentDecision.SKIP,
                    reason="No body content after cleaning",
                )
            logger.info("Cleaned content: %d chars for %s", len(cleaned), url)

            with log_step("EMBED", logger=logger, url=url):
                embedding = self.ollama.embed(cleaned)

            with log_step("RECALL", logger=logger, url=url):
                similar = self.memory.query_similar(embedding, top_k=self.top_k)
                relevant = [
                    doc
                    for doc in similar
                    if (1.0 - doc.distance) >= self.similarity_threshold
                ]
                logger.info(
                    "Recall: %d similar, %d above threshold %.2f",
                    len(similar),
                    len(relevant),
                    self.similarity_threshold,
                )

            with log_step("DECIDE", logger=logger, url=url):
                decision, target_id, reason = self._decide(
                    url, title, cleaned, relevant
                )
            logger.info(
                "Decision for %s: %s target_id=%s reason=%s",
                url,
                decision.value,
                target_id,
                reason,
            )

            if decision == AgentDecision.SKIP:
                self.stats.skipped += 1
                logger.info("SKIP %s: %s", url, reason)
                return ProcessResult(
                    decision=AgentDecision.SKIP, reason=reason
                )

            if decision == AgentDecision.CONSOLIDATE and target_id:
                with log_step("CONSOLIDATE", logger=logger, url=url):
                    return self._consolidate(
                        target_id=target_id,
                        url=url,
                        title=title,
                        new_content=cleaned,
                        embedding=embedding,
                        reason=reason,
                    )

            with log_step("SAVE", logger=logger, url=url):
                return self._save_new(
                    url=url,
                    title=title,
                    content=cleaned,
                    embedding=embedding,
                    reason=reason,
                )

        except Exception as exc:
            self.stats.errors += 1
            logger.exception("Agent failed for %s: %s", url, exc)
            return ProcessResult(
                decision=AgentDecision.SKIP,
                reason=f"Agent error: {exc}",
            )

    def _clean_content(self, url: str, title: str, content: str) -> str:
        content = _truncate_for_llm(content, "raw scrape body")
        prompt = CLEAN_USER_PROMPT.format(url=url, title=title, content=content)
        return self.ollama.generate(CLEAN_SYSTEM_PROMPT, prompt)

    def _decide(
        self,
        url: str,
        title: str,
        content: str,
        similar: List[SimilarDocument],
    ) -> Tuple[AgentDecision, Optional[str], str]:
        if similar:
            blocks = []
            for doc in similar:
                blocks.append(
                    f"ID: {doc.doc_id}\n"
                    f"URL: {doc.url}\n"
                    f"Title: {doc.title}\n"
                    f"Similarity: {1.0 - doc.distance:.2f}\n"
                    f"Content preview:\n{doc.content[:1500]}\n"
                )
            similar_section = SIMILAR_SECTION_TEMPLATE.format(
                similar_docs="\n---\n".join(blocks)
            )
        else:
            similar_section = "No similar documents in memory yet."

        prompt = DECIDE_USER_PROMPT.format(
            url=url,
            title=title,
            content=content[:8000],
            similar_section=similar_section,
        )
        response = self.ollama.generate(DECIDE_SYSTEM_PROMPT, prompt)
        return self._parse_decision(response)

    def _parse_decision(
        self, response: str
    ) -> Tuple[AgentDecision, Optional[str], str]:
        match = self.DECISION_PATTERN.search(response)
        if not match:
            logger.warning("Could not parse decision, defaulting to SAVE: %s", response)
            return AgentDecision.SAVE, None, "Unparseable decision; saved by default"

        decision_str = match.group(1).upper()
        target_id = (match.group(2) or "").strip() or None
        reason = (match.group(3) or "").strip()
        try:
            decision = AgentDecision(decision_str)
        except ValueError:
            decision = AgentDecision.SAVE
        return decision, target_id, reason

    def _save_new(
        self,
        url: str,
        title: str,
        content: str,
        embedding: List[float],
        reason: str,
    ) -> ProcessResult:
        doc_id = self._make_doc_id(title)
        file_path = self._write_file(doc_id, url, title, content)
        self.memory.upsert(
            doc_id=doc_id,
            content=content,
            embedding=embedding,
            metadata=self._metadata(url, title, doc_id, content),
        )
        self.stats.saved += 1
        logger.info("SAVE %s -> %s: %s", url, file_path.name, reason)
        return ProcessResult(
            decision=AgentDecision.SAVE,
            doc_id=doc_id,
            file_path=file_path,
            reason=reason,
        )

    def _consolidate(
        self,
        target_id: str,
        url: str,
        title: str,
        new_content: str,
        embedding: List[float],
        reason: str,
    ) -> ProcessResult:
        existing = self.memory.get(target_id)
        existing_content = existing.content if existing else ""
        if not existing_content:
            existing_path = self.output_dir / f"{target_id}.txt"
            if existing_path.exists():
                existing_content = self._read_body(existing_path)

        prompt = CONSOLIDATE_USER_PROMPT.format(
            target_id=target_id,
            existing_content=existing_content,
            url=url,
            title=title,
            new_content=new_content,
        )
        merged = self.ollama.generate(CONSOLIDATE_SYSTEM_PROMPT, prompt)
        file_path = self._write_file(
            target_id,
            url if existing is None else existing.url,
            title if existing is None else existing.title,
            merged,
        )
        self.memory.upsert(
            doc_id=target_id,
            content=merged,
            embedding=embedding,
            metadata=self._metadata(
                url if existing is None else existing.url,
                title if existing is None else existing.title,
                target_id,
                merged,
            ),
        )
        self.stats.consolidated += 1
        logger.info("CONSOLIDATE %s -> %s: %s", url, target_id, reason)
        return ProcessResult(
            decision=AgentDecision.CONSOLIDATE,
            doc_id=target_id,
            file_path=file_path,
            reason=reason,
        )

    def _metadata(
        self, url: str, title: str, doc_id: str, content: str
    ) -> Dict[str, Any]:
        return {
            "url": url,
            "title": title,
            "doc_id": doc_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "word_count": len(content.split()),
        }

    def _write_file(
        self, doc_id: str, url: str, title: str, content: str
    ) -> Path:
        file_path = self.output_dir / f"{doc_id}.txt"
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(f"URL: {url}\n")
            handle.write(f"Title: {title}\n")
            handle.write("-" * 50 + "\n\n")
            handle.write(content)
        return file_path

    def _read_body(self, file_path: Path) -> str:
        text = file_path.read_text(encoding="utf-8")
        parts = text.split("-" * 50 + "\n\n", 1)
        return parts[1] if len(parts) > 1 else text
