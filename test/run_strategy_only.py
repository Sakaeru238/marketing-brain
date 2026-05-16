import json
from pathlib import Path
from datetime import datetime

from core.pipeline.master_pipeline import MasterPipeline
from core.loaders.campaign_direction_loader import CampaignDirectionLoader

RUN_ID = "AODAI_01"
CONTROL_PANEL_FILE = "data/control_panels/marketing_brain_control_panel.xlsx"
CUSTOMER_FEEDBACK_FILE = "data/input/customer_feedback_raw.txt"


def main():
    pipeline = MasterPipeline()

    campaign_loader = CampaignDirectionLoader(
        control_panel_file=CONTROL_PANEL_FILE
    )
    campaign_direction = campaign_loader.load_by_run_id(RUN_ID)

    brand_intake_file = (
        campaign_direction.get("run", {}).get("brand_intake_file")
        or "data/knowledge/brand_context/brand_intake/AODAI_01_brand_intake.json"
    )

    brand_intake_path = Path(brand_intake_file)

    if not brand_intake_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy brand intake JSON: {brand_intake_file}"
        )

    brand_intake = json.loads(brand_intake_path.read_text(encoding="utf-8"))

    customer_feedback_file = (
        campaign_direction.get("run", {}).get("customer_feedback_file")
        or CUSTOMER_FEEDBACK_FILE
    )

    customer_feedback_raw = pipeline.load_customer_feedback_raw(
        feedback_file=customer_feedback_file
    )

    claude_mode = "api"

    research_output = pipeline.research_pipeline.run(
        _id=RUN_ID,
        brand_intake=brand_intake,
        claude_mode=claude_mode,
        claude_api_adapter=pipeline.claude_api_adapter,
    )

    insight_output = pipeline.insight_pipeline.run(
        research_output,
        claude_mode=claude_mode,
        claude_api_adapter=pipeline.claude_api_adapter,
    )

    strategy_output = pipeline.strategy_pipeline.run(
        insight_output,
        brand_intake=brand_intake,
        customer_feedback_raw=customer_feedback_raw,
        campaign_direction=campaign_direction,
        claude_mode=claude_mode,
        claude_api_adapter=pipeline.claude_api_adapter,
    )

    output_path = Path("data/output/strategy_output.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(strategy_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history_dir = Path("data/output/history/strategy")
    history_dir.mkdir(parents=True, exist_ok=True)

    history_path = history_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    history_path.write_text(
        json.dumps(strategy_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n====== STRATEGY ONLY RESULT ======\n")
    print(
        json.dumps(
            {
                "_id": RUN_ID,
                "campaign_id": campaign_direction.get("campaign_id"),
                "campaign_direction": campaign_direction.get("campaign_direction"),
                "primary_angle_family": campaign_direction.get("primary_angle_family"),
                "must_use_direction": campaign_direction.get("must_use_direction"),
                "brand_intake_file": brand_intake_file,
                "customer_feedback_used": bool(customer_feedback_raw),
                "customer_feedback_length": len(customer_feedback_raw or ""),
                "strategy_status": strategy_output.get("status"),
                "saved_to": str(output_path),
                "history_saved_to": str(history_path),
                "has_claude_strategy_raw": bool(
                    strategy_output.get("data", {}).get("claude_strategy_raw")
                ),
                "strategy_parse_error": strategy_output.get("data", {}).get(
                    "claude_strategy_parse_error"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
