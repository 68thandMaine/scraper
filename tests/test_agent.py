"""Tests for the Ollama content agent."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from web_scraper.agent import (
    AgentDecision,
    ContentAgent,
    DocumentMemory,
    OllamaClient,
)


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
            "models": [{"name": "phi3:mini"}]
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
        mock_response.json.return_value = {"response": "cleaned body"}
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
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_client.post.return_value = mock_response

        client = OllamaClient(host="http://localhost:11434")
        result = client.embed("sample text")

        assert result == [0.1, 0.2, 0.3]
        call_kwargs = mock_client.post.call_args
        sent_input = call_kwargs[1]["json"]["input"]
        assert isinstance(sent_input, str)

    @patch("web_scraper.agent.httpx.Client")
    def test_embed_multi_chunk_mean_pooled(self, mock_client_cls: MagicMock) -> None:
        import math

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "embeddings": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
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
