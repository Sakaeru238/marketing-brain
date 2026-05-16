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
                return self.client.messages.create(
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
