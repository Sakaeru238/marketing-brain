import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config.paths import BASE_DIR, GLOBAL_CONFIG_DIR
from core.services.brand_context_resolver import BrandContextResolver
from core.services.brand_learning_store import BrandLearningStore
from core.services.brand_registry_service import BrandRegistryService


class BrandLearningSummaryService:
    """Build a compact brand-level learning summary from append-only JSONL memory.

    This is intentionally deterministic for the first implementation:
    - load active records
    - group by category
    - keep recent/high-confidence items
    - expose context-update candidates separately

    A future AI synthesis layer can consume the same summary input without changing
    the storage contract.
    """

    DEFAULT_SETTINGS = {
        "schema_version": "1.0",
        "max_items_per_category": 10,
        "max_total_items": 60,
        "prefer_high_confidence": True,
        "auto_queue_context_candidates": True,
    }

    CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

    def __init__(
        self,
        *,
        brand_id: str,
        resolver: Optional[BrandContextResolver] = None,
        store: Optional[BrandLearningStore] = None,
        registry_service: Optional[BrandRegistryService] = None,
    ):
        self.brand_id = str(brand_id or "").strip()
        if not self.brand_id:
            raise ValueError("brand_id is required")
        self.resolver = resolver or BrandContextResolver(registry_service)
        self.paths = self.resolver.resolve(self.brand_id)
        self.store = store or BrandLearningStore(brand_id=self.brand_id, resolver=self.resolver)
        self.settings = self._load_settings()

    def rebuild_summary(self) -> Dict[str, Any]:
        active = self.store.load_active()
        sorted_rows = sorted(active, key=self._sort_key, reverse=True)
        capped_rows = sorted_rows[: self.settings["max_total_items"]]

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        context_candidates: List[Dict[str, Any]] = []
        for row in capped_rows:
            category = str(row.get("learning_category") or "general").strip() or "general"
            grouped.setdefault(category, [])
            if len(grouped[category]) < self.settings["max_items_per_category"]:
                grouped[category].append(self._summary_item(row))
            if bool(row.get("context_update_candidate")):
                context_candidates.append(self._candidate_item(row))
                if self.settings.get("auto_queue_context_candidates", True):
                    self.store.queue_context_update_candidate(row)

        summary = {
            "schema_version": "1.0",
            "brand_id": self.brand_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_log_file": str(self.paths["brand_learning_log_file"]),
            "summary_settings": self.settings,
            "stats": {
                "total_records": len(self.store.load_all()),
                "active_records": len(active),
                "summarized_records": sum(len(items) for items in grouped.values()),
                "categories": len(grouped),
                "context_update_candidates": len(context_candidates),
            },
            "active_learnings": grouped,
            "context_update_candidates": context_candidates,
            "usage_guidance": [
                "Downstream strategy layers may read this summary as recent verified operating knowledge.",
                "The Brand Context Source of Truth should not be overwritten automatically from this file.",
                "Use learning_review_queue.json to review which learnings deserve a context update proposal.",
            ],
        }
        self._write_json(Path(self.paths["brand_learning_summary_file"]), summary)
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _summary_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "learning_id": row.get("learning_id"),
            "source_type": row.get("source_type"),
            "source_ref": row.get("source_ref") or {},
            "learning_scope": row.get("learning_scope") or "brand",
            "learning": row.get("learning") or "",
            "confidence": row.get("confidence") or "medium",
            "evidence": row.get("evidence") or [],
            "recommended_action": row.get("recommended_action") or "",
            "created_at": row.get("created_at"),
        }

    def _candidate_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "learning_id": row.get("learning_id"),
            "learning_category": row.get("learning_category") or "general",
            "learning": row.get("learning") or "",
            "confidence": row.get("confidence") or "medium",
            "evidence": row.get("evidence") or [],
            "recommended_action": row.get("recommended_action") or "",
        }

    def _sort_key(self, row: Dict[str, Any]):
        confidence = str(row.get("confidence") or "medium").strip().lower()
        confidence_rank = self.CONFIDENCE_RANK.get(confidence, 2)
        created_at = str(row.get("created_at") or "")
        if self.settings.get("prefer_high_confidence", True):
            return (confidence_rank, created_at)
        return (created_at, confidence_rank)

    def _load_settings(self) -> Dict[str, Any]:
        settings = dict(self.DEFAULT_SETTINGS)

        global_file = GLOBAL_CONFIG_DIR / "brand_learning_defaults.json"
        if global_file.exists():
            settings.update(self._read_settings_file(global_file))

        brand_file = Path(self.paths["brand_config_root"]) / "learning" / "brand_learning_settings.json"
        if brand_file.exists():
            settings.update(self._read_settings_file(brand_file))

        settings["max_items_per_category"] = max(1, int(settings.get("max_items_per_category", 10)))
        settings["max_total_items"] = max(1, int(settings.get("max_total_items", 60)))
        settings["prefer_high_confidence"] = bool(settings.get("prefer_high_confidence", True))
        settings["auto_queue_context_candidates"] = bool(settings.get("auto_queue_context_candidates", True))
        return settings

    def _read_settings_file(self, path: Path) -> Dict[str, Any]:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in learning settings: {path}")
        return data

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
