from core.wrappers.strategy.creative_strategy_wrapper import CreativeStrategyWrapper
from core.engines.skill_loader import SkillLoader
from core.engines.prompt_engine import PromptEngine
from core.engines.skill_scorer import SkillScorer
from core.engines.learning_engine import LearningEngine
from core.engines.performance_engine import PerformanceEngine


class CreativePipeline:
    def __init__(self):
        self.wrapper = CreativeStrategyWrapper()
        self.prompt_engine = PromptEngine()
        self.learning_engine = LearningEngine()
        self.skill_scorer = SkillScorer()

    def _clean(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower() == "nan":
            return None
        return text

    def _build_context(self, brand_intake):
        if not brand_intake:
            return {}

        brand = brand_intake.get("brand", {}) or {}
        product = brand_intake.get("product", {}) or {}
        offer = brand_intake.get("offer", {}) or {}
        audience_core = brand_intake.get("audience_core", {}) or {}

        return {
            "brand_name": self._clean(brand.get("brand_name")),
            "product_name": self._clean(product.get("product_name")),
            "offer_text": self._clean(offer.get("offer_text")),
            "audience_name": self._clean(audience_core.get("audience_name")),
            "pain_point": self._clean(audience_core.get("pain_point")),
            "desired_outcome": self._clean(audience_core.get("desired_outcome")),
            "message_pillars": brand_intake.get("message_pillars", []) or [],
            "creative_angles": brand_intake.get("creative_angles", []) or [],
            "guardrails": brand_intake.get("guardrails", []) or [],
        }

    def _build_idea_text(self, objective, skill_name, context):
        brand_name = context.get("brand_name")
        product_name = context.get("product_name")
        audience_name = context.get("audience_name")
        pain_point = context.get("pain_point")
        desired_outcome = context.get("desired_outcome")
        offer_text = context.get("offer_text")
        message_pillars = context.get("message_pillars", [])
        creative_angles = context.get("creative_angles", [])

        parts = []

        if brand_name and product_name:
            parts.append(f"{brand_name} | {product_name}")
        elif brand_name:
            parts.append(brand_name)

        parts.append(objective)

        if audience_name:
            parts.append(f"Audience: {audience_name}")

        if pain_point and desired_outcome:
            parts.append(f"Tension: {pain_point} -> {desired_outcome}")

        if creative_angles:
            parts.append(f"Angle: {creative_angles[0]}")

        if message_pillars:
            parts.append(f"Proof: {message_pillars[0]}")

        if offer_text:
            parts.append(f"Offer: {offer_text}")

        parts.append(f"Skill lens: {skill_name}")

        return " | ".join(parts)

    def run(self, strategy_output, brand_intake=None):
        self.wrapper.validate()

        strategy_data = strategy_output["data"]["strategy_summary"]
        objectives = strategy_data["recommended_objectives"]

        learning_memory = self.learning_engine.learning_memory()

        performance_skills = learning_memory.get("top_performance_skills", [])

        performance_objectives = learning_memory.get("top_performance_objectives", [])

        if performance_skills:
            ranked_skills = performance_skills
        else:
            skill_scores = self.skill_scorer.score(learning_memory)
            ranked_skills = self.skill_scorer.rank(skill_scores)

        self.performance_engine = PerformanceEngine()

        repo = self.wrapper.get_repo_path()

        loader = SkillLoader(repo)
        skills = loader.load_skills()

        ranked_names = [s[0] for s in ranked_skills]
        top_objective_names = [o[0] for o in performance_objectives[:3]]

        skills = sorted(
            skills,
            key=lambda x: (
                ranked_names.index(x["name"]) if x["name"] in ranked_names else 999
            ),
        )

        context = self._build_context(brand_intake)
        creative_ideas = []

        for obj in objectives:
            for skill in skills:

                skill_name = skill["name"].lower()
                objective_name = obj.lower()

                if "hook" in skill_name and (
                    "pain" in objective_name
                    or "proof" in objective_name
                    or "positioning" in objective_name
                    or "turn '" in objective_name
                ):
                    selected = True
                elif "visual" in skill_name and (
                    "show" in objective_name
                    or "product" in objective_name
                    or "glance" in objective_name
                ):
                    selected = True
                elif "strategy" in skill_name:
                    selected = True
                else:
                    selected = False

                if not selected:
                    continue

                if top_objective_names and obj not in top_objective_names:
                    continue

                creative_idea = {
                    "objective": obj,
                    "skill": skill["name"],
                    "idea": self._build_idea_text(obj, skill["name"], context),
                    "brand_context": context,
                }

                prompts = self.prompt_engine.generate(creative_idea)
                creative_idea["prompts"] = prompts

                creative_ideas.append(creative_idea)

        performance = self.performance_engine.simulate(creative_ideas)

        return {
            "stage": "creative",
            "status": "ready",
            "input_stage": strategy_output["stage"],
            "data": {
                "skills_used": [s["name"] for s in skills],
                "creative_ideas": creative_ideas,
                "performance": performance,
            },
        }