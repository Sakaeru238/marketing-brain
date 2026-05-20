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
from core.services.pod_open_design_translation_service import PodOpenDesignTranslationService, STEP_NAME
from core.services.pod_pipeline_utils import read_json, utc_now, write_json


TITLE = "[4] Open Design / Generative Media Translation Layer"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    add_common_args(parser)
    parser.add_argument("--pod-campaign-intake-file", required=True)
    parser.add_argument("--product-catalog-entry-file", required=True)
    parser.add_argument("--strategy-output-file", required=True)
    parser.add_argument("--approved-design-brief-file", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings, paths, ledger, client, notifier = build_runtime(args)
    notify_step_started(notifier, TITLE, args.brand_id, args.campaign_id)
    report = {
        "job": "run_pod_open_design_translation_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "started_at": utc_now(),
        "status": "running",
    }
    try:
        campaign_intake = read_json(args.pod_campaign_intake_file)
        product_catalog_entry = read_json(args.product_catalog_entry_file)
        strategy_output = read_json(args.strategy_output_file)
        design_brief = read_json(args.approved_design_brief_file)

        translation, api_meta = PodOpenDesignTranslationService(client).run(
            brand_id=args.brand_id,
            campaign_id=args.campaign_id,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy_output,
            design_brief=design_brief,
        )

        translation_file = write_json(paths.step_4_translation_dir / "pod_open_design_translation.json", translation)
        chatgpt_prompt_file = write_json(
            paths.step_4_translation_dir / "chatgpt_image_prompts.json",
            {
                "brand_id": args.brand_id,
                "campaign_id": args.campaign_id,
                "prompts": translation.get("chatgpt_image_prompts", []),
            },
        )
        comfyui_bundle_file = write_json(
            paths.step_4_translation_dir / "comfyui_render_request_bundle.json",
            {
                "brand_id": args.brand_id,
                "campaign_id": args.campaign_id,
                "requests": translation.get("comfyui_render_requests", []),
            },
        )
        api_meta_file = write_json(paths.step_4_translation_dir / "pod_open_design_translation_api_meta.json", api_meta)

        report.update({
            "status": "success",
            "completed_at": utc_now(),
            "artifacts": {
                "translation": str(translation_file),
                "chatgpt_image_prompts": str(chatgpt_prompt_file),
                "comfyui_render_request_bundle": str(comfyui_bundle_file),
                "api_meta": str(api_meta_file),
            },
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_4_open_design_translation_usage_report.json",
            report_file=paths.reports_dir / "step_4_open_design_translation_run_report.json",
            report=report,
        )
        notify_step_completed(notifier, title=TITLE, brand_id=args.brand_id, campaign_id=args.campaign_id, ledger=ledger, step_name=STEP_NAME)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_4_open_design_translation_usage_report.json",
            report_file=paths.reports_dir / "step_4_open_design_translation_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
