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
from core.services.pod_pipeline_utils import read_json, utc_now, write_json
from core.services.pod_strategy_service import PodStrategyService, STEP_NAME


TITLE = "[1] Alysha — creative-strategy-engine"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    add_common_args(parser)
    parser.add_argument("--brand-context-file", required=True)
    parser.add_argument("--brand-learning-file", default=None)
    parser.add_argument("--pod-campaign-intake-file", required=True)
    parser.add_argument("--product-catalog-entry-file", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings, paths, ledger, client, notifier = build_runtime(args)
    notify_step_started(notifier, TITLE, args.brand_id, args.campaign_id)
    report = {
        "job": "run_pod_strategy_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "started_at": utc_now(),
        "status": "running",
    }
    try:
        brand_context = read_json(args.brand_context_file)
        brand_learning = read_json(args.brand_learning_file, required=False) if args.brand_learning_file else None
        campaign_intake = read_json(args.pod_campaign_intake_file)
        product_catalog_entry = read_json(args.product_catalog_entry_file)

        strategy, api_meta = PodStrategyService(client).run(
            brand_context=brand_context,
            brand_learning=brand_learning,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            brand_id=args.brand_id,
        )

        strategy_file = write_json(paths.step_1_strategy_dir / "pod_strategy_output.json", strategy)
        api_meta_file = write_json(paths.step_1_strategy_dir / "pod_strategy_output_api_meta.json", api_meta)
        report.update({
            "status": "success",
            "completed_at": utc_now(),
            "artifacts": {
                "pod_strategy_output": str(strategy_file),
                "api_meta": str(api_meta_file),
            },
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_1_strategy_usage_report.json",
            report_file=paths.reports_dir / "step_1_strategy_run_report.json",
            report=report,
        )
        notify_step_completed(notifier, title=TITLE, brand_id=args.brand_id, campaign_id=args.campaign_id, ledger=ledger, step_name=STEP_NAME)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_1_strategy_usage_report.json",
            report_file=paths.reports_dir / "step_1_strategy_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
