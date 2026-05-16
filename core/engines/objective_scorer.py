class ObjectiveScorer:
    def score(self, current_objectives, learning_memory):

        learned_objectives = dict(learning_memory.get("top_objectives", []))

        objective_scores = {}

        for obj in current_objectives:
            base_score = 1
            learned_score = learned_objectives.get(obj, 0)
            objective_scores[obj] = base_score + learned_score

        return objective_scores

    def rank(self, objective_scores):

        ranked = sorted(objective_scores.items(), key=lambda x: x[1], reverse=True)

        return ranked
