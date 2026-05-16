from pathlib import Path
from typing import Any, Dict

from core.config.paths import BASE_DIR, BRANDS_DATA_DIR, BRANDS_CONFIG_DIR
from core.services.brand_registry_service import BrandRegistryService


class BrandContextResolver:
    """Resolve canonical brand-centric folders and files for a brand."""

    def __init__(self, registry_service: BrandRegistryService | None = None):
        self.registry_service = registry_service or BrandRegistryService()

    def resolve(self, brand_id: str, *, ensure_dirs: bool = True) -> Dict[str, Any]:
        brand = self.registry_service.get_brand(brand_id)
        brand_data_root = self._resolve_root(brand.get("brand_root"), BRANDS_DATA_DIR / brand_id)
        brand_config_root = self._resolve_root(brand.get("config_root"), BRANDS_CONFIG_DIR / brand_id)

        brand_context_root = brand_data_root / "brand_context"
        intake_root = brand_context_root / "intake"
        alysha_root = brand_context_root / "alysha"
        alysha_history_root = alysha_root / "history"
        learning_root = brand_context_root / "learning"

        organic_root = brand_data_root / "organic"
        paid_ads_root = brand_data_root / "paid_ads"
        pod_root = brand_data_root / "pod"

        paths = {
            "brand_id": brand_id,
            "brand": brand,
            "brand_data_root": brand_data_root,
            "brand_config_root": brand_config_root,
            "brand_context_root": brand_context_root,
            "intake_root": intake_root,
            "alysha_root": alysha_root,
            "alysha_history_root": alysha_history_root,
            "learning_root": learning_root,
            "organic_root": organic_root,
            "paid_ads_root": paid_ads_root,
            "pod_root": pod_root,
            "brand_intake_raw_file": intake_root / "brand_intake_raw.json",
            "brand_intake_normalized_file": intake_root / "brand_intake_normalized.json",
            "brand_context_markdown_file": alysha_root / "brand_context_source_of_truth.md",
            "brand_context_json_file": alysha_root / "brand_context_source_of_truth.json",
            "brand_research_notes_file": alysha_root / "brand_research_notes.json",
            "brand_intake_run_file": alysha_root / "brand_intake_run.json",
            "brand_learning_log_file": learning_root / "brand_learning_log.jsonl",
            "brand_learning_summary_file": learning_root / "brand_learning_summary.json",
            "learning_review_queue_file": learning_root / "learning_review_queue.json",
            "context_update_history_file": learning_root / "context_update_history.json",
        }

        if ensure_dirs:
            for key in [
                "brand_data_root",
                "brand_config_root",
                "brand_context_root",
                "intake_root",
                "alysha_root",
                "alysha_history_root",
                "learning_root",
                "organic_root",
                "paid_ads_root",
                "pod_root",
            ]:
                Path(paths[key]).mkdir(parents=True, exist_ok=True)

        return paths

    def _resolve_root(self, configured, fallback: Path) -> Path:
        if configured:
            path = Path(str(configured))
            return path if path.is_absolute() else BASE_DIR / path
        return fallback
