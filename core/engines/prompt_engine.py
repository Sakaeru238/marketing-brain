class PromptEngine:

    def generate(self, creative_idea):

        objective = creative_idea["objective"]
        skill = creative_idea["skill"]

        return {
            "image_prompt": f"Create marketing image for {objective} using {skill}",
            "video_prompt": f"Create video ad for {objective} using {skill}",
            "ad_prompt": f"Write ad copy for {objective} using {skill}",
        }