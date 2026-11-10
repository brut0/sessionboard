"""Direct HTTP LLM client supporting Google Gemini and OpenAI-compatible APIs."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx


class LLMError(RuntimeError):
    """Raised when the upstream LLM request fails or returns unparseable output."""


def mask_secret(secret: str) -> str:
    """Return a non-reversible masked preview of an API key."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from raw LLM output or ```json fenced code blocks."""
    cleaned = raw_text.strip()
    if not cleaned:
        raise LLMError("LLM returned an empty response.")

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise LLMError(f"Failed to parse JSON object from LLM response: {exc}") from exc

    raise LLMError("LLM response did not contain a valid JSON object.")


class LLMClient:
    """Unified synchronous HTTP LLM client for Gemini REST and OpenAI Chat Completions."""

    def __init__(
        self,
        *,
        provider: Literal["gemini", "openai"],
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 90.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _sanitize(self, text: str) -> str:
        if self.api_key:
            return text.replace(self.api_key, "<redacted-key>")
        return text

    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Invoke the configured LLM API and return raw assistant text."""
        if not self.api_key.strip():
            raise LLMError(
                f"No API key configured for provider '{self.provider}'. "
                "Open API Settings in the Web UI or set GEMINI_API_KEY / OPENAI_API_KEY."
            )

        if self.provider == "gemini":
            return self._call_gemini(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        return self._call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

    def _call_gemini(self, *, system_prompt: str, user_prompt: str, temperature: float) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(self._sanitize(f"Gemini request error: {exc}")) from exc

        if resp.status_code >= 400:
            raise LLMError(self._sanitize(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}"))

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError(self._sanitize(f"Gemini returned invalid JSON: {exc}")) from exc
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("Gemini response contained no candidates.")
        parts = candidates[0].get("content", {}).get("parts") or []
        text_chunks = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "".join(text_chunks)

    def _call_openai(self, *, system_prompt: str, user_prompt: str, temperature: float) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(self._sanitize(f"OpenAI-compatible request error: {exc}")) from exc

        if resp.status_code >= 400:
            raise LLMError(self._sanitize(f"LLM HTTP {resp.status_code}: {resp.text[:500]}"))

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError(self._sanitize(f"LLM returned invalid JSON: {exc}")) from exc
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("LLM response contained no choices.")
        message = choices[0].get("message", {})
        return str(message.get("content", ""))
