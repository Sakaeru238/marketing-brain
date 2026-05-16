import json
from pathlib import Path

from core.config.paths import RESEARCH_PROMPTS_DIR
from core.config.research_config import (
    COMPETITOR_LAYERS,
    DEFAULT_TARGET_MARKETS,
    MAX_COMPETITORS,
)


class CompetitorEngine:
    def __init__(self):
        self.research_prompts_dir = Path(RESEARCH_PROMPTS_DIR)

        # Prompt mapping:
        # logical key -> prompt file
        self.prompt_files = {
            "discover_competitors": "discover_competitors_prompt.txt",
        }

    # ---------------------------------------------------
    # Prompt helpers
    # ---------------------------------------------------
    def _get_prompt_file_path(self, prompt_key):
        file_name = self.prompt_files.get(prompt_key)
        if not file_name:
            raise ValueError(f"Unknown prompt key: {prompt_key}")
        return self.research_prompts_dir / file_name

    def _load_prompt_template(self, prompt_key):
        path = self._get_prompt_file_path(prompt_key)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _render_prompt(self, prompt_key, variables):
        template = self._load_prompt_template(prompt_key)
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered

    # ---------------------------------------------------
    # Claude output helpers
    # ---------------------------------------------------
    def _normalize_claude_response(self, api_result):
        if api_result is None:
            return None

        if isinstance(api_result, str):
            return api_result

        if isinstance(api_result, dict):
            for key in ["response_text", "response", "content", "result", "text"]:
                value = api_result.get(key)
                if value:
                    return value

        if hasattr(api_result, "content"):
            try:
                blocks = getattr(api_result, "content", [])
                texts = []
                for block in blocks:
                    text = getattr(block, "text", None)
                    if text:
                        texts.append(text)
                if texts:
                    return "\n".join(texts)
            except Exception:
                pass

        return str(api_result)

    def _extract_json_block(self, text):
        if not text:
            return None

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return None

    # ---------------------------------------------------
    # Input bundle
    # ---------------------------------------------------
    def _build_bundle(self, brand_intake, research_data=None):
        """
        Build a compact bundle for competitor discovery.
        We keep it focused so Claude reasons about realistic competitor layers.
        """
        brand = (brand_intake or {}).get("brand", {}) or {}
        product = (brand_intake or {}).get("product", {}) or {}
        audience_core = (brand_intake or {}).get("audience_core", {}) or {}
        website_context = (brand_intake or {}).get("website_context", {}) or {}

        return {
            "brand_name": brand.get("brand_name"),
            "website": brand.get("website"),
            "brand_positioning": brand.get("brand_positioning"),
            "brand_type": brand.get("brand_type"),
            "origin": brand.get("origin"),
            "target_markets": DEFAULT_TARGET_MARKETS,
            "product_name": product.get("product_name"),
            "product_type": product.get("product_type"),
            "format": product.get("format"),
            "price": product.get("list_price_usd"),
            "audience_core": audience_core,
            "core_truth": (brand_intake or {}).get("core_truth", []) or [],
            "guardrails": (brand_intake or {}).get("guardrails", []) or [],
            "message_pillars": (brand_intake or {}).get("message_pillars", []) or [],
            "creative_angles": (brand_intake or {}).get("creative_angles", []) or [],
            "website_sources": website_context.get("sources", []),
            "website_status": website_context.get("status"),
            "research_summary": (research_data or {}).get("research_summary", {}),
            "competitor_layers": COMPETITOR_LAYERS,
        }

    # ---------------------------------------------------
    # Main discovery
    # ---------------------------------------------------
    def discover_competitors(
        self,
        brand_intake,
        research_data,
        claude_api_adapter,
    ):
        """
        Discover competitor set using Claude.
        This version is Claude-first.
        Later we can enrich with Apify without changing this interface.
        """
        bundle = self._build_bundle(
            brand_intake=brand_intake,
            research_data=research_data,
        )

        prompt = self._render_prompt(
            "discover_competitors",
            {
                "INPUT_BUNDLE": json.dumps(bundle, ensure_ascii=False, indent=2),
                "MAX_COMPETITORS": MAX_COMPETITORS,
            },
        )

        api_result = claude_api_adapter.run(prompt=prompt)
        raw_text = self._normalize_claude_response(api_result)

        parsed = None
        json_block = self._extract_json_block(raw_text)
        if json_block:
            try:
                parsed = json.loads(json_block)
            except Exception:
                parsed = None

        return {
            "status": "success" if parsed else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed,
            "prompt_key": "discover_competitors",
            "prompt_file": str(self._get_prompt_file_path("discover_competitors")),
        }
