import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config.paths import BASE_DIR, BRANDS_CONFIG_DIR


class BrandRegistryService:
    """Load and query the multi-brand registry.

    The registry is the single entry point for jobs that need to decide which
    brands are eligible for a given module. It intentionally keeps business
    routing simple: brand settings live in per-brand config folders, while this
    file is the top-level index used by routers/jobs.
    """

    def __init__(self, registry_file: Optional[str] = None):
        self.registry_file = Path(registry_file) if registry_file else BRANDS_CONFIG_DIR / "brand_registry.json"
        self._cache: Optional[Dict[str, Any]] = None

    def _load_raw(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache

        if not self.registry_file.exists():
            self._cache = {"schema_version": "1.0", "brands": []}
            return self._cache

        data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Invalid brand registry payload: {self.registry_file}")
        brands = data.get("brands") or []
        if not isinstance(brands, list):
            raise ValueError(f"brand_registry.json brands must be a list: {self.registry_file}")
        data["brands"] = brands
        self._cache = data
        return data

    def reload(self) -> Dict[str, Any]:
        self._cache = None
        return self._load_raw()

    def list_brands(self, *, active_only: bool = False) -> List[Dict[str, Any]]:
        brands = list(self._load_raw().get("brands") or [])
        if not active_only:
            return brands
        return [brand for brand in brands if self.is_active(brand)]

    def is_active(self, brand: Dict[str, Any]) -> bool:
        return str(brand.get("status") or "active").strip().lower() == "active"

    def get_brand(self, brand_id: str) -> Dict[str, Any]:
        wanted = str(brand_id or "").strip()
        if not wanted:
            raise ValueError("brand_id is required")
        for brand in self._load_raw().get("brands") or []:
            if str(brand.get("brand_id") or "").strip() == wanted:
                return brand
        raise KeyError(f"Brand not found in registry: {wanted}")

    def module_enabled(self, brand: Dict[str, Any], module_name: str) -> bool:
        modules = brand.get("enabled_modules") or {}
        if not isinstance(modules, dict):
            return False
        return bool(modules.get(module_name))

    def list_brands_for_module(self, module_name: str, *, active_only: bool = True) -> List[Dict[str, Any]]:
        brands = self.list_brands(active_only=active_only)
        return [brand for brand in brands if self.module_enabled(brand, module_name)]

    def brand_config_root(self, brand_id: str) -> Path:
        brand = self.get_brand(brand_id)
        configured = brand.get("config_root")
        if configured:
            path = Path(str(configured))
            return path if path.is_absolute() else BASE_DIR / path
        return BRANDS_CONFIG_DIR / str(brand_id)

    def brand_data_root(self, brand_id: str) -> Path:
        brand = self.get_brand(brand_id)
        configured = brand.get("brand_root")
        if configured:
            path = Path(str(configured))
            return path if path.is_absolute() else BASE_DIR / path
        from core.config.paths import BRANDS_DATA_DIR

        return BRANDS_DATA_DIR / str(brand_id)
