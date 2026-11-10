"""Unit tests for LLM API clients, JSON extraction, and secret redaction."""

import httpx
import pytest

from sdlc_app.llm import LLMClient, LLMError, extract_json_object, mask_secret


def test_mask_secret_never_exposes_full_key() -> None:
    assert mask_secret("") == ""
    assert mask_secret("short") == "*****"
    masked = mask_secret("AIzaSyDummySecretValue123456")
    assert masked == "AIza...3456"
    assert "DummySecretValue" not in masked


def test_extract_json_object_handles_markdown_fences() -> None:
    raw = 'Here is the plan:\n```json\n{"summary": "Add note field", "in_scope": true}\n```\nDone.'
    parsed = extract_json_object(raw)
    assert parsed == {"summary": "Add note field", "in_scope": True}


def test_gemini_client_sends_key_in_header_not_url() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"summary": "OK", "in_scope": true}'}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = LLMClient(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="AIzaTestKeySecret9999",
        transport=transport,
    )
    text = client.complete(system_prompt="You are Spec Agent.", user_prompt="Review feature")
    assert '"summary": "OK"' in text
    assert "AIzaTestKeySecret9999" not in str(captured["url"])
    assert captured["headers"]["x-goog-api-key"] == "AIzaTestKeySecret9999"


def test_openai_compatible_client_posts_chat_completion() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"summary": "Compat OK", "in_scope": true}'}},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = LLMClient(
        provider="openai",
        model="gpt-4o-mini",
        api_key="sk-test-secret-0001",
        base_url="https://api.example.test/v1/",
        transport=transport,
    )
    text = client.complete(system_prompt="Architect", user_prompt="Plan")
    assert "Compat OK" in text
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test-secret-0001"


def test_llm_error_sanitizes_api_key_if_echoed_upstream() -> None:
    secret = "AIzaSecretLeakCandidate8888"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": f"Bad key {secret}"}})

    client = LLMClient(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key=secret,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMError) as exc_info:
        client.complete(system_prompt="sys", user_prompt="usr")

    assert secret not in str(exc_info.value)
    assert "401" in str(exc_info.value)
