from __future__ import annotations

import json
from typing import Any

from core.evaluators.deepeval_claude_judge import build_deepeval_claude_judge
from .pod_llm_client import PodClaudeJsonClient


class PodBriefEvalService:
    def __init__(self, llm_client: PodClaudeJsonClient, *, threshold: float = 0.85) -> None:
        self.llm_client = llm_client
        self.threshold = float(threshold)

    def run(
        self,
        *,
        campaign_intake: dict[str, Any],
        strategy_output: dict[str, Any],
        design_brief: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from deepeval.metrics import GEval
            from deepeval.test_case import LLMTestCase, LLMTestCaseParams
        except Exception as exc:
            raise RuntimeError(
                "deepeval is required. Install with: pip install -r requirements-pod-strategy-brief.txt"
            ) from exc

        judge = build_deepeval_claude_judge(self.llm_client)
        metric = GEval(
            name="POD Brief Strategy Alignment",
            criteria=(
                "Evaluate whether the POD Design Brief faithfully implements the POD Strategy Output. "
                "The brief must preserve persona, priority angles, core message, brand fit, SKU fit, "
                "must_keep/must_avoid constraints, product application consistency, and enough specificity "
                "for downstream media translation."
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
                    "strategy_output": strategy_output,
                },
                ensure_ascii=False,
                indent=2,
            ),
            actual_output=json.dumps(design_brief, ensure_ascii=False, indent=2),
            expected_output=(
                "A precise POD Design Brief that is strategy-aligned, SKU-aware, constraint-preserving, "
                "and executable for Open Design / Generative Media Translation."
            ),
        )

        metric.measure(test_case)
        score = float(metric.score or 0.0)
        status = "pass" if score >= self.threshold else "fail"
        return {
            "stage": "pod_brief_strategy_evaluation",
            "framework": "deepeval_geval",
            "metric_name": "POD Brief Strategy Alignment",
            "threshold": self.threshold,
            "score": round(score, 6),
            "status": status,
            "reason": metric.reason or "",
            "revision_required": status == "fail",
            "revision_feedback": {
                "reason": metric.reason or "",
                "score": round(score, 6),
                "threshold": self.threshold,
                "required_action": "Revise POD Design Brief to resolve the alignment issues."
            },
        }
