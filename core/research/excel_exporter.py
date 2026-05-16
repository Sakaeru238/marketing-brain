import pandas as pd
from pathlib import Path
from datetime import datetime


class ResearchExcelExporter:
    """
    Export research data to Excel for human-readable review.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, _id, research_data):
        """
        Main export function.
        """

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_path = self.output_dir / f"{_id}_research.xlsx"

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:

            # ---------------------------------------------------
            # Summary sheet
            # ---------------------------------------------------
            summary = research_data.get("research_summary", {})
            df_summary = pd.DataFrame([summary])
            df_summary.to_excel(writer, sheet_name="Summary", index=False)

            # ---------------------------------------------------
            # Competitors
            # ---------------------------------------------------
            competitors = research_data.get("competitor_intelligence", {}).get(
                "competitors", []
            )

            if competitors:
                df_comp = pd.json_normalize(competitors)
                df_comp.to_excel(writer, sheet_name="Competitors", index=False)

            # ---------------------------------------------------
            # Hooks
            # ---------------------------------------------------
            hooks = research_data.get("hooks", [])
            df_hooks = pd.DataFrame({"hooks": hooks})
            df_hooks.to_excel(writer, sheet_name="Hooks", index=False)

            # ---------------------------------------------------
            # Claims
            # ---------------------------------------------------
            claims = research_data.get("claims", [])
            df_claims = pd.DataFrame({"claims": claims})
            df_claims.to_excel(writer, sheet_name="Claims", index=False)

            # ---------------------------------------------------
            # Trends
            # ---------------------------------------------------
            trends = research_data.get("trend_findings", [])
            df_trends = pd.DataFrame({"trends": trends})
            df_trends.to_excel(writer, sheet_name="Trends", index=False)

            # ---------------------------------------------------
            # Warnings
            # ---------------------------------------------------
            warnings = research_data.get("warnings", [])
            df_warn = pd.DataFrame({"warnings": warnings})
            df_warn.to_excel(writer, sheet_name="Warnings", index=False)

        return str(file_path)
