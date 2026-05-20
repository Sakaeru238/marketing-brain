import os
import time
try:
    from anthropic._exceptions import OverloadedError
except Exception:  # pragma: no cover - allows dry-run flows without anthropic installed
    class OverloadedError(Exception):
        pass

from core.config.claude_mode_settings import CLAUDE_MODE
from core.config.claude_api_settings import (
    CLAUDE_API_ENABLED,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
)

try:
    from anthropic import Anthropic

    HAS_ANTHROPIC = True
except Exception:
    HAS_ANTHROPIC = False


class ClaudeAPIAdapter:
    def __init__(self):
        self.mode = CLAUDE_MODE
        self.enabled = CLAUDE_API_ENABLED
        self.api_key = CLAUDE_API_KEY
        self.model = CLAUDE_MODEL
        self.default_max_tokens = 4000
        self.input_usd_per_million_tokens = float(os.getenv("CLAUDE_INPUT_USD_PER_MILLION_TOKENS", "3.0"))
        self.output_usd_per_million_tokens = float(os.getenv("CLAUDE_OUTPUT_USD_PER_MILLION_TOKENS", "15.0"))
        self._usage_events = []

        if HAS_ANTHROPIC and self.api_key and self.enabled:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def readiness(self):
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
            "has_sdk": HAS_ANTHROPIC,
            "model": self.model,
            "ready": (
                self.mode == "api"
                and self.enabled
                and bool(self.api_key)
                and HAS_ANTHROPIC
                and self.client is not None
            ),
        }


    def _usage_from_response(self, response):
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        input_cost = (input_tokens / 1_000_000) * self.input_usd_per_million_tokens
        output_cost = (output_tokens / 1_000_000) * self.output_usd_per_million_tokens
        event = {
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost_usd": round(input_cost, 8),
            "output_cost_usd": round(output_cost, 8),
            "total_cost_usd": round(input_cost + output_cost, 8),
            "status": "available" if usage is not None else "unavailable_from_api_response",
        }
        self._usage_events.append(event)
        return event

    def usage_summary(self, reset=False):
        events = list(self._usage_events)
        summary = {
            "model": self.model,
            "calls": len(events),
            "input_tokens": sum(event.get("input_tokens", 0) for event in events),
            "output_tokens": sum(event.get("output_tokens", 0) for event in events),
            "total_tokens": sum(event.get("total_tokens", 0) for event in events),
            "total_cost_usd": round(sum(float(event.get("total_cost_usd", 0.0) or 0.0) for event in events), 8),
            "events": events,
        }
        if reset:
            self._usage_events.clear()
        return summary

    def run(self, prompt=None, package=None, **kwargs):
        readiness = self.readiness()
        if not readiness.get("ready"):
            raise RuntimeError(f"Claude API adapter is not ready: {readiness}")

        payload = prompt if prompt is not None else package
        if payload is None:
            payload = ""
        if not isinstance(payload, str):
            payload = str(payload)

        max_tokens = int(kwargs.get("max_tokens") or self.default_max_tokens)
        temperature = kwargs.get("temperature", 0)

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": payload}],
                        }
                    ],
                )
                self._usage_from_response(response)
                return response
            except OverloadedError as e:
                last_error = e
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
            except Exception as e:
                last_error = e
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))

        raise RuntimeError(f"Claude API call failed: {last_error}")
