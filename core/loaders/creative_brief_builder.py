def _split_csv(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [item.strip() for item in str(value).split(",") if item and item.strip()]


def _to_int(value, default=0):
    if value is None or str(value).strip() == "":
        return default

    try:
        return int(value)
    except Exception:
        return default


class CreativeBriefBuilder:
    def build(self, run, campaign, creative_control, strategy_output, style_library):
        selected_style_ids = _split_csv(creative_control.get("creative_style_ids"))

        selected_styles = []
        for style_id in selected_style_ids:
            style = style_library.get(style_id)
            if style:
                selected_styles.append(style)

        return {
            "run": {
                "run_id": run.get("run_id"),
                "campaign_id": run.get("campaign_id"),
                "status": run.get("status"),
                "notes": run.get("notes"),
            },
            "campaign": {
                "campaign_id": campaign.get("campaign_id"),
                "campaign_type": campaign.get("campaign_type"),
                "brand_id": campaign.get("brand_id"),
                "product_id": campaign.get("product_id"),
                "campaign_goal": campaign.get("campaign_goal"),
                "selling_orientation": campaign.get("selling_orientation"),
                "occasion": campaign.get("occasion"),
                "target_audience": campaign.get("target_audience"),
                "content_theme": campaign.get("content_theme"),
                "primary_channel": campaign.get("primary_channel"),
                "creative_outputs": _split_csv(campaign.get("creative_outputs")),
                "notes": campaign.get("notes"),
            },
            "creative_control": {
                "ads_num_angles": _to_int(creative_control.get("ads_num_angles")),
                "ads_variants_per_angle": _to_int(
                    creative_control.get("ads_variants_per_angle")
                ),
                "organic_num_posts": _to_int(creative_control.get("organic_num_posts")),
                "organic_goal": creative_control.get("organic_goal"),
                "video_num_concepts": _to_int(
                    creative_control.get("video_num_concepts")
                ),
                "video_mapping_mode": creative_control.get("video_mapping_mode"),
                "image_num_concepts": _to_int(
                    creative_control.get("image_num_concepts")
                ),
                "image_mapping_mode": creative_control.get("image_mapping_mode"),
                "creative_style_ids": selected_style_ids,
                "selected_styles": selected_styles,
                "notes": creative_control.get("notes"),
            },
            "strategy_output": strategy_output,
        }
