# Marketing Brain — Canonical Docs Index

This `docs/` folder is the canonical handoff package for the current Marketing Brain organic-content pipeline.

It is written so that:
- another engineer can continue implementation,
- another ChatGPT tab can resume work without re-discovering decisions,
- production fixes do not accidentally duplicate existing functions,
- runtime outputs are not mistaken for source files,
- legacy patches do not overwrite newer logic.

## Current system scope

The currently integrated flow is:

```text
Page_Channel_Library + routing + KPI context
→ Organic Alysha Source Strategy
→ Organic Strategy Review / Translation
→ Organic Post Generation
→ Open Design visual translation per post
→ ChatGPT image prompt for Google Sheet
→ ComfyUI workflow/config JSON preparation
→ Organic_Posts sheet export
→ Facebook scheduling/publishing
→ Organic results collection
→ Daily learning log + local JSONL memory
→ next organic strategy/generation uses recent learning
```

## Canonical documents

1. [`01_SYSTEM_OVERVIEW.md`](01_SYSTEM_OVERVIEW.md)  
   End-to-end architecture and current working state.

2. [`02_FOLDER_AND_SOURCE_MAP.md`](02_FOLDER_AND_SOURCE_MAP.md)  
   Source file ownership, where code lives, and what not to duplicate.

3. [`03_GSHEET_AND_DATA_CONTRACTS.md`](03_GSHEET_AND_DATA_CONTRACTS.md)  
   Sheet tabs, row contracts, required fields, and status rules.

4. [`04_STRATEGY_LAYER_ALYSHA_AND_ORGANIC.md`](04_STRATEGY_LAYER_ALYSHA_AND_ORGANIC.md)  
   Alysha source-of-truth logic, evergreen/event routing, and output standards.

5. [`05_ORGANIC_GENERATION_OPEN_DESIGN_AND_COMFYUI.md`](05_ORGANIC_GENERATION_OPEN_DESIGN_AND_COMFYUI.md)  
   Organic post generation, text-to-visual mapping, ChatGPT prompt output, and ComfyUI JSON output.

6. [`06_FACEBOOK_SCHEDULER_AND_PUBLISHER.md`](06_FACEBOOK_SCHEDULER_AND_PUBLISHER.md)  
   Scheduling, timezone logic, hashtag formatting, dry run vs real run.

7. [`07_RESULTS_COLLECTION_AND_LEARNING.md`](07_RESULTS_COLLECTION_AND_LEARNING.md)  
   Facebook results collection, metrics rules, AI learning, Daily_Learning_Log, local memory.

8. [`08_RUNTIME_OUTPUT_LOCATIONS.md`](08_RUNTIME_OUTPUT_LOCATIONS.md)  
   Exact output folders and files created by jobs.

9. [`09_RUNBOOK_TESTING_AND_OPERATIONS.md`](09_RUNBOOK_TESTING_AND_OPERATIONS.md)  
   Commands to run, what to expect, and what files to inspect.

10. [`10_CURRENT_STATE_KNOWN_ISSUES_AND_NEXT_WORK.md`](10_CURRENT_STATE_KNOWN_ISSUES_AND_NEXT_WORK.md)  
    What is confirmed working, what remains open, and next recommended fixes.

11. [`11_CONTRIBUTOR_GUARDRAILS.md`](11_CONTRIBUTOR_GUARDRAILS.md)  
    Rules for future developers/AI: do not duplicate functions, do not write failed artifacts into production folders, patch safely.

12. [`12_REPO_STANDARDS_AND_EXTERNAL_REFERENCES.md`](12_REPO_STANDARDS_AND_EXTERNAL_REFERENCES.md)  
    Repos/standards being used: Alysha, creative strategy mapping, Open Design, ComfyUI.

## Canonical vs legacy docs

These files are the recommended starting point.  
Older docs that may still exist in a local checkout should be treated as historical unless they are explicitly referenced by this index.

Do **not** blindly apply old patch ZIPs over the newest code.  
This project has had sequential patches, and later patches supersede earlier ones.

## Current most important implementation files

```text
core/jobs/daily_generate_organic_job.py
core/services/organic_alysha_source_service.py
core/services/organic_strategy_service.py
core/services/organic_generation_service.py
core/services/open_design_visual_translation_service.py
core/services/comfyui_preparation_service.py

core/jobs/daily_schedule_facebook_job.py
core/publishers/facebook_page_publisher.py
core/publishers/facebook_graph_client.py
core/publishers/facebook_publish_validator.py

core/jobs/daily_collect_organic_results_job.py
core/services/organic_results_learning_service.py
core/learning/organic_learning_memory_store.py
core/exporters/google_sheets_exporter.py
```

## Current high-level verified status

Verified in testing:
- organic generation job runs successfully,
- evergreen organic source is generated when `notes` is not an event,
- Mother’s Day event strategy is no longer reused for evergreen growth content,
- Open Design produces per-post visual packages,
- ChatGPT image prompts are exported for GSheet use,
- ComfyUI workflow/config JSON files are generated per post,
- Organic_Posts receives generated rows,
- Facebook scheduler correctly filters only `post_status = ready`,
- organic results collector logic exists for results + learning + local JSONL memory.

One currently observed flow issue remains:
- generated rows in `Organic_Posts` were observed with `post_status = posted`, while scheduler expects `ready`. This prevents scheduler processing until fixed or manually changed. See `10_CURRENT_STATE_KNOWN_ISSUES_AND_NEXT_WORK.md`.
