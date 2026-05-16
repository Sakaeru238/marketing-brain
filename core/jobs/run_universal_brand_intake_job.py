from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import traceback
from typing import Any, Dict

from core.engines.universal_brand_intake_engine import UniversalBrandIntakeEngine
from core.engines.universal_brand_intake_loader import UniversalBrandIntakeLoader
from core.notifications.telegram_notifier import TelegramNotifier


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Universal Brand Intake — Alysha 100% brand context source of truth."
    )
    parser.add_argument("--brand-id", required=True, help="Brand ID from config/brands/brand_registry.json")
    parser.add_argument("--input-xlsx", default=None, help="Optional local Excel intake workbook path.")
    parser.add_argument("--worksheet-name", default=None, help="Optional worksheet override.")
    parser.add_argument("--gsheet-url", default=None, help="Optional Google Sheet URL override.")
    parser.add_argument("--dry-run", action="store_true", help="Validate/load intake and save raw+normalized files without Claude generation.")
    parser.add_argument("--max-fetch-pages", type=int, default=6, help="Maximum direct public pages/source URLs to fetch.")
    return parser


def run_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    loader = UniversalBrandIntakeLoader(
        brand_id=args.brand_id,
        excel_path=args.input_xlsx,
        worksheet_name=args.worksheet_name,
        gsheet_url=args.gsheet_url,
    )
    engine = UniversalBrandIntakeEngine(
        brand_id=args.brand_id,
        loader=loader,
    )
    return engine.run(dry_run=args.dry_run, max_fetch_pages=args.max_fetch_pages)


def _safe_notify(notifier: TelegramNotifier, message: str) -> None:
    """Send Telegram notification without breaking the intake job if Telegram fails."""
    try:
        notifier.send(message)
    except Exception:
        # Telegram must never make the core brand intake job fail.
        pass


def _success_message(args: argparse.Namespace, result: Dict[str, Any]) -> str:
    validation = result.get("validation") or {}
    fetched = result.get("fetched_sources") or {}
    compliance = result.get("alysha_compliance") or {}
    status_label = "validated (dry-run)" if args.dry_run else "completed"
    lines = [
        f"✅ Universal Brand Intake {status_label}",
        f"Brand: {args.brand_id}",
        f"Validation: {validation.get('status', 'unknown')} ({validation.get('required_fields_filled', '?')}/{validation.get('required_fields_total', '?')} required fields)",
        f"Source fetch: {fetched.get('status', 'unknown')}",
    ]
    if not args.dry_run:
        lines.append(f"Alysha compliance: {compliance.get('status', 'unknown')}")
    return "\n".join(lines)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    notifier = TelegramNotifier()
    mode = "dry-run validation" if args.dry_run else "full generation"
    _safe_notify(
        notifier,
        f"🚀 Universal Brand Intake started\nBrand: {args.brand_id}\nMode: {mode}",
    )
    try:
        result = run_from_args(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        _safe_notify(notifier, _success_message(args, result))
    except Exception as exc:
        print(traceback.format_exc())
        print(json.dumps({
            "status": "error",
            "brand_id": args.brand_id,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        _safe_notify(
            notifier,
            f"❌ Universal Brand Intake failed\nBrand: {args.brand_id}\nError: {exc}",
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
