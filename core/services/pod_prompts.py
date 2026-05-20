from __future__ import annotations

from typing import Any

from .pod_pipeline_utils import compact_json


STRATEGY_SYSTEM_PROMPT = """
You are executing the POD adaptation of Alysha's creative-strategy-engine.
Your output must be a JSON object only, no Markdown fences.
Do not write a design brief. Do not write image prompts.
"""


def build_pod_strategy_prompt(
    *,
    brand_context: dict[str, Any],
    brand_learning: dict[str, Any] | None,
    campaign_intake: dict[str, Any],
    product_catalog_entry: dict[str, Any],
) -> str:
    return f"""
Create a POD Strategy Output.

INPUT 1 — Brand Context Source of Truth:
{compact_json(brand_context)}

INPUT 2 — Brand Learning:
{compact_json(brand_learning or {"status": "no_learning_available"})}

INPUT 3 — POD Campaign Intake:
{compact_json(campaign_intake)}

INPUT 4 — Product Catalog:
{compact_json(product_catalog_entry)}

The strategy must answer:
- This campaign targets which persona?
- Which pain / desire / belief matters most?
- Which strategic angles should lead the campaign?
- What is the core message?
- Why does this concept fit the brand and the chosen SKU/product?

Return exactly:
{{
  "stage": "pod_strategy_output",
  "strategy_version": "v001",
  "strategy_summary": {{
    "campaign_opportunity": "",
    "campaign_positioning": "",
    "brand_fit_rationale": "",
    "sku_fit_rationale": "",
    "campaign_fit_rationale": ""
  }},
  "target_persona": {{
    "primary_persona": "",
    "secondary_persona_if_relevant": "",
    "audience_signals": []
  }},
  "customer_psychology": {{
    "pain_points": [],
    "desires": [],
    "beliefs": [],
    "objections": [],
    "purchase_triggers": []
  }},
  "priority_angles": [
    {{
      "angle_name": "",
      "why_it_matters": "",
      "how_it_connects_to_persona": "",
      "fit_with_brand_and_sku": ""
    }}
  ],
  "core_message": {{
    "main_message": "",
    "supporting_messages": []
  }},
  "creative_strategy_guardrails": {{
    "must_preserve": [],
    "must_avoid": [],
    "ip_or_brand_safety_notes": []
  }},
  "recommended_direction_for_brief": {{
    "brief_should_emphasize": [],
    "brief_should_not_drift_into": [],
    "design_problem_to_solve": ""
  }},
  "confidence_notes": {{
    "confirmed_from_inputs": [],
    "inferred": [],
    "unknown_or_needs_human_confirmation": []
  }}
}}
"""


BRIEF_SYSTEM_PROMPT = """
You are adapting julianoczkowski/designer-skills to produce a POD Design Brief.
Your output must be a JSON object only, no Markdown fences.
"""


def build_pod_design_brief_prompt(
    *,
    brand_context: dict[str, Any],
    campaign_intake: dict[str, Any],
    product_catalog_entry: dict[str, Any],
    strategy_output: dict[str, Any],
    revision_feedback: dict[str, Any] | None = None,
) -> str:
    feedback_block = ""
    if revision_feedback:
        feedback_block = f"""
REVISION FEEDBACK FROM DEEPEVAL:
{compact_json(revision_feedback)}

The revised brief must address every failed point.
"""
    return f"""
Create a POD Design Brief from the strategy.

BRAND CONTEXT:
{compact_json(brand_context)}

CAMPAIGN INTAKE:
{compact_json(campaign_intake)}

PRODUCT CATALOG ENTRY:
{compact_json(product_catalog_entry)}

POD STRATEGY OUTPUT:
{compact_json(strategy_output)}

{feedback_block}

Rules:
- Preserve Alysha strategy, persona, priority angles, and core message.
- Preserve must_keep / must_avoid constraints from campaign intake.
- The only official visual output groups are:
  - flat_mockup
  - worn_mockup
  - lifestyle_scene
- Any ad-style / contextual / promotional scene request must go into lifestyle_scene.
- The brief must be execution-ready for Open Design / Generative Media Translation.

Return exactly:
{{
  "stage": "pod_design_brief",
  "brief_version": "v001",
  "design_objective": {{
    "core_message": "",
    "why_this_design_exists": "",
    "target_emotion": [],
    "desired_customer_reaction": ""
  }},
  "strategy_alignment": {{
    "persona_alignment": "",
    "priority_angle_alignment": "",
    "brand_fit_alignment": "",
    "sku_fit_alignment": ""
  }},
  "text_to_visual_alignment": {{
    "strategy_message": "",
    "visual_translation": "",
    "why_this_visual_matches_strategy": ""
  }},
  "design_direction": {{
    "primary_style": "",
    "secondary_style_notes": "",
    "design_archetype": "",
    "composition_system": "",
    "visual_hierarchy": ""
  }},
  "must_show": [],
  "must_feel": [],
  "must_avoid": [],
  "brand_and_ip_rules": {{
    "logo_usage": "",
    "symbol_reinterpretation_allowed": false,
    "copyright_safety_notes": [],
    "forbidden_elements": []
  }},
  "product_application": {{
    "product_ref_id": "",
    "product_name_or_scope": "",
    "placement": "",
    "front_back_system": "",
    "print_area_notes": "",
    "personalization_notes": ""
  }},
  "visual_spec": {{
    "palette_direction": "",
    "typography_direction": "",
    "texture_direction": "",
    "illustration_direction": "",
    "mockup_direction": ""
  }},
  "output_groups": {{
    "flat_mockup": {{
      "required": false,
      "brief_vi": "",
      "generation_objective": "",
      "must_show": [],
      "must_avoid": []
    }},
    "worn_mockup": {{
      "required": false,
      "brief_vi": "",
      "generation_objective": "",
      "must_show": [],
      "must_avoid": []
    }},
    "lifestyle_scene": {{
      "required": false,
      "brief_vi": "",
      "generation_objective": "",
      "must_show": [],
      "must_avoid": []
    }}
  }},
  "self_review_checklist": [],
  "human_review_focus": [],
  "open_questions": []
}}
"""


TRANSLATION_SYSTEM_PROMPT = """
You are Open Design / Generative Media Translation Layer.
Convert an approved POD Design Brief into:
- ChatGPT Image Prompt(s)
- ComfyUI JSON render request(s)
Your output must be a JSON object only, no Markdown fences.
"""


def build_pod_translation_prompt(
    *,
    brand_id: str,
    campaign_id: str,
    campaign_intake: dict[str, Any],
    product_catalog_entry: dict[str, Any],
    strategy_output: dict[str, Any],
    design_brief: dict[str, Any],
) -> str:
    return f"""
Create Open Design / Generative Media Translation output.

brand_id: {brand_id}
campaign_id: {campaign_id}

CAMPAIGN INTAKE:
{compact_json(campaign_intake)}

PRODUCT CATALOG ENTRY:
{compact_json(product_catalog_entry)}

POD STRATEGY OUTPUT:
{compact_json(strategy_output)}

APPROVED POD DESIGN BRIEF:
{compact_json(design_brief)}

Rules:
- Only output required groups in design_brief.output_groups.
- job_id must be blank here. Code will assign job_id later.
- Do not claim that rendering has happened.
- The render request must be ready to send later to ComfyUI Render Worker.
- Output groups are only flat_mockup / worn_mockup / lifestyle_scene.

Return exactly:
{{
  "stage": "open_design_generative_media_translation",
  "translation_version": "v001",
  "chatgpt_image_prompts": [
    {{
      "output_group": "flat_mockup",
      "prompt": ""
    }}
  ],
  "comfyui_render_requests": [
    {{
      "brand_id": "{brand_id}",
      "campaign_id": "{campaign_id}",
      "job_id": "",
      "output_group": "flat_mockup",
      "workflow_id_hint": "",
      "generation_payload": {{
        "positive_prompt": "",
        "negative_prompt": "",
        "seed": null,
        "width": 1024,
        "height": 1024
      }},
      "metadata": {{
        "product_ref_id": "",
        "product_name_or_scope": "",
        "brief_version": "",
        "strategy_version": "",
        "attempt_no": 1
      }}
    }}
  ],
  "translation_notes": {{
    "workflow_assumptions": [],
    "items_for_render_worker_configuration": [],
    "items_for_future_iteration": []
  }}
}}
"""


VISUAL_REGENERATION_SYSTEM_PROMPT = """
You are the Central Orchestrator for a POD visual regeneration loop.
Your output must be a JSON object only, no Markdown fences.
"""


def build_pod_visual_regeneration_prompt(
    *,
    brand_id: str,
    campaign_id: str,
    campaign_intake: dict[str, Any],
    product_catalog_entry: dict[str, Any],
    strategy_output: dict[str, Any],
    design_brief: dict[str, Any],
    translation_output: dict[str, Any],
    render_result: dict[str, Any],
    visual_eval_result: dict[str, Any] | None = None,
    human_review_result: dict[str, Any] | None = None,
) -> str:
    return f"""
Create regeneration instructions for Step [4] Open Design / Generative Media Translation.

brand_id: {brand_id}
campaign_id: {campaign_id}

CAMPAIGN INTAKE:
{compact_json(campaign_intake)}

PRODUCT CATALOG ENTRY:
{compact_json(product_catalog_entry)}

POD STRATEGY OUTPUT:
{compact_json(strategy_output)}

POD DESIGN BRIEF:
{compact_json(design_brief)}

CURRENT STEP [4] TRANSLATION OUTPUT:
{compact_json(translation_output)}

STEP [5] RENDER RESULT:
{compact_json(render_result)}

STEP [6] VISUAL EVAL RESULT:
{compact_json(visual_eval_result or {{"status": "not_available"}})}

STEP [7] HUMAN REVIEW RESULT:
{compact_json(human_review_result or {{"status": "not_available"}})}

Rules:
- Preserve approved strategy and design brief unless the rejection explicitly says the brief is wrong.
- If the visual issue is prompt/payload-level, revise Step [4] instructions only.
- If the issue requires a brief rewrite, set route_back_to to "step_2_design_brief".
- Be specific enough that Step [4] can produce corrected ChatGPT prompts and ComfyUI render requests.
- Do not claim rendering has happened.

Return exactly:
{{
  "stage": "pod_visual_regeneration_instruction",
  "brand_id": "{brand_id}",
  "campaign_id": "{campaign_id}",
  "route_back_to": "step_4_open_design_translation",
  "regeneration_summary": "",
  "failed_output_groups": [],
  "prompt_revision_instructions": [],
  "payload_revision_instructions": [],
  "brief_revision_instructions_if_needed": [],
  "must_preserve": [],
  "must_change": [],
  "must_avoid": [],
  "next_attempt_guidance": {{
    "attempt_no": 2,
    "temperature_guidance": "",
    "composition_guidance": "",
    "negative_prompt_guidance": ""
  }}
}}
"""


POD_LEARNING_SYSTEM_PROMPT = """
You create concise POD learning from production pipeline evidence.
Your output must be a JSON object only, no Markdown fences.
"""


def build_pod_learning_prompt(
    *,
    brand_id: str,
    campaign_id: str,
    strategy_output: dict[str, Any],
    design_brief: dict[str, Any],
    translation_output: dict[str, Any],
    render_result: dict[str, Any],
    visual_eval_result: dict[str, Any],
    human_review_result: dict[str, Any],
) -> str:
    return f"""
Extract brand-level and POD-specific learning from the approved POD pipeline run.

brand_id: {brand_id}
campaign_id: {campaign_id}

POD STRATEGY OUTPUT:
{compact_json(strategy_output)}

APPROVED DESIGN BRIEF:
{compact_json(design_brief)}

APPROVED OPEN DESIGN TRANSLATION:
{compact_json(translation_output)}

RENDER RESULT:
{compact_json(render_result)}

VISUAL EVAL RESULT:
{compact_json(visual_eval_result)}

HUMAN REVIEW RESULT:
{compact_json(human_review_result)}

Return exactly:
{{
  "stage": "pod_learning",
  "brand_id": "{brand_id}",
  "campaign_id": "{campaign_id}",
  "brand_learning": [
    {{
      "learning_category": "visual_design",
      "learning": "",
      "confidence": "medium",
      "recommended_action": "",
      "evidence": []
    }}
  ],
  "pod_learning": [
    {{
      "learning_category": "pod_execution",
      "learning": "",
      "confidence": "medium",
      "recommended_action": "",
      "evidence": []
    }}
  ],
  "future_strategy_implications": [],
  "future_design_brief_implications": [],
  "future_render_prompt_implications": []
}}
"""
