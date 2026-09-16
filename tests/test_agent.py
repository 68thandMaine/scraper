"""Tests for the Ollama content agent."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from web_scraper.agent import (
    AgentDecision,
    ContentAgent,
    DocumentMemory,
    OllamaClient,
)
from web_scraper.logging_config import Spinner, configure_logging


class TestConfigureLogging:
    def _reset_root(self) -> None:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.NOTSET)

    def test_verbose_false_sets_warning(self) -> None:
        self._reset_root()
        configure_logging(verbose=False)
        assert logging.getLogger().level == logging.WARNING
        self._reset_root()

    def test_verbose_true_sets_debug(self) -> None:
        self._reset_root()
        configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG
        self._reset_root()


class TestSpinner:
    def test_start_no_op_when_not_tty(self) -> None:
        mock_pbar = MagicMock()
        spinner = Spinner(mock_pbar, interval=0.05)

        with patch.object(sys.stderr, "isatty", return_value=False):
            spinner.start()
            spinner.stop()

        assert spinner._thread is None
        mock_pbar.set_description_str.assert_not_called()


class TestOllamaClient:
    """Tests for OllamaClient HTTP wrapper."""

    def test_model_matches(self) -> None:
        available = ["qwen2.5:3b", "nomic-embed-text:latest", "phi3:mini"]
        assert OllamaClient._model_matches("qwen2.5:3b", available)
        assert OllamaClient._model_matches("nomic-embed-text", available)
        assert not OllamaClient._model_matches("llama3.2:3b", available)

    @patch("web_scraper.agent.httpx.Client")
    def test_ensure_models_missing(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "phi3"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        client = OllamaClient(
            host="http://localhost:11434",
            model="qwen2.5:3b",
            embed_model="nomic-embed-text",
        )
        with pytest.raises(ValueError, match="missing model"):
            client.ensure_models()

    @patch("web_scraper.agent.httpx.Client")
    def test_generate(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "cleaned body"}}]
        }
        mock_client.post.return_value = mock_response

        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        result = client.generate("system", "prompt")

        assert result == "cleaned body"
        mock_client.post.assert_called_once()

    @patch("web_scraper.agent.httpx.Client")
    def test_embed_single_chunk(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }
        mock_client.post.return_value = mock_response

        client = OllamaClient(host="http://localhost:11434")
        result = client.embed("sample text")

        assert result == [0.1, 0.2, 0.3]
        call_kwargs = mock_client.post.call_args
        sent_input = call_kwargs[1]["json"]["input"]
        assert isinstance(sent_input, str)

    @patch("web_scraper.agent.time.sleep")
    @patch("web_scraper.agent.httpx.Client")
    def test_generate_retries_on_timeout_then_succeeds(
        self, mock_client_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "result text"}}]
        }
        mock_client.post.side_effect = [
            httpx.ReadTimeout("timed out"),
            mock_response,
        ]

        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        client.max_retries = 1
        client.retry_backoff = 0.0

        result = client.generate("sys", "prompt")

        assert result == "result text"
        assert mock_client.post.call_count == 2
        mock_sleep.assert_called_once_with(0.0)

    @patch("web_scraper.agent.time.sleep")
    @patch("web_scraper.agent.httpx.Client")
    def test_generate_exhausts_retries_raises(
        self, mock_client_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.post.side_effect = httpx.ReadTimeout("timed out")

        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        client.max_retries = 2
        client.retry_backoff = 0.0

        with pytest.raises(httpx.ReadTimeout):
            client.generate("sys", "prompt")

        assert mock_client.post.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("web_scraper.agent.httpx.Client")
    def test_embed_multi_chunk_mean_pooled(self, mock_client_cls: MagicMock) -> None:
        import math

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": [
                {"embedding": [1.0, 0.0, 0.0]},
                {"embedding": [0.0, 1.0, 0.0]},
            ]
        }
        mock_client.post.return_value = mock_response

        client = OllamaClient(host="http://localhost:11434")
        client.max_embed_input_chars = 10

        long_text = "hello world " * 5
        result = client.embed(long_text)

        call_kwargs = mock_client.post.call_args
        sent_input = call_kwargs[1]["json"]["input"]
        assert isinstance(sent_input, list)

        expected = 1.0 / math.sqrt(2)
        assert result == pytest.approx([expected, expected, 0.0], abs=1e-6)


class TestContentAgent:
    """Tests for ContentAgent pipeline with mocked dependencies."""

    def setup_method(self) -> None:
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=DocumentMemory)

    def test_process_document_save(self, tmp_path: Path) -> None:
        self.mock_ollama.generate.side_effect = [
            "Cleaned article body",
            "DECISION: SAVE\nREASON: Unique content",
        ]
        self.mock_ollama.embed.return_value = [0.1, 0.2, 0.3]
        self.mock_memory.query_similar.return_value = []

        agent = ContentAgent(
            output_dir=str(tmp_path),
            ollama=self.mock_ollama,
            memory=self.mock_memory,
        )

        result = agent.process_document(
            {
                "url": "https://example.com/page",
                "title": "Test Page",
                "content": "Raw nav and body content",
            }
        )

        assert result.decision == AgentDecision.SAVE
        assert result.file_path is not None
        assert result.file_path.exists()
        assert agent.stats.saved == 1
        self.mock_memory.upsert.assert_called_once()

    def test_process_document_skip(self, tmp_path: Path) -> None:
        self.mock_ollama.generate.side_effect = [
            "Cleaned body",
            "DECISION: SKIP\nREASON: Duplicate",
        ]
        self.mock_ollama.embed.return_value = [0.1, 0.2, 0.3]
        self.mock_memory.query_similar.return_value = []

        agent = ContentAgent(
            output_dir=str(tmp_path),
            ollama=self.mock_ollama,
            memory=self.mock_memory,
        )

        result = agent.process_document(
            {
                "url": "https://example.com/dup",
                "title": "Duplicate",
                "content": "Same content",
            }
        )

        assert result.decision == AgentDecision.SKIP
        assert agent.stats.skipped == 1
        self.mock_memory.upsert.assert_not_called()

    def test_process_document_consolidate(self, tmp_path: Path) -> None:
        from web_scraper.agent import SimilarDocument

        existing = SimilarDocument(
            doc_id="000_Existing",
            url="https://example.com/existing",
            title="Existing",
            content="Existing body",
            distance=0.05,
        )
        self.mock_ollama.generate.side_effect = [
            "New cleaned body",
            "DECISION: CONSOLIDATE\nTARGET_ID: 000_Existing\nREASON: Overlap",
            "Merged body text",
        ]
        self.mock_ollama.embed.return_value = [0.1, 0.2, 0.3]
        self.mock_memory.query_similar.return_value = [existing]
        self.mock_memory.get.return_value = existing

        agent = ContentAgent(
            output_dir=str(tmp_path),
            ollama=self.mock_ollama,
            memory=self.mock_memory,
            similarity_threshold=0.85,
        )

        result = agent.process_document(
            {
                "url": "https://example.com/new",
                "title": "New Page",
                "content": "Raw content",
            }
        )

        assert result.decision == AgentDecision.CONSOLIDATE
        assert result.doc_id == "000_Existing"
        assert agent.stats.consolidated == 1
        self.mock_memory.upsert.assert_called_once()

    def test_parse_decision_defaults_to_save(self, tmp_path: Path) -> None:
        agent = ContentAgent(
            output_dir=str(tmp_path),
            ollama=self.mock_ollama,
            memory=self.mock_memory,
        )
        decision, target_id, reason = agent._parse_decision("garbled response")
        assert decision == AgentDecision.SAVE
        assert target_id is None


class TestDocumentMemory:
    """Tests for DocumentMemory ChromaDB timeout and retry behavior."""

    def _make_memory(self) -> "tuple[DocumentMemory, MagicMock]":
        mem = DocumentMemory()
        mem._retry_backoff = 0.0
        mock_collection = MagicMock()

        def _mock_connect() -> None:
            mem._collection = mock_collection

        mem._ensure_connected = _mock_connect  # type: ignore[method-assign]
        mem._collection = mock_collection
        return mem, mock_collection

    def test_query_retries_on_transient_error(self) -> None:
        mem, mock_col = self._make_memory()
        valid_result = {
            "ids": [["doc1"]],
            "documents": [["body text"]],
            "metadatas": [[{"url": "http://x.com", "title": "X"}]],
            "distances": [[0.1]],
        }
        mock_col.count.return_value = 1
        mock_col.query.side_effect = [
            httpx.ConnectError("boom"),
            valid_result,
        ]

        result = mem.query_similar([0.1, 0.2, 0.3])

        assert len(result) == 1
        assert result[0].doc_id == "doc1"
        assert mock_col.query.call_count == 2

    def test_query_raises_non_transient_immediately(self) -> None:
        mem, mock_col = self._make_memory()
        mock_col.count.return_value = 1
        mock_col.query.side_effect = ValueError("bad")

        with pytest.raises(ValueError, match="bad"):
            mem.query_similar([0.1, 0.2, 0.3])

        assert mock_col.query.call_count == 1

    def test_query_timeout_raises_timeout_error(self) -> None:
        import threading as _threading

        mem, mock_col = self._make_memory()
        mem._timeout = 0.2
        mem._max_retries = 0

        block = _threading.Event()

        def _slow_count() -> int:
            block.wait()
            return 1

        mock_col.count.side_effect = _slow_count

        try:
            with pytest.raises(TimeoutError):
                mem.query_similar([0.1, 0.2, 0.3])
        finally:
            block.set()
