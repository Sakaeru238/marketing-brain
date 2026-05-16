class CampaignGenerator:
    def generate(self, creative_ideas):
        campaigns = []

        for idx, idea in enumerate(creative_ideas, start=1):
            objective = idea["objective"]
            skill = idea["skill"]

            campaign = {
                "campaign_id": f"campaign_{idx}",
                "campaign_name": f"{objective} | {skill}",
                "objective": objective,
                "angle": idea["idea"],
                "primary_text": f"Discover a new campaign direction: {objective} powered by {skill}.",
                "headline": f"{objective} with {skill}",
                "cta": "Learn More",
                "prompts": idea.get("prompts", {}),
            }

            campaigns.append(campaign)

        return campaigns
