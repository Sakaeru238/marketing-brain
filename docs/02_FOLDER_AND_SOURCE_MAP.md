# 02 — Folder and Source Map

## Source code ownership map

### Organic generation flow

```text
core/jobs/daily_generate_organic_job.py
```
Entry point job. Finds generation tasks and calls `OrganicGenerationService`.

```text
core/services/organic_generation_service.py
```
High-level organic generation orchestration:
- load page context and KPI,
- review/create organic strategy,
- generate organic posts,
- run Open Design visual translation,
- prepare ComfyUI files,
- write organic output JSON,
- export rows to Organic_Posts,
- send Telegram summary.

```text
core/services/organic_alysha_source_service.py
```
Creates the organic-specific upstream Alysha source:
- `evergreen_growth` when notes is blank/non-event,
- `event_aware` only when notes begins with `event:`,
- writes `organic_alysha_source_output.json`.

```text
core/services/organic_strategy_service.py
```
Builds and reviews `organic_strategy_output.json`.
Responsible for:
- Alysha mapping audit,
- protected strategy sections,
- execution strategy,
- daily learning adjustment,
- stable revision decisions,
- Telegram strategy-change metadata.

```text
core/services/open_design_visual_translation_service.py
```
Per-post visual translation:
- input: exact post text and metadata,
- output: visual spec, ChatGPT prompt, ComfyUI prompt bundle.

```text
core/services/comfyui_preparation_service.py
```
Runtime JSON preparation:
- uses Open Design output,
- injects into workflow template,
- writes per-post ComfyUI workflow/config files.

### Data prompts and templates

```text
data/prompts/organic/organic_alysha_source_prompt.txt
data/prompts/organic/organic_strategy_review_prompt.txt
data/prompts/organic/organic_generation_prompt.txt
data/prompts/organic/open_design_visual_translation_prompt.txt
```

```text
data/templates/comfyui/organic_social_image_template.json
```

### Facebook scheduling / publishing

```text
core/jobs/publish_ready_organic_posts_to_facebook_job.py
```
Reads `Organic_Posts`, filters `ready`, schedules/publishes Facebook posts, writes job-control fields.

```text
core/services/facebook_page_publisher_service.py
```
Schedules a feed post or photo post.  
Also appends `content_tags` as Facebook hashtags.

```text
core/publishers/facebook_graph_client.py
```
Graph API client used by scheduler and collector.

```text
core/utils/facebook_publish_validator.py
```
Validates publishable rows and scheduling constraints.

```text
core/publishers/facebook_publish_logger.py
```
Publisher logs.

### Google Sheets and context loading

```text
core/exporters/google_sheets_exporter.py
```
Sheet read/write helpers and output upserts.

```text
core/campaign/page_campaign_context_loader.py
```
Loads `Campaign_Config` row and campaign/page context.

```text
core/campaign/campaign_kpi_calculator.py
```
Computes KPI pressure fields:
- gap,
- days remaining,
- required growth/day,
- content intensity.

```text
config/google_sheet_routing.json
```
Maps brand/platform/page route to actual Google Sheet and real Meta page ID.

### Results collection and learning

```text
core/jobs/daily_collect_organic_results_job.py
```
Collector job:
- reads posted rows,
- fetches Graph API content/insights,
- writes Organic_Results,
- writes Daily_Learning_Log,
- updates local learning memory.

```text
core/services/organic_results_learning_service.py
```
Turns metrics into:
- Vietnamese learning text for GSheet,
- English learning memory for local JSONL.

```text
core/learning/organic_learning_memory_store.py
```
Stores English canonical memory:

```text
data/knowledge/organic_learning/{brand_id}/{brand_id}_{page_id}.jsonl
```

## Runtime output map

These are **not source files**:

```text
data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/
  organic_alysha_source_output.json
  organic_strategy_output.json
  organic_output.json
  comfyui/
    {post_id}_comfyui_workflow.json
    {post_id}_comfyui_config.json
```

Do not manually edit runtime outputs as if they were code.  
Use them for inspection, debugging, and postmortems.

## What not to duplicate

Do **not** create a second version of:
- page context loader,
- KPI calculator,
- organic strategy service,
- visual translation service,
- ComfyUI preparation service,
- Facebook scheduler job,
- results collector job,
- local learning memory store.

Enhance the existing implementation instead.

## Current patch lineage warning

Later patches supersede older patches.  
Do not apply old ZIPs over newer source.

The current intended logic includes:
- evergreen Alysha organic source,
- Open Design per-post visual translation,
- ComfyUI workflow preparation,
- Facebook hashtag publisher fix,
- results collector with Daily Learning Log and JSONL memory.
