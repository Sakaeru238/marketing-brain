# 08 — Runtime Output Locations

## Output root

Campaign/page runtime artifacts live under:

```text
data/output/{brand_id}/{page_id}/{campaign_id}/
```

## Organic outputs

```text
data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/
```

### Files

```text
organic_alysha_source_output.json
organic_strategy_output.json
organic_output.json
```

### Meaning

#### `organic_alysha_source_output.json`
Upstream organic-specific strategy source:
- evergreen or event-aware,
- derived from reference strategy + page notes + KPI,
- source of truth for organic strategy translation.

#### `organic_strategy_output.json`
Operational organic strategy:
- Alysha compliance mapping,
- organic execution strategy,
- KPI pressure layer,
- social engagement layer,
- learning adjustments,
- update history.

#### `organic_output.json`
Generated content batch:
- all organic posts,
- Open Design output packages,
- ChatGPT image prompts,
- ComfyUI prompt bundles,
- workflow file paths,
- preparation summaries.

## ComfyUI per-post artifacts

```text
data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/comfyui/
```

Files:
```text
{post_id}_comfyui_workflow.json
{post_id}_comfyui_config.json
```

### Workflow JSON
Ready-to-run or runtime-prepared ComfyUI graph JSON using the post’s visual prompt data.

### Config JSON
Trace metadata:
- brand ID,
- page ID,
- campaign ID,
- organic run ID,
- post ID,
- prompt source,
- workflow file path,
- positive prompt,
- negative prompt,
- prepared status.

## Local learning memory

```text
data/knowledge/organic_learning/{brand_id}/{brand_id}_{page_id}.jsonl
```

This is not a one-off debug log.  
It is reusable memory for future organic strategy/generation.

## Sheets vs local runtime

### Google Sheets
Operationally visible / human-reviewable:
- Organic_Posts
- Organic_Results
- Daily_Learning_Log

### Local runtime
Traceable machine artifacts:
- organic strategy source,
- organic strategy,
- organic output,
- ComfyUI files,
- learning JSONL.

## Do not store

Do not write:
- failed half-generated JSON into production output paths unless it is explicitly marked with an error schema,
- temporary debug dumps into the same canonical folders,
- obsolete patch outputs under runtime campaign folders.

Use a separate debug/temp location if needed.
