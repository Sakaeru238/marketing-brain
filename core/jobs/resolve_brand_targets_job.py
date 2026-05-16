import argparse
import json

from core.services.brand_job_router import BrandJobRouter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve active brands for a Marketing-Brain module.")
    parser.add_argument("--module", required=True, choices=["brand_intake", "organic", "paid_ads", "pod"], help="Target module name.")
    parser.add_argument("--brand-id", default=None, help="Optional single brand override.")
    parser.add_argument("--include-inactive", action="store_true", help="Include inactive brands in lookup.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    router = BrandJobRouter()
    targets = router.resolve_targets(
        module_name=args.module,
        brand_id=args.brand_id,
        active_only=not args.include_inactive,
    )
    serializable = []
    for target in targets:
        paths = target.get("paths") or {}
        serializable.append({
            "brand_id": target.get("brand_id"),
            "brand": target.get("brand"),
            "paths": {key: str(value) for key, value in paths.items() if key != "brand"},
        })
    print(json.dumps({
        "status": "success",
        "module": args.module,
        "brand_id_filter": args.brand_id,
        "targets_found": len(serializable),
        "targets": serializable,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
