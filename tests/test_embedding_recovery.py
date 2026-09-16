"""Regression coverage for llama.cpp physical batch size failures."""

import httpx
import pytest

from web_scraper.agent import OllamaClient
from web_scraper.agent import ContentAgent, AgentDecision, DocumentMemory
from unittest.mock import MagicMock


def test_size_recovery_preserves_every_character():
    accepted = []

    def serve(request):
        import json
        value = json.loads(request.content)["input"]
        if len(value) > 4:
            return httpx.Response(500, json={"error": {"message":
                "input is too large to process. increase the physical batch size"}})
        accepted.append(value)
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    with OllamaClient() as client:
        client._embed_client.close()
        client._embed_client = httpx.Client(
            base_url="http://test", transport=httpx.MockTransport(serve))
        assert client.embed("abcdefghijklmno") == [1.0, 0.0]
    assert "".join(accepted) == "abcdefghijklmno"


def test_unrelated_server_error_is_not_split():
    calls = []

    def serve(request):
        calls.append(request)
        return httpx.Response(500, json={"error": "backend unavailable"})

    with OllamaClient() as client:
        client._embed_client.close()
        client._embed_client = httpx.Client(
            base_url="http://test", transport=httpx.MockTransport(serve))
        with pytest.raises(httpx.HTTPStatusError, match="backend unavailable"):
            client.embed("document")
    assert len(calls) == 1


def test_failed_page_is_preserved_and_next_page_uses_ai(tmp_path):
    model = MagicMock(spec=OllamaClient)
    model.generate.side_effect = [httpx.ReadTimeout("unavailable"),
                                  "clean content", "DECISION: SAVE\nREASON: unique"]
    model.embed.return_value = [1.0, 0.0]
    memory = MagicMock(spec=DocumentMemory)
    memory.query_similar.return_value = []
    agent = ContentAgent(str(tmp_path), ollama=model, memory=memory)
    failed = agent.process_document(dict(url="https://example.com/1", title="one", content="original body"))
    assert failed.decision == AgentDecision.ERROR
    assert "original body" in failed.file_path.read_text()
    succeeded = agent.process_document(dict(url="https://example.com/2", title="two", content="second body"))
    assert succeeded.decision == AgentDecision.SAVE
    assert agent.stats.errors == 1
    assert agent.stats.saved == 1
    assert agent.stats.skipped == 0
    assert len(list(tmp_path.glob("*.txt"))) == 2
