from __future__ import annotations

from typing import Any

from core.services.pod_llm_client import PodClaudeJsonClient


STEP_NAME = "03_deepeval_brief_strategy_evaluation"


def build_deepeval_claude_judge(llm_client: PodClaudeJsonClient):
    try:
        from deepeval.models.base_model import DeepEvalBaseLLM
    except Exception as exc:
        raise RuntimeError(
            "deepeval is required. Install with: pip install -r requirements-pod-strategy-brief.txt"
        ) from exc

    class ClaudeJudge(DeepEvalBaseLLM):
        def load_model(self):
            return llm_client

        def generate(self, prompt: str, schema: Any | None = None):
            return llm_client.generate_text_for_eval(step=STEP_NAME, prompt=prompt)

        async def a_generate(self, prompt: str, schema: Any | None = None):
            return self.generate(prompt, schema=schema)

        def get_model_name(self):
            return llm_client.model

    return ClaudeJudge()
