from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.config.paths import BRANDS_DATA_DIR
from core.services.pod_pipeline_utils import read_json, utc_now, write_json


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PodLLMOutputCache:
    def __init__(self, *, brand_id: str, namespace: str, data_root: str | Path | None = None) -> None:
        self.brand_id = brand_id
        root = Path(data_root) / "brands" if data_root else BRANDS_DATA_DIR
        self.cache_dir = root / brand_id / "cache" / "llm" / namespace

    def input_hash(self, payload: dict[str, Any]) -> str:
        return stable_hash(payload)

    def path_for(self, input_hash: str) -> Path:
        return self.cache_dir / f"{input_hash}.json"

    def get(self, input_hash: str) -> dict[str, Any] | None:
        path = self.path_for(input_hash)
        if not path.exists():
            return None
        cached = read_json(path)
        if not isinstance(cached, dict):
            return None
        cached["cache_status"] = "hit"
        cached["cache_file"] = str(path)
        return cached

    def set(
        self,
        *,
        input_hash: str,
        output: dict[str, Any],
        api_meta: dict[str, Any],
        cache_input: dict[str, Any],
    ) -> Path:
        path = self.path_for(input_hash)
        payload = {
            "cache_status": "stored",
            "created_at": utc_now(),
            "brand_id": self.brand_id,
            "namespace": self.cache_dir.name,
            "input_hash": input_hash,
            "cache_input": cache_input,
            "output": output,
            "api_meta": api_meta,
        }
        return write_json(path, payload)

