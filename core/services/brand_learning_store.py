import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.services.brand_context_resolver import BrandContextResolver


class BrandLearningStore:
    """Append-only brand learning store.

    This store intentionally keeps the learning log separate from the Brand Context
    Source of Truth. New operational evidence is appended to JSONL, then a separate
    synthesis/review process decides whether it should influence a future context
    update.
    """

    VALID_CONFIDENCE = {"low", "medium", "high"}
    VALID_STATUS = {"active", "deprecated", "rejected", "superseded"}
    DEFAULT_SCOPE = "brand"
    DEFAULT_CATEGORY = "general"

    def __init__(self, *, brand_id: str, resolver: Optional[BrandContextResolver] = None):
        self.brand_id = str(brand_id or "").strip()
        if not self.brand_id:
            raise ValueError("brand_id is required")
        self.resolver = resolver or BrandContextResolver()
        self.paths = self.resolver.resolve(self.brand_id)
        self.log_file = Path(self.paths["brand_learning_log_file"])
        self.review_queue_file = Path(self.paths["learning_review_queue_file"])
        self.context_update_history_file = Path(self.paths["context_update_history_file"])
        self._ensure_support_files()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def append_learning(
        self,
        *,
        source_type: str,
        learning: str,
        learning_category: str = DEFAULT_CATEGORY,
        confidence: str = "medium",
        recommended_action: str = "",
        evidence: Optional[Iterable[str]] = None,
        source_ref: Optional[Dict[str, Any]] = None,
        learning_scope: str = DEFAULT_SCOPE,
        status: str = "active",
        context_update_candidate: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        learning_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        cleaned_learning = str(learning or "").strip()
        cleaned_source_type = str(source_type or "").strip()
        if not cleaned_source_type:
            raise ValueError("source_type is required")
        if not cleaned_learning:
            raise ValueError("learning is required")

        confidence_value = self._clean_confidence(confidence)
        status_value = self._clean_status(status)
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "learning_id": learning_id or self._new_learning_id(),
            "brand_id": self.brand_id,
            "source_type": cleaned_source_type,
            "source_ref": source_ref or {},
            "learning_scope": str(learning_scope or self.DEFAULT_SCOPE).strip() or self.DEFAULT_SCOPE,
            "learning_category": str(learning_category or self.DEFAULT_CATEGORY).strip() or self.DEFAULT_CATEGORY,
            "learning": cleaned_learning,
            "confidence": confidence_value,
            "evidence": [str(item).strip() for item in (evidence or []) if str(item).strip()],
            "recommended_action": str(recommended_action or "").strip(),
            "status": status_value,
            "context_update_candidate": bool(context_update_candidate),
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        self._append_jsonl(record)
        if record["context_update_candidate"]:
            self.queue_context_update_candidate(record)
        return record

    def load_all(self) -> List[Dict[str, Any]]:
        if not self.log_file.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line_number, line in enumerate(self.log_file.read_text(encoding="utf-8").splitlines(), start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception as exc:
                raise ValueError(f"Invalid JSONL in {self.log_file} at line {line_number}: {exc}") from exc
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    def load_active(self) -> List[Dict[str, Any]]:
        return [row for row in self.load_all() if str(row.get("status") or "active") == "active"]

    def queue_context_update_candidate(self, learning_record: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._read_json(
            self.review_queue_file,
            default={
                "brand_id": self.brand_id,
                "updated_at": None,
                "pending_context_updates": [],
                "reviewed_context_updates": [],
            },
        )
        pending = list(queue.get("pending_context_updates") or [])
        learning_id = str(learning_record.get("learning_id") or "").strip()
        if not learning_id:
            raise ValueError("learning_record is missing learning_id")

        existing = next(
            (
                item
                for item in pending
                if str(item.get("learning_id") or "").strip() == learning_id
            ),
            None,
        )
        if existing:
            return existing

        proposal = {
            "proposal_id": f"CTX_{uuid.uuid4().hex[:12].upper()}",
            "brand_id": self.brand_id,
            "learning_id": learning_id,
            "proposed_update_area": self._suggest_context_area(str(learning_record.get("learning_category") or "")),
            "reason": str(learning_record.get("learning") or "").strip(),
            "evidence": list(learning_record.get("evidence") or []),
            "recommended_action": str(learning_record.get("recommended_action") or "").strip(),
            "confidence": str(learning_record.get("confidence") or "medium"),
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        pending.append(proposal)
        queue["pending_context_updates"] = pending
        queue["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.review_queue_file, queue)
        return proposal

    def ensure_context_update_history(self) -> Dict[str, Any]:
        return self._read_json(
            self.context_update_history_file,
            default={
                "brand_id": self.brand_id,
                "updated_at": None,
                "history": [],
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _new_learning_id(self) -> str:
        return f"BL_{self.brand_id}_{uuid.uuid4().hex[:12].upper()}"

    def _append_jsonl(self, payload: Dict[str, Any]) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _clean_confidence(self, confidence: str) -> str:
        value = str(confidence or "medium").strip().lower()
        return value if value in self.VALID_CONFIDENCE else "medium"

    def _clean_status(self, status: str) -> str:
        value = str(status or "active").strip().lower()
        return value if value in self.VALID_STATUS else "active"

    def _ensure_support_files(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.review_queue_file.exists():
            self._write_json(
                self.review_queue_file,
                {
                    "brand_id": self.brand_id,
                    "updated_at": None,
                    "pending_context_updates": [],
                    "reviewed_context_updates": [],
                },
            )
        if not self.context_update_history_file.exists():
            self._write_json(
                self.context_update_history_file,
                {
                    "brand_id": self.brand_id,
                    "updated_at": None,
                    "history": [],
                },
            )

    def _read_json(self, path: Path, *, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            self._write_json(path, default)
            return dict(default)
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            self._write_json(path, default)
            return dict(default)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in {path}")
        return data

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _suggest_context_area(self, category: str) -> str:
        normalized = str(category or "").strip().lower()
        mapping = {
            "audience": "Brand Context > Core Audience(s)",
            "competitive": "Brand Context > Competitor Landscape",
            "competitors": "Brand Context > Competitor Landscape",
            "product": "Brand Context > Product Catalog / What Makes Them Different",
            "product_truth": "Brand Context > What Makes Them Different",
            "brand_voice": "Brand Context > Brand Voice & Tone",
            "creative_constraints": "Brand Context > Creative Constraints",
            "strategic_context": "Brand Context > Must-Know Strategic Context",
            "visual_design": "Brand Context > Must-Know Strategic Context",
        }
        return mapping.get(normalized, "Brand Context > Review Needed")
