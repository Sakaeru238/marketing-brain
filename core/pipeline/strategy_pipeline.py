import json
import re
from datetime import datetime
from pathlib import Path


class StrategyPipeline:
    def __init__(self):
        self.prompt_path = Path("data/prompts/strategy/strategy_generation_prompt.txt")

    # =========================
    # PARSE JSON
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

        try:
            return json.loads(match.group()), None
        except Exception as e:
            return None, str(e)

    # =========================
    # NORMALIZE RESPONSE
    # =========================
    def _normalize_claude_response(self, result):
        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            for key in ["response", "content", "text", "result", "response_text"]:
                value = result.get(key)
                if value:
                    return value

        if hasattr(result, "content"):
            try:
                return "\n".join([b.text for b in result.content if hasattr(b, "text")])
            except Exception:
                pass

        return str(result)

    # =========================
    # BUILD STRATEGY INPUT
    # =========================
    def _build_strategy_input(
        self,
        insight_output,
        brand_intake=None,
        customer_feedback_raw="",
        campaign_direction=None,
    ):
        return {
            "brand_intake": brand_intake or {},
            "campaign_direction": campaign_direction or {},
            "insight_output": insight_output or {},
            "customer_feedback_raw": customer_feedback_raw or "",
            "strategy_standard": {
                "required_blocks": [
                    "target_persona",
                    "customer_psychology",
                    "strategy_map",
                    "priority_angles",
                    "hook_guidance",
                    "core_message",
                    "offer_strategy",
                    "reason_to_believe",
                    "mechanism",
                    "voc_summary",
                    "creative_mechanics",
                    "visual_formats",
                    "creative_direction",
                    "do_not_do",
                ],
                "goal": "Alysha-ready strategy output for Creative Engine",
                "direction_rule": (
                    "Campaign direction is the source of truth. "
                    "Research and insight support the campaign direction; they must not override it."
                ),
            },
        }

    # =========================
    # BUILD PROMPT
    # =========================
    def _build_prompt(
        self,
        insight_output,
        brand_intake=None,
        customer_feedback_raw="",
        campaign_direction=None,
    ):
        if not self.prompt_path.exists():
            raise FileNotFoundError(
                f"Strategy prompt file not found: {self.prompt_path}"
            )

        template = self.prompt_path.read_text(encoding="utf-8")

        strategy_input = self._build_strategy_input(
            insight_output=insight_output,
            brand_intake=brand_intake,
            customer_feedback_raw=customer_feedback_raw,
            campaign_direction=campaign_direction,
        )

        prompt = template.replace(
            "{{STRATEGY_INPUT}}",
            json.dumps(strategy_input, ensure_ascii=False, indent=2),
        )

        return prompt

    # =========================
    # BUILD LEGACY COMPATIBILITY SUMMARY
    # =========================
    def _build_legacy_strategy_summary(
        self,
        insight_output,
        brand_intake=None,
        customer_feedback_raw="",
        campaign_direction=None,
    ):
        insight_data = insight_output.get("data", {}) or {}

        recommended_focus = insight_data.get("recommended_focus", []) or []
        top_findings = insight_data.get("top_findings", []) or []
        hooks = insight_data.get("hooks", []) or []
        claims = insight_data.get("claims", []) or []
        warnings_list = insight_data.get("warnings", []) or []

        brand_name = None
        product_name = None
        offer_text = None
        audience_name = None
        pain_point = None
        desired_outcome = None
        guardrails = []
        brand_strategy_brief = {}

        if brand_intake:
            brand = brand_intake.get("brand", {}) or {}
            product = brand_intake.get("product", {}) or {}
            offer = brand_intake.get("offer", {}) or {}
            audience_core = brand_intake.get("audience_core", {}) or {}

            brand_name = brand.get("brand_name")
            product_name = product.get("product_name")
            offer_text = offer.get("offer_text")

            audience_name = audience_core.get("audience_name")
            pain_point = audience_core.get("pain_point")
            desired_outcome = audience_core.get("desired_outcome")

            if isinstance(audience_core.get("ai_expanded_audience"), dict):
                ai_audience = audience_core.get("ai_expanded_audience") or {}
                audience_name = audience_name or ai_audience.get("audience_name")
                pain_point = pain_point or ai_audience.get("pain_point")
                desired_outcome = desired_outcome or ai_audience.get("desired_outcome")

            guardrails = brand_intake.get("guardrails", []) or []
            brand_strategy_brief = brand_intake.get("strategy_brief", {}) or {}

        current_objectives = []

        if campaign_direction:
            must_use = campaign_direction.get("must_use_direction")
            if must_use:
                current_objectives.append(f"Follow campaign direction: {must_use}")

            do_not_focus = campaign_direction.get("do_not_focus")
            if do_not_focus:
                current_objectives.append(f"Avoid direction drift: {do_not_focus}")

            primary_angle = campaign_direction.get("primary_angle_family")
            if primary_angle:
                current_objectives.append(
                    f"Prioritize primary angle family: {primary_angle}"
                )

        if pain_point and desired_outcome and audience_name:
            current_objectives.append(
                f"Turn '{pain_point}' into '{desired_outcome}' for {audience_name}"
            )

        for focus in recommended_focus[:4]:
            if focus:
                current_objectives.append(focus)

        for finding in top_findings[:3]:
            if finding:
                current_objectives.append(finding)

        if claims:
            current_objectives.append(f"Use '{claims[0]}' as a primary proof point")

        if offer_text:
            current_objectives.append(
                f"Use '{offer_text}' to reduce trial friction and create a clear reason to act now"
            )

        if product_name:
            current_objectives.append(
                f"Make {product_name} feel easy to try and easy to understand in one glance"
            )

        if customer_feedback_raw:
            current_objectives.append(
                "Use real customer feedback / Voice of Customer language to sharpen pain, objections, buying triggers, hooks, and creative direction"
            )

        deduped = []
        seen = set()
        for item in current_objectives:
            key = str(item).strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)

        current_objectives = deduped

        objective_scores = {obj: 1 for obj in current_objectives}
        ranked_objectives = [(obj, score) for obj, score in objective_scores.items()]

        return {
            "priority": [],
            "legacy_objectives": [],
            "current_objectives": current_objectives,
            "recommended_objectives": current_objectives[:8],
            "objective_scores": objective_scores,
            "ranked_objectives": ranked_objectives,
            "brand_strategy_brief": brand_strategy_brief,
            "campaign_direction": campaign_direction or {},
            "insight_strategy_brief": insight_data,
            "customer_feedback_context": {
                "available": bool(customer_feedback_raw),
                "character_count": len(customer_feedback_raw or ""),
            },
            "hooks": hooks,
            "claims": claims,
            "warnings": warnings_list,
            "guardrails": guardrails,
            "brand_name": brand_name,
            "product_name": product_name,
            "offer_text": offer_text,
            "audience_name": audience_name,
            "pain_point": pain_point,
            "desired_outcome": desired_outcome,
        }

    # =========================
    # MAIN RUN
    # =========================
    def run(
        self,
        insight_output,
        brand_intake=None,
        customer_feedback_raw="",
        campaign_direction=None,
        claude_mode="off",
        claude_api_adapter=None,
    ):
        legacy_summary = self._build_legacy_strategy_summary(
            insight_output=insight_output,
            brand_intake=brand_intake,
            customer_feedback_raw=customer_feedback_raw,
            campaign_direction=campaign_direction,
        )

        if claude_mode == "api" and claude_api_adapter:
            prompt = self._build_prompt(
                insight_output=insight_output,
                brand_intake=brand_intake,
                customer_feedback_raw=customer_feedback_raw,
                campaign_direction=campaign_direction,
            )

            api_result = claude_api_adapter.run(prompt=prompt)
            raw_text = self._normalize_claude_response(api_result)
            parsed, error = self._try_parse_json_response(raw_text)

            if parsed:
                return {
                    "stage": "strategy",
                    "status": "ready",
                    "input_stage": "insight",
                    "generated_at": datetime.utcnow().isoformat(),
                    "data": {
                        **parsed,
                        "strategy_summary": legacy_summary,
                        "campaign_direction_used": campaign_direction or {},
                        "claude_strategy_raw": raw_text,
                        "claude_strategy_parse_error": None,
                    },
                }

            return {
                "stage": "strategy",
                "status": "unparsed",
                "input_stage": "insight",
                "generated_at": datetime.utcnow().isoformat(),
                "data": {
                    "strategy_summary": legacy_summary,
                    "campaign_direction_used": campaign_direction or {},
                    "claude_strategy_raw": raw_text,
                    "claude_strategy_parse_error": error,
                },
            }

        return {
            "stage": "strategy",
            "status": "ready",
            "input_stage": "insight",
            "generated_at": datetime.utcnow().isoformat(),
            "data": {
                "strategy_summary": legacy_summary,
                "campaign_direction_used": campaign_direction or {},
            },
        }
