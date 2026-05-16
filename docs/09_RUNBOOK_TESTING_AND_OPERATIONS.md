# 09 — Runbook, Testing, and Operations

## A. Generate organic content

Command:
```bash
python -m core.jobs.daily_generate_organic_job
```

Expected:
- status success,
- rows appended to Organic_Posts,
- strategy output path returned,
- organic output path returned.

### Inspect after run

1. `organic_alysha_source_output.json`
2. `organic_strategy_output.json`
3. `organic_output.json`
4. `organic_posts/comfyui/` folder
5. GSheet `Organic_Posts`

## B. Validate evergreen strategy

If `Page_Channel_Library.notes` is blank/non-event:
```text
strategy_mode = evergreen_growth
```

No stale event strategy should leak into generated posts.

## C. Validate Open Design and ComfyUI

In `organic_output.json`, confirm:
- `open_design_visual_translation.posts_translated > 0`
- `comfyui_preparation.workflows_prepared > 0`

Each post should contain:
- `text_to_visual_alignment`
- `open_design_visual_spec`
- `chatgpt_image_prompt`
- `comfyui_positive_prompt`
- `comfyui_negative_prompt`
- `comfyui_workflow_file`
- `comfyui_config_file`

## D. Test Facebook schedule in dry run

Set:
```env
FACEBOOK_PUBLISH_DRY_RUN=true
```

Command:
```bash
python -m core.jobs.daily_schedule_facebook_job
```

Expected for processable rows:
```text
scheduled_dry_run
```

If:
```text
processed = 0
```
then likely no row has:
```text
post_status = ready
```

## E. Real Facebook schedule/publish

Set:
```env
FACEBOOK_PUBLISH_DRY_RUN=false
```

Command:
```bash
python -m core.jobs.daily_schedule_facebook_job
```

Expected:
- processed rows > 0,
- status moves to `posted`,
- `facebook_post_id` filled,
- Facebook Business Manager shows scheduled post if schedule time is future.

## F. Test hashtag publishing

Given sheet cell:
```text
#VietnameseCoffee|#CoffeeHeritage|#VietnameseFamily
```

Published caption should append:
```text
#VietnameseCoffee #CoffeeHeritage #VietnameseFamily
```

Not:
```text
##VietnameseCoffee
```

## G. Collect organic results

Command:
```bash
python -m core.jobs.daily_collect_organic_results_job
```

Rows only collect after:
- post status posted,
- real Facebook post ID,
- next target-market calendar day.

Expected output summary:
- rows collected,
- Organic_Results updated,
- Daily_Learning_Log updated,
- local organic learning JSONL updated.

## H. Troubleshooting checklist

### 1. Scheduler skipped all rows
Check:
- `post_status = ready`
- route mapping,
- page URL,
- target timezone,
- dry-run mode.

### 2. Strategy still uses old event messaging
Check:
- `Page_Channel_Library.notes`
- `organic_alysha_source_output.json`
- `source_mode`
- whether source was refreshed.

### 3. ComfyUI folder missing
Check:
- current `organic_generation_service.py` includes:
  - `OpenDesignVisualTranslationService`
  - `ComfyUIPreparationService`
- organic job has run after patch application.

### 4. Collector returns metric "-"
Check:
- Graph API metric availability,
- post/photo object compatibility,
- token permissions,
- Meta metric support.

`-` is intentional for unavailable metrics; it is not the same as 0.

## I. Recommended files to send for debugging

### Organic generation issue
- terminal output,
- `organic_alysha_source_output.json`,
- `organic_strategy_output.json`,
- `organic_output.json`.

### Scheduler issue
- terminal output,
- one affected Organic_Posts row,
- `.env` publish mode,
- current `facebook_page_publisher.py`.

### Results issue
- terminal output,
- one posted row,
- collector JSON output,
- row error detail if present.
