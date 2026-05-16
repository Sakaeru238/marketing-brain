# 05 — Organic Generation, Open Design, and ComfyUI

## Organic generation job

Entry point:
```bash
python -m core.jobs.daily_generate_organic_job
```

Main orchestration:
```text
OrganicGenerationService
```

## Organic generation input

The service builds an input bundle containing:
- `brand_id`
- `niche_id`
- `page_id`
- `platform_id`
- `campaign_id`
- page context
- campaign KPI context
- organic strategy output
- recent organic learning memory
- generation rules

## Organic generation output

The post generator creates:
- content metadata,
- post text,
- hook,
- content tags,
- SEO keywords,
- intended post outcome,
- image intent,
- product reference note.

### Important image rule
The organic post generator **does not** produce final `chatgpt_image_prompt`.

Instead:
```text
post text + image_intent + product_reference_note
→ Open Design
→ final prompt packages
```

This prevents visual prompts from being detached from the actual caption.

## Open Design visual translation

Service:
```text
core/services/open_design_visual_translation_service.py
```

It runs **per post**, not per batch.

### Required input for each post
The visual layer must receive the corresponding post’s:
- post ID,
- hook,
- post text,
- engagement prompt,
- target human,
- core problem,
- core solution,
- primary takeaway,
- desired action,
- content pillar,
- angle used,
- image intent,
- product reference note.

## Open Design output package

Each post receives:

```text
open_design_visual_package
text_to_visual_alignment
open_design_visual_spec
open_design_master_prompt
chatgpt_image_prompt
comfyui_prompt_bundle
```

### `text_to_visual_alignment`
Explains:
- core text message,
- visual objective,
- why the visual matches the post,
- must show,
- must feel,
- must avoid.

### `open_design_visual_spec`
Defines:
- subject and composition,
- lighting and mood,
- palette and textures,
- camera/lens,
- what to avoid.

### `chatgpt_image_prompt`
This is the prompt exported to GSheet.

### `comfyui_prompt_bundle`
Contains:
- `positive_prompt`
- `negative_prompt`

## Why Open Design owns both image branches

The goal is not pixel-identical outputs across image engines.  
The goal is **consistent visual intent and comparable creative quality** across:
- ChatGPT/OpenAI image generation,
- ComfyUI.

Therefore:

```text
Open Design visual truth
→ ChatGPT prompt
→ ComfyUI prompts/workflow
```

## ComfyUI preparation

Service:
```text
core/services/comfyui_preparation_service.py
```

Template:
```text
data/templates/comfyui/organic_social_image_template.json
```

Per-post output folder:
```text
data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/comfyui/
```

Files:
```text
{post_id}_comfyui_workflow.json
{post_id}_comfyui_config.json
```

## Runtime JSON vs GSheet split

### Runtime JSON keeps everything
`organic_output.json` stores:
- organic post data,
- full Open Design package,
- ChatGPT prompt,
- ComfyUI positive/negative prompt,
- ComfyUI file paths,
- preparation summary.

### GSheet keeps operationally useful output
`Organic_Posts` stores:
- post content,
- `chatgpt_image_prompt`,
- scheduling fields,
- publisher fields.

GSheet does **not** need full ComfyUI internals.

## Quality standard for visual mapping

A prompt is acceptable only when:
- it clearly supports the post hook,
- it reflects the desired emotion,
- it reinforces the post’s angle,
- it avoids conflicting claims or visuals,
- it is not generic batch filler.

## Current verified result

Latest test produced:
- 4 posts,
- 4 Open Design translations,
- 4 ChatGPT prompts,
- 4 ComfyUI workflow/config pairs.
