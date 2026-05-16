from collections import Counter


class SkillScorer:

    def score(self, learning_memory):

        skills = learning_memory.get("top_skills", [])

        skill_scores = {}

        for skill, count in skills:

            # score đơn giản ban đầu
            score = count

            skill_scores[skill] = score

        return skill_scores

    def rank(self, skill_scores):

        ranked = sorted(skill_scores.items(), key=lambda x: x[1], reverse=True)

        return ranked
