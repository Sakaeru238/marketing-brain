import json
from pathlib import Path

import pandas as pd


class OrganicControlLoader:
    """
    Loads organic generation controls from marketing_brain_control_panel.xlsx.

    Excel is the control layer. Brand/product/audience details come from brand_intake JSON.
    page_id is supported for multi-page/channel brands.
    """

    def __init__(self, control_panel_file="data/control_panels/marketing_brain_control_panel.xlsx"):
        self.control_panel_file = Path(control_panel_file)

    def _read_sheet(self, sheet_name):
        if not self.control_panel_file.exists():
            raise FileNotFoundError(f"Control panel not found: {self.control_panel_file}")
        try:
            df = pd.read_excel(self.control_panel_file, sheet_name=sheet_name)
        except ValueError:
            return pd.DataFrame()
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
        return [item.strip() for item in str(value).split(",") if item and item.strip()]

    def _find_first_match(self, df, column, value):
        if df.empty or column not in df.columns or value is None:
            return {}
        matched = df[df[column].astype(str).str.strip() == str(value).strip()]
        if matched.empty:
            return {}
        return self._row_to_dict(matched.iloc[0])

    def _find_first_status_run(self, df, status_col="status"):
        if df.empty or status_col not in df.columns:
            return {}
        matched = df[df[status_col].astype(str).str.strip().str.lower() == "run"]
        if matched.empty:
            return {}
        return self._row_to_dict(matched.iloc[0])

    def _resolve_final(self, row, final_key, user_key=None, ai_key=None, default=None):
        final_value = row.get(final_key)
        if final_value not in [None, ""]:
            return final_value
        if user_key:
            user_value = row.get(user_key)
            if user_value not in [None, ""]:
                return user_value
        if ai_key:
            ai_value = row.get(ai_key)
            if ai_value not in [None, ""]:
                return ai_value
        return default

    def load_organic_control(self, organic_run_id=None):
        df = self._read_sheet("Organic_Control")
        if df.empty:
            raise ValueError("Sheet Organic_Control is missing or empty.")
        if organic_run_id:
            row = self._find_first_match(df, "organic_run_id", organic_run_id)
            if not row:
                raise ValueError(f"organic_run_id not found: {organic_run_id}")
            return row
        row = self._find_first_status_run(df, "status")
        if not row:
            raise ValueError("No Organic_Control row with status='run' found.")
        return row

    def load_run(self, run_id):
        return self._find_first_match(self._read_sheet("Runs"), "run_id", run_id)

    def load_campaign(self, campaign_id):
        return self._find_first_match(self._read_sheet("Campaign_Control"), "campaign_id", campaign_id)

    def load_platform(self, platform_id):
        return self._find_first_match(self._read_sheet("Platform_Library"), "platform_id", platform_id)

    def load_niche(self, niche_id):
        return self._find_first_match(self._read_sheet("Niche_Library"), "niche_id", niche_id)

    def load_page(self, page_id=None, page_url=None):
        df = self._read_sheet("Page_Library")
        if df.empty:
            return {}
        if page_id:
            row = self._find_first_match(df, "page_id", page_id)
            if row:
                return row
        if page_url:
            row = self._find_first_match(df, "page_url", page_url)
            if row:
                return row
        return {}

    def load_latest_page_audit(self, organic_run_id=None, page_id=None, page_url=None):
        df = self._read_sheet("Page_Audit_Log")
        if df.empty:
            return {}
        filtered = df.copy()
        if organic_run_id and "organic_run_id" in filtered.columns:
            candidate = filtered[filtered["organic_run_id"].astype(str).str.strip() == str(organic_run_id).strip()]
            if not candidate.empty:
                filtered = candidate
        if page_id and "page_id" in filtered.columns:
            candidate = filtered[filtered["page_id"].astype(str).str.strip() == str(page_id).strip()]
            if not candidate.empty:
                filtered = candidate
        if page_url and "page_url" in filtered.columns:
            candidate = filtered[filtered["page_url"].astype(str).str.strip() == str(page_url).strip()]
            if not candidate.empty:
                filtered = candidate
        if "audit_date" in filtered.columns:
            try:
                filtered = filtered.sort_values("audit_date", ascending=False)
            except Exception:
                pass
        if filtered.empty:
            return {}
        return self._row_to_dict(filtered.iloc[0])

    def load_previous_results(self, organic_run_id=None, page_id=None, limit=20):
        df = self._read_sheet("Organic_Results")
        if df.empty:
            return []
        filtered = df.copy()
        if organic_run_id and "organic_run_id" in filtered.columns:
            candidate = filtered[filtered["organic_run_id"].astype(str).str.strip() == str(organic_run_id).strip()]
            if not candidate.empty:
                filtered = candidate
        if page_id and "page_id" in filtered.columns:
            candidate = filtered[filtered["page_id"].astype(str).str.strip() == str(page_id).strip()]
            if not candidate.empty:
                filtered = candidate
        if "published_date" in filtered.columns:
            try:
                filtered = filtered.sort_values("published_date", ascending=False)
            except Exception:
                pass
        return [self._row_to_dict(row) for _, row in filtered.head(limit).iterrows()]

    def _candidate_brand_intake_paths(self, run_id, explicit_path=None):
        candidates = []
        if explicit_path:
            candidates.append(Path(str(explicit_path)))
        if run_id:
            run_id = str(run_id).strip()
            candidates.extend([
                Path(f"data/knowledge/brand_context/brand_intake/{run_id}_brand_intake.json"),
                Path(f"data/knowledge/brand_intake/{run_id}_brand_intake.json"),
                Path(f"data/knowledge/brand_context/{run_id}/brand_intake.json"),
            ])
        return candidates

    def load_brand_intake(self, run_id=None, explicit_path=None):
        checked = self._candidate_brand_intake_paths(run_id, explicit_path)
        for path in checked:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8")), str(path)
        raise FileNotFoundError("Brand intake JSON not found. Checked: " + ", ".join([str(p) for p in checked]))

    def load_package(self, organic_run_id=None):
        organic = self.load_organic_control(organic_run_id)
        organic_run_id = organic.get("organic_run_id")
        base_run_id = organic.get("run_id")
        campaign_id = organic.get("campaign_id")
        platform_id = organic.get("platform_id")
        niche_id = organic.get("niche_id")
        page_id = organic.get("page_id")
        page_url = organic.get("page_url")

        run = self.load_run(base_run_id) if base_run_id else {}
        campaign = self.load_campaign(campaign_id) if campaign_id else {}
        platform = self.load_platform(platform_id) if platform_id else {}
        niche = self.load_niche(niche_id) if niche_id else {}
        page = self.load_page(page_id=page_id, page_url=page_url)

        page_id = page_id or page.get("page_id")
        page_url = page_url or page.get("page_url")
        platform_id = platform_id or page.get("platform_id")
        niche_id = niche_id or page.get("niche_id")

        brand_intake_path = run.get("brand_intake_file")
        brand_intake, resolved_brand_intake_file = self.load_brand_intake(run_id=base_run_id, explicit_path=brand_intake_path)
        brand = brand_intake.get("brand", {}) or {}
        product = brand_intake.get("product", {}) or {}

        resolved = {
            "organic_run_id": organic_run_id,
            "run_id": base_run_id,
            "campaign_id": campaign_id,
            "brand_id": organic.get("brand_id") or page.get("brand_id") or brand.get("brand_id"),
            "product_id": organic.get("product_id") or product.get("product_id"),
            "niche_id": niche_id,
            "page_id": page_id,
            "platform_id": platform_id,
            "page_url": page_url,
            "organic_scope": self._split_csv(organic.get("organic_scope")),
            "growth_goal": organic.get("growth_goal") or page.get("growth_goal") or page.get("primary_goal"),
            "growth_goal_target": organic.get("growth_goal_target") or page.get("target_followers"),
            "growth_goal_deadline": organic.get("growth_goal_deadline"),
            "page_stage": self._resolve_final(organic, "final_page_stage", "page_stage_user_override", "page_stage_ai_suggested", page.get("page_stage") or "low_content_page"),
            "today_content_goal": self._resolve_final(organic, "final_today_content_goal", "today_content_goal_user_override", "today_content_goal_ai_suggested", page.get("default_content_goal") or "fill_content_base"),
            "organic_stage": organic.get("organic_stage_ai_suggested") or "foundation",
            "content_pillars": self._split_csv(self._resolve_final(organic, "final_content_pillars", "content_pillars_user", "content_pillars_ai_suggested", "")),
            "num_posts": int(self._resolve_final(organic, "final_num_posts", "num_posts_requested", "num_posts_ai_suggested", 5)),
            "post_format_mix": self._split_csv(self._resolve_final(organic, "final_post_format_mix", "post_format_mix_user", "post_format_mix_ai_suggested", "text_post,question_post,soft_story,educational,relatable")),
            "product_mention_level": organic.get("product_mention_level") or page.get("default_product_mention_level") or "soft",
            "tone": self._resolve_final(organic, "final_tone", "tone_user", "tone_ai_suggested", page.get("default_tone") or "warm, relatable, conversational"),
            "must_use_topics": self._split_csv(organic.get("must_use_topics")),
            "avoid_topics": self._split_csv(organic.get("avoid_topics")),
            "language": organic.get("language") or page.get("language") or "en",
            "status": organic.get("status"),
            "notes": organic.get("notes"),
            "resolved_brand_intake_file": resolved_brand_intake_file,
        }

        return {
            "organic_control_raw": organic,
            "organic_control": resolved,
            "run": run,
            "campaign": campaign,
            "platform": platform,
            "niche": niche,
            "page": page,
            "brand_intake": brand_intake,
            "page_audit_context": self.load_latest_page_audit(organic_run_id=organic_run_id, page_id=page_id, page_url=page_url),
            "previous_results_context": self.load_previous_results(organic_run_id=organic_run_id, page_id=page_id),
        }
