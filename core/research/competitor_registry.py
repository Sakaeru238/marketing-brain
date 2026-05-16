import json
from datetime import datetime
from pathlib import Path

from core.config.paths import COMPETITOR_REGISTRY_DIR


class CompetitorRegistry:
    """
    Registry for competitor candidates and verification status.

    Priority logic:
    1. confirmed -> always use
    2. rejected -> never use
    3. pending -> use based on auto_trust_level / score
    """

    def __init__(self):
        self.registry_dir = Path(COMPETITOR_REGISTRY_DIR)

    def _registry_path(self, _id):
        return self.registry_dir / f"{_id}_competitor_registry.json"

    def load_registry(self, _id):
        path = self._registry_path(_id)
        if not path.exists():
            return {
                "_id": _id,
                "updated_at": datetime.utcnow().isoformat(),
                "items": [],
            }

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "_id": _id,
                "updated_at": datetime.utcnow().isoformat(),
                "items": [],
            }

    def save_registry(self, _id, payload):
        path = self._registry_path(_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def _make_key(self, item):
        brand = (item.get("brand_name") or "").strip().lower()
        product = (item.get("product_name") or "").strip().lower()
        link = (item.get("product_link") or "").strip().lower()
        return f"{brand}||{product}||{link}"

    def upsert_candidates(self, _id, candidates):
        registry = self.load_registry(_id)
        items = registry.get("items", [])
        existing_map = {self._make_key(item): item for item in items}

        for cand in candidates or []:
            key = self._make_key(cand)
            old = existing_map.get(key, {})

            merged = {
                "brand_name": cand.get("brand_name", old.get("brand_name", "")),
                "product_name": cand.get("product_name", old.get("product_name", "")),
                "product_type": cand.get("product_type", old.get("product_type", "")),
                "product_link": cand.get("product_link", old.get("product_link", "")),
                "price_range": cand.get("price_range", old.get("price_range", "")),
                "reason": cand.get("reason", old.get("reason", "")),
                "confirm_status": old.get("confirm_status", "pending"),
                "confirmed_by": old.get("confirmed_by", ""),
                "confirmed_at": old.get("confirmed_at", ""),
                "notes": old.get("notes", ""),
                "auto_trust_level": old.get("auto_trust_level", "low"),
                "auto_trust_score": old.get("auto_trust_score", 0.0),
                "validation_flags": old.get("validation_flags", {}),
                "website_link": old.get("website_link", ""),
                "amazon_link": old.get("amazon_link", ""),
                "facebook_link": old.get("facebook_link", ""),
                "instagram_link": old.get("instagram_link", ""),
                "tiktok_link": old.get("tiktok_link", ""),
                "source_group": cand.get("source_group", old.get("source_group", "")),
            }

            existing_map[key] = merged

        registry["items"] = list(existing_map.values())
        registry["updated_at"] = datetime.utcnow().isoformat()
        self.save_registry(_id, registry)
        return registry

    def get_accepted_items(self, _id):
        registry = self.load_registry(_id)
        accepted = []

        for item in registry.get("items", []):
            status = item.get("confirm_status", "pending")
            trust = item.get("auto_trust_level", "low")

            if status == "confirmed":
                accepted.append(item)
            elif status == "rejected":
                continue
            elif status == "pending" and trust == "high":
                accepted.append(item)

        return accepted