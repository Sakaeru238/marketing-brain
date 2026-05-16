import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.prompts.prompt_loader import PromptLoader


class OpenDesignVisualTranslationService:
    """
    Per-post visual translation layer inspired by Open Design's image-poster skill.

    It takes the exact organic post text/context and produces one visual truth package per post:
    - text_to_visual_alignment
    - open_design_visual_spec
    - open_design_master_prompt
    - chatgpt_image_prompt (used by GSheet export)
    - comfyui_prompt_bundle (used to prepare ComfyUI runtime JSON)
    """

    DEFAULT_SKILL_CANDIDATES = [
        "external/creative_execution/open_design/skills/image-poster/SKILL.md",
        "external/creative_execution/providers/open_design/skills/image-poster/SKILL.md",
        "external/creative_execution/external/open_design/skills/image-poster/SKILL.md",
    ]

    def __init__(
        self,
        prompt_file: str = "data/prompts/organic/open_design_visual_translation_prompt.txt",
    ):
        self.prompt_file = prompt_file
        self.prompt_loader = PromptLoader()
        self.claude = ClaudeAPIAdapter()

    def _clean_str(self, value: Any) -> str:
        return str(value or "").strip()

    def _load_open_design_skill_excerpt(self) -> Dict[str, Any]:
        candidates = []
        configured = self._clean_str(os.getenv("OPEN_DESIGN_IMAGE_POSTER_SKILL_FILE"))
        if configured:
            candidates.append(configured)
        candidates.extend(self.DEFAULT_SKILL_CANDIDATES)

        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                text = path.read_text(encoding="utf-8")
                return {
                    "source": str(path),
                    "skill_excerpt": text[:6000],
                }
        return {
            "source": "built_in_open_design_image_poster_contract",
            "skill_excerpt": (
                "Open Design image-poster contract: compose prompts in this order: "
                "(1) subject + composition, (2) lighting + mood, (3) palette + textures, "
                "(4) camera/lens only when photographic realism is needed, (5) what to avoid. "
                "The prompt must be tight, structured, and image-generation-provider agnostic."
            ),
        }

    def _parse_json_response(self, raw: Any) -> Tuple[Dict[str, Any], str]:
        if isinstance(raw, dict):
            for key in ["response", "content", "text", "result", "response_text"]:
                if raw.get(key):
                    raw = raw[key]
                    break
        if hasattr(raw, "content"):
            try:
                raw = "\n".join([block.text for block in raw.content if hasattr(block, "text")])
            except Exception:
                raw = str(raw)
        if not isinstance(raw, str):
            raw = str(raw)
        try:
            return json.loads(raw), raw
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Open Design visual translation response did not contain valid JSON.")
        return json.loads(match.group()), raw

    def _call_claude(self, prompt: str):
        try:
            return self.claude.run(prompt=prompt, max_tokens=5000, temperature=0.25)
        except TypeError:
            return self.claude.run(prompt=prompt)

    def _visual_input_for_post(
        self,
        post: Dict[str, Any],
        organic_output: Dict[str, Any],
        organic_strategy_output: Dict[str, Any],
        skill_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "identifiers": {
                "brand_id": organic_output.get("brand_id"),
                "niche_id": organic_output.get("niche_id"),
                "page_id": organic_output.get("page_id"),
                "campaign_id": organic_output.get("campaign_id"),
                "organic_run_id": organic_output.get("organic_run_id"),
                "post_id": post.get("post_id"),
                "platform_id": post.get("platform_id") or organic_output.get("platform_id"),
            },
            "open_design_skill_context": skill_context,
            "strategy_context": {
                "strategy_mode": organic_strategy_output.get("strategy_mode"),
                "event_context": organic_strategy_output.get("event_context"),
                "organic_execution_strategy": organic_strategy_output.get("organic_execution_strategy"),
                "social_engagement_layer": organic_strategy_output.get("social_engagement_layer"),
                "alysha_do_not_do": (
                    organic_strategy_output.get("alysha_strategy_source", {}).get("do_not_do")
                    or organic_strategy_output.get("alysha_compliance", {}).get("protected_alysha_snapshot", {}).get("do_not_do")
                    or []
                ),
            },
            "exact_post_source": {
                "hook": post.get("hook"),
                "post_text": post.get("post_text"),
                "engagement_prompt": post.get("engagement_prompt"),
                "target_human": post.get("target_human"),
                "current_emotional_state": post.get("current_emotional_state"),
                "core_problem": post.get("core_problem"),
                "core_solution": post.get("core_solution"),
                "primary_takeaway": post.get("primary_takeaway"),
                "desired_post_outcome": post.get("desired_post_outcome"),
                "desired_action": post.get("desired_action"),
                "content_archetype": post.get("content_archetype"),
                "interaction_trigger_type": post.get("interaction_trigger_type"),
                "content_role": post.get("content_role"),
                "content_pillar": post.get("content_pillar"),
                "angle_used": post.get("angle_used"),
                "hook_type": post.get("hook_type"),
                "product_mention_level": post.get("product_mention_level"),
                "image_intent": post.get("image_intent"),
                "product_reference_required": post.get("product_reference_required"),
                "product_reference_note": post.get("product_reference_note"),
                "content_tags": post.get("content_tags"),
                "seo_keywords_used": post.get("seo_keywords_used"),
            },
            "output_contract": {
                "g_sheet_field": "chatgpt_image_prompt",
                "json_runtime_fields": [
                    "text_to_visual_alignment",
                    "open_design_visual_spec",
                    "open_design_master_prompt",
                    "chatgpt_image_prompt",
                    "comfyui_prompt_bundle",
                ],
            },
        }

    def _fallback_package(self, post: Dict[str, Any]) -> Dict[str, Any]:
        image_intent = self._clean_str(post.get("image_intent"))
        hook = self._clean_str(post.get("hook"))
        takeaway = self._clean_str(post.get("primary_takeaway"))
        base = ". ".join([x for x in [image_intent, hook, takeaway] if x])
        prompt = (
            f"{base}. Subject and composition must visually reflect the post text exactly. "
            "Clear focal point, social-media-ready 1:1 composition, emotionally coherent, no text overlay."
        ).strip()
        return {
            "text_to_visual_alignment": {
                "core_text_message": takeaway or hook,
                "visual_objective": image_intent or takeaway or hook,
                "must_show": [image_intent] if image_intent else [],
                "must_feel": [self._clean_str(post.get("current_emotional_state"))] if self._clean_str(post.get("current_emotional_state")) else [],
                "must_avoid": ["visuals that contradict the post text"],
            },
            "open_design_visual_spec": {
                "subject_and_composition": image_intent or hook,
                "lighting_and_mood": self._clean_str(post.get("current_emotional_state")) or "natural, emotionally aligned",
                "palette_and_textures": "brand-aligned, clean, social-feed friendly",
                "camera_or_lens": "natural realism when people are present",
                "what_to_avoid": ["text overlay", "watermarks", "visuals unrelated to the post"],
            },
            "open_design_master_prompt": prompt,
            "chatgpt_image_prompt": prompt,
            "comfyui_prompt_bundle": {
                "positive_prompt": prompt,
                "negative_prompt": "low quality, blurry, watermark, text overlay, distorted anatomy, visuals unrelated to the post",
            },
            "translation_status": "fallback_generated",
        }

    def translate_output(
        self,
        organic_output: Dict[str, Any],
        organic_strategy_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        skill_context = self._load_open_design_skill_excerpt()
        translated = []
        errors = []
        posts = organic_output.get("organic_posts", []) or []

        for post in posts:
            visual_input = self._visual_input_for_post(post, organic_output, organic_strategy_output, skill_context)
            prompt = self.prompt_loader.render(
                self.prompt_file,
                {"OPEN_DESIGN_VISUAL_INPUT": json.dumps(visual_input, ensure_ascii=False, indent=2)},
            )
            try:
                parsed, raw = self._parse_json_response(self._call_claude(prompt))
                package = parsed
                package["translation_status"] = package.get("translation_status") or "ok"
                package["raw_response_excerpt"] = raw[:1200]
            except Exception as exc:
                package = self._fallback_package(post)
                package["translation_error"] = str(exc)
                errors.append({"post_id": post.get("post_id"), "error": str(exc)})

            post["open_design_visual_package"] = package
            post["text_to_visual_alignment"] = package.get("text_to_visual_alignment") or {}
            post["open_design_visual_spec"] = package.get("open_design_visual_spec") or {}
            post["open_design_master_prompt"] = self._clean_str(package.get("open_design_master_prompt"))
            post["comfyui_prompt_bundle"] = package.get("comfyui_prompt_bundle") or {}

            chatgpt_prompt = self._clean_str(package.get("chatgpt_image_prompt"))
            if not chatgpt_prompt:
                chatgpt_prompt = self._fallback_package(post)["chatgpt_image_prompt"]
            post["chatgpt_image_prompt"] = chatgpt_prompt
            post["chatgpt_image_prompt_source"] = "open_design_visual_translation"

            translated.append({
                "post_id": post.get("post_id"),
                "translation_status": package.get("translation_status"),
                "chatgpt_prompt_ready": bool(chatgpt_prompt),
                "comfyui_prompt_ready": bool((package.get("comfyui_prompt_bundle") or {}).get("positive_prompt")),
            })

        return {
            "posts_translated": len(translated),
            "open_design_skill_source": skill_context.get("source"),
            "translated_posts": translated,
            "errors": errors,
        }
