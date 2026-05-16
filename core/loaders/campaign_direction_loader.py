from pathlib import Path
import pandas as pd


class CampaignDirectionLoader:
    """
    Loads campaign direction from marketing_brain_control_panel.xlsx.

    Source of truth:
    - Runs sheet maps run_id -> campaign_id
    - Campaign_Control sheet defines the campaign direction

    This loader is production-safe:
    - It does not call Claude.
    - It does not mutate Excel.
    - It returns plain dictionaries.
    """

    def __init__(self, control_panel_file="data/control_panels/marketing_brain_control_panel.xlsx"):
        self.control_panel_file = Path(control_panel_file)

    def _read_sheet(self, sheet_name):
        if not self.control_panel_file.exists():
            raise FileNotFoundError(
                f"Không tìm thấy Excel control panel: {self.control_panel_file}"
            )

        try:
            df = pd.read_excel(self.control_panel_file, sheet_name=sheet_name)
        except ValueError:
            raise ValueError(
                f"Không tìm thấy sheet '{sheet_name}' trong file: {self.control_panel_file}"
            )

        df = df.dropna(how="all")
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _clean_value(self, value):
        if pd.isna(value):
            return None

        if isinstance(value, str):
            value = value.strip()
            return value if value else None

        return value

    def _row_to_dict(self, row):
        return {k: self._clean_value(v) for k, v in row.to_dict().items()}

    def _split_csv(self, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [
            item.strip()
            for item in str(value).split(",")
            if item and item.strip()
        ]

    def load_run(self, run_id):
        runs = self._read_sheet("Runs")

        if "run_id" not in runs.columns:
            raise ValueError("Sheet Runs thiếu cột bắt buộc: run_id")

        matched = runs[runs["run_id"].astype(str).str.strip() == str(run_id).strip()]

        if matched.empty:
            raise ValueError(f"Không tìm thấy run_id trong Runs: {run_id}")

        return self._row_to_dict(matched.iloc[0])

    def load_campaign(self, campaign_id):
        campaigns = self._read_sheet("Campaign_Control")

        if "campaign_id" not in campaigns.columns:
            raise ValueError("Sheet Campaign_Control thiếu cột bắt buộc: campaign_id")

        matched = campaigns[
            campaigns["campaign_id"].astype(str).str.strip() == str(campaign_id).strip()
        ]

        if matched.empty:
            raise ValueError(
                f"Không tìm thấy campaign_id trong Campaign_Control: {campaign_id}"
            )

        return self._row_to_dict(matched.iloc[0])

    def load_by_run_id(self, run_id):
        run = self.load_run(run_id)
        campaign_id = run.get("campaign_id")

        if not campaign_id:
            raise ValueError(f"Run {run_id} không có campaign_id")

        campaign = self.load_campaign(campaign_id)

        direction = {
            "run_id": run_id,
            "campaign_id": campaign_id,
            "run": run,
            "campaign": campaign,

            # Normalized fields for prompt / strategy
            "campaign_type": campaign.get("campaign_type"),
            "brand_id": campaign.get("brand_id"),
            "product_id": campaign.get("product_id"),
            "offer_id": campaign.get("offer_id"),
            "campaign_objective": campaign.get("campaign_objective"),
            "campaign_direction": campaign.get("campaign_direction"),
            "primary_audience": campaign.get("primary_audience"),
            "primary_angle_family": campaign.get("primary_angle_family"),
            "secondary_angle_family": self._split_csv(
                campaign.get("secondary_angle_family")
            ),
            "occasion": campaign.get("occasion"),
            "content_intent": self._split_csv(campaign.get("content_intent")),
            "must_use_direction": campaign.get("must_use_direction"),
            "do_not_focus": campaign.get("do_not_focus"),
            "primary_channel": self._split_csv(campaign.get("primary_channel")),
            "creative_outputs": self._split_csv(campaign.get("creative_outputs")),
            "status": campaign.get("status"),
            "notes": campaign.get("notes"),
        }

        return direction
