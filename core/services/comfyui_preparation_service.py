import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List


class ComfyUIPreparationService:
    """
    Creates per-post ComfyUI workflow/config JSON files from Open Design visual packages.
    """

    def __init__(
        self,
        template_path: str = "data/templates/comfyui/organic_social_image_template.json",
    ):
        self.template_path = Path(template_path)

    def _clean_str(self, value: Any) -> str:
        return str(value or "").strip()

    def _safe_component(self, value: Any) -> str:
        raw = self._clean_str(value)
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
        return cleaned or "unknown"

    def _load_template(self) -> Dict[str, Any]:
        if self.template_path.exists():
            return json.loads(self.template_path.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"ComfyUI template not found: {self.template_path}")

    def _render_placeholders(self, node: Any, replacements: Dict[str, Any]) -> Any:
        if isinstance(node, dict):
            return {k: self._render_placeholders(v, replacements) for k, v in node.items()}
        if isinstance(node, list):
            return [self._render_placeholders(v, replacements) for v in node]
        if isinstance(node, str) and node in replacements:
            return replacements[node]
        return node

    def _prompt_bundle(self, post: Dict[str, Any]) -> Dict[str, str]:
        package = post.get("open_design_visual_package") or {}
        bundle = package.get("comfyui_prompt_bundle") or post.get("comfyui_prompt_bundle") or {}
        positive = self._clean_str(bundle.get("positive_prompt")) or self._clean_str(post.get("chatgpt_image_prompt"))
        negative = self._clean_str(bundle.get("negative_prompt")) or "low quality, blurry, watermark, text overlay, distorted anatomy"
        return {"positive_prompt": positive, "negative_prompt": negative}

    def _workflow_replacements(self, positive_prompt: str, negative_prompt: str, output_prefix: str) -> Dict[str, Any]:
        width = int(os.getenv("COMFYUI_ORGANIC_WIDTH", "1024"))
        height = int(os.getenv("COMFYUI_ORGANIC_HEIGHT", "1024"))
        steps = int(os.getenv("COMFYUI_ORGANIC_STEPS", "30"))
        cfg = float(os.getenv("COMFYUI_ORGANIC_CFG", "6.5"))
        seed_env = self._clean_str(os.getenv("COMFYUI_ORGANIC_SEED", "0"))
        seed = int(seed_env) if seed_env.isdigit() else 0
        return {
            "__CHECKPOINT__": self._clean_str(os.getenv("COMFYUI_ORGANIC_CHECKPOINT", "put_your_checkpoint_here.safetensors")),
            "__POSITIVE_PROMPT__": positive_prompt,
            "__NEGATIVE_PROMPT__": negative_prompt,
            "__WIDTH__": width,
            "__HEIGHT__": height,
            "__SEED__": seed,
            "__STEPS__": steps,
            "__CFG__": cfg,
            "__SAMPLER_NAME__": self._clean_str(os.getenv("COMFYUI_ORGANIC_SAMPLER", "dpmpp_2m")),
            "__SCHEDULER__": self._clean_str(os.getenv("COMFYUI_ORGANIC_SCHEDULER", "karras")),
            "__OUTPUT_PREFIX__": output_prefix,
        }

    def prepare_for_output(
        self,
        organic_output: Dict[str, Any],
        organic_strategy_output: Dict[str, Any],
        organic_output_file: Path,
    ) -> Dict[str, Any]:
        workflow_template = self._load_template()
        comfyui_dir = organic_output_file.parent / "comfyui"
        comfyui_dir.mkdir(parents=True, exist_ok=True)

        files: List[Dict[str, Any]] = []
        prepared = 0

        for post in organic_output.get("organic_posts", []) or []:
            post_id = self._safe_component(post.get("post_id") or f"post_{prepared + 1}")
            bundle = self._prompt_bundle(post)
            output_prefix = f"{self._safe_component(organic_output.get('brand_id'))}_{post_id}"
            replacements = self._workflow_replacements(bundle["positive_prompt"], bundle["negative_prompt"], output_prefix)
            workflow = self._render_placeholders(copy.deepcopy(workflow_template), replacements)

            workflow_file = comfyui_dir / f"{post_id}_comfyui_workflow.json"
            config_file = comfyui_dir / f"{post_id}_comfyui_config.json"
            workflow_file.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

            config = {
                "brand_id": organic_output.get("brand_id"),
                "niche_id": organic_output.get("niche_id"),
                "page_id": organic_output.get("page_id"),
                "campaign_id": organic_output.get("campaign_id"),
                "organic_run_id": organic_output.get("organic_run_id"),
                "post_id": post.get("post_id"),
                "platform_id": post.get("platform_id") or organic_output.get("platform_id"),
                "prompt_source": "open_design_visual_package.comfyui_prompt_bundle",
                "open_design_master_prompt": self._clean_str(post.get("open_design_master_prompt")),
                "chatgpt_image_prompt": self._clean_str(post.get("chatgpt_image_prompt")),
                "comfyui_positive_prompt": bundle["positive_prompt"],
                "comfyui_negative_prompt": bundle["negative_prompt"],
                "workflow_file": str(workflow_file),
                "status": "prepared_for_comfyui",
            }
            config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            post["comfyui_workflow_file"] = str(workflow_file)
            post["comfyui_config_file"] = str(config_file)
            post["comfyui_positive_prompt"] = bundle["positive_prompt"]
            post["comfyui_negative_prompt"] = bundle["negative_prompt"]
            post["image_generation_provider_ready"] = "comfyui"

            files.append({
                "post_id": post.get("post_id"),
                "workflow_file": str(workflow_file),
                "config_file": str(config_file),
            })
            prepared += 1

        return {
            "workflow_template": str(self.template_path),
            "comfyui_output_dir": str(comfyui_dir),
            "workflows_prepared": prepared,
            "files": files,
        }
