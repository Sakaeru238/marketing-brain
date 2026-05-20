from __future__ import annotations

import argparse
import json

from core.jobs.pod_job_common import (
    add_common_args,
    build_runtime,
    notify_step_completed,
    notify_step_failed,
    notify_step_started,
    write_usage_and_report,
)
from core.evaluators.deepeval_claude_judge import STEP_NAME
from core.services.pod_brief_eval_service import PodBriefEvalService
from core.services.pod_pipeline_utils import read_json, utc_now, write_json


TITLE = "[3] DeepEval — Brief Strategy Evaluation"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    add_common_args(parser)
    parser.add_argument("--pod-campaign-intake-file", required=True)
    parser.add_argument("--strategy-output-file", required=True)
    parser.add_argument("--design-brief-file", required=True)
    parser.add_argument("--brief-version", default="v001")
    parser.add_argument("--threshold", type=float, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings, paths, ledger, client, notifier = build_runtime(args)
    threshold = args.threshold if args.threshold is not None else float(settings.get("brief_eval", {}).get("threshold", 0.85))
    notify_step_started(notifier, TITLE, args.brand_id, args.campaign_id)
    report = {
        "job": "run_pod_brief_eval_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "brief_version": args.brief_version,
        "threshold": threshold,
        "started_at": utc_now(),
        "status": "running",
    }
    try:
        campaign_intake = read_json(args.pod_campaign_intake_file)
        strategy_output = read_json(args.strategy_output_file)
        design_brief = read_json(args.design_brief_file)

        eval_result = PodBriefEvalService(client, threshold=threshold).run(
            campaign_intake=campaign_intake,
            strategy_output=strategy_output,
            design_brief=design_brief,
        )
        eval_result["brief_version_evaluated"] = args.brief_version

        eval_file = write_json(paths.step_3_brief_eval_dir / f"pod_brief_eval_{args.brief_version}.json", eval_result)
        revision_feedback_file = write_json(paths.step_3_brief_eval_dir / f"pod_brief_revision_feedback_{args.brief_version}.json", eval_result.get("revision_feedback", {}))

        report.update({
            "status": "success",
            "completed_at": utc_now(),
            "eval_status": eval_result.get("status"),
            "eval_score": eval_result.get("score"),
            "artifacts": {
                "pod_brief_eval": str(eval_file),
                "revision_feedback": str(revision_feedback_file),
            },
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / f"step_3_brief_eval_{args.brief_version}_usage_report.json",
            report_file=paths.reports_dir / f"step_3_brief_eval_{args.brief_version}_run_report.json",
            report=report,
        )
        notify_step_completed(
            notifier,
            title=TITLE,
            brand_id=args.brand_id,
            campaign_id=args.campaign_id,
            ledger=ledger,
            step_name=STEP_NAME,
            extra=f"Eval status: {eval_result.get('status')}\nScore: {eval_result.get('score')}",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / f"step_3_brief_eval_{args.brief_version}_usage_report.json",
            report_file=paths.reports_dir / f"step_3_brief_eval_{args.brief_version}_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
