from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from .pod_pipeline_utils import UsageLedger


class PodClaudeJsonClient:
    """
    Standalone Anthropic Messages API client for the POD [1]-[4] jobs.
    If the existing project already has a Claude adapter, this can be swapped later.
    """

    def __init__(
        self,
        *,
        model: str,
        usage_ledger: UsageLedger,
        timeout_seconds: int = 300,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.usage_ledger = usage_ledger
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required.")

    def _request(self, *, system: str, user: str, max_tokens: int, temperature: float) -> dict[str, Any]:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_text(response_payload: dict[str, Any]) -> str:
        chunks: list[str] = []
        for block in response_payload.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(str(block.get("text", "")))
        return "\n".join(chunks).strip()

    @staticmethod
    def _parse_json(text: str) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(1))

    def generate_json(
        self,
        *,
        step: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.2,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw = self._request(system=system, user=user, max_tokens=max_tokens, temperature=temperature)
        usage = raw.get("usage") or {}
        event = self.usage_ledger.record(
            step=step,
            provider="anthropic",
            model=self.model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            metadata=metadata or {},
        )
        parsed = self._parse_json(self._extract_text(raw))
        if not isinstance(parsed, dict):
            raise TypeError("Expected JSON object from LLM.")
        return parsed, {
            "provider": "anthropic",
            "model": self.model,
            "response_id": raw.get("id"),
            "stop_reason": raw.get("stop_reason"),
            "usage_event": event.__dict__,
        }

    def generate_text_for_eval(
        self,
        *,
        step: str,
        prompt: str,
        max_tokens: int = 4096,
    ) -> str:
        raw = self._request(system="", user=prompt, max_tokens=max_tokens, temperature=0.0)
        usage = raw.get("usage") or {}
        self.usage_ledger.record(
            step=step,
            provider="anthropic",
            model=self.model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            metadata={"purpose": "deepeval_geval_judge"},
        )
        return self._extract_text(raw)
