# 07 — Results Collection and Learning

## Collector entry point

```bash
python -m core.jobs.daily_collect_organic_results_job
```

## Collector scope

The collector:
1. reads `Organic_Posts`,
2. filters collectable Facebook posts,
3. fetches content details + insights from Graph API,
4. writes `Organic_Results`,
5. writes `Daily_Learning_Log`,
6. writes local JSONL learning memory.

## Collectable row rule

A row is collectable only when:
- `platform_id = facebook`
- `post_status = posted`
- `facebook_post_id` exists
- `facebook_post_id` is not a dry run ID
- the target audience local calendar date is now later than the post date

This replaces the former:
```text
age >= 24h
```
rule.

## Results timing rule

The collector runs at a daily time such as 2 PM, but collection eligibility is based on:
```text
next target-market calendar day
```

Example:
- post date in target timezone = May 12
- results become collectable on May 13 in that timezone

## Facebook content fetching

The collector uses:
```text
FacebookGraphClient.get_content_details(...)
```

It handles post/photo object differences and resolves a canonical permalink when possible.

`post_url` should be the actual canonical Page Post permalink, not an internal or malformed photo link.

## Metrics

### Post-level counters
Collected where available:
- likes
- comments
- shares

### Insights metrics
Collector accepts modern and legacy Graph metric names, mapping to:
- impressions
- reach
- clicks

If a Graph API metric is not available:
```text
write "-"
```

### Platform-specific unavailable metrics
For Facebook:
```text
saves = "-"
follows = "-"
```

## Engagement rate

Formula:

```text
engagement_rate =
  (likes + comments + shares + clicks) / denominator * 100
```

Rules:
- use only available numerator components,
- denominator priority:
  1. reach
  2. impressions
- if no denominator: `-`,
- if all numerator components unavailable: `-`.

## Learning enrichment

Service:
```text
core/services/organic_results_learning_service.py
```

It creates:
- Vietnamese sheet-facing AI fields,
- English local memory fields.

### Google Sheet language
These are Vietnamese:
- `ai_result_summary`
- `ai_learning`
- `ai_next_action`
- Daily_Learning_Log fields

### Local memory language
These remain English:
- `ai_result_summary_en`
- `ai_learning_en`
- `ai_next_action_en`

The English JSONL memory is the canonical learning layer reused by future organic generation.

## Daily_Learning_Log

The daily aggregate log captures:
- growth goal,
- today's content goal,
- posts reviewed,
- best/worst post,
- winning and weak roles,
- winning and weak pillars,
- winning and weak hooks,
- audience signals,
- next-day recommendation.

## Local organic learning memory

Path:

```text
data/knowledge/organic_learning/{brand_id}/{brand_id}_{page_id}.jsonl
```

Example:
```text
data/knowledge/organic_learning/AODAI/AODAI_61585442436771.jsonl
```

Each JSONL record includes:
- learning key,
- date,
- brand/page/campaign/run IDs,
- post IDs,
- metrics,
- AI learning text,
- AI next action.

## Upsert identity

Local memory upsert key:
```text
date + facebook_post_id
```

This prevents duplicate learning lines on reruns.

## Feed-back loop

Next organic strategy/generation can load recent memory:
```text
OrganicLearningMemoryStore.load_recent(...)
```

and use it to:
- revise daily organic execution,
- increase/decrease content types,
- inform next content batch.

## Current Graph API caveat

Some metrics may be unavailable for a valid Facebook object/token/version even if Business Manager UI shows a number.  
Collector should preserve available metrics and mark missing fields with `-` rather than failing the whole row.
