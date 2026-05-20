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
from core.services.pod_comfyui_render_worker import PodComfyUIRenderWorker, STEP_NAME
from core.services.pod_pipeline_utils import read_json, utc_now, write_json


TITLE = "[5] ComfyUI Render Worker"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    add_common_args(parser)
    parser.add_argument("--render-request-bundle-file", required=True)
    parser.add_argument("--attempt-no", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings, paths, ledger, client, notifier = build_runtime(args)
    notify_step_started(notifier, TITLE, args.brand_id, args.campaign_id)
    report = {
        "job": "run_pod_comfyui_render_worker_job",
        "title": TITLE,
        "brand_id": args.brand_id,
        "campaign_id": args.campaign_id,
        "started_at": utc_now(),
        "status": "running",
    }
    try:
        bundle = read_json(args.render_request_bundle_file)
        render_result = PodComfyUIRenderWorker(settings=settings).run(
            brand_id=args.brand_id,
            campaign_id=args.campaign_id,
            render_request_bundle=bundle,
            output_dir=paths.step_5_render_dir,
            attempt_no=args.attempt_no,
        )
        render_file = write_json(paths.step_5_render_dir / f"comfyui_render_result_attempt_{args.attempt_no:02d}.json", render_result)
        report.update({
            "status": render_result.get("status"),
            "completed_at": utc_now(),
            "artifacts": {"render_result": str(render_file)},
        })
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_5_comfyui_render_usage_report.json",
            report_file=paths.reports_dir / "step_5_comfyui_render_run_report.json",
            report=report,
        )
        notify_step_completed(notifier, title=TITLE, brand_id=args.brand_id, campaign_id=args.campaign_id, ledger=ledger, step_name=STEP_NAME)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        report.update({"status": "failed", "completed_at": utc_now(), "error": str(exc)})
        write_usage_and_report(
            ledger=ledger,
            usage_file=paths.usage_dir / "step_5_comfyui_render_usage_report.json",
            report_file=paths.reports_dir / "step_5_comfyui_render_run_report.json",
            report=report,
        )
        notify_step_failed(notifier, TITLE, args.brand_id, args.campaign_id, exc)
        raise


if __name__ == "__main__":
    main()
