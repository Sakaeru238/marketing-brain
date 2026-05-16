import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


class PageAssessmentPipeline:
    """Creates weekly page assessment JSON."""

    def __init__(
        self,
        prompt_file="data/prompts/organic/page_assessment_prompt.txt",
        output_file="data/output/organic/page_assessment/page_assessment_output.json",
        strategy_file="data/output/strategy_output.json",
    ):
        self.prompt_file = Path(prompt_file)
        self.output_file = Path(output_file)
        self.strategy_file = Path(strategy_file)

    def _load_json(self, path, default=None):
        path = Path(path)
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

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
                if result.get(key):
                    return result.get(key)
        if hasattr(result, "content"):
            try:
                return "\n".join([b.text for b in result.content if hasattr(b, "text")])
            except Exception:
                pass
        return str(result)

    def _build_input(self, **kwargs):
        today = datetime.now(timezone.utc).date()
        page_id = kwargs.get("page_id", "AODAI_FB_US")
        return {
            "assessment_context": {
                "assessment_id": f"ASSESS_{page_id}_{today.isoformat().replace('-', '')}",
                "assessment_type": "weekly",
                "generated_at": datetime.utcnow().isoformat(),
            },
            "page_context": kwargs,
            "review_window": {"start": (today - timedelta(days=7)).isoformat(), "end": today.isoformat()},
            "strategy_output": self._load_json(self.strategy_file, default={}),
            "previous_week_results": kwargs.get("previous_results") or [],
            "daily_learning_log": kwargs.get("daily_learning") or [],
        }

    def _build_prompt(self, assessment_input):
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Page assessment prompt not found: {self.prompt_file}")
        return self.prompt_file.read_text(encoding="utf-8").replace(
            "{{PAGE_ASSESSMENT_INPUT}}",
            json.dumps(assessment_input, ensure_ascii=False, indent=2),
        )

    def _run_claude(self, claude_api_adapter, prompt):
        try:
            return claude_api_adapter.run(prompt=prompt, max_tokens=6000, temperature=0.2)
        except TypeError:
            return claude_api_adapter.run(prompt=prompt)

    def run(self, claude_api_adapter, **kwargs):
        defaults = {
            "brand_id": "AODAI",
            "niche_id": "vietnamese_coffee",
            "page_id": "AODAI_FB_US",
            "platform_id": "facebook",
            "page_url": "",
            "current_followers": 0,
            "current_likes": 0,
            "target_followers": 1000,
            "target_likes": 1000,
            "target_market": "US",
            "target_timezone": "America/New_York",
        }
        defaults.update(kwargs)
        assessment_input = self._build_input(**defaults)
        raw = self._normalize_claude_response(self._run_claude(claude_api_adapter, self._build_prompt(assessment_input)))
        parsed, err = self._try_parse_json_response(raw)

        output = {
            "stage": "page_assessment",
            "status": "ready" if parsed else "unparsed",
            "generated_at": datetime.utcnow().isoformat(),
            "data": parsed or {},
            "claude_page_assessment_raw": raw,
            "claude_page_assessment_parse_error": err,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return output
