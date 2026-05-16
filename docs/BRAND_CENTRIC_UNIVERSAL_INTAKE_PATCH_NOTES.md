# Brand-Centric Universal Brand Intake Patch Notes

## What this patch implements

This patch starts the real source-code migration to the brand-centric Marketing-Brain architecture:

```text
marketing-brain
  → brand
    → Universal Brand Intake — Alysha 100%
      → Brand Context Source of Truth
        → Organic / Paid Ads / POD
```

## Added

### Multi-brand config foundation

```text
config/global/system_settings.json
config/brands/brand_registry.json
config/brands/AODAI/brand_settings.json
config/brands/AODAI/gsheet_settings.json
config/brands/AODAI/organic/organic_settings.json
config/brands/AODAI/paid_ads/paid_ads_settings.json
config/brands/AODAI/pod/pod_settings.json
```

### Brand routing services

```text
core/services/brand_registry_service.py
core/services/brand_context_resolver.py
core/services/brand_job_router.py
```

### Universal Brand Intake flow

```text
core/engines/universal_brand_intake_loader.py
core/engines/universal_brand_intake_engine.py
core/jobs/run_universal_brand_intake_job.py
core/jobs/resolve_brand_targets_job.py
```

### Alysha prompt

```text
data/prompts/brand_intake/universal_brand_context_alysha_prompt.txt
```

### Docs

```text
docs/13_BRAND_CENTRIC_FOUNDATION_AND_UNIVERSAL_INTAKE.md
```

## Modified

```text
core/config/paths.py
core/exporters/google_sheets_exporter.py
core/engines/claude_api_adapter.py
```

## Compatibility behavior

- Existing organic runtime paths are not migrated in this patch.
- Existing organic jobs should keep working.
- Google Sheets routing now prefers `config/brands/{brand_id}/gsheet_settings.json` and falls back to legacy `config/google_sheet_routing.json` if no brand routes are available.
- The new universal intake system writes canonical brand context files to:

```text
data/brands/{brand_id}/brand_context/
```

## Test commands

### 1. Resolve active brand targets

```bat
python -m core.jobs.resolve_brand_targets_job --module brand_intake
python -m core.jobs.resolve_brand_targets_job --module organic
```

### 2. Dry-run intake from a local Excel workbook

```bat
python -m core.jobs.run_universal_brand_intake_job ^
  --brand-id AODAI ^
  --dry-run ^
  --input-xlsx E:\path\to\Universal_Brand_Intake_GSheet_Template_Alysha.xlsx
```

### 3. Run real intake from configured Google Sheet

First paste the real Brand Intake GSheet URL into:

```text
config/brands/AODAI/gsheet_settings.json
```

Then run:

```bat
python -m core.jobs.run_universal_brand_intake_job --brand-id AODAI
```

## Known honest limitation

The intake engine fetches direct public pages and user-provided source URLs. It structurally enforces Alysha Brand Intake output requirements, but search-engine style competitor discovery is not implemented inside this patch yet. If full research automation beyond direct URLs is required, that should be added as a separate research capability.
