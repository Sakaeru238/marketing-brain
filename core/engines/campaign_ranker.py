class CampaignRanker:
    def rank(self, campaigns, feedback_summary):
        best_objectives = dict(feedback_summary.get("best_objectives", []))

        best_skills = dict(feedback_summary.get("best_skills", []))

        ranked_campaigns = []

        for campaign in campaigns:
            objective = campaign["objective"]
            campaign_name = campaign["campaign_name"]
            prompts = campaign.get("prompts", {})

            skill = campaign_name.split(" | ")[-1]

            objective_score = best_objectives.get(objective, 0)
            skill_score = best_skills.get(skill, 0)

            prompt_score = 0
            if prompts.get("image_prompt"):
                prompt_score += 1
            if prompts.get("video_prompt"):
                prompt_score += 1
            if prompts.get("ad_prompt"):
                prompt_score += 1

            total_score = round(objective_score + skill_score + prompt_score, 2)

            enriched = dict(campaign)
            enriched["objective_score"] = objective_score
            enriched["skill_score"] = skill_score
            enriched["prompt_score"] = prompt_score
            enriched["ranking_score"] = total_score

            ranked_campaigns.append(enriched)

        ranked_campaigns = sorted(
            ranked_campaigns, key=lambda x: x["ranking_score"], reverse=True
        )

        return ranked_campaigns
