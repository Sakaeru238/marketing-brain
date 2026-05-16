# Brand Context JSON Export

This folder was generated from `marketing_brain_control_panel_v3.xlsx`.

## Structure

- `raw_sheets/`: every original Excel sheet exported as raw JSON records.
- `brands/`: brand-level JSON grouped with core truth, guardrails, products, offers, and audiences.
- `products/`: product-level JSON grouped with product benefits, usage, brand guardrails, and offers.
- `offers/`: offer-level JSON.
- `audiences/`: audience seed and AI-expanded audience JSON.
- `brand_intake/`: run/test-id based brand intake JSON ready to use as pipeline input.

## Important

The JSON files preserve the Excel data as much as possible. They are meant to become raw knowledge files for the AI Marketing Brain.
