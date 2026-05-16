import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

from core.config.paths import (
    BRAND_INTAKE_DIR,
    BRAND_INTAKE_PROMPTS_DIR,
    WEBSITE_CONTEXT_DIR,
)
from core.engines.brand_intake_loader import BrandIntakeLoader


class BrandIntakeEngine:
    """
    Build brand-intake context từ Excel control panel.

    Output của engine này là context chuẩn hóa để dùng cho:
    - research
    - insight
    - Alysha strategy
    - Claude handoff
    """

    def __init__(self, workbook_path=None):
        self.loader = BrandIntakeLoader(workbook_path=workbook_path)
        self.brand_intake_prompts_dir = Path(BRAND_INTAKE_PROMPTS_DIR)

        # Prompt mapping:
        # logical prompt key -> file name in data/prompts/brand_intake/
        self.prompt_files = {
            "run_claude_brand_core": "brand_core_prompt.txt",
            "run_claude_brand_strategy": "brand_strategy_prompt.txt",
            "run_claude_brand_constraints": "brand_constraints_prompt.txt",
        }

    # ---------------------------------------------------
    # File save helpers
    # ---------------------------------------------------
    def _save_brand_intake_file(self, _id, brand_intake):
        """
        Save brand intake into a dedicated file for debugging and reuse.
        """
        if not _id:
            return None

        out_dir = Path(BRAND_INTAKE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{_id}_brand_intake.json"
        out_file.write_text(
            json.dumps(brand_intake, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(out_file)

    def _save_website_context_file(self, _id, website_context):
        """
        Save website context into a dedicated file for debugging and reuse.
        """
        if not _id or not website_context:
            return None

        out_dir = Path(WEBSITE_CONTEXT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{_id}_website_context.json"
        out_file.write_text(
            json.dumps(website_context, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(out_file)

    def _save_brand_stage_file(self, _id, suffix, payload):
        """
        Save each Claude brand stage output separately.
        """
        if not _id:
            return None

        out_dir = Path(BRAND_INTAKE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{_id}_{suffix}.json"
        out_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(out_file)

    # ---------------------------------------------------
    # Prompt helpers
    # ---------------------------------------------------
    def _get_prompt_file_path(self, prompt_key):
        file_name = self.prompt_files.get(prompt_key)
        if not file_name:
            raise ValueError(f"Unknown prompt key: {prompt_key}")
        return self.brand_intake_prompts_dir / file_name

    def _load_prompt_template(self, prompt_key):
        path = self._get_prompt_file_path(prompt_key)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _render_prompt(self, prompt_key, variables):
        """
        Simple variable replacement for prompt templates.
        """
        template = self._load_prompt_template(prompt_key)
        rendered = template

        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

        return rendered

    # ---------------------------------------------------
    # Data cleaning helpers
    # ---------------------------------------------------
    def _clean_list(self, values):
        cleaned = []
        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if text.lower() == "nan":
                continue
            cleaned.append(text)
        return cleaned

    def _parse_multi_value(self, value):
        if value is None:
            return []

        text = str(value).strip()
        if not text or text.lower() == "nan":
            return []

        parts = re.split(r"[,;|]", text)
        cleaned = []
        for part in parts:
            item = str(part).strip().lower()
            if not item or item == "nan":
                continue
            item = re.sub(r"[^a-z0-9]+", "_", item)
            item = re.sub(r"_+", "_", item).strip("_")
            if item and item not in cleaned:
                cleaned.append(item)
        return cleaned

    def _first_non_empty(self, *values):
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if text.lower() == "nan":
                continue
            return text
        return None

    # ---------------------------------------------------
    # Website fetch helpers
    # ---------------------------------------------------
    def _strip_html(self, html):
        if not html:
            return ""
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<noscript[\s\S]*?</noscript>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _candidate_urls(self, website):
        if not website:
            return []

        website = website.strip()
        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        candidates = [
            website,
            urljoin(website, "/about"),
            urljoin(website, "/pages/about"),
            urljoin(website, "/shop"),
            urljoin(website, "/collections/all"),
            urljoin(website, "/products"),
            urljoin(website, "/faq"),
        ]

        deduped = []
        seen = set()
        for url in candidates:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def _fetch_website_context(self, website, max_pages=4):
        """
        Fetch public website text excerpts for brand intake.
        """
        if not website:
            return {
                "status": "skipped",
                "reason": "No website provided.",
                "sources": [],
                "pages": {},
            }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            )
        }

        pages = {}
        sources = []

        for url in self._candidate_urls(website):
            if len(sources) >= max_pages:
                break

            try:
                response = requests.get(url, headers=headers, timeout=12)
                if response.status_code >= 400:
                    continue

                text = self._strip_html(response.text)
                if not text:
                    continue

                text = text[:5000]
                pages[url] = text
                sources.append(url)

            except Exception:
                continue

        if not sources:
            return {
                "status": "failed",
                "reason": "Could not fetch public website pages.",
                "sources": [],
                "pages": {},
            }

        return {
            "status": "success",
            "reason": None,
            "sources": sources,
            "pages": pages,
        }

    # ---------------------------------------------------
    # Claude response helpers
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
        """
        Extract the most likely JSON object from a Claude response.

        Supports:
        - plain JSON
        - fenced ```json ... ```
        - extra commentary before/after JSON
        """
        if not text:
            return None

        text = text.strip()

        fenced = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            text,
            flags=re.IGNORECASE,
        )
        if fenced:
            candidate = fenced.group(1).strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate
            text = candidate

        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return text[start:]

    def _repair_json_candidate(self, candidate):
        """
        Try lightweight repair for truncated JSON object.
        Only balances missing closing braces/brackets when safe.
        """
        if not candidate:
            return None

        repaired = candidate.strip()

        brace_open = repaired.count("{")
        brace_close = repaired.count("}")
        bracket_open = repaired.count("[")
        bracket_close = repaired.count("]")

        if bracket_close < bracket_open:
            repaired += "]" * (bracket_open - bracket_close)

        if brace_close < brace_open:
            repaired += "}" * (brace_open - brace_close)

        return repaired

    def _try_parse_json_response(self, raw_text):
        """
        Try multiple strategies to parse Claude response into JSON.
        Returns:
        - parsed_json
        - parse_error
        """
        if not raw_text:
            return None, "Empty Claude response."

        candidate = self._extract_json_block(raw_text)
        if not candidate:
            return None, "Could not locate JSON object in response."

        try:
            return json.loads(candidate), None
        except Exception as e1:
            first_error = str(e1)

        repaired = self._repair_json_candidate(candidate)
        if repaired and repaired != candidate:
            try:
                return json.loads(repaired), None
            except Exception as e2:
                second_error = str(e2)
                return (
                    None,
                    f"Initial parse failed: {first_error} | Repaired parse failed: {second_error}",
                )

        return None, f"Initial parse failed: {first_error}"

    # ---------------------------------------------------
    # Claude brand intake stages
    # ---------------------------------------------------
    def _run_claude_brand_core(self, brand_intake, website_context, claude_api_adapter):
        prompt = self._render_prompt(
            "run_claude_brand_core",
            {
                "SEED_BRAND_DATA": json.dumps(
                    brand_intake, ensure_ascii=False, indent=2
                ),
                "FETCHED_WEBSITE_EXCERPTS": json.dumps(
                    website_context, ensure_ascii=False, indent=2
                ),
            },
        )

        api_result = claude_api_adapter.run(prompt=prompt)
        raw_text = self._normalize_claude_response(api_result)
        parsed_json, parse_error = self._try_parse_json_response(raw_text)

        return {
            "status": "success" if parsed_json else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed_json,
            "parse_error": parse_error,
            "prompt_key": "run_claude_brand_core",
            "prompt_file": str(self._get_prompt_file_path("run_claude_brand_core")),
        }

    def _run_claude_brand_strategy(
        self,
        brand_intake,
        website_context,
        brand_core_output,
        claude_api_adapter,
    ):
        prompt = self._render_prompt(
            "run_claude_brand_strategy",
            {
                "SEED_BRAND_DATA": json.dumps(
                    brand_intake, ensure_ascii=False, indent=2
                ),
                "FETCHED_WEBSITE_EXCERPTS": json.dumps(
                    website_context, ensure_ascii=False, indent=2
                ),
                "BRAND_CORE_OUTPUT": json.dumps(
                    brand_core_output, ensure_ascii=False, indent=2
                ),
            },
        )

        api_result = claude_api_adapter.run(prompt=prompt)
        raw_text = self._normalize_claude_response(api_result)
        parsed_json, parse_error = self._try_parse_json_response(raw_text)

        return {
            "status": "success" if parsed_json else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed_json,
            "parse_error": parse_error,
            "prompt_key": "run_claude_brand_strategy",
            "prompt_file": str(self._get_prompt_file_path("run_claude_brand_strategy")),
        }

    def _run_claude_brand_constraints(
        self,
        brand_intake,
        website_context,
        brand_core_output,
        brand_strategy_output,
        claude_api_adapter,
    ):
        prompt = self._render_prompt(
            "run_claude_brand_constraints",
            {
                "SEED_BRAND_DATA": json.dumps(
                    brand_intake, ensure_ascii=False, indent=2
                ),
                "FETCHED_WEBSITE_EXCERPTS": json.dumps(
                    website_context, ensure_ascii=False, indent=2
                ),
                "BRAND_CORE_OUTPUT": json.dumps(
                    brand_core_output, ensure_ascii=False, indent=2
                ),
                "BRAND_STRATEGY_OUTPUT": json.dumps(
                    brand_strategy_output, ensure_ascii=False, indent=2
                ),
            },
        )

        api_result = claude_api_adapter.run(prompt=prompt)
        raw_text = self._normalize_claude_response(api_result)
        parsed_json, parse_error = self._try_parse_json_response(raw_text)

        return {
            "status": "success" if parsed_json else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed_json,
            "parse_error": parse_error,
            "prompt_key": "run_claude_brand_constraints",
            "prompt_file": str(
                self._get_prompt_file_path("run_claude_brand_constraints")
            ),
        }

    def _merge_brand_intake_outputs(self, base, core, strategy, constraints):
        merged = dict(base)

        if core:
            merged["positioning_summary"] = core.get(
                "positioning_summary",
                merged.get("positioning_summary"),
            )
            merged["audience_core"] = core.get(
                "audience_core",
                merged.get("audience_core"),
            )
            merged["differentiation"] = self._clean_list(
                core.get("differentiation") or merged.get("differentiation")
            )
            merged["message_pillars"] = self._clean_list(
                core.get("message_pillars") or merged.get("message_pillars")
            )

        if strategy:
            merged["creative_angles"] = self._clean_list(
                strategy.get("creative_angles") or merged.get("creative_angles")
            )
            merged["research_focus"] = self._clean_list(
                strategy.get("research_focus") or merged.get("research_focus")
            )
            merged["strategy_brief"] = strategy.get(
                "strategy_brief",
                merged.get("strategy_brief"),
            )

        if constraints:
            merged["competitors"] = self._clean_list(constraints.get("competitors"))
            merged["constraints"] = constraints.get("constraints") or []
            merged["messaging_notes"] = self._clean_list(
                constraints.get("messaging_notes")
            )
            merged["research_notes"] = constraints.get("research_notes") or {}

        return merged

    # ---------------------------------------------------
    # Public API
    # ---------------------------------------------------
    def build_from_test_id(self, test_id, claude_mode="off", claude_api_adapter=None):
        """
        Build brand intake context theo test_id.

        Keep function name unchanged for compatibility.
        """
        package = self.loader.load_test_run_package(test_id)
        test_run = package.get("test_run", {}) or {}

        selling_orientation = self._parse_multi_value(
            test_run.get("selling_orientation")
        )
        occasion = self._parse_multi_value(test_run.get("occasion"))

        brand = package["brand"]
        product = package["product"]
        offer = package["offer"]
        seed_audience = package["seed_audience"]
        ai_audience = package["ai_audience"]

        # -----------------------------
        # Brand truths / guardrails / product supporting data
        # -----------------------------
        brand_truths = [
            row["truth_text"]
            for row in sorted(
                package["brand_truths"],
                key=lambda x: str(x.get("priority", "")).lower(),
            )
            if row.get("truth_text")
        ]
        brand_truths = self._clean_list(brand_truths)

        guardrails = [
            row["guardrail_text"]
            for row in package["brand_guardrails"]
            if row.get("guardrail_text")
        ]
        guardrails = self._clean_list(guardrails)

        product_benefits = [
            row["benefit_text"]
            for row in package["product_benefits"]
            if row.get("benefit_text")
        ]
        product_benefits = self._clean_list(product_benefits)

        usage_steps = [
            row["usage_text"]
            for row in sorted(
                package["product_usage"],
                key=lambda x: x.get("step_no", 999),
            )
            if row.get("usage_text")
        ]
        usage_steps = self._clean_list(usage_steps)

        # -----------------------------
        # Audience seed / AI audience
        # -----------------------------
        seed_audience_block = {
            "audience_id": seed_audience.get("audience_id"),
            "audience_name": seed_audience.get("audience_name"),
            "source_type": seed_audience.get("source_type"),
            "pain_point_input": seed_audience.get("pain_point_input"),
            "desired_outcome_input": seed_audience.get("desired_outcome_input"),
            "pain_point_required": seed_audience.get("pain_point_required"),
            "desired_outcome_required": seed_audience.get("desired_outcome_required"),
            "notes": seed_audience.get("notes"),
        }

        ai_audience_block = None
        if ai_audience:
            ai_audience_block = {
                "expanded_audience_id": ai_audience.get("expanded_audience_id"),
                "audience_name": ai_audience.get("audience_name"),
                "pain_point": ai_audience.get("pain_point"),
                "desired_outcome": ai_audience.get("desired_outcome"),
                "evidence_source": ai_audience.get("evidence_source"),
                "confidence": ai_audience.get("confidence"),
                "created_by": ai_audience.get("created_by"),
            }

        audience_name = self._first_non_empty(
            ai_audience.get("audience_name") if ai_audience else None,
            seed_audience.get("audience_name"),
        )
        pain_point = self._first_non_empty(
            ai_audience.get("pain_point") if ai_audience else None,
            seed_audience.get("pain_point_input"),
        )
        desired_outcome = self._first_non_empty(
            ai_audience.get("desired_outcome") if ai_audience else None,
            seed_audience.get("desired_outcome_input"),
        )

        # -----------------------------
        # Core fields
        # -----------------------------
        brand_name = self._first_non_empty(brand.get("brand_name"))
        brand_positioning = self._first_non_empty(brand.get("brand_positioning"))
        brand_type = self._first_non_empty(brand.get("brand_type"))
        origin = self._first_non_empty(brand.get("origin"))
        website = self._first_non_empty(brand.get("website"))
        product_name = self._first_non_empty(product.get("product_name"))
        product_format = self._first_non_empty(product.get("format"))
        offer_text = self._first_non_empty(offer.get("offer_text"))

        positioning_summary_parts = [brand_name, brand_positioning, product_name]
        positioning_summary = (
            " | ".join([p for p in positioning_summary_parts if p]) or brand_name
        )

        # -----------------------------
        # Derived strategy helpers
        # -----------------------------
        differentiation = []
        if brand_positioning:
            differentiation.append(brand_positioning)
        if brand_type:
            differentiation.append(f"Category focus: {brand_type}")
        if origin:
            differentiation.append(f"Origin: {origin}")
        if brand_truths:
            differentiation.extend(brand_truths[:3])

        message_pillars = []
        if brand_truths:
            message_pillars.extend(brand_truths[:4])
        if product_benefits:
            for benefit in product_benefits:
                if benefit not in message_pillars:
                    message_pillars.append(benefit)
        if offer_text and offer_text not in message_pillars:
            message_pillars.append(offer_text)
        message_pillars = message_pillars[:6]

        creative_angles = []
        if pain_point and desired_outcome:
            creative_angles.append(
                f"Turn '{pain_point}' into '{desired_outcome}' for {audience_name or 'the target audience'}."
            )
        if brand_positioning:
            creative_angles.append(
                f"Lead with {brand_positioning.lower()} instead of generic coffee messaging."
            )
        if brand_truths:
            creative_angles.append(f"Use {brand_truths[0]} as the primary proof point.")
        if product_format or usage_steps:
            creative_angles.append(
                f"Show convenience clearly with the {product_format or 'product format'} and simple usage."
            )
        if offer_text:
            creative_angles.append(
                f"Use {offer_text} to reduce trial friction and create a clear reason to act now."
            )
        creative_angles = self._clean_list(creative_angles)[:5]

        research_focus = self._clean_list(
            [
                (
                    f"Selling orientation: {', '.join(selling_orientation)}"
                    if selling_orientation
                    else None
                ),
                f"Occasion: {', '.join(occasion)}" if occasion else None,
                f"Audience: {audience_name}" if audience_name else None,
                f"Pain point: {pain_point}" if pain_point else None,
                f"Desired outcome: {desired_outcome}" if desired_outcome else None,
                f"Differentiate with: {brand_truths[0]}" if brand_truths else None,
                f"Offer role: {offer_text}" if offer_text else None,
            ]
        )

        strategy_brief = {
            "selling_orientation": selling_orientation,
            "occasion": occasion,
            "audience_core": audience_name,
            "pain_point": pain_point,
            "desired_outcome": desired_outcome,
            "positioning_summary": positioning_summary,
            "differentiation": differentiation[:4],
            "message_pillars": message_pillars,
            "creative_angles": creative_angles,
            "offer_role": offer_text,
            "do_not_say": guardrails[:5],
        }

        # -----------------------------
        # Base brand intake payload
        # -----------------------------
        brand_intake = {
            "timestamp": datetime.utcnow().isoformat(),
            "test_id": test_run.get("test_id"),
            "objective": test_run.get("objective"),
            "claude_mode": test_run.get("claude_mode"),
            "use_brand_intake": test_run.get("use_brand_intake"),
            "use_alysha_strategy": test_run.get("use_alysha_strategy"),
            "expected_focus": test_run.get("expected_focus"),
            "success_check": test_run.get("success_check"),
            "selling_orientation": selling_orientation,
            "occasion": occasion,
            "brand": {
                "brand_id": brand.get("brand_id"),
                "brand_name": brand.get("brand_name"),
                "website": brand.get("website"),
                "brand_positioning": brand.get("brand_positioning"),
                "brand_type": brand.get("brand_type"),
                "origin": brand.get("origin"),
                "default_market": brand.get("default_market"),
                "brand_story_short": brand.get("brand_story_short"),
                "notes": brand.get("notes"),
            },
            "product": {
                "product_id": product.get("product_id"),
                "product_name": product.get("product_name"),
                "product_line": product.get("product_line"),
                "product_type": product.get("product_type"),
                "format": product.get("format"),
                "pack_size": product.get("pack_size"),
                "sku": product.get("sku"),
                "list_price_usd": product.get("list_price_usd"),
                "priority_market": product.get("priority_market"),
                "status": product.get("status"),
                "notes": product.get("notes"),
            },
            "offer": {
                "offer_id": offer.get("offer_id"),
                "offer_text": offer.get("offer_text"),
                "offer_type": offer.get("offer_type"),
                "market": offer.get("market"),
                "status": offer.get("status"),
                "notes": offer.get("notes"),
            },
            "core_truth": brand_truths,
            "guardrails": guardrails,
            "product_benefits": product_benefits,
            "product_usage_steps": usage_steps,
            "audience_seed": seed_audience_block,
            "audience_ai_expanded": ai_audience_block,
            "positioning_summary": positioning_summary,
            "audience_core": {
                "audience_name": audience_name,
                "pain_point": pain_point,
                "desired_outcome": desired_outcome,
            },
            "differentiation": differentiation[:6],
            "message_pillars": message_pillars,
            "creative_angles": creative_angles,
            "research_focus": research_focus,
            "strategy_brief": strategy_brief,
        }

        # -----------------------------
        # Website fetch stage
        # -----------------------------
        website_context = self._fetch_website_context(website)
        website_context_file = self._save_website_context_file(test_id, website_context)

        brand_intake["website_context"] = website_context
        brand_intake["website_context_file"] = website_context_file

        # -----------------------------
        # Claude enrichment stage (3-stage)
        # -----------------------------
        brand_intake["claude_brand_core"] = {
            "status": "skipped",
            "raw_response": None,
            "parsed": None,
            "parse_error": None,
            "prompt_key": "run_claude_brand_core",
            "prompt_file": str(self._get_prompt_file_path("run_claude_brand_core")),
        }
        brand_intake["claude_brand_strategy"] = {
            "status": "skipped",
            "raw_response": None,
            "parsed": None,
            "parse_error": None,
            "prompt_key": "run_claude_brand_strategy",
            "prompt_file": str(self._get_prompt_file_path("run_claude_brand_strategy")),
        }
        brand_intake["claude_brand_constraints"] = {
            "status": "skipped",
            "raw_response": None,
            "parsed": None,
            "parse_error": None,
            "prompt_key": "run_claude_brand_constraints",
            "prompt_file": str(
                self._get_prompt_file_path("run_claude_brand_constraints")
            ),
        }

        if claude_mode == "api" and claude_api_adapter:
            readiness = claude_api_adapter.readiness()
            if readiness.get("ready"):
                try:
                    core_result = self._run_claude_brand_core(
                        brand_intake=brand_intake,
                        website_context=website_context,
                        claude_api_adapter=claude_api_adapter,
                    )
                    brand_intake["claude_brand_core"] = core_result
                    core_parsed = core_result.get("parsed") or {}
                    self._save_brand_stage_file(test_id, "brand_core", core_result)

                    strategy_result = self._run_claude_brand_strategy(
                        brand_intake=brand_intake,
                        website_context=website_context,
                        brand_core_output=core_parsed,
                        claude_api_adapter=claude_api_adapter,
                    )
                    brand_intake["claude_brand_strategy"] = strategy_result
                    strategy_parsed = strategy_result.get("parsed") or {}
                    self._save_brand_stage_file(
                        test_id, "brand_strategy", strategy_result
                    )

                    constraints_result = self._run_claude_brand_constraints(
                        brand_intake=brand_intake,
                        website_context=website_context,
                        brand_core_output=core_parsed,
                        brand_strategy_output=strategy_parsed,
                        claude_api_adapter=claude_api_adapter,
                    )
                    brand_intake["claude_brand_constraints"] = constraints_result
                    constraints_parsed = constraints_result.get("parsed") or {}
                    self._save_brand_stage_file(
                        test_id, "brand_constraints", constraints_result
                    )

                    brand_intake = self._merge_brand_intake_outputs(
                        base=brand_intake,
                        core=core_parsed,
                        strategy=strategy_parsed,
                        constraints=constraints_parsed,
                    )

                except Exception as e:
                    brand_intake["claude_brand_constraints"] = {
                        "status": "error",
                        "reason": str(e),
                        "raw_response": None,
                        "parsed": None,
                        "parse_error": None,
                        "prompt_key": "run_claude_brand_constraints",
                        "prompt_file": str(
                            self._get_prompt_file_path("run_claude_brand_constraints")
                        ),
                    }
            else:
                brand_intake["claude_brand_core"][
                    "reason"
                ] = "Claude brand intake adapter not ready."
                brand_intake["claude_brand_strategy"][
                    "reason"
                ] = "Claude brand intake adapter not ready."
                brand_intake["claude_brand_constraints"][
                    "reason"
                ] = "Claude brand intake adapter not ready."

        # -----------------------------
        # Save brand intake file last,
        # after website context + Claude enrichment
        # -----------------------------
        brand_intake_file = self._save_brand_intake_file(test_id, brand_intake)
        brand_intake["brand_intake_file"] = brand_intake_file

        # Save again so the attached file path is also included in saved payload
        self._save_brand_intake_file(test_id, brand_intake)

        return brand_intake
