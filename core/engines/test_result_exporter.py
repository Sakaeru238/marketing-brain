import json
from pathlib import Path
from datetime import datetime

import pandas as pd


class TestResultExporter:
    """
    Export kết quả test ra:
    - JSON: cho AI / pipeline khác dùng tiếp
    - Excel: cho người đọc kiểm tra dễ
    """

    def __init__(self, save_dir="performance/test_results"):
        self.project_root = Path(__file__).resolve().parents[2]
        self.save_dir = self.project_root / save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _build_base_name(self, test_id):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{test_id}_real_flow_{timestamp}"

    def export_json(self, test_id, payload):
        base_name = self._build_base_name(test_id)
        file_path = self.save_dir / f"{base_name}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

        return file_path

    def export_excel(self, test_id, payload):
        base_name = self._build_base_name(test_id)
        file_path = self.save_dir / f"{base_name}.xlsx"

        summary_rows = []
        execution_trace = payload.get("execution_trace", {})

        summary_rows.append(
            {
                "section": "summary",
                "key": "test_id",
                "value": payload.get("test_id"),
            }
        )
        summary_rows.append(
            {
                "section": "summary",
                "key": "final_pass",
                "value": payload.get("final_pass"),
            }
        )

        for key, value in execution_trace.items():
            summary_rows.append(
                {
                    "section": "execution_trace",
                    "key": key,
                    "value": value,
                }
            )

        round_1 = payload.get("round_1_brand_intake", {})
        round_2 = payload.get("round_2_strategy", {})
        round_3 = payload.get("round_3_claude_parse", {})
        round_4 = payload.get("round_4_learning", {})

        round_rows = [
            {"round": "round_1_brand_intake", "pass": round_1.get("pass")},
            {"round": "round_2_strategy", "pass": round_2.get("pass")},
            {"round": "round_3_claude_parse", "pass": round_3.get("pass")},
            {"round": "round_4_learning", "pass": round_4.get("pass")},
        ]

        brand_intake = round_1.get("brand_intake", {})
        top_campaign = round_2.get("top_campaign")
        top_campaigns = round_2.get("top_campaigns", [])
        parsed = round_3.get("parsed", {})
        learning = round_4.get("learning", {})
        feedback_profile = round_4.get("feedback_profile", {})
        validation_result = round_4.get("validation_result", {})

        brand_rows = []
        if brand_intake:
            brand_rows.append(
                {
                    "brand_name": brand_intake.get("brand", {}).get("brand_name"),
                    "product_name": brand_intake.get("product", {}).get("product_name"),
                    "offer_text": brand_intake.get("offer", {}).get("offer_text"),
                    "objective": brand_intake.get("objective"),
                    "expected_focus": brand_intake.get("expected_focus"),
                }
            )

        campaign_rows = []
        for idx, campaign in enumerate(top_campaigns, start=1):
            row = {"rank": idx}
            if isinstance(campaign, dict):
                for k, v in campaign.items():
                    row[k] = v
            else:
                row["campaign"] = str(campaign)
            campaign_rows.append(row)

        parsed_rows = [
            {
                "status": parsed.get("status"),
                "format": parsed.get("format"),
                "source_mode": parsed.get("source_mode"),
                "parsed_file": round_3.get("parsed_file"),
            }
        ]

        learning_rows = [
            {
                "campaign_angles": json.dumps(
                    learning.get("campaign_angles", []), ensure_ascii=False
                ),
                "cta_patterns": json.dumps(
                    learning.get("cta_patterns", []), ensure_ascii=False
                ),
                "audience_patterns": json.dumps(
                    learning.get("audience_patterns", []), ensure_ascii=False
                ),
                "formats": json.dumps(learning.get("formats", []), ensure_ascii=False),
            }
        ]

        feedback_rows = [
            {
                "preferred_angles": json.dumps(
                    feedback_profile.get("preferred_angles", []), ensure_ascii=False
                ),
                "preferred_ctas": json.dumps(
                    feedback_profile.get("preferred_ctas", []), ensure_ascii=False
                ),
                "preferred_audiences": json.dumps(
                    feedback_profile.get("preferred_audiences", []), ensure_ascii=False
                ),
                "preferred_formats": json.dumps(
                    feedback_profile.get("preferred_formats", []), ensure_ascii=False
                ),
            }
        ]

        validation_rows = [
            {
                "valid": validation_result.get("validation", {}).get("valid"),
                "issues": json.dumps(
                    validation_result.get("validation", {}).get("issues", []),
                    ensure_ascii=False,
                ),
            }
        ]

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            pd.DataFrame(summary_rows).to_excel(
                writer, sheet_name="Summary", index=False
            )
            pd.DataFrame(round_rows).to_excel(
                writer, sheet_name="Round_Status", index=False
            )
            pd.DataFrame(brand_rows).to_excel(
                writer, sheet_name="Brand_Intake", index=False
            )
            pd.DataFrame(campaign_rows).to_excel(
                writer, sheet_name="Top_Campaigns", index=False
            )
            pd.DataFrame(parsed_rows).to_excel(
                writer, sheet_name="Claude_Parse", index=False
            )
            pd.DataFrame(learning_rows).to_excel(
                writer, sheet_name="Learning", index=False
            )
            pd.DataFrame(feedback_rows).to_excel(
                writer, sheet_name="Feedback", index=False
            )
            pd.DataFrame(validation_rows).to_excel(
                writer, sheet_name="Validation", index=False
            )

        return file_path
