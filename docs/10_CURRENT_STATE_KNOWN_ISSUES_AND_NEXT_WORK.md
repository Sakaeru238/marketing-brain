# 10 — Current State, Known Issues, and Next Work

## Current verified working state

### Organic strategy
Working:
- evergreen strategy source generated when no `event:` note is present,
- stale Mother’s Day strategy no longer automatically controls evergreen content,
- organic strategy review can trigger stable revision when upstream source changes,
- Telegram notification payload is produced for strategy change.

### Organic content
Working:
- organic post batch generation,
- KPI-aware content intensity,
- use of recent learning memory,
- GSheet row export.

### Open Design and ComfyUI
Working:
- per-post Open Design visual translation,
- post-specific image mapping,
- ChatGPT image prompt generation,
- ComfyUI positive/negative prompts,
- ComfyUI workflow/config JSON generation.

### Results collection
Implemented:
- posted-row filtering,
- next-calendar-day collection rule,
- Organic_Results upsert,
- Daily_Learning_Log upsert,
- local English JSONL learning memory,
- Vietnamese sheet learning text.

### Facebook hashtag handling
Implemented:
- preserve sheet storage such as:
  `#VietnameseCoffee|#CoffeeHeritage`
- publish as:
  `#VietnameseCoffee #CoffeeHeritage`
- avoid double `##`.

## Known issue 1 — Organic_Posts status default

Observed after organic generation:
```text
post_status = posted
```

But scheduler processes only:
```text
post_status = ready
```

Impact:
- scheduler skips newly generated rows,
- no Facebook schedule is created,
- Business Manager does not show new scheduled posts.

### Recommended fix
Update the Organic_Posts exporter/mapping so newly generated rows are written with:
```text
post_status = ready
```

Do not change scheduler to process `posted`; that would confuse true published state.

## Known issue 2 — Claim discipline in generated content

One generated batch produced a claim suggesting:
```text
Vietnamese families have used a 1–6 strength system for generations
```

The 1–6 system is a product mechanism and should not be expanded into unverifiable cultural history without approved source support.

### Recommended fix
Add content-generation guardrail:
- do not turn product mechanism into historical/cultural fact unless supported,
- phrase cautiously:
  - “AODAI’s 1–6 strength system helps express different coffee intensity preferences”
  - not “Vietnamese families historically used levels 1–6.”

## Known issue 3 — Facebook metrics availability

Graph API may not return all reach/impression/click metrics even when Business Manager UI shows a value.

Current behavior:
- preserve available metrics,
- mark unavailable metrics as `-`,
- do not fail the whole result row.

This is acceptable, but should remain documented.

## Next recommended work order

1. Fix `post_status = ready` default for newly generated Organic_Posts rows.
2. Add claim-discipline guardrails to organic generation prompt.
3. Run full dry-run scheduling test.
4. Run one real schedule test.
5. After a next-day window, collect results and validate:
   - Organic_Results,
   - Daily_Learning_Log,
   - JSONL learning memory.
6. Optionally build ComfyUI execution adapter if automatic image rendering is desired.

## Do not do next

Do not:
- rewrite the whole scheduler,
- create a second strategy service,
- merge Open Design and content generation into one step,
- remove local English JSONL memory,
- change posted filtering in collector without checking publish semantics.
