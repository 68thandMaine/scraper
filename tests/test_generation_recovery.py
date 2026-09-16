"""Regression coverage for reasoning-only and incomplete generation."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from web_scraper.agent import OllamaClient


@pytest.mark.parametrize(
    "choice, error",
    [
        ({"message": {"content": "OK"}, "finish_reason": "stop"}, None),
        ({"message": {"content": "partial"}, "finish_reason": "length"}, "token budget"),
        ({"message": {"reasoning_content": "thinking"}}, "no assistant text"),
        ({"message": {"content": "  "}}, "no assistant text"),
    ],
)
@patch("web_scraper.agent.httpx.Client")
def test_generation_returns_only_complete_text(mock_client_cls, choice, error):
    http = mock_client_cls.return_value
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {"choices": [choice]}
    http.post.return_value = response
    client = OllamaClient(model="hermes")
    if error:
        with pytest.raises(ValueError, match=error):
            client.generate("system", "prompt")
    else:
        assert client.generate("system", "prompt") == "OK"
    payload = http.post.call_args.kwargs["json"]
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["stream"] is True


@pytest.mark.parametrize("ending, error", [
    ('data: {"choices":[{"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n', None),
    ('', "before completion"),
    ('data: [DONE]\n\n', "before completion"),
    ('data: {"error":"server failed"}\n\n', "server failed"),
    ('data: {"choices":[{"finish_reason":"length"}]}\n\ndata: [DONE]\n\n', "token budget"),
])
def test_sse_generation(ending, error):
    body = (
        'data: {"choices":[{"delta":{"reasoning_content":"ignored"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"clean"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" text"}}]}\n\n'
    ) + ending
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, text=body,
    ))
    with httpx.Client(transport=transport, base_url="http://test") as http:
        with patch("web_scraper.agent.httpx.Client", return_value=http):
            client = OllamaClient()
            if error:
                with pytest.raises(ValueError, match=error):
                    client.generate("system", "prompt")
            else:
                assert client.generate("system", "prompt") == "clean text"
