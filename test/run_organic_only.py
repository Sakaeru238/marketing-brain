import json

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.pipeline.organic_pipeline import OrganicPipeline

ORGANIC_RUN_ID = "ORG_AODAI_FB_20260505_01"
CONTROL_PANEL_FILE = "data/control_panels/marketing_brain_control_panel.xlsx"
STRATEGY_OUTPUT_FILE = "data/output/strategy_output.json"


def main():
    claude_api_adapter = ClaudeAPIAdapter()
    pipeline = OrganicPipeline(control_panel_file=CONTROL_PANEL_FILE, strategy_file=STRATEGY_OUTPUT_FILE)
    organic_output = pipeline.run(organic_run_id=ORGANIC_RUN_ID, claude_mode="api", claude_api_adapter=claude_api_adapter)
    data = organic_output.get("data", {}) or {}
    posts = data.get("organic_posts", []) or []
    print("\n====== ORGANIC ONLY RESULT ======\n")
    print(json.dumps({"organic_run_id": organic_output.get("organic_run_id"), "brand_id": organic_output.get("brand_id"), "page_id": organic_output.get("page_id"), "campaign_id": organic_output.get("campaign_id"), "platform_id": organic_output.get("platform_id"), "status": organic_output.get("status"), "posts_generated": len(posts), "has_claude_organic_raw": bool(data.get("claude_organic_raw")), "organic_parse_error": data.get("claude_organic_parse_error"), "latest_path": organic_output.get("saved_paths", {}).get("latest_path"), "history_path": organic_output.get("saved_paths", {}).get("history_path")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
