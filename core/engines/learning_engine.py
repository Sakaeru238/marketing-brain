import json
from collections import Counter, defaultdict
from core.config.paths import PERFORMANCE_DIR


class LearningEngine:
    def __init__(self):
        self.experiments_dir = PERFORMANCE_DIR / "experiments"

    def load_experiments(self):

        if not self.experiments_dir.exists():
            return []

        experiment_files = sorted(self.experiments_dir.glob("creative_*.json"))

        experiments = []

        for file_path in experiment_files:

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            experiments.append(
                {
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                    "data": data,
                }
            )

        return experiments

    def summarize(self):

        experiments = self.load_experiments()

        return {
            "total_experiments": len(experiments),
            "experiment_files": [exp["file_name"] for exp in experiments],
        }

    def learning_memory(self):

        experiments = self.load_experiments()

        skill_counter = Counter()
        objective_counter = Counter()

        performance_skill_scores = defaultdict(list)
        performance_objective_scores = defaultdict(list)

        for exp in experiments:

            data = exp["data"]

            if "creative" in data:
                creative_data = data["creative"]["data"]
            elif "data" in data:
                creative_data = data["data"]
            else:
                continue

            creative_ideas = creative_data.get("creative_ideas", [])
            performance_items = creative_data.get("performance", [])

            for idea in creative_ideas:

                skill = idea.get("skill")
                objective = idea.get("objective")

                if skill:
                    skill_counter[skill] += 1

                if objective:
                    objective_counter[objective] += 1

            for item in performance_items:

                skill = item.get("skill")
                objective = item.get("objective")
                score = item.get("score", 0)

                if skill is not None:
                    performance_skill_scores[skill].append(score)

                if objective is not None:
                    performance_objective_scores[objective].append(score)

        avg_skill_scores = {
            skill: round(sum(scores) / len(scores), 2)
            for skill, scores in performance_skill_scores.items()
            if scores
        }

        avg_objective_scores = {
            objective: round(sum(scores) / len(scores), 2)
            for objective, scores in performance_objective_scores.items()
            if scores
        }

        top_performance_skills = sorted(
            avg_skill_scores.items(), key=lambda x: x[1], reverse=True
        )[:10]

        top_performance_objectives = sorted(
            avg_objective_scores.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "top_skills": skill_counter.most_common(10),
            "top_objectives": objective_counter.most_common(10),
            "top_performance_skills": top_performance_skills,
            "top_performance_objectives": top_performance_objectives,
            "total_experiments": len(experiments),
        }
