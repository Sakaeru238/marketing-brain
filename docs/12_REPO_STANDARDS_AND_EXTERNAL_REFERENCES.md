# 12 — Repo Standards and External References

## Strategy standards

The project follows the design principle discussed for:
- `motion-team / creative-strategy-skills`
- Alysha Creative Strategy Engine as strategy source of truth.

The target is:
```text
100% Alysha Strategy Engine compliance
```

## Required strategy concepts

Strategy output is not only a list of content ideas.  
It must be deployable creative strategy.

Important fields include:
- campaign direction,
- core message,
- target persona,
- customer psychology,
- pain points,
- desires,
- beliefs,
- objections,
- priority angles,
- angle families,
- content pillars,
- creative hooks,
- proof points,
- offer context,
- product truth,
- emotional territory,
- `do_not_do`.

## Organic expansion policy

Organic content may expand:
- audience slice,
- scenario,
- hook,
- format,
- tone,
- content archetype,
- posting angle,
- SEO wording,
- reaction trigger.

Organic content may not alter protected strategic truth.

## Additional recommended mapping areas

The project previously identified useful mapping additions from:
- `ericosiu / ai-marketing-skills`
  - ICP depth,
  - market sophistication,
  - awareness stage,
  - pain language.

Also valuable:
- review mining systems,
- real customer wording,
- real objections,
- real emotional language.

## Social Engagement Layer

This layer is explicitly required because generic content generation was too weak.

It should consider:
- Facebook-native engagement,
- identity validation,
- comment triggers,
- share triggers,
- light debate,
- carefully guardrailed rage-bait-light patterns,
- tribe validation,
- audience participation.

## Full architecture standard

```text
Alysha Strategy Engine
→ Audience Psychology Layer
→ Social Engagement Layer
→ KPI Pressure Layer
→ Organic Content Generator
→ Open Design Visual Translation
→ Publishing
→ Results Collector
→ Learning / Optimization
```

## Open Design role

Open Design is not merely a pretty prompt formatter.  
It is the visual truth translator from organic post text into:
- visual alignment logic,
- visual spec,
- ChatGPT image prompt,
- ComfyUI prompt bundle.

Current output references an Open Design skill path such as:
```text
external/creative_execution/open_design/skills/image-poster/SKILL.md
```

## ComfyUI role

ComfyUI receives structured visual inputs from Open Design:
- positive prompt,
- negative prompt,
- workflow template injection,
- per-post config/runtime JSON.

It is prepared for later execution; current flow prepares JSON files and does not necessarily render images automatically.

## Content and claim discipline

Creative ambition is welcome, but the system should not:
- invent unsupported historical facts,
- convert product mechanics into universal cultural facts,
- violate brand/product truth,
- use broad stereotypes instead of specific authentic context.

## Documentation standard

Any future addition should document:
- what problem it solves,
- input contract,
- output contract,
- where source code lives,
- where runtime outputs live,
- how to test it,
- how it interacts with existing functions.
