import argparse
import json
from typing import Any, Dict, List

from core.services.brand_job_router import BrandJobRouter
from core.services.brand_learning_summary_service import BrandLearningSummaryService


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild brand learning summaries for one brand or all eligible brands.")
    parser.add_argument("--brand-id", default="")
    parser.add_argument("--include-inactive", action="store_true")
    args = parser.parse_args()

    router = BrandJobRouter()
    targets = router.resolve_targets(
        module_name="brand_learning",
        brand_id=args.brand_id or None,
        active_only=not args.include_inactive,
    )

    outputs: List[Dict[str, Any]] = []
    for target in targets:
        brand_id = target["brand_id"]
        summary = BrandLearningSummaryService(brand_id=brand_id).rebuild_summary()
        outputs.append(
            {
                "brand_id": brand_id,
                "summary_file": str(target["paths"]["brand_learning_summary_file"]),
                "stats": summary.get("stats") or {},
            }
        )

    print(
        json.dumps(
            {
                "status": "success",
                "brands_processed": len(outputs),
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
