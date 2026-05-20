# 03 — Google Sheet and Data Contracts

## Main Google Sheet tabs

The current organic flow depends on these sheet tabs:

```text
Campaign_Config
Organic_Posts
Organic_Results
Daily_Learning_Log
```

## 1. Campaign_Config

### Purpose
This is the page-level operating context and the main per-page strategy router.

### Important identifiers
All IDs must be taken from this sheet / routing layer.  
Do **not** invent IDs in code.

Typical important columns:
- `brand_id`
- `niche_id`
- `page_id`
- `page_url`
- `platform_id`
- `market`
- `language`
- `target_timezone`
- `campaign_id`
- KPI columns such as current/target followers and likes
- `notes`

### Event routing rule

`notes` controls evergreen vs event-aware organic strategy:

```text
notes = ""                         → evergreen_growth
notes = "Test Facebook system"     → evergreen_growth
notes = "event: Mother's Day"      → event_aware
notes = "event: Black Friday"      → event_aware
```

Only a note starting with:

```text
event:
```

is treated as an event marker.

## 2. Organic_Posts

### Purpose
Operational post queue for generated content and publishing.

### Generator output
Organic generation exports rows here.

Expected row concepts:
- identity: `post_id`, `organic_run_id`, `brand_id`, `page_id`, `campaign_id`, `platform_id`
- content: `post_text`, hook, content role, content pillar, desired action, tags
- visual prompt: `chatgpt_image_prompt`
- scheduling: `scheduled_datetime_utc`, posting window
- publisher fields: `post_status`, `publisher_status`, `facebook_post_id`, `publisher_error`

### GSheet visual output rule

GSheet stores only the user-facing ChatGPT prompt:

```text
chatgpt_image_prompt
```

GSheet does **not** need:
- full Open Design spec,
- ComfyUI positive/negative prompts,
- workflow JSON file paths,
- ComfyUI config JSON content.

Those stay in runtime JSON output.

### `content_tags` storage rule

Keep GSheet content exactly in pipe-separated form, including existing hashtags:

```text
#VietnameseCoffee|#CoffeeHeritage|#VietnameseFamily|#CoffeeTradition|#AuthenticCoffee
```

Do **not** remove `#` from sheet storage.

During Facebook publishing, publisher converts it into:

```text
#VietnameseCoffee #CoffeeHeritage #VietnameseFamily #CoffeeTradition #AuthenticCoffee
```

and avoids creating `##VietnameseCoffee`.

### Publisher status contract

Scheduler processes only:

```text
post_status = ready
```

On success, scheduler updates:

```text
post_status = posted
publisher_status = scheduled or published
facebook_post_id = API returned ID
```

On error:

```text
post_status = error
publisher_status = validation_error or error
publisher_error = explanation
```

## 3. Organic_Results

### Purpose
Stores collected result metrics for posts already published/scheduled successfully.

### Collector eligibility
A row is collectable only if:
- `platform_id = facebook`
- `post_status = posted`
- `facebook_post_id` exists and is not `dryrun_*`
- current target-market calendar day is later than post local date

The old strict “24 hours after post” rule is replaced by:
```text
collect on the next local calendar day
```

### Current metric rules

For Facebook:
- `likes`, `comments`, `shares` are collected from content object where available.
- `reach`, `impressions`, `clicks` are collected from Graph API insights when available.
- If unavailable, write `-`, not ambiguous blank.
- `saves = -`
- `follows = -`

### Engagement rate

Current rule:

```text
engagement_rate =
  sum(available likes, comments, shares, clicks)
  / first valid denominator of reach, else impressions
  * 100
```

If no valid denominator exists:
```text
engagement_rate = "-"
```

If all numerator engagement metrics are unavailable:
```text
engagement_rate = "-"
```

### AI learning fields

The sheet receives Vietnamese text:
- `ai_result_summary`
- `ai_learning`
- `ai_next_action`

## 4. Daily_Learning_Log

### Purpose
Daily aggregate content learning for future strategy review and post planning.

This tab is updated by results collector.

It stores Vietnamese learning summaries such as:
- winning roles,
- weak roles,
- winning hooks,
- weak hooks,
- next-day content direction,
- whether strategy review is needed.

## Google Sheet write discipline

Jobs should write only their designated fields:
- generator writes content/planning rows,
- scheduler writes job-control/publisher fields,
- collector writes results and learning outputs.

Do **not** allow the scheduler to rewrite content text or image prompts.
