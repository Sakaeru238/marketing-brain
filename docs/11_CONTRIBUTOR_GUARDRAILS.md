# 11 — Contributor Guardrails

## Objective

Prevent future contributors or AI agents from:
- duplicating existing functions,
- breaking status semantics,
- writing failed outputs into production folders,
- reintroducing old event strategy bugs,
- applying old patch versions over current code.

## Guardrail 1 — Extend existing services

Before creating a new function or service, search for:
- existing service with same responsibility,
- prior patch final file,
- current docs references.

Examples:
- strategy: extend `OrganicStrategyService`, do not create another strategy translator,
- visual design: extend `OpenDesignVisualTranslationService`, do not build parallel prompt maker,
- ComfyUI: extend `ComfyUIPreparationService`, do not create a second workflow writer.

## Guardrail 2 — Respect status semantics

### Organic_Posts
- `ready` = scheduler may process
- `posted` = scheduled/published result already accepted by publisher flow
- `error` = publishing failed

Do not overload these statuses.

## Guardrail 3 — Do not mix runtime and source

Source code:
```text
core/
data/prompts/
data/templates/
docs/
config/
```

Runtime:
```text
data/output/
data/knowledge/organic_learning/
```

Do not place Python source or docs under runtime folders.

## Guardrail 4 — Do not write error artifacts into canonical output folders

If a generation step fails:
- return an error,
- log diagnostics,
- write temp/debug data outside canonical production folders if needed.

Do not replace a valid:
```text
organic_output.json
```
with a partial or malformed error payload.

## Guardrail 5 — Preserve traceability

Every output should retain:
- brand ID,
- page ID,
- campaign ID,
- organic run ID,
- post ID where applicable.

## Guardrail 6 — Treat Alysha as strategy truth

Organic execution may adapt:
- format,
- hook,
- angle execution,
- reactions,
- SEO wording,
- posting angle.

Organic execution must not silently rewrite:
- positioning,
- product truth,
- customer psychology,
- protected `do_not_do`.

## Guardrail 7 — Visuals must map to text

Never generate image prompts from only batch theme.  
Use the exact post text/context.

## Guardrail 8 — GSheet vs runtime JSON split

Do not overload GSheet with machine-only data.  
Keep:
- ChatGPT prompt in GSheet,
- full Open Design / ComfyUI data in runtime JSON.

## Guardrail 9 — Preserve current content_tags storage

Do not refactor GSheet storage away from:
```text
#Tag1|#Tag2|#Tag3
```

Publisher handles transformation at post time.

## Guardrail 10 — Metric uncertainty must be explicit

Unavailable metric:
```text
-
```

Zero metric:
```text
0
```

Do not blur the two.

## Guardrail 11 — Patch safely

Before replacing files:
1. identify current final version,
2. inspect function signatures,
3. run syntax validation,
4. run the relevant job,
5. inspect output artifacts,
6. document known remaining issue.

## Guardrail 12 — Avoid stale docs

If implementation changes:
- update canonical docs,
- update known issues,
- update runbook,
- update current source file list if needed.
