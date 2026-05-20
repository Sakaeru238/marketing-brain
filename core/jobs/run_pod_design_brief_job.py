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
from core.services.pod_design_brief_service import PodDesignBriefService, STEP_NAME
from core.services.pod_pipeline_utils import read_json, utc_now, write_json


TITLE = "[2] julianoczkowski/designer-skills — POD Design Brief"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    add_common_args(parser)
    parser.add_argument("--brand-context-file", required=True)
    parser.add_argument("--pod-campaign-intake-file", required=True)
    parser.add_argument("--product-catalog-entry-file", required=True)
    parser.add_argument("--strategy-output-file", required=True)
    parser.add_argument("--revision-feedback-file", default=None)
    parser.add_argument("--brief-version", default="v001")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings, paths, ledger, client, notifier = build_runtime(args)
    notify_step_started(notifier, TITLE, args.brand_id, args.campaign_id)
    report = {
        "job": "run_pod_design_brief_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "brief_version": args.brief_version,
        "started_at": utc_now(),
        "status": "running",
    }
    try:
        brand_context = read_json(args.brand_context_file)
        campaign_intake = read_json(args.pod_campaign_intake_file)
        product_catalog_entry = read_json(args.product_catalog_entry_file)
        strategy_output = read_json(args.strategy_output_file)
        revision_feedback = read_json(args.revision_feedback_file, required=False) if args.revision_feedback_file else None

        brief, api_meta = PodDesignBriefService(client).run(
            brand_context=brand_context,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy_output,
            revision_feedback=revision_feedback,
            brand_id=args.brand_id,
        )
        brief["brief_version"] = args.brief_version

        brief_file = write_json(paths.step_2_brief_dir / f"pod_design_brief_{args.brief_version}.json", brief)
        api_meta_file = write_json(paths.step_2_brief_dir / f"pod_design_brief_{args.brief_version}_api_meta.json", api_meta)

        report.update({
            "status": "success",
            "completed_at": utc_now(),
            "artifacts": {
                "pod_design_brief": str(brief_file),
                "api_meta": str(api_meta_file),
            },
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / f"step_2_design_brief_{args.brief_version}_usage_report.json",
            report_file=paths.reports_dir / f"step_2_design_brief_{args.brief_version}_run_report.json",
            report=report,
        )
        notify_step_completed(
            notifier,
            title=TITLE,
            brand_id=args.brand_id,
            campaign_id=args.campaign_id,
            ledger=ledger,
            step_name=STEP_NAME,
            extra=f"Brief version: {args.brief_version}",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / f"step_2_design_brief_{args.brief_version}_usage_report.json",
            report_file=paths.reports_dir / f"step_2_design_brief_{args.brief_version}_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
