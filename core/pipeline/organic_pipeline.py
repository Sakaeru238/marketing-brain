import json
import re
from datetime import datetime
from pathlib import Path

from core.loaders.organic_control_loader import OrganicControlLoader


class OrganicPipeline:
    def __init__(self, control_panel_file="data/control_panels/marketing_brain_control_panel.xlsx", prompt_file="data/prompts/organic/organic_engagement_prompt.txt", strategy_file="data/output/strategy_output.json"):
        self.control_panel_file = Path(control_panel_file)
        self.prompt_file = Path(prompt_file)
        self.strategy_file = Path(strategy_file)
        self.loader = OrganicControlLoader(control_panel_file=self.control_panel_file)

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
                return "\n".join([block.text for block in result.content if hasattr(block, "text")])
            except Exception:
                pass
        return str(result)

    def _load_strategy_output(self):
        if not self.strategy_file.exists():
            raise FileNotFoundError(f"Strategy output not found: {self.strategy_file}")
        return json.loads(self.strategy_file.read_text(encoding="utf-8"))

    def _load_prompt_template(self):
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Organic prompt not found: {self.prompt_file}")
        return self.prompt_file.read_text(encoding="utf-8")

    def build_organic_input(self, organic_run_id=None):
        package = self.loader.load_package(organic_run_id=organic_run_id)
        strategy_output = self._load_strategy_output()
        organic = package["organic_control"]
        strategy_data = strategy_output.get("data", {}) or {}
        return {
            "run_context": {"organic_run_id": organic.get("organic_run_id"), "run_id": organic.get("run_id"), "campaign_id": organic.get("campaign_id"), "generated_at": datetime.utcnow().isoformat()},
            "identity_context": {"niche_id": organic.get("niche_id"), "brand_id": organic.get("brand_id"), "product_id": organic.get("product_id"), "page_id": organic.get("page_id"), "campaign_id": organic.get("campaign_id"), "platform_id": organic.get("platform_id")},
            "strategy_context": {
                "strategy_source_file": str(self.strategy_file),
                "strategy_output": strategy_output,
                "campaign_direction_alignment": strategy_data.get("campaign_direction_alignment", []),
                "target_persona": strategy_data.get("target_persona", []),
                "customer_psychology": strategy_data.get("customer_psychology", []),
                "priority_angles": strategy_data.get("priority_angles", []),
                "hook_guidance": strategy_data.get("hook_guidance", []),
                "core_message": strategy_data.get("core_message", []),
                "voc_summary": strategy_data.get("voc_summary", []),
                "creative_direction": strategy_data.get("creative_direction", []),
                "do_not_do": strategy_data.get("do_not_do", []),
            },
            "goal_context": {"growth_goal": organic.get("growth_goal"), "growth_goal_target": organic.get("growth_goal_target"), "growth_goal_deadline": organic.get("growth_goal_deadline"), "today_content_goal": organic.get("today_content_goal"), "organic_stage": organic.get("organic_stage"), "num_posts": organic.get("num_posts")},
            "audience_context": {"target_persona": strategy_data.get("target_persona", []), "customer_psychology": strategy_data.get("customer_psychology", []), "niche_id": organic.get("niche_id"), "niche_context": package.get("niche", {}), "page_stage": organic.get("page_stage")},
            "brand_context": {"brand_id": organic.get("brand_id"), "product_id": organic.get("product_id"), "brand_intake_file": organic.get("resolved_brand_intake_file"), "brand_intake": package.get("brand_intake", {}), "brand_voice": organic.get("tone"), "product_mention_level": organic.get("product_mention_level"), "must_use_topics": organic.get("must_use_topics", []), "avoid_topics": organic.get("avoid_topics", [])},
            "campaign_context": package.get("campaign", {}),
            "platform_context": {"platform_id": organic.get("platform_id"), "platform_rules": package.get("platform", {}), "post_format_mix": organic.get("post_format_mix", [])},
            "page_context": {"page_id": organic.get("page_id"), "page_url": organic.get("page_url"), "page_library": package.get("page", {}), "page_audit_context": package.get("page_audit_context", {}), "previous_results_context": package.get("previous_results_context", [])},
            "output_requirements": {"output_type": "organic_posts", "return_json_only": True, "language": organic.get("language"), "num_posts_required": organic.get("num_posts")},
        }

    def _build_prompt(self, organic_input):
        return self._load_prompt_template().replace("{{ORGANIC_INPUT}}", json.dumps(organic_input, ensure_ascii=False, indent=2))

    def _save_output(self, output):
        base_dir = Path("data/output/organic")
        history_dir = base_dir / "history" / "posts"
        base_dir.mkdir(parents=True, exist_ok=True)
        history_dir.mkdir(parents=True, exist_ok=True)
        latest_path = base_dir / "organic_output.json"
        history_path = history_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        latest_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        history_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"latest_path": str(latest_path), "history_path": str(history_path)}

    def _run_claude(self, claude_api_adapter, prompt):
        try:
            return claude_api_adapter.run(prompt=prompt, max_tokens=7000, temperature=0.2)
        except TypeError:
            return claude_api_adapter.run(prompt=prompt)

    def run(self, organic_run_id=None, claude_mode="off", claude_api_adapter=None):
        organic_input = self.build_organic_input(organic_run_id=organic_run_id)
        prompt = self._build_prompt(organic_input)
        if claude_mode != "api" or not claude_api_adapter:
            raise RuntimeError("OrganicPipeline requires claude_mode='api' and a ready claude_api_adapter.")
        api_result = self._run_claude(claude_api_adapter, prompt)
        raw_text = self._normalize_claude_response(api_result)
        parsed, parse_error = self._try_parse_json_response(raw_text)
        run_ctx = organic_input.get("run_context", {})
        identity = organic_input.get("identity_context", {})
        data = parsed if parsed else {}
        data["claude_organic_raw"] = raw_text
        data["claude_organic_parse_error"] = parse_error
        output = {
            "stage": "organic",
            "status": "ready" if parsed else "unparsed",
            "organic_run_id": run_ctx.get("organic_run_id"),
            "run_id": run_ctx.get("run_id"),
            "campaign_id": run_ctx.get("campaign_id"),
            "niche_id": identity.get("niche_id"),
            "brand_id": identity.get("brand_id"),
            "product_id": identity.get("product_id"),
            "page_id": identity.get("page_id"),
            "platform_id": identity.get("platform_id"),
            "generated_at": datetime.utcnow().isoformat(),
            "data": data,
        }
        output["saved_paths"] = self._save_output(output)
        Path(output["saved_paths"]["latest_path"]).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return output
