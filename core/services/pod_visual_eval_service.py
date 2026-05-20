from __future__ import annotations

import json
from typing import Any

from core.evaluators.deepeval_claude_judge import build_deepeval_claude_judge
from .pod_llm_client import PodClaudeJsonClient


STEP_NAME = "06_deepeval_visual_output_evaluation"


class PodVisualEvalService:
    def __init__(self, llm_client: PodClaudeJsonClient, *, threshold: float = 0.85) -> None:
        self.llm_client = llm_client
        self.threshold = float(threshold)

    def run(
        self,
        *,
        campaign_intake: dict[str, Any],
        product_catalog_entry: dict[str, Any],
        strategy_output: dict[str, Any],
        design_brief: dict[str, Any],
        translation_output: dict[str, Any],
        render_result: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_render_result(render_result)
        try:
            from deepeval.metrics import GEval
            from deepeval.test_case import LLMTestCase, LLMTestCaseParams
        except Exception as exc:
            raise RuntimeError(
                "deepeval is required. Install with: pip install -r requirements.txt"
            ) from exc

        judge = build_deepeval_claude_judge(self.llm_client)
        metric = GEval(
            name="POD Visual Output Evaluation",
            criteria=(
                "Evaluate whether the rendered POD visual outputs, using the available render metadata "
                "and generated image references, satisfy the POD Design Brief and Open Design translation. "
                "The output must preserve brand/product constraints, match required output groups, avoid "
                "forbidden elements, support the strategy, and provide enough evidence for human review."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=self.threshold,
            async_mode=False,
        )

        test_case = LLMTestCase(
            input=json.dumps(
                {
                    "campaign_intake": campaign_intake,
                    "product_catalog_entry": product_catalog_entry,
                    "strategy_output": strategy_output,
                    "design_brief": design_brief,
                    "translation_output": translation_output,
                },
                ensure_ascii=False,
                indent=2,
            ),
            actual_output=json.dumps(render_result, ensure_ascii=False, indent=2),
            expected_output=(
                "Rendered POD visuals or render submissions that match the approved brief, cover each required "
                "output group, preserve brand/IP/product constraints, and are ready for human review."
            ),
        )

        metric.measure(test_case)
        score = float(metric.score or 0.0)
        status = "pass" if score >= self.threshold else "fail"
        return {
            "stage": "pod_visual_output_evaluation",
            "framework": "deepeval_geval",
            "metric_name": "POD Visual Output Evaluation",
            "threshold": self.threshold,
            "score": round(score, 6),
            "status": status,
            "reason": metric.reason or "",
            "regeneration_required": status == "fail",
            "regeneration_feedback": {
                "reason": metric.reason or "",
                "score": round(score, 6),
                "threshold": self.threshold,
                "required_action": "Regenerate Step [4] translation and Step [5] render outputs to resolve visual issues.",
            },
        }

    def _validate_render_result(self, render_result: dict[str, Any]) -> None:
        status = str(render_result.get("status") or "").strip().lower()
        if status == "success":
            return
        if str(render_result.get("mode") or "").strip().lower() == "dry_run":
            raise RuntimeError(
                "Step [6] visual evaluation requires rendered/submitted outputs. "
                "Step [5] is in dry_run mode; configure ComfyUI before evaluating visuals."
            )
        raise RuntimeError(f"Step [5] render result is not successful: {status}")
