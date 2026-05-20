# 01 — System Overview

## Purpose

Marketing Brain is an AI-assisted organic content pipeline designed to:
- create organic social posts from campaign/page strategy,
- adapt strategy to page growth vs event-led content,
- generate post-specific visual instructions,
- prepare prompts for both ChatGPT image generation and ComfyUI,
- export operational data to Google Sheets,
- schedule Facebook posts,
- collect performance results,
- convert results into learning memory for future content.

## End-to-end architecture

```text
1. Input / Context
   ├─ config/google_sheet_routing.json
   ├─ Campaign_Config
   ├─ campaign KPI fields
   ├─ brand/product/campaign context
   └─ recent organic learning memory

2. Organic Strategy Source
   └─ OrganicAlyshaSourceService
      ├─ event-aware when notes begins with `event:`
      └─ evergreen growth when no event marker exists

3. Organic Strategy Translation / Review
   └─ OrganicStrategyService
      ├─ maps 100% to Alysha-required strategy sections
      ├─ protects strategy truth
      ├─ allows execution-level organic adaptation
      ├─ reviews latest learning
      └─ notifies Telegram when strategy changes

4. Organic Post Generation
   └─ OrganicGenerationService
      ├─ generates text post metadata
      ├─ does not create final image prompt directly
      ├─ outputs image intent + product reference note
      └─ passes each post into Open Design

5. Open Design Visual Translation
   └─ OpenDesignVisualTranslationService
      ├─ reads each post’s exact text/context
      ├─ builds text-to-visual alignment
      ├─ creates visual spec
      ├─ creates ChatGPT image prompt
      └─ creates ComfyUI positive/negative prompt bundle

6. ComfyUI Preparation
   └─ ComfyUIPreparationService
      ├─ injects post-level prompt data into workflow template
      ├─ writes workflow JSON and config JSON
      └─ stores files inside campaign/page output tree

7. GSheet Export
   └─ GoogleSheetsExporter
      ├─ writes Organic_Posts
      ├─ GSheet keeps ChatGPT prompt only for visual generation
      └─ runtime JSON keeps full Open Design + ComfyUI structures

8. Facebook Scheduling / Publishing
   └─ publish_ready_organic_posts_to_facebook_job
      ├─ processes only `post_status = ready`
      ├─ computes future schedule in target audience timezone
      ├─ appends hashtags to message
      └─ updates job-control fields only

9. Results Collection / Learning
   └─ daily_collect_organic_results_job
      ├─ collects posted Facebook rows only
      ├─ waits until next local calendar day, not fixed 24h
      ├─ stores Organic_Results
      ├─ stores Daily_Learning_Log
      └─ writes English local JSONL learning memory

10. Next-cycle feedback
    └─ Organic strategy/generation loads recent learning memory
```

## Design principle

The project separates:
- **strategy truth**,
- **organic execution strategy**,
- **post-level content**,
- **post-level visual design**,
- **runtime generation artifacts**,
- **publishing state**,
- **performance learning**.

This separation is intentional.  
Do not collapse them into one file or one mega-function.

## Current verified outcomes

The latest verified test showed:
- `organic_strategy_mode = evergreen_growth`,
- upstream source changed from event-driven Mother’s Day strategy to `vietnamese_coffee_identity`,
- a stable organic strategy revision occurred,
- 4 organic posts were generated,
- Open Design translated all 4 posts,
- 4 ComfyUI workflow/config pairs were prepared,
- GSheet received rows.

## Important conceptual rule

For visual output:

```text
organic post text
→ Open Design visual truth
→ ChatGPT prompt + ComfyUI prompt/workflow
```

Not:

```text
generic batch theme
→ one detached image idea
```

Every image must map to its corresponding post text and desired reaction.
