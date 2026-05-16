from pathlib import Path


class SkillLoader:
    def __init__(self, strategy_repo):
        self.strategy_repo = Path(strategy_repo)

    def load_skills(self):
        skills = []

        for item in sorted(self.strategy_repo.iterdir()):
            if item.is_dir():
                skill_file = item / "SKILL.md"

                if skill_file.exists():
                    skills.append(
                        {
                            "name": item.name,
                            "path": str(skill_file),
                        }
                    )

        return skills