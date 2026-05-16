# 13 — Brand-Centric Foundation and Universal Brand Intake

This patch starts the migration to the brand-centric Marketing-Brain architecture:

```text
marketing-brain
  └── brand
      └── Brand Context Source of Truth
          ├── Organic Strategy
          ├── Paid Ads Strategy
          └── POD Strategy
```

## What was added

### 1. Multi-brand config foundation

```text
config/
  global/
    system_settings.json

  brands/
    brand_registry.json
    AODAI/
      brand_settings.json
      gsheet_settings.json
      organic/organic_settings.json
      paid_ads/paid_ads_settings.json
      pod/pod_settings.json
```

`brand_registry.json` is the top-level index used by jobs and routers to decide which brands are active for each module.

### 2. Brand routing services

```text
core/services/
  brand_registry_service.py
  brand_context_resolver.py
  brand_job_router.py
```

These services provide:
- active brand lookup
- enabled-module filtering
- canonical brand folder resolution
- future-ready brand job routing

### 3. Universal Brand Intake loader

```text
core/engines/universal_brand_intake_loader.py
```

Supports:
- Excel intake workbooks
- Google Sheet intake workbooks
- header-row discovery for the intake layout
- validation of the 8 required Alysha intake seed fields
- optional field aliases for evolving product catalog / hero design mappings

### 4. Universal Brand Intake engine

```text
core/engines/universal_brand_intake_engine.py
```

Produces canonical brand-context files under:

```text
data/brands/{brand_id}/brand_context/
  intake/
    brand_intake_raw.json
    brand_intake_normalized.json

  alysha/
    brand_context_source_of_truth.md
    brand_context_source_of_truth.json
    brand_research_notes.json
    brand_intake_run.json
```

The engine uses:
- universal intake fields
- direct public website/source excerpts when fetchable
- an Alysha-structure prompt that requires the full Brand Context Source of Truth output shape

### 5. New jobs

```text
python -m core.jobs.resolve_brand_targets_job --module brand_intake
python -m core.jobs.run_universal_brand_intake_job --brand-id AODAI --dry-run --input-xlsx <path>
python -m core.jobs.run_universal_brand_intake_job --brand-id AODAI
```

`--dry-run` validates the intake and writes raw/normalized files without invoking Claude.

### 6. Google Sheets routing compatibility

`GoogleSheetsExporter` now prefers routes from:

```text
config/brands/{brand_id}/gsheet_settings.json
```

and falls back to the existing legacy file:

```text
config/google_sheet_routing.json
```

This preserves the existing organic workflow while enabling multi-brand config migration.

## Important compatibility note

This patch does **not** yet migrate Organic Strategy outputs into `data/brands/{brand_id}/organic/...`.
The currently working Organic jobs remain unchanged in their runtime output paths. This patch only establishes:
- multi-brand config
- universal brand intake
- brand context source-of-truth outputs

The organic/paid/POD downstream migration can be done in a later, controlled patch.

## Alysha compliance note

The prompt enforces 100% structure compliance with the Alysha Brand Intake document format:
- Brand Overview
- Brand Story & Origin
- Product Catalog
- What Makes Them Different
- Competitor Landscape
- The Alternative Solution
- Core Audience(s)
- Brand Voice & Tone
- Creative Constraints
- Must-Know Strategic Context
- Research Notes

The current code fetches direct public pages and user-provided source URLs. Search-engine competitor discovery remains a separate research capability if needed later.
