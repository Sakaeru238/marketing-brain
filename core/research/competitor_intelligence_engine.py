import json
from pathlib import Path

from core.config.paths import (
    COMPETITOR_DIR,
    RESEARCH_PROMPTS_DIR,
    PAIN_POINT_DIR,
)


class CompetitorIntelligenceEngine:
    def __init__(self):
        self.research_prompts_dir = Path(RESEARCH_PROMPTS_DIR)
        self.prompt_files = {
            "competitor_discovery": "discover_competitors_prompt.txt",
            "competitor_intake": "competitor_intake_prompt.txt",
            "pain_point_extraction": "pain_point_extraction_prompt.txt",
        }

    def _get_prompt_file_path(self, prompt_key):
        return self.research_prompts_dir / self.prompt_files[prompt_key]

    def _load_prompt_template(self, prompt_key):
        return self._get_prompt_file_path(prompt_key).read_text(encoding="utf-8")

    def _render_prompt(self, prompt_key, variables):
        template = self._load_prompt_template(prompt_key)
        for key, value in variables.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def _normalize_claude_response(self, api_result):
        if api_result is None:
            return None
        if isinstance(api_result, str):
            return api_result
        if isinstance(api_result, dict):
            for key in ["response_text", "response", "content", "result", "text"]:
                if api_result.get(key):
                    return api_result[key]
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
        text = text.strip()
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
                    return text[start:i + 1]

        return text[start:]

    def _repair_json_candidate(self, candidate):
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
                return None, f"Initial parse failed: {first_error} | Repaired parse failed: {second_error}"

        return None, f"Initial parse failed: {first_error}"

    def _save_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_competitor_discovery(self, _id, brand_context, claude_api_adapter):
        prompt = self._render_prompt(
            "competitor_discovery",
            {
                "RUN_ID": _id,
                "INPUT_BUNDLE": json.dumps(brand_context, ensure_ascii=False, indent=2),
                "MAX_COMPETITORS": 3
            }
        )

        api_result = claude_api_adapter.run(prompt=prompt)
        raw_text = self._normalize_claude_response(api_result)

        parsed, parse_error = self._try_parse_json_response(raw_text)

        return {
            "status": "success" if parsed else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed,
            "parse_error": parse_error,
            "prompt_file": self.prompt_files["competitor_discovery"],
        }

    def run_competitor_intake(self, _id, competitor_context, claude_api_adapter, slug):
        prompt = self._render_prompt(
            "competitor_intake",
            {"COMPETITOR_CONTEXT": json.dumps(competitor_context, ensure_ascii=False, indent=2)},
        )
        raw_text = self._normalize_claude_response(
            claude_api_adapter.run(prompt=prompt)
        )
        parsed, parse_error = self._try_parse_json_response(raw_text)

        payload = {
            "status": "success" if parsed else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed,
            "parse_error": parse_error,
            "prompt_file": str(self._get_prompt_file_path("competitor_intake")),
        }
        self._save_json(Path(COMPETITOR_DIR) / f"{_id}_{slug}.json", payload)
        return payload

    def run_pain_point_extraction(self, _id, signal_context, claude_api_adapter):
        prompt = self._render_prompt(
            "pain_point_extraction",
            {"SIGNAL_CONTEXT": json.dumps(signal_context, ensure_ascii=False, indent=2)},
        )
        raw_text = self._normalize_claude_response(
            claude_api_adapter.run(prompt=prompt)
        )
        parsed, parse_error = self._try_parse_json_response(raw_text)

        payload = {
            "status": "success" if parsed else "unparsed",
            "raw_response": raw_text,
            "parsed": parsed,
            "parse_error": parse_error,
            "prompt_file": str(self._get_prompt_file_path("pain_point_extraction")),
        }
        self._save_json(Path(PAIN_POINT_DIR) / f"{_id}_pain_points.json", payload)
        return payload