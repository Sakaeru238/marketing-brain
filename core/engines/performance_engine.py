import random


class PerformanceEngine:

    def simulate(self, creative_ideas):

        performance = []

        for idea in creative_ideas:

            score = random.randint(1, 100)

            performance.append(
                {
                    "objective": idea["objective"],
                    "skill": idea["skill"],
                    "score": score,
                }
            )

        return performance
