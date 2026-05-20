import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests

from core.config.paths import BRAND_INTAKE_PROMPTS_DIR
from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.engines.universal_brand_intake_loader import UniversalBrandIntakeLoader
from core.services.brand_context_resolver import BrandContextResolver


class UniversalBrandIntakeEngine:
    """Build the canonical Brand Context Source of Truth from Alysha intake fields."""

    PROMPT_FILE = BRAND_INTAKE_PROMPTS_DIR / "universal_brand_context_alysha_prompt.txt"

    def __init__(
        self,
        *,
        brand_id: str,
        loader: Optional[UniversalBrandIntakeLoader] = None,
        resolver: Optional[BrandContextResolver] = None,
        claude_api_adapter: Optional[ClaudeAPIAdapter] = None,
    ):
        self.brand_id = str(brand_id or "").strip()
        if not self.brand_id:
            raise ValueError("brand_id is required")
        self.loader = loader or UniversalBrandIntakeLoader(brand_id=self.brand_id)
        self.resolver = resolver or BrandContextResolver()
        self.claude = claude_api_adapter or ClaudeAPIAdapter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, *, dry_run: bool = False, max_fetch_pages: int = 6) -> Dict[str, Any]:
        intake = self.loader.load()
        validation = intake.get("validation") or {}
        if validation.get("status") != "pass":
            raise ValueError(
                "Universal Brand Intake is missing required Alysha seed fields: "
                + ", ".join(validation.get("missing_required_fields") or [])
            )

        paths = self.resolver.resolve(self.brand_id)
        normalized = self._build_normalized_intake(intake)
        self._write_json(paths["brand_intake_raw_file"], intake)
        self._write_json(paths["brand_intake_normalized_file"], normalized)

        fetched_sources = self._fetch_source_excerpts(normalized, max_pages=max_fetch_pages)

        if dry_run:
            run_payload = {
                "status": "validated",
                "brand_id": self.brand_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": True,
                "paths": self._stringify_paths(paths),
                "validation": validation,
                "fetched_sources": fetched_sources,
                "llm_usage": self.claude.usage_summary(),
                "notes": "Dry run completed. Brand context generation was not sent to Claude.",
            }
            self._write_json(paths["brand_intake_run_file"], run_payload)
            return run_payload

        prompt = self._render_prompt(normalized, fetched_sources)
        response = self._call_claude(prompt)
        parsed = self._parse_json_response(response)
        context_json = parsed.get("brand_context_source_of_truth") or {}
        markdown = str(parsed.get("brand_context_source_of_truth_markdown") or "").strip()
        research_notes = parsed.get("brand_research_notes") or {}
        compliance = parsed.get("alysha_compliance") or {}

        if not markdown:
            raise ValueError("Claude response missing brand_context_source_of_truth_markdown")
        if not context_json:
            raise ValueError("Claude response missing brand_context_source_of_truth")

        context_payload = {
            "brand_id": self.brand_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_intake_file": str(paths["brand_intake_normalized_file"]),
            "brand_context_source_of_truth": context_json,
            "alysha_compliance": compliance,
        }

        self._write_text(paths["brand_context_markdown_file"], markdown + "\n")
        self._write_json(paths["brand_context_json_file"], context_payload)
        self._write_json(paths["brand_research_notes_file"], research_notes)

        run_payload = {
            "status": "success",
            "brand_id": self.brand_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": False,
            "paths": self._stringify_paths(paths),
            "validation": validation,
            "fetched_sources": fetched_sources,
            "alysha_compliance": compliance,
            "llm_usage": self.claude.usage_summary(),
        }
        self._write_json(paths["brand_intake_run_file"], run_payload)
        return run_payload

    # ------------------------------------------------------------------
    # Normalization / prompts
    # ------------------------------------------------------------------
    def _build_normalized_intake(self, intake: Dict[str, Any]) -> Dict[str, Any]:
        fields = dict(intake.get("fields") or {})
        return {
            "brand_id": self.brand_id,
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "source": intake.get("source") or {},
            "validation": intake.get("validation") or {},
            "fields": fields,
            "field_groups": {
                "alysha_required_seed": {
                    field: fields.get(field, "") for field in UniversalBrandIntakeLoader.REQUIRED_FIELDS
                },
                "optional_human_context": {
                    field: value
                    for field, value in fields.items()
                    if field not in set(UniversalBrandIntakeLoader.REQUIRED_FIELDS) and not field.startswith("_")
                },
            },
        }

    def _render_prompt(self, normalized_intake: Dict[str, Any], fetched_sources: Dict[str, Any]) -> str:
        if not self.PROMPT_FILE.exists():
            raise FileNotFoundError(f"Universal Brand Intake prompt not found: {self.PROMPT_FILE}")
        prompt = self.PROMPT_FILE.read_text(encoding="utf-8")
        prompt = prompt.replace(
            "{{UNIVERSAL_BRAND_INTAKE_FIELDS}}",
            json.dumps(normalized_intake, ensure_ascii=False, indent=2),
        )
        prompt = prompt.replace(
            "{{FETCHED_SOURCE_EXCERPTS}}",
            json.dumps(fetched_sources, ensure_ascii=False, indent=2),
        )
        return prompt

    def _call_claude(self, prompt: str) -> str:
        try:
            result = self.claude.run(prompt=prompt, max_tokens=12000, temperature=0.1)
        except TypeError:
            result = self.claude.run(prompt=prompt)
        return self._normalize_claude_response(result)

    # ------------------------------------------------------------------
    # Lightweight public source fetching
    # ------------------------------------------------------------------
    def _fetch_source_excerpts(self, normalized: Dict[str, Any], *, max_pages: int) -> Dict[str, Any]:
        fields = normalized.get("fields") or {}
        urls = self._candidate_urls(fields)
        pages: Dict[str, str] = {}
        sources: List[str] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            )
        }

        for url in urls:
            if len(sources) >= max_pages:
                break
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code >= 400:
                    continue
                text = self._strip_html(response.text)
                if not text:
                    continue
                pages[url] = text[:6000]
                sources.append(url)
            except Exception:
                continue

        return {
            "status": "success" if sources else "no_sources_fetched",
            "sources": sources,
            "pages": pages,
            "candidate_urls": urls,
            "notes": (
                "This engine fetches direct public pages and user-provided source URLs. "
                "Search-engine style competitor discovery remains a separate research capability."
            ),
        }

    def _candidate_urls(self, fields: Dict[str, Any]) -> List[str]:
        website = str(fields.get("brand_website_url") or "").strip()
        candidates: List[str] = []
        if website:
            if not website.startswith(("http://", "https://")):
                website = "https://" + website
            candidates.extend(
                [
                    website,
                    urljoin(website, "/about"),
                    urljoin(website, "/pages/about"),
                    urljoin(website, "/collections/all"),
                    urljoin(website, "/shop"),
                    urljoin(website, "/faq"),
                ]
            )

        for key in [
            "known_product_catalog_sources",
            "hero_product_or_winner_design_source",
            "known_source_links_or_docs",
        ]:
            candidates.extend(self._extract_urls(str(fields.get(key) or "")))

        deduped: List[str] = []
        seen = set()
        for url in candidates:
            cleaned = str(url or "").strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                deduped.append(cleaned)
        return deduped

    def _extract_urls(self, text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"https?://[^\s,;|]+", text)

    def _strip_html(self, html: str) -> str:
        if not html:
            return ""
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<noscript[\s\S]*?</noscript>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()

    # ------------------------------------------------------------------
    # Claude response parsing
    # ------------------------------------------------------------------
    def _normalize_claude_response(self, api_result: Any) -> str:
        if api_result is None:
            return ""
        if isinstance(api_result, str):
            return api_result
        if isinstance(api_result, dict):
            for key in ["response_text", "response", "content", "result", "text"]:
                value = api_result.get(key)
                if value:
                    return str(value)
        if hasattr(api_result, "content"):
            try:
                texts = []
                for block in getattr(api_result, "content", []) or []:
                    text = getattr(block, "text", None)
                    if text:
                        texts.append(text)
                if texts:
                    return "\n".join(texts)
            except Exception:
                pass
        return str(api_result)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        candidate = self._extract_json_block(raw)
        if not candidate:
            raise ValueError("Claude Brand Intake response did not contain a JSON object")
        try:
            return json.loads(candidate)
        except Exception as exc:
            repaired = self._repair_json_candidate(candidate)
            if repaired != candidate:
                return json.loads(repaired)
            raise ValueError(f"Unable to parse Brand Intake JSON response: {exc}")

    def _extract_json_block(self, text: str) -> Optional[str]:
        if not text:
            return None
        text = text.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
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
                    return text[start : idx + 1]
        return text[start:]

    def _repair_json_candidate(self, candidate: str) -> str:
        repaired = candidate.strip()
        missing_brackets = repaired.count("[") - repaired.count("]")
        missing_braces = repaired.count("{") - repaired.count("}")
        if missing_brackets > 0:
            repaired += "]" * missing_brackets
        if missing_braces > 0:
            repaired += "}" * missing_braces
        return repaired

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------
    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _stringify_paths(self, paths: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for key, value in paths.items():
            if isinstance(value, Path):
                out[key] = str(value)
            elif key == "brand":
                out[key] = value
            else:
                out[key] = value
        return out
