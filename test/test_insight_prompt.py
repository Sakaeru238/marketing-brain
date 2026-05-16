import json
from pathlib import Path

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.pipeline.research_pipeline import ResearchPipeline
from utils.save_output import save_output

adapter = ClaudeAPIAdapter()
pipeline = ResearchPipeline()


research_path = Path("data/output/research_output.json")

if not research_path.exists():
    print("❌ Không tìm thấy data/output/research_output.json")
    print("Hãy chạy: python -m test.test_market_prompt")
    exit()

research_data = json.loads(research_path.read_text(encoding="utf-8"))


prompt_path = Path("data/prompts/insight/insight_extraction_prompt.txt")

if not prompt_path.exists():
    print("❌ Không tìm thấy data/prompts/insight/insight_extraction_prompt.txt")
    exit()

template = prompt_path.read_text(encoding="utf-8")

prompt = template.replace(
    "{{RESEARCH_DATA}}",
    json.dumps(research_data, ensure_ascii=False, indent=2),
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

save_output(parsed, "insight", "insight_output.json")
