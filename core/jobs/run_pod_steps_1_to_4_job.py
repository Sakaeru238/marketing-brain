from __future__ import annotations

import argparse
import json

from core.config.paths import GLOBAL_CONFIG_DIR
from core.jobs.pod_job_common import (
    DEFAULT_CONFIG_FILE,
    build_runtime,
    notify_step_completed,
    notify_step_failed,
    notify_step_started,
    write_usage_and_report,
)
from core.evaluators.deepeval_claude_judge import STEP_NAME as STEP_3_NAME
from core.services.pod_brief_eval_service import PodBriefEvalService
from core.services.pod_design_brief_service import PodDesignBriefService, STEP_NAME as STEP_2_NAME
from core.services.pod_input_resolver import PodInputResolver
from core.services.pod_open_design_translation_service import PodOpenDesignTranslationService, STEP_NAME as STEP_4_NAME
from core.services.pod_pipeline_utils import read_json, utc_now, write_json
from core.services.pod_strategy_service import PodStrategyService, STEP_NAME as STEP_1_NAME


TITLE = "POD Steps [1]-[4] Production Pipeline"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config-file", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--telegram-disabled", action="store_true")
    parser.add_argument("--brief-eval-threshold", type=float, default=None)
    return parser


def load_brief_eval_limits(settings: dict) -> dict:
    global_settings = read_json(GLOBAL_CONFIG_DIR / "system_settings.json")
    global_limits = (
        (global_settings.get("evaluation_limits") or {})
        .get("brief_eval")
        or {}
    )
    pod_limits = settings.get("brief_eval") or {}
    return {
        "min_score": float(pod_limits.get("threshold", global_limits.get("min_score", 0.85))),
        "max_cost_usd": float(pod_limits.get("max_cost_usd", global_limits.get("max_cost_usd", 0.1))),
        "max_attempts": int(
            pod_limits.get(
                "max_attempts",
                global_limits.get("max_attempts", int(pod_limits.get("max_brief_revisions", 4)) + 1),
            )
        ),
    }


def main() -> None:
    args = build_parser().parse_args()
    resolver = PodInputResolver()
    resolved_source = resolver.resolve_ready_campaign(brand_id=args.brand_id)
    resolver.mark_campaign_status(
        brand_id=args.brand_id,
        row_number=resolved_source["source"]["campaign_row_number"],
        status="working",
    )
    args.campaign_id = resolved_source["campaign_id"]

    settings, paths, ledger, client, notifier = build_runtime(args)
    brief_eval_limits = load_brief_eval_limits(settings)
    threshold = args.brief_eval_threshold if args.brief_eval_threshold is not None else brief_eval_limits["min_score"]
    max_attempts = brief_eval_limits["max_attempts"]
    max_cost_usd = brief_eval_limits["max_cost_usd"]

    report = {
        "job": "run_pod_steps_1_to_4_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "started_at": utc_now(),
        "status": "running",
        "brief_eval_threshold": threshold,
        "max_brief_eval_attempts": max_attempts,
        "max_cost_usd": max_cost_usd,
        "steps": {},
        "artifacts": {},
        "source": resolved_source["source"],
    }

    try:
        brand_context = read_json(resolved_source["paths"]["brand_context_file"])
        brand_learning_file = resolved_source["paths"]["brand_learning_file"]
        brand_learning = read_json(brand_learning_file, required=False) if brand_learning_file else None
        campaign_intake = read_json(resolved_source["paths"]["pod_campaign_intake_file"])
        product_catalog_entry = read_json(resolved_source["paths"]["product_catalog_entry_file"])

        # Step [1]
        step_title = "[1] Alysha — creative-strategy-engine"
        notify_step_started(notifier, step_title, args.brand_id, args.campaign_id)
        strategy, strategy_meta = PodStrategyService(client).run(
            brand_context=brand_context,
            brand_learning=brand_learning,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            brand_id=args.brand_id,
        )
        strategy_file = write_json(paths.step_1_strategy_dir / "pod_strategy_output.json", strategy)
        strategy_meta_file = write_json(paths.step_1_strategy_dir / "pod_strategy_output_api_meta.json", strategy_meta)
        report["steps"]["step_1_strategy"] = "success"
        report["artifacts"]["pod_strategy_output"] = str(strategy_file)
        report["artifacts"]["pod_strategy_api_meta"] = str(strategy_meta_file)
        notify_step_completed(notifier, title=step_title, brand_id=args.brand_id, campaign_id=args.campaign_id, ledger=ledger, step_name=STEP_1_NAME)

        # Steps [2] and [3] loop
        latest_brief = None
        latest_eval = None
        revision_feedback = None
        eval_loop_start_cost = float(ledger.summary().get("total_cost_usd", 0.0))
        previous_attempt_cost = 0.0

        for attempt_index in range(max_attempts):
            current_cost = float(ledger.summary().get("total_cost_usd", 0.0))
            eval_loop_cost = round(current_cost - eval_loop_start_cost, 8)
            remaining_budget = round(max_cost_usd - eval_loop_cost, 8)
            if attempt_index > 0 and previous_attempt_cost > 0 and remaining_budget < previous_attempt_cost:
                report.update({
                    "status": "stopped_budget_not_enough_for_next_brief_eval_attempt",
                    "completed_at": utc_now(),
                    "final_brief_eval": latest_eval,
                    "budget_limit": {
                        "max_cost_usd": max_cost_usd,
                        "current_eval_loop_cost_usd": eval_loop_cost,
                        "remaining_budget_usd": remaining_budget,
                        "estimated_next_attempt_cost_usd": previous_attempt_cost,
                    },
                })
                write_usage_and_report(
                    ledger=ledger,
                    usage_file=paths.usage_dir / "pod_steps_1_to_4_usage_report.json",
                    report_file=paths.reports_dir / "pod_steps_1_to_4_run_report.json",
                    report=report,
                )
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return

            attempt_start_cost = current_cost
            brief_version = f"v{attempt_index + 1:03d}"

            step_title = "[2] julianoczkowski/designer-skills — POD Design Brief"
            notify_step_started(notifier, step_title, args.brand_id, args.campaign_id)
            brief, brief_meta = PodDesignBriefService(client).run(
                brand_context=brand_context,
                campaign_intake=campaign_intake,
                product_catalog_entry=product_catalog_entry,
                strategy_output=strategy,
                revision_feedback=revision_feedback,
                brand_id=args.brand_id,
            )
            brief["brief_version"] = brief_version
            brief_file = write_json(paths.step_2_brief_dir / f"pod_design_brief_{brief_version}.json", brief)
            brief_meta_file = write_json(paths.step_2_brief_dir / f"pod_design_brief_{brief_version}_api_meta.json", brief_meta)
            latest_brief = brief
            report["artifacts"][f"pod_design_brief_{brief_version}"] = str(brief_file)
            report["artifacts"][f"pod_design_brief_{brief_version}_api_meta"] = str(brief_meta_file)
            notify_step_completed(
                notifier,
                title=step_title,
                brand_id=args.brand_id,
                campaign_id=args.campaign_id,
                ledger=ledger,
                step_name=STEP_2_NAME,
                extra=f"Brief version: {brief_version}",
            )

            step_title = "[3] DeepEval — Brief Strategy Evaluation"
            notify_step_started(notifier, step_title, args.brand_id, args.campaign_id)
            eval_result = PodBriefEvalService(client, threshold=threshold).run(
                campaign_intake=campaign_intake,
                strategy_output=strategy,
                design_brief=brief,
            )
            eval_result["brief_version_evaluated"] = brief_version
            eval_file = write_json(paths.step_3_brief_eval_dir / f"pod_brief_eval_{brief_version}.json", eval_result)
            feedback_file = write_json(paths.step_3_brief_eval_dir / f"pod_brief_revision_feedback_{brief_version}.json", eval_result.get("revision_feedback", {}))
            latest_eval = eval_result
            report["artifacts"][f"pod_brief_eval_{brief_version}"] = str(eval_file)
            report["artifacts"][f"pod_brief_revision_feedback_{brief_version}"] = str(feedback_file)
            notify_step_completed(
                notifier,
                title=step_title,
                brand_id=args.brand_id,
                campaign_id=args.campaign_id,
                ledger=ledger,
                step_name=STEP_3_NAME,
                extra=f"Eval status: {eval_result.get('status')}\nScore: {eval_result.get('score')}",
            )

            if eval_result.get("status") == "pass":
                break
            current_cost = float(ledger.summary().get("total_cost_usd", 0.0))
            previous_attempt_cost = round(current_cost - attempt_start_cost, 8)
            revision_feedback = eval_result.get("revision_feedback") or {}

        if not latest_brief or not latest_eval or latest_eval.get("status") != "pass":
            report.update({
                "status": "brief_eval_failed_after_revision_loop",
                "completed_at": utc_now(),
                "final_brief_eval": latest_eval,
            })
            write_usage_and_report(
                ledger=ledger,
                usage_file=paths.usage_dir / "pod_steps_1_to_4_usage_report.json",
                report_file=paths.reports_dir / "pod_steps_1_to_4_run_report.json",
                report=report,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return

        # Step [4]
        step_title = "[4] Open Design / Generative Media Translation Layer"
        notify_step_started(notifier, step_title, args.brand_id, args.campaign_id)
        translation, translation_meta = PodOpenDesignTranslationService(client).run(
            brand_id=args.brand_id,
            campaign_id=args.campaign_id,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy,
            design_brief=latest_brief,
        )
        translation_file = write_json(paths.step_4_translation_dir / "pod_open_design_translation.json", translation)
        prompts_file = write_json(paths.step_4_translation_dir / "chatgpt_image_prompts.json", {
            "brand_id": args.brand_id,
            "campaign_id": args.campaign_id,
            "prompts": translation.get("chatgpt_image_prompts", []),
        })
        render_bundle_file = write_json(paths.step_4_translation_dir / "comfyui_render_request_bundle.json", {
            "brand_id": args.brand_id,
            "campaign_id": args.campaign_id,
            "requests": translation.get("comfyui_render_requests", []),
        })
        translation_meta_file = write_json(paths.step_4_translation_dir / "pod_open_design_translation_api_meta.json", translation_meta)
        report["artifacts"]["pod_open_design_translation"] = str(translation_file)
        report["artifacts"]["chatgpt_image_prompts"] = str(prompts_file)
        report["artifacts"]["comfyui_render_request_bundle"] = str(render_bundle_file)
        report["artifacts"]["pod_open_design_translation_api_meta"] = str(translation_meta_file)
        notify_step_completed(notifier, title=step_title, brand_id=args.brand_id, campaign_id=args.campaign_id, ledger=ledger, step_name=STEP_4_NAME)

        report.update({
            "status": "success_ready_for_comfyui_render_worker",
            "completed_at": utc_now(),
            "final_brief_eval": latest_eval,
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "pod_steps_1_to_4_usage_report.json",
            report_file=paths.reports_dir / "pod_steps_1_to_4_run_report.json",
            report=report,
        )
        total = ledger.summary()
        notifier.send(
            f"🏁 POD [1]-[4] pipeline completed\n"
            f"Brand: {args.brand_id}\nCampaign: {args.campaign_id}\n"
            f"Status: {report['status']}\n"
            f"Total tokens: {total['total_tokens']}\n"
            f"Total cost: ${total['total_cost_usd']:.6f}"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "pod_steps_1_to_4_usage_report.json",
            report_file=paths.reports_dir / "pod_steps_1_to_4_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
