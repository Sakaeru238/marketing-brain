import json
from pathlib import Path

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.pipeline.research_pipeline import ResearchPipeline
from utils.save_output import save_output

adapter = ClaudeAPIAdapter()
pipeline = ResearchPipeline()


brand_intake = {
    "brand": {
        "brand_name": "AODAI Coffee",
        "brand_positioning": "Pure Vietnamese Coffee",
        "origin": "Buon Ma Thuot, Dak Lak, Vietnam",
    },
    "product": {
        "product_name": "AODAI Level 1–6 Tasting Set – Freeze-Dried Vietnamese Espresso | 12 Pods",
        "product_type": "pure coffee",
        "format": "instant pod",
        "pack_size": "12 pods",
    },
    "offer": {
        "offer_text": "35% OFF first order",
    },
    "selling_orientation": ["gift"],
    "occasion": ["mothers_day"],
    "core_truth": [
        "100% Vietnamese Robusta",
        "Freeze-dried Vietnamese espresso",
        "No machine needed",
        "Strong authentic Vietnamese coffee taste",
        "Works in hot or cold water",
        "6 roast levels",
    ],
    "guardrails": [
        "Do not describe AoDai as flavored coffee.",
        "Do not mix AoDai positioning with Nonla flavor messaging.",
        "Keep messaging focused on pure Vietnamese coffee.",
    ],
}


insight_path = Path("data/output/insight_output.json")

if not insight_path.exists():
    print("❌ Không tìm thấy data/output/insight_output.json")
    print("Hãy chạy: python -m test.test_insight_prompt")
    exit()

insight_output = json.loads(insight_path.read_text(encoding="utf-8"))

strategy_input = {
    "brand_intake": brand_intake,
    "insight_output": insight_output,
}


prompt_path = Path("data/prompts/strategy/strategy_generation_prompt.txt")

if not prompt_path.exists():
    print("❌ Không tìm thấy data/prompts/strategy/strategy_generation_prompt.txt")
    exit()

template = prompt_path.read_text(encoding="utf-8")

prompt = template.replace(
    "{{STRATEGY_INPUT}}",
    json.dumps(strategy_input, ensure_ascii=False, indent=2),
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

save_output(parsed, "strategy", "strategy_output.json")
