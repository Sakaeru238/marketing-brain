import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from core.services.brand_learning_store import BrandLearningStore
from core.services.brand_learning_summary_service import BrandLearningSummaryService


def _parse_json_arg(value: str, *, default):
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Invalid JSON argument: {raw}") from exc


def _payload_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if args.input_json:
        path = Path(args.input_json)
        if not path.exists():
            raise FileNotFoundError(f"Input JSON not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("--input-json must contain one JSON object")
        return payload

    return {
        "source_type": args.source_type,
        "learning": args.learning,
        "learning_category": args.learning_category,
        "confidence": args.confidence,
        "recommended_action": args.recommended_action,
        "evidence": _parse_json_arg(args.evidence_json, default=[]),
        "source_ref": _parse_json_arg(args.source_ref_json, default={}),
        "learning_scope": args.learning_scope,
        "status": args.status,
        "context_update_candidate": args.context_update_candidate,
        "metadata": _parse_json_arg(args.metadata_json, default={}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one brand-level learning record and rebuild summary.")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--input-json", default="", help="Optional JSON object containing the full learning payload.")
    parser.add_argument("--source-type", default="")
    parser.add_argument("--learning", default="")
    parser.add_argument("--learning-category", default="general")
    parser.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--recommended-action", default="")
    parser.add_argument("--evidence-json", default="[]", help='JSON array, e.g. ["signal 1", "signal 2"]')
    parser.add_argument("--source-ref-json", default="{}", help='JSON object, e.g. {"campaign_id":"..."}')
    parser.add_argument("--learning-scope", default="brand")
    parser.add_argument("--status", default="active")
    parser.add_argument("--context-update-candidate", action="store_true")
    parser.add_argument("--metadata-json", default="{}", help="Optional JSON object for extra metadata.")
    parser.add_argument("--skip-summary", action="store_true")
    args = parser.parse_args()

    payload = _payload_from_args(args)
    store = BrandLearningStore(brand_id=args.brand_id)
    record = store.append_learning(**payload)

    result: Dict[str, Any] = {
        "status": "success",
        "brand_id": args.brand_id,
        "learning_record": record,
    }
    if not args.skip_summary:
        summary = BrandLearningSummaryService(brand_id=args.brand_id).rebuild_summary()
        result["summary_stats"] = summary.get("stats") or {}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
