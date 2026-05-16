import json
from pathlib import Path

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.pipeline.research_pipeline import ResearchPipeline
from utils.save_output import save_output

adapter = ClaudeAPIAdapter()
pipeline = ResearchPipeline()

input_bundle = {
    "brand_filter": {
        "brand_name": "AODAI Coffee",
        "product_name": "AODAI Level 1–6 Tasting Set",
        "product_type": "pure coffee",
        "format": "instant pod",
        "offer_text": "35% OFF first order",
        "selling_orientation": ["gift"],
        "occasion": ["mothers_day"],
        "audience_core": {
            "audience_name": "US strong coffee seekers",
            "pain_point": "Mainstream coffee feels too weak or bland",
            "desired_outcome": "Wants stronger caffeine and bolder taste",
        },
    },
    "research_direction": {
        "selling_orientation": ["gift"],
        "occasion": ["mothers_day"],
        "focus_terms": ["selling_orientation:gift", "occasion:mothers_day"],
        "research_instruction": "Prioritize coffee gift competitors, gift boxes, sampler boxes, subscription gifts, and Mother's Day gift messaging.",
    },
    "seed_competitors": [
        {
            "brand_name": "Atlas Coffee Club",
            "domain": "atlascoffeeclub.com",
            "category": "coffee_subscription_gift",
            "source": "competitor_registry",
        },
        {
            "brand_name": "Bean Box",
            "domain": "beanbox.com",
            "category": "coffee_gift_box",
            "source": "competitor_registry",
        },
        {
            "brand_name": "Trade Coffee",
            "domain": "drinktrade.com",
            "category": "coffee_subscription",
            "source": "competitor_registry",
        },
    ],
    "existing_competitor_signals": [],
    "website_context": {"status": "skipped", "sources": [], "pages": {}},
    "manual_overrides": {},
}


prompt_path = Path("data/prompts/research/research_market_prompt.txt")
template = prompt_path.read_text(encoding="utf-8")

prompt = template.replace("{{RUN_ID}}", "TEST_MARKET_PROMPT").replace(
    "{{INPUT_BUNDLE}}", json.dumps(input_bundle, ensure_ascii=False, indent=2)
)

print("\n====== PROMPT PREVIEW ======\n")
print(prompt[:1500])

result = adapter.run(prompt=prompt)
raw = pipeline._normalize_claude_response(result)

print("\n====== RAW RESPONSE ======\n")
print(raw)

parsed, error = pipeline._try_parse_json_response(raw)

print("\n====== PARSED ======\n")
print(json.dumps(parsed, ensure_ascii=False, indent=2) if parsed else None)

print("\n====== ERROR ======\n")
print(error)

save_output(parsed, "research", "research_output.json")
