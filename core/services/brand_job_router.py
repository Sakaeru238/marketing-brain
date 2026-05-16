from typing import Any, Dict, List, Optional

from core.services.brand_context_resolver import BrandContextResolver
from core.services.brand_registry_service import BrandRegistryService


class BrandJobRouter:
    """Select brands for a module/job and attach resolved paths.

    This service is intentionally lightweight so daily jobs can adopt it without
    changing their business logic all at once.
    """

    def __init__(self, registry_service: BrandRegistryService | None = None, resolver: BrandContextResolver | None = None):
        self.registry_service = registry_service or BrandRegistryService()
        self.resolver = resolver or BrandContextResolver(self.registry_service)

    def resolve_targets(self, *, module_name: str, brand_id: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        if brand_id:
            brand = self.registry_service.get_brand(brand_id)
            if active_only and not self.registry_service.is_active(brand):
                return []
            if not self.registry_service.module_enabled(brand, module_name):
                return []
            return [self._attach_paths(brand)]

        brands = self.registry_service.list_brands_for_module(module_name, active_only=active_only)
        return [self._attach_paths(brand) for brand in brands]

    def _attach_paths(self, brand: Dict[str, Any]) -> Dict[str, Any]:
        brand_id = str(brand.get("brand_id") or "").strip()
        if not brand_id:
            raise ValueError("Registry brand entry is missing brand_id")
        return {
            "brand_id": brand_id,
            "brand": brand,
            "paths": self.resolver.resolve(brand_id),
        }
