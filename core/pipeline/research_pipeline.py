import json
import re
from datetime import datetime
from pathlib import Path

from core.research.competitor_intelligence_engine import CompetitorIntelligenceEngine
from core.research.competitor_registry import CompetitorRegistry
from core.research.competitor_verifier import CompetitorVerifier
from core.research.competitor_signal_collector import CompetitorSignalCollector
from core.config.paths import (
    MANUAL_OVERRIDES_DIR,
    RESEARCH_RAW_DIR,
    RESEARCH_NORMALIZED_DIR,
    RESEARCH_CONTEXT_DIR,
    RESEARCH_PROMPTS_DIR,
    WEBSITE_CONTEXT_DIR,
)


class ResearchPipeline:
    def __init__(self):
        self.manual_overrides_dir = Path(MANUAL_OVERRIDES_DIR)
        self.research_raw_dir = Path(RESEARCH_RAW_DIR)
        self.research_normalized_dir = Path(RESEARCH_NORMALIZED_DIR)
        self.research_context_dir = Path(RESEARCH_CONTEXT_DIR)
        self.research_prompts_dir = Path(RESEARCH_PROMPTS_DIR)

        self.competitor_intelligence_engine = CompetitorIntelligenceEngine()
        self.competitor_registry = CompetitorRegistry()
        self.competitor_verifier = CompetitorVerifier()
        self.competitor_signal_collector = CompetitorSignalCollector()

        self.prompt_files = {
            "run_claude_research_core": "research_core_prompt.txt",
            "run_claude_research_messaging": "research_messaging_prompt.txt",
            "run_claude_research_market": "research_market_prompt.txt",
        }

        self.static_competitor_registry_path = Path(
            "data/knowledge/competitor_registry/competitor_registry.json"
        )
        self.competitor_signals_path = Path(
            "data/knowledge/competitor_signals/competitor_signals.json"
        )

    # =========================
    # CORE PARSER
    # =========================
    def _try_parse_json_response(self, raw_text):
        if not raw_text:
            return None, "Empty response"

        try:
            return json.loads(raw_text), None
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", raw_text)
        if not match:
            return None, "No JSON found"

        candidate = match.group()

        try:
            return json.loads(candidate), None
        except Exception as e:
            return None, str(e)

    # =========================
    # NORMALIZE RESPONSE
    # =========================
    def _normalize_claude_response(self, result):
        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            for k in ["response", "content", "text", "result", "response_text"]:
                value = result.get(k)
                if value:
                    return value

        if hasattr(result, "content"):
            try:
                return "\n".join([b.text for b in result.content if hasattr(b, "text")])
            except Exception:
                pass

        return str(result)

    # =========================
    # SAFE READ JSON
    # =========================
    def _read_json_if_exists(self, path, default):
        path = Path(path)

        if not path.exists():
            return default

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    # =========================
    # BUILD INPUT BUNDLE
    # =========================
    def _build_input_bundle(self, _id=None, brand_intake=None, manual_overrides=None):
        """
        Build the same kind of input bundle used by prompt tests,
        but now as production logic.

        This keeps test flow and production flow aligned.
        """

        brand_intake = brand_intake or {}
        manual_overrides = manual_overrides or {}

        brand = brand_intake.get("brand", {}) or {}
        product = brand_intake.get("product", {}) or {}
        offer = brand_intake.get("offer", {}) or {}
        audience_core = brand_intake.get("audience_core", {}) or {}

        # Some exported brand_intake JSON stores nested audience records.
        if isinstance(audience_core.get("ai_expanded_audience"), dict):
            ai_audience = audience_core.get("ai_expanded_audience") or {}
            audience_name = audience_core.get("audience_name") or ai_audience.get(
                "audience_name"
            )
            pain_point = audience_core.get("pain_point") or ai_audience.get(
                "pain_point"
            )
            desired_outcome = audience_core.get("desired_outcome") or ai_audience.get(
                "desired_outcome"
            )
        else:
            audience_name = audience_core.get("audience_name")
            pain_point = audience_core.get("pain_point")
            desired_outcome = audience_core.get("desired_outcome")

        competitor_signals = self._read_json_if_exists(
            self.competitor_signals_path,
            default=[],
        )

        static_competitor_registry = self._read_json_if_exists(
            self.static_competitor_registry_path,
            default=[],
        )

        brand_filter = {
            "brand_name": brand.get("brand_name"),
            "brand_positioning": brand.get("brand_positioning"),
            "brand_type": brand.get("brand_type"),
            "origin": brand.get("origin"),
            "product_name": product.get("product_name"),
            "product_type": product.get("product_type"),
            "format": product.get("format"),
            "pack_size": product.get("pack_size"),
            "offer_text": offer.get("offer_text"),
            "selling_orientation": brand_intake.get("selling_orientation", []),
            "occasion": brand_intake.get("occasion", []),
            "audience_core": {
                "audience_name": audience_name,
                "pain_point": pain_point,
                "desired_outcome": desired_outcome,
            },
            "core_truth": brand_intake.get("core_truth", []),
            "guardrails": brand_intake.get("guardrails", []),
            "product_benefits": brand_intake.get("product_benefits", []),
            "product_usage": brand_intake.get("product_usage", []),
        }

        research_direction = {
            "selling_orientation": brand_intake.get("selling_orientation", []),
            "occasion": brand_intake.get("occasion", []),
            "focus_terms": [
                f"selling_orientation:{x}"
                for x in (brand_intake.get("selling_orientation", []) or [])
            ]
            + [f"occasion:{x}" for x in (brand_intake.get("occasion", []) or [])],
            "research_instruction": (
                "Prioritize competitor ads, hooks, angles, emotional triggers, "
                "positioning, product proof, and patterns useful for immediate ad writing."
            ),
        }

        return {
            "run_id": _id,
            "brand_filter": brand_filter,
            "research_direction": research_direction,
            "seed_competitors": static_competitor_registry,
            "existing_competitor_signals": competitor_signals,
            "website_context": {"status": "skipped", "sources": [], "pages": {}},
            "manual_overrides": manual_overrides,
        }

    # =========================
    # BUILD PROMPT FROM TEMPLATE
    # =========================
    def _build_prompt(
        self, prompt_key, _id=None, brand_intake=None, manual_overrides=None
    ):
        """
        Production prompt renderer.

        Prompt files stay outside code.
        This function only:
        - resolves prompt key to prompt file
        - reads the .txt template
        - injects runtime data into placeholders
        """

        prompt_filename = self.prompt_files.get(prompt_key)

        if not prompt_filename:
            raise ValueError(f"Unknown research prompt key: {prompt_key}")

        prompt_path = self.research_prompts_dir / prompt_filename

        if not prompt_path.exists():
            raise FileNotFoundError(f"Research prompt file not found: {prompt_path}")

        template = prompt_path.read_text(encoding="utf-8")

        input_bundle = self._build_input_bundle(
            _id=_id,
            brand_intake=brand_intake,
            manual_overrides=manual_overrides,
        )

        prompt = template.replace("{{RUN_ID}}", str(_id or ""))
        prompt = prompt.replace(
            "{{INPUT_BUNDLE}}",
            json.dumps(input_bundle, ensure_ascii=False, indent=2),
        )

        return prompt

    # =========================
    # RUN MARKET RESEARCH
    # =========================
    def _run_claude_research_market(self, _id, brand_intake, claude_api_adapter):
        prompt = self._build_prompt(
            "run_claude_research_market",
            _id=_id,
            brand_intake=brand_intake,
        )

        api_result = claude_api_adapter.run(prompt=prompt)

        raw_text = self._normalize_claude_response(api_result)

        print("\n================ CLAUDE RAW RESEARCH ================")
        print(raw_text[:2000])
        print("=====================================================\n")

        parsed, error = self._try_parse_json_response(raw_text)

        return {
            "status": "success" if parsed else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed,
            "parse_error": error,
        }

    # =========================
    # MAIN RUN
    # =========================
    def run(
        self,
        _id=None,
        brand_intake=None,
        claude_mode="off",
        claude_api_adapter=None,
    ):
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "competitor_findings": [],
            "ad_findings": [],
            "sources": [],
            "hooks": [],
            "claims": [],
        }

        if claude_mode == "api" and claude_api_adapter:
            result = self._run_claude_research_market(
                _id=_id,
                brand_intake=brand_intake,
                claude_api_adapter=claude_api_adapter,
            )

            data["claude_research_market"] = result

            parsed = result.get("parsed") or {}

            data["competitor_findings"] = parsed.get("competitor_findings", [])
            data["ad_findings"] = parsed.get("ad_findings", [])
            data["sources"] = parsed.get("sources", [])

            # Optional compatibility fields
            for ad in data["ad_findings"]:
                if isinstance(ad, dict):
                    hook = ad.get("hook") or ad.get("ad_expression")
                    if hook:
                        data["hooks"].append(hook)

                    claim = ad.get("claim") or ad.get("proof_point")
                    if claim:
                        data["claims"].append(claim)

        return {
            "stage": "research",
            "status": "ready",
            "data": data,
        }
