import json
import re
from datetime import datetime
from pathlib import Path


class InsightPipeline:
    def __init__(self):
        self.prompt_path = Path("data/prompts/insight/insight_extraction_prompt.txt")

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
    # LEGACY SUMMARY
    # =========================
    def _build_legacy_summary(self, research_output):
        data = research_output.get("data", {}) or {}

        if isinstance(data, list):
            data = {}

        items = data.get("items", []) or []

        research_summary = data.get("research_summary", {}) or {}
        competitor_findings = data.get("competitor_findings", []) or []
        trend_findings = data.get("trend_findings", []) or []
        ad_findings = data.get("ad_findings", []) or []
        note_findings = data.get("note_findings", []) or []
        hooks = data.get("hooks", []) or []
        claims = data.get("claims", []) or []
        warnings_list = data.get("warnings", []) or []
        recommended_focus = data.get("recommended_focus", []) or []

        categories = {}
        categorized_items = {}

        for item in items:
            category = item.get("category", "unknown")
            file_name = item.get("file_name", "unknown")
            categories[category] = categories.get(category, 0) + 1
            categorized_items.setdefault(category, []).append(file_name)

        insight_summary = {
            "total_items": len(items),
            "categories": categories,
            "research_overview": research_summary.get("overview"),
            "top_findings_count": len(research_summary.get("top_findings", []) or []),
            "key_risks_count": len(research_summary.get("key_risks", []) or []),
            "key_opportunities_count": len(
                research_summary.get("key_opportunities", []) or []
            ),
            "hooks_count": len(hooks),
            "claims_count": len(claims),
            "warnings_count": len(warnings_list),
            "recommended_focus_count": len(recommended_focus),
            "competitor_findings_count": len(competitor_findings),
            "ad_findings_count": len(ad_findings),
        }

        return {
            "insight_summary": insight_summary,
            "categorized_items": categorized_items,
            "research_summary": research_summary,
            "top_findings": research_summary.get("top_findings", []) or [],
            "key_risks": research_summary.get("key_risks", []) or [],
            "key_opportunities": research_summary.get("key_opportunities", []) or [],
            "competitor_findings": competitor_findings,
            "trend_findings": trend_findings,
            "ad_findings": ad_findings,
            "note_findings": note_findings,
            "hooks": hooks,
            "claims": claims,
            "warnings": warnings_list,
            "recommended_focus": recommended_focus,
        }

    # =========================
    # BUILD PROMPT
    # =========================
    def _build_prompt(self, research_output):
        if not self.prompt_path.exists():
            raise FileNotFoundError(
                f"Insight prompt file not found: {self.prompt_path}"
            )

        template = self.prompt_path.read_text(encoding="utf-8")

        prompt = template.replace(
            "{{RESEARCH_DATA}}",
            json.dumps(research_output, ensure_ascii=False, indent=2),
        )

        return prompt

    # =========================
    # MAIN RUN
    # =========================
    def run(self, research_output, claude_mode="off", claude_api_adapter=None):
        legacy_data = self._build_legacy_summary(research_output)

        if claude_mode == "api" and claude_api_adapter:
            prompt = self._build_prompt(research_output)

            api_result = claude_api_adapter.run(prompt=prompt)
            raw_text = self._normalize_claude_response(api_result)
            parsed, error = self._try_parse_json_response(raw_text)

            if parsed:
                return {
                    "stage": "insight",
                    "status": "ready",
                    "input_stage": "research",
                    "generated_at": datetime.utcnow().isoformat(),
                    "data": {
                        **legacy_data,
                        **parsed,
                        "claude_insight_raw": raw_text,
                        "claude_insight_parse_error": None,
                    },
                }

            return {
                "stage": "insight",
                "status": "unparsed",
                "input_stage": "research",
                "generated_at": datetime.utcnow().isoformat(),
                "data": {
                    **legacy_data,
                    "claude_insight_raw": raw_text,
                    "claude_insight_parse_error": error,
                },
            }

        return {
            "stage": "insight",
            "status": "ready",
            "input_stage": "research",
            "generated_at": datetime.utcnow().isoformat(),
            "data": legacy_data,
        }
