from pathlib import Path


class CreativeStrategyWrapper:
    """
    Wrapper for external creative strategy repo
    """

    def __init__(self):

        # project root
        self.project_root = Path(__file__).resolve().parents[3]

        # external repo path
        self.repo_path = (
            self.project_root
            / "external"
            / "strategy"
            / "creative-strategy-skills"
        )

    def get_repo_path(self):
        return self.repo_path

    def validate(self):
        if not self.repo_path.exists():
            raise FileNotFoundError(
                f"Creative strategy repo not found: {self.repo_path}"
            )

        return True