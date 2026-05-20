# 04 — Strategy Layer: Alysha and Organic

## Core principle

Alysha Strategy Engine is the source of truth for strategic direction.

Organic content may **translate** and **execute** strategy, but it must not silently rewrite:
- core positioning,
- product truth,
- brand promise,
- emotional territory,
- customer psychology,
- campaign direction,
- `do_not_do` rules.

## Strategy hierarchy

```text
Reference strategy source
  data/output/strategy_output.json
        ↓
OrganicAlyshaSourceService
  organic_alysha_source_output.json
        ↓
OrganicStrategyService
  organic_strategy_output.json
        ↓
OrganicGenerationService
  organic_output.json
```

## Why an organic-specific Alysha source exists

The prior issue:
- the reference strategy was still tied to a Mother’s Day event,
- organic page growth content incorrectly inherited event messaging even after the event context was no longer desired.

The fix:
- create `organic_alysha_source_output.json`,
- make it mode-aware:
  - `evergreen_growth`
  - `event_aware`

## Evergreen vs event-aware logic

### Evergreen
Used when `Campaign_Config.notes` is blank or not prefixed with `event:`.

Example:
```text
notes = ""
notes = "Test Facebook organic content system"
```

Expected:
```text
source_mode = evergreen_growth
strategy_mode = evergreen_growth
```

### Event-aware
Used only when:
```text
notes = "event: ..."
```

Example:
```text
notes = "event: Mother's Day"
```

Expected:
```text
source_mode = event_aware
strategy_mode = event-aware organic strategy
```

## Organic strategy output standard

`organic_strategy_output.json` must include:
- Alysha compliance block,
- source path,
- mapping audit,
- protected fields snapshot,
- audience psychology layer,
- social engagement layer,
- KPI pressure layer,
- organic execution strategy,
- daily learning adjustments,
- review decision,
- update history,
- KPI snapshot.

## Alysha mapping requirements

The strategy mapping target is 100%.

Required sections:
- `campaign_direction_alignment`
- `target_persona`
- `customer_psychology`
- `strategy_map`
- `priority_angles`
- `hook_guidance`
- `core_message`
- `offer_strategy`
- `reason_to_believe`
- `mechanism`
- `voc_summary`
- `creative_mechanics`
- `visual_formats`
- `creative_direction`
- `do_not_do`

Missing required sections should fail the strategy audit, not be ignored.

## Organic execution is allowed to expand

Organic content may expand:
- audience slice,
- scenario,
- hook,
- format,
- tone,
- content archetype,
- posting angle,
- SEO wording,
- reaction trigger,
- social engagement tactics,
- daily learning adjustments,
- KPI pressure actions.

## KPI pressure layer

Inputs include:
- start day,
- end day,
- duration,
- current followers,
- target followers,
- current likes,
- target likes,
- primary growth metric.

The layer derives:
- days remaining,
- follower gap,
- required growth per day,
- KPI status,
- content intensity.

If KPI is behind, content should increase use of:
- relatable content,
- humor,
- identity validation,
- shareable emotional hooks,
- light debate,
- comment triggers,
- tagging prompts.

## Review behavior

Organic strategy review can produce:
- `no_change`
- `daily_adjustment`
- `stable_revision`
- `created`

Stable revision is allowed when the upstream Alysha source changes materially.

When strategy changes:
- Telegram should notify,
- `strategy_update_history` should record the reason,
- output should remain traceable.

## Current verified latest strategy state

Latest tested evergreen output shifted away from event gift messaging into:
```text
campaign_direction = vietnamese_coffee_identity
```

This confirms upstream source refresh is working.
